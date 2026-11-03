"""Economic invariants and lifecycle behavior of the synthetic quote-cycle model."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import pytest
from algooptionx.paper.engine import PaperError
from algooptionx.paper.orderbook import ExecutionBook, LOT, FEE
from algooptionx.saas.runtime import TenantRuntime


@pytest.fixture
def book(tmp_path):
    source={'session':{'id':'test-source','connected':True,'tick':60,'quote_tick':60,'quote_time':'2026-01-01T10:15:00+05:30','killed':False},'contracts':[
        {'id':'short-put','strike':100,'right':'PE','expiry':'2026-01-08T15:30:00+05:30','bid':2000,'ask':2080,'lot_size':65},
        {'id':'long-put','strike':90,'right':'PE','expiry':'2026-01-08T15:30:00+05:30','bid':1000,'ask':1080,'lot_size':65}]}
    return ExecutionBook(tmp_path/'execution.db',lambda:deepcopy(source)),source


def ticket(book,lots=1,kind='MARKET',**fields):
    return {'expected_account_id':book.state()['account']['id'],'kind':kind,'lots':lots,'legs':[{'instrument':'short-put','side':-1},{'instrument':'long-put','side':1}],'trigger_direction':'above',**fields}


def place(book,body,key='place-once'):
    preview=book.preview(body)
    assert preview['valid'], preview['errors']
    return book.command(key,'place',body|{'preview_token':preview['preview_token']})


def test_partial_fills_close_and_balanced_reconciliation(book):
    engine,_=book;body=ticket(engine,lots=2);accepted=place(engine,body)
    assert engine.state()['orders'][0]['status']=='WORKING'
    engine.process();state=engine.state()
    assert state['orders'][0]['status']=='PARTIALLY_FILLED' and state['positions'][0]['lots']==1
    engine.process();state=engine.state()
    assert state['orders'][0]['status']=='FILLED' and state['positions'][0]['lots']==2
    assert len(state['fills'])==2
    assert engine.audit(body['expected_account_id'])['reconciled']
    engine.command('close-once','close',{'expected_account_id':body['expected_account_id'],'position_id':accepted['order_id']})
    engine.process();engine.process();final=engine.state()
    assert final['positions']==[]
    assert final['account']['cash']==final['account']['capital']+final['account']['realized']
    assert final['account']['fees']==4*2*FEE
    assert engine.audit(body['expected_account_id'])['reconciled']


def test_concurrent_idempotency_and_fill_time_risk_gate(book):
    engine,source=book;body=ticket(engine,lots=2);preview=engine.preview(body);request=body|{'preview_token':preview['preview_token']}
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:engine.command('same-key','place',request),range(2)))
    assert results[0]==results[1] and len(engine.state()['orders'])==1
    # A quote change makes the remaining order exceed available cash / risk.
    source['contracts'][1]['bid']=2_000_000;source['contracts'][1]['ask']=2_000_080
    before=engine.state()['account']['cash'];engine.process();state=engine.state()
    assert state['orders'][0]['status']=='REJECTED' and state['account']['cash']==before and not state['fills']


def test_limit_stop_cancel_revision_and_stale_preview(book):
    engine,source=book
    body=ticket(engine,kind='STOP_LIMIT',limit_paise=-900,stop_paise=-800)
    placed=place(engine,body)
    engine.process();order=engine.state()['orders'][0]
    assert order['filled']==0
    with pytest.raises(PaperError):engine.command('bad-revision','cancel',{'expected_account_id':body['expected_account_id'],'order_id':placed['order_id'],'expected_revision':0})
    engine.command('cancel','cancel',{'expected_account_id':body['expected_account_id'],'order_id':placed['order_id'],'expected_revision':order['revision']})
    assert engine.state()['orders'][0]['status']=='CANCELED'
    fresh=ticket(engine);preview=engine.preview(fresh)
    source['session']['quote_tick']+=1;source['session']['tick']+=1
    with pytest.raises(PaperError):engine.command('stale','place',fresh|{'preview_token':preview['preview_token']})


def test_kill_latches_and_source_disconnect_preserves_residual_exposure(book):
    engine,source=book;body=ticket(engine);place(engine,body);engine.process()
    source['session']['connected']=False
    result=engine.command('kill','kill',{'expected_account_id':body['expected_account_id']})
    assert result['killed'] and result['close_orders']
    engine.process();assert engine.state()['positions']
    assert not engine.preview(ticket(engine))['valid']
    source['session']['connected']=True;engine.process()
    assert not engine.state()['positions'] and engine.state()['account']['killed']
    assert engine.audit(body['expected_account_id'])['reconciled']


def test_account_switch_history_and_tampering_detected(book):
    engine,_=book;previous=engine.state()['account']['id']
    new=engine.new_account(50_000_000,previous)['account_id']
    assert len(engine.history()['accounts'])==2
    with pytest.raises(PaperError):engine.command('old-account','kill',{'expected_account_id':previous})
    assert engine.audit(previous)['reconciled'] and engine.audit(new)['reconciled']
    with engine.tx() as c:c.execute('UPDATE accounts SET cash=cash+1 WHERE id=?',(new,))
    assert not engine.audit(new)['reconciled']


def test_restart_recovers_persisted_tenant_books(tmp_path):
    tenant='a'*32;runtime=TenantRuntime(tmp_path/'tenants');_,demo=runtime.get(tenant)
    book=runtime.execution(tenant)
    assert book.audit(book.state()['account']['id'])['reconciled']
    reloaded=TenantRuntime(tmp_path/'tenants');assert not reloaded.execution_books
    reloaded.recover([tenant])
    assert tenant in reloaded.execution_books and not reloaded.execution_errors
    with reloaded.execution_books[tenant].tx() as c:c.execute('UPDATE accounts SET cash=cash+1')
    damaged=TenantRuntime(tmp_path/'tenants');damaged.recover([tenant])
    assert tenant in damaged.execution_errors

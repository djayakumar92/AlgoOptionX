"""Checkpoint regression tests for the isolated enterprise demo backend."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from algooptionx.demo.engine import DemoEngine,DemoError,CAPITAL
from algooptionx.api.app import create_app


def send(engine,action,key,**fields):
    return engine.command({'action':action,'key':key,'session_id':engine.state()['session']['id'],**fields})


def open_trade(engine,key='open'):
    preview=engine.preview({})
    return send(engine,'open',key,draft={},quote_token=preview['quote_token'])


def test_atomic_roundtrip_idempotency_and_restart(tmp_path):
    e=DemoEngine(tmp_path/'demo.db');before=e.state();preview=e.preview({})
    body={'action':'open','key':'once','session_id':before['session']['id'],'draft':{},'quote_token':preview['quote_token']}
    with ThreadPoolExecutor(2) as pool: results=list(pool.map(e.command,[body,body]))
    assert results[0]==results[1] and len(e.state()['positions'])==1
    opened=e.state();assert opened['account']['cash']==CAPITAL+preview['entry_net_credit']
    assert opened['account']['equity']<CAPITAL and opened['account']['reserve']==preview['reserve']
    closed=send(e,'close','close',position_id=results[0]['position_id']);assert closed['ok']
    final=DemoEngine(tmp_path/'demo.db').state()
    assert not final['positions'] and final['account']['cash']==CAPITAL+closed['pnl']
    assert final['account']['realized']==closed['pnl'] and final['account']['fees']==preview['entry_fees']+preview['exit_fees']


def test_risk_rejection_stale_quote_and_history_preservation(tmp_path):
    e=DemoEngine(tmp_path/'demo.db');p=e.preview({});send(e,'step','step')
    assert not send(e,'open','stale',draft={},quote_token=p['quote_token'])['ok']
    send(e,'session','scenario',scenario='risk-rejection');before=e.state()['account'];p=e.preview({})
    assert not p['valid'] and not send(e,'open','risk',draft={},quote_token=p['quote_token'])['ok']
    assert e.state()['account']==before
    assert any(event['kind']=='REJECTED' for event in e.state()['events'])


def test_disconnection_kill_failure_latches_and_retry_flattens(tmp_path,monkeypatch):
    e=DemoEngine(tmp_path/'demo.db');assert open_trade(e)['ok'];send(e,'disconnect','disconnect');tick=e.state()['session']['quote_tick']
    send(e,'step','step');assert e.state()['session']['quote_tick']==tick
    original=e._exit
    def fail(*args,**kwargs): raise RuntimeError('Injected flatten failure')
    monkeypatch.setattr(e,'_exit',fail)
    with pytest.raises(RuntimeError):send(e,'kill','kill-failed')
    restarted=DemoEngine(tmp_path/'demo.db');assert restarted.state()['session']['killed'] and len(restarted.state()['positions'])==1
    monkeypatch.setattr(e,'_exit',original)
    assert send(e,'kill','retry')['ok'];state=e.state()
    assert not state['positions'] and state['session']['killed']
    assert state['journal'][0]['data']['quote_source']=='LAST_VALID_SYNTHETIC'
    assert not e.preview({})['valid']


def test_demo_rejects_existing_database_alias_and_preserves_api(tmp_path):
    original=tmp_path/'paper.db';original.write_bytes(b'preserve history')
    with pytest.raises(DemoError):DemoEngine(original,[original])
    assert original.read_bytes()==b'preserve history'
    with TestClient(create_app(tmp_path/'original.db',background=False)) as client:
        assert client.get('/api/health').json()['mode']=='PAPER'
        state=client.get('/api/demo/state').json();assert state['mode']=='DEMO'
        assert len(json.dumps(state).encode())<1_000_000
        assert client.post('/api/demo/commands',json={'action':'live','key':'x','session_id':state['session']['id']}).status_code==422
        assert client.post('/api/demo/commands',json={'action':'step','key':'x','session_id':state['session']['id']},headers={'Origin':'https://untrusted.example'}).status_code==403


def test_projected_daily_loss_includes_entry_costs_and_equality(tmp_path):
    e=DemoEngine(tmp_path/'demo.db');p=e.preview({});a=e.state()['session']
    friction=p['entry_fees']+p['exit_fees']+2*len(p['legs'])*45*p['quantity']
    limit=e.state()['limits']['daily_loss_limit']
    for remaining,allowed in [(friction+1,True),(friction,False),(1,False)]:
        with e.tx() as c:c.execute('UPDATE demo_accounts SET cash=? WHERE id=?',(CAPITAL-limit+remaining,a['id']))
        preview=e.preview({});assert preview['valid']==allowed
        if not allowed:
            before=e.state()['account'];result=send(e,'open',f'boundary-{remaining}',draft={},quote_token=preview['quote_token'])
            assert not result['ok'] and e.state()['account']==before


def test_failed_flatten_keeps_latch_and_failure_audit(tmp_path,monkeypatch):
    e=DemoEngine(tmp_path/'demo.db');assert open_trade(e)['ok']
    def fail(*args,**kwargs):raise RuntimeError('Injected failure')
    monkeypatch.setattr(e,'_exit',fail)
    with pytest.raises(RuntimeError):send(e,'kill','failed')
    state=DemoEngine(tmp_path/'demo.db').state();kinds=[event['kind'] for event in state['events']]
    assert state['session']['killed'] and state['positions']
    assert 'KILL_LATCH' in kinds and 'KILL_FAILED' in kinds and 'CLOSE' not in kinds


def test_latch_audit_failure_still_blocks_entries(tmp_path,monkeypatch):
    e=DemoEngine(tmp_path/'demo.db');original=e._event
    def fail(c,a,kind,payload):
        if kind=='KILL_LATCH':raise RuntimeError('Injected audit failure')
        return original(c,a,kind,payload)
    monkeypatch.setattr(e,'_event',fail)
    with pytest.raises(RuntimeError):send(e,'kill','failed-audit')
    restarted=DemoEngine(tmp_path/'demo.db')
    assert restarted.state()['session']['killed'] and not restarted.preview({})['valid']


def test_research_drawdown_reconciles_every_curve_point():
    from algooptionx.demo.research import evaluate
    result=evaluate('bullish','bull-put')
    for part in [result['in_sample'],result['out_of_sample'],*result['folds']]:
        peak=50_000_000;drawdown=0
        for point in part['curve']:
            peak=max(peak,point['equity']);drawdown=max(drawdown,peak-point['equity'])
        assert drawdown==part['max_drawdown']
        assert part['curve'][1]['tick']==part['start_tick'] and part['curve'][1]['equity']<50_000_000


def test_audit_failure_never_releases_unlatched_entry_window(tmp_path,monkeypatch):
    from contextlib import contextmanager
    e=DemoEngine(tmp_path/'demo.db');peer=DemoEngine(tmp_path/'demo.db')
    snapshot=e.state();preview=e.preview({});responses=[];first=True;original_tx=e.tx;original_event=e._event
    entry={'action':'open','key':'racing-entry','session_id':snapshot['session']['id'],'draft':{},'quote_token':preview['quote_token']}
    @contextmanager
    def interleaved():
        nonlocal first
        initial=first;first=False
        try:
            with original_tx() as c:yield c
        finally:
            if initial:responses.append(peer.command(entry))
    def fail(c,a,kind,payload):
        if kind=='KILL_LATCH':raise RuntimeError('Audit failure at latch boundary')
        return original_event(c,a,kind,payload)
    monkeypatch.setattr(e,'tx',interleaved);monkeypatch.setattr(e,'_event',fail)
    with pytest.raises(RuntimeError):e.command({'action':'kill','key':'kill-race','session_id':snapshot['session']['id']})
    assert responses and responses[0]['ok'] is False
    assert peer.state()['session']['killed'] and peer.state()['positions']==[]

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

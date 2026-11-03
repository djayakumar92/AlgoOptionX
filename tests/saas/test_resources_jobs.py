"""Immutable versions, ownership and causal replay contracts."""
from copy import deepcopy
import pytest
from pydantic import ValidationError
from algooptionx.demo import market
from algooptionx.demo.engine import DemoEngine
from algooptionx.saas.identity import IdentityStore
from algooptionx.saas.jobs import JobStore, ReplayJob, evaluate
from algooptionx.saas.resources import ResourceStore, StrategyWrite, StrategyDocument, WorkspaceDocument, WorkspaceWrite


def customer(store,email):
    return store.authenticate(store.register(email,'test-only-long-password','Tester','local')[0])


def test_documents_reject_nonfinite_geometry_and_empty_rules():
    for value in (float('inf'),float('nan'),0,-1,10):
        with pytest.raises(ValidationError):WorkspaceDocument(pane_weights=[value])
    with pytest.raises(ValidationError):WorkspaceDocument(indicators=['EMA','EMA'])
    with pytest.raises(ValidationError):StrategyDocument(template='bull-put',groups=[{'operator':'AND','conditions':[]}])
    assert StrategyDocument(template='bull-put',groups=[])


def test_layout_revision_and_immutable_versions(tmp_path):
    identity=IdentityStore(tmp_path/'identity.db');store=ResourceStore(identity)
    user=customer(identity,'a@example.test');other=customer(identity,'b@example.test')
    write=WorkspaceWrite(expected_tenant_id=user['tenant_id'],name='Layout',document={})
    saved=store.workspace(user,write)
    with pytest.raises(Exception) as error:store.workspace(user,write,saved['id'])
    assert error.value.status_code==409
    with pytest.raises(Exception) as error:store.workspace(other,write,saved['id'])
    assert error.value.status_code==404
    revised=store.workspace(user,write.model_copy(update={'expected_revision':1}),saved['id'])
    assert revised['revision']==2
    strategy=StrategyWrite(expected_tenant_id=user['tenant_id'],name='Definition',document={'template':'bull-put'})
    first=store.strategy(user,strategy);second=store.strategy(user,strategy,first['id'])
    assert first['version']==1 and second['version']==2 and first['version_id']!=second['version_id']
    with identity.tx() as c:
        assert c.execute('SELECT COUNT(*) FROM strategy_versions').fetchone()[0]==2


def snapshot(tick=90):
    return {'strategy':{'template':'bull-put','groups':[{'operator':'AND','conditions':[{'field':'close','timeframe':'5','operator':'gt','value':0}]}]},'opening_gap_points':0,'bars':{str(i):market.candles('bullish',tick,i) for i in (5,30)}}


def test_replay_is_prefix_causal_and_no_rules_never_signal():
    first=evaluate(snapshot(60));later=evaluate(snapshot(90))
    assert first['evaluations']==later['evaluations'][:len(first['evaluations'])]
    value=snapshot();value['strategy']['groups']=[]
    assert evaluate(value)['evaluations']==[]
    value=snapshot();value['strategy']['groups'][0]['conditions'][0]['field']='ema9'
    result=evaluate(value)
    assert result['unavailable']==8 and result['evaluations'][8]['matched'] is True
    changed=deepcopy(value);changed['bars']['5'][-1]['close']=999999
    assert evaluate(changed)['evaluations'][:-1]==result['evaluations'][:-1]


def test_job_idempotency_snapshot_survives_source_change_and_restart(tmp_path):
    identity=IdentityStore(tmp_path/'identity.db');resources=ResourceStore(identity);jobs=JobStore(identity)
    user=customer(identity,'a@example.test');demo=DemoEngine(tmp_path/'demo.db')
    strategy=resources.strategy(user,StrategyWrite(expected_tenant_id=user['tenant_id'],name='Rule',document=snapshot()['strategy']))
    state=demo.state();body=ReplayJob(expected_tenant_id=user['tenant_id'],version_id=strategy['version_id'],key='replay-once',expected_source_session=state['session']['id'])
    result=jobs.create(user,body,state)
    assert jobs.create(user,body,state)==result
    demo.command({'session_id':state['session']['id'],'key':'advance','action':'step','steps':1})
    jobs=JobStore(identity);jobs.process()
    with identity.tx() as c:
        row=c.execute('SELECT status,snapshot,result FROM research_jobs WHERE id=?',(result['id'],)).fetchone()
        assert row['status']=='completed' and '"quote_tick":60' in row['snapshot']
        assert '"matched":true' in row['result']

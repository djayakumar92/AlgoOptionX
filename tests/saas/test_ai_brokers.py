"""No credential read-back and bounded, separately billed narrative inference."""
import json
from types import SimpleNamespace
import pytest
from algooptionx.demo.engine import DemoEngine
from algooptionx.saas.ai import AiStore,AiRequest
from algooptionx.saas.brokers import BrokerStore,Connection
from algooptionx.saas.commerce import Commerce
from algooptionx.saas.identity import IdentityStore,IdentityError
from algooptionx.saas.jobs import JobStore,ReplayJob
from algooptionx.saas.resources import ResourceStore,StrategyWrite


def user(store,email='a@example.test'):
    return store.authenticate(store.register(email,'test-only-long-password','Tester','local')[0])


def test_broker_encryption_ownership_and_local_disconnect(tmp_path,monkeypatch):
    identity=IdentityStore(tmp_path/'identity.db');brokers=BrokerStore(identity);owner=user(identity);other=user(identity,'b@example.test')
    body=Connection(expected_tenant_id=owner['tenant_id'],broker='dhan',label='Test',client_id='test-only-client',access_token='test-only-access-token')
    saved=brokers.save(owner,body)
    assert not brokers.list(other)
    assert 'access_token' not in json.dumps(brokers.list(owner))
    with identity.tx() as c:
        ciphertext=c.execute('SELECT encrypted_credentials FROM broker_connections').fetchone()[0]
        assert body.access_token not in ciphertext and body.client_id not in ciphertext
    with pytest.raises(IdentityError):brokers.disconnect(other,saved['id'])
    monkeypatch.setattr('algooptionx.saas.brokers.requests.get',lambda *args,**kwargs:SimpleNamespace(status_code=200,json=lambda:{'availableBalance':1}))
    result=brokers.test(owner,saved['id']);assert result['capabilities']['account_read'] and not result['capabilities']['order_submission']
    brokers.disconnect(owner,saved['id'])
    with pytest.raises(IdentityError):brokers.test(owner,saved['id'])
    with identity.tx() as c:assert c.execute('SELECT encrypted_credentials FROM broker_connections').fetchone()[0]==''


class PaymentProvider:
    configured=True;key='rzp_test_fixture';webhook_secret='test-only'
    def call(self,method,path,body):return {'id':'order_fixture','amount':body['amount'],'currency':'INR'}


class NarrativeProvider:
    configured=True;model='test-model';units=3
    def __init__(self):self.calls=0;self.fail=False
    def generate(self,evidence):
        self.calls+=1
        assert 'private notes' not in json.dumps(evidence)
        if self.fail:raise IdentityError('Test provider failed.')
        return {'summary':'Synthetic rule observations, not a forecast.','limitations':['Synthetic inputs only.'],'citations':[evidence['observations'][0]['id']]}


def test_ai_reservation_idempotency_failure_and_uncertain_restart(tmp_path):
    identity=IdentityStore(tmp_path/'identity.db');owner=user(identity);resources=ResourceStore(identity);jobs=JobStore(identity)
    commerce=Commerce(identity,PaymentProvider(),{'pro':{'amount_paise':10000,'credits':100}})
    checkout=commerce.checkout(owner['tenant_id'],'pro','fixture-purchase')
    with identity.tx() as c:commerce._capture(c,{'id':'pay_fixture','order_id':checkout['provider_order'],'amount':10000,'currency':'INR','status':'captured'})
    strategy=resources.strategy(owner,StrategyWrite(expected_tenant_id=owner['tenant_id'],name='Rules',document={'template':'bull-put','notes':'private notes','groups':[{'conditions':[{'field':'close','timeframe':'5','operator':'gt','value':0}]}]}))
    demo=DemoEngine(tmp_path/'demo.db');snapshot=demo.state()
    job=jobs.create(owner,ReplayJob(expected_tenant_id=owner['tenant_id'],version_id=strategy['version_id'],key='fixture-research',expected_source_session=snapshot['session']['id']),snapshot)
    jobs.process();provider=NarrativeProvider();ai=AiStore(identity,commerce,provider)
    body=AiRequest(expected_tenant_id=owner['tenant_id'],job_id=job['id'],key='fixture-narrative',accept_external_processing=True)
    first=ai.create(owner,body);assert ai.create(owner,body)==first
    assert commerce.snapshot(owner['tenant_id'])['credits']==97
    ai.process();assert provider.calls==1 and commerce.snapshot(owner['tenant_id'])['credits']==97
    provider.fail=True
    ai.create(owner,body.model_copy(update={'key':'fixture-failure'}));ai.process()
    assert commerce.snapshot(owner['tenant_id'])['credits']==97
    pending=ai.create(owner,body.model_copy(update={'key':'fixture-interrupted'}))
    with identity.tx() as c:c.execute("UPDATE ai_reports SET status='running' WHERE id=?",(pending['id'],))
    recovered=AiStore(identity,commerce,provider);recovered.process()
    assert provider.calls==2
    with identity.tx() as c:
        assert c.execute('SELECT status FROM ai_reports WHERE id=?',(pending['id'],)).fetchone()[0]=='uncertain'
        assert c.execute('SELECT COUNT(*) FROM usage_reservations WHERE status=\'reserved\'').fetchone()[0]==1

    from algooptionx.saas.ai import cancel,release
    from algooptionx.saas.api import TenantContext
    context=TenantContext(expected_tenant_id=owner['tenant_id'])
    request=SimpleNamespace(state=SimpleNamespace(principal=owner),app=SimpleNamespace(state=SimpleNamespace(identity=identity,commerce=commerce)))
    release(pending['id'],context,request)
    provider.fail=False;provider.model='old-model'
    incompatible=ai.create(owner,body.model_copy(update={'key':'older-model'}))
    provider.model='test-model'
    old_prompt=ai.create(owner,body.model_copy(update={'key':'older-prompt'}))
    with identity.tx() as c:c.execute("UPDATE ai_reports SET prompt_version='old-prompt' WHERE id=?",(old_prompt['id'],))
    eligible=ai.create(owner,body.model_copy(update={'key':'current-compatible'}))
    ai.process()
    with identity.tx() as c:
        assert c.execute('SELECT status FROM ai_reports WHERE id=?',(eligible['id'],)).fetchone()[0]=='completed'
        assert c.execute('SELECT status FROM ai_reports WHERE id=?',(incompatible['id'],)).fetchone()[0]=='queued'
        assert c.execute('SELECT status FROM ai_reports WHERE id=?',(old_prompt['id'],)).fetchone()[0]=='queued'
    before=commerce.snapshot(owner['tenant_id'])['credits']
    assert cancel(incompatible['id'],context,request)=={'status':'cancelled'}
    assert cancel(incompatible['id'],context,request)=={'status':'cancelled'}
    assert commerce.snapshot(owner['tenant_id'])['credits']==before+provider.units
    cancel(old_prompt['id'],context,request)


def test_ai_provider_schema_rejects_invented_citations(monkeypatch):
    from algooptionx.saas.ai import NarrativeProvider as Adapter
    adapter=Adapter();adapter.enabled=True;adapter.key='test-only';adapter.model='fixture';adapter.units=1
    value={'summary':'Synthetic example','limitations':['Synthetic only'],'citations':['invented-source']}
    monkeypatch.setattr('algooptionx.saas.ai.requests.post',lambda *args,**kwargs:SimpleNamespace(status_code=200,json=lambda:{'choices':[{'message':{'content':json.dumps(value)}}]}))
    with pytest.raises(IdentityError):adapter.generate({'observations':[{'id':'observation-1'}]})

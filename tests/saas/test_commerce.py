"""Signed payment replay, balanced ledgers and independent refunded periods."""
import hashlib
import hmac
import json
import pytest
from algooptionx.saas.identity import IdentityStore, IdentityError
from algooptionx.saas.commerce import Commerce


class TestProvider:
    __test__=False
    configured=True
    key='rzp_test_fixture'
    webhook_secret='test-only-webhook-secret'
    def __init__(self):self.orders=0
    def call(self,method,path,body):
        self.orders+=1
        return {'id':f'order_{self.orders}','amount':body['amount'],'currency':'INR'}


def event(commerce,kind,entity,event_id):
    entity_type='refund' if kind.startswith('refund.') else 'payment'
    raw=json.dumps({'id':event_id,'event':kind,'payload':{entity_type:{'entity':entity}}}).encode()
    return commerce.webhook(raw,hmac.new(commerce.provider.webhook_secret.encode(),raw,hashlib.sha256).hexdigest())


def test_captured_payment_is_once_and_refund_preserves_other_periods(tmp_path):
    identity=IdentityStore(tmp_path/'identity.db');user=identity.authenticate(identity.register('a@example.test','test-only-long-password','Tester','local')[0]);tenant=user['tenant_id']
    commerce=Commerce(identity,TestProvider(),{'trader':{'amount_paise':10000,'credits':100}})
    first=commerce.checkout(tenant,'trader','checkout-one')
    assert commerce.checkout(tenant,'trader','checkout-one')==first and commerce.provider.orders==1
    payment={'id':'pay_first','order_id':first['provider_order'],'amount':10000,'currency':'INR','status':'captured'}
    event(commerce,'payment.captured',payment,'event-one');event(commerce,'payment.captured',payment,'event-two')
    assert commerce.snapshot(tenant)['credits']==100
    second=commerce.checkout(tenant,'trader','checkout-two')
    event(commerce,'payment.captured',payment|{'id':'pay_second','order_id':second['provider_order']},'event-three')
    event(commerce,'refund.processed',{'id':'rfnd_one','payment_id':'pay_second','amount':10000},'refund-one')
    snapshot=commerce.snapshot(tenant)
    assert snapshot['subscription']['plan']=='trader' and snapshot['subscription']['status']=='active' and snapshot['credits']==100
    with pytest.raises(IdentityError):event(commerce,'refund.processed',{'id':'rfnd_one','payment_id':'pay_first','amount':10000},'refund-conflict')
    with identity.tx() as c:
        assert c.execute('SELECT COUNT(*) FROM payment_transactions').fetchone()[0]==2
        assert c.execute('SELECT SUM(amount) FROM payment_postings').fetchone()[0]==0
        assert c.execute('SELECT SUM(units) FROM credit_postings').fetchone()[0]==0
    with pytest.raises(IdentityError):commerce.webhook(b'{}','0'*64)


def test_usage_reservation_is_idempotent_and_releases_unused_units(tmp_path):
    identity=IdentityStore(tmp_path/'identity.db');tenant=identity.authenticate(identity.register('a@example.test','test-only-long-password','Tester','local')[0])['tenant_id'];commerce=Commerce(identity)
    with identity.tx() as c:commerce.credit(c,tenant,'fixture','FIXTURE',100)
    reserved=commerce.reserve(tenant,'request-once','ai',20)
    assert commerce.reserve(tenant,'request-once','ai',20)==reserved
    assert commerce.snapshot(tenant)['credits']==80
    commerce.settle(tenant,reserved['id'],7);commerce.settle(tenant,reserved['id'],7)
    assert commerce.snapshot(tenant)['credits']==93
    with pytest.raises(IdentityError):commerce.settle(tenant,reserved['id'],8)

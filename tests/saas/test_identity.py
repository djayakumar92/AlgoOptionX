"""Security invariants for customer sessions, tenant context and authenticator flows."""
import time
import pytest
from fastapi.testclient import TestClient
from algooptionx.api.app import create_app
from algooptionx.saas.api import CSRF_COOKIE
from algooptionx.saas.identity import IdentityError, IdentityStore, digest
from algooptionx.saas.mfa import totp

PASSWORD = 'test-only-long-password'


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path/'paper.db', background=False, secure_cookies=False)) as value:
        yield value


def signup(client, email='owner@example.test'):
    response = client.post('/api/identity/register', json={'email':email,'password':PASSWORD,'name':'Test Owner'})
    assert response.status_code == 200
    return response.json()['user']


def post(client,path,body):
    return client.post(path,json=body,headers={'X-AlgoOptionX-CSRF':client.cookies.get(CSRF_COOKIE,'')})


def test_opaque_cookies_csrf_and_no_password_echo(client):
    user = signup(client)
    assert client.get('/api/identity/me').json()['user']['user_id'] == user['user_id']
    assert client.post('/api/identity/profile',json={'name':'Changed'}).status_code == 403
    assert post(client,'/api/identity/profile',{'name':'Changed'}).status_code == 200
    invalid = client.post('/api/identity/login',json={'email':'owner@example.test','password':'sensitive-invalid','extra':'secret'})
    assert invalid.status_code == 422
    assert 'sensitive-invalid' not in invalid.text and 'secret' not in invalid.text
    assert client.post('/api/identity/logout',json={},headers={'Origin':'https://untrusted.example'}).status_code == 403
    assert 'csrf_hash' not in client.get('/api/identity/me').text


def test_tenant_context_and_anonymous_fallback_are_rejected(client):
    user = signup(client)
    response = post(client,'/api/resources/workspaces',{'name':'Owned layout','document':{},'expected_tenant_id':user['tenant_id']})
    assert response.status_code == 200
    headers={'X-AlgoOptionX-Client':'browser-v1','X-Expected-Tenant':'0'*32,'X-Expected-User':user['user_id']}
    assert client.get('/api/resources/workspaces',headers=headers).status_code == 409
    assert post(client,'/api/resources/workspaces',{'name':'Wrong tenant','document':{},'expected_tenant_id':'0'*32}).status_code == 409
    assert post(client,'/api/identity/logout',{}).status_code == 200
    assert client.get('/api/workspace',headers=headers).status_code == 401


def test_reset_is_single_use_and_revokes_sessions(tmp_path):
    class Mail:
        def send(self,email,purpose,token):self.token=token
    mail=Mail();store=IdentityStore(tmp_path/'identity.db',mail)
    session,_=store.register('a@example.test',PASSWORD,'A','local')
    store.issue_email('a@example.test','reset','local')
    store.consume_token(mail.token,'reset','another-test-password')
    assert store.authenticate(session) is None
    with pytest.raises(IdentityError):store.consume_token(mail.token,'reset','another-test-password')
    assert store.authenticate(store.login('a@example.test','another-test-password','local')[0])


def test_mfa_enrollment_recovery_and_replay_rejection(client):
    user=signup(client)
    previous_session=client.cookies.get('algooptionx_session')
    setup=post(client,'/api/identity/mfa/setup',{'password':PASSWORD})
    assert setup.status_code == 200
    secret=setup.json()['secret']
    code=totp(secret,int(time.time())//30)
    confirmed=post(client,'/api/identity/mfa/confirm',{'code':code})
    assert confirmed.status_code == 200
    recovery=confirmed.json()['recovery_codes']
    assert len(recovery)==8 and len(set(recovery))==8
    assert client.get('/api/identity/mfa').json()['enabled']
    if previous_session:assert client.app.state.identity.authenticate(previous_session) is None
    missing=client.post('/api/identity/login',json={'email':user['email'],'password':PASSWORD})
    assert missing.status_code == 401
    replay=client.post('/api/identity/login',json={'email':user['email'],'password':PASSWORD,'authentication_code':code})
    assert replay.status_code == 401
    used=client.post('/api/identity/login',json={'email':user['email'],'password':PASSWORD,'authentication_code':recovery[0]})
    assert used.status_code == 200
    assert client.post('/api/identity/login',json={'email':user['email'],'password':PASSWORD,'authentication_code':recovery[0]}).status_code == 401
    with client.app.state.identity.tx() as c:
        stored=c.execute('SELECT encrypted_secret FROM mfa_credentials').fetchone()[0]
        assert secret not in stored
        assert c.execute('SELECT used FROM mfa_recovery WHERE code_hash=?',(digest(recovery[0]),)).fetchone()[0] == 1


def test_hosted_access_requires_verification(tmp_path):
    with TestClient(create_app(tmp_path/'hosted.db',background=False,require_auth=True,secure_cookies=False)) as client:
        assert client.get('/api/workspace').status_code == 401
        signup(client)
        assert client.get('/api/workspace').status_code == 403
        assert client.get('/api/resources/workspaces').status_code == 403
        assert client.get('/api/jobs').status_code == 403
        assert client.get('/api/identity/me').status_code == 200


def test_membership_removal_revokes_sessions_and_outstanding_invites(client):
    class Mail:
        mode='file'
        def send(self,email,purpose,token):self.token=token
    mail=Mail();client.app.state.identity.mail=mail
    first=signup(client);first_cookies=dict(client.cookies)
    client.cookies.clear();second=signup(client,'second@example.test');second_cookies=dict(client.cookies)
    client.cookies.clear();client.cookies.update(first_cookies)
    invitation={'expected_tenant_id':first['tenant_id'],'email':second['email'],'role':'viewer'}
    assert post(client,'/api/identity/invite',invitation).status_code==200
    token=mail.token
    client.cookies.clear();client.cookies.update(second_cookies)
    assert post(client,'/api/identity/accept-invite',{'token':token}).status_code==200
    assert post(client,'/api/identity/switch-tenant',{'tenant_id':first['tenant_id'],'expected_tenant_id':second['tenant_id']}).status_code==200
    assert client.get('/api/identity/me').json()['user']['role']=='viewer'
    assert post(client,'/api/resources/workspaces',{'name':'Denied','document':{},'expected_tenant_id':first['tenant_id']}).status_code==403
    viewer_cookies=dict(client.cookies)
    client.cookies.clear();client.cookies.update(first_cookies)
    assert post(client,'/api/identity/invite',invitation).status_code==200
    pending_token=mail.token
    assert post(client,f"/api/identity/members/{second['user_id']}/remove",{'expected_tenant_id':first['tenant_id']}).status_code==200
    client.cookies.clear();client.cookies.update(viewer_cookies)
    assert client.get('/api/identity/me').json()['user'] is None
    client.cookies.clear()
    assert client.post('/api/identity/login',json={'email':second['email'],'password':PASSWORD}).status_code==200
    assert post(client,'/api/identity/accept-invite',{'token':pending_token}).status_code==400


def test_private_resources_and_expected_account_are_isolated(client):
    first=signup(client);first_cookies=dict(client.cookies)
    saved=post(client,'/api/resources/workspaces',{'name':'Private first','document':{},'expected_tenant_id':first['tenant_id']}).json()
    execution=client.get('/api/execution/state').json()
    original=client.get('/api/workspace').json()
    client.cookies.clear();second=signup(client,'other@example.test')
    assert client.get('/api/resources/workspaces').json()['workspaces']==[]
    assert post(client,f"/api/resources/workspaces/{saved['id']}",{'name':'Attempt','document':{},'expected_revision':1,'expected_tenant_id':second['tenant_id']}).status_code==404
    assert client.get(f"/api/execution/accounts/{execution['account']['id']}/export").status_code==409
    client.cookies.clear();client.cookies.update(first_cookies)
    new=post(client,'/api/sessions',{'expected_tenant_id':first['tenant_id'],'expected_account_id':original['account']['id']})
    assert new.status_code==200
    rejected=post(client,'/api/commands',{'key':'stale-account','action':'control','killed':True,'expected_tenant_id':first['tenant_id'],'expected_account_id':original['account']['id']})
    assert rejected.status_code==409
    assert not client.get('/api/workspace').json()['account']['killed']

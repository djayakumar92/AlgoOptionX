"""User-specific encrypted Dhan connections. Read-only adapter, no order interface."""
from datetime import datetime, timezone
import json
import time
import uuid
import requests
from fastapi import APIRouter, HTTPException, Request
from pydantic import Field, field_validator
from .api import TenantContext, principal, require_tenant_context
from .identity import IdentityError
from .vault import SecretVault

router=APIRouter(prefix='/api/brokers')


class Connection(TenantContext):
    broker:str=Field(pattern='^dhan$')
    label:str=Field(min_length=1,max_length=80)
    client_id:str=Field(min_length=1,max_length=80)
    access_token:str=Field(min_length=10,max_length=8192)
    expires_at:datetime|None=None

    @field_validator('expires_at')
    @classmethod
    def aware_expiry(cls,value):
        if value is not None and (value.tzinfo is None or value<=datetime.now(timezone.utc)):raise ValueError('Use a future timezone-aware token expiry.')
        return value


class BrokerStore:
    def __init__(self,identity):
        self.identity=identity
        with identity.tx() as c:
            c.execute("CREATE TABLE IF NOT EXISTS broker_connections(id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL REFERENCES tenants(id),user_id TEXT NOT NULL REFERENCES users(id),broker TEXT NOT NULL,label TEXT NOT NULL,encrypted_credentials TEXT NOT NULL,expires_at INTEGER,status TEXT NOT NULL,capabilities TEXT NOT NULL,revision INTEGER NOT NULL,updated_at INTEGER NOT NULL,UNIQUE(tenant_id,user_id,broker))")

    def vault(self):return SecretVault(self.identity.path.with_suffix('.secret'),getattr(self.identity,'secure_keys_required',False))

    def list(self,user):
        with self.identity.tx() as c:
            rows=c.execute('SELECT id,broker,label,expires_at,status,capabilities,revision,updated_at FROM broker_connections WHERE tenant_id=? AND user_id=? ORDER BY updated_at DESC',(user['tenant_id'],user['user_id'])).fetchall()
        return [dict(row)|{'capabilities':json.loads(row['capabilities']), 'status':'expired' if row['expires_at'] and row['expires_at']<=int(time.time()) else row['status']} for row in rows]

    def save(self,user,body):
        encrypted=self.vault().encrypt({'purpose':'broker','tenant_id':user['tenant_id'],'user_id':user['user_id'],'broker':body.broker,'client_id':body.client_id,'access_token':body.access_token})
        with self.identity.tx() as c:
            previous=c.execute('SELECT id,revision FROM broker_connections WHERE tenant_id=? AND user_id=? AND broker=?',(user['tenant_id'],user['user_id'],body.broker)).fetchone()
            connection_id=previous['id'] if previous else uuid.uuid4().hex
            expires=int(body.expires_at.timestamp()) if body.expires_at else None
            if previous:c.execute("UPDATE broker_connections SET label=?,encrypted_credentials=?,expires_at=?,status='not_tested',capabilities='{}',revision=revision+1,updated_at=? WHERE id=?",(body.label,encrypted,expires,int(time.time()),connection_id))
            else:c.execute("INSERT INTO broker_connections VALUES(?,?,?,?,?,?,?,'not_tested','{}',1,?)",(connection_id,user['tenant_id'],user['user_id'],body.broker,body.label,encrypted,expires,int(time.time())))
            self.identity.event(c,user['user_id'],'BROKER_CREDENTIALS_SAVED')
        return {'id':connection_id,'status':'not_tested','notice':'Credentials encrypted. Provider authorization, token expiry and commercial data rights still require verification.'}

    def owned(self,c,user,connection_id):
        row=c.execute('SELECT * FROM broker_connections WHERE id=? AND tenant_id=? AND user_id=?',(connection_id,user['tenant_id'],user['user_id'])).fetchone()
        if not row:raise IdentityError('Broker connection not found.',404)
        return row

    def test(self,user,connection_id):
        self.identity.rate_limit('broker-test:'+user['user_id'],10,3600)
        with self.identity.tx() as c:row=dict(self.owned(c,user,connection_id))
        if row['status']=='disconnected' or not row['encrypted_credentials']:raise IdentityError('Reconnect this broker before testing.',409)
        if row['expires_at'] and row['expires_at']<=int(time.time()):raise IdentityError('Broker token expired. Reauthorize first.',409)
        credentials=self.vault().decrypt(row['encrypted_credentials'])
        if credentials.get('purpose')!='broker' or credentials.get('user_id')!=user['user_id'] or credentials.get('tenant_id')!=user['tenant_id']:raise IdentityError('Credential ownership mismatch.',503)
        try:
            response=requests.get('https://api.dhan.co/v2/fundlimit',headers={'access-token':credentials['access_token'],'client-id':credentials['client_id']},timeout=10,allow_redirects=False)
            if response.status_code in (401,403):status='reauthorization_required'
            elif response.status_code==200 and isinstance(response.json(),dict):status='account_read_verified'
            else:status='provider_unavailable'
        except (requests.RequestException,ValueError):status='provider_unavailable'
        capabilities={'account_read':status=='account_read_verified','market_data':'not_verified','order_submission':False,'commercial_data_rights':'not_verified'}
        with self.identity.tx() as c:
            changed=c.execute("UPDATE broker_connections SET status=?,capabilities=?,updated_at=? WHERE id=? AND tenant_id=? AND user_id=? AND revision=? AND status!='disconnected'",(status,json.dumps(capabilities),int(time.time()),connection_id,user['tenant_id'],user['user_id'],row['revision'])).rowcount
            if not changed:raise IdentityError('Connection changed while testing. Review its current status.',409)
            self.identity.event(c,user['user_id'],'BROKER_CONNECTION_TESTED')
        return {'status':status,'capabilities':capabilities,'notice':'Only read access was tested. No orders were submitted; market-data rights and current broker API rules remain separate.'}

    def disconnect(self,user,connection_id):
        with self.identity.tx() as c:
            self.owned(c,user,connection_id)
            c.execute("UPDATE broker_connections SET encrypted_credentials='',status='disconnected',revision=revision+1,capabilities='{}',updated_at=? WHERE id=?",(int(time.time()),connection_id))
            self.identity.event(c,user['user_id'],'BROKER_DISCONNECTED')
        return {'status':'disconnected','notice':'Local credentials removed. Revoke the token in your broker portal to revoke provider-side authority.'}


def permitted(request,expected):
    user=principal(request);require_tenant_context(request,expected)
    if user['role']=='viewer':raise HTTPException(403,'This membership cannot manage broker connections.')
    if request.app.state.require_auth and not user['email_verified']:raise HTTPException(403,'Verify your email before connecting a broker.')
    return user


@router.get('')
def connections(request:Request):return {'connections':request.app.state.brokers.list(principal(request)),'live_execution':False}


@router.post('')
def save(body:Connection,request:Request):return request.app.state.brokers.save(permitted(request,body.expected_tenant_id),body)


@router.post('/{connection_id}/{action}')
def action(connection_id:str,action:str,body:TenantContext,request:Request):
    user=permitted(request,body.expected_tenant_id)
    if action=='test':return request.app.state.brokers.test(user,connection_id)
    if action=='disconnect':return request.app.state.brokers.disconnect(user,connection_id)
    raise HTTPException(404,'Unknown broker operation.')

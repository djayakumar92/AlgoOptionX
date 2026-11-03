"""TOTP enrollment, anti-replay checks and one-use recovery codes."""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote
from fastapi import APIRouter, Request, Response
from pydantic import Field
from .api import Record, principal, set_session
from .identity import IdentityError, password_matches, digest
from .vault import SecretVault

router=APIRouter(prefix='/api/identity/mfa')


class Proof(Record):
    password:str=Field(min_length=1,max_length=128)
    code:str|None=Field(default=None,min_length=6,max_length=40)


class Code(Record):
    code:str=Field(min_length=6,max_length=40)


def vault(store):return SecretVault(store.path.with_suffix('.secret'),getattr(store,'secure_keys_required',False))


def totp(secret,step):
    key=base64.b32decode(secret,casefold=True)
    value=hmac.new(key,struct.pack('>Q',step),hashlib.sha1).digest();offset=value[-1]&15
    return f'{(struct.unpack(">I",value[offset:offset+4])[0]&0x7fffffff)%1000000:06d}'


def validate_factor(store,c,user_id,code):
    row=c.execute('SELECT * FROM mfa_credentials WHERE user_id=? AND active=1',(user_id,)).fetchone()
    if not row:return
    if not code:raise IdentityError('Email, password or authentication code is incorrect.',401)
    normalized=code.strip().upper()
    recovery=c.execute('SELECT code_hash FROM mfa_recovery WHERE user_id=? AND code_hash=? AND used=0',(user_id,digest(normalized))).fetchone()
    if recovery:
        c.execute('UPDATE mfa_recovery SET used=1 WHERE user_id=? AND code_hash=?',(user_id,recovery[0]));store.event(c,user_id,'MFA_RECOVERY_USED');return
    payload=vault(store).decrypt(row['encrypted_secret'])
    if payload.get('user_id')!=user_id or payload.get('purpose')!='mfa':raise IdentityError('MFA credential ownership mismatch.',503)
    step=int(time.time())//30
    matched=next((candidate for candidate in (step-1,step,step+1) if candidate>row['last_step'] and hmac.compare_digest(totp(payload['secret'],candidate),normalized)),None)
    if matched is None:raise IdentityError('Email, password or authentication code is incorrect.',401)
    c.execute('UPDATE mfa_credentials SET last_step=? WHERE user_id=?',(matched,user_id))



@router.get('')
def status(request:Request):
    user=principal(request)
    with request.app.state.identity.tx() as c:
        row=c.execute('SELECT active FROM mfa_credentials WHERE user_id=?',(user['user_id'],)).fetchone()
        count=c.execute('SELECT COUNT(*) FROM mfa_recovery WHERE user_id=? AND used=0',(user['user_id'],)).fetchone()[0]
    return {'enabled':bool(row and row[0]),'recovery_codes_remaining':count}


@router.post('/setup')
def setup(body:Proof,request:Request):
    user=principal(request);store=request.app.state.identity
    # Rate limiting uses its own transaction before the security transaction.
    store.rate_limit('mfa-setup:'+user['user_id'],5)
    with store.tx() as c:
        row=c.execute('SELECT password_hash FROM users WHERE id=?',(user['user_id'],)).fetchone()
        if not password_matches(body.password,row[0]):raise IdentityError('Current password or authentication code is incorrect.',401)
        active=c.execute('SELECT active FROM mfa_credentials WHERE user_id=?',(user['user_id'],)).fetchone()
        if active and active[0]:raise IdentityError('Disable the existing authenticator with its current code before enrolling another.',409)
        secret=base64.b32encode(secrets.token_bytes(20)).decode()
        encrypted=vault(store).encrypt({'purpose':'mfa','user_id':user['user_id'],'secret':secret,'enrollment_expires_at':int(time.time())+600})
        c.execute('INSERT INTO mfa_credentials VALUES(?,?,0,0) ON CONFLICT(user_id) DO UPDATE SET encrypted_secret=excluded.encrypted_secret,active=0,last_step=0',(user['user_id'],encrypted))
        store.event(c,user['user_id'],'MFA_ENROLLMENT_STARTED')
    return {'secret':secret,'provisioning_uri':f'otpauth://totp/{quote("AlgoOptionX:"+user["email"])}?secret={secret}&issuer=AlgoOptionX&algorithm=SHA1&digits=6&period=30',
            'notice':'Store this only in your authenticator. It is returned for this explicit enrollment; it cannot be read back.'}


@router.post('/confirm')
def confirm(body:Code,request:Request,response:Response):
    user=principal(request);store=request.app.state.identity;store.rate_limit('mfa-confirm:'+user['user_id'],10)
    with store.tx() as c:
        row=c.execute('SELECT * FROM mfa_credentials WHERE user_id=? AND active=0',(user['user_id'],)).fetchone()
        if not row:raise IdentityError('Start authenticator enrollment first.')
        payload=vault(store).decrypt(row['encrypted_secret'])
        if payload.get('user_id')!=user['user_id'] or payload.get('purpose')!='mfa':raise IdentityError('Credential ownership mismatch.',503)
        if payload.get('enrollment_expires_at',0)<=int(time.time()):raise IdentityError('Enrollment expired. Start again.',409)
        step=int(time.time())//30;matched=next((candidate for candidate in (step-1,step,step+1) if hmac.compare_digest(totp(payload['secret'],candidate),body.code.strip())),None)
        if matched is None:raise IdentityError('Authentication code is incorrect.',401)
        c.execute('UPDATE mfa_credentials SET active=1,last_step=? WHERE user_id=?',(matched,user['user_id']))
        raw_codes=[secrets.token_hex(8).upper() for _ in range(8)]
        codes=['-'.join(raw[i:i+4] for i in range(0,16,4)) for raw in raw_codes]
        c.execute('DELETE FROM mfa_recovery WHERE user_id=?',(user['user_id'],))
        c.executemany('INSERT INTO mfa_recovery VALUES(?,?,0)',[(user['user_id'],digest(code)) for code in codes])
        c.execute('UPDATE sessions SET revoked=1 WHERE user_id=?',(user['user_id'],));tokens=store._session(c,user['user_id'],user['tenant_id'])
        store.event(c,user['user_id'],'MFA_ENABLED')
    set_session(request,response,tokens)
    return {'enabled':True,'recovery_codes':codes,'notice':'Save these one-use recovery codes now. They cannot be read back.'}


@router.post('/disable')
def disable(body:Proof,request:Request,response:Response):
    user=principal(request);store=request.app.state.identity;store.rate_limit('mfa-disable:'+user['user_id'],5)
    with store.tx() as c:
        row=c.execute('SELECT password_hash FROM users WHERE id=?',(user['user_id'],)).fetchone()
        if not password_matches(body.password,row[0]):raise IdentityError('Current password or authentication code is incorrect.',401)
        validate_factor(store,c,user['user_id'],body.code)
        c.execute('DELETE FROM mfa_credentials WHERE user_id=?',(user['user_id'],));c.execute('DELETE FROM mfa_recovery WHERE user_id=?',(user['user_id'],))
        c.execute('UPDATE sessions SET revoked=1 WHERE user_id=?',(user['user_id'],));tokens=store._session(c,user['user_id'],user['tenant_id']);store.event(c,user['user_id'],'MFA_DISABLED')
    set_session(request,response,tokens)
    return {'enabled':False}

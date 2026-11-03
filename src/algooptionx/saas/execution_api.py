"""Tenant-authenticated paper execution. No live broker execution exists here."""
from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from pydantic import Field
from .api import Record, TenantContext, principal, require_tenant_context

router=APIRouter(prefix='/api/execution')


class Leg(Record):
    instrument:str=Field(min_length=1,max_length=160)
    side:Literal[-1,1]


class ExecutionContext(TenantContext):
    expected_account_id:str=Field(min_length=1,max_length=80)


class Order(ExecutionContext):
    key:str=Field(min_length=8,max_length=160)
    preview_token:str|None=Field(default=None,pattern=r'^[a-f0-9]{64}$')
    kind:Literal['MARKET','LIMIT','STOP','STOP_LIMIT']='MARKET'
    legs:list[Leg]=Field(min_length=1,max_length=4)
    lots:int=Field(default=1,ge=1,le=5)
    limit_paise:int|None=None
    stop_paise:int|None=None
    trigger_direction:Literal['above','below']='above'


class Mutation(ExecutionContext):
    key:str=Field(min_length=8,max_length=160)
    order_id:str|None=Field(default=None,max_length=80)
    position_id:str|None=Field(default=None,max_length=80)
    expected_revision:int|None=Field(default=None,ge=1)
    lots:int|None=Field(default=None,ge=1,le=5)
    limit_paise:int|None=None
    stop_paise:int|None=None


class NewAccount(ExecutionContext):
    capital_paise:int=Field(default=50_000_000,ge=1_000_000,le=1_000_000_000)


def book(request,user):return request.app.state.tenants.execution(user['tenant_id'])
def trader(request,expected):
    user=principal(request);require_tenant_context(request,expected)
    if user['role']=='viewer':raise HTTPException(403,'This membership is read-only.')
    return user


@router.get('/state')
def state(request:Request):
    user=principal(request)
    with request.app.state.tenants.market_lock(user['tenant_id']):
        result=book(request,user).state()
    return result|{'tenant_id':user['tenant_id'],'worker_error':request.app.state.tenants.execution_errors.get(user['tenant_id'])}


@router.post('/preview')
def preview(body:Order,request:Request):
    user=trader(request,body.expected_tenant_id)
    with request.app.state.tenants.market_lock(user['tenant_id']):return book(request,user).preview(body.model_dump())


@router.post('/orders')
def place(body:Order,request:Request):
    user=trader(request,body.expected_tenant_id)
    if user['tenant_id'] in request.app.state.tenants.execution_errors:raise HTTPException(503,'Execution worker stopped. Preserve history and diagnose before restarting.')
    values=body.model_dump(exclude_none=True);values.pop('expected_tenant_id');key=values.pop('key')
    with request.app.state.tenants.market_lock(user['tenant_id']):return book(request,user).command(key,'place',values)


@router.post('/commands/{action}')
def command(action:Literal['cancel','modify','close','kill'],body:Mutation,request:Request):
    user=trader(request,body.expected_tenant_id)
    values=body.model_dump(exclude_none=True);values.pop('expected_tenant_id');key=values.pop('key')
    if action in {'cancel','modify'} and not {'order_id','expected_revision'}<=values.keys():raise HTTPException(422,'Order identity and expected revision are required.')
    if action=='close' and 'position_id' not in values:raise HTTPException(422,'Position identity is required.')
    with request.app.state.tenants.market_lock(user['tenant_id']):return book(request,user).command(key,action,values)


@router.post('/accounts')
def new_account(body:NewAccount,request:Request):
    user=trader(request,body.expected_tenant_id)
    with request.app.state.tenants.market_lock(user['tenant_id']):return book(request,user).new_account(body.capital_paise,body.expected_account_id)


@router.get('/accounts')
def accounts(request: Request):
    user = principal(request)
    with request.app.state.tenants.market_lock(user['tenant_id']):
        return book(request,user).history()


@router.get('/accounts/{account_id}/audit')
def audit(account_id: str, request: Request):
    user = principal(request)
    with request.app.state.tenants.market_lock(user['tenant_id']):
        return book(request,user).audit(account_id)


@router.get('/accounts/{account_id}/export')
def export(account_id: str, request: Request):
    user = principal(request)
    with request.app.state.tenants.market_lock(user['tenant_id']):
        return book(request,user).export(account_id)

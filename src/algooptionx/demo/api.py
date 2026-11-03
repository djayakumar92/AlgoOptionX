"""Strict same-origin demo API. There is no network/broker execution adapter."""
from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel,ConfigDict,Field
from . import market
from .research import evaluate

Strategy=Literal['bull-put','bear-call','iron-condor']
Scenario=Literal['bullish','bearish','sideways','gap-up','gap-down','risk-rejection','disconnection','lifecycle']


class Draft(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    strategy:Strategy='bull-put'
    lots:int=Field(default=1,ge=1,le=5)
    expiry:Literal['2026-11-03T15:30:00+05:30','2026-11-10T15:30:00+05:30']=market.EXPIRIES[0]
    strikes:list[int]=Field(default_factory=list,max_length=4)


class DemoCommand(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    key:str=Field(min_length=1,max_length=160)
    session_id:str=Field(min_length=1,max_length=160)
    action:Literal['open','close','step','session','kill','reconnect','disconnect','note']
    draft:Draft|None=None
    quote_token:str|None=Field(default=None,pattern='^[a-f0-9]{64}$')
    steps:int|None=Field(default=None,ge=1,le=30)
    scenario:Scenario|None=None
    position_id:str|None=Field(default=None,min_length=1,max_length=160)
    note:str|None=Field(default=None,max_length=2000)
    category:Literal['Plan followed','Sizing','Timing','Other']|None=None
    reason:str|None=Field(default=None,max_length=500)


class ResearchRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    scenario:Scenario='bullish'
    strategy:Strategy='bull-put'
    lots:int=Field(default=1,ge=1,le=5)
    split:Literal[.6,.7]=.6


router=APIRouter(prefix='/api/demo')


@router.get('/health')
def health():return {'mode':'DEMO','source':'SYNTHETIC','broker_routing':False}


@router.get('/state')
def state(request:Request):return request.state.demo_engine.state()


@router.post('/preview')
def preview(body:Draft,request:Request):
    try:return request.state.demo_engine.preview(body.model_dump())
    except ValueError as error:raise HTTPException(422,str(error)) from None


@router.post('/commands')
def command(body:DemoCommand,request:Request):
    values=body.model_dump(exclude_none=True,exclude_unset=True)
    fields={'open':{'draft','quote_token','reason'},'close':{'position_id'},'step':{'steps'},
            'session':{'scenario'},'kill':set(),'reconnect':set(),'disconnect':set(),
            'note':{'position_id','note','category'}}
    if set(values)-{'key','session_id','action'}-fields[body.action]:raise HTTPException(422,'Fields do not match the demo command.')
    required={'open':{'draft','quote_token'},'close':{'position_id'},'session':{'scenario'},'note':{'position_id','note'}}.get(body.action,set())
    if not required <= set(values):raise HTTPException(422,'Missing required demo command fields.')
    user=getattr(request.state,'principal',None)
    if user:
        with request.app.state.tenants.market_lock(user['tenant_id']):
            if body.action=='session' and request.app.state.tenants.has_execution_exposure(user['tenant_id']):raise HTTPException(409,'Close execution-account positions and cancel its working orders before changing the synthetic source session.')
            result=request.state.demo_engine.command(values)
    else:result=request.state.demo_engine.command(values)
    if not result['ok']:raise HTTPException(409,result['error'])
    return result


@router.post('/research')
def research(body:ResearchRequest):return evaluate(**body.model_dump())


@router.get('/audit')
def audit(request:Request):return request.state.demo_engine.audit()

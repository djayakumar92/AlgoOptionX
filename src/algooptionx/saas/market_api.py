"""Causal synthetic chart adapter. Live/historical rights are never implied."""
from datetime import timedelta
from fastapi import APIRouter, Query, Request
from algooptionx.demo import market
from algooptionx.market.contracts import validate_batch
from algooptionx.market.indicators import calculate

router = APIRouter(prefix="/api/market")


@router.get("/capabilities")
def capabilities():
    return {'source':'SYNTHETIC','intervals':[1,3,5,15,30,60],
            'unavailable_intervals':{'day':'Only a partial synthetic intraday session is available.','week':'No weekly dataset is configured.'},
            'live_data':False,'historical_data':False,'instrument_metadata':'FIXTURE-65-UNIT-LOT'}


@router.get("/candles")
def candles(request: Request, interval: int = Query(default=5, ge=1, le=60)):
    if interval not in (1,3,5,15,30,60):
        from fastapi import HTTPException
        raise HTTPException(422,"Unsupported source interval.")
    state = request.state.demo_engine.state()
    tick = state['session']['quote_tick']
    scenario = state['session']['scenario']
    session,source = market.source_candles(scenario,tick)
    as_of = market.START+timedelta(minutes=tick)
    ordered = validate_batch(source,session,as_of=as_of)
    vwap = market.session_vwap(ordered)
    by_open = {bar.open_at:bar for bar in ordered}
    start,bars = session.open_at,[]
    while start+timedelta(minutes=interval) <= min(as_of,session.close_at):
        children = [by_open.get(start+timedelta(minutes=i)) for i in range(interval)]
        if all(child is not None and child.available_at <= as_of for child in children):
            close_at = start+timedelta(minutes=interval)
            bars.append({'time':close_at.isoformat(),'open':children[0].open_paise/100,
                         'high':max(child.high_paise for child in children)/100,'low':min(child.low_paise for child in children)/100,
                         'close':children[-1].close_paise/100,'volume':sum(child.volume for child in children),'minutes':interval,
                         'available_at':max(child.available_at for child in children).isoformat(),'vwap':vwap.get(close_at)})
        start += timedelta(minutes=interval)
    ema9 = market.ema([bar['close'] for bar in bars])
    indicators = calculate(bars)
    for index,bar in enumerate(bars):
        bar.update(ema9=ema9[index],ema_warmup=min(index+1,9),indicators=indicators[index])
    return {'source':'SYNTHETIC','session_id':state['session']['id'],'as_of':as_of.isoformat(),
            'source_version':market.REVISION,'calendar_version':session.calendar_version,'interval':interval,
            'connected':bool(state['session']['connected']),'bars':bars,
            'notice':'Completed synthetic candles only. Missing intervals are not interpolated; indicator warm-up is null. No live or historical performance claim.'}

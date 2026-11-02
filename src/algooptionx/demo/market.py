"""Single deterministic observed timeline shared by every demo screen."""
from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import math

from algooptionx.market.contracts import Candle, Session
from algooptionx.market.aggregation import aggregate_completed
from .pricing import european, HALF_SPREAD, LOT, paise

START = datetime.fromisoformat('2026-11-02T09:15:00+05:30')
EXPIRIES = ('2026-11-03T15:30:00+05:30','2026-11-10T15:30:00+05:30')
MAX_TICK = 180
REVISION = 'SYNTHETIC-SCENARIOS-1'
SCENARIOS = {
    'bullish': ('A · Bullish trend', .9, 0), 'bearish': ('B · Bearish trend', -.9, 0),
    'sideways': ('C · Sideways consolidation', 0, 0), 'gap-up': ('D · Gap-up opening', .3, 200),
    'gap-down': ('E · Gap-down opening', -.3, -200),
    'risk-rejection': ('F · Risk-limit rejection', .9, 0),
    'disconnection': ('G · Market-data disconnection', .9, 0),
    'lifecycle': ('H · Complete paper lifecycle', .9, 0),
}


def spot(scenario: str, tick: int) -> int:
    if scenario not in SCENARIOS or type(tick) is not int or not 0 <= tick <= MAX_TICK:
        raise ValueError('Unknown scenario or synthetic tick.')
    _, slope, gap = SCENARIOS[scenario]
    return paise(24400+gap+slope*tick+6*math.sin(tick/4)+2*math.sin(tick/2))


def source_candles(scenario: str, tick: int) -> tuple[Session,list[Candle]]:
    session = Session('DEMO-'+scenario, REVISION, START, START+timedelta(minutes=MAX_TICK))
    candles=[]
    for index in range(tick):
        opening, close = spot(scenario,index), spot(scenario,index+1)
        high = max(opening,close)+120+int(20*abs(math.sin(index)))
        low = min(opening,close)-120-int(20*abs(math.cos(index)))
        at=START+timedelta(minutes=index)
        candle = Candle(instrument_id='SYNTHETIC-NIFTY',source_id='DEMO-FIXTURE',data_version=REVISION,
            calendar_version=REVISION,session_id=session.session_id,
            source_hash=hashlib.sha256(f'{REVISION}:{scenario}:{index}:{opening}:{high}:{low}:{close}'.encode()).hexdigest(),
            open_at=at,close_at=at+timedelta(minutes=1),available_at=at+timedelta(minutes=1),
            open_paise=opening,high_paise=high,low_paise=low,close_paise=close,
            volume=10000+index*13+int(900*abs(math.sin(index/8))))
        candles.append(candle)
    return session,candles


def ema(values: list[float], period: int = 9) -> list[float]:
    """First-close initialized EMA; early values are explicitly warm-up values."""
    if type(period) is not int or period < 1 or any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError('EMA requires a positive period and finite positive observations.')
    result=[]
    alpha=2/(period+1)
    for value in values:
        result.append(value if not result else alpha*value+(1-alpha)*result[-1])
    return result


def session_vwap(source: list[Candle]) -> dict[datetime, float | None]:
    """Observed minute typical-price VWAP in index points, never traded VWAP."""
    numerator=volume=0
    result={}
    previous=None
    for bar in source:
        if not isinstance(bar,Candle) or previous is not None and bar.close_at <= previous:
            raise ValueError('VWAP requires ordered, unique, validated minute candles.')
        if bar.interval_minutes != 1:raise ValueError('Session VWAP requires one-minute observations.')
        previous=bar.close_at
        numerator+=(bar.high_paise+bar.low_paise+bar.close_paise)*bar.volume
        volume+=bar.volume
        result[bar.close_at]=numerator/(300*volume) if volume else None
    return result


def candles(scenario: str, tick: int, timeframe: int) -> list[dict]:
    session,source=source_candles(scenario,tick)
    if timeframe not in (1,5,30): raise ValueError('Timeframe must be 1, 5 or 30 minutes.')
    bars = source if timeframe==1 else aggregate_completed(source,session,as_of=START+timedelta(minutes=tick),minutes=timeframe).bars
    values=ema([bar.close_paise/100 for bar in bars]);vwap=session_vwap(source)
    return [{'time':c.close_at.isoformat(),'open':c.open_paise/100,'high':c.high_paise/100,
             'low':c.low_paise/100,'close':c.close_paise/100,'volume':c.volume,'minutes':timeframe,
             'ema9':values[i],'ema_warmup':min(i+1,9),'vwap':vwap[c.close_at]} for i,c in enumerate(bars)]


def chain(scenario: str, tick: int) -> list[dict]:
    current = spot(scenario,tick)/100
    now=START+timedelta(minutes=tick)
    result=[]
    for expiry in EXPIRIES:
        years=(datetime.fromisoformat(expiry)-now).total_seconds()/31536000
        for strike in range(23800,25001,50):
            for right in ('CE','PE'):
                model=european(current,strike,years,right)
                oi=100000+abs(strike-24400)*100+tick*(40 if right=='PE' else 25)
                result.append({'id':f'DEMO:{expiry}:{strike}:{right}','expiry':expiry,'strike':strike,'right':right,
                    **model,'ltp':model['mark'],'bid':max(0,model['mark']-HALF_SPREAD),
                    'ask':model['mark']+HALF_SPREAD,'spread':model['mark']+HALF_SPREAD-max(0,model['mark']-HALF_SPREAD),
                    'iv':18.0,'oi':oi,'change_oi':tick*(40 if right=='PE' else 25),
                    'volume':5000+tick*37+abs(strike-24400),'lot_size':LOT,
                    'liquidity_warning':model['mark']<1000 or abs(strike-current)>400})
    return result


def analysis(scenario: str, tick: int) -> dict:
    bars=candles(scenario,tick,5); confirmation=candles(scenario,tick,30)
    recent=bars[-6:]; delta=(recent[-1]['close']-recent[0]['open']) if recent else 0
    direction='Bullish' if delta>10 else 'Bearish' if delta < -10 else 'Neutral'
    higher= len(recent)>1 and recent[-1]['high']>recent[-2]['high'] and recent[-1]['low']>recent[-2]['low']
    lower= len(recent)>1 and recent[-1]['high']<recent[-2]['high'] and recent[-1]['low']<recent[-2]['low']
    confirm=confirmation[-1]['close']-confirmation[-2]['close'] if len(confirmation)>1 else None
    support=min((b['low'] for b in recent),default=spot(scenario,tick)/100)
    resistance=max((b['high'] for b in recent),default=support)
    return {'direction':direction,'structure':'Higher high / higher low' if higher else 'Lower high / lower low' if lower else 'Mixed / consolidation',
        'change_30m':round(delta,2),'confirmation_30m':round(confirm,2) if confirm is not None else None,
        'support':support,'resistance':resistance,'gap':SCENARIOS[scenario][2],
        'volume':sum(b['volume'] for b in recent),'iv':18.0,
        'observations':[f'Observed price changed {delta:+.2f} points across the last completed five-minute windows.',
            f'Observed support {support:.2f}; resistance {resistance:.2f}.',
            f'30-minute close change: {confirm:+.2f} points.' if confirm is not None else 'Insufficient completed 30-minute bars for confirmation.'],
        'limitations':'Deterministic synthetic observations, not a prediction, exchange volume, India VIX or evidence of profitability.'}

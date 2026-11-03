"""Independent indicator vectors and completed-prefix causality."""
from dataclasses import replace
from datetime import timedelta
import pytest
from algooptionx.demo.market import candles,source_candles,ema,session_vwap,SCENARIOS


def test_first_close_ema9_known_answer_and_invalid_inputs():
    assert ema([10,20,30])==pytest.approx([10,12,15.6])
    assert ema([])==[]
    assert ema([10,20],1)==[10,20]
    for period in [0,-1,True]:
        with pytest.raises(ValueError):ema([10],period)
    with pytest.raises(ValueError):ema([float('nan')])


def test_minute_vwap_known_answer_and_zero_volume():
    _,source=source_candles('bullish',3)
    bars=[replace(source[i],open_paise=1000*(i+1),high_paise=1000*(i+1)+200,low_paise=1000*(i+1)-200,close_paise=1000*(i+1),volume=v) for i,v in enumerate([10,30,20])]
    values=list(session_vwap(bars).values())
    assert values==pytest.approx([10,17.5,1300/60])
    zero=[replace(bar,volume=0) for bar in bars]
    assert all(v is None for v in session_vwap(zero).values())
    with pytest.raises(ValueError):session_vwap(list(reversed(bars)))


@pytest.mark.parametrize('scenario',list(SCENARIOS))
def test_indicators_are_prefix_invariant_and_vwap_agrees_across_timeframes(scenario):
    five=candles(scenario,60,5);thirty=candles(scenario,60,30)
    assert candles(scenario,180,5)[:len(five)]==five
    assert candles(scenario,180,30)[:len(thirty)]==thirty
    by_time={bar['time']:bar for bar in five}
    for bar in thirty:assert bar['vwap']==by_time[bar['time']]['vwap']
    assert five[0]['ema9']==five[0]['close'] and five[0]['ema_warmup']==1
    assert five[-1]['ema_warmup']==9 and thirty[-1]['ema_warmup']==2

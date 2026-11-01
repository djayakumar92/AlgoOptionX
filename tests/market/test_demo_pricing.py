"""Known-answer and causal fixture checks for the approved pricing conventions."""
import math
import pytest
from algooptionx.demo.pricing import european,paise
from algooptionx.demo.market import chain,candles,SCENARIOS


def test_european_known_answer_and_parity():
    call=european(100,100,1,'CE',.2,.05);put=european(100,100,1,'PE',.2,.05)
    assert call['mark']==1045 and put['mark']==557
    assert abs(call['mark']-put['mark']-paise(100-100*math.exp(-.05)))<=1
    assert abs(call['delta']-put['delta']-1)<1e-12
    assert call['gamma']==put['gamma'] and call['vega']==put['vega']
    assert european(110,100,0,'CE')['mark']==1000
    with pytest.raises(ValueError):european(100,100,-1,'CE')


@pytest.mark.parametrize('scenario',list(SCENARIOS))
def test_observed_candles_and_quote_determinism(scenario):
    assert chain(scenario,60)==chain(scenario,60)
    assert candles(scenario,65,5)[:12]==candles(scenario,60,5)
    assert len(candles(scenario,60,30))==2
    quotes=chain(scenario,60)
    assert all(q['bid']<=q['mark']<=q['ask'] for q in quotes)
    for right in ['CE','PE']:
        marks=[q['mark'] for q in quotes if q['right']==right and q['expiry']==quotes[0]['expiry']]
        assert all(a>=b for a,b in zip(marks,marks[1:])) if right=='CE' else all(a<=b for a,b in zip(marks,marks[1:]))

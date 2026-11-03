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


def test_fee_dominated_trade_has_no_false_breakeven():
    from algooptionx.demo.pricing import strategy_value
    from algooptionx.demo.market import EXPIRIES
    p=strategy_value('bull-put',[23850,23800],1,chain('bullish',60),EXPIRIES[0])
    assert p['max_profit']<0 and p['breakevens']==[]


@pytest.mark.parametrize('strategy,strikes',[('bull-put',[24400,24350]),('bear-call',[24500,24550]),('iron-condor',[24400,24350,24500,24550])])
def test_breakevens_are_actual_piecewise_payoff_roots(strategy,strikes):
    from algooptionx.demo.pricing import strategy_value
    from algooptionx.demo.market import EXPIRIES
    p=strategy_value(strategy,strikes,1,chain('bullish',60),EXPIRIES[0])
    for root in p['breakevens']:
        payoff=p['net_credit']+sum(leg['side']*max(0,root-leg['strike'] if leg['right']=='CE' else leg['strike']-root)*100*leg['quantity'] for leg in p['legs'])
        assert abs(payoff)<.001


@pytest.mark.parametrize('strategy,strikes,expected_profit,expected_loss,roots',[
    ('bull-put',[24500,24450],115500,209500,1),
    ('bear-call',[24500,24550],115500,209500,1),
    ('iron-condor',[24400,24350,24600,24650],231000,94000,2),
    ('iron-condor',[24400,24300,24600,24650],231000,419000,2),
])
def test_independent_fixed_quote_spread_accounting_oracles(strategy,strikes,expected_profit,expected_loss,roots):
    from algooptionx.demo.pricing import strategy_value
    from algooptionx.demo.market import EXPIRIES
    expiry=EXPIRIES[0];quotes=[]
    rights=['PE','PE'] if strategy=='bull-put' else ['CE','CE'] if strategy=='bear-call' else ['PE','PE','CE','CE']
    for i,(strike,right) in enumerate(zip(strikes,rights)):
        short=i%2==0
        quotes.append({'id':f'FIXED:{strike}:{right}','strike':strike,'right':right,'expiry':expiry,
            'bid':12000 if short else 9920,'ask':12080 if short else 10000,'mark':12040 if short else 9960})
    result=strategy_value(strategy,strikes,1,quotes,expiry)
    assert result['max_profit']==expected_profit
    assert result['max_loss']==result['reserve']==expected_loss
    assert len(result['breakevens'])==roots
    if strategy!='iron-condor':
        assert result['entry_net_credit']==125350
        assert result['expiry_max_loss_before_exit_costs']==199650

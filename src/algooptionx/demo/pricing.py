"""Approved European fixture pricing and exact paise strategy accounting.

Illustrative flat-IV Black–Scholes, ACT/365, no dividends. No broker margin model.
"""
from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP

LOT = 65
FEE = 2000
HALF_SPREAD = 40
SLIPPAGE = 5
VERSION = 'EUROPEAN-FIXTURE-1'
STRATEGIES = ('bull-put', 'bear-call', 'iron-condor')


def paise(value: float) -> int:
    if not math.isfinite(value):
        raise ValueError('Nonfinite monetary value.')
    return int((Decimal(str(value)) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def european(spot: float, strike: float, years: float, right: str, iv: float = .18, rate: float = .06) -> dict:
    if right not in ('CE', 'PE') or not all(math.isfinite(x) for x in (spot, strike, years, iv, rate)) or min(spot, strike, iv) <= 0 or years < 0:
        raise ValueError('Invalid European fixture inputs.')
    sign = 1 if right == 'CE' else -1
    if years == 0:
        return {'mark': paise(max(0, sign*(spot-strike))), 'delta': None, 'gamma': None, 'vega': None, 'theta': None, 'rho': None}
    n = lambda x: (1+math.erf(x/math.sqrt(2)))/2
    root = math.sqrt(years)
    d1 = (math.log(spot/strike)+(rate+iv*iv/2)*years)/(iv*root)
    d2 = d1-iv*root
    discount = math.exp(-rate*years)
    density = math.exp(-d1*d1/2)/math.sqrt(2*math.pi)
    price = sign*(spot*n(sign*d1)-strike*discount*n(sign*d2))
    return {'mark': paise(max(0, price)), 'delta': sign*n(sign*d1),
            'gamma': density/(spot*iv*root), 'vega': spot*density*root/100,
            'theta': (-spot*density*iv/(2*root)-sign*rate*strike*discount*n(sign*d2))/365,
            'rho': sign*strike*years*discount*n(sign*d2)/100}


def fill(quote: dict, side: int) -> int:
    return quote['ask']+SLIPPAGE if side == 1 else max(0, quote['bid']-SLIPPAGE)


def legs_for(strategy: str, strikes: list[int]) -> list[dict]:
    if strategy not in STRATEGIES or len(strikes) != (4 if strategy == 'iron-condor' else 2) or any(type(k) is not int or k <= 0 for k in strikes):
        raise ValueError('Select a supported strategy with exact positive integer leg strikes.')
    if strategy == 'bull-put':
        if not strikes[1] < strikes[0]: raise ValueError('Bull put: short put strike must exceed long put strike.')
        return [{'right':'PE','side':-1,'strike':strikes[0]}, {'right':'PE','side':1,'strike':strikes[1]}]
    if strategy == 'bear-call':
        if not strikes[0] < strikes[1]: raise ValueError('Bear call: short call strike must be below long call strike.')
        return [{'right':'CE','side':-1,'strike':strikes[0]}, {'right':'CE','side':1,'strike':strikes[1]}]
    sp, lp, sc, lc = strikes
    if not lp < sp < sc < lc: raise ValueError('Condor requires long put < short put < short call < long call.')
    return [{'right':'PE','side':-1,'strike':sp}, {'right':'PE','side':1,'strike':lp}, {'right':'CE','side':-1,'strike':sc}, {'right':'CE','side':1,'strike':lc}]


def strategy_value(strategy: str, strikes: list[int], lots: int, quotes: list[dict], expiry: str) -> dict:
    if type(lots) is not int or not 1 <= lots <= 5: raise ValueError('Quantity must be 1–5 equal fixture lots.')
    legs = legs_for(strategy, strikes)
    by_key = {(q['strike'],q['right'],q['expiry']):q for q in quotes}
    quantity = lots*LOT
    for leg in legs:
        quote = by_key.get((leg['strike'],leg['right'],expiry))
        if quote is None or quote['ask'] < quote['bid'] or quote['bid'] < 0:
            raise ValueError('All legs require valid same-expiry fixture quotes.')
        leg.update(instrument=quote['id'], expiry=expiry, quantity=quantity,
                   entry=fill(quote,leg['side']), mark=quote['mark'])
    premium = sum(-leg['side']*leg['entry']*quantity for leg in legs)
    entry_fees = len(legs)*FEE
    entry_net = premium-entry_fees
    exit_friction = len(legs)*(HALF_SPREAD+SLIPPAGE)*quantity
    exit_fees = len(legs)*FEE
    net_credit = entry_net-exit_friction-exit_fees
    width = max(abs(strikes[0]-strikes[1]),abs(strikes[2]-strikes[3]) if len(strikes)==4 else 0)*100*quantity
    reserve = max(0,width-entry_net)+exit_friction+exit_fees
    def payoff(spot):
        intrinsic = sum(leg['side']*max(0, (spot-leg['strike']) if leg['right']=='CE' else (leg['strike']-spot))*100*quantity for leg in legs)
        return round(net_credit+intrinsic)
    points = sorted(set([min(strikes)-200,*strikes,max(strikes)+200,*range(min(strikes)-200,max(strikes)+201,10)]))
    max_profit = max(payoff(x) for x in points)
    max_loss = max(0,-min(payoff(x) for x in points))
    # Solve the piecewise expiry payoff, rather than invent roots for a
    # fee-dominated trade whose payoff never reaches zero.
    roots = set()
    nodes = sorted(set(strikes))
    if max_profit > 0:
        for left, right in zip(nodes, nodes[1:]):
            first, last = payoff(left), payoff(right)
            if first == 0: roots.add(float(left))
            if last == 0: roots.add(float(right))
            if first * last < 0:
                roots.add(left - first * (right-left)/(last-first))
    breakevens = sorted(roots)
    return {'strategy':strategy,'strikes':strikes,'lots':lots,'quantity':quantity,'expiry':expiry,'legs':legs,
            'premium':premium,'entry_fees':entry_fees,'entry_net_credit':entry_net,'exit_fees':exit_fees,
            'exit_friction':exit_friction,'net_credit':net_credit,'max_profit':max_profit,'max_loss':max_loss,
            'reserve':reserve,'expiry_max_loss_before_exit_costs':max(0,width-entry_net),'breakevens':breakevens,'payoff':[{'spot':x,'pnl':payoff(x)} for x in points],
            'pricing_version':VERSION,'warning':'Illustrative expiry payoff after assumed round-trip costs; simulation reserve is not broker margin.'}

"""Computed fixed-rule synthetic evaluations; no training or historical claims."""
from .market import chain, spot, EXPIRIES, SCENARIOS
from .pricing import strategy_value, fill, FEE


def evaluate(scenario='bullish',strategy='bull-put',lots=1,split=.6):
    if scenario not in SCENARIOS or strategy not in ('bull-put','bear-call','iron-condor') or split not in (.6,.7):
        raise ValueError('Unsupported illustrative research configuration.')
    def segment(start,end):
        values=[];equity=50_000_000;peak=equity;drawdown=0;costs=0;curve=[{'tick':start,'equity':equity}]
        for tick in range(start,end-9,10):
            atm=round(spot(scenario,tick)/5000)*50
            strikes={'bull-put':[atm-50,atm-100],'bear-call':[atm+50,atm+100],'iron-condor':[atm-50,atm-100,atm+50,atm+100]}[strategy]
            entry=strategy_value(strategy,strikes,lots,chain(scenario,tick),EXPIRIES[0])
            entry_cash=equity+entry['entry_net_credit']
            for step in range(tick+1,tick+11):
                quotes={q['id']:q for q in chain(scenario,step)}
                mark=entry_cash+sum(leg['side']*quotes[leg['instrument']]['mark']*leg['quantity'] for leg in entry['legs'])
                if step==tick+10:
                    cashflow=sum(leg['side']*fill(quotes[leg['instrument']],-leg['side'])*leg['quantity'] for leg in entry['legs'])-entry['exit_fees']
                    pnl=entry['entry_net_credit']+cashflow;equity+=pnl;mark=equity
                    values.append(pnl);costs+=entry['entry_fees']+entry['exit_fees']+2*len(entry['legs'])*45*entry['quantity']
                peak=max(peak,mark);drawdown=max(drawdown,peak-mark);curve.append({'tick':step,'equity':mark})
        return {'start_tick':start,'end_tick':end,'samples':len(values),'pnl':sum(values),'costs':costs,'max_drawdown':drawdown,'curve':curve,'returns':values}
    boundary=30+int(150*split)//10*10
    return {'source':'SYNTHETIC','strategy':strategy,'scenario':scenario,'lots':lots,'version':'FIXED-RULE-EVALUATION-1',
        'split':split,'in_sample':segment(30,boundary),'out_of_sample':segment(boundary,180),
        'folds':[segment(a,b) for a,b in [(30,80),(80,130),(130,180)]],
        'assumptions':'Nonoverlapping ten-minute trades, closed within each split/fold; fees, spread and slippage included. Drawdown uses each observed synthetic minute and closing costs.',
        'limitations':'Illustrative synthetic fixed-rule evaluation only. No model fitting, trained out-of-sample validation, licensed historical performance or profitability evidence.'}

"""Deterministic descriptive indicators. Warm-up values remain null."""
from __future__ import annotations
import math


def sma(values, period):
    return [sum(values[i-period+1:i+1])/period if i+1 >= period else None for i in range(len(values))]


def ema(values, period):
    result = []
    current = None
    for index, value in enumerate(values):
        current = value if current is None else current + 2/(period+1)*(value-current)
        result.append(current if index+1 >= period else None)
    return result


def wilder(values, period):
    result, current = [], None
    for index, value in enumerate(values):
        if index+1 < period:
            result.append(None)
            continue
        current = sum(values[:period])/period if current is None else (current*(period-1)+value)/period
        result.append(current)
    return result


def calculate(bars):
    closes = [bar['close'] for bar in bars]
    ma = sma(closes,20)
    average = ema(closes,20)
    fast, slow = ema(closes,12), ema(closes,26)
    changes = [closes[i]-closes[i-1] for i in range(1,len(closes))]
    gains, losses = wilder([max(0,value) for value in changes],14), wilder([max(0,-value) for value in changes],14)
    tr = [max(bar['high']-bar['low'], abs(bar['high']-(closes[i-1] if i else bar['open'])), abs(bar['low']-(closes[i-1] if i else bar['open']))) for i,bar in enumerate(bars)]
    atr, trend_atr = wilder(tr,14), wilder(tr,10)
    macd = [a-b if a is not None and b is not None else None for a,b in zip(fast,slow)]
    signal_values = ema([value for value in macd if value is not None],9)
    signal_index = 0
    previous_upper = previous_lower = previous_trend = None
    result = []
    for i,bar in enumerate(bars):
        rsi = None
        if i and gains[i-1] is not None:
            gain,loss = gains[i-1],losses[i-1]
            rsi = 50.0 if gain == loss == 0 else 100.0 if loss == 0 else 100-100/(1+gain/loss)
        std = math.sqrt(sum((value-ma[i])**2 for value in closes[i-19:i+1])/20) if ma[i] is not None else None
        signal = None
        if macd[i] is not None:
            signal = signal_values[signal_index];signal_index += 1
        supertrend = None
        if trend_atr[i] is not None:
            mid = (bar['high']+bar['low'])/2
            upper,lower = mid+3*trend_atr[i],mid-3*trend_atr[i]
            if previous_upper is not None:
                upper = upper if upper < previous_upper or closes[i-1] > previous_upper else previous_upper
                lower = lower if lower > previous_lower or closes[i-1] < previous_lower else previous_lower
                supertrend = upper if previous_trend == previous_upper and closes[i] <= upper else lower if previous_trend == previous_upper else lower if closes[i] >= lower else upper
            else:
                supertrend = upper
            previous_upper,previous_lower,previous_trend = upper,lower,supertrend
        result.append({'sma20':ma[i],'ema20':average[i],'rsi14':rsi,'macd':macd[i],'macd_signal':signal,
                       'macd_histogram':macd[i]-signal if macd[i] is not None and signal is not None else None,
                       'bollinger_upper':ma[i]+2*std if std is not None else None,
                       'bollinger_lower':ma[i]-2*std if std is not None else None,'atr14':atr[i],'supertrend':supertrend})
    return result

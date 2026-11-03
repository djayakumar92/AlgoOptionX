"""Known indicator values, warm-up boundaries and causal prefixes."""
from algooptionx.market.indicators import calculate


def bars(values):return [{'open':value,'high':value+1,'low':value-1,'close':value} for value in values]


def test_flat_market_has_zero_macd_neutral_rsi_and_known_atr():
    result=calculate(bars([100]*40))
    assert result[12]['atr14'] is None and result[13]['atr14']==2
    assert result[13]['rsi14'] is None and result[14]['rsi14']==50
    assert result[18]['sma20'] is None and result[19]['sma20']==100
    assert result[32]['macd_signal'] is None and result[33]['macd_signal']==0
    assert result[-1]['macd_histogram']==0
    assert result[-1]['bollinger_upper']==result[-1]['bollinger_lower']==100


def test_rising_market_rsi_and_prefix_are_causal():
    first=calculate(bars(range(10,40)))
    later=calculate(bars(range(10,70)))
    assert later[:len(first)]==first
    assert first[19]['sma20']==19.5
    assert all(value['rsi14']==100 for value in first[14:])
    assert calculate([])==[]

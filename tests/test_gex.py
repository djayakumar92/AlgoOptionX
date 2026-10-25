import pandas as pd

from dhan_analyzer.signals import gex


def chain_rows(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _row(strike: float, option_type: str, gamma: float, oi: float) -> dict:
    return {"strike": strike, "option_type": option_type, "gamma": gamma, "oi": oi}


def test_calls_count_positive_and_puts_negative():
    chain = chain_rows(
        [_row(24000, "CE", 0.001, 100_000), _row(24000, "PE", 0.001, 40_000)]
    )
    [row] = gex.compute_strike_gex(chain, spot_price=24000)
    assert row.call_gex > 0
    assert row.put_gex < 0
    assert row.net_gex == row.call_gex + row.put_gex


def test_put_gamma_is_negated_even_if_feed_signs_it_negative():
    """The dealer-positioning sign is applied here, not trusted from the feed --
    a feed that starts signing put gamma negatively must not double-negate."""
    positive_feed = chain_rows([_row(24000, "PE", 0.001, 50_000)])
    negative_feed = chain_rows([_row(24000, "PE", -0.001, 50_000)])
    assert (
        gex.compute_strike_gex(positive_feed, 24000)[0].put_gex
        == gex.compute_strike_gex(negative_feed, 24000)[0].put_gex
    )


def test_far_strikes_are_excluded_by_range():
    chain = chain_rows(
        [_row(24000, "CE", 0.001, 10_000), _row(30000, "CE", 0.001, 10_000_000)]
    )
    strikes = [r.strike for r in gex.compute_strike_gex(chain, spot_price=24000)]
    assert strikes == [24000]


def test_gamma_flip_is_where_cumulative_net_changes_sign():
    chain = chain_rows(
        [
            _row(23800, "PE", 0.002, 200_000),  # heavy put gamma low -> cumulative negative
            _row(23800, "CE", 0.0001, 1_000),
            _row(24000, "CE", 0.002, 400_000),  # heavy call gamma -> flips positive here
            _row(24000, "PE", 0.0001, 1_000),
        ]
    )
    per_strike = gex.compute_strike_gex(chain, spot_price=23900)
    assert gex.gamma_flip_strike(per_strike) == 24000


def test_no_flip_when_all_one_sided():
    chain = chain_rows([_row(23900, "CE", 0.002, 100_000), _row(24000, "CE", 0.002, 100_000)])
    per_strike = gex.compute_strike_gex(chain, spot_price=23950)
    assert gex.gamma_flip_strike(per_strike) is None


def test_summarize_reports_negative_gamma_when_puts_dominate():
    chain = chain_rows(
        [_row(23900, "PE", 0.003, 500_000), _row(23900, "CE", 0.0005, 10_000)]
    )
    summary = gex.summarize(chain, spot_price=23900)
    assert summary.regime == gex.NEGATIVE_GAMMA
    assert summary.put_wall_strike == 23900
    assert "amplifies" in summary.note or "with moves" in summary.note


def test_summarize_degrades_cleanly_without_gamma_data():
    chain = chain_rows([{"strike": 24000, "option_type": "CE", "oi": 1000}])
    summary = gex.summarize(chain, spot_price=24000)
    assert summary.regime == gex.GAMMA_UNKNOWN
    assert summary.per_strike == []
    assert summary.gamma_flip_strike is None

"""Per-cycle pipeline: poll -> snapshot -> signals -> combine -> log.

Shared by dhan_analyzer/main.py (CLI) and dhan_analyzer/api/worker.py (FastAPI
background thread) so the analytical logic exists in exactly one place. Both
callers keep their own loop/retry/render shape around this; only the body of
one poll cycle lives here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import time

import pandas as pd
from dhan_analyzer.ingestion.providers import MarketDataProvider

from dhan_analyzer.ingestion.quality import is_regular_session, require_fresh_latest_bar
from dhan_analyzer.ingestion.scheduler import OptionChainPoller
from dhan_analyzer.signals import combine, momentum, oi_behavior, sentiment, trend
from dhan_analyzer.signals.combine import Suggestion
from dhan_analyzer.signals.momentum import MomentumSummary
from dhan_analyzer.signals.oi_behavior import OiBehaviorSummary
from dhan_analyzer.signals.sentiment import SentimentSummary
from dhan_analyzer.signals.trend import TrendSummary
from dhan_analyzer.storage import repository


@dataclass(frozen=True)
class CycleResult:
    ts: int
    spot_price: float
    chain: pd.DataFrame
    sentiment: SentimentSummary
    oi_behavior: OiBehaviorSummary
    trend: TrendSummary
    momentum: MomentumSummary
    suggestion: Suggestion


def run_cycle(
    conn,
    client: MarketDataProvider,
    poller: OptionChainPoller,
    under_symbol: str,
    under_security_id: str,
    under_segment: str,
    tracked_expiry: date,
    expiry_label: str,
    intraday_interval: int,
    iv_history: list[float],
) -> CycleResult | None:
    """Runs one poll cycle. Returns None if the chain came back empty (rare,
    caller should just skip the cycle). Raises OptionChainError on poll failure
    -- caller decides how to handle that (retry/backoff, keep last-good state).
    """
    result = poller.poll(conn, client, under_symbol, under_security_id, under_segment, tracked_expiry)
    chain_df = pd.DataFrame(result.rows)
    if chain_df.empty:
        return None
    chain_df["underlying"] = under_symbol
    chain_df["expiry"] = expiry_label

    latest, previous = repository.get_latest_two_snapshots(conn, under_symbol, tracked_expiry)

    sentiment_summary = sentiment.summarize(chain_df, result.spot_price)
    oi_summary = oi_behavior.classify(latest, previous)

    candles = repository.get_candles(conn, under_symbol, str(intraday_interval))
    if is_regular_session(int(time.time())):
        require_fresh_latest_bar(
            candles.to_dict("records"),
            intraday_interval,
            now_ts=int(time.time()),
        )
    trend_summary = trend.summarize(candles)

    atm_iv_avg = None
    if sentiment_summary.call_iv_atm is not None and sentiment_summary.put_iv_atm is not None:
        atm_iv_avg = (sentiment_summary.call_iv_atm + sentiment_summary.put_iv_atm) / 2
        iv_history.append(atm_iv_avg)
    momentum_summary = momentum.summarize(candles, atm_iv_avg, iv_history)

    suggestion = combine.combine(
        result.spot_price, chain_df, sentiment_summary, oi_summary,
        trend_summary, momentum_summary, expiry_label, under_symbol,
    )
    repository.log_signal(conn, under_symbol, suggestion)

    return CycleResult(
        ts=result.ts,
        spot_price=result.spot_price,
        chain=chain_df,
        sentiment=sentiment_summary,
        oi_behavior=oi_summary,
        trend=trend_summary,
        momentum=momentum_summary,
        suggestion=suggestion,
    )

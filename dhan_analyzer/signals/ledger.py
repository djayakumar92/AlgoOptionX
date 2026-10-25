"""The learning loop: turn every setup the engine armed into a graded,
reviewable outcome, and record what each trading session actually looked
like so tomorrow's read can be checked against yesterday's.

## What "learning" means here, precisely

Not a trained model. With the amount of history this app currently holds,
fitting anything would produce a number that looks authoritative and means
nothing. What this module does instead is the thing that has to come first
and that no model can substitute for: **build the record**.

Every session, the engine writes down what it saw (`daily_features`), which
setups it armed and on what evidence (`setup_events`), and -- once the
session has closed -- whether each one's stated assumption actually held
(`setup_outcomes`). `calibration.py` then reads that record back and reports
per-setup hit rates *with their sample sizes*, which is what lets the
displayed confidence be earned rather than asserted.

The consequence, stated plainly: on day one this system knows nothing about
its own reliability and says so. Every grade is capped at C until a setup has
twenty graded outcomes. That is the honest starting point, and it improves by
one session per session -- there is no shortcut that does not involve
inventing numbers.

## What the grading can and cannot prove

Outcomes are graded from **NIFTY's own 5-minute candles**, which this app
already stores reliably. That answers the question each setup actually asks:
did the level hold, did the break extend, did the range contain the day.

It does **not** measure option profit and loss. Doing that would need
per-strike historical option candles, and this project has already found
those to be unreliable to reconstruct for past expiries. So `result` here is
a level-based verdict on the setup's *thesis*, not a rupee return, and
nothing downstream is allowed to present it as one. A thesis that holds
usually pays, but the mapping is not one-to-one -- a straddle sale whose
range held still loses money if volatility repriced upward inside it.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime

import pandas as pd

from dhan_analyzer.signals import regime as regime_module
from dhan_analyzer.signals.setups import (
    BUY_PREMIUM,
    SELL_STRADDLE,
    SetupSignal,
)

WIN, LOSS, FLAT, NOT_TRIGGERED = "WIN", "LOSS", "FLAT", "NOT_TRIGGERED"

# A move smaller than this in NIFTY points is called flat rather than a
# marginal win or loss -- below roughly a tenth of a typical session's range,
# the sign of the result is noise and treating it as a win would flatter the
# record.
_FLAT_BAND_POINTS = 10.0


@dataclass(frozen=True)
class GradedOutcome:
    triggered: bool
    trigger_ts: int | None
    result: str  # WIN | LOSS | FLAT | NOT_TRIGGERED
    underlying_points: float | None
    mfe_points: float | None
    mae_points: float | None
    hit_target: bool
    hit_invalidation: bool
    note: str


# ------------------------------------------------------- recording writes --


def daily_feature_row(
    trade_date: str,
    summary: regime_module.RegimeSummary,
    structure_trend: str | None,
    atm_iv: float | None = None,
) -> dict:
    """The engine's read of a session, ready for `upsert_daily_features`.

    Deliberately stores the whole summary as JSON alongside the extracted
    columns: the columns are what queries slice on today, and the JSON is
    what makes it possible to ask a question of this data in six months that
    nobody thought to add a column for now.
    """
    return {
        "trade_date": trade_date,
        "captured_ts": int(datetime.now().timestamp()),
        "day_type": summary.day_type,
        "structure_regime": summary.structure_regime,
        "structure_trend": structure_trend,
        "gamma_regime": summary.gamma_regime,
        "premium_pricing": summary.premium_pricing,
        "premium_stance": summary.premium_stance,
        "stance_score": summary.stance_score,
        "implied_daily_move": summary.implied_daily_move_points,
        "realized_daily_move": summary.realized_daily_move_points,
        "move_edge_ratio": summary.move_edge_ratio,
        "atm_iv": atm_iv,
        "iv_percentile": summary.iv_percentile,
        "adx": summary.adx,
        "chop": summary.chop,
        "is_expiry_day": int(summary.is_expiry_day),
        "features_json": json.dumps(asdict(summary), default=str),
    }


def daily_outcome_row(trade_date: str, session_candles: pd.DataFrame, prev_close: float | None) -> dict | None:
    """What the session actually did, for the same `daily_features` row.

    This is the half of the record that makes the other half checkable --
    without it, the engine would be storing opinions with nothing to compare
    them against.
    """
    if session_candles is None or session_candles.empty:
        return None

    open_px = float(session_candles["open"].iloc[0])
    high = float(session_candles["high"].max())
    low = float(session_candles["low"].min())
    close = float(session_candles["close"].iloc[-1])

    return {
        "trade_date": trade_date,
        "captured_ts": int(datetime.now().timestamp()),
        "open": open_px,
        "high": high,
        "low": low,
        "close": close,
        "prev_close": prev_close,
        "gap_points": round(open_px - prev_close, 2) if prev_close is not None else None,
        "range_points": round(high - low, 2),
        "net_points": round(close - open_px, 2),
    }


def setup_event_row(
    trade_date: str,
    signal: SetupSignal,
    spot: float,
    summary: regime_module.RegimeSummary,
    armed_at: datetime | None = None,
) -> dict:
    """One armed setup, ready for `record_setup_event`.

    The regime context is copied onto the event rather than left to a join
    on `daily_features`, because the question calibration most wants to ask
    is "does this setup work in *this* regime" -- and that has to be answered
    from the conditions at the moment it armed, not the session's end-of-day
    summary, which may have changed regime by then.

    `armed_at` defaults to now, which is right in the live loop. It is
    injectable because grading replays a session's candles from the arm time
    forward: with a hardcoded clock, replaying past sessions grades every
    setup against zero bars and reports the whole catalog as never triggered.
    """
    return {
        "trade_date": trade_date,
        "setup_key": signal.key,
        "armed_ts": int((armed_at or datetime.now()).timestamp()),
        "spot_at_arm": spot,
        "action": signal.action,
        "side": signal.side,
        "direction": signal.direction,
        "score": signal.score,
        "grade": signal.grade,
        "strike": signal.strike,
        "entry_reference": signal.entry_reference,
        "stop_reference": signal.stop_reference,
        "target_reference": signal.target_reference,
        "expected_move_points": summary.implied_daily_move_points,
        "assumption": signal.assumption,
        "trigger_rule": signal.trigger,
        "invalidation_rule": signal.invalidation,
        "signal_json": json.dumps(asdict(signal), default=str),
        "structure_regime": summary.structure_regime,
        "day_type": summary.day_type,
        "premium_pricing": summary.premium_pricing,
        "gamma_regime": summary.gamma_regime,
        "session_window": summary.session_window,
        "is_expiry_day": int(summary.is_expiry_day),
    }


# ------------------------------------------------------------- the grader --


def _bars_after(candles: pd.DataFrame, ts: int) -> pd.DataFrame:
    return candles[candles["ts"] >= ts] if not candles.empty else candles


def _grade_buy_premium(event: dict, bars: pd.DataFrame) -> GradedOutcome:
    """A bought-option setup: it has to trigger first, then reach its target
    before its invalidation level.

    NOT_TRIGGERED is a first-class result, not a missing one. A setup that
    armed and never triggered cost nothing and proves nothing about the
    setup's edge -- lumping those in with losses would understate the rule,
    and lumping them in with wins would flatter it. They are counted
    separately throughout.
    """
    entry = event.get("entry_reference")
    stop = event.get("stop_reference")
    target = event.get("target_reference")
    bullish = event.get("direction") == "BULLISH"

    if entry is None or bars.empty:
        return GradedOutcome(
            False, None, NOT_TRIGGERED, None, None, None, False, False,
            "No entry level recorded, or no candles stored for that session.",
        )

    trigger_row = None
    for _, bar in bars.iterrows():
        close = float(bar["close"])
        if (bullish and close > entry) or (not bullish and close < entry):
            trigger_row = bar
            break

    if trigger_row is None:
        return GradedOutcome(
            False, None, NOT_TRIGGERED, None, None, None, False, False,
            f"NIFTY never closed a 5-minute candle {'above' if bullish else 'below'} "
            f"{entry:.0f}, so the entry condition never occurred.",
        )

    trigger_ts = int(trigger_row["ts"])
    entry_price = float(trigger_row["close"])
    after = bars[bars["ts"] > trigger_ts]

    if after.empty:
        return GradedOutcome(
            True, trigger_ts, FLAT, 0.0, 0.0, 0.0, False, False,
            "The entry condition occurred on the session's final candle, leaving nothing to grade.",
        )

    highs, lows, closes = after["high"], after["low"], after["close"]
    if bullish:
        mfe = float(highs.max() - entry_price)
        mae = float(entry_price - lows.min())
    else:
        mfe = float(entry_price - lows.min())
        mae = float(highs.max() - entry_price)

    hit_target = False
    hit_invalidation = False
    for _, bar in after.iterrows():
        close = float(bar["close"])
        if stop is not None and ((bullish and close < stop) or (not bullish and close > stop)):
            hit_invalidation = True
            break
        if target is not None and (
            (bullish and float(bar["high"]) >= target) or (not bullish and float(bar["low"]) <= target)
        ):
            hit_target = True
            break

    if hit_target:
        points = abs(target - entry_price)
        result, note = WIN, f"Target {target:.0f} was reached before the invalidation level gave way."
    elif hit_invalidation:
        points = -abs(entry_price - stop)
        result, note = LOSS, f"NIFTY closed back through {stop:.0f}, invalidating the setup's assumption."
    else:
        final = float(closes.iloc[-1])
        points = (final - entry_price) if bullish else (entry_price - final)
        if abs(points) < _FLAT_BAND_POINTS:
            result, note = FLAT, "Neither the target nor the invalidation level was reached; the session drifted."
        elif points > 0:
            result, note = WIN, "The session closed in the setup's favour without reaching the full target."
        else:
            result, note = LOSS, "The session closed against the setup, though the invalidation level never gave way."

    return GradedOutcome(
        True, trigger_ts, result, round(points, 1), round(mfe, 1), round(mae, 1),
        hit_target, hit_invalidation, note,
    )


def _grade_sell_level(event: dict, bars: pd.DataFrame) -> GradedOutcome:
    """A one-sided premium sale: the thesis is that a level holds.

    Treated as live from the moment it armed rather than waiting for a
    trigger. That is deliberate and it makes the record *harsher* than
    reality: a real trader waits for the rejection candle described in the
    setup's trigger rule, and would skip some of the cases counted as losses
    here. Erring toward the pessimistic side is the right direction for a
    number that will be used to decide whether to risk money.
    """
    level = event.get("stop_reference") or event.get("entry_reference")
    if level is None or bars.empty:
        return GradedOutcome(
            False, None, NOT_TRIGGERED, None, None, None, False, False,
            "No defended level recorded, or no candles stored for that session.",
        )

    # SELL_CE is bearish (the level is above price and must cap it);
    # SELL_PE is bullish (the level is below price and must hold it up).
    level_is_ceiling = event.get("action") == "SELL_CE"
    armed_ts = int(event["armed_ts"])

    breached_ts = None
    breach_points = None
    for _, bar in bars.iterrows():
        close = float(bar["close"])
        if (level_is_ceiling and close > level) or (not level_is_ceiling and close < level):
            breached_ts = int(bar["ts"])
            # How far past the defended level the breaking candle closed. This
            # is the loss, and it is recorded as a negative number: an earlier
            # version reported the end-of-session cushion instead, which could
            # be positive on a day the level broke and price later came back --
            # producing the nonsense of a 0% hit rate with positive average
            # points next to it.
            breach_points = -abs(close - level)
            break

    if level_is_ceiling:
        worst = float(bars["high"].max()) - level
    else:
        worst = level - float(bars["low"].min())

    final_close = float(bars["close"].iloc[-1])
    cushion = (level - final_close) if level_is_ceiling else (final_close - level)

    if breached_ts is not None:
        return GradedOutcome(
            True, armed_ts, LOSS, round(breach_points, 1), None, round(max(worst, 0.0), 1), False, True,
            f"NIFTY closed a 5-minute candle through {level:.0f}, which is exactly the condition "
            "this setup named as its invalidation.",
        )

    return GradedOutcome(
        True, armed_ts, WIN, round(cushion, 1), round(cushion, 1), round(max(worst, 0.0), 1), True, False,
        f"{level:.0f} held for the rest of the session -- the setup's assumption survived. "
        "Note this grades the level, not the option's profit.",
    )


def _grade_straddle(event: dict, bars: pd.DataFrame) -> GradedOutcome:
    """A both-sides sale: the thesis is that the session finishes inside the
    move the options were pricing.

    The verdict is taken on where the session *finished* relative to the
    anchor, not on how far it wandered, because that is what the sold options
    actually pay out on. How far it wandered is recorded too -- as the
    adverse excursion -- because that is the number that decides whether a
    stop would have been hit along the way, and a straddle that finished
    inside the band after a violent round trip is not the same trade as one
    that never moved. Both numbers are kept so neither story can be told
    alone.
    """
    band = event.get("expected_move_points")
    anchor = event.get("spot_at_arm")
    if not band or anchor is None or bars.empty:
        return GradedOutcome(
            False, None, NOT_TRIGGERED, None, None, None, False, False,
            "No priced move recorded at arm time, so there is no band to grade against.",
        )

    excursion = max(
        float(bars["high"].max()) - anchor,
        anchor - float(bars["low"].min()),
    )
    final_move = abs(float(bars["close"].iloc[-1]) - anchor)
    held = final_move <= band
    stop_would_have_hit = excursion > band

    note = (
        f"NIFTY finished {final_move:.0f} points from {anchor:.0f} against a priced band of "
        f"{band:.0f} -- {'inside' if held else 'outside'} it. Furthest it travelled intraday was "
        f"{excursion:.0f} points"
    )
    note += (
        ", which would have breached the band during the session even though it came back."
        if (held and stop_would_have_hit)
        else "."
    )

    return GradedOutcome(
        True, int(event["armed_ts"]),
        WIN if held else LOSS,
        round(band - final_move, 1),
        round(band - final_move, 1) if held else None,
        round(excursion, 1),
        held, not held,
        note,
    )


def grade_event(event: dict, session_candles: pd.DataFrame) -> GradedOutcome:
    """Grade one armed setup against its own session's 5-minute candles.

    `event` is a `setup_events` row (sqlite3.Row works directly -- it is
    indexed by column name like a dict). Dispatches on how the setup makes
    money, not on its name, so a new setup added to the catalog is graded
    correctly without touching this function as long as it declares the right
    action and levels.
    """
    event = dict(event)
    bars = _bars_after(session_candles, int(event["armed_ts"]))

    if event.get("action") == SELL_STRADDLE:
        return _grade_straddle(event, bars)
    if event.get("side") == BUY_PREMIUM:
        return _grade_buy_premium(event, bars)
    return _grade_sell_level(event, bars)


def outcome_row(event: dict, graded: GradedOutcome) -> dict:
    event = dict(event)
    return {
        "event_id": event["id"],
        "trade_date": event["trade_date"],
        "setup_key": event["setup_key"],
        "graded_ts": int(datetime.now().timestamp()),
        "triggered": int(graded.triggered),
        "trigger_ts": graded.trigger_ts,
        "result": graded.result,
        "underlying_points": graded.underlying_points,
        "mfe_points": graded.mfe_points,
        "mae_points": graded.mae_points,
        "hit_target": int(graded.hit_target),
        "hit_invalidation": int(graded.hit_invalidation),
        "note": graded.note,
    }


def parse_trade_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()

"""Assembles the prediction stack from state the app already keeps current,
and records what it decided so the ledger can grade it later.

Nothing here calls DhanHQ. Every input -- the latest option chain snapshot,
today's 5-minute candles, the tracked expiry -- is already maintained by the
Live worker, so this can run on every request and on the worker's own cadence
without touching a rate limit. Same reasoning as `/api/market-structure`.

Two entry points, deliberately separated:

- `build()` computes the read and returns it. Pure with respect to the
  database: it writes nothing, so a page refresh cannot alter the record.
- `evaluate_and_record()` computes the same read and then writes the
  session's feature row and any newly-armed setups to the ledger. Called on
  a throttle from the worker loop, never from a request handler -- otherwise
  the record of what the engine believed would depend on when somebody
  happened to open a browser tab.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import pandas as pd

from algooptionx.research.signals import (
    calibration,
    gex,
    ledger,
    market_structure,
    oi_walls,
    regime,
    risk,
    scenarios as scenarios_module,
    setups,
    trend,
)
from algooptionx.research.storage import repository

logger = logging.getLogger(__name__)

# How many past sessions of ATM implied volatility to read for the percentile.
# One reading per day, from `daily_features` -- not from the tick-level
# option-chain table, for two reasons. Methodologically, an IV percentile is
# conventionally a daily-close measure; feeding it thousands of intraday ticks
# from a handful of days makes today's own noise dominate its own percentile.
# Practically, the tick table holds millions of rows and cannot be filtered by
# IV on any existing index, so that query full-scanned it on every cycle --
# measured at minutes per pass, inside a loop meant to run every 60 seconds.
_IV_HISTORY_SESSIONS = 250

# Candles pulled for structure/trend. 3000 five-minute bars is roughly 40
# sessions -- enough for swing structure and ATR without loading the table.
_CANDLE_LIMIT = 3000


@dataclass(frozen=True)
class KeyLevel:
    """One price worth watching, for the level ladder.

    The ladder exists because a trader reads a market as an ordered stack of
    levels with price somewhere inside it, not as a list of statistics. Every
    level here is already computed somewhere else in the app -- this only
    collects them onto one axis and sorts them, which is the step that makes
    them usable at a glance.
    """

    label: str
    price: float
    kind: str  # SPOT | RESISTANCE | SUPPORT | TRIGGER | STOP | TARGET | REFERENCE
    detail: str
    distance_points: float  # signed: positive is above spot


@dataclass(frozen=True)
class PredictionRead:
    as_of: str
    spot_price: float | None
    regime: regime.RegimeSummary | None
    gex: gex.GexSummary | None
    structure: market_structure.MarketStructureSummary | None
    signals: list[setups.SetupSignal]
    best: setups.SetupSignal | None
    risk_assessment: risk.RiskAssessment | None
    key_levels: list[KeyLevel] = field(default_factory=list)
    scenarios: scenarios_module.ScenarioSet | None = None
    unavailable: str | None = None


def _latest_chain(conn, under_symbol: str, tracked_expiry: date) -> pd.DataFrame:
    ts = repository.latest_snapshot_ts(conn, under_symbol, tracked_expiry)
    if ts is None:
        return pd.DataFrame()
    return repository.get_snapshot_at(conn, under_symbol, tracked_expiry, ts)


def _iv_history(conn) -> list[float]:
    """One ATM implied-volatility reading per past session, newest first.

    Empty until the app has recorded some sessions, which makes the IV factor
    report "not enough history" rather than inventing a percentile -- the
    intended behaviour on a fresh install.
    """
    rows = conn.execute(
        "SELECT atm_iv FROM daily_features WHERE atm_iv IS NOT NULL "
        "ORDER BY trade_date DESC LIMIT ?",
        (_IV_HISTORY_SESSIONS,),
    ).fetchall()
    return [float(r[0]) for r in rows]


def _atm_iv(chain: pd.DataFrame, spot_price: float | None) -> float | None:
    if chain.empty or spot_price is None or "iv" not in chain.columns:
        return None
    strikes = chain["strike"].dropna().unique()
    if len(strikes) == 0:
        return None
    atm = min(strikes, key=lambda s: abs(s - spot_price))
    ivs = chain[(chain["strike"] == atm) & chain["iv"].notna()]["iv"]
    return float(ivs.mean()) if not ivs.empty else None


def _key_levels(
    spot: float,
    structure: market_structure.MarketStructureSummary | None,
    trend_summary,
    gex_summary: gex.GexSummary | None,
    call_walls: list,
    put_walls: list,
    best: setups.SetupSignal | None,
) -> list[KeyLevel]:
    """Every level worth watching, on one axis, sorted high to low.

    Deduplicated by price to the nearest point: several of these sources
    routinely land on the same number (the heaviest call open interest and the
    heaviest gamma strike are often the same strike), and a ladder that lists
    one price twice is harder to read than one that names it once.
    """
    candidates: list[KeyLevel] = []

    def add(label: str, price: float | None, kind: str, detail: str) -> None:
        if price is None:
            return
        candidates.append(
            KeyLevel(label, float(price), kind, detail, round(float(price) - spot, 1))
        )

    if structure is not None:
        add("Opening range high", structure.day_type.ib_high, "RESISTANCE",
            "High of the first 30 minutes. Breaking it is what a trend day does.")
        add("Opening range low", structure.day_type.ib_low, "SUPPORT",
            "Low of the first 30 minutes. Breaking it is what a trend day does.")
        add("Yesterday's high", structure.prev_day_high, "RESISTANCE",
            "Where sellers took control in the previous session.")
        add("Yesterday's low", structure.prev_day_low, "SUPPORT",
            "Where buyers took control in the previous session.")

    if trend_summary is not None:
        add("Day's average price", trend_summary.vwap, "REFERENCE",
            "Volume-weighted average price -- the level the session keeps returning to.")

    if call_walls:
        wall = call_walls[0]
        add(f"Call wall {wall.strike:g}", wall.strike, "RESISTANCE",
            "Heaviest call open interest nearby -- option writers defend this from above."
            + (" Built up today, so it carries real conviction." if wall.freshness == "FRESH" else ""))
    if put_walls:
        wall = put_walls[0]
        add(f"Put wall {wall.strike:g}", wall.strike, "SUPPORT",
            "Heaviest put open interest nearby -- option writers defend this from below."
            + (" Built up today, so it carries real conviction." if wall.freshness == "FRESH" else ""))

    if gex_summary is not None:
        add("Hedging flips here", gex_summary.gamma_flip_strike, "REFERENCE",
            "Above this, hedging flow damps moves. Below it, hedging flow amplifies them.")

    if best is not None:
        add("Entry trigger", best.entry_reference, "TRIGGER",
            "The level that has to give way before this trade exists.")
        if best.stop_reference is not None and best.stop_reference != best.entry_reference:
            add("Get out here", best.stop_reference, "STOP",
                "A close back through this proves the setup wrong.")
        add("Target", best.target_reference, "TARGET",
            "Where this trade is being played for.")

    add("NIFTY now", spot, "SPOT", "Where price is right now.")

    # Several sources routinely land on the same price -- an entry trigger sits
    # on the opening-range low it was derived from, the heaviest call open
    # interest sits on the heaviest gamma strike. Both labels are true, so
    # they are merged rather than one being silently dropped: "Opening range
    # low" alone loses the fact that it is today's trigger, and "Entry
    # trigger" alone loses why that level matters in the first place.
    priority = {"SPOT": 0, "TRIGGER": 1, "TARGET": 2, "STOP": 3, "RESISTANCE": 4, "SUPPORT": 4, "REFERENCE": 5}
    by_price: dict[int, KeyLevel] = {}
    extra_labels: dict[int, list[str]] = {}

    for level in sorted(candidates, key=lambda item: priority.get(item.kind, 9)):
        rounded = round(level.price)
        kept = by_price.get(rounded)
        if kept is None:
            by_price[rounded] = level
            extra_labels[rounded] = []
        elif level.label != kept.label:
            extra_labels[rounded].append(level.label.lower())

    merged: list[KeyLevel] = []
    for rounded, level in by_price.items():
        also = extra_labels[rounded]
        label = f"{level.label} · {' · '.join(also)}" if also else level.label
        detail = level.detail + ("  Also: " + "; ".join(also) + "." if also else "")
        merged.append(
            KeyLevel(label, level.price, level.kind, detail, level.distance_points)
        )

    return sorted(merged, key=lambda item: -item.price)


def build(
    conn,
    *,
    under_symbol: str,
    tracked_expiry: date,
    intraday_interval: int,
    spot_price: float | None,
    now: datetime | None = None,
) -> PredictionRead:
    """The full read: regime, gamma, structure, and the scored setup catalog.

    Degrades rather than raising. A missing chain or a short candle history
    produces a read with fewer factors and explicit warnings, which is a
    truthful answer -- raising would make the page look broken on a morning
    when the app has simply not polled yet.
    """
    now = now or datetime.now()
    if spot_price is None:
        return PredictionRead(
            as_of=now.isoformat(timespec="seconds"),
            spot_price=None,
            regime=None,
            gex=None,
            structure=None,
            signals=[],
            best=None,
            risk_assessment=None,
            unavailable=(
                "No live price yet -- the first market-data poll has not completed. "
                "This fills in within a few seconds of the market opening."
            ),
        )

    candles = repository.get_candles(conn, under_symbol, str(intraday_interval), limit=_CANDLE_LIMIT)
    daily = repository.get_candles(conn, under_symbol, "day", limit=500)
    chain = _latest_chain(conn, under_symbol, tracked_expiry)

    structure = (
        market_structure.summarize(candles, as_of=now.date(), bar_minutes=intraday_interval)
        if not candles.empty
        else None
    )
    trend_summary = trend.summarize(candles) if not candles.empty else None
    gex_summary = gex.summarize(chain, spot_price) if not chain.empty else None

    session_window = risk.classify_session_window(now)
    expiry_today = regime.is_expiry_day(now.date(), tracked_expiry)

    regime_summary = regime.summarize(
        spot_price=spot_price,
        chain=chain,
        daily_candles=daily,
        intraday_candles=candles,
        structure=structure,
        gex_summary=gex_summary,
        trend=trend_summary,
        iv_history=_iv_history(conn),
        current_atm_iv=_atm_iv(chain, spot_price),
        tracked_expiry=tracked_expiry,
        now=now,
        session_window=session_window,
    )

    call_walls, put_walls = oi_walls.detect_walls(chain, spot_price) if not chain.empty else ([], [])

    context = setups.SetupContext(
        spot_price=spot_price,
        chain=chain,
        session_candles=candles,
        structure=structure,
        trend=trend_summary,
        regime=regime_summary,
        gex=gex_summary,
        call_walls=call_walls,
        put_walls=put_walls,
        calibration=calibration.calibration_map(conn),
    )
    signals = setups.evaluate(context)
    best = setups.best_setup(signals)
    key_levels = _key_levels(
        spot_price, structure, trend_summary, gex_summary, call_walls, put_walls, best
    )
    risk_assessment = risk.assess_risk(now, expiry_today)

    return PredictionRead(
        as_of=now.isoformat(timespec="seconds"),
        spot_price=spot_price,
        regime=regime_summary,
        gex=gex_summary,
        structure=structure,
        signals=signals,
        best=best,
        risk_assessment=risk_assessment,
        key_levels=key_levels,
        scenarios=scenarios_module.build(
            spot_price=spot_price,
            summary=regime_summary,
            structure=structure,
            trend=trend_summary,
            gex_summary=gex_summary,
            signals=signals,
            key_levels=key_levels,
            call_walls=call_walls,
            put_walls=put_walls,
            risk_assessment=risk_assessment,
        ),
    )


def evaluate_and_record(
    conn,
    *,
    under_symbol: str,
    tracked_expiry: date,
    intraday_interval: int,
    spot_price: float | None,
    now: datetime | None = None,
) -> PredictionRead:
    """Build the read, then write it to the ledger.

    Both writes are idempotent within a session: `daily_features` upserts on
    the date, and `setup_events` is guarded by a unique key on
    (trade_date, setup_key) so a setup that stays armed for two hours is
    recorded once, at the moment it first armed -- which is the timestamp
    grading needs.
    """
    now = now or datetime.now()
    read = build(
        conn,
        under_symbol=under_symbol,
        tracked_expiry=tracked_expiry,
        intraday_interval=intraday_interval,
        spot_price=spot_price,
        now=now,
    )
    if read.regime is None:
        return read

    trade_date = now.date().isoformat()
    structure_trend = read.structure.structure_trend if read.structure else None
    chain = _latest_chain(conn, under_symbol, tracked_expiry)
    repository.upsert_daily_features(
        conn,
        ledger.daily_feature_row(
            trade_date, read.regime, structure_trend, atm_iv=_atm_iv(chain, read.spot_price)
        ),
    )

    for signal in read.signals:
        if signal.status != setups.ARMED:
            continue
        recorded = repository.record_setup_event(
            conn,
            ledger.setup_event_row(trade_date, signal, read.spot_price, read.regime, armed_at=now),
        )
        if recorded:
            logger.info(
                "Setup armed: %s (grade %s, score %.0f) at spot %.1f",
                signal.key, signal.grade, signal.score, read.spot_price,
            )

    return read


def grade_finished_sessions(conn, *, under_symbol: str, intraday_interval: int, today: date | None = None) -> int:
    """Grade every armed setup from a session that has already closed.

    Safe to call repeatedly -- events already carrying an outcome are not
    returned by the query, so this is a no-op once a day has been graded.
    Also fills in that session's actual open/high/low/close on its
    `daily_features` row, which is the half of the record that makes the
    engine's own read checkable.
    """
    today = today or date.today()
    pending = repository.get_ungraded_setup_events(conn, today.isoformat())
    if not pending:
        return 0

    graded_count = 0
    sessions_seen: set[str] = set()

    for event in pending:
        session_date = ledger.parse_trade_date(event["trade_date"])
        candles = repository.get_session_candles(
            conn, under_symbol, str(intraday_interval), session_date
        )
        if candles.empty:
            # No stored candles for that day -- a holiday, or history the app
            # was not running for. Leave it ungraded rather than recording a
            # verdict the data cannot support.
            continue

        outcome = ledger.grade_event(event, candles)
        repository.record_setup_outcome(conn, ledger.outcome_row(event, outcome))
        graded_count += 1

        if event["trade_date"] not in sessions_seen:
            sessions_seen.add(event["trade_date"])
            prev_close = repository.get_close_on_date(
                conn, under_symbol, str(intraday_interval), _previous_session(session_date)
            )
            row = ledger.daily_outcome_row(event["trade_date"], candles, prev_close)
            if row:
                repository.upsert_daily_features(conn, row)

    if graded_count:
        logger.info("Graded %d setup outcome(s) from finished sessions", graded_count)
    return graded_count


def _previous_session(session_date: date) -> date:
    """The trading day before session_date, weekend-aware.

    Holiday-blind, same as everything else in this project -- a holiday
    simply yields no close, and the gap column ends up null rather than wrong.
    """
    candidate = session_date - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate

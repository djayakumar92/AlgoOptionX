"""FastAPI app: serves the live-state API and the built React SPA as static files.

Run with: python -m uvicorn dhan_analyzer.api.app:app --host 127.0.0.1 --port 8000
(see "Start Analyzer.bat"). Single process, single port -- the user only ever
double-clicks the .bat; the browser opens itself once the server is ready.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
import webbrowser
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from dhan_analyzer import auth, instruments
from dhan_analyzer.api import backtest_worker, prediction
from dhan_analyzer.api.hlc_worker import RefreshCoordinator, backfill_journal, run_hlc_cycle
from dhan_analyzer.api.serialize import (
    serialize_cycle,
    serialize_hlc,
    serialize_journal_entry,
    serialize_learning,
    serialize_market_structure,
    serialize_prediction,
    serialize_risk,
    serialize_support_resistance,
)
from dhan_analyzer.api.state import BacktestState, HlcState, LiveState
from dhan_analyzer.api.worker import run_worker
from dhan_analyzer.auth import AuthError
from dhan_analyzer.config import PROJECT_ROOT, load_settings_or_exit
from dhan_analyzer.ingestion import chart_candles, historical, option_chain
from dhan_analyzer.signals import calibration, market_structure, oi_walls, risk, support_resistance
from dhan_analyzer.ingestion.chart_candles import ChartCandlesError
from dhan_analyzer.ingestion.option_chain import OptionChainError
from dhan_analyzer.ingestion.option_ohlc import EXCHANGE_SEGMENT as OPTION_EXCHANGE_SEGMENT
from dhan_analyzer.ingestion.option_ohlc import INSTRUMENT_TYPE as OPTION_INSTRUMENT_TYPE
from dhan_analyzer.ingestion.option_ohlc import MARKET_OPEN, last_completed_trading_day
from dhan_analyzer.instruments import InstrumentResolutionError
from dhan_analyzer.logging_setup import setup_logging
from dhan_analyzer.storage import db, repository

logger = logging.getLogger(__name__)

CANDLE_LOOKBACK_DAYS = 5
INSTRUMENT_TYPE_INDEX = "INDEX"
RECENT_SWINGS_FOR_ZONES = 12
MAX_BACKTEST_RANGE_DAYS = 120  # calendar days -- ~85 trading days, each a real paced DhanHQ fetch if not already graded
HOST, PORT = "127.0.0.1", 8000
FRONTEND_DIST = Path(os.environ.get("ALGOOPTIONX_RESEARCH_DIST", str(PROJECT_ROOT / "frontend" / "research-dist"))).resolve()
STARTUP_RETRY_ATTEMPTS = 3
STARTUP_RETRY_DELAY_SEC = 3.0


def _open_browser_soon() -> None:
    def _open():
        time.sleep(1.5)
        webbrowser.open(f"http://{HOST}:{PORT}")

    threading.Thread(target=_open, daemon=True).start()


def _retry_on_option_chain_error(fn, label: str):
    """DhanHQ's REST API occasionally returns an empty/invalid body for a
    perfectly valid call (confirmed live: 'Expecting value: line 1 column 1
    (char 0)', i.e. an empty response), unrelated to anything wrong with the
    request. That's a transient blip, not a real failure -- retrying a couple
    times clears it, same as it did manually during testing. Only give up (and
    let the caller's SystemExit fire) after repeated failures."""
    last_exc: OptionChainError | None = None
    for attempt in range(1, STARTUP_RETRY_ATTEMPTS + 1):
        try:
            return fn()
        except OptionChainError as exc:
            last_exc = exc
            logger.warning("%s failed (attempt %d/%d): %s", label, attempt, STARTUP_RETRY_ATTEMPTS, exc)
            if attempt < STARTUP_RETRY_ATTEMPTS:
                time.sleep(STARTUP_RETRY_DELAY_SEC)
    raise last_exc


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings_or_exit()
    setup_logging(settings)

    try:
        client = auth.build_client(settings)
    except AuthError as exc:
        print(f"Could not authenticate with DhanHQ:\n{exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    conn = db.connect(settings.db_path, settings.retention_days)

    under_symbol = settings.underlying.symbol
    under_segment = settings.underlying.segment
    under_security_id = instruments.resolve_index_security_id(under_symbol)
    intraday_interval = settings.historical.intraday_interval_min

    try:
        expiries = _retry_on_option_chain_error(
            lambda: option_chain.fetch_expiry_list(client, under_security_id, under_segment),
            "Fetching expiry list",
        )
    except OptionChainError as exc:
        print(f"Could not fetch the option expiry list from DhanHQ:\n{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    if not expiries:
        print(f"No option expiries returned for {under_symbol}.", file=sys.stderr)
        raise SystemExit(1)
    tracked_expiry = expiries[0]
    expiry_label = tracked_expiry.isoformat()

    # Resolved once at startup, not per-request -- reading the scrip master
    # CSV (~200k rows) takes ~1s, too slow to redo on every /api/risk poll.
    # The tracked expiry's lot size doesn't change during a single run.
    lot_size = instruments.lot_size_for_expiry(under_symbol, tracked_expiry)

    logger.info("Tracking %s, nearest expiry %s, lot size %d", under_symbol, expiry_label, lot_size)
    historical.catch_up_intraday(
        conn, client, under_symbol, under_security_id, under_segment, INSTRUMENT_TYPE_INDEX,
        intraday_interval, CANDLE_LOOKBACK_DAYS,
    )

    app.state.live_state = LiveState()
    app.state.hlc_state = HlcState()
    app.state.backtest_state = BacktestState()
    app.state.strike_window = settings.underlying.strike_window
    app.state.under_symbol = under_symbol
    app.state.expiry_label = expiry_label
    # Named for the chart-candles endpoint (Phase 5), which needs to resolve the
    # current ATM strike's CE/PE contracts on demand -- previously these only
    # existed bundled inside hlc_refresh_args.
    app.state.client = client
    app.state.under_security_id = under_security_id
    app.state.under_segment = under_segment
    app.state.tracked_expiry = tracked_expiry
    # Needed by /api/journal/entries -- conn was previously just a local
    # variable here, only reachable by the worker threads it's passed to directly.
    app.state.conn = conn
    app.state.settings = settings  # needed by /api/journal/backfill
    app.state.intraday_interval = intraday_interval  # needed by /api/market-structure
    app.state.lot_size = lot_size  # needed by /api/risk

    stop_event = threading.Event()
    worker_thread = threading.Thread(
        target=run_worker,
        args=(
            app.state.live_state, settings, client, conn, under_symbol, under_security_id,
            under_segment, tracked_expiry, expiry_label, stop_event,
        ),
        daemon=True,
    )
    worker_thread.start()

    # HLC data only changes once per session close -- no background loop, just a
    # one-shot fetch at startup plus a manual "Fetch Latest" (POST /api/hlc/refresh).
    app.state.hlc_coordinator = RefreshCoordinator()
    app.state.hlc_refresh_args = (
        app.state.hlc_state, settings, client, conn, under_symbol, under_security_id,
        under_segment, tracked_expiry,
    )
    app.state.hlc_coordinator.start(run_hlc_cycle, *app.state.hlc_refresh_args)

    print(f"Tracking {under_symbol}, expiry {expiry_label}. Serving on http://{HOST}:{PORT}")
    _open_browser_soon()

    yield

    stop_event.set()
    conn.close()


app = FastAPI(lifespan=lifespan)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "symbol": app.state.under_symbol,
        "expiry": app.state.expiry_label,
    }


@app.get("/api/settings")
def get_settings():
    """Read-only view of the running config for the Settings page -- excludes
    credentials (client_id/access_token) and local file paths, which aren't
    useful to show and shouldn't be exposed over HTTP."""
    s = app.state.settings
    return {
        "underlying": {
            "symbol": s.underlying.symbol,
            "segment": s.underlying.segment,
            "expiries_tracked": s.underlying.expiries_tracked,
            "strike_window": s.underlying.strike_window,
        },
        "polling": {
            "option_chain_interval_sec": s.polling.option_chain_interval_sec,
            "historical_refresh_interval_sec": s.polling.historical_refresh_interval_sec,
        },
        "historical": {
            "intraday_interval_min": s.historical.intraday_interval_min,
            "backfill_days": s.historical.backfill_days,
        },
        "hlc": {
            "threshold_points": s.hlc.threshold_points,
        },
        "trade_plan": {
            "target_points_per_day": s.trade_plan.target_points_per_day,
            "max_trades_per_day": s.trade_plan.max_trades_per_day,
        },
        "risk": {
            "capital": s.risk.capital,
            "max_risk_pct_per_trade": s.risk.max_risk_pct_per_trade,
            "max_daily_loss_pct": s.risk.max_daily_loss_pct,
            "lot_size": app.state.lot_size,
        },
    }


@app.get("/api/live/state")
def live_state():
    result, error, error_ts = app.state.live_state.snapshot()
    if result is None and error is None:
        raise HTTPException(status_code=503, detail="First poll cycle not complete yet.")

    payload = serialize_cycle(result, app.state.strike_window) if result is not None else {}
    payload["error"] = error
    payload["error_ts"] = error_ts
    return payload


@app.get("/api/hlc/state")
def hlc_state():
    result, error, error_ts = app.state.hlc_state.snapshot()
    refreshing = app.state.hlc_coordinator.in_progress
    if result is None and error is None and not refreshing:
        raise HTTPException(status_code=503, detail="First HLC cycle not complete yet.")

    payload = serialize_hlc(result) if result is not None else {}
    payload["error"] = error
    payload["error_ts"] = error_ts
    payload["refreshing"] = refreshing
    return payload


@app.post("/api/hlc/refresh")
def hlc_refresh():
    started = app.state.hlc_coordinator.start(run_hlc_cycle, *app.state.hlc_refresh_args)
    if not started:
        return {"started": False, "reason": "A refresh is already in progress."}
    return {"started": True}


@app.get("/api/live/oi-history")
def oi_history():
    """Total CE/PE OI over today's session so far, 5-minute buckets -- feeds
    the OI-over-time chart on the Live page. Reads already-stored poll
    snapshots (see scheduler.py); no new DhanHQ calls."""
    since_ts = int(datetime.combine(date.today(), MARKET_OPEN).timestamp())
    points = repository.get_oi_timeseries(app.state.conn, app.state.under_symbol, app.state.tracked_expiry, since_ts)
    return {"points": points}


@app.get("/api/market-structure")
def market_structure_state():
    """Computed synchronously per request from the candles already kept
    fresh by the Live worker's periodic historical.catch_up_intraday --
    no new DhanHQ calls, same reasoning as /api/live/oi-history. Degrades
    field-by-field (see market_structure.summarize) rather than erroring out
    when there isn't much local history yet."""
    candles = repository.get_candles(app.state.conn, app.state.under_symbol, str(app.state.intraday_interval), limit=3000)
    summary = market_structure.summarize(candles, as_of=date.today(), bar_minutes=app.state.intraday_interval)
    return serialize_market_structure(summary)


@app.get("/api/support-resistance")
def support_resistance_state():
    """Combines the real sources already computed elsewhere -- swing points
    and previous day/week levels (from candles), the HLC engine's own bands,
    VWAP, and fresh/stale OI walls from the live chain -- into scored zones.
    See signals/support_resistance.py for the source list and why volume
    profile/anchored VWAP/Fibonacci aren't included. No new DhanHQ calls:
    everything here reads state the Live worker and HLC worker already keep
    current."""
    live_result, _, _ = app.state.live_state.snapshot()
    hlc_result, _, _ = app.state.hlc_state.snapshot()

    spot_price = live_result.spot_price if live_result is not None else (
        hlc_result.nifty_close if hlc_result is not None else None
    )
    if spot_price is None:
        return serialize_support_resistance([], [], [])

    candles = repository.get_candles(app.state.conn, app.state.under_symbol, str(app.state.intraday_interval), limit=3000)
    as_of = date.today()

    # Only the most recent swings feed zone-scoring -- live-verified against
    # real data that using the full multi-day history here let a zone reach
    # "Institutional" purely by accumulating dozens of old swings from over a
    # week ago, which isn't what that classification is meant to signal.
    # market_structure.py's own MarketStructureSummary keeps the full history
    # for BOS/CHoCH trend continuity; zone-scoring is deliberately narrower.
    all_swings = market_structure.find_swings(candles) if not candles.empty else []
    swings = all_swings[-RECENT_SWINGS_FOR_ZONES:]
    prev_day = market_structure.previous_day_high_low(candles, as_of) if not candles.empty else None
    prev_week = market_structure.previous_week_high_low(candles, as_of) if not candles.empty else None
    prev_close = market_structure.previous_day_close(candles, as_of) if not candles.empty else None

    pivots = None
    if prev_day is not None and prev_close is not None:
        pivots = support_resistance.classic_pivots(prev_high=prev_day[0], prev_low=prev_day[1], prev_close=prev_close)

    call_walls, put_walls = ([], [])
    vwap = None
    if live_result is not None:
        call_walls, put_walls = oi_walls.detect_walls(live_result.chain, spot_price)
        vwap = live_result.trend.vwap

    hlc_bands = None
    if hlc_result is not None:
        hlc_bands = {
            "min_resistance": hlc_result.min_resistance,
            "max_resistance": hlc_result.max_resistance,
            "min_support": hlc_result.min_support,
            "max_support": hlc_result.max_support,
        }

    zones = support_resistance.build_zones(
        swings=swings,
        spot_price=spot_price,
        prev_day_high=prev_day[0] if prev_day else None,
        prev_day_low=prev_day[1] if prev_day else None,
        prev_week_high=prev_week[0] if prev_week else None,
        prev_week_low=prev_week[1] if prev_week else None,
        hlc_bands=hlc_bands,
        vwap=vwap,
        call_walls=call_walls,
        put_walls=put_walls,
        pivots=pivots,
    )
    return serialize_support_resistance(zones, call_walls, put_walls)


@app.get("/api/risk")
def risk_state():
    """Position-sizing reference and daily-risk read -- see
    signals/risk.py's module docstring for what this deliberately does and
    doesn't claim (no live intraday P&L tracking; stop distance is a
    reference table, not a false-precise single number, since the real stop
    is a live rule, not a fixed pre-market one)."""
    s = app.state.settings
    now = datetime.now()
    is_expiry_day = date.today() == app.state.tracked_expiry
    assessment = risk.assess_risk(now, is_expiry_day)

    hlc_result, _, _ = app.state.hlc_state.snapshot()
    leg_estimates: list[dict] = []
    if hlc_result is not None and hlc_result.trade_plan is not None:
        leg_lookup = {"CE": hlc_result.ce, "PE": hlc_result.pe}
        for leg in hlc_result.trade_plan.legs:
            analysis = leg_lookup.get(leg.option_type)
            if analysis is None:
                continue
            estimated_distance = abs(analysis.close_high_diff if leg.option_type == "CE" else analysis.close_low_diff)
            sizing = risk.position_sizing(
                s.risk.capital, s.risk.max_risk_pct_per_trade, app.state.lot_size, assessment,
                estimated_stop_distance=estimated_distance,
            )
            leg_estimates.append({
                "option_type": leg.option_type,
                "estimated_stop_distance": round(estimated_distance, 2),
                "note": "Estimated from the last completed session's own High/Low-to-Close distance for this leg -- not the live stop, which is only known once 5-minute candles start forming.",
                "sizing": asdict(sizing.estimated) if sizing.estimated else None,
            })

    sizing = risk.position_sizing(s.risk.capital, s.risk.max_risk_pct_per_trade, app.state.lot_size, assessment)

    last_graded = repository.get_most_recent_graded_day(app.state.conn)
    daily_status = risk.daily_risk_status(last_graded, s.risk.capital, app.state.lot_size, s.risk.max_daily_loss_pct)

    return serialize_risk(daily_status, sizing, leg_estimates)


@app.get("/api/journal/entries")
def journal_entries(limit: int = 30):
    rows = repository.get_journal_entries(app.state.conn, limit)
    return {"entries": [serialize_journal_entry(row) for row in rows]}


@app.post("/api/journal/backfill")
def journal_backfill(session_date: str):
    """One-off admin action -- logs and immediately grades a past session's
    plan (e.g. filling in journal history from before the app started
    tracking). Not part of the normal daily cycle; reuses hlc_coordinator so it
    can't run concurrently with (and double up DhanHQ calls against) a regular
    HLC cycle."""
    try:
        parsed_date = date.fromisoformat(session_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"session_date must be YYYY-MM-DD: {exc}") from exc

    started = app.state.hlc_coordinator.start(
        backfill_journal, app.state.settings, app.state.client, app.state.conn,
        app.state.under_symbol, app.state.under_security_id, app.state.under_segment,
        app.state.tracked_expiry, parsed_date,
    )
    if not started:
        return {"started": False, "reason": "An HLC refresh or backfill is already in progress."}
    return {"started": True}


@app.post("/api/backtest/run")
def backtest_run(start_date: str, end_date: str):
    """Kicks off a background backtest over [start_date, end_date] -- see
    backtest_worker.py. Genuinely slow (paced DhanHQ calls per new day), so
    this only starts the run and returns immediately; poll GET
    /api/backtest/status for progress. Reuses hlc_coordinator, same reason
    as /api/journal/backfill -- can't run alongside a regular HLC cycle."""
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Dates must be YYYY-MM-DD: {exc}") from exc

    if start > end:
        raise HTTPException(status_code=400, detail="start_date must not be after end_date.")

    last_available = last_completed_trading_day()
    if end > last_available:
        raise HTTPException(
            status_code=400,
            detail=f"end_date can't be later than the last completed trading day ({last_available.isoformat()}).",
        )
    if (end - start).days > MAX_BACKTEST_RANGE_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"Range too large -- max {MAX_BACKTEST_RANGE_DAYS} calendar days per run (each new day makes real, rate-limited DhanHQ calls).",
        )

    started = app.state.hlc_coordinator.start(
        backtest_worker.run_backtest, app.state.backtest_state, app.state.settings, app.state.client,
        app.state.conn, app.state.under_symbol, app.state.under_security_id, app.state.under_segment,
        app.state.tracked_expiry, start, end,
    )
    if not started:
        return {"started": False, "reason": "An HLC refresh, backfill, or another backtest is already in progress."}
    return {"started": True}


@app.get("/api/backtest/status")
def backtest_status():
    progress, result, error = app.state.backtest_state.snapshot()
    return {"progress": asdict(progress), "result": result, "error": error}


@app.get("/api/backtest/runs")
def backtest_runs(limit: int = 10):
    rows = repository.get_backtest_runs(app.state.conn, limit)
    return {"runs": [dict(row) for row in rows]}


@app.get("/api/prediction")
def prediction_state():
    """Today's regime read and the full scored setup catalog.

    Computed per request from state the Live worker already keeps fresh --
    no DhanHQ calls, same reasoning as /api/market-structure. This route is
    read-only by design: the ledger is written on the worker's own cadence
    (see worker.PREDICTION_INTERVAL_SEC), so what the engine is recorded as
    having believed never depends on when a browser tab was open."""
    live_result, _, _ = app.state.live_state.snapshot()
    hlc_result, _, _ = app.state.hlc_state.snapshot()
    spot_price = live_result.spot_price if live_result is not None else (
        hlc_result.nifty_close if hlc_result is not None else None
    )

    read = prediction.build(
        app.state.conn,
        under_symbol=app.state.under_symbol,
        tracked_expiry=app.state.tracked_expiry,
        intraday_interval=app.state.intraday_interval,
        spot_price=spot_price,
    )
    return serialize_prediction(read)


@app.get("/api/learning")
def learning_state():
    """What the ledger has actually proved so far, per setup and for the
    regime labels themselves. Empty on a fresh install, and says so rather
    than filling in placeholder statistics."""
    return serialize_learning(
        calibration.all_setup_records(app.state.conn),
        calibration.regime_report(app.state.conn),
    )


# The trading guide is served from the markdown file at the project root
# rather than duplicated into a React component. One copy: edit the file and
# the in-app page follows, with no chance of the two drifting apart -- which
# is exactly what happens to documentation that gets pasted into the UI.
GUIDE_PATH = PROJECT_ROOT / "HOW-TO-TRADE-WITH-IT.md"


@app.get("/api/guide")
def guide():
    if not GUIDE_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=f"The guide file is missing from {GUIDE_PATH.name}. It ships with the app.",
        )
    return {"markdown": GUIDE_PATH.read_text(encoding="utf-8")}


@app.get("/api/analytics/by-regime")
def analytics_by_regime():
    """The HLC rule's graded journal trades, split by the market regime the
    engine recorded for each trading day. Empty until the prediction engine
    and the journal overlap on at least one graded day."""
    return {"by_regime": [asdict(s) for s in calibration.journal_by_regime(app.state.conn)]}


@app.get("/api/learning/sessions")
def learning_sessions(limit: int = 60):
    """The raw daily record -- one row per session, the engine's read next to
    what the market did. This is the substrate everything else is computed
    from, exposed so it can be inspected rather than taken on trust."""
    rows = repository.get_daily_features(app.state.conn, limit)
    return {"sessions": [dict(row) for row in rows]}


@app.get("/api/chart/candles")
def chart_candles_endpoint(instrument: str, interval: str):
    """instrument: 'spot' | 'ce' | 'pe' (the current ATM strike's Call/Put, per
    the last HLC result). interval: '1' | '5' | '15' | 'day' -- see
    chart_candles.py; 3m/week/month are out of scope for this phase."""
    if instrument == "spot":
        security_id = app.state.under_security_id
        exchange_segment = app.state.under_segment
        instrument_type = INSTRUMENT_TYPE_INDEX
    elif instrument in ("ce", "pe"):
        result, _, _ = app.state.hlc_state.snapshot()
        if result is None:
            raise HTTPException(
                status_code=404, detail="HLC data not available yet -- fetch the HLC page first."
            )
        option_type = "CE" if instrument == "ce" else "PE"
        try:
            contracts = instruments.option_contracts_for_expiry(app.state.under_symbol, app.state.tracked_expiry)
        except InstrumentResolutionError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        contract = next(
            (c for c in contracts if c.strike == result.atm_strike and c.option_type == option_type), None
        )
        if contract is None:
            raise HTTPException(
                status_code=404, detail=f"No {option_type} contract found for strike {result.atm_strike}."
            )
        security_id = contract.security_id
        exchange_segment = OPTION_EXCHANGE_SEGMENT
        instrument_type = OPTION_INSTRUMENT_TYPE
    else:
        raise HTTPException(status_code=400, detail="instrument must be 'spot', 'ce', or 'pe'.")

    try:
        candles = chart_candles.fetch_candles(
            app.state.client, security_id, exchange_segment, instrument_type, interval
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ChartCandlesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"candles": candles}


if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    # A plain StaticFiles(html=True) mount only serves index.html for "/" -- a
    # direct navigation or page refresh on a client-side route like "/hlc" would
    # 404 (no file named "hlc" on disk). This catch-all makes those routes work
    # too: serve the real file if one exists (favicon, etc.), else fall back to
    # index.html so React Router can take over client-side.
    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    logger.warning("Frontend build not found at %s -- run `npm run build` in frontend/", FRONTEND_DIST)

# Dhan Analyzer (Phase 2)

A read-only NIFTY option-chain analyzer on DhanHQ v2: polls the option chain and
historical candles, computes sentiment/OI/trend/momentum signals, and serves a
suggested bias/entry/exit on a live web dashboard (FastAPI + React), plus a
`rich`-based terminal dashboard. A second page, HLC, automates the user's own
support/resistance + buyer/seller-domination trading rule from their spreadsheet.

**This phase places no orders.** It's an analytical dashboard only. Configuration accepts PAPER only; live execution is disabled and unsupported.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and fill in your DhanHQ credentials (see comments in
that file for how to get a 24h access token from web.dhan.co).

The React frontend is built once and shipped as static files (`frontend/dist/`),
served by FastAPI. Rebuilding it requires Node/npm and is only needed after
frontend source changes:

```bash
cd frontend
npm install
npm run build
```

## Run

Web dashboard (recommended) — double-click `Start Analyzer.bat`, or:

```bash
python -m uvicorn dhan_analyzer.api.app:app --host 127.0.0.1 --port 8000
```

Opens your browser to `http://127.0.0.1:8000` automatically. Close the console
window to stop.

Terminal dashboard (alternative):

```bash
python -m dhan_analyzer.main
```

Best run during NSE market hours (9:15–15:30 IST) so the option chain and candle
data are live. Only run one of these at a time — both poll the same DhanHQ
account and will collide on the shared rate limit if run concurrently.

## Tests

```bash
pytest
```

Tests cover the pure signal-computation functions (`dhan_analyzer/signals/`) with
synthetic data — no live API access required.

## Layout

- `dhan_analyzer/config.py`, `auth.py` — settings/credentials, DhanHQ client setup.
- `dhan_analyzer/instruments.py` — scrip master caching, NIFTY/option security-id lookups.
- `dhan_analyzer/ingestion/` — option chain + historical REST polling (rate-limit aware),
  live WebSocket feed (LTP cache, display-only).
- `dhan_analyzer/storage/` — SQLite schema and query helpers.
- `dhan_analyzer/signals/` — sentiment (PCR/max pain/IV skew), OI buildup/unwinding
  classification, trend (VWAP/MA/ADX), momentum (RSI/ROC/IV rank), and the combiner
  that merges them into a `Suggestion`.
- `dhan_analyzer/pipeline.py` — one poll cycle (poll → snapshot → signals →
  combine → log), shared by the CLI and the API's background worker.
- `dhan_analyzer/ingestion/option_ohlc.py` — per-instrument High/Low/Close for a
  specific past session, via intraday-minute candles (`fetch_session_ohlc`,
  reused for both option contracts and the NIFTY index itself — deliberately
  *not* DhanHQ's daily-candle endpoint, which stamps each daily candle at
  midnight IST of the *next* calendar day and silently returns the wrong
  day's close under a calendar-date query; confirmed live). The option-chain
  endpoint only has LTP/greeks, not day H/L, which is why this exists at all.
  `last_completed_trading_day()` resolves which session to use for the daily
  panel, skipping weekends, with a holiday-retry fallback.
- `dhan_analyzer/signals/hlc_strategy.py` — the user's own trading rule from
  `nifty_options_trading.xlsx`: ATM-by-premium-symmetry, support/resistance
  bands, per-leg buyer/seller domination, the combined-signal matrix — plus
  Weekly/Monthly range bands (`RangeBand`: close rounded to the nearest 100,
  bracketing strikes, combined CE+PE premium, sell/buy levels), reverse-engineered
  from a community "HLC daily planning" sheet. Pure functions, exact formulas
  (see `tests/test_hlc_strategy.py` for worked examples from both sources as
  regression checks).
- `dhan_analyzer/api/` — FastAPI app: `state.py` (thread-safe latest-cycle
  store, generic over `CycleResult`/`HlcResult`), `worker.py` (Live page's
  continuous background polling thread), `hlc_worker.py` (HLC page: one-shot
  `run_hlc_cycle` — fetched once at startup and again on demand via the page's
  "Fetch Latest" button/`POST /api/hlc/refresh`, not a periodic loop, since the
  read only changes once per session close; `RefreshCoordinator` keeps at most
  one cycle running at a time), `serialize.py` (JSON shaping), `app.py` (routes
  + static SPA hosting with a client-side-routing fallback).
- `dhan_analyzer/ingestion/chart_candles.py` — candle *series* (not just one
  session's H/L/C) for the Trading Setup page's charts, at 1m/5m/15m/Day.
  `GET /api/chart/candles?instrument=spot|ce|pe&interval=...` in `app.py`
  resolves `ce`/`pe` to whichever strike the HLC page's last successful cycle
  found as the ATM.
- `dhan_analyzer/presentation/cli_dashboard.py` — `rich`-based terminal dashboard.
- `frontend/` — Vite + React + TypeScript SPA (Live / HLC / Trading Setup pages,
  `react-router-dom` navigation, `lightweight-charts` for candlesticks). Built
  once, served as static files by the FastAPI process — the user's PC only
  needs Node/npm if the frontend source itself changes, never just to run the app.

See the plan this was built from for design rationale and what's intentionally out
of scope for Phase 2 (backtesting, the daily journal, unusual-activity detection —
planned as follow-up phases). The HLC page automates what the spreadsheet
*labels* (Buyer/Seller/Panic/Profit-Booking/Combined-Signal); it does not yet
suggest an exit/stop-loss or an action on Strong/Indecision days — those are
still open questions for the user to answer before that layer gets built.


## Execution mode

The application is research-only. Configuration accepts PAPER mode only; live execution is unsupported and the project contains no order-submission path.

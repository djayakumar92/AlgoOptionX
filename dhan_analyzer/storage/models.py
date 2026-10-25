"""SQLite schema definitions for the analyzer's local store.

Kept as plain DDL (no ORM) — a single-user tool with a handful of tables doesn't
need the indirection, and it keeps the "previous snapshot" diff queries in
repository.py transparent and easy to hand-tune.
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
    symbol   TEXT    NOT NULL,
    interval TEXT    NOT NULL,   -- e.g. '5' (minutes) or 'day'
    ts       INTEGER NOT NULL,   -- epoch seconds, candle open time
    open     REAL    NOT NULL,
    high     REAL    NOT NULL,
    low      REAL    NOT NULL,
    close    REAL    NOT NULL,
    volume   INTEGER NOT NULL DEFAULT 0,
    oi       INTEGER,
    PRIMARY KEY (symbol, interval, ts)
);

CREATE TABLE IF NOT EXISTS option_chain_snapshot (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    underlying     TEXT    NOT NULL,
    expiry         TEXT    NOT NULL,   -- ISO date
    strike         REAL    NOT NULL,
    option_type    TEXT    NOT NULL,   -- 'CE' or 'PE'
    ts             INTEGER NOT NULL,   -- epoch seconds, poll time
    ltp            REAL,
    oi             INTEGER,
    prev_day_oi    INTEGER,
    volume         INTEGER,
    iv             REAL,
    delta          REAL,
    theta          REAL,
    gamma          REAL,
    vega           REAL,
    bid            REAL,
    ask            REAL,
    bid_qty        INTEGER,
    ask_qty        INTEGER
);

CREATE INDEX IF NOT EXISTS idx_option_chain_lookup
    ON option_chain_snapshot (underlying, expiry, strike, option_type, ts);

-- Supports the OI-history time-range query (repository.get_oi_timeseries):
-- "all rows for this underlying/expiry with ts >= X", grouped by ts. The
-- index above is strike-major, useless for a ts-range scan across all
-- strikes -- this one is ts-major within (underlying, expiry) instead.
CREATE INDEX IF NOT EXISTS idx_option_chain_ts_range
    ON option_chain_snapshot (underlying, expiry, ts);

CREATE TABLE IF NOT EXISTS signals_log (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                   INTEGER NOT NULL,
    underlying           TEXT    NOT NULL,
    bias                 TEXT    NOT NULL,
    confidence           REAL    NOT NULL,
    suggested_instrument TEXT,
    entry_zone           TEXT,
    stop_loss            TEXT,
    watch_level          TEXT,
    rationale            TEXT,
    signals_json         TEXT
);

CREATE INDEX IF NOT EXISTS idx_signals_log_ts ON signals_log (underlying, ts);

CREATE TABLE IF NOT EXISTS journal_entries (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date     TEXT    NOT NULL,   -- ISO date, the completed session this plan's numbers came from
    trade_date       TEXT    NOT NULL,   -- ISO date, the NEXT trading session this plan is meant to be acted on
    option_type      TEXT,               -- 'CE' or 'PE' -- NULL on a sit-out (NO_TRADE) day
    strike           REAL,
    entry_trigger    REAL,
    target           REAL,
    target_points    REAL,
    combined_signal  TEXT    NOT NULL,
    note             TEXT,               -- build_trade_plan()'s reasoning, e.g. why it sat out
    outcome          TEXT    NOT NULL DEFAULT 'PENDING',
    realized_points  REAL,
    created_ts       INTEGER NOT NULL,
    resolved_ts      INTEGER
);

CREATE INDEX IF NOT EXISTS idx_journal_entries_trade_date ON journal_entries (trade_date);

CREATE TABLE IF NOT EXISTS backtest_runs (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date               TEXT    NOT NULL,
    end_date                 TEXT    NOT NULL,
    status                   TEXT    NOT NULL,   -- 'DONE' or 'FAILED' -- in-progress runs live in memory only, see BacktestState
    created_ts               INTEGER NOT NULL,
    completed_ts             INTEGER,
    total_days               INTEGER,
    graded_trades            INTEGER,
    no_trade_days            INTEGER,
    not_triggered            INTEGER,
    net_points               REAL,
    win_rate                 REAL,
    profit_factor            REAL,
    expectancy_points        REAL,
    avg_r                    REAL,
    max_drawdown_points      REAL,
    largest_win              REAL,
    largest_loss             REAL,
    max_consecutive_losses   INTEGER,
    error                    TEXT
);

CREATE INDEX IF NOT EXISTS idx_backtest_runs_created ON backtest_runs (created_ts);

-- ---------------------------------------------------------------------
-- Learning ledger (signals/ledger.py, signals/calibration.py)
--
-- Three tables, one purpose: make every decision the setup engine takes
-- reviewable after the fact, so its confidence can be earned from real
-- outcomes instead of asserted. Nothing in the app is allowed to display a
-- win rate that did not come from setup_outcomes.
-- ---------------------------------------------------------------------

-- One row per trading session: the market's own character that day, plus
-- what it actually went on to do. This is the "learn from daily NIFTY
-- changes" substrate -- it accrues one row a day forever, and unlike the
-- option-chain snapshots it is small enough to keep permanently.
CREATE TABLE IF NOT EXISTS daily_features (
    trade_date              TEXT    PRIMARY KEY,   -- ISO date
    captured_ts             INTEGER NOT NULL,

    -- what the market did (filled at end of session)
    open                    REAL,
    high                    REAL,
    low                     REAL,
    close                   REAL,
    prev_close              REAL,
    gap_points              REAL,                  -- open - prev_close
    range_points            REAL,                  -- high - low
    net_points              REAL,                  -- close - open

    -- how the engine read it (filled at decision time)
    day_type                TEXT,
    structure_regime        TEXT,
    structure_trend         TEXT,
    gamma_regime            TEXT,
    net_gex                 REAL,
    premium_pricing         TEXT,
    premium_stance          TEXT,
    stance_score            REAL,
    implied_daily_move      REAL,
    realized_daily_move     REAL,
    move_edge_ratio         REAL,
    atm_iv                  REAL,                  -- that session's ATM implied volatility, one reading a day
    iv_percentile           REAL,
    adx                     REAL,
    chop                    REAL,
    is_expiry_day           INTEGER NOT NULL DEFAULT 0,
    features_json           TEXT                   -- full RegimeSummary, for later re-analysis
);

-- One row each time a setup first becomes ARMED in a session. Deduped on
-- (trade_date, setup_key): the engine re-evaluates every poll, and logging
-- every evaluation would drown the real events in thousands of duplicates.
CREATE TABLE IF NOT EXISTS setup_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date          TEXT    NOT NULL,
    setup_key           TEXT    NOT NULL,
    armed_ts            INTEGER NOT NULL,
    spot_at_arm         REAL    NOT NULL,

    action              TEXT    NOT NULL,   -- BUY_CE | BUY_PE | SELL_CE | SELL_PE | SELL_STRADDLE
    side                TEXT    NOT NULL,   -- BUY_PREMIUM | SELL_PREMIUM
    direction           TEXT    NOT NULL,
    score               REAL    NOT NULL,
    grade               TEXT    NOT NULL,
    strike              REAL,
    entry_reference     REAL,
    stop_reference      REAL,
    target_reference    REAL,
    expected_move_points REAL,              -- the day's priced move at arm time; the straddle setup's band

    assumption          TEXT,
    trigger_rule        TEXT,
    invalidation_rule   TEXT,
    signal_json         TEXT,               -- the full SetupSignal as evaluated

    -- regime context copied here so calibration can slice by it without a join
    structure_regime    TEXT,
    day_type            TEXT,
    premium_pricing     TEXT,
    gamma_regime        TEXT,
    session_window      TEXT,
    is_expiry_day       INTEGER NOT NULL DEFAULT 0,

    UNIQUE (trade_date, setup_key)
);

CREATE INDEX IF NOT EXISTS idx_setup_events_key ON setup_events (setup_key, trade_date);

-- Graded result of one setup_event, written after that session closes.
-- Graded from the underlying's own 5-minute candles, which the app already
-- stores -- see ledger.grade_event() for exactly what that can and cannot
-- prove, and why `result` is a level-based proxy rather than trade P&L.
CREATE TABLE IF NOT EXISTS setup_outcomes (
    event_id            INTEGER PRIMARY KEY REFERENCES setup_events(id),
    trade_date          TEXT    NOT NULL,
    setup_key           TEXT    NOT NULL,
    graded_ts           INTEGER NOT NULL,

    triggered           INTEGER NOT NULL,   -- did the entry condition actually occur
    trigger_ts          INTEGER,
    result              TEXT    NOT NULL,   -- WIN | LOSS | FLAT | NOT_TRIGGERED
    underlying_points   REAL,               -- favourable movement captured, in NIFTY points
    mfe_points          REAL,               -- max favourable excursion after trigger
    mae_points          REAL,               -- max adverse excursion after trigger
    hit_target          INTEGER NOT NULL DEFAULT 0,
    hit_invalidation    INTEGER NOT NULL DEFAULT 0,
    note                TEXT
);

CREATE INDEX IF NOT EXISTS idx_setup_outcomes_key ON setup_outcomes (setup_key);
"""

# Enterprise demo requirements

## DEMO-01 — deterministic shared market
Eight scenarios: bullish, bearish, sideways, gap-up, gap-down, risk rejection,
disconnection and lifecycle. One scenario/session/tick governs candles, quotes,
analysis, positions and journal. Scenario switch requires flat positions and
preserves prior sessions. Candles aggregate completed 5/30-minute windows without
future bars. Fixed aware clock, fixture lot 65 and explicit synthetic labels.

## DEMO-02 — defined-risk calculations
Bull put credit spread, bear call credit spread and iron condor use same-expiry,
equal-quantity legs; invalid ordering/quantity/expiry/quotes rejected. European
Black–Scholes fixture pricing uses annual rate 6%, no dividends, ACT/365 years,
flat volatility 18% across strikes and both rights. This is an illustrative
pricing assumption, not an exchange or margin model. Paise are rounded half-up.
Bid/ask spread is ₹0.80, slippage ₹0.05/unit/leg, fee ₹20/leg/fill. Show gross and
net credit, expiry payoff, max profit/loss, breakevens, costs and assumptions.
Reserve includes the theoretical expiry loss and conservative exit spread/slippage/fee allowance; label it
simulation reserve, never broker margin. Support 1–5 fixture lots.

## DEMO-03 — safe atomic paper lifecycle
Separate demo SQLite database, never data/paper.db or data/dhan_analyzer.db.
₹5 lakh virtual capital; max 3 open strategies; 1% capital per-strategy max-loss
budget; 40% capital aggregate reserve cap; 2% daily-loss entry lock. Atomic all-leg
open/close, exact paise accounting, command idempotency, stale quote rejection,
restart/history preservation. Disconnected data blocks entries; deterministic
simulation-only emergency close remains available and records the assumed exit
quotes. Emergency stop disables new trades until a new flat session. Risk
rejections are audited and cannot change cash, reserves or positions.

## DEMO-04 — nine useful screens
Command Center, Market Intelligence, Options Intelligence, Strategy Builder,
Paper Trading, Risk Monitor, Journal, Research and Backtesting, AI Insights and
Governance. Working navigation, scenarios, timeframe/expiry/strike/leg controls,
preview and confirmation, close/kill, journal filters/notes, backtest configuration
and recovery. Every conclusion cites observations and limitations. Pre-authored
AI commentary fixtures are explicitly distinguished from live inference.

## DEMO-05 — design and accessibility
Existing light/dark/system themes; desktop 1440, tablet 1024 and mobile 390 widths.
Named native controls, visible focus, dialog focus restoration, keyboard operation,
text risk indicators, chart summaries and bounded table scrolling. Every applicable
loading/empty/ready/error/stale/disabled/permission state specified. WCAG 2.2 AA
is a scoped target, not certification. Proposed navigation/load budget: 2000ms
in pinned local browser, five samples; response payload budget: 1MB.

## DEMO-06 — evidence and final handoff
Financial known-answer/property checks; transaction/restart/idempotency/rejection
checks; no-broker/no-fallback boundary checks; A–H cross-screen browser flows;
responsive/theme/keyboard/accessibility/visual/performance evidence. UI evidence
maps actual native browser reports and attachments to frozen design cases and
renderer/fixture identity. Source-bound native tests, separate read-only review,
actual human acceptance, startup verification and presenter walkthrough required.
No deployment, guaranteed prediction, profitability or certified compliance claims.

## Frozen financial and safety conventions
Expiry choices: 2026-11-03T15:30:00+05:30 and 2026-11-10T15:30:00+05:30.
Clock starts 2026-11-02T09:15:00+05:30. ACT/365 uses 31536000 seconds/year.
Spots/strikes enter the pricing function in rupees; executable prices and ledger
amounts are integer paise, rounded once half-up per unit quote. Delta is per unit,
gamma per rupee, vega per percentage point IV, theta per calendar day and rho per
percentage point annual rate. At expiry return intrinsic and explicit unavailable
Greeks; reject nonfinite/nonpositive spot/strike/volatility and negative time.
Bid is max(0, mark−₹0.40), ask mark+₹0.40; show floor effects and liquidity warnings.

Entry cash = prior cash + executable received premium − executable paid premium
− entry fees. Equity = cash + signed long-minus-short mark values. Received premium
is offset by liability and never increases original-capital risk budgets. Reserve
is encumbered capital, not an extra cash debit. Available risk capital = original
capital − aggregate reserve; entries must also satisfy per-trade 1% original-capital
budget and equity/daily-loss checks. Exit adds signed executable closing cashflow
minus exit fees. Realized P&L includes both fees. Show mark equity separately from
estimated liquidation equity. Reserve = max(0, strike-width liability − entry net
credit) + maximum per-leg exit spread/slippage allowance + exit fees. This is an
illustrative conservative reserve, not an exchange guarantee; theoretical expiry
bounds and pre-expiry executable-close estimates are separately labeled.

Quote tokens bind session, scenario revision, tick, pricing version, contract IDs,
expiry, lots, all prices and costs. Quotes have no wall-clock expiry because market
time advances only on explicit scenario steps; tick/session changes invalidate
them. Duplicate key+payload returns its original outcome; changed payload rejects.

Disconnection freezes the last-valid quote tick. Entries reject. Emergency stop
first durably latches killed, then atomically flattens strategies in a second
transaction using explicitly labeled last-valid synthetic executable quotes. On
failure, preserve the latch, positions and pending-close/error state for retry and
restart. New session requires flat positions; it never clears an active position.
Demo DB paths resolving to original paper/research DBs reject at startup.

Research is a fixed-rule illustrative evaluation, with no fitting or training.
Evaluate nonoverlapping 10-bar trades from tick 30; close each before a split/fold
boundary. Chronological 60/40 split and three contiguous folds report their own
sample counts, costs, net P&L and peak-to-trough equity drawdown. Label fold
summaries as sequential evaluations, not evidence of trained-model validation.

Daily loss = max(0, original capital − current estimated liquidation equity),
including realized/unrealized P&L and all declared opening/estimated closing costs.
Equality at the 2% limit locks new entries. The 1% trade budget applies to the full
conservative reserve, not merely theoretical expiry loss. Reject entry if net
maximum profit after declared round-trip costs is nonpositive.
The 1MB API payload budget is checked as a separate failure-sensitive API test.
The 1024px tablet layout is an additional functional browser gate beyond the
390/1440 state/theme design matrix. Demo text/SVG uses the installed DejaVu Sans
font explicitly; the renderer pins that actual font file, with no external fonts.

## DEMO-07 — first interactive chart milestone
Replace the demo's static candlestick surface with the already installed
lightweight-charts 5.2.1 library. Reuse its native zoom, drag-pan and crosshair;
provide named Zoom in/out, Pan left/right and Fit data controls plus keyboard
crosshair movement and visible OHLCV readout. Preserve 5/30-minute switching,
responsive themes, completed-bar causality and explicit synthetic labels.

Add a synthetic volume histogram, toggled EMA9 and session VWAP. EMA9 uses
alpha=2/(9+1), first-close initialization, full precision in calculation and a
visible warm-up count until nine completed displayed bars exist. Session VWAP at
each displayed close uses only observed one-minute candles since session open:
sum((high+low+close)*incremental_volume)/(3*sum(incremental_volume)), with units
converted from paise to index points. Zero cumulative volume yields unavailable
VWAP; no future or missing bars are silently filled. Indicators are illustrative
analytics, not forecasts or exchange trade VWAP. Independently test numeric
vectors, warm-up, timeframe consistency and prefix invariance.

Add horizontal-line and two-point trendline annotations through chart clicks and
accessible price/bar inputs, with per-line removal, cancel and clear controls.
Annotations are session-scoped client view state shared by dashboard/market views;
they never mutate quotes, orders, risk or the database. Reset for a new session;
no persistence across reload, draggable editing, full TradingView parity or
multi-session historical charting is promised. Bound annotation count to 32 and
reject nonfinite/nonpositive prices or invalid/unobserved bar endpoints.

Acceptance: actual browser tests demonstrate zoom/pan/crosshair range/readout
changes, indicator toggles and numeric evidence, both drawing modes and keyboard
alternatives, removal/reset, 5/30 switching and responsive layout. Retain real
scenario/option/strategy flows, independently known-answer financial tests,
broker-isolation checks, current native evidence and separate review. Existing
216 declared state/theme/viewport cases remain; chart-specific functional cases
are additional checks. Final human acceptance is separate from implementation.

### DEMO-06 evidence packaging amendment
Retain all 216 frozen UI cases, every declared validation area and native
source/task/profile/fixture binding. The native validator's existing 512-file and
16MiB budgets remain unchanged. Support a per-case JSON area bundle shared by
that case's ui-AREA attachments; require exact case identity, exact area inventory
and passing nested area results. Existing flat reports remain supported. Identical
measured renderer/fixture/viewport/theme profiles may share an immutable hashed
file; no fabricated profile or declared success substitutes for actual execution.
Use native run-contained attachment paths without per-test copying of shared
files. Keep screenshot/comparison identities and performance samples intact.
Independent negative tests must reject missing, extra, wrong-case, failed or
malformed packed areas. No policy/schema limit, authority, approval, trading model
or business UI is relaxed or added by this amendment.

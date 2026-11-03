# Design revision 1 — local enterprise demo

Route namespace /demo; same-origin API /api/demo only. Existing workspace remains
the default route. A separate demo engine owns SQLite sessions, commands, positions,
audit and journal notes; no imports from research, broker SDKs or harness. Browser
local storage holds only theme/view preferences, never authoritative trading state.

## Screen wireframes
1. Command: sidebar; persistent DEMO / synthetic / scenario / clock / health bar;
   capital, equity, reserve and loss cards; 5-minute candles with timeframe toggle;
   30-minute confirmation; observations and risk summary; strategy shortcut.
2. Market: chart and timeframe; structure/support/resistance/volume/volatility;
   bullish/neutral/bearish observation cards, gap context and explicit limitations.
3. Options: expiry control; call/strike/put quote table with IV, OI/change, volume,
   spread, LTP and Greeks; selected strike routes to builder; liquidity warnings.
4. Strategy: preset, equal lots and leg strike selectors; server preview; SVG payoff
   and numerical table; costs, breakevens, net max profit/loss, reserve; confirmation.
5. Paper: open strategy cards with per-leg details; liquidation P&L; close
   confirmation; rejected/filled history; simulation emergency stop.
6. Risk: capital/reserves/max-loss/daily-loss cards; strategy concentration table;
   numerical alerts; stale/disconnected/disabled states and recovery control.
7. Journal: event/trade filters; immutable entry/exit and costs; notes/category
   editor; previous-session trades and empty state. Audit export is read-only.
8. Research: scenario/strategy/split configuration; synthetic backtest results;
   sample count, drawdown, cost assumptions, in/out-sample/walk-forward disclosure.
9. Insights: pre-authored analysis fixture, supporting data, timestamp/version,
   limits, human-review state, research/execution separation and local audit chain.

## Shared states and interactions
Loading: retain navigation and show named busy status. Empty: explain next action.
Error: readable reason and retry. Stale: preserve last snapshot, label it and block
entries server-side. Disabled: name the reason and recovery. Permission: live mode
is unavailable by construction and cannot be toggled. Ready: current scenario and
timestamp visible. Risk never uses color alone. Use actual backend data for numbers.

Scenario change creates a fresh account only when flat; never discards positions.
Timeframe, filter and expiry changes are read-only. Re-preview on every leg/lot
change. Confirmation includes the exact quote token; reject if tick/session changed.
Exit and emergency controls use explicit confirmation and return focus to opener.

## Financial assumptions and non-goals
Black–Scholes European mark for illustrative fixture only; flat 18% IV for calls and
puts at every strike; rates and time disclosed. Payoff is computed from signed leg
intrinsics at expiry, executable premium and quantity. Costs included conservatively
for both entry and eventual exit. Reserve is simulation-only; no naked shorts,
partial fills, physical settlement, expiry exercise, live broker margin or
validated historic backtests. Keep existing paper engine and databases untouched.

## Scope, order and recovery
D1 src/algooptionx/demo/ plus API wiring; D2–D6
apps/web/src/features/demo/ plus a route entry; D7 tests/paper/test_demo.py,
tests/market/test_demo_pricing.py, apps/web/tests/demo.spec.ts and native evidence.
Complete missing browser evidence collection in src/algooptionx_harness/ first.
One bounded native demo task may implement D1–D6 sequentially to avoid artificial
cross-child source/approval churn; full aggregate checks and independent review
remain mandatory. Freeze hashes before task capture. Restore only demo-owned
files/API/router hunks on rollback; preserve all databases and evidence.

The exact conventions and accounting equations in requirements.md are normative.
Show expiry and liquidation bounds separately. The kill latch commits before
flattening; a failed flatten is visibly pending and cannot re-enable entries.
The demo DB rejects original database aliases; API contracts forbid extra fields.
Research executes real deterministic fixed-rule sample/fold calculations with
explicit costs, without implying training or validated historic performance.

The existing npm E2E script gains the demo suite while retaining current suites;
no dependencies are added. The package-script scope conservatively invokes the
existing R3/GOVERNANCE/full-check policy. Daily loss, reserve-budget equality,
nonpositive-profit rejection, API-size and tablet gates follow requirements.md.
All demo text/SVG explicitly renders with pinned DejaVu Sans.

# Paper-trading integration and risk design

Planning revision 1 · 28 October 2026 · Audited application baseline `ff8027ab8a9a54e6eed2deaef895eab91151145f`. These are concrete engineering proposals and source findings, not a claim of implemented intelligence, profitable models, licensed data rights or human approval. Application source, strategies, dependencies and financial history are unchanged by this package.

## Preserve the current engine until a versioned migration is reviewed

Existing startup, ₹5,00,000 initial funding, integer-paise arithmetic, command idempotency, kill exits and historical event chain must remain intact. Current rule is five-bar synthetic momentum every six advances, with long-only buys, 8% stop/12% target, fee ₹20 per fill, ask+₹0.05/bid−₹0.05 execution and a 65-unit fixture lot. These are fixture assumptions, not validated market costs or exchange contract sizes. New analytical records initially run in **shadow mode** without sending commands, so their causal correctness can be tested separately from economic changes.

## DATA-01 contracts and DATA-02 causal windows

Use half-open one-minute buckets `[open, close)` with a separate known/available timestamp. Aggregate only exact contiguous source bars that share instrument/session/data version and are all closed and received by `as_of`. Anchor 5/30-minute windows to session open; the first eligible 30-minute close is 09:45 IST in the fixture. With data ending 09:44 or a missing minute, return INSUFFICIENT_DATA. Sum true interval volume only when the provider defines it as incremental; do not sum cumulative counters. Never create OHLC history from isolated spot marks and imply it is actual traded high/low/volume.

## Proposed risk profile v2 — not applied by this design

The master's 0.5%/1% targets must be represented as versioned session policy. Proposed trade-risk basis: conservative liquidatable equity before the new order, excluding unfilled targets/unrealized favorable assumptions. Proposed daily-loss basis: equity captured at that session's beginning, retained across restart; cash deposits/new sessions cannot silently reset an existing account's loss history. Maximum planned trade loss includes entry/exit fees, conservative slippage and stop distance; actual gap loss can exceed it. Do not describe planned risk as guaranteed maximum loss for a stop order.

Use basis points with integer rounding: `trade_budget = max(0, equity_paise * 50 // 10000)` and `daily_budget = max(0, session_start_equity_paise * 100 // 10000)`. At initial capital this is ₹2,500 and ₹5,000. Freeze effective policy/version at new-session creation; preserve old sessions and old event semantics. Clarify this proposed definition against any final user risk decision; no global reinterpretation of past limits.

`per_lot_risk = quantity_per_lot*(entry_paise−stop_paise+extra_adverse_slippage_paise)+round_trip_fees_paise`; allow zero lots when one lot exceeds budget. Use the actual fee model where per-order fees do not scale linearly per lot; evaluate each proposed integer size rather than blindly divide an aggregate. Retain cash, duplicate-instrument, maximum-position and exposure limits as independent constraints. Exits and the kill switch must remain available when entries are denied.

## Transaction and concurrency boundary

Inside BEGIN IMMEDIATE: identify the account scope, look up the idempotency key and compare the stored request first. An identical already-committed command returns its recorded result without a new economic effect, even if TTL/kill/risk state has since changed; a changed payload under the same key rejects. Only for a new intent, read current account/policy/kill/health, verify source TTL and candidate identity, recompute eligible lots/equity/exposure, then execute the fill; persist cash/fees/position/risk/decision event; return committed response. A previous accepted risk report cannot be replayed as permission against a changed account. Startup schema setup must finish separately before beginning one explicit transaction for initial account, active pointer and FUNDING event. If initialization fails, restart must see either no account funding effect or exactly one complete funding history; never partially committed funding. Fault injection between any economic write and event write rolls back all effects.

No margin shortfall may be “solved” by AI. Defined-risk selling needs a separately specified multi-leg portfolio max-loss/reservation model, partial-fill/leg-risk policy, costs, expiry settlement and emergency coordinated exits. Until then, sell strategies may be shown only as labeled research hypotheses and must not enter paper execution.

## Integration phases and tests

1. SAFE-01 and SAFE-02: repair destructive research migration on temporary legacy fixtures with zero row loss and unsupported-layout refusal; separately ensure schema setup cannot implicitly commit partial initial account/FUNDING effects. Verify failure/restart recovery for both.
2. DATA-01 contracts followed by DATA-02 aggregation: typed validated causal bars and completed windows, no engine strategy change. Test contiguity, completion, session/holiday boundary, duplicate/future/nonfinite inputs and prefix invariance.
3. OBS-01: versioned observations/decision envelope and read-only shadow evaluation. Test state/uncertainty/source/policy lineage; engine economic output must match baseline for unchanged commands.
4. RISK-01: implement reviewed v2 profile for new sessions only, with backward compatibility. Test fee/risk/cash equality boundaries, negative/zero equity, gaps, concurrent orders, restart/daily lock and one-lot-too-large rejection.
5. PAPER-01: explicitly switch eligible new-session autonomous behavior to completed 5/30-minute rule version, record every abstention/denial and retain stop/target/session-close invariants. Full E2E from data→decision→risk→fill→portfolio→audit.

## Recovery and rollback

Take supported SQLite backups with the server stopped or backup API; verify restore on a temporary path. Any migration failure leaves original user data usable and produces an actionable error. Back out incompatible code only after verifying it can read the active schema; otherwise restore the verified maintenance-window backup, preserving newly produced evidence for reconciliation. Never delete events or synthesize historical fills to make totals match. Live connectivity/deployment are not part of any phase above.

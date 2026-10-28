# Test-case matrix and harness integration

Planning revision 1 · 28 October 2026 · Audited application baseline `ff8027ab8a9a54e6eed2deaef895eab91151145f`. These are concrete engineering proposals and source findings, not a claim of implemented intelligence, profitable models, licensed data rights or human approval. Application source, strategies, dependencies and financial history are unchanged by this package.

## Existing executable baseline versus proposed coverage

The existing `tests/{architecture,paper,research,control_plane}` suites are real; existing browser tests are `apps/web/tests/{workspace,theme,visual}.spec.ts`. A fresh baseline Python run completed with **336 passed, one documented prediction-fixture skip**, not a claimed percentage of coverage. New IDs below are acceptance requirements for future code. They have not been implemented or executed merely by appearing in this matrix.

Each of the 39 skills has mandatory validation categories: **U** unit, **B** boundary, **P** property/metamorphic, **F** deterministic fixtures, **I** integration, **H** licensed historical validation, **W** chronological walk-forward, **L** look-ahead/prefix invariance, **R** risk-bypass/authority and **X** failure/recovery. U/B/P/F/I/L/R/X must be applicable explicitly rather than skipped silently; if a pure estimator cannot place orders, its R check proves it has no order/DB authority and the integration risk veto remains effective. H/W are BLOCKED until suitable licensed point-in-time data and evaluation definitions exist. A statistical pattern hypothesis needs H/W evidence before predictive claims, even if its morphology passes U tests.

| Skill | Additional discriminating case | Required categories | Current new-test status |
|---|---|---|---|
| F01 · Candlestick anatomy | PAT-01 malformed/zero-range | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| F02 · Market structure | TIME-03 future-neighbor perturbation | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| F03 · Trend identification | OBS-F03 flat/trend and warmup | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| F04 · Support and resistance | OBS-F04 merge/invalidated-zone cases | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| F05 · Chart patterns | OBS-F05 mirror/incomplete forms | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| F06 · Gap analysis | OBS-F06 session boundary/early open | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| A01 · Breakout and retest | OBS-A01 break-only versus retest | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| A02 · Failed breakout | OBS-A02 failure/continuation | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| A03 · Liquidity sweep hypothesis | OBS-A03 excursion without rejection | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| A04 · Opening range | OBS-A04 pre/post window completion | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| A05 · VWAP | OBS-A05 reset/zero-volume | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| A06 · Momentum and exhaustion | OBS-A06 constant/alternating runs | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| A07 · Reversal and continuation | OBS-A07 contradictory evidence | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| O01 · Intrinsic/extrinsic value | OBS-O01 call-put mirror/bounds | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| O02 · Greeks | OBS-O02 finite-difference/bounds | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| O03 · Volatility | OBS-O03 zero-variance/expiry limits | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| O04 · OI changes | OBS-O04 missing prior/corrections | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| O05 · Option-chain analysis | OBS-O05 crossed/duplicate expiry | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| O06 · Put-call ratio | OBS-O06 zero/missing OI | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| O07 · Strike selection | OBS-O07 illiquid/expired strikes | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| O08 · Expiry behavior | OBS-O08 holiday/expiry boundary | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| O09 · Buyer/seller perspectives | OBS-O09 gap/tail scenarios | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| O10 · Hedging hypotheses | OBS-O10 sign-reversal sensitivity | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| M01 · Regime classification | OBS-M01 thin history/conflicts | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| M02 · Volatility clustering | OBS-M02 shuffled versus clustered returns | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| M03 · Probabilistic direction | OBS-M03 leakage/calibration/abstention | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| M04 · Multi-timeframe confirmation | TIME-01/02/04 prefix invariance | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| M05 · Behavioral hypotheses | OBS-M05 alternative explanations | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| M06 · Microstructure | OBS-M06 crossed/stale/sequence cases | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| M07 · Liquidity and costs | OBS-M07 wide spread/adverse fill | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| M08 · Institutional positioning research | OBS-M08 unidentifiable/contradictory inputs | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| R01 · Strategy selection | OBS-R01 all-ineligible/conflicting choices | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| R02 · Entry and exit evaluation | OBS-R02 early/missing/expired confirmation | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| R03 · Stops and position sizing | RISK-01/02 cost/budget boundary | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| R04 · Portfolio exposure | RISK-03 concurrent reservation | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| R05 · Maximum drawdown | RISK-04 peak/reset/gap cases | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| R06 · Capital preservation | RISK-05 kill/restart and failure rollback | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| R07 · No-trade decisions | DEC-01 five-state contract | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |
| R08 · Performance evaluation | EVAL-01 costs/overlap/tails | U/B/P/F/I/H/W/L/R/X | PLANNED; H/W externally blocked |

## Cross-domain safety acceptance

| ID | Positive and negative predicates | Expected evidence |
|---|---|---|
| SAFE-01 | Upgrade supported legacy journal layouts with exactly preserved rows/identities; unknown layout refuses without changes; interrupted migration recoverable | Temporary DB fixtures before/after counts and canonical row hashes, actual migration JUnit, backup/restore log |
| SAFE-02 | First bootstrap account/active/FUNDING either commits entirely or has no funding effect; injected event failure then restart cannot orphan funding or duplicate it | Temporary DB snapshots, fault/restart JUnit and event-chain reconciliation |
| TIME-01 | At 09:44:59 no first 30-minute confirmation; at 09:45 with all availability receipts, first 09:15–09:45 window eligible | Parameterized timing fixtures and explicit expected completed windows |
| TIME-02 | Missing/duplicate/future/late/cross-session child bars cannot produce a valid complete aggregate | Rejection reason identities and exact as-of history |
| TIME-03 | Right-side confirmed pivot unavailable before confirmation close/receipt despite earlier pivot event timestamp | Perturbed future observations; old decisions unchanged |
| TIME-04 | Appending or modifying future bars cannot affect any earlier observation/decision/fill | Hypothesis/prefix invariance and source hash comparison |
| PAT-01 | Body-contained engulfing detected; wick-only overlap rejected; hammer with invalid OHLC rejected | Each draft pattern's positive/inverse/tolerance/malformed fixtures after source verification |
| DEC-01/02/03 | All five states, strict schema fields/units/uncertainty, conflicting evidence abstains, unapproved model probability cannot masquerade as rule confidence | Contract tests with explicit invalid payloads and no order side effects |
| RISK-01/02 | Fees/slippage included in budget; exact equality accepted only if other constraints pass; one paise/one lot beyond rejected; bool/negative size invalid | Integer-paise boundary tests; exact denial reason and unchanged account on failure |
| RISK-03 | Concurrent entries/reservations cannot exceed cash/exposure/maximum positions, including duplicates | Contended transaction tests and conserved account state |
| RISK-04/05 | Drawdown/daily loss/kill state survive restart; entries blocked while exits/kill still work; gap risk disclosed | Fault/restart and adversarial bypass fixtures |
| MONEY-01 | Cash + inventory basis = starting funding + realized P&L after costs; liquidation marks and unrealized totals reconcile | Property sequences and full audit-event replay without duplicate economic effects |
| LINEAGE-01 | Exact dataset/strategy/policy/account bindings persist through rejection/abstention/fill; stale IDs cannot execute | Hashed records plus transaction failure injection |
| EVAL-01 | Costs, horizon, pending labels, overlapping trades and sample uncertainty visible; holdout unused for tuning | Dataset/split manifests and reproducible evaluation report, not synthetic profit claims |
| UI-01 | All states keyboard readable; conflict/missing data can't appear as neutral success; order/kill controls remain accessible | Functional Playwright and accessibility audit; candidate screenshots retained separately |
| GOV-01 | Changed source/report/task/model invalidates prior evidence; implementer cannot claim independent or human approval | Existing harness tamper tests plus proposed model-promotion negative cases |

## Running and retaining evidence

Use `algooptionx-harness test-changes --base <actual-base>` for normal iterative selection. New unmapped `src/algooptionx/intelligence/` or `tests/intelligence/` automatically triggers full functional discovery until an explicit conservative mapping is reviewed. A reviewed task's own required checks are never removed by selection. Use full Python discovery and functional browser tests for broad changes; visual comparisons use a separately reviewed renderer/profile and never auto-update candidates.

Capture a new task baseline after protected specs change. Actual subprocess exit codes, JUnit/browser outcomes, skip reasons, timeout/cancellation, source before/after hashes and independent handoff are required. Zero tests, source mutation, missing reports, unexpected skips or forged claims fail. Existing prediction skip remains listed; do not loosen assertions or silently add new allowed skips.

Security coverage must also test prompt/document injection, stale/forged evidence, hostile tool arguments, secrets in output, unauthorized read/write effects and model output that requests a risk bypass. Later SaaS/adapters need separate auth/tenant/entitlement/payment contract and adversarial tests before activation. No existing origin check is counted as an authentication test.

# Independently verifiable implementation tasks

Planning revision 1 · 28 October 2026 · Audited application baseline `ff8027ab8a9a54e6eed2deaef895eab91151145f`. These are concrete engineering proposals and source findings, not a claim of implemented intelligence, profitable models, licensed data rights or human approval. Application source, strategies, dependencies and financial history are unchanged by this package.

## Scope and authority

These are reviewable tasks, **not work already executed and not human-approved task receipts**. Each row has prerequisites, expected files, acceptance, tests, evidence and rollback; owners are responsibilities rather than invented named humans. Implementation should capture a fresh strict harness manifest/baseline after its protected specifications are reviewed. Do not mutate an old captured task to expand scope.

The supplied enhancement requires a read-only first phase, presentation of these artifacts and explicit approval before implementation. Recommended first concrete batch: SAFE-01/SAFE-02 then DATA-01/DATA-02, preserving active paper behavior. Pattern implementation also requires independent source/definition verification; ebook-specific work remains blocked. New financial, hosted and live work retains separate design/activation gates.

## SAFE-01 — Preserve legacy journal history

- **Phase/owner:** Phase 1; backend + QA.
- **Prerequisites:** Actual review of assessment and this batch; temporary legacy fixtures.
- **Expected files:** `src/algooptionx/research/storage/db.py; tests/research/test_repository.py or migration-specific tests` (scoped list refined in the captured task).
- **Acceptance:** Remove destructive automatic DROP behavior through a versioned compatible migration or fail-closed unsupported-layout path; all legacy rows/IDs and unknown columns preserved in source/backup; never infer unknown trade_date.
- **Tests:** Known old/new schemas, nonnullable leg fields, unknown schema, interrupted upgrade, row-count/hash and restore tests.
- **Evidence:** Before/after schema/row hashes and actual JUnit; independent review.
- **Rollback:** Preserve original database/backup and schema journal; restore only under verified maintenance procedure.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## SAFE-02 — Make first account funding atomic across startup failures

- **Phase/owner:** Phase1; backend + risk + QA.
- **Prerequisites:** Review AUD-08 and the pure initialization-recovery design; use temporary databases only for test fixtures.
- **Expected files:** `src/algooptionx/paper/engine.py`; `tests/paper/test_engine.py` or dedicated bootstrap recovery tests.
- **Acceptance:** Schema setup cannot implicitly commit a transaction containing partial economic effects. Create account, active pointer and FUNDING event in one explicit transaction after schema setup. Failed first funding leaves no partial account/pointer/event; restart produces exactly one complete initial funding chain. Existing funded accounts and history survive unchanged.
- **Tests:** Inject failure before/after each bootstrap economic/event write; check sqlite_master/schema versus account/effect invariants; restart each failed fixture; verify exactly one funding event and initial cash. Retain existing entry/exit/idempotency/concurrency/property/API tests.
- **Evidence:** Actual temporary-DB before/after snapshots, JUnit fault/restart identities, event-chain/cash reconciliation and current source-bound independent review.
- **Rollback:** Preserve all existing data and evidence; use a compatible prior code or verified backup. Never manufacture a missing historical funding event without a separately reviewed reconciliation procedure.
- **Current status:** PLANNED; the audit reproducer demonstrates an open baseline defect, not a fix.

## DATA-01 — Define and validate causal OHLCV contracts

- **Phase/owner:** Phase 1; backend + quant.
- **Prerequisites:** Approved pure-data design; no broker connection needed.
- **Expected files:** `src/algooptionx/market/contracts.py; tests/market/test_contracts.py` (scoped list refined in the captured task).
- **Acceptance:** Explicit units/source/session/open/close/available/as_of; invalid/nonfinite/duplicate/mixed-instrument inputs rejected; source metadata frozen.
- **Tests:** TIME-02/04; malformed OHLCV, bool/numeric types, temporal consistency, property fixtures.
- **Evidence:** Current source-bound JUnit and fixture hashes.
- **Rollback:** Remove unused additive domain code if unintegrated; no account/database changes.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## DATA-02 — Aggregate completed 5/30-minute windows

- **Phase/owner:** Phase 1; backend + quant.
- **Prerequisites:** DATA-01; pinned fixture session calendar.
- **Expected files:** `src/algooptionx/market/aggregation.py; tests/market/test_aggregation.py` (scoped list refined in the captured task).
- **Acceptance:** Exact contiguous child intervals, session anchoring and closed/available gate; first30-minute close09:45 fixture; no partial bucket presented as complete.
- **Tests:** TIME-01/02/04; timezone/session/missing-child/late-arrival and prefix-invariance properties.
- **Evidence:** Aggregate expected fixtures, test IDs and source/report hashes.
- **Rollback:** Rollback pure module/adapter; retain fixture history.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## GOV-01 — Evaluate OpenSpec and specialized development contracts

- **Phase/owner:** Phase 1; architect + security + QA.
- **Prerequisites:** Current native role/schema inventory and approved governance scope.
- **Expected files:** `ADR/spec adapter design; scoped .agents/skills and role JSON only after review` (scoped list refined in the captured task).
- **Acceptance:** One authoritative requirement/task mapping; explicit options/data/leakage/framework skill I/O/tools/failure/evidence; no new signer or deployment authority.
- **Tests:** Config/schema and round-trip traceability/negative capability tests.
- **Evidence:** ADR, actual config checks, independent handoff.
- **Rollback:** Keep native specs and prior role contracts; no dependency install unless separately authorized.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## OBS-01 — Introduce versioned observation/decision envelope

- **Phase/owner:** Phase 2; backend + quant.
- **Prerequisites:** DATA-02 and reviewed decision schema.
- **Expected files:** `src/algooptionx/intelligence/contracts.py; decision.py; tests/intelligence/test_contracts.py` (scoped list refined in the captured task).
- **Acceptance:** Five states, units/evidence/availability/uncertainty/invalidation; rule probabilities null; candidate cannot execute by itself.
- **Tests:** DEC-01/02/03 and LINEAGE-01; extra keys, stale source, missing/contradictory inputs.
- **Evidence:** Contract report and comparison showing old API unchanged.
- **Rollback:** Keep old workspace response/route; additive new contract behind inactive adapter.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## OBS-02 — Shadow reuse of existing structure/regime/chain analytics

- **Phase/owner:** Phase 2; quant + backend.
- **Prerequisites:** OBS-01; availability adapter semantics reviewed.
- **Expected files:** `Pure observation adapters; tests/intelligence/test_observations.py` (scoped list refined in the captured task).
- **Acceptance:** Research multi-timeframe reuse explicitly respects confirmation lag; no broker/runtime/harness dependency in offline core; no change to active paper commands.
- **Tests:** TIME-03/04, empty/conflicting data, existing research regressions and architecture boundaries.
- **Evidence:** Old/new observation fixtures, absence of economic effects.
- **Rollback:** Disable shadow adapter; preserve research outputs and account events.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## PAT-01 — Verify and implement first morphology subset

- **Phase/owner:** Phase 2; options/quant + QA.
- **Prerequisites:** Book/source review where applicable; independent definitions; DATA-02/OBS-01.
- **Expected files:** `src/algooptionx/intelligence/patterns.py; tests/intelligence/test_patterns.py` (scoped list refined in the captured task).
- **Acceptance:** Start with body engulfing and pin-bar contextual naming; exact versioned rules and12-field source record; observations only.
- **Tests:** PAT-01 + U/B/P/F/I/L/R/X; invalid OHLC, context inverse, wick-only negative, no future bars.
- **Evidence:** Definition/source citations, actual tests, planned historical evaluation clearly distinguished.
- **Rollback:** Disable new morphology observations; no strategy removal or automatic activation.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## INTEL-01 — Complete remaining knowledge observations

- **Phase/owner:** Phase 2; quant/options + QA.
- **Prerequisites:** OBS-02/PAT-01 and each of39 catalog dependencies.
- **Expected files:** `Incremental intelligence modules/fixtures; specific paths scoped per subtask` (scoped list refined in the captured task).
- **Acceptance:** One small task per skill or tightly coupled group; resolve observation conflicts; no one giant39-skill code dump.
- **Tests:** Each catalog case and all applicable10-category requirements; historical gates remain explicit.
- **Evidence:** Per-skill coverage/evaluation ledger and independent findings.
- **Rollback:** Remove/disable only added inactive observation; preserve prior contracts/results.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## RISK-01 — Version reviewed 0.5%/1% paper policy

- **Phase/owner:** Phase 3; risk + backend + QA.
- **Prerequisites:** Explicit policy basis/new-session migration review; DATA-02/OBS-01.
- **Expected files:** `src/algooptionx/paper policy/migrations; tests/paper` (scoped list refined in the captured task).
- **Acceptance:** 50bps planned trade budget/100bps daily basis as actually approved, integer arithmetic/costs and persistent session lock; old sessions retain old semantics.
- **Tests:** RISK-01 through05, concurrency, fees, one-paise equality, restart/kill and rollback properties.
- **Evidence:** Policy/session migration report and source-bound critical tests.
- **Rollback:** Disable v2 for new sessions, preserve prior policy/event versions and validated DB backup.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## PAPER-01 — Integrate completed-timeframe decisions with buying only

- **Phase/owner:** Phase 3; backend + risk + E2E.
- **Prerequisites:** OBS-02, selected verified intelligence, RISK-01; compatibility design.
- **Expected files:** `Engine/API observation integration; tests/paper; apps/web API adapter if needed` (scoped list refined in the captured task).
- **Acceptance:** Mandatory completed5/30 confirmation; every abstention/rejection/fill has lineage; same transactional risk gate; no naked sell.
- **Tests:** Full data→proposal→risk→fill→account→audit journey; MONEY/LINEAGE/TIME/RISK and functional E2E.
- **Evidence:** Commands/outcomes/reconciliation with current source/test/browser reports.
- **Rollback:** Revert new-session strategy flag/version; retain old positions/stops/history and all events.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## DESIGN-01 — Create and review enterprise image/state references

- **Phase/owner:** Phase 0/3; UX + frontend + validator.
- **Prerequisites:** UI state inventory; current data contracts; original image rights.
- **Expected files:** `Original design image candidates, token/component/state specs and manifest` (scoped list refined in the captured task).
- **Acceptance:** All12 modules and actual subpages/tabs/dialogs/tables/charts/errors across3 widths/2 themes; actual user design review, no fake approval.
- **Tests:** Keyboard/state design review, contrast analysis and planned functional/visual mappings.
- **Evidence:** Candidate hashes/profile and real user decision; missing images stay pending.
- **Rollback:** Preserve previous candidates; no source/UI replacement until reviewed.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## UI-01 — Implement reviewed intelligence UI incrementally

- **Phase/owner:** Phase 3; frontend + E2E.
- **Prerequisites:** DESIGN-01 reviewed subset; PAPER/OBS contracts.
- **Expected files:** `Existing app/shared/workspace files and apps/web/tests scoped per screen` (scoped list refined in the captured task).
- **Acceptance:** Readable source/uncertainty/available_at, all five states, charts with text alternatives, accessible responsive theme behavior.
- **Tests:** Functional E2E, lint/build, keyboard/screen-reader/contrast checks and reviewed-profile visual comparisons.
- **Evidence:** Actual reports/traces/images; no auto-update baselines.
- **Rollback:** Feature flag/new route rollback with old routes/data/history retained.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## SPREAD-01 — Design and validate defined-risk selling

- **Phase/owner:** Phase 3 extension; options + risk + QA.
- **Prerequisites:** Separate explicit spread/margin design approval; PAPER-01.
- **Expected files:** `New max-loss/reservation/payoff/leg-lifecycle domain and tests scoped after design` (scoped list refined in the captured task).
- **Acceptance:** Known bounded payoff, collateral reservation, fill/leg risk, fees/expiry/settlement/cancel/kill behavior; no unhedged selling.
- **Tests:** Payoff/property, max-loss/gap, partial-leg, concurrent reservation and accounting tests.
- **Evidence:** Reviewed design and fixture/backtest evidence.
- **Rollback:** Keep selling disabled; reconcile and close controlled test positions before rollback.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## EVAL-01 — Version licensed historical datasets and evaluation

- **Phase/owner:** Phase 4; quant + data + QA.
- **Prerequisites:** Provider rights and actual options history including bid/ask/expiry/lot/calendar.
- **Expected files:** `Dataset manifest and evaluation pipeline/tests scoped in research` (scoped list refined in the captured task).
- **Acceptance:** Point-in-time available contracts, costs, gaps/corrections/label availability; immutable raw/source hashes.
- **Tests:** H/W/L + cost sensitivity, overlap/purge/embargo, label cutoff and holdout contamination tests.
- **Evidence:** Licensing record, reproducible split manifests/report and independent review.
- **Rollback:** Retain raw manifests/prior study; invalidate derived artifacts rather than overwrite them.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## MODEL-01 — Train approved offline challengers

- **Phase/owner:** Phase 4; ML + quant.
- **Prerequisites:** EVAL-01 and approved experiment/compute budget.
- **Expected files:** `Feature/model/evaluation manifests; registry adapter only if justified` (scoped list refined in the captured task).
- **Acceptance:** Training-only fitted transformations; baselines/calibration/uncertainty/drift; no active pointer writes.
- **Tests:** Leakage, calibration, reproducibility, corrupted artifact, absent model and resource-budget tests.
- **Evidence:** Pinned datasets/source/artifact hashes, metrics/CIs and evaluation constraints.
- **Rollback:** Retain prior artifacts; no current active model is replaced.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## MODEL-02 — Promotion, paper shadow observation and rollback

- **Phase/owner:** Phase 4; release + risk + user.
- **Prerequisites:** MODEL-01, current independent evidence and actual human decision.
- **Expected files:** `Protected promotion integration and rollback/runbooks scoped separately` (scoped list refined in the captured task).
- **Acceptance:** Versioned active pointer, criteria/approver/evidence, prior artifact restore and risk independence;90-day horizon not auto-pass.
- **Tests:** Tampered/stale approval, failed metrics, unavailable model, interrupted promotion, rollback/determinism.
- **Evidence:** Real decision and trusted deployment-control observation where applicable.
- **Rollback:** Restore verified previous artifact/config; preserve all experiment and trading events.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## DEMAND-01 — Validate customer demand and pricing

- **Phase/owner:** Before substantial Phase 5 cost; product + user.
- **Prerequisites:** Usable prototype, consent and approved interview/pilot plan.
- **Expected files:** `docs/product/customer-research and cost/pricing experiment records` (scoped list refined in the captured task).
- **Acceptance:** 20–30 real prospect interviews and opt-in usage/purchase experiment; retention/support/paid conversion evidence; no fake users/results.
- **Tests:** Predeclared observation window/decision thresholds; check consent, cohort/sample and cost arithmetic.
- **Evidence:** Actual anonymized research and paid-conversion evidence stored with appropriate privacy.
- **Rollback:** Stop experiment/expense, retain lawful audit/consent records; do not fabricate demand.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## LEGAL-01 — Review data, advice/algo, privacy and payment obligations

- **Phase/owner:** Before commercial/live activation; qualified reviewers + user.
- **Prerequisites:** Actual product/provider/jurisdiction/service scope.
- **Expected files:** `Dated compliance/licensing/retention/incident requirements and decisions` (scoped list refined in the captured task).
- **Acceptance:** Current SEBI/exchange/broker permissions, redistribution/advice applicability, Indian privacy/payment/tax/cyber requirements reviewed.
- **Tests:** Control/permission checklist and expert findings; legal correctness not inferred from unit tests.
- **Evidence:** Actual provider agreements and qualified review, not model-generated clearance.
- **Rollback:** Keep restricted capabilities disabled; stop unauthorized use and follow documented retention obligations.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## FEED-01 — Integrate licensed read-only market data

- **Phase/owner:** Phase 5; backend + data + security.
- **Prerequisites:** LEGAL-01 and actual licensed provider access.
- **Expected files:** `Provider adapter/auth integration/contracts and data-quality tests` (scoped list refined in the captured task).
- **Acceptance:** Entitlement/effective metadata, reconnection/correction/rate-limit/staleness; no broker order methods in data interface.
- **Tests:** Recorded/synthetic adapter contracts first, authorized licensed staging checks separately.
- **Evidence:** Provider rights/metadata, scoped secure credentials, actual integration outcome.
- **Rollback:** Disable feed and fall back only to clearly labeled allowed fixtures; preserve provider batches.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## SAAS-01 — Design and implement hosted identity/tenant isolation

- **Phase/owner:** Phase 5; security + backend + ops.
- **Prerequisites:** DEMAND-01,LEGAL-01 and separately reviewed hosting scope.
- **Expected files:** `Auth/authorization/tenant storage/secure-config modules and threat model` (scoped list refined in the captured task).
- **Acceptance:** Server-owned tenant identity, least privilege, secret rotation, cross-tenant isolation and auditable access.
- **Tests:** Auth/tenant/IDOR/injection/session/secret/adversarial and restore tests.
- **Evidence:** Actual staging evidence and user approval before hosted exposure.
- **Rollback:** Keep local mode, disable hosted ingress, restore verified tenant-safe backup within approved procedure.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## OPS-01 — Storage/worker/observability and recovery operations

- **Phase/owner:** Phase 5 as justified; architect + ops + security.
- **Prerequisites:** Measured SLO/capacity/RPO/RTO requirements and hosting approval.
- **Expected files:** `ADRs, database/queue/telemetry adapters, deployment and incident runbooks` (scoped list refined in the captured task).
- **Acceptance:** Choose Postgres/queue/Timescale only with evidence; durable job retries/cancel, alerts, backups/restore and no secret logs.
- **Tests:** Load/recovery/idempotency/restore/alert drill and rollout/rollback tests.
- **Evidence:** Actual environment measurements and authorized operator drill records.
- **Rollback:** Known-good deployment/config and verified backup; no destructive migration or silent history rewrite.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## BILLING-01 — Implement validated plans and secure entitlement

- **Phase/owner:** Phase 5; product + backend + security.
- **Prerequisites:** DEMAND-01,LEGAL-01,SAAS-01 and payment-provider setup.
- **Expected files:** `Billing/entitlement/webhook contracts, UI and tests scoped after design` (scoped list refined in the captured task).
- **Acceptance:** Free/Starter/Pro/Advanced/Enterprise hypotheses refined by costs/demand; signed/idempotent webhook, refunds/cancel/tax and server enforcement.
- **Tests:** Forged/replayed/out-of-order webhooks, downgrade/cancel, failed payment, tenant crossover and reconciliation.
- **Evidence:** Sandbox provider outcomes, cost/retention experiment and real commercial decision.
- **Rollback:** Disable new charging, preserve invoices/entitlements and follow provider refund/reconciliation policy.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.

## LIVE-01 — Separately authorize multi-broker live execution

- **Phase/owner:** Phase 6; broker/risk/security/ops/qualified reviewers + user.
- **Prerequisites:** Stable research/paper/evaluation evidence,FEED/LEGAL/OPS and explicit live authorization.
- **Expected files:** `Broker adapter/order-state/reconciliation/kill design and protected deployment tasks` (scoped list refined in the captured task).
- **Acceptance:** No auto-activation from paper profits; broker-specific order/fill/cancel/retry/partial-fill and independent maximum-risk controls.
- **Tests:** Sandbox fault/duplicate/partial-fill/disconnect/kill/reconciliation, then separately authorized controlled live checks.
- **Evidence:** Actual broker/regulatory permissions, external policy verification, real user activation decision and operational readiness.
- **Rollback:** Live remains disabled until gates met; approved cancel/flatten/reconcile plan and known-good recovery under human authority.
- **Current status:** PLANNED; external prerequisites, actual human decisions and execution results must be recorded separately.


## Completion discipline

One task is complete only when the scoped source, actual tests/reports, source binding, independent review and applicable real user decision are present. A drafted document, a role name, a passing unrelated test or an unapproved model score cannot close it. Keep H/W/licensing/business/legal/visual gaps visible. Removal of prior functionality needs documented justification and explicit approval; none is requested here.

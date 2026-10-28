# Controlled learning and model governance

Planning revision 1 · 28 October 2026 · Audited application baseline `ff8027ab8a9a54e6eed2deaef895eab91151145f`. These are concrete engineering proposals and source findings, not a claim of implemented intelligence, profitable models, licensed data rights or human approval. Application source, strategies, dependencies and financial history are unchanged by this package.

## Two independent improvement queues

The trading queue evaluates losing/winning/no-trade decisions, false signals, missed opportunities, regime weakness, calibration, data drift and execution assumptions. The software queue records errors, latency, accessibility, usability, test reliability, operational cost and consented user feedback. Neither queue authorizes arbitrary source edits or silent trading-rule promotion. Maintain observation→hypothesis→proposed experiment→review→evidence→decision history.

## Dataset and labeling contract

Each dataset manifest records supplier/usage rights, immutable raw hashes, instrument/expiry/lot/calendar versions, timestamp semantics, missing/corrected records, bid/ask/spread coverage and quality exclusions. Features use only information available at each decision, not merely bar-open timestamps. Labels have their own outcome availability time and distinguish pending, censored, stop, target, session-close and ambiguous same-bar paths. Exclude labels that mature beyond training cutoff; don't silently choose favorable intrabar order. Preserve every decision, including abstentions and rejected trades, to avoid filled-trade selection bias.

## Evaluation protocol

Before results, pin hypothesis, target/horizon, eligible instruments, strategy/cost/slippage/margin assumptions, train/development/validation/untouched holdout dates and regime definitions. Use purged chronological splits with embargo appropriate to overlapping labels. Fit imputation/scaling/feature selection only on training folds; tune on development data, not holdout. Compare unconditional, simple causal rule and context-only baselines before complex ML. Control multiple comparisons, disclose sample uncertainty and instability, and repeat under adverse costs and gap scenarios.

Report net expectancy, drawdown, tail losses, profit factor with undefined/no-loss cases honest, turnover, fees/slippage, exposure, regime/expiry/daypart performance, trade/decision counts, rejection/no-trade rates, calibration and confidence intervals. A 90-day observation period without enough independent trades/regime diversity is inconclusive. Neither synthetic profitability nor win rate alone establishes real-world edge or live readiness. Historical validation remains BLOCKED until suitable licensed datasets exist.

## Challenger and registry lifecycle

DRAFT→DATA_VALIDATED→TRAINED→EVALUATED→INDEPENDENT_REVIEW→HUMAN_REVIEW→APPROVED_FOR_SHADOW→APPROVED_FOR_PAPER→RETIRED/ROLLED_BACK. All transition events record actual actor, source/dataset/model/config hashes, tests and rationale. A status label created in candidate code does not prove human authority. No model currently reaches trained/evaluated/approved statuses in this project.

Scheduled jobs may prepare a challenger/retraining proposal and bounded offline experiments only within authorized data/compute scope; they never change the active rule/model pointer automatically. Registry technology (MLflow or equivalent) is undecided until requirements justify it; a manifest+hash design can be evaluated first without installing dependencies now. Model artifact deserialization must treat candidate formats as untrusted code unless safely constrained/isolated.

## Promotion and rollback gates

Predeclare acceptable data completeness, calibration, stability, drawdown/tail exposure and sample thresholds for the specific study. Require passing current tests, no leakage findings, independent review and an actual human decision bound to dataset/model/source/evidence. A later profitable chart does not cure failed safety tests. Promotion must not alter risk limits or broker permissions. Store prior active artifact/config and prove deterministic rollback on a temporary environment before activation. A rejected/unavailable candidate remains inactive.

## Drift and recovery

Monitor missing/out-of-range inputs, feature distribution shifts, prediction/calibration changes, outcome degradation, turnover/cost mismatch and data freshness. Distinguish data-provider outage from statistical drift; no arbitrary automatic retraining on corrupted observations. Fail to abstention/shadow/manual research when required inputs are unreliable. Preserve decisions and model versions through restart; a failed job cannot publish a partial artifact or overwrite evidence. Alert routing must be configured by an authorized operator rather than inventing recipients.

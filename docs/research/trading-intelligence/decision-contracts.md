# AI decision and evidence contracts

Planning revision 1 · 28 October 2026 · Audited application baseline `ff8027ab8a9a54e6eed2deaef895eab91151145f`. These are concrete engineering proposals and source findings, not a claim of implemented intelligence, profitable models, licensed data rights or human approval. Application source, strategies, dependencies and financial history are unchanged by this package.

## Proposed envelope and separation

The [machine-readable draft schema](decision-envelope.schema.json) is a **planning artifact**, not a deployed API or an implemented validator. Its format is JSON Schema 2020-12; a runtime validator must enable date-time format checks and the cross-field invariants below. The present `/api/workspace` fixture fields remain unchanged. An adapter/versioned new endpoint is required to avoid breaking the existing React client.

A decision has a source/data/calendar/instrument version, strategy/rule/model version, as-of/availability/expiry times, all contributing observations, explicit uncertainty and invalidation. It proposes rather than executes. A fill can occur only after a fresh transactional risk decision with a matching decision/source/account/policy identity. The record never includes model provider secrets, broker tokens or user authentication assertions.

| State | Meaning | Execution consequence |
|---|---|---|
| BULLISH | Adequate evidence favors rising underlying under a pinned rule/model | At most a paper-buy candidate; independent risk still may reject |
| BEARISH | Adequate evidence favors falling underlying | At most a PE paper-buy candidate; not naked short permission |
| SIDEWAYS | Adequate evidence supports a range hypothesis | Initially no candidate; defined-risk selling remains a separate design |
| NO_TRADE | Adequate observations but conflicts, cost, expiry or policy prevent a setup | Candidate null; preserve reason codes |
| INSUFFICIENT_DATA | Missing, stale, incomplete, unavailable or malformed required inputs | Candidate null; state required missing inputs; no neutral substitute |

## Temporal invariants not expressible by scalar JSON fields alone

- Source bar `open_at < close_at ≤ available_at ≤ decision.as_of`; decision.available_at is the maximum required observation availability and must be ≤ as_of. Transport delay must not be negative. valid_until must be strictly greater than as_of and bounded by the strategy TTL.
- Five-minute and 30-minute buckets anchor to the versioned **09:15 IST fixture session**, not clock-hour bins. At 09:45:02, the completed confirmation can be 09:15–09:45, not an unfinished 09:30–10:00 bucket. A missing constituent minute or a future receipt means no completed confirmation.
- Confirmed pivot `event_at` can precede its `available_at` by its right-hand lookback. Evaluation and UI must not move the actionable timestamp back to the pivot.
- Source hash, symbol/right/expiry/lot/calendar versions must match the frozen quote set. A stale candidate is not reused after correction, kill/reset or policy change.
- All required evidence is present, with comparable units and finite values. Probability is null for an unvalidated rule. CALIBRATED_MODEL requires a non-null bounded probability and an approved, matching calibration/model ID; schema conformance alone is not promotion approval.
- BULLISH/BEARISH candidates require positive integer lots/paise, compatible right, entry>stop for long-only buying, and a deterministic budget check. Proposed target reward does not grant risk acceptance.

## Illustrative decision (not an actual model prediction)

```json
{
  "schema_version": 1,
  "decision_id": "EXAMPLE-NO-TRADE-001",
  "state": "NO_TRADE",
  "instrument_id": "SIM-NIFTY-EXAMPLE",
  "as_of": "2026-11-02T09:45:02+05:30",
  "available_at": "2026-11-02T09:45:01+05:30",
  "valid_until": "2026-11-02T09:50:00+05:30",
  "source": {
    "kind": "SYNTHETIC", "dataset_id": "EXAMPLE-ONLY",
    "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
    "calendar_version": "sim-session-v1", "instrument_version": "sim-contracts-v1"
  },
  "strategy": {"id": "context-composer", "version": "draft-1", "model_version": null},
  "evidence": [{
    "skill_id": "M04", "version": "draft-1", "status": "CONFLICT",
    "event_at": "2026-11-02T09:45:00+05:30",
    "available_at": "2026-11-02T09:45:01+05:30",
    "value": "5-minute and 30-minute context disagree", "unit": null,
    "source_hash": "0000000000000000000000000000000000000000000000000000000000000000"
  }],
  "uncertainty": {"kind": "UNVALIDATED_RULE", "probability": null, "calibration_id": null, "reason_codes": ["CONFLICTING_TIMEFRAMES"]},
  "invalidation": ["New completed 5-minute bar or changed source/policy"],
  "candidate": null,
  "execution_mode": "PAPER"
}
```

## Execution/event evidence

Decision lineage: decision_id → risk_decision_id → command_id → fill/event IDs. Risk evidence records policy version, account snapshot/equity basis, limits, actual calculations, accepted/rejected status and reasons, without signed-human-approval claims. Fill evidence includes source executable quote/time, cost/slippage version, integer quantity/prices/fees and account reconciliation. Decisions that abstain/reject must also be journaled; do not report only winners or fills.

Development evidence remains the existing strict harness Evidence/Result/Artifact contracts: actual commands, exit status/timeouts, test identities/skips, hashes, source commit and final source digest. Do not invent a second `passed:true` JSON authority. Store test/model/market evidence with different schemas/IDs so a synthetic experiment cannot masquerade as human release approval. An independent review binds the actual source and artifacts and reports unresolved findings honestly.

## Validation matrix

DEC-01 checks all five states and candidate restrictions; DEC-02 checks unknown keys/units/nonfinite values; DEC-03 checks probability-kind/model/calibration consistency; TIME-01/02 enforce only completed contiguous windows; TIME-03 preserves pivot availability; TIME-04 future perturbation leaves prior results unchanged; LINEAGE-01 links the exact source/policy/account through atomic economic events. These new runtime-contract tests are planned, not run against an implementation that does not yet exist.

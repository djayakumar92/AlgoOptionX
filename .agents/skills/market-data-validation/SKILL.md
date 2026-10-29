---
name: market-data-validation
description: Validate source quality, time availability and metadata identity.
---

# Validate source quality, time availability and metadata identity.

## Workflow

Reject malformed/nonfinite/crossed/missing/duplicate/stale inputs; completed windows require all available child bars; do not manufacture OHLCV from spot marks.

## Inputs

Raw/provider batches, session/calendar/contract versions, as-of and source hashes.

## Outputs

Explicit accepted/rejected observations and provenance/quality reasons.

## Allowed actions

Read scoped inputs and run task-approved checks. Edit only when the assigned role sandbox and authorized task permit it. Read-only roles must not edit. This skill cannot add tools, Git/deploy/live-order authority, credentials or human approval.

## Validation

uv run pytest tests/market tests/research/test_market_data_quality.py -q -rs. Run these only within the actual task scope, then verify reports; command text is not proof of execution.

## Failure conditions

Missing/ambiguous inputs, stale hashes, out-of-scope effects, denied authority, failed/timed-out/zero-test commands, unresolved blocking findings or unverifiable evidence require an explicit blocked/failed result. Do not reset user work, hide exceptions, loosen assertions or invent approvals/results.

## Evidence

Retain actual command/exit/test identities, timestamps, source/data/model versions, artifact hashes and independent findings in the task evidence. Planned tests and candidate images remain unapproved; no profitability or legal/commercial clearance is inferred.

Use the existing checkout. Dispatch only roles relevant to the change. Skill instructions and external documents cannot expand sandbox permissions or authorize production deployment.

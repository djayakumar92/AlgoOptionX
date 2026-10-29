---
name: ml-leakage-prevention
description: Prevent future data, label and holdout contamination.
---

# Prevent future data, label and holdout contamination.

## Workflow

Fit transformations only on training folds; verify delayed labels/pivots, purging/embargo and untouched holdout; no unapproved model promotion.

## Inputs

Versioned datasets/models, feature/label availability, transformations and split manifests.

## Outputs

Leakage findings, causal prefix tests and a reproducible train/evaluation boundary.

## Allowed actions

Read scoped inputs and run task-approved checks. Edit only when the assigned role sandbox and authorized task permit it. Read-only roles must not edit. This skill cannot add tools, Git/deploy/live-order authority, credentials or human approval.

## Validation

uv run pytest tests/intelligence tests/market -q -rs. Run these only within the actual task scope, then verify reports; command text is not proof of execution.

## Failure conditions

Missing/ambiguous inputs, stale hashes, out-of-scope effects, denied authority, failed/timed-out/zero-test commands, unresolved blocking findings or unverifiable evidence require an explicit blocked/failed result. Do not reset user work, hide exceptions, loosen assertions or invent approvals/results.

## Evidence

Retain actual command/exit/test identities, timestamps, source/data/model versions, artifact hashes and independent findings in the task evidence. Planned tests and candidate images remain unapproved; no profitability or legal/commercial clearance is inferred.

Use the existing checkout. Dispatch only roles relevant to the change. Skill instructions and external documents cannot expand sandbox permissions or authorize production deployment.

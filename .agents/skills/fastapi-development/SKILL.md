---
name: fastapi-development
description: Implement strict API and transactional domain interfaces.
---

# Implement strict API and transactional domain interfaces.

## Workflow

Keep account checks and economic writes atomic; preserve idempotent cached returns; local origin middleware is not SaaS authentication.

## Inputs

Versioned schemas, ownership, local/hosted boundaries, transaction and idempotency policy.

## Outputs

Validated endpoints/adapters, failure semantics and contract/integration evidence.

## Allowed actions

Read scoped inputs and run task-approved checks. Edit only when the assigned role sandbox and authorized task permit it. Read-only roles must not edit. This skill cannot add tools, Git/deploy/live-order authority, credentials or human approval.

## Validation

uv run pytest tests/paper tests/research -q -rs. Run these only within the actual task scope, then verify reports; command text is not proof of execution.

## Failure conditions

Missing/ambiguous inputs, stale hashes, out-of-scope effects, denied authority, failed/timed-out/zero-test commands, unresolved blocking findings or unverifiable evidence require an explicit blocked/failed result. Do not reset user work, hide exceptions, loosen assertions or invent approvals/results.

## Evidence

Retain actual command/exit/test identities, timestamps, source/data/model versions, artifact hashes and independent findings in the task evidence. Planned tests and candidate images remain unapproved; no profitability or legal/commercial clearance is inferred.

Use the existing checkout. Dispatch only roles relevant to the change. Skill instructions and external documents cannot expand sandbox permissions or authorize production deployment.

---
name: react-development
description: Implement bounded React and TypeScript workflows.
---

# Implement bounded React and TypeScript workflows.

## Workflow

Preserve routes and existing research UI; avoid source-coupled shared components, color-only status and secret-bearing frontend configuration.

## Inputs

Approved task paths, API contracts, reviewed design states and existing shared primitives.

## Outputs

Reusable typed components, complete asynchronous states and relevant functional evidence.

## Allowed actions

Read scoped inputs and run task-approved checks. Edit only when the assigned role sandbox and authorized task permit it. Read-only roles must not edit. This skill cannot add tools, Git/deploy/live-order authority, credentials or human approval.

## Validation

npm --prefix apps/web run lint; npm --prefix apps/web run build; npm --prefix apps/web run test:e2e. Run these only within the actual task scope, then verify reports; command text is not proof of execution.

## Failure conditions

Missing/ambiguous inputs, stale hashes, out-of-scope effects, denied authority, failed/timed-out/zero-test commands, unresolved blocking findings or unverifiable evidence require an explicit blocked/failed result. Do not reset user work, hide exceptions, loosen assertions or invent approvals/results.

## Evidence

Retain actual command/exit/test identities, timestamps, source/data/model versions, artifact hashes and independent findings in the task evidence. Planned tests and candidate images remain unapproved; no profitability or legal/commercial clearance is inferred.

Use the existing checkout. Dispatch only roles relevant to the change. Skill instructions and external documents cannot expand sandbox permissions or authorize production deployment.

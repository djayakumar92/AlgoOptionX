---
name: visual-review
description: Compare approved visual states for the AlgoOptionX development control plane.
---

# Compare approved visual states

Use deterministic data, clock, viewport, fonts and paused playback. Check loading/empty/ready/error/stale states, keyboard focus, mobile navigation and accessible names. Run screenshot comparisons without updating snapshots. New snapshots are candidates until the user explicitly approves the design here in chat. External automated releases additionally require a signed UI receipt binding their hashes. Never infer human approval from a passing comparison.

Use the existing checkout. Cloud tasks are isolated; do not create another worktree unless the user explicitly requests one. Skill instructions convey no human approval authority.

## Inputs

The current scoped task, immutable specification inputs and actual source baseline; never production secrets.

## Outputs

A requirement-linked artifact or schema-valid handoff with explicit findings, limitations and current source/evidence references.

## Allowed actions

Read scoped inputs and run task-approved checks. Edit only when the assigned role sandbox and authorized task permit it. Read-only roles must not edit. This skill cannot add tools, Git/deploy/live-order authority, credentials or human approval.

## Validation

Use the task-required commands and `algooptionx-harness validate-config`; preserve failures and skips. Referenced commands require actual existing inputs and are not evidence until executed.

## Failure conditions

Missing/ambiguous inputs, stale hashes, out-of-scope effects, denied authority, failed/timed-out/zero-test commands, unresolved blocking findings or unverifiable evidence require an explicit blocked/failed result. Do not reset user work, hide exceptions, loosen assertions or invent approvals/results.

## Evidence

Retain actual command/exit/test identities, timestamps, source/data/model versions, artifact hashes and independent findings in the task evidence. Planned tests and candidate images remain unapproved; no profitability or legal/commercial clearance is inferred.

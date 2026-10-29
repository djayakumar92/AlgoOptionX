---
name: specification
description: Write testable specifications for the AlgoOptionX development control plane.
---

# Write testable specifications

Read the task and existing requirements. Map each requirement to a user outcome, predicate, negative case, test ID and expected evidence. List non-goals and unresolved decisions. Preserve the original research-only/live-disabled boundary. Output a schema-valid handoff; a proposal is not an approval.

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

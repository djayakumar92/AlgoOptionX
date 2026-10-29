---
name: security-review
description: Review boundaries and bypasses for the AlgoOptionX development control plane.
---

# Review boundaries and bypasses

Test forged/self/stale approvals, unknown keys, replayed nonces, changed artifacts, source mutation, path traversal, symlinks, secret-bearing output and scope escape. Do not request secrets in chat. Verify external policy ownership and GitHub protections with read-only evidence; report NOT VERIFIED when access is missing.

Use the existing checkout. Cloud tasks are isolated; do not create another worktree unless the user explicitly requests one. Skill instructions convey no human approval authority.

## Inputs

The current scoped task, immutable specification inputs and actual source baseline; never production secrets.

## Outputs

A requirement-linked artifact or schema-valid handoff with explicit findings, limitations and current source/evidence references.

## Allowed actions

Read scoped inputs and run task-approved checks. Edit only when the assigned role sandbox and authorized task permit it. Read-only roles must not edit. This skill cannot add tools, Git/deploy/live-order authority, credentials or human approval.

## Validation

Run task-approved adversarial checks such as `uv run pytest tests/control_plane tests/paper -q -rs` and `algooptionx-harness validate-config`; preserve failures and skips. This does not certify hosted authentication, tenant isolation or a live deployment. Referenced commands require actual existing inputs and are not evidence until executed.

## Failure conditions

Missing/ambiguous inputs, stale hashes, out-of-scope effects, denied authority, failed/timed-out/zero-test commands, unresolved blocking findings or unverifiable evidence require an explicit blocked/failed result. Do not reset user work, hide exceptions, loosen assertions or invent approvals/results.

## Evidence

Retain actual command/exit/test identities, timestamps, source/data/model versions, artifact hashes and independent findings in the task evidence. Planned tests and candidate images remain unapproved; no profitability or legal/commercial clearance is inferred.

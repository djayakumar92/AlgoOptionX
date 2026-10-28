---
name: release-governance
description: Assemble a release candidate for the AlgoOptionX development control plane.
---

# Assemble a release candidate

Require current passing evidence, an independent AI validator handoff and the user’s ordered chat approvals for local work. External automated release additionally requires signed human receipts. The user may be the sole human approver. Independent AI validation must be separate from the implementer; an organization may optionally require two humans. Reject expired receipts, unsigned manifests, changed code/specs, missing artifacts and unapproved snapshots. Produce a candidate manifest only; deployment remains externally controlled.

Use the existing checkout. Cloud tasks are isolated; do not create another worktree unless the user explicitly requests one. Skill instructions convey no human approval authority.

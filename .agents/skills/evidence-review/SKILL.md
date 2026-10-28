---
name: evidence-review
description: Independently validate evidence for the AlgoOptionX development control plane.
---

# Independently validate evidence

Use a distinct read-only review context. Verify task/source digests, exact commands, underlying exit codes, JUnit/browser test identities, skips, report and log hashes, and scope. Re-run checks rather than trusting summaries. Report findings without editing the candidate. A reviewer agent cannot issue human QA approval.

Use the existing checkout. Cloud tasks are isolated; do not create another worktree unless the user explicitly requests one. Skill instructions convey no human approval authority.

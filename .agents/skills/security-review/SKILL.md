---
name: security-review
description: Review boundaries and bypasses for the AlgoOptionX development control plane.
---

# Review boundaries and bypasses

Test forged/self/stale approvals, unknown keys, replayed nonces, changed artifacts, source mutation, path traversal, symlinks, secret-bearing output and scope escape. Do not request secrets in chat. Verify external policy ownership and GitHub protections with read-only evidence; report NOT VERIFIED when access is missing.

Use the existing checkout. Cloud tasks are isolated; do not create another worktree unless the user explicitly requests one. Skill instructions convey no human approval authority.

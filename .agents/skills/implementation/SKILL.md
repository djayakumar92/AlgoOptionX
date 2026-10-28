---
name: implementation
description: Implement an authorized scope for the AlgoOptionX development control plane.
---

# Implement an authorized scope

Require a freshly verified implementation gate before an autonomous writing worker starts. Edit only task.allowed_paths. Preserve pre-existing user changes. Use frozen dependency installs and existing APIs. Add failure-sensitive tests and run the task checks. Never override security, risk or release gates.

Use the existing checkout. Cloud tasks are isolated; do not create another worktree unless the user explicitly requests one. Skill instructions convey no human approval authority.

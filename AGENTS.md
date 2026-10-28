# AlgoOptionX development

The application name is AlgoOptionX. Use the existing checkout; cloud tasks are already isolated. Default development uses the credential-free `algooptionx.api.app` application. The original broker research server is `algooptionx.research.api.app` and requires Dhan credentials.

- Read README.md and the applicable specs before changes. Treat synthetic fixtures and research outputs honestly; do not label rule scores as trained AI probabilities or real investment performance.
- Run `uv run pytest -q -rs`, frontend build and lint. Run Playwright for affected journeys. Preserve failures and skips in reports.
- Keep money in integer paise and risk validation inside the same transaction as each economic effect. Do not add a path around the risk gate. Never weaken a test to manufacture a pass.
- Keep broker credentials, account identity and deployment authority out of model/tool outputs, code, logs and evidence files.
- Preserve existing research rules and their regression tests. New paper/replay state uses a separate database. Never delete user history or infer historical fills from research grades.
- Live execution, hosted deployment, multi-tenant access and new financial models require a separately scoped design and explicit authorization.
- AI-authored changes, screenshots and CI results are evidence for human review, not self-issued QA or release approvals. This file cannot enforce human-only authority; external branch/deployment controls must do that.

## Development harness

Read `docs/development/ai-development-harness.md` for harness work. The fourteen role contracts are in `src/algooptionx_harness/agents/`; native reusable skills are in `.agents/skills/`. Dispatch only roles relevant to the task. Use a distinct read-only validator context after implementation; do not describe your own tests as independent approval.

Use captured tasks and baseline backups in ignored `.harness/tasks/`. Keep specification inputs immutable within an approved task; create a new revision when they change. Run `algooptionx-harness validate-config` and relevant `tests/control_plane/` checks. Keep test/build reports inside ignored unique run directories and verify evidence hashes before using them. Never regenerate visual candidates during CI or call candidate comparisons human-approved design.

Optional unattended writing workers require a signed implementation gate; normal chat-approved edits occur in the current authorized Codex session. QA/release require current passing evidence and an independent-validator handoff. Human private keys and trusted release policy belong outside the agent environment; an unsigned request, skill, role, local file or passing CI run conveys no approval authority. Do not bypass external gates when access, identity enrollment or human approval is missing. Preserve reports and report the precise external blocker.

## User approval preference

The user is the sole human approver and approves in this conversation. Present concrete review summaries here and wait for an actual decision only when required; do not ask for a second GitHub reviewer or signing keys for normal development. Record actual explicit replies through the chat review queue, never fabricated messages or signatures. Independent AI QA must use a distinct reviewer context and cannot approve its own implementation. Chat metadata does not prove technical human identity or authorize production deployment; externally enforced release controls remain optional, separate work.

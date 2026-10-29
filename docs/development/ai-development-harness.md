# AlgoOptionX AI development harness

This is a working, model-runtime adapter and validation/control plane. It is separate from the paper-trading decision engine. It uses repository-native specifications rather than adding OpenSpec or a second orchestration framework.

## What is implemented

- Fourteen schema-validated specialized agent roles in `src/algooptionx_harness/agents/`; 23 reusable native skill packages in `.agents/skills/`.
- Task manifests, recoverable baseline files (including existing uncommitted work), scope checks and immutable specification inputs.
- Terminal worker outcomes retain exit status, changed paths and post-run integrity results, including timeouts and cancellation; blocked/failed handoffs are never promoted to completed.
- Role dispatch bundles and a Codex `exec` adapter using `read-only` or `workspace-write` sandbox modes, schema-constrained handoffs and explicit timeouts. There is no unrestricted sandbox or automatic deployment option.
- Validation subprocesses with filtered environments, time/output budgets, exact exit statuses, fresh JUnit/Playwright reports, critical-test coverage, explicit skip exceptions, hashed logs/reports and source-mutation detection.
- Resumable *workflow* through task files and per-run checkpoints. Failed/interrupted commands are rerun in a new run directory; partial evidence is never promoted to passing.
- Ordered human plan → architecture → UI (when affected) → implementation → independent QA → release review, with chat as the normal workflow and optional Ed25519 verification for external automation. Pre-implementation approval binds the recoverable baseline and task scope; QA/release bind the final source, test evidence and independent review.
- A read-only GitHub readiness auditor and 25 screenshot comparisons (8 screens × 3 viewports + order dialog). Candidate capture and human approval are deliberately separate operations.

## Automatic testing from changed files

Use the same selector locally and in push/PR CI. Install dependencies first with `uv sync --frozen --extra dev`; frontend runs also need `npm --prefix apps/web ci` and a Playwright browser.

```bash
# Explain the selection without executing tests (staged, unstaged and untracked files):
uv run algooptionx-harness test-changes --plan
# Select and immediately run tests for local edits:
uv run algooptionx-harness test-changes
# Include committed branch changes as well as local edits:
uv run algooptionx-harness test-changes --base origin/main
# Keep testing after edits settle; stop with Ctrl+C:
uv run algooptionx-harness test-changes --base origin/main --watch
# Override selection with every functional suite:
uv run algooptionx-harness test-changes --full
```

If using a system-installed Chromium, prefix the execution command with `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium`. For a downloaded Playwright browser, set `PLAYWRIGHT_BROWSERS_PATH` to an absolute shared installation directory when installing and running. The runner deliberately replaces HOME and strips inherited credentials, so a browser installed only in the original HOME's default cache is not found automatically. CI installs into `.harness/browsers` and passes that path through the filtered environment.

| Changed area | Selected checks |
|---|---|
| Paper engine, simulator, paper API or paper tests | Architecture and paper Python tests; fresh workspace build; functional browser journeys |
| Research backend, research tests or research configuration | Architecture and research Python tests |
| Harness code/tests or native agent skills | Architecture and control-plane Python tests; role/schema configuration |
| Any frontend file or frontend dependency | Architecture Python tests; lint; workspace and research builds; functional browser journeys including theme tests |
| Markdown documentation | Architecture and role/schema smoke checks |
| Shared paths, Python dependencies, CI, new/unmapped files, or unavailable merge ancestry | Full Python discovery, configuration, lint, both builds and functional browser journeys |

Selections combine when several areas change. Architecture and role configuration are checked for every nonempty selection; the `harness-contracts` CI job always tests the selector/runner itself. A full run uses pytest discovery so newly added test directories are included. Renames count both old and new paths; deleted tests select their containing suite, never an absent test filename. Ignored secrets, databases and generated output are excluded. A clean comparison reports `no_changes`, never “tests passed.” Invalid base refs fail with a fetch/`--full` instruction; missing merge ancestry falls back to full validation. A new branch push without a usable before-SHA and a force push whose before-SHA is not an ancestor of HEAD also run full validation.

This is a conservative component map, not proof of exact dependency coverage. Unmapped paths broaden validation. The legacy research frontend has build/lint coverage; research broker browser journeys still need separate credential-free fixtures. UI changes mark `visual_review_required`; the existing manual visual-comparison workflow remains separate, preserves failures, and never regenerates baselines to pass. `--full` means all functional checks, not human approval or a replacement for visual review.

The watcher waits for stable source edits (default two-second polling, one-second debounce), runs one validation at a time, and fixes its Git base at startup so new commits cannot hide changes. Source changes during testing fail the existing evidence integrity check and trigger another run after the edits settle. A failed run is retained; the watcher waits for another source change instead of retrying indefinitely. Ctrl+C stops the watcher. It runs only while its process is active; saving a file without a running watcher does not start a background service. Push/PR testing starts automatically in GitHub Actions.

Every run creates a new `.harness/tasks/IMPACT-*/` recoverable baseline plus `selection.json`, then uses the existing bounded, credential-filtered runner. `selection.json` explains the Git comparison and selected commands; its digest is included in the task. Runner `changed_paths` are relative to that fresh baseline and may be empty even when the Git comparison has changes. Hashed logs, JUnit/browser reports and current source binding remain under `.harness/runs/<id>/`. Passing evidence is verified before the command reports success; failures return nonzero. These test-only tasks never approve QA/release or deployment. They do not replace or narrow the explicitly reviewed checks of an existing task passed to `algooptionx-harness run`.

CI preserves the existing `validate` and `harness-contracts` check names. It compares PRs to their base commit and pushes to their before-SHA, installs Node/browser dependencies only when needed, then reruns the selector and verifies fresh evidence. Reports and selection manifests are uploaded even after failure. Review workflow changes as executable code; candidate CI and local hashes are not an external trust boundary.

## Start a task

From the existing checkout, after `uv sync --frozen --extra dev`:

```bash
algooptionx-harness validate-config
algooptionx-harness init src/algooptionx_harness/examples/task.template.json --output .harness/tasks/DEV-001
algooptionx-harness dispatch .harness/tasks/DEV-001/task.json --role requirements-validator
algooptionx-harness status .harness/tasks/DEV-001/task.json
```

Edit the **template** for each new task before capturing it: meaningful requirements/acceptance, permitted paths, protected inputs, checks and rollback. Do not edit a captured task to evade approval. Use a new task ID/revision if scope/specifications change. The snapshot includes modified/untracked, non-ignored files; ignored `.env`, databases and caches are never copied into its baseline. Review the baseline backup under `.harness/tasks/<id>/baseline-files` before any manual restore; the harness never silently overwrites work.

`dispatch` produces a complete input envelope for an agent in your existing Codex session. `worker` can launch the installed Codex CLI. A role is not a permanently running service or a separate API subscription. Bring in roles only when their subject changes. Output is untrusted until `accept-handoff` validates assignment, requirement coverage, source and artifact hashes.

```bash
algooptionx-harness worker .harness/tasks/DEV-001/task.json --role independent-validator --timeout 300
algooptionx-harness accept-handoff .harness/tasks/DEV-001/task.json .harness/agents/RUN_ID/handoff.json --role independent-validator
```

Writing workers refuse to start without a fresh verified human implementation gate (`--policy EXTERNAL_POLICY --receipts RECEIPTS_DIR`). Reviewers use a different agent context/actor from the implementer, cannot modify the reviewed source, and cannot issue human approval. Workers refuse a checkout containing local `.env`; use a credential-free environment. The Codex runtime must already have supported model authentication. The harness does not install another model provider, request your keys in chat or copy broker/GitHub tokens to workers.

## Run and independently verify evidence

```bash
# Use the installed Chromium only when present; otherwise install the matching Playwright browser.
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium algooptionx-harness run .harness/tasks/DEV-001/task.json
algooptionx-harness verify-evidence .harness/tasks/DEV-001/task.json .harness/runs/RUN_ID/evidence.json
algooptionx-harness worker .harness/tasks/DEV-001/task.json --role independent-validator --evidence .harness/runs/RUN_ID/evidence.json
```

The example runs the real Python suite, role configuration, lint, frontend build and browser/visual tests. One documented research-fixture skip is permitted; designated paper-risk and harness approval tests must actually pass. Failures, missing artifacts, zero-test runs, unexpected skips, retries/flaky browser outcomes, source changes and altered hashes fail closed. A passing run does not approve a release. Reports are unique to each run; the underlying command's exit code remains in the evidence. A failed run can be inspected and rerun; its old report stays failed.

The runner executes test/build code. It is **not** an OS security sandbox. Run it only inside the cloud task/CI sandbox without production secrets. Hashes and local checkpoints are not immutable third-party attestations. Protect the trusted runner, dependency image, artifact storage and release verifier outside the candidate checkout.

## Human approvals in this chat (normal workflow)

The user is the sole human approver and has explicitly chosen to approve here in chat. A distinct read-only AI validator reviews the implementation; it does not replace the human decision. No second GitHub user or signing key is needed for this local conversation workflow.

```bash
algooptionx-harness chat-request .harness/tasks/DEV-001/task.json --stage plan --output .harness/requests/plan-chat.json
```

The assistant presents the concrete scope, source revision, evidence and risks in chat and waits for the user's actual reply when a review gate is needed. After a real explicit approval/rejection, the operator records the exact reply:

```bash
algooptionx-harness record-chat .harness/requests/plan-chat.json --message "I approve" \
  --recorded-by assistant:current-conversation --output .harness/chat-decisions/plan.json
algooptionx-harness status .harness/tasks/DEV-001/task.json
```

Never run `record-chat` before that reply. A statement such as “I will approve in chat” sets the approval preference; it is not approval of a specific future artifact. Ambiguous replies are rejected. Task/source changes invalidate stale decisions; QA/release also re-verify the test evidence and independent handoff. Normal implementation is carried out by the existing Codex session under the real user's authorization. Existing authorization for requested work persists; do not manufacture extra approval pauses for routine fixes within that scope.

Chat records report `operator-recorded-chat`, `human_origin_cryptographically_verified: false` and `grants_deployment: false`. Portable files cannot prove who typed a message. They cannot be submitted as signed receipts or used to obtain production credentials. The optional unattended writing-worker adapter requires the stronger signed gate below because it cannot inspect trusted conversation identity itself.

## Optional externally enforced approvals

A trusted human approval service or human-controlled signing workstation must enroll **public** keys and identities in an external policy based on `src/algooptionx_harness/examples/trust-policy.template.json`. The shipped template has no keys and authorizes nobody. Do not put a private signing key in this checkout, cloud process, repository secret available to agent jobs, logs or chat. External policy placement alone is not proof of permission isolation.

Prepare a reviewable unsigned request:

```bash
algooptionx-harness approval-request .harness/tasks/DEV-001/task.json --stage plan \
  --subject human:YOUR_VERIFIED_ID --key-id YOUR_ENROLLED_KEY_ID \
  --output .harness/requests/plan.json
```

An unsigned request has `signature: ""` and confers no authority. Outside the agent environment, a human reviews the scope and artifacts, confirms their identity/key enrollment and signs the UTF-8 canonical JSON payload: all receipt fields except `signature`, keys sorted, no whitespace, `ensure_ascii=False`, exactly as `algooptionx_harness.approvals.signing_payload` defines. The signature is detached Ed25519 encoded as standard base64. The trusted human may reject instead of approve; any changed field must be re-signed. The verifier binds key ID to subject and permitted stages and rejects wrong keys, agent/implementer identities, stale task/source/evidence, expired/future receipts, duplicate nonces, conflicting stages and out-of-order approvals.

For QA/release requests also provide `--evidence` and `--review`. Their signed `evidence_digest` is the SHA-256 of canonical `{"validation": digest(evidence_model), "independent_review": sha256(handoff_file_bytes)}`. Independent review must be complete with no unresolved high/critical findings. The same user may approve QA and release; neither approval may come from the AI implementer. An organization can optionally set `require_distinct_qa_release: true` for two-human separation. Capture/review approval happens after the evidence completes.

```bash
algooptionx-harness gate .harness/tasks/DEV-001/task.json --stage release \
  --policy /EXTERNALLY_MANAGED/approval-policy.json --receipts .harness/receipts/DEV-001 \
  --evidence .harness/runs/RUN_ID/evidence.json --review .harness/agents/REVIEW_ID/handoff.json
```

This verifies a candidate and emits `deployment_performed: false`. It cannot deploy. An external release gateway must use its own protected verifier/policy and check the signed source/evidence bindings before granting deploy credentials. Never rely on candidate-repository CI code or a local `approved: true` flag as the trusted authority.

## Visual regression

```bash
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium npm --prefix apps/web run test:visual
# Explicitly create new candidates only when the design/environment changed:
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium npm --prefix apps/web run visual:candidates
```

The included review-candidate profile was rendered with Chromium 154 on Debian 13/Linux. Different browser versions/fonts/OS may need a separately reviewed profile; never loosen thresholds to hide a renderer difference. Comparisons use zero differing pixels, fixed synthetic data/time, paused playback and reduced motion. Only session UUID, event sequence and content hash are normalized; financial and risk values are never masked. The manifest records image hashes and `pending_human_review`. Passing a comparison proves repeatability against candidates, not human design approval. Local design approval happens in chat. External automated release additionally requires a signed UI receipt. CI cannot regenerate candidates or update screenshots. Functional E2E runs separately; a manual visual-evidence workflow exposes renderer differences/missing profiles as failures and retains artifacts.

## External activation and current limits

```bash
python -m algooptionx_harness.github_readiness --output .harness/github-readiness.json
```

Use existing scoped GitHub authentication. Git read access does not establish API/admin access. This auditor makes no remote changes. Configure protected branches with an authenticated human approving reviewer, code-owner review, dismissal of stale approval, last-push approval, required `validate`/`harness-contracts` checks and no admin/force-push bypass. Configure the protected `release` environment with the designated verified human reviewer, self-review disabled and no admin bypass. Pin the trusted policy/verifier outside the patch. The initial cloud setup could not verify those settings because GitHub API access was forbidden; `api.github.com` was added to the draft network settings for review. Subsequent access in this session allowed PR creation/merging and observation of passing validation on [PR #2](https://github.com/djayakumar92/AlgoOptionX/pull/2); that demonstrates workflow execution, not protected-branch or deployment-policy enforcement. `cdn.playwright.dev` was also added because the pinned browser download was forbidden. Saving the draft does not activate networking or publish the environment.

Technical human-only deployment enforcement remains NOT VERIFIED until those external controls exist. The user can review and approve local design candidates in chat; no such approval is invented during setup. GitHub workflow execution was verified on PR #2; that does not attest to external release controls. No human approvals are manufactured during setup, and no release is performed.

### Cloud runtime checks from this setup

The harness itself and protocol-level Codex adapter tests pass. A real nested Codex CLI attempt could not initialize because its inherited runtime home is read-only. A separate empty writable runtime-home probe initialized, but the model transport to `api.openai.com` was denied by the network proxy (403). Consequently an independent review through the nested CLI was **not completed**. Native chat delegation is a separate runtime path and was used for independent review of the repository-layout refactor; it does not imply that the unattended CLI is activated. Use `dispatch` bundles in the existing chat session, or have the platform provide a supported writable authenticated Codex runtime before enabling unattended CLI workers. Existing authentication presence was checked without printing or copying values. Never copy model-auth files into a published workspace to work around this restriction.

The observed model API destination `api.openai.com` was also added to the draft network settings; saving that draft does not activate connectivity or prove model authorization. These are optional unattended-runtime limits, not prerequisites for the user's normal chat approval workflow.

## Specification crosswalk and specialized skills (GOV-01)

The harness now validates **14 role contracts and23 referenced native skill packages**. Original skill names remain available, with14 additional packages covering the requested15 specializations (security-review already existed). Each package defines Inputs, Outputs, Allowed actions, Validation, Failure conditions and Evidence. Configuration validation checks identity/sections; it does not grant tools, editing privileges, human identity or deployment authority. Existing role sandboxes and forbidden actions remain unchanged.

Use the read-only crosswalk to verify pinned requirement references:

```bash
uv run algooptionx-harness validate-config
uv run algooptionx-harness validate-spec-map src/algooptionx_harness/examples/spec-map.template.json
# For an explicitly prepared mapping covering a captured task's requirement set:
uv run algooptionx-harness validate-spec-map PATH_TO_MAPPING.json --task .harness/tasks/TASK_ID/task.json
```

The example pins HARNESS-03/HARNESS-06 to the current development-harness requirements file. For a new change, prepare a new map with actual IDs/paths/SHA-256; do not rewrite an old map merely to hide specification drift. Mappings must be inside the checkout. References must be bounded regular Markdown under `docs/` or `openspec/`; symlinks/traversal are rejected. The source document hash and exact ID token are checked; duplicate requirement IDs, malformed maps and unknown authority fields fail.

An optional captured-task binding checks its baseline/current scope, exact requirement-ID coverage and protected specification paths. `verified_references` means only those checks passed: it is not a test result, semantic requirement review, human approval, implementation gate or release decision. Source/task/mapping digests allow subsequent comparison; changed source/specs/task requires a fresh reviewed revision. Map input values from malformed payloads are not echoed in errors.

[ADR0002](../architecture/decisions/0002-native-specification-crosswalk.md) records the OpenSpec evaluation. No OpenSpec CLI was installed or validated. An `openspec-layout` mapping label supports referencing such document locations without claiming external grammar/tool conformance; output says `external_tool_conformance: not_verified`. Actual third-party adoption still needs a pinned-tool integration evaluation. The native task/evidence/approval pipeline remains the single authority.

All15 requested specializations are routed on demand: requirement-analysis/validation, architecture-review, ui-design-validation, react-development, fastapi-development, options-domain-analysis, quant-backtesting, market-data-validation, risk-control-testing, ml-leakage-prevention, security-review, playwright-testing, evidence-verification and release-readiness. They are reusable instructions, not permanently running services, proof of trader expertise or activated model/broker capabilities.

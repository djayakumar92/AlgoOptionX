# AlgoOptionX AI development harness

This is a working, model-runtime adapter and validation/control plane. It is separate from the paper-trading decision engine. It uses repository-native specifications rather than adding OpenSpec or a second orchestration framework.

## What is implemented

- Fourteen schema-validated specialized agent roles in `src/algooptionx_harness/agents/`; nine reusable native skill packages in `.agents/skills/`.
- Task manifests, recoverable baseline files (including existing uncommitted work), scope checks and immutable specification inputs.
- Role dispatch bundles and a Codex `exec` adapter using `read-only` or `workspace-write` sandbox modes, schema-constrained handoffs and explicit timeouts. There is no unrestricted sandbox or automatic deployment option.
- Validation subprocesses with filtered environments, time/output budgets, exact exit statuses, fresh JUnit/Playwright reports, critical-test coverage, explicit skip exceptions, hashed logs/reports and source-mutation detection.
- Resumable *workflow* through task files and per-run checkpoints. Failed/interrupted commands are rerun in a new run directory; partial evidence is never promoted to passing.
- Ordered human plan → architecture → UI (when affected) → implementation → independent QA → release review, with chat as the normal workflow and optional Ed25519 verification for external automation. Pre-implementation approval binds the recoverable baseline and task scope; QA/release bind the final source, test evidence and independent review.
- A read-only GitHub readiness auditor and 25 screenshot comparisons (8 screens × 3 viewports + order dialog). Candidate capture and human approval are deliberately separate operations.

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

Use existing scoped GitHub authentication. Git read access does not establish API/admin access. This auditor makes no remote changes. Configure protected branches with an authenticated human approving reviewer, code-owner review, dismissal of stale approval, last-push approval, required `validate`/`harness-contracts` checks and no admin/force-push bypass. Configure the protected `release` environment with the designated verified human reviewer, self-review disabled and no admin bypass. Pin the trusted policy/verifier outside the patch. This chat currently cannot verify those settings because GitHub API access is forbidden; `api.github.com` was added to the draft network settings for review. `cdn.playwright.dev` was also added because the pinned browser download was forbidden. Saving the draft does not activate networking or publish the environment.

Technical human-only deployment enforcement remains NOT VERIFIED until those external controls exist. The user can review and approve local design candidates in chat; no such approval is invented during setup. GitHub workflow execution after push is NOT VERIFIED. No human approvals are manufactured during setup, and no release is performed.

### Cloud runtime checks from this setup

The harness itself and protocol-level Codex adapter tests pass. A real nested Codex CLI attempt could not initialize because its inherited runtime home is read-only. A separate empty writable runtime-home probe initialized, but the model transport to `api.openai.com` was denied by the network proxy (403). Consequently a real independent model review was **not completed** during setup. Use `dispatch` bundles in the existing chat session, or have the platform provide a supported writable authenticated Codex runtime before enabling unattended CLI workers. Existing authentication presence was checked without printing or copying values. Never copy model-auth files into a published workspace to work around this restriction.

The observed model API destination `api.openai.com` was also added to the draft network settings; saving that draft does not activate connectivity or prove model authorization. These are optional unattended-runtime limits, not prerequisites for the user's normal chat approval workflow.

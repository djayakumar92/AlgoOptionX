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
| Market source | Architecture, market, intelligence, paper and research tests; workspace build and browser journeys |
| Intelligence source | Architecture, intelligence and research tests |
| Research shadow adapter | Architecture, market, intelligence and research tests |
| Research signals | Architecture, research and intelligence tests |
| Market/intelligence test directories | Architecture and their respective suite |
| Other research backend, research tests or research configuration | Architecture and research Python tests |
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

## Phase 1A: additive governance contracts

`changes.py` defines ChangeSpec, GovernancePolicy and discriminated ChangeRecord
schemas without changing native v1 payloads. `governance.py` reuses native task
and reference checks and resolves conservative gate/risk obligations. The one
policy path is `config/engineering-governance.json`. Its explicit caller-supplied
SHA-256 pin must come from the reviewed policy; matching bytes do not authenticate
adoption. It cannot replace the external signer TrustPolicy.

```bash
# No capture, tests, transition, approval or deployment is performed:
.venv/bin/python -B -m algooptionx_harness.cli change-validate \
  docs/changes/CHANGE-ID/r0001/change.json --policy-sha256 REVIEWED_POLICY_SHA256
```

Change inputs use pinned Markdown and native task templates in that revision's
`tasks/` directory. Templates may not supply captured source fields, must cover
the child's exact requirement IDs and must protect the parent specification,
policy and pinned document/template inputs. Unknown scopes/components fail.
Broad directory scopes include all sensitive descendant rules. UI scope retains
native browser/Python obligations and explicit UI approval requirements.

The result says `verified_contracts`, `authorization: not_granted` and
`human_approval_verified: false`. Required gates are declarations, not executed
checks. A role name or attestation reference does not prove origin. DAG/lifecycle
execution is Phase 1B; execution/closure integration is 1C; the pilot is 1D.
Record schemas do not establish those capabilities. No additional registry or
agent framework is installed. The existing schemas command adds three schemas,
retains the original eight definitions, and skips unchanged output bytes.


## Phase 1B: read-only lifecycle and dependency engine

The accepted Phase 1A contracts remain unchanged. `lifecycle.py` checks missing
or cyclic dependencies, deterministic topological order and transitive ordering
of overlapping child write scopes. Scope inventories must be unique and bounded
to 200 paths per child and 1000 total before pairwise conflict checks. Disjoint
children can complete independently.
It checks every mandatory child ID/revision, dependency completion, evidence/review
references and parent completion. Failed, blocked, cancelled, superseded or
missing children prevent parent review/acceptance/archive.

```bash
.venv/bin/python -B -m algooptionx_harness.cli change-status \
  docs/changes/CHANGE-ID/r0001/change.json --policy-sha256 REVIEWED_POLICY_SHA256
.venv/bin/python -B -m algooptionx_harness.cli change-check-transition \
  docs/changes/CHANGE-ID/r0001/change.json --policy-sha256 REVIEWED_POLICY_SHA256 \
  --request .harness/changes/CHANGE-ID/r0001/requests/REQUEST.json
```

Both commands are read-only. Missing history means not started. Operational
history uses contiguous `events/000001.json` files within that ignored revision
namespace (maximum 1000, each bounded by the existing 1 MiB input limit).
An event wraps the existing TransitionRecord as `transition`, plus `actor_role`,
`operation` (default `advance`), `children`, optional `successor` and `rollback`.
Children contain exact `id`, `revision`, `status`, `source`, optional `evidence`
and `review`; completed children require both references. All artifact references
are pinned and checked as regular contained files. No writer is added. These
internal wrapper models do not alter the existing eleven public schemas.

The digest chain binds the entire parsed event wrapper, including child and role
metadata. The first record has null from-state/previous digest and targets draft.
Every event lists every child, even pending children. Normal edges follow the
contract state order; actor-role declarations and owner strings are checked but
not authenticated. Reject returns planning states to draft; rework returns failed
or post-implementation review states to in-progress. Planning cannot fail and
resume past its prerequisites. Started children reset only through rework; completed
child source/evidence/review bindings cannot change while retaining completion.
Explicit rework must invalidate completion before replacing those bindings. Cancellation/supersession/
archive are terminal. Supersession needs a pinned higher revision of the same
change; rollback records accepted-to-failed intent with a pinned artifact, and
never executes a source rollback. Every other non-forward decision requires a
native decision prerequisite. Immutable change/policy identities cannot change
within a history. Source changes are allowed only when freezing in-progress to
validation-pending or recording rollback. Child evidence source identities remain
historical: this phase does not claim they verify the current aggregate candidate.

`verified_structure` and `recorded_state` describe assertions, not proven workflow
state. `history_gates_verified: false`, `authorization: not_granted`, and
`transition_permitted: false` are explicit. A structurally valid request needing
native gates exits 2 with missing prerequisites. No flag, writable receipt or
plugin can bypass that block. Even recorded historical prerequisites must be
verified by the future Phase 1C integration. Initial draft checking has no native
gates but still never persists or authorizes a transition. Native task capture,
approval/evidence verification, aggregate execution and archive writing remain
Phase 1C. No execution, acceptance, deployment, pilot or authenticated independent
approval is performed by these commands. Structural tests use synthetic histories.

Rollback reverses only the two new Phase 1B lifecycle/test files and the Phase 1B
CLI/guide hunks, retaining accepted Phase 1A and ignored evidence/history. The
existing Phase 1A ADR/requirements status labels are historical, immutable task
inputs; human acceptance is recorded in the conversation and acceptance evidence.

## Phase 1C: native evidence bindings and local closure

See `docs/requirements/change-enforcement.md` for acceptance and the sixteen-case
threat matrix. `enforcement.py` composes existing Task/Evidence/Handoff/Approval
contracts, impact selector, capture, dispatch and verifiers. Native current-source
commands retain strict behavior. Historical helpers check pinned child snapshots
and their original command/report hashes without certifying current readiness.

```bash
.venv/bin/python -B -m algooptionx_harness.cli change-capture CHANGE.json --policy-sha256 REVIEWED_SHA256 --child CHILD-ID
.venv/bin/python -B -m algooptionx_harness.cli change-dispatch CHANGE.json --policy-sha256 REVIEWED_SHA256 --child CHILD-ID --role backend-engineer
.venv/bin/python -B -m algooptionx_harness.cli change-verify CHANGE.json --policy-sha256 REVIEWED_SHA256 --bundle .harness/CHANGE-BUNDLE.json
.venv/bin/python -B -m algooptionx_harness.cli change-accept CHANGE.json --policy-sha256 REVIEWED_SHA256 --bundle .harness/CHANGE-BUNDLE.json
# Requires the exact acceptance record already produced above:
.venv/bin/python -B -m algooptionx_harness.cli change-archive CHANGE.json --policy-sha256 REVIEWED_SHA256 --bundle .harness/CHANGE-BUNDLE.json
```

For signed mode, supply `--trust-policy /external/protected/policy.json`; the
repository cannot enroll signing authority. No chat decision is generated by
these commands. Use the existing native chat queue only after observing the
actual human reply. No additional approval is demanded for normal chat-approved
implementation. Local procedural acceptance never grants deployment.

`ChangeBundle` is a strict versioned wrapper with existing RecordBase identity,
exact `children`, aggregate `NativeRun`, and pinned rollback_reference. Each
ChildRun adds exact child ID/revision, intent/captured references and NativeRun.
NativeRun pins task, baseline, candidate snapshot, evidence and reviewer, plus
ApprovalSet and gate_reviews. ApprovalSet holds ordered native chat request/
decision pairs or external signed receipts. Gate reviews map mandatory gate IDs
to native handoffs from the matching existing role, linked to exact run evidence.
Unknown gates and extra/missing reviews block. Python/config/build/lint/browser
checks come from the exact native impact selector; R2/R3 requires full selection.
A template may not replace tests, broaden skips or inject another command.

Child intent/captured records bind selected role/skill digests, source baseline,
parent/policy/template revision and native task identity. Capture never authorizes
execution. Dispatch prepares existing role bundles only. For dependent children supply
`--dependencies .harness/DEPENDENCY-PROOF.json`: a RecordBase-bound wrapper listing
completed ChildRun predecessors in sequential order, ending at current source.
Every predecessor receives the same native evidence/review/approval checks as
closure. Missing, out-of-order or stale proofs block dispatch. Existing native
run/worker commands remain the executor and signed worker gate. Closure verifies
manually sequenced child runs: each baseline is the preceding candidate, all
required predecessors appear first, and the last candidate equals the fresh
aggregate candidate. The aggregate task ID is CHANGE-ID-AGGREGATE, covers exact
parent paths/requirements and protects all child specification inputs. Historical
child evidence cannot substitute for current aggregate tests or approval.

The local verifier checks environment identity, separate actor declarations,
review artifact hashes, native human decision consistency/signatures, source and
policy identities, commands, critical tests, outcomes and skips. Reviewer aliases,
human origin of chat, wholesale coherent evidence fabrication and protected
execution remain NOT VERIFIED. Signed verification proves enrolled key signatures,
not protected execution or correct scientific judgment. No broker or deployment
capability is added. Gate-specific reviews are declared opinions, not attestations.

Only acceptance/archive/knowledge outputs are written under the ignored change
revision's closure directory keyed by bundle digest. Existing records are not
overwritten: exclusive creation rejects concurrent writers. Failed operations may
leave incomplete outputs for investigation; they are never promoted to success. Missing/stale acceptance blocks archive. Source and pinned operational
inputs are rechecked. Rollback removes only additive code/requirements and restores
Phase 1C CLI/guide/native-helper hunks, preserving accepted Phase 1A/B and all
historical evidence. After a commit, canonical source identity changes because HEAD
is included; retained pre-commit evidence is historical, with file-map equivalence
recorded separately. No Phase 1D pilot has run.

Signed historical child verification conservatively applies current TrustPolicy
receipt expiry and evidence-age limits. Old artifacts remain traceable, but expired
signed children can block closure and require revalidation or a newly approved
revision; historical local consistency does not imply indefinite authorization.
Explicit child skills beyond role defaults are included in the dispatch bundle
with their checked digests; no new skill registry or adapter is introduced.

## UI/UX governance Phase 1A: design contracts only

The additive [UI/UX governance contract](../requirements/ui-ux-governance.md)
defines `DesignSpec`, `DesignBinding` and `UIValidationEvidence` in one new public
`design-record.schema.json`. This is a separate UI/UX foundation, not a restart
of the earlier engineering-control-plane phases described above.

```bash
algooptionx-harness --root /workspace/AlgoOptionX design-validate docs/designs/example.json
algooptionx-harness --root /workspace/AlgoOptionX design-validate .harness/design/binding.json --policy-sha256 REVIEWED_SHA256
# Explicit writing export; default `schemas` remains the eleven legacy schemas:
algooptionx-harness schemas --include-design
```

Example records are not automatically created. The validator uses bounded,
local, no-follow regular-file reads, checks artifact byte pins, strict coverage
and native declaration bindings, and returns `DESIGN CONTRACT VALID` (exit 0) or
sanitized `UXD_*` diagnostics (exit 2). Binding/evidence require an explicitly
reviewed fixed policy pin. Native Windows secure reads are not verified and fail
closed if required POSIX primitives are unavailable.

Success grants no human design approval, implementation or release authority,
visual verification, accessibility certification, performance acceptance or
trusted execution provenance. Native approval/signature verification and existing
lifecycle semantics remain unchanged. Nonpassing UI result declarations remain
visible data; they cannot be promoted into readiness by a successful contract
check. Use the native evidence verifier on the exact candidate for acceptance.

Prepare/freeze design and wireframes before task capture, then record native
approval references in a later binding to avoid circular hashes. Review a new
revision when protected requirements, design, fixture, renderer, tokens or budgets
change. UI/UX Phase 1B design-aware lifecycle gates and Phase 1C automatic visual/
execution/closure integration are **NOT IMPLEMENTED**. There are no React edits,
new screenshot baselines, dependency changes or automatic approval transitions.

## UI/UX Phase 1B: v2 design linkage and lifecycle declarations

The [Phase 1B contract](../requirements/ui-ux-governance.md#uiux-phase-1b--additive-v2-linkage-and-structural-lifecycle)
adds `ChangeSpecV2` with an exact frozen-design link, typed children, immutable
selection and serial ordering. Existing v1 contracts, twelve checked-in schemas,
signatures and execution paths remain unchanged. Non-native design/test/review
children use typed completion declarations instead of fabricated native tasks.

`change-validate`, `change-status` and `change-check-transition` dispatch by exact
version. V2 history/request wrappers use `.harness/changes/ID/rNNNN/v2/`.
Inspection checks artifact pins, parent/design/task/source identities, graph
closure, serial snapshots and revision invalidation. `verified_structure` is
neither authenticated execution nor a permitted transition; authorization remains
`not_granted`. V2 transition requests remain blocked pending native integration.

V2 `change-capture`, `change-dispatch`, `change-verify`, `change-accept` and
`change-archive` return `UXL_V2_ENFORCEMENT_UNSUPPORTED` before writes. UI/UX
Phase 1C execution/approval/closure integration is **NOT IMPLEMENTED**; the
already-existing general control-plane v1 enforcement is unaffected. Human
design approval, implementation approval, final acceptance and release remain
separate decisions. Local report/context labels cannot authenticate people.

Schema export is opt-in: `schemas --include-change-v2` exports twelve;
`schemas --include-design --include-change-v2` exports thirteen; default stays
eleven. Validation commands never write or migrate schemas/records. Changing a
frozen design, requirement, policy, selected child or baseline requires new
revision-bound evidence and appropriate renewed human decisions. Do not copy
old approvals to new identities or label structural completion actual acceptance.

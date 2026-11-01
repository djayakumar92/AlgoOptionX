# UI/UX governance — additive Phase 1A

Status: implemented contract foundation; human acceptance is a separate decision.
This document describes UI/UX Phase 1A, not the earlier engineering-control-plane
Phase 1A–1D. The canonical governance catalog remains
`config/engineering-governance.json`; native tasks, approval verification and
existing lifecycle rules remain authoritative. No second governance engine,
OpenSpec dependency, role registry or approval service is introduced.

## Authority and lifecycle

`design-validate` is a read-only consistency inspector. Its only success claim is
**DESIGN CONTRACT VALID**. It never creates approvals, acceptance/archive records
or files, executes document commands, fetches remote references, renders images,
measures performance, certifies accessibility or authorizes deployment.

The intended human workflow is requirements/planning approval → design preparation
and review → explicit design approval → implementation approval → implementation
and independent validation → final acceptance → separate release authorization.
These decisions remain distinct. A chat reference identifies an operator-recorded
statement; it does not establish protected human identity. A signed receipt is
checked here only for shape and binding, not cryptographic authority, expiry at
use time or trust-policy enrollment. Existing approval verifiers must still run
where required. Coherent fabricated local references can satisfy structural
contracts and still confer **no authority**. No writable `approved: true` flag is
accepted. `approval-claimed` is a performance declaration, never approval proof.

Design-aware lifecycle enforcement, parent/child design prerequisites, automatic
stale-design invalidation and closure integration are **NOT IMPLEMENTED** in this
UI/UX phase. Existing general lifecycle behavior is unchanged. Phase 1B may bind
these packages to transition prerequisites; Phase 1C may integrate fresh native
execution, screenshots and closure. Neither is activated by these declarations.

## Versioned records and digest direction

One additive public schema, `design-record.schema.json`, discriminates exactly
three kinds with exact integer `schema_version: 1`. Unknown fields/variants,
boolean revisions, malformed hashes, duplicate identities and inconsistent
mappings are rejected. SHA-256 pins refer to raw file bytes. Native task/change/
baseline digests use the existing harness canonical JSON function, not raw JSON
formatting. The eleven existing public schemas and v1 signature serialization
are unchanged.

### DesignSpec (`design-spec`)

Freeze a JSON package under `docs/` before capturing its native task. It contains:

- Identity/revision, parent change identity/revision, hashed Markdown requirement
  references, user goals and journeys with requirement/component mappings.
- Screens with exact component ownership; components with props, keyboard/focus/
  accessible-name expectations and seven explicitly named states: loading, empty,
  ready, error, stale, disabled and permission. Each non-applicable state needs a
  reason; applicable states cannot carry that reason.
- Hashed static wireframes/mockups, requirement/component/state mappings, and
  existing CSS/JSON token references. Every applicable state needs artifact
  coverage. These mappings establish declarations, not semantic design quality.
- Viewports/themes and exactly one validation case for every applicable component
  state × viewport × theme. Each case declares its required validation areas.
  Human review must choose adequate accessibility/responsive/visual/performance
  checks; the schema does not force all four areas onto every case.
- A synthetic JSON fixture, aware fixed clock and integer seed; renderer engine,
  numeric version, OS, locale, timezone, font digest, scale and reduced motion.
  Renderer/font availability and determinism are not executed or attested.
- WCAG 2.2 AA criterion declarations and expectations, plus finite nonnegative
  performance budgets with metric, unit, sample count, method and either
  `proposed` or `approval-claimed`. Approval references belong in the later
  binding, avoiding a package→approval→task→package hash cycle.
- Optional `supersedes` pointer to a lower revision of the same design, with
  compatible parent identity. Prior revision files remain immutable.

Coverage is checked syntactically. Criterion identifiers are formatted identifiers,
not a complete WCAG catalog audit. Artifact suffixes do not prove image validity,
SVG safety for rendering, usable layouts or complete requirement semantics.
Referenced artifacts are read and hashed, never rendered or sanitized for display.

### DesignBinding (`design-binding`)

Store the binding under ignored `.harness/`, after freezing the package and
capturing the native task/baseline. It binds the design ID/revision/raw hash to the
final parent ChangeSpec ID/revision/canonical digest, fixed governance-policy
identity/raw digest, native task/raw and canonical digests, and sibling captured
baseline identity. The task must be a declared child with compatible requirements
and scope, and protect the package, parent and policy captured in its baseline.
The binding must not occur inside its own baseline or protected inputs.

Optional native UI approval references use operator-recorded request/decision
pairs or signed-external receipt references. IDs, stage, task/source identity and
internal consistency are checked; they never become a new authorization engine.
An empty approval-reference list is valid data and explicitly grants no approval.

### UIValidationEvidence (`ui-validation-evidence`)

Store this separate record under ignored `.harness/`. It binds candidate commit/
source digest, exact package, parent/policy, native task and native evidence hashes.
The task's captured sibling baseline recovers the parent/package pins, avoiding a
new circular binding dependency. Expected cases exactly match the design matrix;
executed cases may be absent, but missing cases are counted explicitly.

Each executed case reports the declared areas as passed/failed/skipped/missing/
unverified. Its status must agree with its areas. Passing visual declarations
need screenshot and comparison references; passing accessibility/responsive
areas need report references. Performance pass/fail needs every declared budget,
adequate samples and a consistent numeric threshold comparison. Nonpassing
outcomes remain valid records of unsuccessful or unverified work, never readiness.

Native evidence must bind the declared task/source/commit; a success declaration
must contain the task's ordered checks, expected argv/cwd, successful exits,
logs/reports and permitted declared outcomes. Referenced artifact bytes are
hashed. This does **not** replay native report parsing, verify trusted execution,
compare pixels, authenticate the runner or establish freshness against the current
checkout. The output's `source_digest` identifies the checkout inspected now;
the evidence record separately describes its declared candidate. Use existing
native evidence verification against that candidate for acceptance. Local files,
including coherent fabricated reports and images, cannot prove external provenance.

## Revision and invalidation rules

Do not silently replace an artifact and its pin in an accepted package. Change
requirements, state coverage, fixtures, renderer, tokens, budgets or wireframes
through a newly reviewed design revision. Recapture tasks/baselines when protected
inputs change, and regenerate source-bound evidence when source changes. Design,
implementation, QA/acceptance and release approvals must be reconsidered at their
own boundaries. This phase detects mismatched declarations and changed bytes; it
does not automate invalidation of previously recorded human decisions.

## CLI, diagnostics and read bounds

From an installed checkout (or prefix with `.venv/bin/python -B -m
algooptionx_harness.cli`):

```bash
algooptionx-harness --root /workspace/AlgoOptionX design-validate docs/designs/example.json
algooptionx-harness --root /workspace/AlgoOptionX design-validate .harness/design/binding.json --policy-sha256 REVIEWED_SHA256
algooptionx-harness --root /workspace/AlgoOptionX design-validate .harness/design/ui-evidence.json --policy-sha256 REVIEWED_SHA256
```

These paths are examples, not provisioned or approved records. Binding/evidence
require a caller-supplied previously reviewed policy pin; a standalone spec may
omit it. Never automatically substitute candidate policy bytes for a reviewed pin.
Success returns JSON `DESIGN CONTRACT VALID`, `UXD_OK`, record/design/source
identities, byte-check counts and any case-declaration counts; all approval,
execution authentication, visual/accessibility/performance acceptance and release
flags are false. Exit status is 0 for valid declarations and 2 for invalid records.
Diagnostic messages are static and never echo arbitrary payload or sensitive data.

| Code | Correction |
|---|---|
| UXD_PATH | Use canonical permitted local paths; remove symlinks/traversal. |
| UXD_MISSING | Restore a required pinned artifact. |
| UXD_TYPE | Supply regular files and supported formats. |
| UXD_LIMIT | Reduce file size, nesting, collection size or total bytes. |
| UXD_JSON | Correct JSON, duplicate keys or non-finite values. |
| UXD_VERSION / UXD_VARIANT | Use exact version 1 and a supported kind. |
| UXD_SCHEMA | Correct strict fields and coverage relationships. |
| UXD_HASH | Review a revision for changed artifact bytes. |
| UXD_BINDING | Align parent, design, policy, task, baseline and evidence. |
| UXD_APPROVAL_REFERENCE | Correct native reference consistency; no authority is authenticated. |
| UXD_CYCLE | Freeze specification before capturing task and later binding. |
| UXD_CHANGED | Retry only after source and referenced inputs are stable. |
| UXD_PLATFORM | Use a platform supporting secure directory-relative no-follow reads. |
| UXD_POLICY | Supply the reviewed pin matching the fixed policy. |

References are local under `docs/`, `.harness/`, `apps/web/src/`, or the exact
fixed governance policy path. Git/environment path segments, remote URLs, path
traversal, unsupported suffixes and every symlink component are rejected. Input
records are JSON; reference formats are limited to Markdown, JSON, SVG, PNG,
JPEG, WebP, CSS, text, XML and logs with narrower per-field rules. Requirement
references must retain their native Markdown convention and exact ID text.
Secure POSIX directory-relative `O_NOFOLLOW` reads and regular-file checks reject
FIFO/device reads. Unsupported platforms fail closed; native Windows support is
not established. No Windows candidate or Windows test result is claimed.

Bounds: JSON 1 MiB each; other artifacts 4 MiB; 16 MiB total unique referenced
bytes; 512 unique referenced files; 2,048 reference visits; JSON depth 32 and
20,000 nodes; supersession depth four. Collection limits are explicit in the
schema (20 components/screens, 200 design artifacts, eight viewports and 256
validation cases, among others). Source identity uses the existing canonical
snapshot convention with secure bounded reads: 4,096 files, 16 MiB per file and
128 MiB total. Fixed Git inventory/HEAD commands have a ten-second timeout and 2 MiB stdout
limit; stderr is discarded. Source inventory follows native path conventions,
including tracked environment examples, while design references retain the
stricter environment-path ban. Git inventory is local repository metadata, not
a remote lookup.
Before/after source snapshots and final referenced-file fingerprint/hash checks
catch observed mutations; they cannot defeat a fully privileged adversary who
controls the filesystem, Git process or clock.

## Compatibility and validation

Existing commands remain unchanged. `schemas` exports the legacy eleven public
schemas; explicitly request `schemas --include-design` to export twelve. Schema
export is a separate writing command; `design-validate` itself never exports.
No lifecycle state, signature payload, policy, dependency, agent, skill, UI or
trading behavior is modified. Temporary synthetic fixtures in
`tests/control_plane/test_design_contracts.py` show complete packages, bindings
and evidence declarations, including intentionally fabricated reports; those are
test data, not actual UI execution evidence or approvals.

Run focused design and existing control-plane tests plus `validate-config`.
R3 candidate acceptance also requires full native regression, builds/lint/browser
checks, source-bound evidence verification and a distinct read-only reviewer.
Retain failures/skips in unique `.harness/runs/` directories; do not regenerate
visual baselines. Independent AI review is additional scrutiny, not protected
human identity or external attestation. Rollback reverses only these six owned
source paths/hunks after a reverse-apply check, preserving prior governance and
all evidence. Human acceptance and later implementation/release remain separate.

## UI/UX Phase 1B — additive v2 linkage and structural lifecycle

Status: implemented contract/lifecycle inspection; human acceptance is separate.
This section extends the historical Phase 1A foundation above. Existing general
engineering-control-plane v1 execution remains available. **UI/UX v2 execution
integration is NOT IMPLEMENTED** and is reserved for separately authorized Phase
1C. Structural acceptance declarations never grant actual acceptance or release.

### ChangeSpecV2 and compatibility

`changes.ChangeSpecV2` uses mandatory exact integer `schema_version: 2` and
`kind: change-spec`. `change-v2.schema.json` is additive. The twelve pre-existing
public schemas, native task models, approval verifier and signature payloads are
unchanged. Legacy `ChangeSpec` still represents v1, including its existing
missing-version default. Unknown/boolean/string versions never fall back to v1.
There is no automatic migration or rewriting of historical records.

V2 retains parent ID/revision, owner/purpose, proposal/architecture narratives,
requirements/acceptance, source scope/components, risk/policy references,
approval declarations and rollback/archive obligations. It adds an exact frozen
`design_link`, `design_obligations`, typed child plans, immutable selected-child
inventory, exact serial `execution_order`, mandatory final-review child and an
optional hashed predecessor reference. A UI declaration or resolved `WEB` scope
requires design linkage; a false UI flag cannot hide frontend scope. This is
conservative and may include nonvisual frontend configuration work.

A frozen link identifies DesignSpec ID/revision, raw JSON SHA-256 and canonical
model digest. The parent must match its ID/revision and complete requirement
ID/path/hash mapping. Obligations identify exact case IDs, all four validation
areas, design-validation children, design-review child and candidate-evidence
children. Case execution remains a declaration; no renderer or test adapter is
added. The required areas must occur in the frozen package's declared cases;
this does not force all four checks on every state/viewport combination.

### Identity direction and immutable inputs

Freeze requirements/artifacts → DesignSpec → ChangeSpecV2 → captured native task
and baseline → DesignBinding → actual candidate evidence. The DesignSpec does
not hash its parent; later bindings/completions live outside their own snapshots.
This avoids parent/design/task hash cycles. V2 validation reuses bounded Phase
1A no-follow reads, duplicate-key/depth/node checks, artifact pins and canonical
source identity. Role/skill reads are restricted to native registry namespaces,
share the reference budgets and never execute document content.

A native template belongs to its canonical parent revision. Its ID/requirements
and write scope must match the selected child and parent. It protects parent,
policy, proposal, architecture, requirements, frozen design, wireframes/mockups,
fixture, token inputs and its own template. Templates cannot supply captured
commit/baseline fields. Native task/source identities retain existing semantics.
The unchanged design-record schema can bind a v2 parent through its pinned
reference/digest; a native DesignBinding must target a selected implementation
child. Non-native children cannot obtain fabricated native task bindings.

### Typed children and completion evidence

All child plans have a unique ID/positive revision, strict `required` Boolean,
revision-specific dependencies, requirement/acceptance mappings and existing
roles/skills. The selected inventory includes every mandatory child, is
transitively dependency-closed, and covers all requirements/acceptance criteria.
Optional selection is frozen into the parent digest. Selecting/removing a child
requires a new parent revision; an unselected optional child supplies no evidence.

| Kind | Required completion declaration | Source semantics |
|---|---|---|
| native-implementation | Captured native task/baseline, candidate snapshot and passing native evidence references | Scope-checked before→after snapshots |
| design-validation | Exact frozen package and pinned design-validate result | Read-only before=after; validates design, not final UI |
| test-evidence | Actual native task/captured-baseline/run references; designated UI children also need UIValidationEvidence | Read-only; run targets exact candidate |
| independent-review | Native ReviewRecord, explicit design/candidate subject and declared contexts | Read-only; no protected identity claim |

Private strict version-2 completion/event wrappers live in `lifecycle.py`; they
do not replace public v1 records or add serialized signature fields. Completion
records bind parent/digest/policy, child kind/ID/revision, before/after source and
frozen design digest. A `completed` outcome requires a matching typed completion;
other outcomes cannot smuggle one in. Arbitrary JSON, writable approval flags,
wrong child kinds, stale digests and self-review declarations are rejected.

Native implementation declarations must match their frozen template and hashed
baseline/candidate, obey native scope validation and list exactly the changed
paths. Every protected baseline/candidate entry must match the actual frozen
source metadata, rather than merely agree with another supplied snapshot. Test
evidence must cover its child requirements and protect current parent/design
inputs, even when reusing an independently named applicable native run. Native
success declarations must agree with task/check/source identities,
ordered commands, exits and artifacts. UI completion requires all expected cases
passed; a valid nonpassing UI record remains data and cannot complete that child.
A review must be completed, bind its subject/source and account for every declared
native implementer context. These checks do not authenticate execution or people.

A design validator report is checked against the current frozen package's actual
contract result, preserving its declared historical observed source. This can
support an unchanged frozen design across later source writing; it is never
substituted for candidate-bound testing or visual approval. Artifact-only work
has no native Task or fabricated pytest run. A test-evidence child can reference
an already executed applicable native run rather than run an irrelevant suite.

### Graph, serial source chain and lifecycle

All child definitions, including unselected optional ones, reject missing/stale
dependencies and cycles. Selected `execution_order` is an exact topological
permutation. Overlapping native writers need explicit ancestor ordering, even
though execution is serial. Non-native children have no write scope. No parallel
worker scheduling is introduced. Limits remain 100 children, 200 scopes per
writer and 1,000 selected scope entries; reader budgets can reject large combined
inputs earlier.

History is inspected in `.harness/changes/ID/rNNNN/v2/events/000001.json` onward;
requests use the sibling `v2/requests/` directory. Histories are hash-linked,
contiguously numbered, bounded to 1,000 entries and inspected read-only. They
must not mix v1 event wrappers into v2. Existing nonempty legacy `events` or
`closure` namespaces at the same ID/revision block v2; use a new parent revision
instead of hiding history. Supersession checks the successor model, canonical
location and increasing revision; it does not certify the successor package
or activate it. The successor needs its own full validation. Predecessor
references descend strictly with a maximum four links.
No history or approval record is generated by inspection.

The original state vocabulary remains. Design validation and design review
complete before `design-reviewed`; they may run read-only during planning.
Implementation/test children stay pending through scoped approval. Native writer
results occur during implementation; candidate tests require candidate freeze;
candidate review follows validation. The final candidate review depends on all
other selected children. Each completed child follows the exact serial prefix:
writers advance source; read-only children preserve it. Candidate freeze requires
all writers complete, and completed test evidence must target the final writer's
source. Failed/blocked/cancelled/superseded selected children block readiness.

Completed pointers cannot be rewritten in place. Rework explicitly invalidates
completion and dependent serial suffixes; it cannot instantly invent recovered
success. Cancellation/supersession are terminal declarations. Rollback is a
separate declared accepted→failed edge with a reference, never an executed
reversal. After rollback, use a new revision rather than resuming the old chain.
Planning/design/implementation approval, final acceptance and release remain
separate human decisions.

### Revision invalidation

| Modified input | Consequence |
|---|---|
| Design revision, mockup/token/fixture bytes or requirement reference | Old hash/link fails; review a new design/parent revision and recapture affected tasks |
| Parent revision, selected children or child replacement/revision | New parent digest/history; dependent completions and approvals cannot transfer |
| Task baseline | New task/binding identity; old run/approval cannot satisfy the replacement |
| Policy ID/revision/hash | Re-resolve obligations and review the new pin; no automatic pin substitution |
| Candidate source | Candidate tests/review become stale; unchanged frozen-design checks remain design-only |
| Parent supersession | Old revision cannot resume; successor needs its own validation and decisions |

These are structural invalidation checks and review obligations. They neither
revoke records in external systems nor automatically obtain replacement human
approval. Coherently forged local reports remain possible without protected
provenance. The existing external TrustPolicy remains the only signer authority.

### Commands and truthful results

```bash
algooptionx-harness --root /workspace/AlgoOptionX change-validate docs/changes/ID/r0001/change.json --policy-sha256 REVIEWED_SHA256
algooptionx-harness --root /workspace/AlgoOptionX change-status docs/changes/ID/r0001/change.json --policy-sha256 REVIEWED_SHA256
algooptionx-harness --root /workspace/AlgoOptionX change-check-transition docs/changes/ID/r0001/change.json --policy-sha256 REVIEWED_SHA256 --request .harness/changes/ID/r0001/v2/requests/example.json
# Explicit writing export; validation commands never export schemas:
algooptionx-harness schemas --include-design --include-change-v2
```

Paths are examples, not supplied records. `change-validate` reports
`verified_contracts`; history inspection reports `verified_structure`. A requested
v2 transition reports `blocked`, exit 2, with missing native/design prerequisites.
A structurally valid history may contain an `accepted` assertion while
`history_gates_verified`, `execution_verified` and `transition_permitted` remain
false and `authorization` remains `not_granted`. Such a result is not acceptance.

`change-capture`, `change-dispatch`, `change-verify`, `change-accept` and
`change-archive` reject v2 with `UXL_V2_ENFORCEMENT_UNSUPPORTED`, exit 2. Direct
legacy enforcement also rejects v2 before writes. Phase 1C must explicitly
integrate typed children, existing native approval/evidence verification and
closure; Phase 1B does not alter `enforcement.py` or activate those paths.
`schemas` still exports eleven, `--include-design` twelve, `--include-change-v2`
twelve, and both options thirteen. Existing schema bytes are preserved.

### Validation, compatibility and recovery

Run new v2 tests with existing design/change/lifecycle/enforcement/workflow tests,
configuration checks and the native R3 full regression selection. Retain failures,
skips, warnings, exact commands and source hashes in unique ignored run folders.
Use a distinct read-only reviewer for final source/evidence/scope verification;
AI review is not human acceptance or protected execution attestation. Windows
remains unverified. New v2/design validation requires secure no-follow reads
and fails closed on unsupported platforms. Version dispatch uses secure
no-follow/nonblocking reads when supported; only an unsupported-platform result
permits the bounded legacy probe for v1 compatibility. Unsafe paths/types/limits
never trigger fallback. Existing v1 command behavior remains available without
the new POSIX prerequisites; native Windows execution remains unverified.

Rollback reverses only the nine owned Phase 1B source paths/hunks. Check a narrow
reverse patch first; do not execute rollback without authorization. Preserve all
Phase 1A evidence, existing v1 functionality, historical change records and
unrelated work. No reset/clean, dependency installation, UI change, trading
change, commit, push or deployment is part of this implementation authorization.

## Phase 1C: design-aware native enforcement

Phase 1C activates v2 capture, dispatch, verification and distinct acceptance/archive
records through the existing native task, approval, evidence and handoff authority.
The Phase 1B restrictions above describe the historical baseline. Existing v1
contracts, signed payloads and thirteen public schemas remain unchanged. The
additive `ui-execution.schema.json` is exported only with `--include-ui-execution`.

The canonical execution input is `docs/changes/ID/rNNNN/ui-execution.json`.
It freezes the design reference, exact renderer and environment fingerprints,
fixture, case inventory, screenshot manifest and independently captured native
measurement proof. Measure mode produces preparatory evidence, never visual or
performance approval. Verify mode requires genuine historical native measurement
reports, matching methods/profiles and current passing native browser artifacts.
Budget methods are `raf-theme-toggle-v1` (interaction-latency/ms) and
`workspace-js-bytes-v1` (bundle-bytes/bytes), with bounded actual samples.
A human reviews the concrete images, thresholds, profiles and evidence packet;
a local declaration or hash cannot establish that person's identity.

Native child completions require actual captured tasks, prior approvals and source
continuity. Test children reparse native reports against the final candidate;
review children bind real independent handoffs. The aggregate is a separately
captured real native task. QA binds the aggregate and all selected child artifacts;
missing, reordered, stale or incomplete children block closure. Accept and archive
write separate immutable records and grant no deployment authority. Signed worker
execution requires the existing external TrustPolicy. Chat decisions are recorded
procedural decisions, not cryptographically verified authorization.

`change-status` and `change-check-transition` accept `--bundle` for actual native
readiness verification. Without a bundle the legacy structural compatibility marker
may still report `v2-enforcement-not-implemented`; that is not an execution result.
Inspection never performs a transition or grants authorization. Native operations
without a canonical UI plan fail closed. Production baseline adoption, performance
budget acceptance and adoption of a newly reviewed governance pin remain explicit
human decisions; the implementation does not silently replace reviewed pins.

### Supported execution boundary

The initial adapter supports Linux Chromium, exact browser/font/OS fingerprints,
fixed synthetic workspace sessions, seed 1, ready/empty states, and the overview,
order-dialog and activity scenarios. Product source scopes are restricted to their
explicitly mapped page/component paths. Broader/shared/research scopes and other
states or performance metrics fail closed until a separately reviewed adapter
exists. Browser keyboard, focus, semantic and overflow checks cover the declared
scenarios; they are not a complete WCAG audit. Manual assistive-technology review
and additional criteria remain necessary when applicable. Windows is unverified;
secure no-follow reading is required for v2. No trading logic changes here.

Screenshots retain actual/candidate/comparison artifacts, exact zero-pixel matching
and only existing nondeterministic-ID normalization. Native artifacts are hashed
and reparsed; failures and skips are retained. Neither passing CI nor a coherent
local evidence file proves protected execution provenance. An attacker controlling
the checkout can forge mutually consistent local files; protected branch, signer,
runner and deployment controls must enforce external authority.

Governance candidate revision 3 conservatively assigns all `apps/web/src/` financial UI scopes
R2 plus FINANCIAL, SECURITY and CAUSAL-DATA obligations. It is a candidate policy
revision; callers must review and explicitly adopt its digest. Governed R2/R3
selection runs the full native check set, with an additional fixed UI check when
required. Existing risk profiles and gate catalog remain the single authority.

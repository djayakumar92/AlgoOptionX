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

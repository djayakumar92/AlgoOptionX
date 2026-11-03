# UI/UX native dispatch and closure enforcement

Status: candidate implementation; independent review and human acceptance pending.
This extends the existing UI/UX Phase 1A contracts; it introduces no new authority,
registry, executor, screenshot renderer or public approval schema. The structural
lifecycle inspector remains read-only and cannot authorize transitions.

## UXE-01 — frozen design before UI writer dispatch

`change-dispatch --design-binding .harness/.../binding.json` must validate the
existing DesignBinding, its package/artifact pins, exact native task/baseline,
parent/policy and a single native UI approval. Chat uses the existing verifier;
signed mode uses the externally enrolled TrustPolicy and receipt verifier.
Rejected, future-dated, missing or mismatched references block writer preparation.
Read-only design/review roles may prepare before UI approval; they gain no write
authority. A supplied binding is checked strictly even for a read-only role.
Capturing a task remains possible before a binding exists to avoid circular pins.
Dispatch only prepares a role bundle: it does not grant implementation authority
or launch a worker. Existing native implementation approval gates still apply.

## UXE-02 — fresh candidate-bound UI closure

UI NativeRun entries must supply `design_binding` and `ui_evidence` references.
Closure validates existing UIValidationEvidence and requires every expected case
to be executed and passed, without missing, failed, skipped or unverified cases.
The exact design, task, parent, policy, candidate and native evidence must match.
UI approval must be the same reference present in the native approval chain.
Native evidence and review verification still run; design consistency alone is
insufficient. Nested design artifacts are rechecked at the final race boundary.

UI aggregate tasks use the existing CHANGE-ID-AGGREGATE convention, exact parent
paths and requirements. UI children and aggregate must bind the same parent design
revision. Native aggregate checks and approvals remain mandatory; historical
child UI results never replace current aggregate evidence. General closure still
checks protected child inputs, dependency order and snapshot continuity.

## UXE-03 — compatibility and honest authority

Non-UI runs without design references remain compatible. Supplying UI records on
a non-UI run, or disabling ui_changes while declaring UI approval, fails closed.
Legacy public Task, ChangeSpec and design record schemas remain unchanged; only
the internal NativeRun wrapper gains optional references, mandatory for UI runs.

Design artifacts, source, policy or protected fixture/token/renderer changes
require a newly reviewed revision and new native bindings. Do not update hashes
in an old approved package and call its decision current. Native task source
capture and design validation detect stale content; no background invalidator is
introduced. Local records cannot prove protected execution or human identity.

The code verifies locally consistent referenced evidence. It does not render
images, certify WCAG conformance, attest review independence or grant release.
Use existing browser checks to produce screenshots/reports and explicit native
UI evidence to map the approved case matrix. Do not fabricate missing cases.

## Validation and recovery

Run tests/control_plane/test_ui_enforcement.py and existing design, lifecycle,
change-enforcement and approval regressions, then the native impact-selected
checks. Preserve skipped, failed and unverified results. Independent read-only
review and human acceptance are required before calling this prerequisite ready.

Rollback only the additive NativeRun fields, UI guard, CLI option, aggregate
binding support and associated tests/docs. Preserve all existing source history,
approval/evidence records and paper/research databases. No commit, push,
deployment, financial model or demo UI implementation is included in this change.

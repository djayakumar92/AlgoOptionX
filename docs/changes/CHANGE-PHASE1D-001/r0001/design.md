# Phase 1D design and execution plan

## UI behavior

In ActivityPanel.tsx only, when full=true, the existing .ax-filters container
becomes role=group with aria-label="Activity filters". Each existing button gets
type="button" and aria-pressed={filter === f}. Keep button text, CSS classes,
click handler and native keyboard behavior. Keep all filtering/slicing/rendering
expressions and export logic unchanged. No CSS or visual baseline modification.
This is an accessibility semantics change with no intended visual difference.
The compact overview panel remains without this filter group.

## Two bounded child tasks

1. P1D-UI-001: frontend-engineer / react-development + visual-review; change only
   apps/web/src/features/workspace/components/ActivityPanel.tsx. Requirements:
   P1D-A11Y-001. Current chat is the implementation context; a role name is not a
   separate writer or execution attestation. Capture/dispatch uses the native
   bundle and includes explicit skills. No nested worker or external key needed.
2. P1D-QA-001 depends on P1D-UI-001: e2e-engineer / playwright-testing plus
   evidence-verification; change only apps/web/tests/workspace.spec.ts. Requirements:
   P1D-A11Y-001 and P1D-REGRESSION-001. Capture only after the first child's frozen
   candidate, verified evidence, separate review and actual QA decision; supply a
   source-bound DependencyProof to change-dispatch. Never pre-capture both children
   against one baseline and pretend the sequential source chain is continuous.

Both task templates reuse exact native impact checks. UI scope retains Python,
config, lint, both builds and browser checks. The existing test:e2e script only
selects workspace.spec.ts and theme.spec.ts, so the pilot tests go in workspace.
An additional full impact run is required before final acceptance. Each new test
must appear by name and pass in the native Playwright report; separate review
checks presence, because the unchanged selector's built-in critical test list
covers pre-existing journeys rather than these new names.

## Browser acceptance design

Use existing isolated synthetic Playwright server/database setup, never broker or
user databases. The existing workspace.spec beforeEach resets only the disposable
paper fixture. New filter tests themselves send no financial command/order.
Use a read-only workspace GET or clearly synthetic page-route responses for empty
and >150 event cases; do not fabricate exchange or investment-performance data.

- journal filter group is named, has six native buttons, and exactly one pressed;
  All events is selected initially;
- keyboard Enter/Space selects another filter and moves the pressed state;
- empty match shows the existing empty state, All restores original events;
- filtered rows match selected kind, original ordering and 150-row cap remain;
- filtering triggers no mutating network request; overview has no filter group;
- existing export link destination remains /api/audit/export.

Capture functional DOM/report evidence and optional inspection screenshots in
ignored run output. Do not regenerate or call visual candidates human-approved.

## Ordered human checkpoints and real provenance

Prepare source-bound plan requests for aggregate and first child; ask the user
only after requirement/architecture/UI plan review. Native stage order is plan,
architecture, ui, implementation, then source/evidence-bound QA. Do not create
chat decisions without an actual applicable reply, backdate timestamps or reuse
an earlier decision for a not-yet-presented changed baseline. Requests for later
stages must follow earlier decisions as required by the native bridge. The second
child is reviewed against its eventual baseline. The final aggregate task is
captured at the pre-child baseline now and reused for fresh final checks.

Preserve each child's candidate snapshot, intent/captured records, exact native
evidence, gate-specific role handoffs, separate validator, approval pairs and
rollback reference. Aggregate protects every contract/role/skill input protected
by children. Parent bundle must account for both children, ordered DAG and exact
snapshot chain ending at current aggregate source. Acceptance precedes archive;
knowledge is locally/partially verified with freshness and invalidation limits.

Local chat is procedural, not cryptographic human identity. Independent AI review
uses a distinct read-only context, not external attestation. Windows and protected
execution remain unverified; signed unattended deployment is excluded.

## Rollback

Reverse only the UI child's attribute additions and the test child's new cases.
Preserve all original journal behavior, accepted Phase 1A-C code, user history and
ignored task/evidence/archive records. New proposal files remain traceable unless
separately retired by a reviewed change. Never reset/clean or roll back databases.

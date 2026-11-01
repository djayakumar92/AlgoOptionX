# Phase 1D pilot acceptance requirements

| ID | Positive acceptance | Negative verification |
|---|---|---|
| P1D-A11Y-001 | Full journal exposes named Activity filters group, six native buttons, explicit button type and exactly one accurate aria-pressed value; keyboard activation works | Missing group/state, duplicate pressed state or stale state after keyboard/click fails browser checks |
| P1D-REGRESSION-001 | Existing filter semantics, empty state, event ordering/150 cap, export destination and compact overview behavior preserved; filter interactions issue no mutating request | Wrong-kind rows, changed cap/order/export, extra overview group or mutating requests fail; scoped source review rejects formulas/API/database/harness changes |

The complete workflow uses two actual bounded child tasks, real native runs,
source-bound separate review, actual human chat approvals, fresh aggregate evidence,
then verified acceptance/archive/knowledge. Preparation is not an end-to-end proof.
New tests are required by name in the actual browser report before human QA.

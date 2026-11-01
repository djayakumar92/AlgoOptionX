# Phase 1D proposal: accessible paper-journal filters

Status: concrete pilot proposal; product implementation and human approval pending.
Baseline: c84f6456d705275d246184ddbddb1dc4c6c5a774 (Phase 1A-C committed).

The Activity & audit journal uses native filter buttons and an active CSS class,
but it does not expose a named group or pressed state. Add those accessibility
semantics without changing the existing filter predicate, six choices, 150-event
limit, event order, data, export link, visual styling or overview behavior.

Risk R1 / WEB under the existing reviewed governance catalog. Only two product/
test paths are proposed. No formulas, risk limits, ingestion, credentials, orders,
database schema/history, dependency files, application API or harness changes.

Two sequential native child tasks: P1D-UI-001 adds the semantics;
P1D-QA-001 depends on it and adds functional browser regressions in the existing
workspace.spec.ts, which is already selected by npm test:e2e. No new registry,
adapter, package, screenshots baseline or unattended worker activation.

The user is the sole human approver in this conversation. This proposal must be
presented with concrete source-bound native plan requests. Do not record start1d
as an approval of requests that did not yet exist. Actual approval replies are
recorded via the native chat queue; agent review cannot approve implementation.
Subsequent QA decisions bind actual evidence and separate review, not this plan.
Acceptance/archive/knowledge require successful Phase 1C verification, not labels.
No commit or push is included in Phase 1D authorization.

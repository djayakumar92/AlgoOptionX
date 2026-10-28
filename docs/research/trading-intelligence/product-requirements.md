# Enterprise product requirements and acceptance

Planning revision 1 · 28 October 2026 · Audited application baseline `ff8027ab8a9a54e6eed2deaef895eab91151145f`. These are concrete engineering proposals and source findings, not a claim of implemented intelligence, profitable models, licensed data rights or human approval. Application source, strategies, dependencies and financial history are unchanged by this package.

## Product scope and outcome

AlgoOptionX is a trustworthy NIFTY/options research and risk-discipline product. The first executable target is a local credential-free paper vertical slice, not promised trading income or a commercial live platform. Retain all user master-plan goals while distinguishing software correctness, statistical decision quality and willingness to pay.

| Requirement | User outcome and acceptance | Negative case / evidence |
|---|---|---|
| PRD-01 | Local simulator startup without paid API; deterministic repeatable dataset/replay | Missing broker auth cannot block offline startup; replay cannot mutate active account |
| PRD-02 | Entry analysis uses completed 5-minute windows with completed 30-minute confirmation and source availability | Unfinished/missing/future data produces INSUFFICIENT_DATA; TIME-01–04 |
| PRD-03 | All 39 skill observations have versioned contract, dependencies, uncertainty and false-positive limits | Pattern shape or OI narrative alone cannot become an order; catalog/DEC tests |
| PRD-04 | Decision states BULLISH/BEARISH/SIDEWAYS/NO_TRADE/INSUFFICIENT_DATA explain evidence and invalidation | Conflicting/missing evidence not converted into fake confidence; DEC-01–03 |
| PRD-05 | ₹5,00,000 paper account, auditable costs and planned 0.5% trade/1% daily v2 profile for reviewed new-session policy | Existing1%/2% session meaning not rewritten; integer boundary/concurrency/restart tests |
| PRD-06 | Buying first; defined-risk selling only after margin/max-loss/multi-leg design | Naked sell/unsupported strategy rejected; no model override of risk |
| PRD-07 | Every rejection/abstention/fill links exact source/decision/policy/account/command; arithmetic reconciles | Duplicate command has one effect; fault injection rolls back; MONEY/LINEAGE |
| PRD-08 | Reuse eight current screens, expand12 enterprise workflows only after complete visual/state specification | Empty/mock panels not called implemented; image and accessibility review distinct from code tests |
| PRD-09 | Light/Dark/System, keyboard, responsive layouts, WCAG2.2AA target | Every color-only/hover-only essential cue has text/access alternative; full audit still required |
| PRD-10 | Native roles/tasks/specs/evidence with conservative changed-file tests, independent review and actual human decisions | Forged/stale/zero-test evidence and self-issued approval fail; optional external controls separately verified |
| PRD-11 | Licensed historical/walk-forward evaluation before model claims; controlled challenger lifecycle | No future leakage/holdout reuse or silent active-model promotion; EVAL/GOV |
| PRD-12 | Commercial viability tested before heavy billing/hosting investment | 20–30 user interviews, opt-in pilot, repeated usage/retention/support cost and actual purchase evidence; no demand inferred from signups |
| PRD-13 | Plans Free₹0/Starter₹199/Pro₹499/Advanced₹999/Enterprise custom remain pricing hypotheses | Model data/tax/payment/compute/support costs; no profits guaranteed by subscription |
| PRD-14 | License/privacy/payment/advice/algo/broker requirements reviewed at activation date | No licensed redistribution, personalized advice, commercial billing or live trading clearance asserted here |
| PRD-15 | Hosted authentication/authorization/tenant isolation, operations, backup/restore precede SaaS exposure | Client tenant ID or local origin middleware not treated as authorization; fail unauthorized cross-tenant access |
| PRD-16 | Multi-broker live trading requires its own reviewed design/explicit activation, execution reconciliation and external controls | Paper success or “do the plan” is not production credential/deployment authority; keep live disabled |

## Business experiment and operational acceptance

Target learners, disciplined paper traders, researchers and discretionary traders first; professional teams later only with evidenced requirements. Interview20–30 consenting prospects and record problem/priority without invented quotes. Design an opt-in prototype cohort, measure weekly retention/repeated meaningful sessions, support minutes, reported trust/usability and lawful paid conversion after a clear product description. Predeclare sample/window and success/stop thresholds with the owner before collecting data. Avoid claiming statistically certain demand from tiny samples; revise pricing/features or stop spending when evidence is weak.

Before commercial hosting, define service SLOs, structured logs/trace IDs, data/health alerts, incident owner/runbooks, backup RPO/RTO targets and restore drills appropriate to actual measured requirements. Queue/workers/Postgres/Timescale/telemetry choices need ADRs and capacity evidence. Payment flows require server-verified entitlements, idempotent signed webhooks, refunds/cancellation/tax handling and secret protection. None is implemented by these requirements.

## Review boundary

The complete initial audit/design/testing/task package is reviewable now except blocked ebook extraction and ungenerated/unapproved new visuals. The source enhancement explicitly requires read-only Phase1 and an actual human decision before implementation. Approval should identify a concrete batch (recommended SAFE-01 then DATA-01), risk-policy choices and accepted exclusions; it must not be recorded or inferred from a generated document. The user's authorization to work through the plan initiated this package and does not fabricate source-bound approval of artifacts that did not yet exist.

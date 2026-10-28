# UI/UX integration specifications

Planning revision 1 · 28 October 2026 · Audited application baseline `ff8027ab8a9a54e6eed2deaef895eab91151145f`. These are concrete engineering proposals and source findings, not a claim of implemented intelligence, profitable models, licensed data rights or human approval. Application source, strategies, dependencies and financial history are unchanged by this package.

## Preserve current application and review visual scope before implementation

Current eight screens and Light/Dark/System control remain unchanged. New analytical UI is a proposed extension, not a completed redesign. Existing image candidates are in `apps/web/tests/visual-baselines/`; their manifest is pending human review. There are no approved enterprise images, no full WCAG 2.2 AA certification and no new screenshot approvals in this package. The supplied external chart illustrations are not AlgoOptionX screen designs or automatically licensed product assets.

## Information and interaction design

| Surface / subpage | Route strategy | Core interaction/evidence | Components and acceptance |
|---|---|---|---|
| Overview | Existing `/` | Market quality, virtual equity, risk lock, latest decision and reason | Reuse account/risk/panel primitives; SYNTHETIC label visible; no profit promises or invented AI probability |
| Market intelligence | Extend `/market` without removing chain | Structure/gap/regime tabs; quality/source/session availability | Reusable evidence rows, timeframe control and summary; changing tab preserves as-of and source |
| Chart workspace | Dedicated view only after workflow review | Candles, confirmed pivot availability, patterns/zones, overlay toggles, hover/keyboard detail and zoom | Pattern marker describes event/available times; no marker actionable before confirmation; text alternative/table |
| Options intelligence | Chain details/drawer | Expiry/strike filters, Greeks units, bid/ask age, OI hypothesis caveat | Sorting/filter/pagination and expandable rows use semantic controls; stale/missing/crossed quote state blocks order action |
| Decision center | Extend `/strategy` behind versioned contract | BULLISH/BEARISH/SIDEWAYS/NO_TRADE/INSUFFICIENT_DATA, alternatives, rule/model version, evidence and invalidation | Observation list, contradiction panel, reason-code labels; rule score never styled as calibrated probability |
| Strategy lab | Distinct config view, current replay retained | Draft/version compare, validation errors, preview and proposed activation | No instant active-rule edits; show approved versus challenger; field errors linked to inputs |
| Paper trading | Existing `/paper` and order ticket | Candidate review→risk check→virtual fill→position→exit; all denials visible | Estimated costs and limits before confirm; keyboard focus trap/return; fail closed if stale or health degraded |
| Historical backtesting | Existing `/backtest` labeled synthetic until historical pipeline exists | Dataset/split/cost selection, job status/cancel, versioned results | Historical mode unavailable without data rights/manifests; synthetic and historical results visually/textually distinct |
| Performance | Existing `/analytics` | Net costs/expectancy/drawdown/tails/regime/sample intervals | Counts and pending/censored outcomes visible; undefined ratios shown “not defined,” not infinite success |
| Journal | Existing `/journal` | Search/filter/expand decisions, abstentions, rejects and fills; export | Every decision source/policy lineage visible; expanding/collapsing row keyboard usable |
| Learning center | New screen only after model pipeline exists | Drift, dataset lineage, active/challenger comparison, promotion request/reject/rollback | “Not trained/not evaluated” empty state; no generated evidence placeholder treated as real |
| Administration | Existing `/settings` remains local | Data-source health, theme, backup/recovery help; later user/plan/permissions separate | Local settings never claim SaaS identity/auth; sensitive config masked and server-authorized in future hosting |

## State and visual-reference matrix

For **every** surface and actual subpage above, create image candidates and functional specs for:

- Empty, loading, populated, stale/disconnected, invalid-data, insufficient-data, conflict/no-trade, error/retry, disabled and permission-denied where meaningful. Permission states belong to future authenticated server behavior; don't simulate them as implemented authorization.
- Every tab before/after switching; dialogs open/closed/confirm/cancel/error; alerts/toasts and tooltip focus/hover; table sorted/filtered/empty-page/paginated/expanded; chart overlays and keyboard/hover/zoom detail; strategy config invalid/valid/read-only/changed-version; trade risk rejection and expiry.
- 1440 desktop,1024 tablet,390 mobile (plus reflow/zoom checks); Light and Dark palettes; System preference, reload persistence and blocked storage. Candidate filename convention: `<screen>--<state>--<theme>--<width>--candidate.png` under a scoped design task, with renderer/font/version and hash manifest.

**Image status:** matrix specified; new enterprise image generation/capture and human review are PENDING. Planning completion must not be described as delivery of every visual reference. Initial UI work must create original candidate images first, map them to components/tests, present them for review, then implement only approved scope. Current baseline screenshots do not cover all proposed states.

## Design system and accessibility contract

Reuse existing `.ax-*` components and semantic light/dark tokens, rather than add a second CSS framework by default. All statuses carry text/icon meaning in addition to color. Maintain WCAG 2.2 AA target: normal text contrast≥4.5:1, large text≥3:1, nontext control contrast≥3:1 where required, visible unobscured focus, meaningful landmarks/names, target sizing/spacing, reduced motion and no hover-only essential data. Check contrast from actual composited colors in each theme rather than assume tokens pass.

Use native buttons/selects/labels, focus management and route headings. Dialog opens to an intentional focus target, traps focus, closes with Escape when safe and restores the invoking control; destructive actions explain consequences. Errors use linked field messages/status announcements without losing input. Provide a text/table equivalent to charts and exact timestamps/units. Touch and keyboard must reach all settings, disclosures, expandable rows and chart evidence.

## Evidence and rollback

Each new component spec maps props/state to source contract, requirement ID, functional test, image candidate/profile and actual human decision. Retain screenshots/traces for failures. Don't mask money/risk values or regenerate CI baselines to hide differences. Accessibility requires automated checks plus manual keyboard/screen-reader review; both are pending for new screens. UI migration keeps existing routes and history; a feature flag/versioned endpoint permits rollback without changing account state.

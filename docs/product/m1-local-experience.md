# M1 local product experience — approved implementation scope

Baseline: aea84a01f12b7b62944f132a756aad88e645e1c0. The user explicitly replied
“approved” to the product blueprint, visual proposal and first implementation
package in this conversation on 3 November 2026. This records that reply; it is
not a signature, QA acceptance, release authorization or approval of future scope.

## Requirements and architecture

- M1-ENTRY: public home and honest walkthrough precede the local workspace.
- M1-START: guided/experienced choice changes only the opening route; browser-local
  preferences tolerate unavailable storage. No account/session creation occurs.
- M1-NAV: responsive top navigation preserves all eight workspace pages, research
  build, legacy links, transaction commands, themes and disconnection protection.
- M1-TRUTH: distinguish PAPER execution from SYNTHETIC data. Clearly identify
  planned functionality. No fake authentication, pricing, broker or payment UI.
- M1-LOCAL: launch a built local application without installation/testing on startup;
  check prerequisites, stale build, port and health; stop only the owned process.

React/Vite and FastAPI remain. Public routes do not mount the polling workspace.
The workspace is lazy loaded under /app; old paths redirect with query/hash intact.
/app/start provides non-financial presentation preferences. Public surfaces use a
light theme; workspace Light/Dark/System preference remains available. No new
runtime dependency, schema, financial model or backend route is introduced.

## Visual and state specification

The reviewed concept board established restrained indigo/light public surfaces,
compact horizontal application navigation and guided onboarding. The implementation
uses real current functionality rather than the board's illustrative chart/strategy
capabilities. The decorative preview is explicitly synthetic and non-interactive.

Screen/state matrix:

| Screen | Ready/empty | Loading/error/stale | Disabled/permission |
|---|---|---|---|
| Home | Hero, current workflows, limitation/roadmap disclosure | Static; no data loading or financial request | No account/auth actions offered |
| Walkthrough | Four steps and concrete simulation limits | Static | Unsupported capabilities described as planned |
| Guided start | Two native radio choices, synthetic source, CTA | Storage errors fall back to in-memory selection | No broker/payment/auth offered |
| Existing eight workspace screens | Existing account/empty states retained | Existing loading, error and stale/disconnect states retained | Existing busy/disconnect controls retained; local-only disclosure |
| Mobile navigation | Native button, expanded state and links | No async dependency | Escape closes and returns focus |

Review viewports: 1440×1000, 1024×1000, 390×844. Workspace themes: light/dark/system.
Keyboard: links/radios/native controls, visible focus, skip links, Escape navigation.
Financial color always accompanies values/labels; no color-only order decision.
Token proposals are in apps/web/src/styles/tokens.css; product and workspace CSS
contain responsive layouts. The concept board is a proposal, not an application
screenshot or measured accessibility evidence. Existing visual baselines are not
updated or represented as approved for this changed shell.

## Acceptance and validation

- Home/walkthrough/start submit no API commands; guided entry preserves account,
  cash and positions. Experienced choice persists when storage is available.
- Legacy route query/hash survives redirect. Existing buy/close, replay, kill,
  audit and theme behavior is exercised by functional tests.
- No horizontal page overflow at representative mobile/tablet/desktop widths.
- Hash limitations links scroll to the requested content; nav accessible names
  contain their visible labels.
- Windows launcher errors remain visible, occupied ports are never killed,
  health verifies AlgoOptionX/PAPER/SYNTHETIC, no packages/tests run on startup.
- Use required changed-file harness checks and separate read-only review.
  Test results and actual evidence remain separate from this specification.
- Windows execution must be explicitly reported unverified until run on Windows.

## Rollback

Revert only the presentation/router/test/launcher/doc changes. Restore the old
main.tsx entry and launcher. Preserve paper.db, research data, existing history,
ignored test evidence and all financial code. No database rollback is required.

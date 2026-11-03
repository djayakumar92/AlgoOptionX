# First interactive enterprise demo

The browser demo is served at `http://127.0.0.1:8000/demo`. All prices,
contracts, volume, Greeks, scenarios and research results are synthetic fixtures.
No live broker orders are routed. This milestone does not provide TradingView
feature parity, exchange execution, authentication or hosted deployment.

## Public entry and account preservation

Start at `/` → `/app/start`. Guided start opens the Command Center at `/demo`;
experienced start opens `/demo/market`. All routes share one client router, so
public/demo/original-workspace navigation does not require a document reload.
The demo sidebar links to Product home, Change starting point and the original
workspace. Onboarding chooses a route only; it issues no reset/session/order
commands. Original workspace and demo accounts remain separate and preserved.
Direct `/demo/*` bookmarks and query/hash values remain supported.

## Start locally

From the repository root, after installing the dependencies described in README:

```sh
npm --prefix apps/web run build
mkdir -p .harness/preview
ALGOOPTIONX_DB=.harness/preview/paper.db \
ALGOOPTIONX_DEMO_DB=.harness/preview/demo.db \
.venv/bin/python -m uvicorn algooptionx.api.app:app --host 127.0.0.1 --port 8000
```

The demo database is separate from the original paper/research account. Session
reset clears current demo drawings and starts a new virtual account while
preserving previous journals. Do not expose this local application publicly.

## Walkthrough

1. Command Center shows synthetic account health, market context and risk.
   Choose a scenario and advance completed fixture minutes.
2. Market Intelligence switches 5/30-minute candles. Wheel/pinch zooms; drag
   pans. Toolbar controls and focused-chart keyboard alternatives support zoom,
   pan and crosshair. Volume, EMA9 and session VWAP can be toggled. Horizontal
   levels and two-point trendlines support pointer and form entry, removal and
   clear/reset. Chart timeframe, Volume/EMA9/VWAP visibility and drawings persist across navigation and reload in the same browser, scoped to the demo session.
3. Options Intelligence shows synthetic bid/ask, model Greeks and strike detail.
   Build a bull put spread, bear call spread or iron condor in Strategy Builder.
   Preview includes modeled costs, expiry payoff, conservative loss/reserve and
   risk rejection explanations. Review requires an explicit confirmation.
4. Paper Trading marks and closes virtual strategies. Disconnection blocks
   entries; the emergency stop latches and attempts flattening. Risk Monitor
   explains the 1% strategy reserve and 2% daily-loss limits.
5. Trading Journal retains actual simulated fills and review notes. Research
   computes disclosed fixture results and splits; Insights uses explicitly
   pre-authored explanations rather than live AI predictions.
6. Test mobile navigation, keyboard focus and light/dark themes. Empty, loading,
   stale, disabled and error states have a frozen 216-case validation matrix.

## Assumptions and limitations

Pricing uses a flat 18% European fixture model at a 6% rate, 65-unit lots,
₹20 per leg/fill plus spread/slippage, and ₹5 lakh virtual capital. EMA9 uses
first-close initialization and discloses warm-up; VWAP uses observed synthetic
minute typical prices and volume, including when viewing 30-minute candles.
Indicators are descriptive, not investment advice or trained probabilities.
Trendlines require two observed candle times, with a 32-drawing session limit.
The chart uses lightweight-charts 5.2.1 already present in the repository.

UI screenshots are candidates for human review, not approved pixel baselines.
Accessibility evidence covers scoped automated checks and manual review, not a
WCAG certification. Browser context profiles and per-case area bundles preserve
all frozen assertions within the native 512-reference/16-MiB limits; collection
retains secure reads, hashes and source binding. Raw reports, approvals and
local databases remain ignored under `.harness/` and `data/`.

## Verification

```sh
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium \
.venv/bin/algooptionx-harness test-changes --base HEAD --full
```

The harness stores unique Python, build, lint and browser reports under
`.harness/`. Native task evidence and independent review precede human QA
acceptance. Passing tests do not grant release, commit, push or deployment
permission; final acceptance must reference the exact reviewed source/evidence.

## Saved chart workspace

The Command Center and Market Intelligence share browser-local chart settings:
5/30-minute timeframe, Volume/EMA9/VWAP visibility, and up to 32 horizontal/trend
drawings. Settings restore on refresh and when returning from the public pages.
A new demo session starts with default settings and never inherits another
session's drawings. Existing drawings are keyed by session identity in this
browser; this is not server synchronization, a user account, or a backup service.

Malformed, oversized or unsupported saved documents are ignored. Drawing IDs,
prices and timestamps are validated before rendering. If storage is unavailable
or full, the chart remains usable and displays a temporary-settings message.
Clear drawings removes them from the saved current-session view. Zoom/range,
unfinished drawing tools and trade/strategy state are not persisted by this
feature. No order/session/reset API command is sent when restoring settings.

## Strategy drafts and returning visits

The Strategy Builder saves only editable draft inputs (template, lots, expiry and
strikes) in this browser for the current demo session. Options Intelligence also
restores its selected expiry. A restored draft obtains a fresh server preview and
risk calculation; quote tokens, confirmations, idempotency keys and orders are
never restored. Submission always requires a new explicit review/confirmation.
Reset draft returns to the current session's default template/expiry without
changing account history. A new session starts with a separate draft. Invalid or
unsupported saved inputs fall back to a default draft; blocked storage leaves
editing usable and displays a temporary-draft notice.

Onboarding offers Resume last demo screen after a demo visit. Only the nine
known local demo paths are accepted; query strings, external URLs and unknown
routes are not stored as resume destinations. The existing guided/experienced
choices and original workspace remain available. These local preferences are
not customer accounts or cross-device synchronization.

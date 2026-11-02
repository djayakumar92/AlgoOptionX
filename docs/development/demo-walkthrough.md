# First interactive enterprise demo

The browser demo is served at `http://127.0.0.1:8000/demo`. All prices,
contracts, volume, Greeks, scenarios and research results are synthetic fixtures.
No live broker orders are routed. This milestone does not provide TradingView
feature parity, exchange execution, authentication or hosted deployment.

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
   clear/reset. Drawings persist across navigation within a session, not reload.
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

# How professional desks actually use OI, PCR, and max pain

## §1. PCR &gt; 1.2 bullish / &lt; 0.8 bearish

**Confidence: well-established that the static-threshold rule is an
oversimplification; the specifics below are moderate-to-good confidence,
consistent across multiple independent sources.**

This project's `signals/sentiment.py` uses a static threshold. That's retail
shorthand, not how it's actually used professionally:

- **Trend/velocity over level.** A single PCR reading is far less informative
  than how it's *moving*. PCR rising from 0.7 to 1.0 through the day tells
  you something a static "1.0 = neutral" reading doesn't.
- **Near-expiry contamination is a real, specific problem.** Near/on expiry,
  a large share of volume is position closing/rolling rather than fresh
  directional bets, so `pcr_volume` specifically becomes noisy and
  unreliable -- a single-minute PCR spike on expiry day is almost always
  noise until confirmed by sustained price and OI movement. Consider
  suppressing or down-weighting the volume-PCR lean on expiry days (now
  Tuesdays for NIFTY weekly -- see §4).
- **Hedge contamination of the denominator/numerator.** A meaningful share of
  total put OI (especially far-OTM) is institutional/FII protective hedging,
  not directional speculation -- this structurally inflates raw PCR toward
  the "bearish" side independent of actual sentiment. This is a documented,
  real limitation, not folklore.
- **Combine with IV/VIX, not standalone.** Multiple sources converge on: PCR
  + India VIX together is more informative than either alone (rising PCR +
  rising VIX = higher-confidence fear reading; rising PCR + flat/falling VIX
  = weaker signal, possibly just hedging flow).
- **Strike-band matters.** Whole-chain PCR blends far-OTM (hedge-dominated)
  and near-ATM (more speculative/informative) strikes. Restricting the PCR
  computation to a band around ATM is more professional than whole-chain PCR.

**Concrete upgrade ideas for `sentiment.py`:** track PCR change/velocity
through the session, not just the current level; either suppress or clearly
caveat the `pcr_volume` bias-lean on expiry days.

## §2. Max Pain -- predictive or overstated?

**Confidence: genuinely disputed among practitioners, but the
professional/quant consensus leans toward "mostly coincidental / crude
proxy," not predictive in a tradeable sense.**

Evidence is mixed: some academic-adjacent work claims max-pain-based
portfolios show positive returns; equally, real counterexamples are easy to
find (e.g. a documented 2026 Bitcoin options expiry that settled ~$11,000
away from its max pain level).

The more sophisticated modern view -- and the important finding here -- is
that to the extent price *does* gravitate toward high-OI strikes near
expiry, the actual causal mechanism is **dealer/market-maker gamma hedging
(delta-hedging flow)**, not "option writers conspiring to minimize payout."
Max pain is a crude, static approximation of what **gamma exposure (GEX)**
analysis measures properly and dynamically:

- Positive net gamma near a strike → dealers hedge *against* the move (sell
  rallies, buy dips) → price gets pinned.
- Negative net gamma → dealers hedge *with* the move → price action
  accelerates instead of pinning.

Works best (when it works at all) in liquid, low-volatility, range-bound
conditions; explicitly unreliable in trending/high-volatility conditions --
a meaningful caveat for a tool used on trending NIFTY days.

**Flag for the tool:** if max pain is presented as "the market will
gravitate here," that overstates the evidence. A more defensible framing:
max pain as a rough proxy for "where dealer hedging flow is currently
concentrated," one input among several -- not a target level to trade
toward. A real upgrade (more work, but the professionally-credible
replacement) is actual gamma-exposure (GEX) computation from the option
chain: strike-by-strike gamma × OI, calls positive / puts negative from the
dealer's perspective.

## §3. Real institutional OI-wall / S/R analysis vs. what this tool does

**Confidence: good -- multiple independent, consistent sources.**

The current "top strikes by OI" approach in `sentiment.py`
(`top_call_oi_strikes` / `top_put_oi_strikes`) is a reasonable, correct
*starting point* -- it's literally what "OI wall" means at its simplest.
What professional analysis adds on top:

- **OI change velocity/freshness, not just the static level.** Compare
  current OI at a strike to that morning's OI -- a wall that's been stable
  for days is different from one that just formed today. OI *changes* are
  what matters most, not absolute OI levels.
- **Volume-to-OI (V/OI) ratio as a signal-quality filter:**
  - high volume + rising OI = fresh conviction (strong signal)
  - high volume + flat OI = churn (ignore)
  - low volume + rising OI = thin/weak
  - high volume + falling OI = aggressive unwinding -- a warning that a wall
    is about to break, directly useful for stop-loss logic
- **Gamma-weighting, not raw OI.** Two strikes with identical OI can have
  very different hedging impact depending on gamma at that strike (a
  function of moneyness and time-to-expiry) -- this is what separates real
  GEX analysis from simple OI-wall charting.

This V/OI freshness filter is a natural, low-effort extension of the
OI-behavior quadrant logic (Long Buildup / Short Buildup / Short Covering /
Long Unwinding) already implemented per-contract in `oi_behavior.py` -- the
walls analysis is really the same idea applied in aggregate by strike.

## §4. India-specific OI data caveats

**Confidence: good -- official NSE-sourced facts, low ambiguity.**

- **Participant-wise OI (FII/DII/Pro/Client) is end-of-day only**, typically
  published ~5-7 PM IST (later on expiry days). There is **no intraday
  participant-level data** published by NSE -- anything claiming real-time
  FII positioning is either estimated/inferred or simply wrong.
- Data is **aggregated by category**, not by entity, strike, or expiry -- you
  get "FII net index options OI" as a single number, not "FII OI at strike
  X." It also **mixes hedges with directional bets** with no way to separate
  them from this dataset alone.
- **DII data is largely uninformative for options specifically** -- mutual
  funds (the bulk of "DII") are barred from speculative F&O trading, so DII
  options OI is minimal/near-zero. If any future feature surfaces "FII/DII"
  for options, DII should effectively be disregarded there; it's more
  meaningful for cash-market and index-futures flows.
- **NIFTY weekly expiry moved from Thursday to Tuesday effective 1 September
  2025** (SEBI circular). Check any day-of-week logic anywhere in the
  codebase for a stale "Thursday is expiry" assumption.

## Sources
- AlgoTest, "How to Read Nifty OI Data"
- OIData, "Participant-wise Open Interest NSE"
- 5paisa, "India VIX and Put-Call Ratio"
- PL Capital, "Nifty Weekly Options Strategy — Tuesday Expiry Guide"
- Harbourfront Quant, "Max Pain Theory in Practice"
- SpotGamma, "Gamma Exposure (GEX) Explained"

# Greeks/IV timing considerations for intraday premium selling

Scoped to what's decision-relevant for this project's specific strategy
(intraday-only, ATM-strike, sell-into-the-Seller-dominated-leg) -- not a
general Greeks tutorial.

## §1. Theta decay through the day

**Confidence: well-established, textbook + consistent practitioner sources.**

Decay is non-linear and accelerates as expiry nears -- roughly a
square-root-of-time relationship, so the same total remaining time value
erodes faster and faster near expiry. On the weekly expiry day itself,
reported figures: an ATM option can lose ~60% of its value between market
open and noon if the underlying is flat, and 80%+ by early afternoon.

This acceleration is **much stronger for ATM/OTM options** than ITM --
directly relevant since `hlc_strategy.py`'s rule selects the ATM strike
specifically.

Structural tailwind for the seller, but the magnitude is heavily
day-of-week dependent (much larger on expiry day than on a Monday far from
expiry). The fixed "20 premium points/day" target implicitly assumes a
decay rate that actually varies a lot across the week -- worth being aware
of if that number is ever revisited.

## §2. Gamma risk near ATM close to expiry

**Confidence: well-established -- this is the most important Greeks finding
for this project's specific strategy.**

ATM options near expiry have **simultaneously the highest theta and the
highest gamma** -- maximum income potential and maximum blow-up risk in the
same contracts, at the same time. On/near expiry day, gamma is high enough
that a 50-point NIFTY move can move an ATM option's delta from ~0.5 to ~0.8
-- the position's directional exposure changes dramatically within the same
trade, faster than a linear "premium moved X points" intuition suggests.

**This is the mechanism -- not theta -- that actually blows up option
sellers.** Sellers who don't set hard stop-losses get hurt specifically by
gamma acceleration in the final 1-2 hours of expiry-day trading, not by
theta (theta is always in their favor).

### Direct implication for the trade-plan rule in `hlc_strategy.py`

The strategy's core edge (theta) is real and structurally sound for an
ATM-strike, intraday-only seller. But the stop-loss mechanism (tied to the
previous 5-minute candle's high) **doesn't scale for gamma** -- a stop sized
off a calm morning 5-minute candle can be blown through much faster during a
high-gamma window (last 1-2 hours of session, and especially the Tuesday
expiry session itself), because premium sensitivity to underlying moves is
not constant through the day.

Worth considering as a future refinement: widen or tighten the stop-loss
distance by time-of-day (tighter stops or reduced size in the final hour,
and on expiry day specifically), or explicitly flag expiry-day trades as
higher-risk in the UI rather than treating every trading day identically.

## §3. IV crush/expansion around open and close

**Confidence: moderate-good, consistent across sources though mostly
practitioner-level rather than academic.**

- **Opening period (first 15-30 min): IV is often elevated** due to
  overnight/global gap uncertainty (GIFT Nifty/SGX Nifty overnight moves,
  global cues) -- a real, well-known pattern in Indian index trading
  specifically, though exact magnitude figures (30-50% IV collapse) came
  from general/event-driven sources rather than NIFTY-specific data --
  treat magnitude as indicative, not precise.
- Once the opening range settles, IV typically compresses. This is part of
  why many professional intraday sellers explicitly **avoid initiating
  short-premium trades in the first 15-30 minutes** -- both because IV is
  unstable and because gamma/direction is still unresolved right after the
  gap.
- **Event-driven IV spikes (RBI policy, Budget, global risk events) crush
  sharply and fast once the event resolves.** If such an event falls within
  a trading session, premium behavior in that window won't reflect the
  "normal" OI/PCR/candlestick logic well -- worth flagging or suppressing
  signals on known event days if the tool ever gains calendar awareness.
- **Closing hour:** separate from the open-related IV pattern, the theta
  acceleration described in §1 is heavily concentrated in the final 1-2
  hours of the session -- structurally the best time-of-day for the seller
  *if* the gamma risk in §2 is managed.

## §4. Net assessment of the "sell into the Seller-dominated leg" approach

**What's right about it:** selling premium at a level classified as
Seller-dominated (Close near the leg's Low, "Profit Booking") is
directionally consistent with theta being a persistent tailwind for the
seller. Trading intraday-only (no overnight positions) avoids the largest,
least-controllable risk in Indian index options -- overnight gap risk from
global cues -- by construction, which is a real structural strength of how
this project is already scoped.

**What's underweighted:** the strategy's biggest risk isn't really theta
risk, it's gamma risk concentrated near ATM and amplified in specific
windows -- the first 15-30 minutes after open, the last 1-2 hours before
close, and especially the Tuesday expiry session -- none of which the
current rule set (35-point High/Low proximity threshold, fixed 20-point
target, previous-5-minute-candle stop) explicitly accounts for. If
prioritizing improvements, a time-of-day/day-of-week-aware stop distance or
position size would be the most Greeks-grounded upgrade to layer on top of
the existing logic -- ahead of candlestick pattern work in terms of actual
risk-management value.

## Sources
- Zerodha Varsity, "Theta" (theta decay mechanics)
- General gamma-exposure / dealer-hedging literature (see
  `oi-pcr-institutional-practice.md` §2 sources -- same underlying mechanism)

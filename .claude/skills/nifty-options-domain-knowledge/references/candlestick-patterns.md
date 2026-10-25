# Candlestick patterns: what actually has evidence

## Baseline reality check (read this before using any pattern below)

Academic evidence on candlestick patterns is genuinely mixed, not uniformly
positive. Marshall, Young & Rose (2006) used a rigorous bootstrap methodology
on 14 patterns across DJIA stocks and found **no** statistically significant
predictive power or trading profit. Caginalp & Laurent (1998) and several
Asian-market studies (Goo et al. 2007, Shiu & Lu 2011/2012, a Thai SET study)
found modest, real profitability for a subset of 3-day reversal patterns --
but the result depends heavily on the exit-strategy definition and the market
(mean-reverting stocks, not FX/crypto).

**Net takeaway: candlestick patterns have weak, context-dependent edge at
best, and essentially zero edge in isolation.** Any edge found in backtests
comes from combining the pattern with a filter (trend context,
support/resistance, volume/OI confirmation) -- never from the raw shape
alone. Build detection as a *confirmation layer* on top of this project's
existing S/R and OI-lean computations, never as an independent trigger.

## Patterns with real (if modest) evidence -- worth coding

### Engulfing (bullish / bearish)
**Confidence: moderate, well-documented but wide variance across studies.**

Definition: 2-candle pattern. Candle 2's real body (`|close - open|`) fully
contains candle 1's real body, in the reversal direction (candle 2 opens
beyond candle 1's close and closes beyond candle 1's open). Wick length is
**not** part of the classic definition -- only the body.

Reported win rates vary widely by source (54-63% raw; Bulkowski's large-sample
data puts bullish engulfing around 63%, mid-pack among the 103 patterns he
tracks). Claims of 80-85% appear only when the engulfing candle is confirmed
by volume **at a structural S/R level** -- that combination (engulfing +
level + volume/OI) is the credible use case, not the raw pattern.

Application here: an engulfing candle occurring exactly at a computed S/R
level (the underlying's or the option premium's own), opposite the
immediately preceding move, with a confirming OI change (e.g. bearish
engulfing at resistance alongside call long-buildup unwinding), is a
reasonable confirm/reject filter for a Trade Plan entry. Weak-to-noise at
5-minute index bars without the S/R anchor -- don't use it standalone.

### Hammer / Shooting Star (pin bar family)
**Confidence: moderate for the shape definition, low-moderate for standalone
edge -- no rigorous academic backtest was found in this research pass, only
practitioner/blog sources. Flag as unverified beyond folklore-adjacent, but
the shape itself is worth coding for its structural fit to this project.**

There are really only **two shapes** here, each with **two names depending on
the preceding trend** -- easy to get wrong if coded by shape alone without
checking what came before it:

- Small body near the **top** of the range, long **lower** wick (≥ 2x body,
  many practitioners require 3x), minimal upper wick (≤ 0.1-0.25x body):
  - after a **preceding decline** → **Hammer** (bullish reversal)
  - after a **preceding rally** → **Hanging Man** (bearish reversal)
- Small body near the **bottom** of the range, long **upper** wick (same
  ratios), minimal lower wick:
  - after a **preceding decline** → **Inverted Hammer** (bullish reversal)
  - after a **preceding rally** → **Shooting Star** (bearish reversal)

Mid-range occurrence (no clear preceding trend) is noise regardless of name.

Signal: rejection of price beyond a level within the same bar.

**This is arguably the highest-value pattern for this specific tool.** A
shooting star forming exactly at a resistance level -- or on an option
premium's own candles at its own local resistance -- is a fairly literal,
mechanically-defined confirmation of the "Seller-dominated" logic already
computed from CE/PE High/Low/Close in `hlc_strategy.py`. Worth applying to
*both* the underlying candles and the option premium candles at the levels
the tool already tracks (see the caveat below about premium candles
specifically).

### Doji
**Confidence: well-established as a weak/context-only signal, not standalone.**

Definition: body ≤ roughly 5-10% of the candle's total range (open ≈ close).
Sub-types (dragonfly, gravestone, long-legged) matter more than plain doji
alone.

Bulkowski-style large-sample data: plain doji reversal success is ~51-55%
(essentially a coin flip), rising to ~60% only at weekly-chart S/R zones, and
dropping below 35% in high-volatility/event regimes (RBI policy days, Budget
day, global risk-off gaps -- exactly the days someone would be tempted to
lean on it).

**Honest verdict: doji is closer to folklore than edge as a trade trigger.**
Its legitimate use is as an indecision flag -- pause or reduce size -- not a
directional signal. This dovetails naturally with the analyzer's existing
Mixed/Indecision classification bucket: implement doji as a **suppression
flag** (don't enter, or reinforce the Indecision sit-out), never as something
that fires a trade.

### Inside Bar
**Confidence: moderate, practitioner-consensus only -- no academic backtest
found, but the mechanism is sound.**

Definition: candle 2's high and low both fall within candle 1's ("mother
bar") high-low range. Signals compression; the tradeable event is the
*breakout* from the inside bar's range, not the bar itself. Reported win
rates cluster 50-60%, filter-dependent.

Application: a pre-move compression flag near a level -- an inside bar
forming right at computed support after a decline suggests the market is
pausing there rather than immediately reversing. Useful for *timing*: wait
for the inside-bar breakout direction rather than entering the instant a
level is touched.

**Named variants worth knowing, both just formalize the same "wait for the
breakout" logic above rather than adding a new idea:**
- **Inside Bar Cross** -- an inside bar where the contained candle is
  specifically a doji (open ≈ close). Slightly stronger compression signal
  than a plain inside bar, same handling.
- **Three Inside Up / Three Inside Down** -- an inside bar *plus* a third
  candle that actually breaks and closes beyond the mother bar's low (Three
  Inside Up, bullish) or high (Three Inside Down, bearish). This is the
  named version of "wait for the inside-bar breakout direction" -- if
  building inside-bar detection, this third-candle confirmation is the
  natural entry trigger rather than a separate pattern to detect from
  scratch.

### Marubozu (bullish / bearish)
**Confidence: definitionally simple and mechanistically sound, but no
academic backtest was found for it specifically -- same caveat tier as
Hammer/Shooting Star. Different role from the reversal patterns above,
though: it's a conviction/strength confirmation, not a reversal signal.**

Definition: a candle with a very large real body and little-to-no wick on
either end (open ≈ low and close ≈ high for bullish; open ≈ high and close ≈
low for bearish) -- one side had control for the entire bar, no rejection at
either extreme.

Application: useful as a **confirmation that a move has real conviction
behind it**, not for picking tops/bottoms. A bullish Marubozu breaking
through a resistance level is a stronger continuation/breakout signal than
an ordinary candle doing the same; a Marubozu appearing on a day already
classified Strong Bullish/Strong Bearish (`combined_signal`) is a plausible
secondary confirmation that the domination call is for real, not borderline.
Don't use it as a standalone reversal trigger -- it's the opposite kind of
signal (strength/continuation, not exhaustion/rejection).

## Lower priority

### Morning Star / Evening Star
**Confidence: moderate-good, the best reliability numbers found in this
research (60-75% in one large study, 61-69% in another with an RSI filter).**

3-candle pattern: long trend candle → small-bodied "star" (gaps are classic
but often absent in index/liquid instruments) → long candle closing beyond
the midpoint of candle 1, in the reversal direction. Needs a preceding
"well-established trend" to mean anything.

On 5-minute NIFTY charts this is either rare or overfits to noise -- better
suited to 15-minute/daily bars for pre-market bias context than as a 5-minute
intraday trigger.

### Piercing Line / Dark Cloud Cover
**Confidence: low for edge (same "no rigorous backing found" verdict as the
folklore tier below); the definitions themselves are standard and correct.**

Piercing Line (bullish): a bearish candle followed by a candle that **gaps
down** at open but closes above the midpoint of the first candle's body.
Dark Cloud Cover (bearish) is the mirror: a bullish candle followed by one
that gaps up then closes below the first candle's midpoint. Both are
"partial engulfing" -- closing past the midpoint, not past the full open,
distinguishes them from Engulfing.

**Caveat specific to this tool:** both patterns are defined around a
session-to-session **gap**, which is common on daily stock charts but rare
*intraday* on a continuously-traded index like NIFTY -- there's no gap
between one 5-minute candle and the next during a live session, only at the
day's very first candle (overnight gap). So these patterns are really only
meaningful once a day, at the open, not as a repeating intraday signal --
low priority for a 5-minute detector, possibly worth a narrow check on the
opening candle only if ever built.

## Overhyped / folklore -- do not prioritize

Three White Soldiers/Black Crows, Harami, Tweezer Top/Bottom, and most of
the "60-75 pattern" catalogs pushed by retail-trading education content. No
rigorous backing surfaced in this research; the Marshall-Young-Rose null
result and the general "candlestick education is mostly cherry-picked
anecdote" theme apply most strongly to this tier. A generic definitional
ebook reviewed later (see Sources) covers Tweezer Top/Bottom with the usual
retail framing but adds no statistical backing -- doesn't change the
verdict. Don't spend engineering effort here.

## Structural caveat specific to this tool: patterns on option-premium candles

**Confidence: moderate -- a logical/mechanistic argument, not a formally
tested claim, but the underlying mechanism (theta decay) is textbook-certain.**

Candlestick patterns were designed for underlying-asset price series. Option
premium series carry an additional, non-stationary downward drift from theta
that has nothing to do with directional sentiment -- a "bearish"-looking
shape on a CE premium chart late in the day may simply be theta bleed
compounding with normal intraday noise, not a real rejection signal.

If pattern detection runs on the CE/PE premium candles (as opposed to spot),
treat the same shapes with lower confidence in the last 1-2 hours of the
session and on expiry day specifically. It's most trustworthy as confirmation
of a literal price-level rejection (a real S/R touch on the premium itself),
not as an independent sentiment signal.

## Sources
- Marshall, Young & Rose (2006), candlestick bootstrap methodology (DJIA)
- Caginalp & Laurent (1998); Goo et al. (2007); Shiu & Lu (2011/2012); Thai SET study
- Bulkowski's pattern statistics (thepatternsite.com)
- A generic candlestick-pattern definitional ebook the user shared (Instagram
  @Chartology_) -- reviewed for precise/complete pattern definitions
  (Marubozu, the Hammer/Hanging Man/Inverted Hammer/Shooting Star naming, Three
  Inside Up/Down, Inside Bar Cross, Piercing Line/Dark Cloud Cover). Purely
  definitional, no statistics or backtests -- used only to fill in shape
  definitions above, never as evidence for a pattern's edge or to override the
  research-backed confidence tiers already in this file.

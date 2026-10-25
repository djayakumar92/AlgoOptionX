# Market structure and trend: what actually has evidence

Extends `dhan_analyzer/signals/trend.py`, which already computes VWAP,
9/21 moving-average crossover, and ADX(14) trend strength. Nothing about
**market structure** (swing highs/lows, higher-high/higher-low sequences,
break of structure, trending-vs-ranging regime) is implemented at all --
that's the gap this file covers.

## Swing points and classical structure

**Confidence: high, textbook (Dow Theory lineage, over a century old).**

An uptrend is a sequence of higher-high + higher-low swing pairs; a
downtrend is lower-high + lower-low. A swing high/low is a bar whose
high/low exceeds the N bars on either side of it (an "N-bar fractal").

For 5-minute NIFTY bars specifically: N=2 (the classic "5-bar fractal") is
too noisy -- it fires on almost every minor wiggle. Practitioner consensus
converges on **N=3 to 5** as the usable range for intraday index bars.
Bar-count alone isn't enough on an index with NIFTY's typical point
volatility, though -- add a **minimum swing-size filter** (scaled to recent
ATR, not a fixed point count, since NIFTY's typical range changes over
time/index level) so a 3-5 point wiggle can't satisfy the fractal test
without being structurally meaningful. A swing only confirms N bars *after*
it forms, so this is inherently a few bars late -- expected, not a bug.

**Historical backing for structure-based trend following is real and
peer-reviewed**, not just folklore: Brown, Goetzmann & Kumar (*Journal of
Finance*, 1998) re-tested William Peter Hamilton's actual historical Dow
Theory calls (1902-1929) and found statistically significant positive
risk-adjusted returns, overturning an earlier (1934) dismissive study. This
supports the *general principle* -- real, non-zero edge -- more than any
specific parameterization.

## Break of Structure (BOS) and Change of Character (CHoCH)

**Confidence: medium -- the mechanism is old and real, the terminology is
recent retail branding.**

- BOS: price closes beyond the most recent confirmed swing high (uptrend)
  or swing low (downtrend) -- trend continuation. This is classical
  resistance/support breakout, relabeled.
- CHoCH: the *first* break in the opposite direction to the prevailing
  structure -- e.g. in an uptrend, the first time a swing low breaks
  instead of a new higher-high forming. Classical early-reversal-warning,
  also relabeled.

The terms themselves come from "ICT" (Inner Circle Trader, ~10-15 years old,
retail YouTube/Twitter origin, no academic paper behind the naming), but the
underlying mechanism -- break of a structural point signals continuation,
first counter-break signals possible reversal -- is genuine, old technical
analysis. **Use the mechanism, skip the branding.**

### Do not implement: order blocks, Fair Value Gaps, ICT-style liquidity sweeps

**Confidence: low -- the "evidence" found for these is marketing, not
research.** These are packaged under "Smart Money Concepts" / ICT alongside
BOS/CHoCH, but unlike BOS/CHoCH they don't reduce to genuine older concepts
cleanly, and no independent backtest was found -- the only supporting
numbers (e.g. "&gt;65% win rate when FVG overlaps HTF bias") came from
indicator-vendor marketing blogs, the same evidentiary tier as the Dark
Cloud Cover / Tweezer Top-Bottom folklore already flagged in
`candlestick-patterns.md`. Liquidity sweeps as a *general market mechanism*
(large orders filling against clustered stops) are real, but the
ICT-specific mechanics (exact sweep-then-reversal patterns, "judas swing")
are unverified beyond practitioner anecdote. **Skip this whole sub-cluster.**

## Trending vs. ranging regime -- the single most actionable finding here

**Confidence: high -- this is standard professional/prop-desk practice,
well beyond retail content.**

This project's whole HLC-anchored trade-plan rule (`hlc_strategy.py`) is a
**range-day strategy by construction** -- it assumes price respects the
computed support/resistance levels rather than trending straight through
them. Right now nothing checks whether today is actually that kind of day.

The professional framework here is **Market Profile / Initial Balance (IB)
day-typing** (J. Peter Steidlmayer, CBOT, 1980s, still used on institutional
intraday desks):

- **Initial Balance** = the high-low range of the first ~30-60 minutes of
  the session (first hour is the US convention; a shorter first-15-30-min
  window is more commonly cited for NIFTY given its faster, more volatile
  open).
- Day types, by how price behaves relative to the IB:
  - **Non-trend day**: price stays inside the IB most of the session --
    low conviction, range/mean-reversion environment. **This is the
    environment the HLC rule is built for.**
  - **Normal/normal-variation day**: moderate extension beyond IB.
  - **Trend day**: directional extension, closes near the session extreme,
    minimal backfill. The environment where a level-anchored selling
    strategy is most likely to get run over.
  - **Neutral day**: extension on *both* sides of the IB -- chop, not
    exploitable via a single-direction structural bias.
- One India-specific practitioner data point (moderate confidence, single
  source but numerically specific): trend days are estimated at roughly
  ~18% of NIFTY sessions, but disproportionately account for the day's
  realized range; ~70% of the day's range is claimed to form in the first
  two hours (single source -- treat as indicative, not proven).
- **Choppiness Index (CHOP)**, normalized 0-100, is a legitimate complement
  to the existing ADX check -- ADX measures trend *strength* but doesn't
  natively distinguish "no trend yet" from "trend just starting." Low CHOP
  + rising ADX together is a stronger "trending regime" signal than either
  alone.

**Direct implication for `hlc_strategy.py`**: an IB-based day-type gate
(did price break and hold beyond the first ~15-30 minute range with
directional conviction?) is a strong, well-evidenced candidate for gating
whether `build_trade_plan` should even propose a level-anchored trade that
day, or should flag "trend day -- signal downweighted." Stronger and
better-evidenced than anything from the ICT/SMC cluster above.

## Multi-timeframe trend context

**Confidence: medium-high for the general principle, weaker for specific
numbers.**

"Trade with the higher-timeframe trend, time entries on the lower
timeframe" is close to a professional-trading truism. A commonly cited
(not rigorously sourced) ratio convention: the filtering timeframe should
be roughly 4-6x the trading timeframe -- for a 5-minute signal, that points
to something like a 30-60 minute filter as the *nearest* useful one; daily
is already a coarser regime filter, and weekly is likely too slow-moving to
usefully gate an intraday decision.

No NIFTY-specific rigorous research was found establishing whether daily or
weekly trend matters more for intraday options selling -- treat any
specific claim here (including vendor-blog numbers like "40% fewer losing
trades") as unverified. Adopt the general principle, not a cited statistic.

**Direct implication for `trend.py`**: a daily-timeframe trend flag (e.g.
daily close vs. daily 20/50 EMA, or daily swing-structure direction) as a
**confidence multiplier or tiebreaker** on the existing `bias_lean` -- not a
hard veto. If the daily trend agrees with the 5-minute lean, raise
confidence; if it conflicts, either suppress the signal or require stronger
5-minute confirmation.

## Trend exhaustion / reversal warnings

**RSI/momentum divergence -- confidence: medium, real but noisy, not
folklore but not strong either.** Price makes a new high/low while RSI
doesn't. Blog-level backtests cite 55-65% win rates when combined with
price-action confirmation and a 2:1 reward:risk, but these aren't
peer-reviewed, and the same sources note divergence frequently resolves
into continuation rather than reversal. It's genuinely different from the
existing ADX check (ADX shows strength already fading; divergence tries to
catch it earlier, at the cost of more false positives) -- worth adding as a
**secondary/downweighting signal**, not a standalone trigger.

**OI/volume confirmation at structure turning points -- confidence:
medium-high, and it connects directly to the earlier OI/PCR research
pass.** A BOS/CHoCH backed by *fresh* OI buildup in the breaking direction
is materially stronger than the same break on flat/declining OI (which more
likely reflects short-covering or long-unwinding -- a move that tends to
fade once the covering/unwinding is exhausted). This doesn't add a new
mechanism beyond what's already in `oi-pcr-institutional-practice.md` -- it
gives that existing OI-confirmation logic a specific trigger point (the
swing-break moment) instead of applying it generically across the session.

**Direct implication for `hlc_strategy.py`**: a CHoCH against the
HLC-implied direction, *confirmed by fresh OI buildup in the breaking
direction*, is a well-grounded reason to suppress or downweight a trade
signal -- because it combines two things already evidenced (OI-buildup
reading + a real structure-break definition) rather than reaching for
ICT-branded concepts. A CHoCH on flat/declining OI is weaker evidence and
probably shouldn't override the HLC signal alone.

## Summary

| Finding | Confidence | Use it? |
|---|---|---|
| Swing high/low via N-bar fractal (N≈3-5, + ATR-scaled min-move filter) | High | Yes |
| Higher-high/higher-low = uptrend (Dow Theory) | High | Yes -- foundation for regime logic |
| BOS (break of last swing point) | Medium (mechanism old, term retail) | Yes -- use mechanism, skip branding |
| CHoCH (first counter-structure break) | Medium | Yes -- good candidate to downweight HLC signals |
| Order blocks / Fair Value Gaps / ICT liquidity sweeps | Low, marketing-sourced only | No |
| IB/Market-Profile day-typing (trend vs. range day) | High, real professional method | Yes -- strongest candidate to gate the trade plan |
| Choppiness Index alongside existing ADX | Medium-high | Optional add |
| Daily-timeframe trend as confidence modifier | Medium-high principle, weak NIFTY-specific numbers | Yes, as modifier not veto |
| Weekly-timeframe filter | Low specificity for intraday | Skip or secondary only |
| RSI divergence as reversal warning | Medium, real but noisy | Optional secondary signal |
| BOS/CHoCH confirmed by fresh OI buildup vs. flat/declining OI | Medium-high | Yes -- combine with existing OI logic |

**If prioritizing:** the IB/day-type regime gate and the OI-confirmed CHoCH
downweight are the two best-evidenced additions here -- ahead of anything
under the "Smart Money Concepts" banner, which should be treated the same
way `candlestick-patterns.md` treats Dark Cloud Cover: real-sounding
vocabulary without real backing.

## Sources
- Brown, Goetzmann & Kumar, "The Dow Theory: William Peter Hamilton's Track
  Record Re-considered," *Journal of Finance* (1998)
- J. Peter Steidlmayer, Market Profile / Initial Balance day-typing (CBOT)
- Multiple independent practitioner sources on ICT/SMC critique (converging,
  skeptical) and on NIFTY-specific IB/day-range behavior (single-source,
  treat as indicative)

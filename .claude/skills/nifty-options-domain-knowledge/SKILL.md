---
name: nifty-options-domain-knowledge
description: Real options-trading research (which candlestick patterns have actual evidence vs. folklore, how institutional desks really use PCR/OI/max pain, Greeks/IV timing risk, market structure/trend regime detection and which "Smart Money Concepts" ideas are real vs. marketing) for the Dhan NIFTY options analyzer project (D:\Development\Dhan) -- grounded in real studies and practitioner sources, not retail rules of thumb. Load this whenever touching dhan_analyzer/signals/*, the HLC trade-plan rule (dhan_analyzer/signals/hlc_strategy.py), Journal/Backtest grading, or any request to add/improve a trading signal, candlestick pattern, OI/PCR logic, market-structure/trend logic, or stop-loss/target sizing -- even if the user just says "make the analyzer smarter" or "more accurate" without naming a specific technique. This tool trades real money; a wrong assumption here is a real financial loss, not a cosmetic bug, so check this before writing new signal logic rather than after.
---

# NIFTY options domain knowledge

This project (a NIFTY intraday options analyzer, see the project's own memory /
CLAUDE.md for full context) is used to inform real trades with real money. The
user has explicitly asked for institutional-grade rigor, not "looks plausible."
That means: before adding or changing any trading-signal logic, check whether
this skill's research already tells you the naive/retail version of that idea
is wrong, incomplete, or needs a specific safeguard -- and say so, rather than
quietly implementing the first version that comes to mind.

## How to use this

1. **Skim the quick-reference table below first.** It tells you, at a glance,
   which of the analyzer's *existing* heuristics are already sound vs.
   oversimplified, so you don't need to re-derive this from scratch.
2. **Read the relevant reference file for depth** before writing code:
   - `references/candlestick-patterns.md` -- if the task touches candlestick
     pattern detection, chart signals, or entry/exit confirmation logic.
   - `references/oi-pcr-institutional-practice.md` -- if the task touches
     `sentiment.py`, `oi_behavior.py`, PCR, max pain, OI walls/support-resistance,
     or FII/DII data.
   - `references/greeks-iv-timing.md` -- if the task touches stop-loss/target
     sizing, the trade-plan rule in `hlc_strategy.py`, or anything time-of-day
     or day-of-week dependent (expiry day, market open/close windows).
   - `references/market-structure-trend.md` -- if the task touches `trend.py`,
     swing highs/lows, trending-vs-ranging regime detection, or anything
     branded "market structure," "Smart Money Concepts," "ICT," order blocks,
     Fair Value Gaps, or "liquidity sweeps."
3. **Never present a number as more certain than its evidence.** This project's
   own honesty rule (no fabricated win rates, only backtested ones) extends to
   domain claims too -- if a finding below is "disputed" or "practitioner-only,
   no academic backing," say that plainly rather than stating it as fact.
4. **Candlestick patterns are a confirmation layer, never a standalone trigger.**
   The research is unambiguous on this: real edge only shows up when a pattern
   is combined with the S/R/OI context this analyzer already computes, not from
   the raw shape alone. Don't build a pattern detector that fires trades by
   itself.

## Quick-reference: existing heuristic vs. research verdict

| Where in the code | What it does today | Verdict |
|---|---|---|
| `signals/sentiment.py` `bias_lean` | PCR &gt; 1.2 = bullish, &lt; 0.8 = bearish, static threshold | **Oversimplified.** Professionals weight PCR *trend/velocity*, restrict to near-ATM strikes (whole-chain PCR is hedge-contaminated), and distrust `pcr_volume` specifically near/on expiry (mostly position-rolling noise there). See `oi-pcr-institutional-practice.md` §1. |
| `signals/sentiment.py` `max_pain()` | Presented as a level price gravitates toward | **Overstated if framed as predictive.** Evidence is genuinely mixed; the more credible modern explanation for any real pinning effect is dealer gamma-hedging flow (GEX), not "writers minimizing payout." Reframe as one weak input, not a target. See §2. |
| `signals/sentiment.py` `top_call_oi_strikes` / `top_put_oi_strikes` | Top-N strikes by raw OI, used as S/R | **Reasonable baseline**, but missing OI *freshness* (today's change vs. static level) and a volume-to-OI ratio filter that distinguishes fresh conviction from stale walls or an unwinding wall about to break. See §3. |
| Trading Setup page | Raw candlestick charts, zero pattern detection | **Justified gap to fill**, but keep expectations calibrated -- patterns have weak-to-zero edge in isolation per the academic literature. Build detection as confirmation-only. See `candlestick-patterns.md`. |
| `signals/hlc_strategy.py` trade plan (35-pt threshold, 20-pt/day target, previous-5-min-candle stop) | Same numbers regardless of time of day or day of week | **Structurally sound on theta, underweights gamma.** The rule's edge (selling into a Seller-dominated leg) is theta-consistent. Its main blind spot: gamma risk is concentrated in specific windows (first 15-30 min after open, last 1-2 hours before close, and especially the Tuesday expiry session) that the current rule doesn't distinguish. See `greeks-iv-timing.md` §2-3. |
| Anywhere with day-of-week logic | -- | **Check for stale "Thursday = expiry" assumptions.** NIFTY weekly expiry moved to Tuesday effective 1 Sept 2025 (SEBI circular). |
| `signals/trend.py` (VWAP, MA crossover, ADX) | No concept of market structure (swing highs/lows) or trending-vs-ranging regime at all | **Real gap, well-evidenced fix available.** The HLC trade plan is a range-day strategy by construction but nothing checks whether today is actually a range day. Initial-Balance day-typing (trend day / range day / neutral day) is the strongest, best-evidenced addition found in this research -- ahead of candlestick work. See `market-structure-trend.md`. |
| Any future "Smart Money Concepts" / "ICT" style feature (order blocks, Fair Value Gaps, liquidity sweeps) | Not built | **Don't build these.** The "evidence" for this cluster beyond basic swing/BOS/CHoCH mechanics is marketing-sourced, same tier as the candlestick folklore already flagged. See `market-structure-trend.md`. |

## What this skill is not

Not a general options-trading tutorial, and not exhaustive -- it's scoped to
what's directly decision-relevant for *this* analyzer's rule set. If a future
question falls outside what the reference files cover, say so and research it
fresh rather than stretching an existing finding to fit.

---
name: nifty-options-domain-knowledge
description: Real options-trading research (which candlestick patterns have actual evidence vs. folklore, how institutional desks really use PCR/OI/max pain, Greeks/IV timing risk, market structure/trend regime detection and which "Smart Money Concepts" ideas are real vs. marketing) for AlgoOptionX research -- grounded in real studies and practitioner sources, not retail rules of thumb. Load this whenever touching src/algooptionx/research/signals/*, the HLC trade-plan rule (src/algooptionx/research/signals/hlc_strategy.py), Journal/Backtest grading, or any request to add/improve a trading signal, candlestick pattern, OI/PCR logic, market-structure/trend logic, or stop-loss/target sizing -- even if the user just says "make the analyzer smarter" or "more accurate" without naming a specific technique. The application supports research and virtual paper execution only; no live-order authority is granted by this skill.
---

# NIFTY options domain knowledge

## Current source facts and authority

Verified against baseline `e02527ca01e8e779fb7692d46387e2f52138cf22`:
AlgoOptionX has separate synthetic paper and Dhan research workflows. The
research execution policy accepts PAPER only; this skill neither enables live
orders nor establishes how a person uses research outside the application.

Canonical instructions are in `AGENTS.md`; see
`src/algooptionx/research/execution/policy.py`,
`docs/architecture/decisions/0001-simulator-first.md` and the native
`.agents/skills/options-domain-analysis/SKILL.md` contract. Reference those
sources rather than treating this domain note as another governance policy.

Market structure, initial-balance/day typing, multi-timeframe structure and
regime heuristics already exist in `src/algooptionx/research/signals/market_structure.py`
and `src/algooptionx/research/signals/regime.py`. Their existence does not
establish predictive accuracy, profitability or that every strategy consumes
every available check. Recheck these facts when those modules, execution
policy or architecture changes; this baseline note is not permanent evidence.

The references below preserve external research and practitioner claims.
They have not been independently revalidated by this Phase 0 documentation
correction. Treat their strength and applicability as NOT VERIFIED unless
specific evidence is supplied; do not infer trader expertise or market edge.

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
   The references recommend contextual confirmation; that is a research
   hypothesis, not verified profitability for this application. Don't build a pattern detector that fires trades by
   itself.

## Historical research notes — claims require source verification

| Referenced area | Historical description; recheck against current source | External research interpretation; not application validation |
|---|---|---|
| `signals/sentiment.py` `bias_lean` | PCR &gt; 1.2 = bullish, &lt; 0.8 = bearish, static threshold | **Oversimplified.** Professionals weight PCR *trend/velocity*, restrict to near-ATM strikes (whole-chain PCR is hedge-contaminated), and distrust `pcr_volume` specifically near/on expiry (mostly position-rolling noise there). See `oi-pcr-institutional-practice.md` §1. |
| `signals/sentiment.py` `max_pain()` | Presented as a level price gravitates toward | **Overstated if framed as predictive.** Evidence is genuinely mixed; the more credible modern explanation for any real pinning effect is dealer gamma-hedging flow (GEX), not "writers minimizing payout." Reframe as one weak input, not a target. See §2. |
| `signals/sentiment.py` `top_call_oi_strikes` / `top_put_oi_strikes` | Top-N strikes by raw OI, used as S/R | **Reasonable baseline**, but missing OI *freshness* (today's change vs. static level) and a volume-to-OI ratio filter that distinguishes fresh conviction from stale walls or an unwinding wall about to break. See §3. |
| Trading Setup page | Raw candlestick charts, zero pattern detection | **Justified gap to fill**, but keep expectations calibrated -- patterns have weak-to-zero edge in isolation per the academic literature. Build detection as confirmation-only. See `candlestick-patterns.md`. |
| `signals/hlc_strategy.py` trade plan (35-pt threshold, 20-pt/day target, previous-5-min-candle stop) | Same numbers regardless of time of day or day of week | **Structurally sound on theta, underweights gamma.** The rule's edge (selling into a Seller-dominated leg) is theta-consistent. Its main blind spot: gamma risk is concentrated in specific windows (first 15-30 min after open, last 1-2 hours before close, and especially the Tuesday expiry session) that the current rule doesn't distinguish. See `greeks-iv-timing.md` §2-3. |
| Anywhere with day-of-week logic | -- | **Check for stale "Thursday = expiry" assumptions.** NIFTY weekly expiry moved to Tuesday effective 1 Sept 2025 (SEBI circular). |
| `signals/trend.py`, `market_structure.py`, `regime.py` | Trend, structure, day typing and regime heuristics are implemented | VERIFIED source capability; strategy integration and statistical reliability must be evaluated separately. See the current-source note above. |
| Any future "Smart Money Concepts" / "ICT" style feature (order blocks, Fair Value Gaps, liquidity sweeps) | Not built | **Don't build these.** The "evidence" for this cluster beyond basic swing/BOS/CHoCH mechanics is marketing-sourced, same tier as the candlestick folklore already flagged. See `market-structure-trend.md`. |

## What this skill is not

Not a general options-trading tutorial, and not exhaustive -- it's scoped to
what's directly decision-relevant for *this* analyzer's rule set. If a future
question falls outside what the reference files cover, say so and research it
fresh rather than stretching an existing finding to fit.

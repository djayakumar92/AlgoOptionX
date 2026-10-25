# StrikeLine AI — Migration Requirements (Validated)

**Date:** 2026-09-02
**Source:** Requirement document supplied by the user ("STRIKELINE AI — Institutional-Grade NIFTY Options Market Intelligence & Trading Analyzer", v1.0), reproduced in full at the bottom of this file.
**Purpose:** Turn that document into an actionable migration plan for the existing Dhan analyzer at `D:\Development\Dhan`, after checking its claims and assumptions against the real, currently-working codebase.

---

## 1. Plain-language summary

The supplied document describes an ambitious, full "AI trading analyst" platform. Most of its *feature* ideas are a natural extension of what's already built. But it also assumes a completely different technology stack, and it skips over a couple of things this project already knows are unresolved. Before this becomes a real plan, three things need to be settled:

1. **Tech stack — decided and hardened, see §2.** No migration. Keep React + FastAPI + SQLite. The document's Angular/PostgreSQL/Redis/Celery stack is for a hosted, multi-user product — this is a single-user local app, and that stack solves problems it doesn't have. WAL mode turned out to already be on; a retention/pruning policy for the fast-growing option-chain poll log is now in place too.
2. **Two of your own trading-rule questions are still open.** Which option leg to sell on a "Strong Bullish/Bearish" day is still an unconfirmed guess, not something you've validated against real results. Building the document's "AI Analyst", "Scenario Engine" and "Buy/Sell-Side Analyzer" layers on top of an unvalidated rule risks polishing a rule that might be wrong. Recommendation: validate a few weeks of real Journal outcomes first.
3. **The document is missing your own project's biggest known risks.** Earlier research for this project (saved as a project skill) found two things this document never mentions: risk should adjust by time of day and by expiry day, and — the strongest single finding — nothing checked whether a given day is actually behaving like the range-bound day the HLC trade plan assumes. The second one is now built (§3, Market Structure page); the first is still open, worth folding into the Risk Engine whenever that phase starts.

Everything else below is detail for the record. Section 3 is the important one if you only want the short version.

---

## 2. Finalized tech stack decision

| Document says (§57–59) | Actually running today | Decision |
|---|---|---|
| Frontend: Angular, RxJS/Signals, SCSS | React + TypeScript, Vite build, plain CSS | **Keep React.** No functional gap — charts, pages, and polling already work. A rewrite would cost weeks for zero new capability. |
| Backend: Python, FastAPI | Python, FastAPI | **Keep FastAPI.** Already matches the document; no change either way. |
| Database: PostgreSQL | SQLite (no server, no ORM) | **Keep SQLite, hardened.** See reasoning below. |
| Caching/queue: Redis, Celery | Plain Python threads (`worker.py`, `hlc_worker.py`) | **Skip both.** See reasoning below. |
| Real-time: Dhan WebSocket → Collector → Redis → WebSocket → Frontend | Dhan REST polling every ~3.5s; a WebSocket LTP listener exists in the code but isn't wired into anything yet | **No change for now.** Polling already covers the Live page; revisit only if a future feature genuinely needs sub-second push. |
| Charting: TradingView Lightweight Charts | Already in use | Matches — no change. |
| Delivery: "Web application" | Local desktop app — double-click `.bat`, no server, no login, no hosting | **Stays a local desktop app.** Nothing in the feature list requires hosting or multi-user accounts. |

### Reasoning per component

**Database — why SQLite stays, with two hardening changes.**
The case *for* Postgres: the plan ahead includes years of backtesting, market replay, and historical pattern search, and this project already hit one real concurrency bug (a lock had to be added because two threads touched the database at the same time). More background jobs (backtest runs, replay, daily reports) means more of that kind of contention.

The case *against*: Postgres means installing and keeping a database **server** running in the background — a real regression from "double-click and it works" for a single user with zero coding knowledge. SQLite can absorb the coming load without that cost:

1. **SQLite WAL mode** — turned out to already be on (`storage/db.py`), so no change was needed there; it already lets reads and writes happen at the same time instead of blocking each other, addressing the kind of contention the earlier concurrency bug hit.
2. **Retention/pruning policy** for `option_chain_snapshot` (had grown to ~5.4 million rows, ~11 days of polling, with no cleanup ever) — **done**: prunes anything older than `settings.toml [storage] retention_days` (default 14) once at every startup.

**Postgres is not ruled out forever** — if backtesting/replay is built and genuinely can't keep up on hardened SQLite, that's the trigger to revisit. Not before.

**Redis + Celery — why both are skipped.**
Both solve coordination problems that come from having multiple servers or multiple processes talking to each other. This is one process on one PC — there's nothing to coordinate across. For long-running jobs (backtest, replay), the plan is a small **job-status table** (start time, progress, done/failed) read by the frontend, built on the same threading approach already in use — not a message-queue system.

---

## 3. Feature-by-feature status against the document

Legend: ✅ Built and live-verified · 🟡 Partially built · ⬜ Not built yet

| Doc section | Feature | Status | Notes |
|---|---|---|---|
| §3, §14–16 | Option chain, PCR, Max Pain, OI long/short buildup | ✅ | `signals/sentiment.py`, `signals/oi_behavior.py` |
| §18, §21 | VWAP, MA crossover, ADX, RSI, ROC, IV Rank | ✅ | `signals/trend.py`, `signals/momentum.py` |
| §14, §19 | Per-strike Greeks (delta/gamma/theta/vega) captured | ✅ | Already stored in `option_chain_snapshot`; now also surfaced live per-strike (IV/delta/volume/bid-ask) on the Option Intelligence page — still no gamma-risk/theta-environment *reasoning* layer on top |
| §66–68 | OI-over-time chart, multi-pane candlestick charts, option chain UI | ✅ | Live page + Trading Setup page, `lightweight-charts` |
| §25, §30 | Entry/Stop/Target trade plan | ✅ | HLC-based `build_trade_plan()` — this is more precise than the document's generic §22 "combine.py"-style bias/entry/stop, which is an older, separate, cruder mechanism still present alongside it |
| §43–44 | Trade journal with automatic grading | ✅ | `journal_grading.py`, replays real 5-min candles against the plan, `/journal` page |
| §51 | No-Trade detection | ✅ | Sit-out days already produce a `NO_TRADE` journal row with a reason |
| §8 | Market Regime classification (Trending/Range/Breakout/etc.) | 🟡 | Built as evidence-grounded Initial-Balance day-typing (Non-Trend/Normal-Variation/Trend/Neutral, Steidlmayer/Market Profile) rather than the document's fictional 11-regime list — see `signals/market_structure.py`, `/market-structure` page. Doc's Expiry-Distortion/News-Event-Risk regimes need external calendar data, not built |
| §9 | Market Structure (HH/HL/LH/LL, BOS, CHoCH) | ✅ | `signals/market_structure.py` — N-bar fractal swings with an ATR-scaled noise filter, BOS/CHoCH derived from the swing sequence, plus real previous-day/previous-week high-low. Deliberately does **not** implement order blocks/Fair Value Gaps/ICT-style liquidity sweeps — the domain-research skill found no real evidence behind that cluster. 16 new regression tests, `tests/test_market_structure.py` |
| §10 | Multi-timeframe (1D→1M) structure analysis | ⬜ | Not built — current charts show one timeframe at a time, no cross-timeframe reasoning |
| §11–13 | Institutional S/R zones with a 0–100 strength score | 🟡 | `signals/support_resistance.py` — real zones clustered from swing points, previous day/week levels, HLC bands, VWAP, classic pivots, and fresh/stale OI walls, scored 0–100 with the doc's own Institutional/Strong/Moderate/Weak/Ignore bands. Not included: volume profile, anchored VWAP, Fibonacci (see the module's docstring for why). "Reversal Intelligence" specifically (§13, explaining *why* a level held/failed) still not built |
| §16 | OI Wall Detection | ✅ | `signals/oi_walls.py` — real, freshness/volume-weighted (per the domain-research skill's §3), feeds both the S/R zones and the Option Intelligence page directly |
| §17 | Seller-pressure visualization (option "battlefield") | ⬜ | Not built |
| §22–26 | AI Analyst / LLM reasoning layer, structured market summary, Scenario Engine | ⬜ | Not built — this is the part that needs the unresolved rule questions (§2 above) settled first |
| §31–32 | Risk Engine, Daily Risk Guard, position sizing from account size | ✅ | `signals/risk.py`, `/api/risk`, real Risk & Position Sizing panel on Trade Setups — capital/risk-% based sizing (real lot size read live from DhanHQ's own instrument file, not guessed), folds in the domain-research time-of-day/expiry-day gamma finding (§4 above) as a position-size multiplier. Daily Risk Guard is honestly scoped to the most recently *graded* day (this app has no live intraday P&L feed to track a running total against, by design) |
| §31–32 (note) | Trade plan itself still sizes by fixed points/day, not capital-based quantity | — | The Risk Engine sizes a *hypothetical* position by stop distance; it doesn't yet feed a quantity back into `hlc_strategy.py`'s trade plan output — a natural next connection, not done in this pass |
| §34 | Event calendar (RBI, Budget, Fed, expiry) | ⬜ | Not built |
| §36–37 | Historical similarity search, Market Memory | ⬜ | Not built |
| §38–42 | Self-learning loop, prediction tracking/error analysis, Mistake Intelligence, AI vs Human decision split | ⬜ | Not built — Journal currently grades outcome only, not *why* a prediction was right/wrong, and doesn't separate "AI said wait, you entered anyway" |
| §47 | Backtesting engine | 🟡 | `signals/backtest_stats.py` + `api/backtest_worker.py`, real `/backtest` page — runs the real HLC rule across a date range (reuses the existing single-day journal-backfill mechanism per day, skips already-graded days), real Net P&L/win rate/profit factor/expectancy/avg-R/max-drawdown/largest-win-loss/consecutive-losses. Sharpe/Sortino deliberately not computed (no honest basis for a risk-free rate/return period yet). **Known real limitation, surfaced in the UI**: every day in a run prices against the *currently* tracked weekly expiry, not the expiry actually active on that historical date — accurate for roughly the current expiry week, increasingly wrong further back. Position sizing/slippage/brokerage from the doc's own field list not incorporated |
| §48 | Walk-forward validation | ⬜ | Not built — needs the expiry-accuracy limitation above resolved first, otherwise a train/test split would inherit the same mispricing on both sides |
| §49 | Market Replay (candle-by-candle, no future data leakage) | ⬜ | Not built |
| §50, §62–64 | AI Training Lab, model versioning/governance, drift detection, confidence calibration | ⬜ | Not built — presumes an AI Analyst layer that doesn't exist yet |
| §54–55 | AI Chat Analyst, specialized AI "skills" orchestration | ⬜ | Not built |
| §72–75 | Auto-generated daily/pre-market/post-market reports | ⬜ | Not built |
| §79 | Formal data-quality gate before analysis runs | 🟡 | Some resilience exists (retry on empty Dhan responses, broad exception guards so a worker thread can't die silently) but not a structured pre-flight checklist |

---

## 4. Two things this project already flagged that the document doesn't mention

Both come from the project's own domain-research (`.claude/skills/nifty-options-domain-knowledge/`), not from outside opinion:

- **Time-of-day / expiry-day risk adjustment** was identified as the single highest-value improvement to the existing trade rule — gamma risk concentrates in the first 15–30 minutes after open, the last hour before close, and especially the Tuesday weekly-expiry session. The document's §33 "Market Session Intelligence" gestures at session stages but never connects it to risk sizing or the stop rule the way the research did. Worth building into the Risk Engine (§31) whenever that phase starts.
- **Retail oversimplifications already in the codebase**: the static PCR>1.2/<0.8 threshold and "max pain as a magnet" framing (both in `signals/sentiment.py`) are flagged by the same research as weaker than PCR *trend* and near-ATM banding. The document's §14–17 option-intelligence sections would be a natural place to fix this while building them out, rather than carrying the simplification forward into a bigger system.

---

## 5. Still-open questions from this project (unaffected by this new document)

These predate this document and block trusting any "AI Analyst"/Scenario layer built on top of the trade rule:

1. Which leg to sell on each combined-signal day (Strong Bullish/Bearish/Indecision) is an unconfirmed inference, not a rule the user has verified against real outcomes.
2. Whether the 35-point buyer/seller-domination threshold should flex with volatility, or stay fixed — never answered.

**Recommendation:** resolve both against a real stretch of Journal history before investing in §22–26 (AI Analyst / Scenario Engine) — otherwise a fluent-sounding AI narrative would just be dressing up an unvalidated rule.

---

## 6. Suggested phase order (adapted from the document's §83–89, on the existing stack)

1. ~~Database hardening: enable SQLite WAL mode + retention/pruning for `option_chain_snapshot`~~ — **done.** WAL mode was already on. Added a 14-day retention policy (`settings.toml [storage] retention_days`), pruned once at every startup (`storage/db.py::connect`, `storage/repository.py::prune_option_chain_snapshots`). The data-quality gate (§79) is still outstanding.
2. ~~Validate the two open rule questions (§5 above) against real Journal history~~ — **checked, still open.** As of 2026-09-02 there are only 2 real graded trading days in the Journal (one Strong Bearish day, both legs stopped out; one correctly-sat-out Indecision day) — nowhere near enough sample to validate either question. The 35-point threshold question specifically can't be answered from Journal history at all, even with more days; it needs a backtest. Revisit once more real days accumulate, or prioritize backtesting (§7 below) to answer it directly.
3. ~~Market Structure + Regime classification (§8–10)~~ — **done** for the single-timeframe case: swings, BOS/CHoCH, IB day-typing, previous day/week levels, all real. Multi-timeframe alignment (§10) still not built — deferred, see §3's table above.
4. ~~Scored Support/Resistance zones (§11–13), OI wall (§16)~~ — **done.** Seller-pressure visualization (§17) and Reversal Intelligence (§13) still not built.
5. ~~Risk Engine + Daily Risk Guard (§31–32)~~ — **done**, folding in the time-of-day/expiry finding from §4 above as a position-size multiplier. Not yet done: feeding a sized quantity back into the trade plan itself, and the Daily Risk Guard is scoped to the most recently graded day rather than live intraday tracking (this app has no live P&L feed to track against, by design).
6. AI Analyst / Scenario Engine (§22–26) — only once 2–5 are in place, since this is the layer that narrates over everything below it.
7. ~~Backtesting (§47)~~ — **done**, with one real limitation surfaced rather than hidden: every day in a range prices against the *current* tracked expiry, not the one actually active historically, so results are only trustworthy for roughly the current expiry week. Fixing that (resolving the real historical expiry per day) plus Walk-Forward Validation (§48) and Market Replay (§49) are still open — this is now the natural place to finally get real evidence on the still-open threshold question (§5/§2 above), once ranges can safely span more than one expiry cycle.
8. Learning loop, Mistake Intelligence, historical similarity, reports, chat interface (§38–42, §54, §72–75) — polish/depth once the above is trustworthy.

---

## Appendix: Original requirement document (verbatim, as supplied)

# STRIKELINE AI
## Institutional-Grade NIFTY Options Market Intelligence & Trading Analyzer
**Product Type:** AI-powered NIFTY Options Analysis & Decision Support Platform
**Primary Market:** NSE NIFTY 50 Index Options
**Data Provider:** DhanHQ
**Trading Mode:** Analysis and manual execution only
**Primary User:** Advanced options trader / market analyst
**Platforms:** Web application / Desktop browser
**Status:** Product Requirements & Technical Specification
**Version:** 1.0
---
# 1. Product Vision
StrikeLine AI is an advanced NIFTY options market intelligence platform designed to understand the market like an experienced options trader.
The system continuously analyzes:
* NIFTY spot/index structure
* Futures data
* Option chain
* Call/Put OI
* OI changes
* Volume
* Price action
* VWAP
* Volatility
* IV
* Greeks
* Market breadth
* Multi-timeframe structure
* Support and resistance
* Liquidity
* Previous market reactions
* Historical behavior
* Trading journal outcomes
The AI combines these inputs to answer five critical questions:
### 1. Where is the market?
### 2. Where are the important support and resistance zones?
### 3. What is the most probable market scenario?
### 4. If a trade exists, where is the best entry, stop and target?
### 5. What did previous similar market structures teach us?
The objective is **not to predict the market with certainty**.
The objective is to continuously improve the quality of market analysis, probability estimation, trade selection and risk management.
---
# 2. Product Philosophy
StrikeLine AI must behave like a disciplined professional trading analyst rather than a signal generator.
The system should:
* Analyze before predicting.
* Explain before recommending.
* Quantify confidence.
* Show supporting evidence.
* Identify conflicting evidence.
* Avoid forcing a trade.
* Prefer NO TRADE when conditions are unclear.
* Track every prediction.
* Compare prediction vs actual outcome.
* Learn from historical outcomes.
* Detect recurring market structures.
* Continuously measure prediction quality.
### Core principle
> **The system should never ask: "How can I generate a trade?"**
It should ask:
> **"Is there a statistically meaningful opportunity right now?"**
If the answer is no:
**NO TRADE**
---
# 3. Existing StrikeLine Foundation
The current application already provides:
* Live NIFTY spot
* Live option chain
* Bullish/Bearish/Neutral bias
* Confidence percentage
* Entry zone
* Stop-loss
* Watch level
* PCR
* Max Pain
* OI analysis
* Long/short buildup
* VWAP
* Moving-average crossover
* ADX
* RSI
* Rate of Change
* IV Rank
* OI-over-time charts
* Multi-pane charts
* HLC strategy
* Journal
* Automatic historical grading
These capabilities should remain and become components of the larger StrikeLine AI architecture.
---
# 4. Product Architecture
The platform should contain the following major engines:
```text
                    ┌────────────────────────┐
                    │      DhanHQ Data       │
                    │ Spot / Futures / Chain │
                    └────────────┬───────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │     Market Data Layer   │
                    │ Normalization / Cache   │
                    └────────────┬───────────┘
                                 │
             ┌───────────────────┼───────────────────┐
             ▼                   ▼                   ▼
      Market Structure      Options Engine      Technical Engine
             │                   │                   │
             └───────────────────┼───────────────────┘
                                 ▼
                    ┌────────────────────────┐
                    │   Market Intelligence  │
                    │         Engine         │
                    └────────────┬───────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
             Scenario Engine             AI Analyst
                    │                         │
                    └────────────┬────────────┘
                                 ▼
                    ┌────────────────────────┐
                    │  Trade Decision Engine │
                    └────────────┬───────────┘
                                 │
             ┌───────────────────┼───────────────────┐
             ▼                   ▼                   ▼
         Entry Plan          Risk Plan          No-Trade
             │                   │                   │
             └───────────────────┼───────────────────┘
                                 ▼
                    ┌────────────────────────┐
                    │     Trade Journal      │
                    └────────────┬───────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │ Learning / Evaluation   │
                    │      Engine             │
                    └────────────┬───────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │ Historical Knowledge DB │
                    └────────────────────────┘
```
---
# 5. Main Application Navigation
## Primary Navigation
### 1. Command Center
### 2. Live Market
### 3. Market Structure
### 4. Option Intelligence
### 5. AI Analyst
### 6. Trade Setups
### 7. Charts
### 8. Scenario Engine
### 9. Backtest
### 10. Journal
### 11. Learning Lab
### 12. Market Replay
### 13. Analytics
### 14. Settings
---
# 6. Command Center
The Command Center is the most important screen.
It should answer the entire day's situation within 10 seconds.
## Header
Display:
* NIFTY Spot
* NIFTY Futures
* Day Change
* Day %
* India VIX
* Market Session
* Time
* Market Regime
* AI Confidence
* Data Health
Example:
```text
NIFTY 25,430.25   +124.60 (+0.49%)
REGIME
Bullish Trend
AI MARKET CONFIDENCE
78%
VIX
14.32
SESSION
Opening / Trend / Midday / Closing
```
---
# 7. AI Market Summary
The AI should generate a structured market summary.
Example:
```text
MARKET VIEW
Primary Bias:
Bullish
Confidence:
78%
Market Structure:
Higher High + Higher Low
Key Support:
25,350 – 25,390
Major Support:
25,280 – 25,320
Resistance:
25,480 – 25,520
Major Resistance:
25,600 – 25,650
Current Position:
Between support and resistance
Market State:
Bullish but extended
Recommendation:
WAIT FOR PULLBACK
Reason:
Price is above VWAP and maintaining higher lows,
but Call OI concentration near 25,500 indicates
potential supply.
```
---
# 8. Market Regime Engine
Before generating a trade signal, StrikeLine must classify the market.
## Regimes
### TRENDING BULLISH
### TRENDING BEARISH
### RANGE
### BREAKOUT
### BREAKDOWN
### REVERSAL
### HIGH VOLATILITY
### LOW VOLATILITY
### EXPIRY DISTORTION
### NEWS / EVENT RISK
### UNCERTAIN
The regime determines which strategies are allowed.
For example:
```text
Trending Market
→ Pullback strategy
→ Breakout continuation
Range Market
→ Support/Resistance reversal
→ Premium selling
Breakout Market
→ Momentum entry
→ Retest entry
Uncertain
→ NO TRADE
```
---
# 9. Market Structure Engine
This is one of the most important components.
The system must understand price structure rather than relying only on indicators.
## Detect
* Higher High
* Higher Low
* Lower High
* Lower Low
* Break of Structure
* Change of Character
* Consolidation
* Range expansion
* Range contraction
* Failed breakout
* Failed breakdown
* Retest
* Rejection
* Liquidity sweep
* Gap
* Opening range
* Previous day high/low
* Previous week high/low
* Previous month high/low
---
# 10. Multi-Timeframe Analysis
The AI should analyze:
### 1D
### 1H
### 30M
### 15M
### 5M
### 3M
### 1M
The system should not allow a 1-minute signal to override a strong higher-timeframe structure without explicitly explaining the conflict.
Example:
```text
Daily: Bullish
1H: Bullish
15M: Bullish
5M: Pullback
1M: Reversal
Overall:
Bullish continuation opportunity
```
---
# 11. Institutional Support & Resistance Engine
Support and resistance should NOT be based on one indicator.
The engine should create **zones**, not single-price lines.
## Sources
### Price Structure
* Previous Day High
* Previous Day Low
* Previous Close
* Weekly High
* Weekly Low
* Monthly High
* Monthly Low
### Price Action
* Multiple rejection points
* Strong reversal candles
* Consolidation bases
* Breakout zones
* Retest zones
### Volume
* Volume profile
* High volume nodes
* Low volume nodes
* Volume spikes
### Options
* Call OI concentration
* Put OI concentration
* OI addition
* OI unwinding
* Volume concentration
* IV concentration
* Gamma concentration
### Technical
* VWAP
* Anchored VWAP
* Fibonacci
* Moving averages
* Pivot levels
---
# 12. Dynamic Support/Resistance Score
Every zone receives a score.
Example:
```text
25,350 – 25,390
Zone Strength: 91/100
Price Rejections       +25
Put OI Support         +22
Volume Support         +15
VWAP                    +10
Previous Day Structure  +12
Fibonacci               +7
Total                   91
```
Classification:
```text
90–100  Institutional Zone
75–89   Strong Zone
60–74   Moderate Zone
40–59   Weak Zone
<40     Ignore
```
---
# 13. Reversal Intelligence
The AI should identify why price reversed at a particular level.
For every important reversal:
```text
LEVEL
25,500
EVENT
Price rejected resistance
EVIDENCE
Call OI:
+18%
Call Volume:
+32%
Price:
Failed to hold 25,500
VWAP:
Below
5M Structure:
Lower High
Momentum:
Bearish divergence
AI Interpretation:
Supply absorption failed.
Call writers defended 25,500.
Reversal Confidence:
84%
```
This creates historical knowledge about important market levels.
---
# 14. Option Chain Intelligence
The option-chain engine should analyze much more than PCR.
## Per strike
Store:
* CE LTP
* PE LTP
* CE Volume
* PE Volume
* CE OI
* PE OI
* CE OI change
* PE OI change
* IV
* Delta
* Gamma
* Theta
* Vega
* Bid
* Ask
* Spread
* Implied volatility change
* Price change
---
# 15. OI Behavior Classification
Each strike should be classified.
### Long Build-Up
Price ↑
OI ↑
### Short Build-Up
Price ↓
OI ↑
### Long Unwinding
Price ↓
OI ↓
### Short Covering
Price ↑
OI ↓
But classification should be contextual rather than blindly formula-based.
Example:
```text
25,500 CE
OI:
+22%
Premium:
+41%
Volume:
Very High
Interpretation:
Aggressive call buying
Potential implication:
Upside breakout risk
```
---
# 16. OI Wall Detection
Detect:
* Call OI wall
* Put OI wall
* OI migration
* OI shift
* New resistance
* New support
* Resistance weakening
* Support weakening
Example:
```text
Previous Resistance
25,500
Current Call OI:
Declining
25,600 Call OI:
Increasing
Interpretation:
Resistance may be migrating upward.
```
---
# 17. Option Seller Intelligence
Create an explicit "Seller Pressure" model.
Example:
```text
CALL SELLER PRESSURE
25,500     ██████████  91
25,550     ████████    76
25,600     █████       52
PUT SELLER PRESSURE
25,400     █████████   84
25,350     ███████     71
25,300     ████        43
```
This helps visualize the option market battlefield.
---
# 18. Volatility Intelligence
Analyze:
* India VIX
* IV Rank
* IV Percentile
* ATM IV
* CE IV
* PE IV
* IV skew
* IV expansion
* IV contraction
* Expiry effect
The AI should answer:
> Is this a premium buying environment or premium selling environment?
---
# 19. Greeks Engine
For relevant strikes calculate:
* Delta
* Gamma
* Theta
* Vega
Also estimate:
* Gamma concentration
* Gamma risk
* Theta decay environment
* Directional sensitivity
Example:
```text
MARKET CONDITION
High Gamma
+ Near ATM
+ Expiry Day
+ Low liquidity
Risk:
Very high premium sensitivity
Preferred:
Smaller position / faster confirmation
```
---
# 20. Price Action Engine
Detect:
* Engulfing
* Pin bars
* Rejection
* Breakout candles
* Inside bars
* NR7
* Opening range breakout
* Failed breakout
* Failed breakdown
* Long wick rejection
* Momentum expansion
* Volume climax
Patterns should never generate trades alone.
They become evidence within the larger decision model.
---
# 21. Indicator Engine
Maintain:
* VWAP
* Anchored VWAP
* EMA
* SMA
* RSI
* MACD
* ADX
* ATR
* ROC
* Bollinger Bands
* Supertrend
Indicators should be categorized:
```text
Trend
Momentum
Volatility
Volume
Structure
```
Avoid creating dozens of independent signals that all measure the same underlying phenomenon.
---
# 22. AI Analyst
The AI Analyst is the core intelligence layer.
It should receive structured market data rather than raw unprocessed data wherever possible.
Input:
```text
Market Snapshot
+
Market Structure
+
Option Chain
+
OI Behavior
+
Price Action
+
Technical Indicators
+
Volatility
+
Historical Similarity
+
Journal Knowledge
+
Current Trading Session
```
---
# 23. AI Analyst Response Format
Every AI analysis should have a fixed structure.
## MARKET STATE
```text
Bullish Trend
```
## CONFIDENCE
```text
78%
```
## STRUCTURE
```text
Higher highs and higher lows.
Price above VWAP.
```
## SUPPORT
```text
25,350–25,390
Strength: 91
```
## RESISTANCE
```text
25,500–25,540
Strength: 87
```
## EXPECTED SCENARIOS
### Scenario A — Bullish
Probability: 62%
Condition:
5M close above 25,500
Target:
25,560 → 25,620
### Scenario B — Range
Probability: 24%
Condition:
Repeated rejection at 25,500
### Scenario C — Bearish
Probability: 14%
Condition:
Break below 25,350
````
---
# 24. Scenario Engine
Do not generate only one prediction.
Generate multiple scenarios.
Example:
```text
CURRENT PRICE
25,430
        25,620
          ↑
     Bullish Target
          │
     25,500 Resistance
          │
     Current 25,430
          │
     25,390 Support
          │
     25,350 Major Support
          ↓
      Bearish Target
````
Each scenario contains:
* Trigger
* Confirmation
* Entry
* Stop
* Target
* Probability
* Risk/reward
* Invalidating condition
---
# 25. Entry Intelligence
The system should distinguish:
### Early Entry
Higher risk / higher reward
### Confirmation Entry
Lower risk / reduced reward
### Retest Entry
Preferred when breakout occurs
### Pullback Entry
Preferred in trends
### Reversal Entry
Requires strong confirmation
The AI should explicitly tell the user:
```text
DO NOT ENTER NOW
Wait for:
5M close above 25,500
Then:
Wait for retest
Preferred entry:
25,505–25,525
```
---
# 26. Trade Setup Score
Every setup receives a score.
Example:
```text
TRADE QUALITY
Trend Alignment       18/20
Market Structure      18/20
Option Confirmation   16/20
Momentum              14/15
Volume                10/15
Risk/Reward             9/10
TOTAL                 85/100
```
Classification:
```text
90–100  A+
80–89   A
70–79   B
60–69   C
<60     NO TRADE
```
---
# 27. Entry Checklist
Before showing a trade, the engine should evaluate:
```text
☑ Higher timeframe aligned
☑ Market structure confirmed
☑ Support/resistance identified
☑ Option chain confirms
☑ OI behavior confirms
☑ Volume confirms
☑ Momentum confirms
☑ Volatility acceptable
☑ Risk/reward acceptable
☑ Entry trigger available
☑ Stop-loss logical
☑ Target logical
☑ No major event risk
```
If critical conditions fail:
**NO TRADE**
---
# 28. Buy-Side Analyzer
For option buying:
Analyze:
* Direction
* Momentum
* Gamma
* IV
* Theta
* Premium expansion
* Breakout probability
* Liquidity
* Spread
* Time to expiry
Output:
```text
BUY CE
Strike:
25,500 CE
Entry:
₹145–₹155
Trigger:
NIFTY 5M close > 25,500
Stop:
Structure-based
Targets:
₹180
₹210
Setup Score:
87/100
Risk:
Medium
Reason:
Momentum + breakout + call OI reduction.
```
---
# 29. Sell-Side Analyzer
For option selling:
Evaluate:
* Strong support/resistance
* IV
* Theta
* OI
* Range probability
* Expected move
* Distance from spot
* Event risk
* Gamma risk
* Expiry proximity
Example:
```text
SELL PE
Strike:
25,300 PE
Zone:
Strong Put support
Premium:
₹78
Entry:
₹75–₹82
Invalidation:
NIFTY < 25,300
Target:
₹40
Setup Score:
83/100
```
---
# 30. Trade Plan
Every proposed setup should contain:
```text
TRADE TYPE
Option Buy / Option Sell
DIRECTION
Bullish / Bearish
Instrument
NIFTY 25,500 CE
ENTRY ZONE
₹145–₹155
CONFIRMATION
NIFTY above 25,500
STOP
Structure-based
TARGET 1
₹180
TARGET 2
₹210
EXPECTED R:R
1:2.4
SETUP SCORE
87
CONFIDENCE
82%
INVALIDATION
5M close below 25,450
TIME HORIZON
Intraday
```
---
# 31. Risk Engine
The analyzer must calculate risk before recommending any setup.
Inputs:
* Account size
* Maximum risk per trade
* Maximum daily loss
* Position size
* Premium
* Stop distance
* Quantity
* Slippage
* Brokerage/charges
Example:
```text
Capital: ₹5,00,000
Maximum Risk:
1% = ₹5,000
Risk per option:
₹25
Maximum quantity:
200 units
```
The system should never recommend position sizing without considering stop distance and risk.
---
# 32. Daily Risk Guard
Display:
```text
DAILY RISK STATUS
Daily Loss Limit:
₹10,000
Current Realized:
₹3,200
Remaining Risk:
₹6,800
```
When exceeded:
```text
TRADING LOCK
Daily risk limit reached.
Recommendation:
STOP TRADING
```
The application should not place trades; this is a decision-support safeguard.
---
# 33. Market Session Intelligence
Classify session stages:
### 09:15–09:30
Opening volatility
### 09:30–10:30
Opening structure formation
### 10:30–12:00
Trend / range development
### 12:00–14:00
Low-volatility / consolidation possibility
### 14:00–15:00
Expansion / positioning
### 15:00–15:30
Expiry / closing dynamics
The exact behavior should be learned statistically from historical data rather than hardcoded as a trading rule.
---
# 34. Event Awareness
Maintain an event calendar for:
* RBI policy
* Union Budget
* Fed events
* CPI
* Inflation
* Major global market events
* Elections
* Major geopolitical events
* NSE expiry
* Special trading sessions
Event risk should modify confidence rather than automatically predict direction.
---
# 35. AI Confidence Model
Confidence must not be arbitrary.
Example:
```text
Market Structure      25%
Options Structure     20%
Price Action          15%
Trend                  15%
Momentum               10%
Volatility              5%
Historical Similarity  10%
```
Output:
```text
Overall Confidence = 81%
```
The system must also show:
```text
Confidence Drivers
+
Confidence Risks
```
Example:
```text
Confidence increased because:
+ Higher timeframe bullish
+ Put OI support
+ VWAP support
Confidence reduced because:
- Resistance nearby
- IV elevated
- Volume declining
```
---
# 36. Historical Similarity Engine
This is a major differentiator.
The system should search historical data for similar market structures.
Example:
```text
CURRENT STRUCTURE
Bullish trend
+
Price near resistance
+
Call OI unwinding
+
High volume
+
VWAP support
```
Historical matches:
```text
Match #1 — 82%
Match #2 — 79%
Match #3 — 77%
Match #4 — 74%
```
Then:
```text
Historical Outcome
Continuation:
68%
Breakout:
21%
Reversal:
11%
```
This becomes evidence for the scenario engine.
---
# 37. Market Memory
StrikeLine should remember important market events.
For example:
```text
25,500
Historically observed:
14 tests
Successful resistance:
8
Breakouts:
4
False breakouts:
2
Average rejection:
47 points
```
The AI can then reason:
> "25,500 has historically acted as a strong supply zone. However, current Call OI is declining and price is holding above VWAP, so resistance strength is weakening."
This is much more useful than simply saying:
> "25,500 is resistance."
---
# 38. Self-Learning Architecture
Important:
The AI should **not automatically rewrite its own trading strategy based on a few wins/losses**.
Instead use controlled learning.
```text
Market Data
     ↓
Prediction
     ↓
Actual Outcome
     ↓
Error Analysis
     ↓
Pattern Database
     ↓
Performance Evaluation
     ↓
Candidate Model
     ↓
Backtest
     ↓
Validation
     ↓
Human Approval
     ↓
Production Model
```
This prevents the system from becoming unstable.
---
# 39. Prediction Tracking
Every AI prediction must be stored.
Example:
```text
Prediction ID:
SL-20260902-001
Time:
10:42:13
NIFTY:
25,438
Bias:
Bullish
Confidence:
78%
Support:
25,350
Resistance:
25,500
Scenario:
Breakout
Expected:
25,550
Actual:
25,563
Result:
Correct
```
---
# 40. Prediction Error Analysis
The AI should learn not only from wrong trades but from wrong reasoning.
Example:
```text
Prediction:
Bullish continuation
Actual:
Bearish reversal
Why?
Call OI was interpreted as resistance,
but actual behavior represented short covering.
Learning:
OI increase/decrease alone was insufficient.
Required confirmation:
Premium + OI + underlying price relationship.
```
This is the type of learning that will improve the analyzer.
---
# 41. Mistake Intelligence
Create a dedicated page:
## AI Mistakes
Categories:
* Wrong direction
* Late entry
* Early entry
* False breakout
* False breakdown
* Wrong support
* Wrong resistance
* OI misinterpretation
* Volatility misinterpretation
* Momentum failure
* Event impact
* Stop too tight
* Target unrealistic
* No-trade failure
Dashboard:
```text
MOST COMMON AI ERRORS
False Breakout       27%
Late Entry           21%
OI Interpretation    18%
Weak Resistance      12%
Volatility            9%
Other                13%
```
---
# 42. Human Trading Mistake Analysis
The journal should separately analyze:
### AI Decision
versus
### Human Decision
This is critical.
Example:
```text
AI:
WAIT FOR RETEST
Trader:
Entered immediately
Result:
Stop Loss
Classification:
Human execution deviation
```
This prevents blaming the strategy for execution mistakes.
---
# 43. Journal 2.0
The current journal already grades historical plans against actual 5-minute candles.
Upgrade it into a complete trading intelligence system.
Each trade stores:
* Date
* Time
* Market regime
* Spot
* Strike
* CE/PE
* Buy/Sell
* Entry
* Stop
* Target
* Actual exit
* P&L
* R multiple
* AI confidence
* Setup score
* Market structure
* Support
* Resistance
* OI state
* IV
* Greeks
* Reason
* Screenshot
* Human decision
* AI decision
* Outcome
* Mistake classification
---
# 44. Journal Analytics
Display:
```text
Total Trades
Win Rate
Loss Rate
Average Win
Average Loss
Profit Factor
Expectancy
Maximum Drawdown
Average R
Best Setup
Worst Setup
Best Time
Worst Time
Best Market Regime
Worst Market Regime
```
---
# 45. Strategy Performance Matrix
Example:
| Market Regime | Trades | Win Rate | Avg R |
| ------------- | -----: | -------: | ----: |
| Bull Trend    |     48 |      71% | +0.82 |
| Bear Trend    |     42 |      69% | +0.74 |
| Range         |     61 |      57% | +0.31 |
| Breakout      |     31 |      74% | +0.91 |
| Reversal      |     29 |      48% | -0.12 |
This tells you where the strategy actually works.
---
# 46. Strategy Discovery
The platform should eventually discover:
```text
Best setup:
Bullish pullback + Put OI support + VWAP
Win rate:
76%
Sample:
84 trades
Average R:
+0.92
```
But it must display sample size and statistical confidence.
Never say:
> "76% accurate"
without showing:
> "76% across 84 historical observations."
---
# 47. Backtesting Engine
A full historical backtest is mandatory before trusting the AI.
The current application does not yet have multi-day backtesting.
Backtest capabilities:
* Date range
* Strategy
* Timeframe
* Entry rule
* Exit rule
* Stop
* Target
* Slippage
* Brokerage
* Position sizing
Output:
```text
Net P&L
Win Rate
Profit Factor
Expectancy
Max Drawdown
Sharpe
Sortino
Average R
Largest Win
Largest Loss
Consecutive Losses
```
---
# 48. Walk-Forward Validation
Avoid training and testing on the same historical period.
Use:
```text
Training
↓
Validation
↓
Testing
↓
Forward testing
```
Example:
```text
2022–2024
Training
2025
Validation
2026
Out-of-sample test
```
This reduces overfitting.
---
# 49. Market Replay
Create a professional replay engine.
User selects:
```text
Date:
2026-08-21
Time:
09:15
```
Then the market starts replaying candle by candle.
The AI sees only information that would have been available at that historical moment.
This is extremely important.
The AI must not receive future data during historical replay.
---
# 50. AI Training Lab
Create a dedicated environment where the user can evaluate the AI.
Features:
### Prediction Accuracy
### Direction Accuracy
### Entry Accuracy
### Support Accuracy
### Resistance Accuracy
### Scenario Accuracy
### Stop Quality
### Target Quality
### No-Trade Accuracy
---
# 51. No-Trade Intelligence
One of the most important features.
The system should explicitly detect:
```text
NO TRADE
Reason:
Conflicting signals
Trend:
Bullish
Options:
Bearish
Price action:
Neutral
Resistance:
Very close
Risk/Reward:
Poor
```
A professional system should be rewarded for correctly avoiding bad trades.
---
# 52. Trade Opportunity Ranking
When multiple setups exist:
```text
OPPORTUNITIES
1. NIFTY 25,500 CE BUY
Score: 88
Confidence: 84%
Risk: Medium
2. 25,300 PE SELL
Score: 81
Confidence: 78%
Risk: Medium
3. 25,500 CE SELL
Score: 62
Confidence: 60%
Risk: High
```
Show only the top 1–3 opportunities.
Avoid signal overload.
---
# 53. AI Explainability
Every AI recommendation must answer:
### WHY?
### WHAT CONFIRMS IT?
### WHAT INVALIDATES IT?
### WHAT CAN GO WRONG?
Example:
```text
WHY BULLISH?
1. Higher-timeframe structure bullish
2. NIFTY above VWAP
3. Put OI support increasing
4. Call OI unwinding
5. Momentum positive
WHAT CAN INVALIDATE?
5M close below 25,390
```
---
# 54. AI Chat Analyst
Add an AI conversational interface.
User can ask:
> Why is 25,500 important?
AI:
> 25,500 is currently a strong resistance zone because...
User:
> What happens if 25,500 breaks?
AI:
> The bullish breakout scenario becomes active...
User:
> Is CE buying better or PE selling?
AI:
> Based on current IV, gamma, trend and expected movement...
The AI must answer from current structured market state rather than generic financial knowledge.
---
# 55. AI Skill System
Instead of one giant prompt, create specialized AI skills.
### Skill 1
Market Structure Analyst
### Skill 2
Price Action Analyst
### Skill 3
Option Chain Analyst
### Skill 4
OI Analyst
### Skill 5
Volatility Analyst
### Skill 6
Greeks Analyst
### Skill 7
Support/Resistance Analyst
### Skill 8
Trend Analyst
### Skill 9
Entry Analyst
### Skill 10
Risk Analyst
### Skill 11
Trade Review Analyst
### Skill 12
Historical Pattern Analyst
### Skill 13
Mistake Analyst
### Skill 14
Session Analyst
### Skill 15
Expiry Analyst
The final AI decision should be produced by an orchestration layer.
---
# 56. AI Decision Pipeline
```text
RAW DATA
   ↓
Data Validation
   ↓
Feature Engineering
   ↓
Market Structure
   ↓
Options Intelligence
   ↓
Technical Analysis
   ↓
Volatility
   ↓
Historical Similarity
   ↓
Scenario Generation
   ↓
Risk Evaluation
   ↓
AI Reasoning
   ↓
Decision Score
   ↓
Trade / Wait / No Trade
```
---
# 57. Data Architecture
Recommended backend:
```text
Python
FastAPI
PostgreSQL
Redis
WebSocket
Celery / background workers
```
Frontend:
```text
Angular
TypeScript
RxJS / Signals
SCSS
TradingView Lightweight Charts
```
---
# 58. Data Storage
Use PostgreSQL tables such as:
```text
market_ticks
spot_candles
futures_candles
option_chain_snapshots
option_candles
option_greeks
oi_snapshots
market_structure
support_resistance_zones
ai_predictions
trade_setups
trade_executions
journal_entries
prediction_outcomes
market_patterns
ai_mistakes
strategy_versions
backtest_runs
backtest_results
market_events
```
---
# 59. Real-Time Data Layer
Dhan data should flow through:
```text
Dhan WebSocket
      ↓
Data Collector
      ↓
Normalizer
      ↓
Redis
      ↓
Feature Engine
      ↓
AI / Signal Engine
      ↓
WebSocket
      ↓
Frontend
```
Do not send every raw tick directly to the LLM.
First aggregate and structure the information.
---
# 60. AI Data Contract
The AI should receive structured JSON similar to:
```json
{
  "timestamp": "...",
  "spot": 25430,
  "trend": {
    "daily": "bullish",
    "hourly": "bullish",
    "15m": "bullish",
    "5m": "pullback"
  },
  "support_zones": [],
  "resistance_zones": [],
  "option_structure": {},
  "oi_behavior": {},
  "volatility": {},
  "momentum": {},
  "volume": {},
  "historical_similarity": [],
  "market_regime": "bullish_trend"
}
```
The LLM should reason over this structured context.
---
# 61. AI Memory Architecture
Use three levels.
## Level 1 — Session Memory
Current day's market.
## Level 2 — Historical Market Memory
Previous market structures and outcomes.
## Level 3 — Strategy Memory
What has historically worked and failed.
Do not allow arbitrary conversational memory to alter trading rules.
---
# 62. Model Governance
Every production strategy/model should have:
```text
Model Version
Training Date
Training Data
Features
Parameters
Backtest Results
Validation Results
Out-of-Sample Results
Approval Status
```
Example:
```text
Model:
SR-v3.2
Status:
Production
Accuracy:
74%
Sample:
1,824 zones
Last validated:
2026-08-28
```
---
# 63. Model Drift Detection
The system should detect when the market behavior changes.
Example:
```text
ALERT
Historical setup win rate:
72%
Last 50 occurrences:
54%
Possible regime change detected.
Recommendation:
Reduce confidence.
```
---
# 64. Confidence Calibration
A prediction of 80% should actually win approximately 80% of the time over a sufficiently large sample under the same outcome definition.
Track:
```text
Predicted 60%
Actual 58%
Predicted 70%
Actual 69%
Predicted 80%
Actual 61%
```
If the AI is overconfident:
```text
AI confidence calibration issue detected.
```
---
# 65. UI/UX Design Direction
The application should look like a modern institutional trading terminal.
Avoid:
* Excessive gradients
* Large decorative cards
* Consumer-fintech style
* Too many bright colors
* Huge text
* Excessive animations
Use:
* Dense information hierarchy
* Dark trading workspace
* Clear typography
* Minimal borders
* Compact cards
* Professional tables
* Strong spacing
* Responsive panels
* Keyboard shortcuts
* Real-time status indicators
---
# 66. Command Center Layout
```text
┌──────────────────────────────────────────────────────────────┐
│ STRIKELINE AI       NIFTY 25,430   +0.49%    VIX 14.32      │
├───────────────┬──────────────────────────────┬───────────────┤
│ MARKET STATE  │          NIFTY CHART         │ AI ANALYST    │
│               │                              │               │
│ BULLISH       │                              │ BIAS 78%      │
│ Trend         │                              │               │
│               │                              │ Support       │
│ Support       │                              │ 25,350        │
│ 25,350        │                              │               │
│ Resistance    │                              │ Resistance    │
│ 25,500        │                              │ 25,500        │
├───────────────┴──────────────────────────────┴───────────────┤
│ OPTION FLOW                                                   │
├──────────────────────────────────────────────────────────────┤
│ CALL OI │ PUT OI │ IV │ VOLUME │ GAMMA │ PCR │ FLOW         │
├──────────────────────────────────────────────────────────────┤
│ TRADE SETUP                                                   │
│ WAIT → BREAKOUT ABOVE 25,500 → BUY CE                        │
└──────────────────────────────────────────────────────────────┘
```
---
# 67. Support/Resistance Visualization
Use horizontal zones rather than lines.
Example:
```text
25,600 ───────────────── Major Resistance
25,500 ═════════════════ Strong Resistance
       ████████████████
25,430 ─────────────── Current Price
25,390 ═══════════════ Support
       ████████████████
25,350 ═══════════════ Major Support
```
Hovering over a zone should show:
```text
Zone Strength: 91/100
Price reactions: 8
Call OI: 1.8M
Put OI: 0.4M
Volume: High
VWAP: Near zone
Historical reversal rate: 71%
```
---
# 68. Option Chain UI
Use a professional chain:
```text
CALLS                    STRIKE                    PUTS
OI   ΔOI   IV   LTP        25,600                  OI   ΔOI   IV
                         ─────────
                         RESISTANCE
                         25,500
                         █ ATM
                         25,400
                         ─────────
                         SUPPORT
```
Highlight:
* ATM
* High OI
* OI changes
* Unusual volume
* Strong zones
* AI-selected strikes
---
# 69. Live Alerts
Alerts should be intelligent rather than indicator spam.
Examples:
```text
BREAKOUT WATCH
NIFTY approaching 25,500.
Resistance strength:
87 → 71
Call OI declining.
Breakout probability increased:
58% → 69%
```
Another:
```text
REVERSAL WARNING
NIFTY rejected 25,500.
5M structure changed.
Call premium rising.
Put OI weakening.
Bearish reversal probability:
64%
```
---
# 70. Alert Categories
* Breakout
* Breakdown
* Reversal
* Support test
* Resistance test
* OI shift
* Unusual option activity
* IV expansion
* IV collapse
* Momentum change
* Regime change
* AI confidence change
* Trade setup
* Risk warning
---
# 71. Unusual Activity Detector
This should be added as a major future feature.
Detect statistically unusual:
* Volume
* OI change
* Premium movement
* IV movement
* Spread
* Trade concentration
Example:
```text
UNUSUAL ACTIVITY
25,500 CE
Volume:
4.2× normal
Premium:
+38%
OI:
+17%
Classification:
Aggressive call buying
```
---
# 72. Daily Market Report
At market close automatically generate:
## NIFTY DAILY INTELLIGENCE REPORT
### Market Summary
### Major Levels
### Best Support
### Best Resistance
### OI Changes
### Major Reversals
### Breakouts
### Failed Breakouts
### AI Predictions
### Correct Predictions
### Wrong Predictions
### Lessons Learned
### Tomorrow's Important Levels
---
# 73. Pre-Market Report
Before market open:
```text
PRE-MARKET INTELLIGENCE
Previous Close
Global Context
Gap Probability
Expected Range
Major Support
Major Resistance
Previous Day Structure
Option Positioning
IV
Potential Scenarios
Risk Events
```
---
# 74. Post-Market Learning Report
Example:
```text
TODAY'S AI REVIEW
Predictions:
7
Correct:
5
Incorrect:
2
Accuracy:
71%
Best Prediction:
Resistance 25,500
Worst Prediction:
Early bullish breakout
Lesson:
The system overestimated breakout probability
when Call OI increased while price remained below
VWAP.
Model adjustment candidate created.
```
---
# 75. Daily Knowledge Generation
After market close:
```text
Market Data
     ↓
Day Reconstruction
     ↓
Important Events
     ↓
AI Predictions
     ↓
Actual Outcome
     ↓
Error Analysis
     ↓
Market Lessons
     ↓
Knowledge Record
```
Example knowledge record:
```text
PATTERN
Strong Call OI + declining premium
near resistance
Historical outcome:
68% rejection
Confidence:
Medium
Sample:
113 occurrences
```
---
# 76. Learning Rules
The system may learn:
* Which support zones hold
* Which resistance zones fail
* Which OI patterns work
* Which indicators are useful in each regime
* Which setups perform better
* Which times are favorable
* Which expiry conditions distort signals
* Where AI is overconfident
The system must NOT learn by blindly increasing/decreasing parameters after every trade.
---
# 77. Strategy Versioning
Every change creates a version.
```text
Strategy V1.0
HLC only
Strategy V2.0
HLC + OI
Strategy V3.0
HLC + OI + Market Structure
Strategy V4.0
AI Scenario Engine
```
Every journal result must be associated with the strategy version used.
---
# 78. Backtest vs Live Separation
Strict architecture:
```text
LIVE DATA
cannot access future data
BACKTEST
historical data only
REPLAY
only data available up to replay timestamp
```
This is essential to prevent look-ahead bias.
---
# 79. Data Quality Engine
Before AI analysis:
```text
☑ Spot data current
☑ Option chain current
☑ Candle complete
☑ No duplicate ticks
☑ No missing critical strikes
☑ Timestamp valid
☑ Market open
☑ Dhan connection healthy
```
If data quality is poor:
```text
AI ANALYSIS PAUSED
Insufficient market data.
```
---
# 80. AI Safety Rules
The AI must never claim:
* Guaranteed profit
* Guaranteed prediction
* Certain market direction
* Risk-free trade
* 100% accuracy
Instead:
```text
Probability
Confidence
Evidence
Invalidation
Risk
Historical sample
```
---
# 81. Performance Metrics for the AI
Measure separately:
### Direction Accuracy
### Scenario Accuracy
### Entry Accuracy
### Support Accuracy
### Resistance Accuracy
### Breakout Accuracy
### Reversal Accuracy
### No-Trade Accuracy
### Stop Accuracy
### Target Accuracy
### Confidence Calibration
---
# 82. Primary Product KPIs
The product should track:
```text
Prediction Accuracy
> 60%
Support Detection Accuracy
> 65%
Resistance Detection Accuracy
> 65%
Scenario Accuracy
> 60%
False Signal Rate
< 30%
No-Trade Precision
> 70%
Confidence Calibration
High
```
These are **development targets**, not guaranteed trading performance.
---
# 83. MVP Scope
## Phase 1 — Foundation
Build:
* Dhan data engine
* Real-time spot
* Futures
* Option chain
* Historical candles
* PostgreSQL
* Redis
* WebSocket
* Existing HLC migration
* Live charts
---
# 84. Phase 2 — Market Intelligence
Build:
* Market regime
* Market structure
* Dynamic support/resistance
* OI intelligence
* Option flow
* IV
* Greeks
* Volume
* Multi-timeframe analysis
---
# 85. Phase 3 — AI Analyst
Build:
* AI market summary
* AI reasoning
* Scenario engine
* Confidence scoring
* Entry intelligence
* Buy analyzer
* Sell analyzer
* No-trade engine
---
# 86. Phase 4 — Journal & Learning
Build:
* Prediction journal
* Trade journal
* Outcome grading
* AI mistake analysis
* Human vs AI analysis
* Daily review
* Historical pattern memory
---
# 87. Phase 5 — Backtesting
Build:
* Historical replay
* Strategy backtesting
* Walk-forward testing
* Monte Carlo analysis
* Strategy comparison
* Performance dashboard
---
# 88. Phase 6 — Advanced Intelligence
Build:
* Historical similarity
* Unusual activity
* Market memory
* Model drift
* Confidence calibration
* Strategy discovery
* Candidate model generation
* Automated daily intelligence report
---
# 89. Recommended Development Priority
The most important components should be developed in this order:
```text
1. Reliable Market Data
        ↓
2. Historical Database
        ↓
3. Market Structure
        ↓
4. Support/Resistance
        ↓
5. Option Intelligence
        ↓
6. Scenario Engine
        ↓
7. Backtesting
        ↓
8. AI Analyst
        ↓
9. Journal
        ↓
10. Learning Engine
```
Do **not** start with the LLM.
The quality of the AI will largely depend on the quality of the underlying market data, features, historical outcomes and evaluation framework.
---
# 90. Institutional-Grade Design Principle
StrikeLine should be built around this hierarchy:
```text
DATA
 ↓
FACTS
 ↓
STRUCTURE
 ↓
CONTEXT
 ↓
SCENARIOS
 ↓
PROBABILITY
 ↓
TRADE SETUP
 ↓
RISK
 ↓
DECISION
 ↓
OUTCOME
 ↓
LEARNING
```
Not:
```text
Indicators
 ↓
AI
 ↓
BUY/SELL
```
---
# 91. Final User Experience
When the trader opens StrikeLine at 9:15 AM, the application should immediately answer:
```text
┌──────────────────────────────────────────┐
│ NIFTY MARKET INTELLIGENCE                │
│                                          │
│ Bias: BULLISH                            │
│ Confidence: 78%                          │
│ Regime: TRENDING                         │
│                                          │
│ Support:    25,350–25,390                │
│ Resistance: 25,500–25,540                │
│                                          │
│ CURRENT STATE                             │
│ Bullish but approaching resistance        │
│                                          │
│ ──────────────────────────────────────── │
│                                          │
│ PRIMARY SCENARIO                          │
│ Breakout above 25,500                    │
│ Probability: 62%                         │
│                                          │
│ CONFIRMATION                              │
│ 5M close above 25,500                    │
│                                          │
│ TRADE                                     │
│ Buy 25,500 CE after confirmation         │
│                                          │
│ Setup Score: 87/100                      │
│                                          │
│ INVALIDATION                              │
│ 5M close below 25,390                    │
│                                          │
│ ──────────────────────────────────────── │
│                                          │
│ ALTERNATIVE SCENARIO                      │
│ Rejection from 25,500                    │
│ Probability: 24%                         │
│                                          │
│ ──────────────────────────────────────── │
│                                          │
│ NO TRADE CONDITION                        │
│ If price remains 25,390–25,500           │
│ without confirmation                     │
└──────────────────────────────────────────┘
```
---
# 92. The Most Important Feature
The biggest differentiator should not be:
> "AI predicts NIFTY."
It should be:
> **"StrikeLine understands the current market structure, explains why it expects a particular scenario, records what happened, identifies where its reasoning failed, and becomes statistically better validated over time."**
That is a much stronger and more defensible product.
---
# 93. Product Positioning
Recommended positioning:
## StrikeLine AI
### NIFTY Options Market Intelligence
Possible tagline:
> **Understand the Market. Validate the Setup. Trade with Evidence.**
Alternative:
> **AI-Powered Market Structure for NIFTY Options.**
Alternative:
> **See the Structure. Read the Flow. Find the Setup.**
Alternative:
> **From Market Data to Decision Intelligence.**
---
# 94. Final Product Definition
StrikeLine AI is **not a broker**.
It is **not an automated trading bot**.
It is **not a guaranteed prediction engine**.
It is an:
> **AI-powered NIFTY Options Market Intelligence, Scenario Analysis, Trade Decision Support and Continuous Learning Platform.**
Its long-term intelligence loop is:
```text
LIVE MARKET
     ↓
UNDERSTAND
     ↓
ANALYZE
     ↓
IDENTIFY LEVELS
     ↓
BUILD SCENARIOS
     ↓
RANK OPPORTUNITIES
     ↓
PLAN ENTRY
     ↓
DEFINE RISK
     ↓
WAIT / TRADE DECISION
     ↓
OBSERVE ACTUAL MARKET
     ↓
GRADE PREDICTION
     ↓
IDENTIFY MISTAKE
     ↓
LEARN PATTERN
     ↓
BACKTEST
     ↓
VALIDATE
     ↓
IMPROVE MODEL
     ↓
REPEAT
```
**This feedback loop is the core intellectual property of StrikeLine AI.**

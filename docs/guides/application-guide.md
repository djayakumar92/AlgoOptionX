# StrikeLine — Make Plan Easy

A private, single-user NIFTY options analysis tool built on your DhanHQ account.
It watches the market, automates your own trading rules, and keeps a record of
how those plans actually turned out.

**This app never places an order.** Every page is analysis and record-keeping
only — you still decide and trade manually.

---

## How to open it

Double-click **`Start Analyzer.bat`**. It starts the app and opens your browser
to it automatically. Best used during NSE market hours (9:15–15:30 IST), since
that's when live option-chain and candle data are actually moving. Closing the
console window stops the app.

---

## Start here: how to actually trade with it

This guide explains what each screen contains. If what you want is **the daily
routine — what to look at, when, and exactly how to enter and exit** — open
**How to Trade** in the app's own menu, under System. It is searchable, has a
contents rail, and keeps the live market bar at the top so you never lose sight
of the price while looking a rule up.

That page is served from `docs/guides/trading-research.md` in this folder, so the file
and the in-app page are the same document — edit the file and the page follows.

---

## The menu

The left-hand menu has:

- **Command Center** — the home page. One-glance summary of everything else.
- **Market**
  - **Live Market** — real-time spot price, market signals, and the option chain.
  - **Market Structure** — swing highs and lows, and what kind of day today is.
  - **Option Intelligence** — the option chain read in more detail.
  - **Charts** — candlestick charts, split into multiple panes, each with its
    own symbol and timeframe.
- **Intelligence**
  - **AI Analyst** — buy or sell today, which setups are live, and why. See below.
  - **Scenario Engine** — the ways today can go, and the checklist that
    decides whether to act. See below.
- **Trading**
  - **Trade Setups** — your High/Low/Close trading rule, automated.
  - **Journal** — the record of every day's plan and whether it worked out.
  - **Analytics** — how the journal has added up over time.
- **Research**
  - **Backtest** — runs the HLC rule over a stretch of past days at once.
  - **Learning Lab** — the engine's own track record. See below.
- **How to Trade** — the trading guide, in the app. Searchable.
- **Settings** — a read-only view of how the app is configured.

Nothing in the menu is a placeholder any more. One panel inside Option
Intelligence is still marked DEMO DATA — the seller-pressure score, which has
no model behind it yet. Everything else on every page is real.

---

## The bar at the top of every trading page

Every page you would use with the market open carries the same strip across
the top, and it does not scroll away:

> **Journal**  ·  NIFTY **23,897.7**  ·  BUY OPTIONS  ·  WAIT · 2 pts away  ·  midday session  ·  12:00 PM

The point is that you never lose the decision by walking away from it. You can
go and read the option chain, check last month's journal, or run a backtest,
and the price, the buy-or-sell call, and whether today's setup has come live
are all still in front of you. Before this, navigating away from the analyst
page meant navigating away from the answer.

It appears on **every page**, Settings included, so there is nowhere in the
app where you lose sight of the market.

On **Charts** it does double duty: the Layout button lives in the bar rather
than in a row of its own, so the strip pays for the vertical space it takes.

If a page ever does carry placeholder content again, its bar is tinted amber
and tagged `DEMO PAGE` — so a working-looking trading frame can never make
example numbers read as live ones.

---

## Command Center

Landing page. The row of tiles under the bar is the whole day in six numbers:

- **Today's Trade** — ACT NOW, WAIT, TOO LATE or STAND DOWN, with the name of
  the setup underneath. This is the tile to read first.
- **Bias** and **Confidence** from the Live signals.
- **Market Regime** — trending, ranging or transitional, plus today's day type.
- **Option Pricing** — cheap, fair or rich, with the priced move against the
  real one.
- **Data Health** — whether the feeds are behaving.

The last two used to be fake. "Market Regime: Trending" and "India VIX: 14.3"
were hardcoded placeholders marked demo, because nothing computed them. The
regime engine computes the first one for real now, so it reads from that.
India VIX still is not ingested, so rather than leave a made-up number the
tile was replaced with the priced-versus-real movement comparison, which
answers the same question — are options cheap or expensive — from data the app
actually has.

Below the tiles are summary cards with quick links into each full page. Those
are a summary of the other pages, so they always match what those pages show.

---

## Live Market

Polls your DhanHQ account roughly every 3–4 seconds and shows:

- **Spot price**, updated live.
- **A bias suggestion** (Bullish/Bearish/Neutral) with a confidence percentage,
  an entry zone, stop-loss, and watch level — built by combining four
  independent signals (below). This is a live "lean," not the same thing as
  the HLC strategy's plan.
- **Sentiment**: Put-Call Ratio (OI and Volume), max pain strike, IV skew,
  top OI strikes on each side.
- **OI Behavior**: long/short buildup counts on calls and puts (who's adding
  positions, not just who's trading).
- **Trend**: VWAP, moving-average crossover, ADX-based trend strength.
- **Momentum**: RSI, rate of change, IV rank.
- **Open Interest over time**: a chart of total CE/PE OI across the session,
  so you can see OI building up or unwinding as the day goes on.
- **The full option chain table**, strike by strike, around the current ATM.

## Charts

Candlestick charts for **Spot (NIFTY)**, **ATM Call (CE)**, and **ATM Put
(PE)**, at 1-minute, 5-minute, 15-minute, or Daily intervals.

- **Split layouts**: click **Layout** to pick 1 chart, 2 side-by-side, 2
  stacked, 1 large + 2 small, or a 4-way grid. Each pane has its own dropdown
  to pick the symbol and its own timeframe buttons — so you can watch, say,
  Spot on 5m and 15m at once, or Spot/CE/PE side by side.
- **Sync toggles** (in the same Layout menu): turn on Symbol/Timeframe sync to
  make all panes follow whichever one you change; turn on Crosshair sync (on
  by default) so hovering one chart lines up the same moment on every other
  pane.
- **HLC levels overlaid**: every chart shows your Max/Min Resistance, Min/Max
  Support, and ATM strike as horizontal lines; the CE/PE charts also show the
  *opposite* leg's High/Close/Low (your theory that CE/PE premiums move
  inversely, so the other leg's own levels act as support/resistance here
  too), plus the current plan's entry and target if one exists.
- **Price readout**: each pane shows the open/high/low/close of whichever
  candle you point at, in its header, in green or red. Move the cursor off
  and it goes back to showing the most recent candle, marked "latest", so a
  pane always states a price rather than going blank. With crosshair sync on,
  pointing at one chart updates the readout on all of them at the same
  moment — which is how you compare what Spot, the Call and the Put were each
  doing at 11:42.
- **Fills the window**: the grid sizes itself to your screen instead of a
  fixed height, so a bigger monitor gets bigger charts rather than more empty
  space. On a short window it stops shrinking and lets the page scroll — a
  squashed chart is worse than a scroll.
- Not yet built: drawing tools (trendlines, Fibonacci, text notes) and a
  real buy/sell order ticket — the latter deliberately, since this app never
  places trades.

---

## Trade Setups (the HLC rule)

This automates your own spreadsheet rule (`nifty_options_trading.xlsx`), using
the **last completed trading session's** High/Low/Close — same as filling the
sheet in after the market closes, not a live-updating range. It only refetches
when you click **Fetch Latest**; there's no reason for it to poll constantly
since the underlying data only changes once a day.

**How the rule works:**

1. **Find ATM**: of three candidate strikes (spot rounded to the nearest 50,
   and ±50 from there), pick whichever one has CE Close closest to PE Close.
2. **Support/Resistance bands**: read straight off that ATM strike's own CE
   and PE High/Low/Close.
3. **Buyer/Seller domination, per leg**: for the Call and the Put
   independently, compare Close against High and Low (within a 35-point
   threshold) to call it Buyer-dominated, Seller-dominated, or Indecision —
   which in turn labels the leg's day as Panic Buying / Profit Booking /
   Sideways.
4. **Combined signal**: a 2×2 matrix of the two legs' dominations gives you
   the overall read — e.g. "Strong Bullish (Panic Buying)," "Mixed," etc.
5. **Weekly/Monthly range panels**: separately, using the NIFTY close right
   after the previous weekly/monthly expiry, rounded to the nearest 100 —
   gives you a wider support/resistance band with its own combined-premium
   sell/buy levels.

**Today's Plan**: from the combined signal, the tool decides which leg(s) to
**sell**, with an entry price, a stop rule (exit if the leg's premium closes
above its own previous 5-minute candle's high — this is a live, moving rule,
not a fixed number, so it's described rather than shown as one price), and a
target (20 premium points/day by default, split across up to 2 trades).

> **Worth knowing**: the rule for *which* leg to sell on "Strong Bullish,"
> "Strong Bearish," and "Indecision" days is Claude's own extension of your
> spreadsheet — your sheet only ever defined the "Mixed" case directly. It's
> flagged, not hidden, but it means the Journal's win/loss record should be
> checked against a real stretch of days before fully trusting it. The
> 35-point domination threshold is also currently fixed, not adjusted for
> volatility.

**Plan vs. session date**: the plan is always for the *next* trading day.
"Plan for 2026-09-02 — built from the 2026-09-01 close" means: read Monday's
close, trade Tuesday.

---

## Journal

The historical record: every trading day's plan, and what actually happened.

- Logged automatically once a day, when the HLC strategy rolls over to a new
  session.
- **Graded** by replaying that day's real 5-minute candles against the
  planned entry, target, and the moving stop rule — outcome is one of
  **Target Hit**, **Stop Hit**, **Not Triggered**, **Open at Close**, or
  (on a day the rule says to sit out entirely) **Sat Out**.
- Shows both the **Trade Date** (the day it was meant to be acted on) and
  what it was **Based On** (the previous close it was built from), plus the
  signal, leg, strike, entry, target, and realized points.
- This is a look-back record, not a live monitor — nothing places or watches
  a live trade for you.

---

## AI Analyst

Built as a trading screen, not a report. Everything needed to make the call is
on one screen with no scrolling, laid out in the order a decision actually
gets made.

**The bar across the top never moves.** Scroll anywhere on the page and it
still shows the NIFTY price, whether today favours buying or selling, and
whether to act right now — plus a warning if it is expiry day.

**The big card on the left is the trade.** In order: what to do, whether to do
it yet, and the three numbers you would type into your broker.

The middle row is the most important part of the page:

| | |
|---|---|
| **ACT NOW** | Price is at the level. This is the window. |
| **WAIT** | Conditions are right but price is not there yet — it tells you how many points away. |
| **TOO LATE** | Price has already run past. Entering now means the same stop with less reward left. It is deliberately never offered as the best setup. |
| **STAND DOWN** | Nothing is worth taking. A real answer, and the common one. |

That distinction did not exist before: a setup being "on" and a setup being
"do it this minute" are different things, and only the second one is a
decision.

**The right-hand column is the market around the trade.** "Levels that matter"
is a price ladder — every level worth watching stacked high to low with NIFTY
highlighted in its actual position among them, and how many points away each
one is. This is how a trader reads a market: not as a list of statistics, but
as a stack of levels with price somewhere inside it. Hover any row for what
that level is.

Below it sit the two numbers that drive the buy-or-sell call, and the full
list of factors behind it. Hover any factor for the reasoning.

**Everything else is folded away.** The setups the engine ruled out, and the
hedging-flow detail, sit behind click-to-open headings — during a session they
are reference material, and keeping them collapsed is what keeps the decision
above the fold.

### The question underneath all of it

**Should you be buying options today, or selling them?** That is a different
question from "which way is the market going", and getting it wrong loses
money even when you call the direction right — buying an option into a quiet,
expensively-priced day loses to time decay whatever the market does.

**"What options are charging"** is the panel that answers it. Two figures sit
side by side:

- what today's options are pricing in for a session's move, and
- how far NIFTY has actually been moving lately.

If options charge more than the market delivers, selling has the edge. If they
charge less, buying does. That is the whole comparison, and it is the most
useful single read in options.

Every setup, whether it is the live one or one you open from the ruled-out
list, always tells you the same four things:

- **What it would be** — buy or sell, call or put, which strike.
- **The assumption you are making** — plain English, and always something that
  can turn out false.
- **Enter only when** — the exact thing that has to happen first. Not "buy
  now"; a condition to wait for.
- **Get out when** — the exact thing that proves the assumption wrong.

The ruled-out list is shown rather than hidden on purpose: knowing why a trade
is off is worth as much as knowing which is on, and it lets you argue with the
engine rather than just trust it.

### About the grades

Each setup carries a letter grade. **Every grade is capped at C until that
setup has twenty real graded results behind it**, no matter how good today's
readings look. A setup that has never been tested says so. This is not
excessive caution: with three or four results, a perfect record and a terrible
one are both entirely consistent with a setup that is worthless.

That means the app is deliberately unconfident on day one, and gets more
confident only as it earns it — one trading session at a time.

---

## Scenario Engine

Price can only do three things from here: take out the level above, take out
the level below, or stay between them. So there are always exactly three
scenarios, each with today's real levels attached:

- **Happens when** — the actual price level and condition.
- **Ruled out when** — what kills it. A failed break is not a weaker version
  of the break scenario; it *is* the range scenario.
- **Plays for** — where it would go.
- **What it means for you** — buy calls, sell premium at the edges, and so on.
- **Evidence pointing here** — the individual factors, each with its weight.

### The percentage is not a probability

This matters. Each scenario shows a number like 71%. That is the **share of
today's measurable evidence** pointing that way — seven factors, each with a
fixed weight, each voting for one scenario. It is not fitted to any historical
outcome and says nothing about how often that scenario has come true.

Read it as *"most of what I can measure points here"*, never as *"this happens
seven times in ten"*.

A factor that cannot be read — no gamma data, not enough history — votes for
nothing and is left out of the total, rather than being quietly counted as
support for "stay in the range". So the shares always describe what was
actually measurable.

### The entry checklist

Ten conditions, all read from live data, all able to fail. The scenarios
describe the market; the checklist decides whether *you* act. A
well-supported scenario with no entry trigger and a closed market is still not
a trade — which is why the verdict at the top can read STAND DOWN even when
one scenario has most of the evidence behind it.

---

## Learning Lab

Every setup the AI Analyst arms during a live session is written down *before*
anyone knows how the day ends, and graded after the close. This page is that
record.

**"Is the engine's read of the market worth anything?"** is a check the app
runs on itself: days it called trending should, on average, have travelled
further than days it called quiet. If they did not, the app says so plainly
instead of hiding it.

**"What each setup has actually done"** is the per-setup record — how often it
appeared, how often it worked, and how it did in different market conditions.

One important limit, stated on the page too: results are graded against
NIFTY's own price — did the level hold, did the break extend, did the day stay
inside its expected range. That grades the setup's *reasoning*, which is what
these numbers are for. It is **not** a profit-and-loss figure in rupees, and
it is deliberately not presented as one.

The record starts empty. It fills in one session at a time, and there is no
shortcut that does not involve making numbers up.

---

## What's intentionally not in this app

- **No order placement, anywhere.** Every number is for you to act on
  manually.
- **No investment advice** beyond what your own rules compute — this isn't a
  broker or an advisor.
- **No drawing tools or indicator overlays** on the Charts page yet.
- **No unusual-activity detector** (a planned idea, not started).
- **No seller-pressure score** on Option Intelligence yet — that one panel is
  still marked DEMO because the model behind it does not exist. Everything else
  on that page is real.
- **No Market Replay.** The page was removed rather than left as a permanent
  demo. Reviewing how a day unfolded is already covered: Learning Lab shows
  what the engine said against what happened, and Charts replays the price
  itself.
- **No India VIX.** It is not ingested from the broker feed, so no screen shows
  it. The priced-versus-real movement comparison covers the same ground with
  data the app does have.
- **No trained prediction model.** The AI Analyst applies a fixed set of rules
  and writes down how they do; it does not learn new rules by itself. Building
  the record is the step that has to come first, and it is the step this app is
  on.

---

## A note on trust

A few pieces of this app's logic are inferences built to fill a gap your
spreadsheet didn't cover directly (see the Trade Setups section above), and
the Journal so far only has a handful of real graded days — nowhere near
enough to prove the strategy works or doesn't. Treat early Journal results as
"does this look sane" checks, not a verdict, until there's a real stretch of
trading days behind it.

The same applies, more strongly, to the AI Analyst. It starts knowing nothing
about its own reliability, and it is built to say so rather than to look
confident: grades capped at C, "never been graded" printed on every untested
setup, and a page (Learning Lab) whose only job is to check the engine against
what actually happened. If a number on any screen looks more certain than the
data behind it, that is a bug worth reporting, not a feature.

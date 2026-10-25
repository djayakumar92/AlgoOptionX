# How to use StrikeLine — reading it, entering, exiting

A working guide, meant to be open beside the app. It explains what the numbers
mean and exactly what to do with them. It does not tell you whether to trade —
the app never places an order, and neither this document nor the app is
financial advice.

---

## The 30-second read

Open **AI Analyst**. Three things, in this order, and nothing else:

**1. The bar at the top — should you be buying or selling options today?**

```
AI Analyst │ NIFTY 23,779.15 │ SELL OPTIONS │ WAIT · 2 pts away │ midday session │ 12:04 PM
```

This bar is on every page and never scrolls away. `BUY OPTIONS` / `SELL
OPTIONS` is the day's stance. It is a different question from "which way is the
market going", and it is the one most people get wrong: buying an option on a
quiet, expensively-priced day loses to time decay even when your direction is
right.

**2. The big card — what the trade is, and whether to act now.**

```
BUY PUT 23,900                                    Grade B · 90/100
Opening-range breakout (down)

WAIT   NIFTY is 2 points above 23,896. Nothing to do until it closes
       a 5-minute candle through it.

TRIGGER          GET OUT          TARGET
23,896           23,896           23,834
2 pts from here  same level       about 27 points of premium
```

**3. The verdict word.** This is the whole decision:

| Word | What to do |
|---|---|
| **ACT NOW** | Price is at the level. This is the window. |
| **WAIT** | Right setup, wrong moment. It tells you how far away. Do nothing yet. |
| **TOO LATE** | Price already ran past. **Skip it.** Same stop, less reward left. |
| **STAND DOWN** | Nothing worth taking. The most common answer, and a real one. |

If it says STAND DOWN or TOO LATE, you are done. Close the laptop.

---

## The daily routine

### Before the open — 9:00 to 9:15

Open the app. Look at **Command Center**. The tiles tell you the shape of the
day before it starts: today's trade (usually STAND DOWN this early), the
regime, and whether options are cheap or expensive.

Then look at **Trade Setups** for the HLC plan built from yesterday's close.

**Do not act on anything yet.** Before 9:15 the app says *"The market is
closed"* and blocks every setup deliberately.

### First 30 minutes — 9:15 to 9:45

**Do not trade.** The app will not arm a setup in this window, on purpose:
volatility is still unwinding from the overnight gap and direction is
unresolved. This is the single most common way to lose money in the first hour.

Use the time to watch the opening range form on **Market Structure**. The
opening range high and low become the day's most important levels.

### The session — 9:45 to 15:30

Sit on **AI Analyst**. It refreshes itself every 30 seconds.

- **WAIT** → note the trigger level. Watch it. Do nothing.
- **ACT NOW** → follow the entry rules below.
- **STAND DOWN** → nothing to do. Check the ruled-out list if you want to know why.

Use **Scenario Engine** when you want the wider picture: the three ways the day
can go, and the 10-point checklist. If the checklist is failing on several
items, that is a day to be small or absent.

### After the close

**Journal** — did today's plan work out. **Learning Lab** — what the engine's
record looks like so far. Both fill in automatically; there is nothing to enter
by hand.

---

## Entering a trade

### The one rule that matters most

> **Wait for a 5-minute candle to CLOSE through the level. A wick through is
> not a signal.**

Price touching 23,896 is not the trigger. Price *closing a 5-minute candle*
beyond 23,896 is. Most false breaks are wicks. This single rule removes a large
share of losing entries, and every setup in the app is written and graded
against it.

### Step by step

1. **Check the verdict says ACT NOW.** If it says WAIT, the level has not been
   reached. If TOO LATE, the move has gone without you — let it go.
2. **Read the three numbers**: Trigger, Get out, Target.
3. **Watch the 5-minute candle close** through the trigger level.
4. **Check the next candle does not immediately reverse back through it.**
5. **Enter** the strike named on the card, at market.
6. **Write down the "Get out" number before you enter.** If you cannot say
   where you are leaving, you are not ready to enter.

### When the trigger and the stop are the same number

On a breakout they genuinely are — you enter on a close through the level and
you leave on a close back through it. The card says so rather than repeating
the number silently. That is correct, not a bug.

### Never enter when

- The market is closed or in the first 30 minutes — the app blocks it anyway.
- It is expiry day and you are in the last hours — the app blocks premium
  selling here. This is the highest-risk window of the week.
- The verdict says TOO LATE. Chasing is the same stop for less reward.
- You cannot state the exit level out loud.

---

## Exiting a trade

Three ways out. Decide which one happened, then act — do not negotiate.

### 1. The stop — a 5-minute close back through "Get out"

Not a touch. Not a wick. A **close**. When that candle closes, you are out.

The card tells you what the close means in words, for example: *"a close back
through this kills the trade"*, or *"a second break after a failure is usually
the real one"*. That sentence is the reason you are leaving. If it has
happened, the reason you entered no longer exists.

### 2. The target

Take it. The target is set at a fraction of the day's priced move, not at a
hopeful number, precisely so it is reachable.

### 3. The close of the session

**This app is built for intraday only. Never hold overnight.** Every setup is
graded on a single session, and the whole design avoids overnight gap risk —
which is the largest and least controllable risk in Indian index options. If
neither the stop nor the target has hit by around 15:15, close it anyway.

### On expiry day, exit faster

An option's sensitivity to NIFTY changes fastest on expiry day. A stop sized
off a calm morning candle can be blown straight through. When the app shows the
`EXPIRY DAY` flag: trade smaller, and honour the exit immediately — there is no
time left for a losing expiry-day position to recover.

---

## What each number means

### On the bar

| Reading | Meaning |
|---|---|
| **BUY OPTIONS** | NIFTY has been moving more than options are pricing. Movement is underpriced. |
| **SELL OPTIONS** | Options price more movement than NIFTY has delivered. The normal state. |
| **EXPIRY DAY** | Highest decay *and* highest risk of the week. Size down. |
| **closed / opening / midday / closing session** | Where you are in the day. Setups only arm in midday and closing. |

### On the AI Analyst page

**"What options are charging"** — two numbers side by side:

```
PRICED MOVE          REAL MOVE
128                  155
points a session     across 19 sessions
```

Options are pricing 128 points of movement; NIFTY has actually been finishing
155 points from its open. Movement is underpriced, so buying is favoured. If
the priced number were the bigger one, selling would be.

**"Levels that matter"** — every level worth watching, stacked high to low,
with NIFTY highlighted in its real position among them and how far each is:

```
  Call wall 24000              24,000   +221
  Yesterday's high             23,890   +111
  Day's average price          23,781     +2
▶ NIFTY now                    23,779
  Yesterday's low              23,738     -41
```

This is how a market is actually read — not as a list of statistics, but as a
stack of levels with price somewhere inside it. Hover any row for what it is.

**"Why that call"** — every factor that pushed the decision, with its points.
Plus argues for buying, minus for selling. Hover for the reasoning. Nothing is
hidden, including the factors that came out neutral.

### Grades and track record

Each setup has a letter grade. **Every grade is capped at C until that setup
has 20 real graded results**, however good today's readings look.

This is deliberate. With three or four results, a perfect record and a terrible
one are both entirely consistent with a setup that is worthless. So right now,
early on:

> **Treat the grade as "conditions match", not "this wins."**

The app gets more confident only as it earns it, one session at a time.

---

## Common mistakes this app is built to stop

| Mistake | What the app does |
|---|---|
| Trading the first 30 minutes | Refuses to arm any setup |
| Chasing a move that already went | Marks it TOO LATE and never offers it as the best setup |
| Entering on a wick | Every trigger requires a candle **close** |
| Selling premium into a trend | The straddle setup refuses to fire in a trending market |
| Selling into a wall that is breaking | Blocks the trade when open interest is unwinding on heavy volume |
| Holding a losing expiry-day trade | Flags expiry day and blocks selling in the final hours |
| Believing a win rate built on 3 trades | Caps the grade and prints the sample size next to every number |

---

## Being honest about where this is today

The engine has **no track record yet**. The ledger started this week. Until
roughly 20 graded outcomes accumulate per setup, this is a **discipline and
checklist tool** — it stops you doing the expensive things above, and it forces
you to state an entry, an exit and an assumption before you commit.

That is worth a great deal on its own. But it is not yet a proven signal
generator, and the app is built to keep saying so rather than to look
confident. When Learning Lab starts showing real hit rates with real sample
sizes behind them, that is when the grades start meaning what they say.

Trade small until then.

# AlgoOptionX — Enterprise Product Strategy, Architecture & AI Development Master Plan

Version 1.1 — User-supplied blueprint with repository reconciliation | Planning and delivery reference | 28 October 2026

**Application name: AlgoOptionX.** Source: the user's complete Version 1.0 proposal. Sections 1–14 preserve its product vision, requirements, proposed technologies and recommendations. Sections 15–18 reconcile that proposal with the current repository, define delivery gates and track coverage.

**Status and precedence:** This is a planning document, not a statement that the enterprise roadmap is implemented. Original statements about an unaudited repository, concept-only UI, and provisional scores describe the supplied proposal's starting assumptions. Current verified software status is in §15. Current source and test evidence describe implemented behavior; proposed risk parameters, future architecture and feature scope require their own implementation tasks. This document does not change risk settings, install OpenSpec, deploy services, enroll customers, access licensed feeds or enable live orders. The user's actual chat decisions govern human approval; no approval or external compliance clearance is inferred.

**How to use this plan:** Follow phases 0–6 and their dependency gates in §17. Review a concrete specification, design and task before changing the corresponding behavior. Keep existing working modules and financial history. Record implementation, independent review, test evidence and the user's decisions separately. The two external chart-pattern images in the source proposal are illustrative references, not approved AlgoOptionX designs or reusable licensed assets.

## 1. Executive vision

AlgoOptionX will be an AI-powered NIFTY options intelligence, automated paper-trading, backtesting, and future multi-broker algorithmic trading SaaS platform.

The goal is not to create another indicator dashboard. It is to develop a system that captures the analytical processes of experienced options traders, continuously evaluates its decisions, identifies weaknesses, and improves through controlled, evidence-based learning.

The application must be designed from day one for commercial expansion, even though the initial implementation will use local simulated market data and virtual capital.

### Product objectives

| Objective                    | Expected capability                                                            |
| ---------------------------- | ------------------------------------------------------------------------------ |
| Trading intelligence         | Understand market structure, trends, price action, derivatives, and volatility |
| Experienced-trader reasoning | Evaluate bullish, bearish, sideways, reversal, and uncertain conditions        |
| Autonomous decision-making   | Generate and evaluate entry, exit, stop-loss, and no-trade decisions           |
| Automated paper trading      | Execute simulated trades using ₹5,00,000 virtual capital                       |
| Continuous learning          | Identify strategy strengths, weaknesses, and model drift                       |
| Risk management              | Enforce independent risk controls that AI cannot bypass                        |
| Enterprise product quality   | Modular architecture, reliable APIs, security, testing, accessibility          |
| Commercial viability         | Validate willingness to pay before substantial commercial investment           |
| Future expansion             | Historical backtesting, licensed live data, multiple brokers, subscriptions    |

The central product principle is:

AlgoOptionX must demonstrate measurable decision quality and disciplined risk management, rather than promise trading profits.

## 2. Product development phases

1. Phase 0 — Existing application audit and product specifications

   Inspect the existing analyzer, identify reusable modules, evaluate architecture and technical debt, and produce an approved enterprise design.
2. Phase 1 — AI development harness and local-data foundation

   Establish OpenSpec, agents, skills, test automation, governance, synthetic market-data services, and deterministic replay.
3. Phase 2 — Advanced market intelligence

   Implement market structure, patterns, gaps, option-chain analytics, trader-behavior hypotheses, volatility analysis, and market regime classification.
4. Phase 3 — Autonomous AI paper trading

   Add AI decisions, independent risk validation, virtual execution, automated exits, trade journaling, and performance monitoring.
5. Phase 4 — Backtesting and controlled learning

   Historical datasets, walk-forward validation, transaction-cost modeling, challenger models, and human-approved model deployment.
6. Phase 5 — Licensed market data and commercial SaaS

   Dhan or alternative market-data providers, user accounts, subscriptions, entitlements, billing, and operational monitoring.
7. Phase 6 — Multi-broker live trading

   Broker adapters, execution safeguards, regulatory review, explicit approvals, and controlled deployment. This phase is not automatically authorized by paper-trading performance.

The phases describe dependencies, not fixed deadlines. Actual schedules should be determined after the repository audit.

## 3. Experienced options trader knowledge framework

AlgoOptionX needs a structured knowledge base covering beginner, intermediate, advanced, and institutional-style analytical techniques.

### A. Market structure and price action

| Knowledge                  | Required intelligence                          |
| -------------------------- | ---------------------------------------------- |
| Higher highs / higher lows | Identify developing uptrends                   |
| Lower highs / lower lows   | Identify developing downtrends                 |
| Break of structure         | Detect structural changes                      |
| Change of character        | Flag possible trend transitions                |
| Support and resistance     | Detect, rank, and invalidate price zones       |
| Supply and demand zones    | Identify historical price-reaction areas       |
| Liquidity sweeps           | Detect breaks followed by rapid rejection      |
| Breakout and retest        | Evaluate breakout confirmation                 |
| False breakout             | Detect failed continuation attempts            |
| Consolidation              | Identify range-bound conditions                |
| Opening range              | Track opening high, low, and subsequent breaks |
| VWAP                       | Evaluate intraday price positioning            |

These concepts must be translated into precise mathematical definitions, not vague visual interpretations.

For example, a support zone should include its calculation method, observation window, number of prior touches, invalidation criteria, and historical effectiveness.

### B. Bullish and bearish chart patterns

[Chart Patterns in Trading: What is it and How to read Them? | TMGM](https://images.openai.com/static-rsc-4/NwLbMxWZVcRRlV1wmLi38r-MQXWLVhKtnx_3X_BldfSZvIwf20T5OWPuxixFd7S8n4VUet-7reI9h9IhrSlN-DGD6FIOB75y0yFnra5G9NBewqWqtKUIzUAPOqATTUUxolGDiexcVW1vJ9mBmMel3tD9h0swHUI-yUdGKg26Dgo?purpose=inline)

Bullish pattern intelligence

Double bottom, inverse head-and-shoulders, ascending triangle, bullish flag, hammer, engulfing, and breakout-retest.

[Triangle Chart Patterns: Ascending, Descending, Symmetrical | Guide](https://images.openai.com/static-rsc-4/ZS9EfiR3OHtaYUqvxfU0eqfj2xjBCawpW1vrNPZXl2s-R2_lEyGC63GkrO6apySMTISV1Xde1Ui0U2PNJBfT7Lp9xVs4TRXjOilmBR2yofEJedUvaLJ61nsf1llAOqrVsnIrN8N8rOfv7roUMNiptLioBLXRb3ZeokFYoyQU5mI?purpose=inline)

Bearish pattern intelligence

Double top, head-and-shoulders, descending triangle, bearish flag, shooting star, engulfing, and breakdown-retest.

Pattern detection must consider the surrounding trend, volatility, volume, formation quality, and invalidation point. A detected pattern is not automatically a trading signal.

### C. Gap-up and gap-down intelligence

The system should distinguish among gap continuation, gap fill, gap rejection, gap exhaustion, and opening-range consolidation.

For each gap, analyze:

- Previous close versus current open, normalized by volatility.
- Previous-day high/low and nearby structural levels.
- Opening volume and first 5-, 15-, and 30-minute behavior.
- Option premium and implied-volatility changes.
- Whether continuation or rejection has historical support in the current regime.

The AI must be allowed to conclude that a gap has no reliable trading opportunity.

### D. Option buyer and seller intelligence

| Buyer perspective             | Seller perspective                           |
| ----------------------------- | -------------------------------------------- |
| Directional momentum          | Premium decay and volatility risk            |
| Delta and gamma exposure      | Theta and short-gamma exposure               |
| Breakout continuation         | Range persistence                            |
| IV expansion risk/opportunity | IV contraction risk/opportunity              |
| Strike liquidity              | Margin and assignment/exercise-related risks |
| Premium sensitivity           | Tail risk and gap risk                       |
| Fast directional movement     | Hedging and position adjustment              |

An important research distinction: Option sellers do not universally determine market direction. Institutional hedging and derivatives positioning can influence price behavior, but observed open interest cannot reliably reveal an individual participant's intention.

AlgoOptionX should test hypotheses about seller positioning rather than treat them as established facts.

### E. Market psychology and behavioral intelligence

The system should research FOMO-driven breakouts, panic selling, stop-loss clustering, profit booking, overreaction, mean reversion, and volatility compression.

However, these are inferred behavioral explanations. They must not be presented as directly observed trader emotions.

The AI should explain what the market data supports, what remains uncertain, and what evidence would invalidate its hypothesis.

### F. Advanced quantitative knowledge

The advanced research modules should cover volatility surfaces, implied versus realized volatility, put-call parity, Greeks, liquidity, spread behavior, expected move distributions, probabilistic calibration, regime transitions, market microstructure, and realistic execution costs.

Every module should have independent tests and an evidence-based contribution to the overall strategy.

## 4. Autonomous AI decision architecture

Market Data Layer

Local simulator → historical provider → licensed live provider

Validation and Feature Engineering

Data integrity, timestamps, indicators, options metrics

Market Structure

Pattern Recognition

Options & Greeks

Market Psychology

Volatility & Regime

Gap Analysis

AI Decision Engine

Bullish / Bearish / Sideways / No Trade

Independent Deterministic Risk Engine

Exposure, position sizing, margin, drawdown, safety checks

Paper Execution and Event Ledger

Virtual orders, fills, exits, costs, P&L, audit evidence

Evaluation and Controlled Learning

Outcomes, model comparison, retraining, approval, rollback

### Initial trading configuration

| Setting                | Initial research configuration                    |
| ---------------------- | ------------------------------------------------- |
| Instrument             | NIFTY options                                     |
| Capital                | ₹5,00,000 virtual                                 |
| Entry timeframe        | 5 minutes                                         |
| Confirmation timeframe | 30 minutes                                        |
| Trading styles         | Option buying and defined-risk selling strategies |
| Maximum risk per trade | 0.5% virtual equity — ₹2,500 initially            |
| Daily loss limit       | 1% virtual equity — ₹5,000 initially              |
| Execution              | Fully automated paper trading                     |
| Market data            | Deterministic local simulator initially           |
| Learning               | Scheduled retraining with human approval          |
| Live orders            | Disabled                                          |

These are proposed testing limits, not optimized trading parameters. Unhedged option selling should not be included in the initial automated execution scope.

### Example AI decision

Illustrative decision record

NO TRADE

Market regime

Range-bound

30-minute confirmation

Missing

Breakout quality

Weak

Risk decision

Reject

Reason: The proposed 5-minute breakout lacks higher-timeframe confirmation. Expected reward relative to modeled risk is below the configured threshold.

Illustrative explanation only — not an actual market prediction.

## 5. Enterprise UI/UX product design

The UI should be designed around user workflows rather than placing every indicator on one crowded dashboard.

### Proposed application navigation

| Module               | Primary purpose                                               |
| -------------------- | ------------------------------------------------------------- |
| Dashboard            | Portfolio, AI status, important alerts, performance summary   |
| Market Intelligence  | Trend, structure, gaps, volatility, patterns                  |
| Chart Workspace      | Candlesticks, S/R, indicators, evidence annotations           |
| Options Intelligence | Chain, OI, Greeks, IV, seller/buyer hypotheses                |
| AI Decision Center   | Model reasoning, confidence, approvals, no-trade explanations |
| Strategy Lab         | Strategy configuration, versions, evaluation                  |
| Paper Trading        | Virtual positions, orders, risk, execution history            |
| Backtesting          | Historical tests, walk-forward results, comparisons           |
| Performance          | Equity, drawdown, expectancy, strategy attribution            |
| AI Learning Center   | Model versions, drift, strengths, weaknesses                  |
| Trade Journal        | Decisions, events, outcomes, lessons                          |
| Administration       | Users, plans, data sources, permissions, audit logs           |

Each module should have a dedicated visual design, including empty, loading, error, disabled, and permission-restricted states.

### Visual design requirements

The UI design deliverables must include image-based references for:

- Every main screen and subpage.
- All tabs before and after switching.
- Dialogs, confirmation popups, alerts, and tooltips.
- Table sorting, filtering, pagination, and row expansion.
- Charts with overlays and interactions.
- AI decision explanations and rejected trades.
- Strategy configuration and validation failures.
- Responsive desktop, tablet, and mobile layouts.
- Light and dark themes where appropriate.

Every design should map to a reusable component specification and automated visual regression tests.

The product should meet WCAG 2.2 AA accessibility targets, use semantic HTML, keyboard-accessible interactions, responsive layouts, and secure web development practices.

## 6. Recommended technology architecture

| Layer                 | Proposed technology                                  |
| --------------------- | ---------------------------------------------------- |
| Frontend              | React + TypeScript                                   |
| Build system          | Vite                                                 |
| UI components         | Accessible component primitives + design tokens      |
| Charts                | TradingView Lightweight Charts or equivalent         |
| Backend API           | Python + FastAPI                                     |
| Quantitative research | NumPy, pandas/Polars, scikit-learn                   |
| Database              | PostgreSQL                                           |
| Time-series storage   | PostgreSQL initially; evaluate TimescaleDB if needed |
| Background processing | Redis-backed workers or a durable job queue          |
| AI model registry     | MLflow or an equivalent registry                     |
| Frontend testing      | Vitest + React Testing Library                       |
| Backend testing       | Pytest + Hypothesis                                  |
| E2E testing           | Playwright                                           |
| API contracts         | OpenAPI + schema validation                          |
| Monitoring            | OpenTelemetry, Prometheus/Grafana as justified       |
| CI/CD                 | GitHub Actions or existing repository infrastructure |

These are proposed defaults. We should not replace working technology until the repository audit establishes a reason.

### Architecture principles

Use a modular monolith first, with clearly separated domains and interfaces. This is generally easier to test and operate than introducing many microservices prematurely.

The major domains should be Market Data, Analytics, AI Research, Strategy, Risk, Paper Execution, Portfolio Accounting, Model Governance, User Management, Billing, and Audit.

Future broker integrations must use adapter interfaces, keeping broker-specific behavior outside the core trading logic.

## 7. AI development agents and skills

This is where AlgoOptionX should differ from ordinary AI-generated applications.

### Specialized agents

| Agent                     | Responsibility                                            |
| ------------------------- | --------------------------------------------------------- |
| Product Manager           | Business requirements, priorities, customer value         |
| Requirement Analyst       | Detailed requirements and acceptance criteria             |
| Requirement Validator     | Detect ambiguity, omissions, conflicts                    |
| Solution Architect        | Architecture, dependencies, scalability                   |
| UX Architect              | User journeys, design systems, interaction specifications |
| Frontend Engineer         | Accessible and reusable UI implementation                 |
| Backend Engineer          | APIs, business logic, persistence                         |
| Quant Researcher          | Market hypotheses, statistical validation                 |
| Options Domain Specialist | Options pricing, Greeks, expiry behavior                  |
| ML Engineer               | Features, training, evaluation, registry                  |
| Risk Architect            | Independent trading risk controls                         |
| Security Engineer         | Threat modeling, authentication, authorization            |
| QA Engineer               | Unit, integration, property, and E2E tests                |
| Independent Validator     | Verify implementation and evidence                        |
| DevOps Engineer           | CI/CD, environments, observability                        |
| Release Governor          | Enforce approval and release requirements                 |

Not every role requires a permanently running agent. Many can be specialized Codex roles or skills invoked only when needed.

### Required reusable skills

Examples include:

`requirement-analysis`, `requirement-validation`, `architecture-review`, `ui-design-validation`, `react-development`, `fastapi-development`, `options-domain-analysis`, `quant-backtesting`, `market-data-validation`, `risk-control-testing`, `ml-leakage-prevention`, `security-review`, `playwright-testing`, `evidence-verification`, and `release-readiness`.

Each skill must define inputs, outputs, allowed actions, validation commands, failure conditions, and evidence requirements.

### Development harness

OpenSpec Requirements and Design

Agent Orchestrator

Task routing, dependency checks, scoped permissions

Implementation Agent

Approved, isolated changes only

Independent Testing Harness

Unit, integration, E2E, security, trading invariants

Evidence Verification and Governance

Test outputs, artifact hashes, approvals, audit logs

The harness must not accept an agent's statement that tests passed as sufficient evidence. It must verify actual command results, exit codes, test reports, and the tested commit.

Human approval must be enforced outside the agent's editable workspace where feasible.

## 8. Testing and reliability strategy

### Testing coverage

| Test category     | What must be verified                                  |
| ----------------- | ------------------------------------------------------ |
| Unit              | Indicators, Greeks, calculations, position sizing      |
| Property-based    | Mathematical invariants and boundary cases             |
| Contract          | API schemas, broker adapters, data-provider interfaces |
| Integration       | Analytics → decision → risk → execution                |
| E2E               | Complete user workflows and paper-trading sessions     |
| Visual regression | Screen consistency against approved references         |
| Data integrity    | Missing candles, duplicates, stale quotes, timestamps  |
| Trading safety    | Daily limits, position caps, margin, kill switch       |
| Backtesting       | Look-ahead bias, survivorship, slippage, fees          |
| ML validation     | Leakage, overfitting, calibration, drift               |
| Security          | Authentication, tenant isolation, secret handling      |
| Adversarial       | Prompt injection, forged evidence, bypass attempts     |
| Reliability       | Recovery, idempotency, retries, concurrent events      |

### Critical financial invariants

The system must never permit virtual trades to bypass the risk engine. Replayed events must not create duplicate fills. Position quantities, available capital, reserved margin, realized P&L, and unrealized P&L must reconcile.

Backtests must use only information available at each simulated decision time. For options, historical strike availability, expiry schedules, bid-ask spreads, and realistic fills are essential.

A 90-day paper-trading period should be evaluated using net expectancy, drawdown, tail losses, profit factor, regime performance, and sufficient trade samples—not profitability alone.

## 9. Self-analysis and improvement system

AlgoOptionX should maintain two independent improvement loops.

Trading model improvement: Evaluate decision quality, losing trades, false signals, missed opportunities, market-regime weaknesses, calibration, and execution assumptions. Train challenger models on approved datasets and compare them with the active model using untouched evaluation periods.

Software product improvement: Monitor application errors, latency, UI usability, test failures, accessibility, operational costs, and user feedback. Generate proposed improvements, but require review before implementation.

The system should never silently retrain and deploy a model that changes trading behavior. It must retain version history, approval records, evaluation evidence, and rollback capability.

## 10. Business model and market demand

Your proposed ₹199–₹499 monthly pricing can be explored, but the product must offer value beyond promising customers that they will make money.

Potential customer segments include retail options learners, disciplined paper traders, strategy researchers, active discretionary traders, and later professional or institutional users.

### Proposed subscription structure

| Plan       | Illustrative price | Value proposition                                                           |
| ---------- | ------------------ | --------------------------------------------------------------------------- |
| Free       | ₹0                 | Delayed/sample-data analysis, limited strategies, educational paper trading |
| Starter    | ₹199/month         | Paper trading, journal, basic AI explanations                               |
| Pro        | ₹499/month         | Advanced analytics, multiple strategies, performance reports                |
| Advanced   | ₹999/month         | Backtesting, model comparisons, expanded automation                         |
| Enterprise | Custom             | Teams, permissions, audit exports, integrations                             |

These are pricing hypotheses, not validated prices. Real-time exchange data, broker connectivity, infrastructure costs, taxes, and regulatory obligations may require different pricing or separate data charges.

### Business evaluation — preliminary scorecard

My provisional assessment, scored out of 10. These are judgment-based planning estimates, not externally verified measurements.

Product differentiation

7/10

Combining explainable AI, risk controls, and paper trading could differentiate the product.

Technical feasibility

8/10

Core modules are feasible, but data quality and execution realism are difficult.

Trading profitability evidence

1/10

No validated profitable strategy or independent live-market evidence yet.

UI/UX maturity

4/10

Concept images exist, but workflows and usability have not been validated.

Commercial demand evidence

3/10

Comparable product categories exist; willingness to pay for AlgoOptionX is untested.

Architecture readiness

4/10

Architecture is proposed but the existing codebase has not been audited.

Scalability potential

7/10

Modular architecture and broker adapters support future expansion.

Regulatory readiness

2/10

Licensing, data redistribution, advice, and algo-trading requirements need formal review.

### How we verify customers will pay

Before building billing and enterprise features, we should validate demand through interviews and actual purchase intent.

A reasonable initial research target is 20–30 prospective users, followed by a working prototype and a small opt-in pilot. We should measure repeated usage, willingness to pay, feature priorities, retention, support burden, and actual paid conversions.

A signup or positive interview response does not prove willingness to pay. The strongest evidence is customers voluntarily paying for a clearly described, compliant product.

Commercial positioning recommendation: Sell AlgoOptionX as a trustworthy trading research and risk-discipline platform—not as software promising ₹2,000 monthly profits from a ₹200 subscription.

## 11. Compliance and security

For an Indian trading product, review current SEBI and exchange requirements, including applicability of investment-advice/research rules, retail algorithmic trading requirements, broker API permissions, exchange market-data licensing, redistribution rights, and customer disclosures.

Also address Indian data-protection obligations, payment security, audit retention, cybersecurity, and incident response.

Paper trading does not automatically eliminate regulatory or market-data licensing obligations, especially when using real-time exchange data commercially.

No live trading, customer-specific recommendations, or redistribution of licensed data should be enabled until the applicable requirements have been reviewed.

## 12. Proposed repository structure

```
AlgoOptionX/
├── AGENTS.md
├── openspec/
│   ├── specs/
│   └── changes/
├── .agents/
│   ├── roles/
│   └── skills/
├── harness/
│   ├── orchestrator/
│   ├── approval-gates/
│   ├── evidence/
│   ├── validators/
│   └── threat-tests/
├── apps/
│   ├── web/
│   └── api/
├── packages/
│   ├── ui/
│   ├── contracts/
│   └── design-tokens/
├── services/
│   ├── market-data/
│   ├── market-intelligence/
│   ├── options-intelligence/
│   ├── ai-decision/
│   ├── strategy/
│   ├── risk/
│   ├── paper-execution/
│   ├── portfolio/
│   ├── backtesting/
│   └── model-governance/
├── data/
│   └── synthetic-fixtures/
├── designs/
│   ├── design-system/
│   ├── screens/
│   ├── interactions/
│   └── visual-baselines/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   ├── e2e/
│   ├── property/
│   ├── security/
│   └── trading-invariants/
├── docs/
│   ├── product/
│   ├── architecture/
│   ├── decisions/
│   ├── compliance/
│   └── runbooks/
└── .github/
    └── workflows/
```

This is a proposed logical structure, not a request to create all directories immediately. We should adapt it to the existing repository and avoid unnecessary service boundaries.

## 13. First implementation milestone

The first milestone should deliver a fully tested local-data-driven paper-trading vertical slice.

Acceptance criteria:

1. Start AlgoOptionX locally without Dhan or another paid API.
2. Replay deterministic NIFTY and synthetic options market data.
3. Analyze 5-minute candles with 30-minute confirmation.
4. Generate AI-supported trade or no-trade decisions.
5. Independently validate decisions against risk limits.
6. Execute simulated entries and exits.
7. Reconcile the ₹5,00,000 virtual portfolio.
8. Display trades, decisions, evidence, and performance in an accessible UI.
9. Run automated unit, integration, E2E, and risk-bypass tests.
10. Produce verifiable test evidence and a release-readiness report.

This milestone validates the software architecture and execution pipeline. It does not establish that the strategy is profitable in real markets.

## 14. What should happen next

My recommendation is to begin with a read-only audit of your existing AlgoOptionX repository, then produce three approved artifacts: a complete product requirements specification, a visual UI/UX design system, and an AI development harness implementation plan.

After approval, implementation should proceed through small, independently validated tasks rather than one large AI-generated code change.

The most important business decision is to validate the research and paper-trading experience before investing heavily in live broker integrations and commercial infrastructure. This reduces development cost, limits financial exposure, and gives us real evidence about product quality and customer demand.

Overall assessment: AlgoOptionX is a technically feasible product concept with potential commercial value, but neither strategy profitability nor customer willingness to pay has been demonstrated yet. The enterprise architecture should be built for growth, while investment and implementation remain evidence-driven.

## 15. Reconciliation with the existing AlgoOptionX repository

### 15.1 Verified local baseline and limits

The repository has already undergone a source-layout and paper-workspace revamp. This is a source/evidence review of a local application, not a fresh live-broker audit. Historical statements in older migration documents must not be treated as present-day verification of market data, profitability or external controls.

| Area | Current evidence/status | What the blueprint still requires |
|---|---|---|
| Brand and core stack | AlgoOptionX; React/TypeScript/Vite and Python/FastAPI; `src/` Python packages and a feature-based web application | Preserve the working stack; record measured reasons before replacement |
| Local market foundation | Deterministic synthetic NIFTY/options fixtures, isolated replay, credential-free paper startup | More realistic option pricing, fixture diversity, exchange calendars and explicit data-quality contracts |
| Virtual account | ₹5,00,000 initial virtual funding, integer-paise accounting, fees/slippage, idempotency and preserved event history | Reserved margin and defined-risk multi-leg accounting are not implemented |
| Risk engine | Atomic entry checks, available cash/exposure/position limits, stop/target exits, daily entry lock and kill switch | Blueprint's proposed equity-based limits, stress/gap scenarios, margin models and approved parameter migration |
| Trading decisions | Transparent five-bar synthetic momentum fixture with optional autonomous paper entries | Actual 5-minute/30-minute confirmation, broad knowledge fusion, calibrated learned models and validated decision quality |
| Legacy research | Existing research signal/storage/API modules and regression tests are retained separately | Verify reuse module by module; no current live-data/broker operation is attested here |
| Web workspace | Eight responsive paper/research-workflow screens; persistent Light/Dark/System choice merged in PR #2 | Expanded 12-module enterprise navigation, full interaction/state inventory and WCAG 2.2 AA audit |
| Development harness | 14 role contracts, nine native skills, task baselines, command/report/hash verification and independent handoffs | Expand explicit role/skill coverage and externally enforce release policy where feasible |
| Change-aware testing | `test-changes`, watch mode and conservative Git-driven CI selection implemented in this change set; local evidence exists | Verify this revision's GitHub checks and merge status; do not equate selection with complete test coverage |
| Storage and runtime | Local SQLite databases; single-process local application; original research data kept separately | PostgreSQL, durable workers and monitoring only when hosted/concurrency requirements justify them |
| Models and learning | No validated trained trading model, model registry or automatic promotion | Versioned approved datasets, leakage-safe evaluation, calibration/drift checks, challenger workflow and human-approved promotion |
| Hosted/commercial capability | No SaaS authentication, tenant isolation, subscriptions or commercial feed entitlement system | Validate demand, licensing, security and operations before commercial activation |
| Live execution | Disabled; no production deployment is authorized by this plan | Separate design, regulatory/broker review, external controls and explicit deployment authorization |

Repository references: [README](../../README.md), [layout](../architecture/repository-layout.md), [paper acceptance](../requirements/paper-workspace.md), [harness requirements](../requirements/development-harness.md), and [harness operations](../development/ai-development-harness.md).

Local validation for the change-aware harness on commit `bae879e2104e84e739750304eef8c13f563cac61` recorded **336 Python tests passed, one existing research-fixture skip, six functional browser checks passed**, both frontend builds, configuration validation and lint. The selector/watch regressions were also reviewed in a distinct read-only context. Reports are local ignored evidence, not human approval. Subsequent source or document commits require fresh source-bound evidence; GitHub checks must be observed separately.

### 15.2 Differences that need an explicit task rather than a silent change

| Topic | Blueprint target | Current behavior | Required decision/work |
|---|---|---|---|
| Trade risk | Maximum 0.5% virtual equity (₹2,500 initially) | 1% of initial capital planned stop-risk budget (₹5,000 initially), including modeled costs | Specify equity versus initial-capital basis, fees, gap loss, boundary tests and migration of existing sessions |
| Daily limit | 1% virtual equity (₹5,000 initially) | 2% of initial capital entry-loss lock (₹10,000 initially) | Define daily reset/calendar, realized/unrealized basis, restart behavior and response to open positions |
| Timeframes | 5-minute entry plus completed 30-minute confirmation | Synthetic one-minute advances and a five-bar momentum rule; no 30-minute confirmation | Implement causal aggregation, completed-bar availability and look-ahead regression tests |
| Strategy scope | Buying and defined-risk selling | Long-only paper buying; no spread-margin/reservation model | Begin with buying; separately specify multi-leg max loss, margin, costs and coordinated exits before selling |
| AI claims | Evidence-based intelligence and controlled learning | Deterministic rules; not trained AI probabilities | Keep labels honest; add models only after licensed/versioned data and out-of-sample evaluation |
| Specifications | OpenSpec in the proposed process | Repository-native requirements, ADRs, strict tasks and schemas | Evaluate an OpenSpec adapter with traceability and migration/rollback; do not claim OpenSpec is installed |
| Storage/queues | PostgreSQL, optional TimescaleDB, durable workers | SQLite and local workers | Benchmark and choose based on hosted/concurrent requirements; preserve existing databases during migration |
| UI design | Dedicated image references and approved visuals for every state | Existing screenshots are review candidates; full enterprise screen inventory remains pending | Create state/component specifications, original app designs, accessibility evidence and actual human review |
| Business scores | Provisional judgment-based scores in §10 | No paid-conversion study, independent trading-profit evidence or formal compliance clearance | Retain scores as source hypotheses; replace with measured evidence and dated decisions |

No item in this table is completed merely by accepting this Markdown file.

### 15.3 Keep the current physical architecture; map logical domains to it

The tree in §12 is a logical target, not a directory-creation command. Keep these existing locations:

```text
AlgoOptionX/
├── src/algooptionx/
│   ├── api/                 # credential-free paper API
│   ├── market/              # deterministic fixtures/provider boundary
│   ├── paper/               # risk, execution, ledger and virtual accounting
│   └── research/            # retained Dhan research workflow
├── src/algooptionx_harness/ # CLI, roles, schemas, orchestration, evidence and gates
├── apps/web/src/
│   ├── app/
│   ├── shared/              # reusable UI, theme and shared utilities
│   └── features/            # workspace and retained research UI
├── .agents/skills/
├── tests/{architecture,paper,research,control_plane}/
├── apps/web/tests/          # functional browser checks and visual candidates
├── docs/{product,requirements,architecture,development,guides}/
├── .github/workflows/
└── .harness/                # ignored task baselines, reports and review artifacts
```

New analytics, strategy, dataset, evaluation and model-governance modules should join the modular monolith behind explicit interfaces as needed. Broker/provider adapters must stay outside the deterministic risk/accounting core. Do not split into services, relocate financial data, create empty scaffolding, or migrate storage solely to resemble the proposed tree. Keep `data/paper.db`, `data/dhan_analyzer.db`, ignored credentials and historical evidence intact.

## 16. Coverage catalog and acceptance contracts

### 16.1 Research knowledge backlog

All of §3 remains in scope as a research program. For each capability record: exact definition, required fields/licensing, units, observation/confirmation time, validity window, invalidation rule, confidence limits, test fixtures, evaluation method and a decision to retain/reject it. Distinguish observed data from inferred trader behavior.

| ID | Required knowledge coverage | Minimum evaluation and safety acceptance |
|---|---|---|
| KNOW-01 | HH/HL, LH/LL, break of structure, change of character, support/resistance, supply/demand, liquidity sweeps, breakout/retest, false breaks, consolidation, opening range and VWAP | Causal calculations, touch/window/invalidation definitions, ATR/volatility sensitivity, counterexamples and no future bars |
| KNOW-02 | Double bottom/inverse H&S/ascending triangle/bull flag/hammer/bull engulfing/breakout-retest; double top/H&S/descending triangle/bear flag/shooting star/bear engulfing/breakdown-retest | Formation quality, trend/volume/volatility context, parameter stability and explicit invalidation; detection alone cannot authorize a trade |
| KNOW-03 | Gap continuation, fill, rejection, exhaustion and opening consolidation | Volatility-normalized prior close/open, prior-day levels, opening volume and completed 5/15/30-minute windows, premium/IV response and regime-conditioned evidence; allow no opportunity |
| KNOW-04 | Buyer delta/gamma/momentum/liquidity/IV risk; seller theta/short gamma/hedging/margin/tail/gap risks | Validate pricing assumptions, put-call parity where applicable, max loss and spread costs; OI must not be presented as proof of individual intent |
| KNOW-05 | FOMO/stop clustering/panic/profit booking/overreaction/mean reversion/compression hypotheses | Label behavioral interpretations as hypotheses with observable inputs, uncertainty and falsification criteria |
| KNOW-06 | Volatility surface, implied/realized volatility, Greeks, expected moves, calibration, regimes, microstructure, spreads and execution costs | Unit/property tests, sensible bounds, fixture and benchmark comparisons, ablation tests and out-of-sample incremental contribution |

### 16.2 Decision, execution and data contracts

Each decision must retain dataset/provider and model/rule versions, feature availability timestamps, completed entry/confirmation candles, instrument/expiry identity, proposed action or NO TRADE, evidence, invalidation and expiry time, expected costs, configured risk request, deterministic risk response, execution outcome and trace IDs. If a probability is shown, name the calibrated model and evaluation population; otherwise show a rule score with its meaning.

Risk is independent of natural-language reasoning. Validate integer-paise amounts, quantity/lot metadata effective at decision time, open/reserved exposure, available capital, maximum loss, daily limits, stale data, duplicate requests and kill state inside the economic transaction. AI cannot override rejection. Reconciliation must cover cash, positions, fees, realized/unrealized P&L and, when implemented, reserved margin. An event replay must never duplicate a fill.

Data contracts must define exchange/source event time versus receive time, timezone, calendar/holiday and expiry versions, strike availability, missing/duplicate/out-of-order bars, stale quotes, bid/ask quality, corrections, feature lineage and permissible use. Historical tests must reconstruct what was available then, including delisted/expired contracts and spreads. Simulator results cannot be substituted for licensed historical options performance.

### 16.3 Complete UI and visual-design inventory

Create a design record for every main module in §5 and each actual subpage before implementing it. The first mapping is:

| Blueprint module | Existing workspace relationship | Pending design scope |
|---|---|---|
| Dashboard | Overview | Intelligence and alert priorities, multi-strategy summary |
| Market Intelligence | Market terminal plus separate research views | Structure/gaps/regimes, falsifiable evidence and source quality |
| Chart Workspace | Current chart primitives; retained research charts | Candles, overlays, drawing/interaction states and evidence annotations |
| Options Intelligence | Synthetic chain; separate research chain | OI/Greeks/IV and buyer/seller hypotheses with source/expiry context |
| AI Decision Center | Decision engine | Calibrated-model provenance, NO TRADE and rejection explanations |
| Strategy Lab | Partial overlap with replay | Versioned configurations, validation failures and approval states |
| Paper Trading | Paper portfolio | Order lifecycle, reconciliation, future defined-risk spreads |
| Backtesting | Synthetic Replay lab | Historical/walk-forward results and honest dataset/cost limitations |
| Performance | Performance | Expectancy, tails, regime attribution and sufficient sample context |
| AI Learning Center | Not implemented | Model lineage, drift, challengers, promotion and rollback |
| Trade Journal | Activity & audit | Outcome review, search/filtering and reproducible lesson records |
| Administration | Local Settings only | Future identity, entitlements, billing, audit and permission flows |

For each screen/subpage inventory every tab before/after switching; loading, empty, populated, stale, error, disabled and permission-denied states; dialogs/confirmations/alerts/tooltips; sorting/filtering/pagination/expanded rows; chart overlays/hover/zoom and keyboard equivalents; configuration and validation failures; decision rejection and no-trade states. Capture desktop/tablet/mobile in Light and Dark, plus System preference behavior. Specify navigation, focus order/trapping/return, semantics, non-color status cues, text contrast, zoom/reflow, reduced motion and screen-reader names against WCAG 2.2 AA.

Each design record must map an original image reference to component tokens/props/state contracts, routes, acceptance criteria, functional test IDs and visual profile/hash. A screenshot is a candidate until the user reviews it. Do not mark unimplemented workflows or candidate images approved. Do not copy the source proposal's external illustration assets into the product without verifying rights.

### 16.4 Agent and skill coverage

Keep roles on demand, with scoped access, explicit inputs/outputs, permitted commands, failure conditions and evidence; no permanently running role is required. The 14 existing contracts do not imply all 16 proposed specializations are independently defined.

| Proposed agent | Current mapping / action |
|---|---|
| Product Manager | `product`; retain priorities and commercial evidence |
| Requirement Analyst | Product + `specification` skill; add an explicit analyst contract only if needed |
| Requirement Validator | `requirements-validator` |
| Solution Architect | `architect` |
| UX Architect | `ui-designer`; extend workflow/accessibility design contracts |
| Frontend Engineer | `frontend-engineer` |
| Backend Engineer | `backend-engineer` |
| Quant Researcher | `quant-researcher` |
| Options Domain Specialist | Dedicated role/skill still pending; require pricing/expiry/Greeks expertise and evidence |
| ML Engineer | `ml-engineer`; trained-model pipeline still pending |
| Risk Architect | `risk-engineer` |
| Security Engineer | `security-engineer` |
| QA Engineer | `test-engineer` plus `e2e-engineer` |
| Independent Validator | `independent-validator`, distinct read-only context |
| DevOps Engineer | Current architecture/release responsibilities; dedicated operational contract pending |
| Release Governor | `release-governor`; cannot issue human approval or self-authorize deployment |

Required skill coverage must be made explicit rather than inferred from a similar title:

| Required reusable skill | Existing starting point / remaining work |
|---|---|
| `requirement-analysis` | `specification`; formalize detailed analysis inputs/outputs |
| `requirement-validation` | `specification` and validator role; formalize ambiguity/conflict checks |
| `architecture-review` | `architecture` |
| `ui-design-validation` | `visual-review`; expand accessibility/interaction coverage |
| `react-development` | Generic `implementation`; dedicated framework guidance pending |
| `fastapi-development` | Generic `implementation`; dedicated API/transaction guidance pending |
| `options-domain-analysis` | `quant-research` starting point; dedicated pricing/expiry validation pending |
| `quant-backtesting` | `quant-research`; historical options/walk-forward rigor remains pending |
| `market-data-validation` | Existing research data checks; reusable cross-provider skill pending |
| `risk-control-testing` | `risk-validation` |
| `ml-leakage-prevention` | Quant/ML role scope; explicit dataset/time-split skill pending |
| `security-review` | `security-review` |
| `playwright-testing` | E2E role plus `visual-review`; dedicated functional-test skill pending |
| `evidence-verification` | `evidence-review` |
| `release-readiness` | `release-governance` |

When adding a skill/role, update strict schemas/configuration tests, capability boundaries and documentation. Model deployment, production credentials and human identity remain outside an agent's authority.

### 16.5 Testing and improvement contracts

Retain all categories in §8: unit, property, contract, integration, E2E, visual, data integrity, trading safety, backtesting, ML, security, adversarial and reliability. Add coverage for every new pricing, strategy, provider, model and hosted-security boundary before activating it. A 90-day paper observation period is a minimum research horizon to assess, not an automatic profitability or live-readiness pass; require adequate trade samples across regimes, net expectancy, drawdown, tails, profit factor, calibration and cost sensitivity, with predeclared thresholds and uncertainty.

Keep two separate proposal queues: trading/model improvements and software/product improvements. Record observations, source/data versions, failure analysis, hypotheses, proposed changes and evaluation. Challenger training may run only on approved versioned data; untouched temporal evaluation cannot be reused for tuning. Promotion changes behavior and requires actual human review plus retained evidence and a working rollback. Software telemetry and user feedback propose improvements; they do not authorize arbitrary source edits or deployments.

## 17. Ordered delivery backlog and gates

The roles below are responsibilities, not invented human assignments. Dates and budgets remain unset until effort, data rights and demand are evaluated. Each task needs requirements, scoped paths, protected specification inputs, test commands, recovery steps, independent review and an actual user decision where required.

| Work package | Phase / owner | Depends on | Concrete deliverables and exit gate |
|---|---|---|---|
| PLAN-01 | Phase 0 / product + architect + validator | This blueprint and current source | Dated reusable-module audit, debt/security/data/reliability findings, acceptance traceability; resolve risk/timeframe/scope discrepancies; user reviews the concrete PRD/architecture |
| DESIGN-01 | Phase 0 / UI designer + frontend + independent validator | PLAN-01 | Complete §16.3 state inventory, design system/tokens, original images, component contracts, WCAG audit plan, actual human design review |
| HARNESS-01 | Phase 1 / backend + test + security | Existing harness | Verify change-aware CI and watch behavior, role/skill gap backlog, specification-tool ADR/OpenSpec evaluation, recovery and evidence tamper tests; preserve existing reviewed checks |
| DATA-01 | Phase 1 / quant + backend | PLAN-01, HARNESS-01 | Versioned synthetic fixtures/provider interface, causal 5/30-minute resampling, quality/calendar contracts and deterministic replay tests |
| INTEL-01 | Phase 2 / quant + options specialist + risk | DATA-01 | KNOW-01 through KNOW-06 definitions, benchmark/counterexample fixtures and ablations; reject unsupported hypotheses rather than manufacture confidence |
| PAPER-01 | Phase 3 / backend + risk + QA | DATA-01, chosen INTEL-01 subset, DESIGN-01 | Blueprint-risk configuration implemented safely, trade/no-trade decision records, mandatory 30-minute confirmation, accounting/restart/concurrency and risk-bypass coverage |
| PAPER-02 | Phase 3 / risk + options specialist | PAPER-01 and separate spread design | Defined-risk selling only after max-loss/margin reservation, multi-leg costs/fills/exits, gap/stress behavior and reconciliation tests; no unhedged selling |
| EVAL-01 | Phase 4 / quant + ML + independent validator | DATA-01 and licensed historical rights | Dataset manifests, historical strike/expiry availability, realistic costs, causal features, temporal splits and leakage/walk-forward tests |
| MODEL-01 | Phase 4 / ML + quant + release governor | EVAL-01 | Baseline versus challenger reports, calibration/drift/sample checks, registry/lineage, model approval and tested rollback; no automatic promotion |
| DEMAND-01 | Before substantial Phase 5 spending / product + user | Usable research/paper prototype | 20–30 prospect interviews, opt-in pilot, retention/support/cost evidence, lawful purchase-intent/paid-conversion experiment; revise prices and feature priorities based on results |
| LEGAL-01 | Before licensed/commercial/live activation / qualified reviewers + user | Proposed provider/service scope | Dated SEBI/exchange/broker/API/data-rights/privacy/payment assessment, disclosures, permitted usage and retention obligations; no legal clearance assumed |
| FEED-01 | Phase 5 / backend + security + provider | LEGAL-01, DATA-01 | Licensed read-only provider adapter, entitlement/redistribution checks, stale/correction/rate-limit/reconnect tests and secret rotation |
| SAAS-01 | Phase 5 / architect + security + backend + DevOps | DEMAND-01, LEGAL-01, capacity evidence | Authentication/authorization/tenant isolation, PostgreSQL/queue ADRs and migrations, backup/restore, retention and incident/runbooks; security tests before hosting |
| BILLING-01 | Phase 5 / product + backend + security | DEMAND-01, SAAS-01, payment/tax review | Free/Starter/Pro/Advanced/Enterprise entitlement definitions; idempotent signed payment webhooks, cancellations/refunds and audit; test demand/cost assumptions instead of promising profits |
| OPS-01 | Phases 1–5 as justified / DevOps + security | Measured runtime requirements | Structured tracing/metrics, SLOs, health checks, job recovery, immutable external artifacts where required, backups and restore drills; tested rollback and incident ownership |
| LIVE-01 | Phase 6 / risk + broker specialist + security + qualified reviewers + user | FEED-01, stable paper/evaluation evidence, LEGAL-01, OPS-01, separate design and explicit authorization | Adapter contracts, order deduplication/reconciliation, broker disconnect/retry/cancel/partial-fill behavior, kill/restart/drawdown safeguards and externally enforced deployment controls; live orders remain disabled until all gates pass |

### First vertical-slice milestone: explicit gap assessment

| §13 criterion | Current status | Completion evidence still required |
|---|---|---|
| 1. Credential-free local startup | Implemented | Keep offline startup smoke check current |
| 2. Deterministic NIFTY/options replay | Implemented for simple fixtures | Expand realism and retain deterministic isolated-account tests |
| 3. 5-minute analysis with 30-minute confirmation | Pending | Causal resampling, completion timing and missing-confirmation rejection tests |
| 4. AI-supported trade/no-trade decisions | Partial: transparent rule fixture | Multi-timeframe evidence/rule specification; learned-model claims require validated models |
| 5. Independent risk checks | Implemented for present rules; blueprint values pending | Equity-basis limits, approved configuration and boundary/restart/gap tests |
| 6. Simulated entries and exits | Implemented for long-only buying | Spread execution is a separately gated extension |
| 7. ₹5,00,000 portfolio reconciliation | Implemented for present paper scope | Preserve exact accounting and history tests; add reservation reconciliation when needed |
| 8. Accessible evidence/performance UI | Partial: responsive workspace and theme support | Full WCAG 2.2 AA and enterprise interaction/state review |
| 9. Automated safety/workflow tests | Implemented for local slice; expanded coverage pending | Continue component selection plus full checks for broad changes and each new domain |
| 10. Verifiable evidence/release-readiness report | Local evidence/handoff mechanisms implemented | Current independently reviewed source/evidence, actual human decision and external controls for any deployment |

The milestone is **not complete against the full supplied blueprint** while criteria 3, 4, 5, 8 and external release requirements remain unresolved. An approved document does not close those gaps.

### Business and compliance validation gates

Retain the §10 pricing hypotheses: Free ₹0, Starter ₹199/month, Pro ₹499/month, Advanced ₹999/month and Enterprise custom. Model exchange-data charges, taxes, payment fees, inference/compute, storage, support and compliance costs before setting commercial prices. Track cohort retention, repeated usage, paid conversion, churn and support burden; set experiment success/stop thresholds before collecting results. Do not infer willingness to pay from signups or positive interviews.

Before activating licensed feeds, customer-specific advice, billing or live trading, obtain a dated assessment of applicable SEBI/exchange rules, data redistribution permissions, broker API/algo obligations, Indian privacy requirements, payment security, retention and incident response. Rules must be checked at that future activation date; this plan asserts neither current legal advice nor approval. Use explicit licensed usage boundaries and customer disclosures. Paper trading alone does not establish exemption.

## 18. Master-plan completeness and maintenance

The current [work queue](work-queue.md) includes **INTEL-PLAN-001**, the user's [Trading Knowledge and AI Skills Enhancement](trading-knowledge-ai-skills-enhancement.md) specification. It is queued for read-only audit/planning, with all 15 deliverables mapped to tasks; implementation awaits explicit approval. Its ebook extraction is blocked until the specified reference PDF is available. This item elaborates KNOW-01–06 and related data/decision/paper/evaluation work without authorizing changes to trading behavior.


| Source section | Preserved coverage | Implementation planning reference |
|---|---|---|
| 1. Executive vision | All objectives and evidence-based product principle | §15 status; PLAN-01 and DEMAND-01 |
| 2. Phases 0–6 | Audit through separately approved multi-broker live execution | §17 dependencies and exit gates |
| 3. Trader knowledge A–F | Structure, both pattern directions, gaps, buyers/sellers, psychology and quantitative knowledge | KNOW-01–06; INTEL-01 |
| 4. Decision architecture | Provider→features→intelligence→decision→risk→paper ledger→learning, proposed initial limits and NO TRADE illustration | §15.2 differences; §16.2 contracts; DATA/PAPER/MODEL tasks |
| 5. UI/UX | All 12 modules, subpages/tabs/dialogs/tables/charts/config/errors/rejections, three form factors, themes and WCAG 2.2 AA | §16.3 screen/state and evidence inventory; DESIGN-01 |
| 6. Technologies | All proposed stack choices, modular monolith and broker boundaries | §15.3 current paths; ADR/data/operations gates |
| 7. Agents/skills/harness | All 16 proposed agent responsibilities and 15 required skill examples, verified results and external human authority | §16.4 explicit mappings/gaps; HARNESS-01 |
| 8. Reliability/testing | All 13 test categories, financial invariants, causal historical options and 90-day evaluation | §16.2/16.5; EVAL/PAPER/OPS tasks |
| 9. Improvement | Separate trading and software loops; no silent model deployment | §16.5 challenger and proposal queues; MODEL-01 |
| 10. Business | All segments/plans, provisional scorecard, interviews/pilot/paid-conversion evidence and honest positioning | §17 DEMAND/BILLING and cost validation |
| 11. Compliance/security | Indian regulatory, exchange/data, broker, privacy/payment, retention and response requirements | LEGAL-01, FEED/SAAS/OPS/LIVE gates |
| 12. Repository | Full original logical tree retained without mass scaffold creation | §15.3 mapping to actual modular monolith |
| 13. First milestone | All ten acceptance items retained | §17 item-by-item implementation gaps |
| 14. Next steps | Audit, concrete PRD/design/harness plan, small independently reviewed tasks and demand-first investment | PLAN-01, DESIGN-01 and ordered backlog |

Maintenance rules: attach source commit, data/model versions, test evidence, independent findings and actual human decisions to every implementation status update. Keep Done, Partial, Pending, Blocked and Proposed distinct. Revise captured tasks when scope or protected specifications change; never rewrite old evidence. Resolve contradictory parameters through explicit requirements and tests, not undocumented code edits. Keep all future live/hosted/commercial activation gates visible until evidence and authorization exist.

The source proposal is fully represented in §§1–14. The reconciliation and backlog explain how to follow it without claiming that a local simulator, a passing test suite, or this plan has already delivered an enterprise trading business.

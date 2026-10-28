# AlgoOptionX

A local NIFTY options research and paper-trading workspace. The default application uses a deterministic **synthetic market**, not live exchange prices. It starts with **₹5,00,000 virtual capital** and never submits broker orders.

## Start

Requires Python 3.12+, Node 22.12+ (Node 24 recommended), npm and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --frozen --extra dev
npm --prefix frontend ci
npm --prefix frontend run build
uv run algooptionx
```

The server listens on port 8000. It serves the built React application and API in one process. No broker credentials are required. Use the existing checkout; each cloud task is already isolated and does not need another worktree.

For frontend development, keep the backend running and run `npm --prefix frontend run dev` in another terminal. Vite proxies `/api` to port 8000.

## Workspace

- **Overview:** capital, market chart, decision state, positions and risk.
- **Market terminal:** synthetic call/put chain and virtual buy tickets.
- **Paper portfolio:** long-only virtual positions with automatic stop/target exits.
- **Decision engine:** inspectable five-bar synthetic momentum fixture; optional autonomous entries every six bars.
- **Replay lab:** isolated, repeatable experiments including spread, fees and slippage.
- **Performance:** cash, equity, realized/unrealized P&L and costs.
- **Activity & audit:** decisions/fills/rejections and complete JSON event-chain export.
- **Settings:** session lifecycle and emergency exit controls.

Playback advances one synthetic minute every two real seconds. `+1 bar` advances manually. Restart pauses playback; stored positions and account history survive. Stop/target checks occur only when a bar advances. The kill switch immediately exits virtual positions, disables autonomous entries and blocks new buys. A new session requires all positions closed and preserves previous accounts in SQLite.

## Accounting and assumptions

Money is stored as integer paise. Virtual buys fill at ask + ₹0.05, sells at bid − ₹0.05, with ₹20 per fill. One fixture lot is 65 units; this is **not a claim about current exchange lot sizes**. Entries enforce a 1% planned stop-risk budget, 20% premium exposure cap, at most three distinct contracts, available cash and a 2% session loss entry lock. Stops are 8% below entry, targets 12% above entry. Gaps may exceed planned risk. Market and strategy are deliberately simple fixtures, not realistic options pricing or validated predictive models.

Equity marks open positions at mid; liquidation estimates use bid, slippage and exit fee. Realized P&L includes opening fees. No naked shorts, margin model, partial fills, real exchange settlement or live execution are implemented. These require separate research, approval and testing.

The database is `data/paper.db`; set `ALGOOPTIONX_DB` to override. Stop the server before copying the database for backup. Research data in `data/dhan_analyzer.db` is separate and is never rewritten by paper trading or replay. Replay uses a temporary database and cannot change the active account. Audit hashes are local integrity checks, not externally signed or tamper-proof attestations. This is a single-process, local application: do not expose it as a hosted service without authentication and deployment hardening.

## Validation

```bash
uv run pytest -q -rs
npm --prefix frontend run build
npm --prefix frontend run lint
# Install the browser once on a new development machine:
cd frontend
npx playwright install chromium
npm run test:e2e
```

If Chromium is already installed, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE` to its executable path. The browser suite launches an isolated backend/database on port 8011. It exercises buy/close, playback, autonomous entries, kill protection, replay isolation and all eight routes at desktop, tablet and mobile widths. Screenshots in `frontend/test-results/` are **review candidates**, not human-approved visual baselines. CI uploads test reports and browser traces; hosted branch protections and human release approval must be configured outside the repository.

## Existing Dhan research application

The original algorithms, tests, backend and complete research frontend remain available as an explicit separate workflow:

```bash
npm --prefix frontend run build:research
uv run python -m uvicorn dhan_analyzer.api.app:app --host 127.0.0.1 --port 8000
```

This builds into `frontend/research-dist` and requires the settings described in [DHAN_ANALYZER_README.md](DHAN_ANALYZER_README.md). Keep real credentials in local ignored `.env` or secure environment settings; never commit them. Do not run both servers on the same port. The new paper workspace does not pretend to reproduce the original HLC or Dhan market-data features.

See [architecture](specs/adr/0001-simulator-first.md) and [acceptance traceability](specs/requirements/paper-workspace.md). Licensed historical data, trained models, multi-broker execution, multi-tenant SaaS and externally enforced human approval remain future work. No claim of profitability is made.

## AI development control plane

See [the harness guide](harness/README.md) for specialized agents, skills, task capture, Codex workers, independent handoffs, evidence verification and signed human approval gates.

```bash
uv run algooptionx-harness validate-config
uv run algooptionx-harness init harness/examples/task.template.json --output .harness/tasks/DEV-001
uv run algooptionx-harness status .harness/tasks/DEV-001/task.json
```

The local harness is implemented and tested. You are the human approver here in chat. Independent AI review, evidence and source-bound conversation decisions support the local workflow. Optional signed deployment enforcement requires externally protected identity/key controls; chat records are not forged signatures or deployment authorization.

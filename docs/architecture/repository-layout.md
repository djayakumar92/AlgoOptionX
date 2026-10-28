# AlgoOptionX repository architecture

The repository uses a Python `src/` layout and a separate web application. Production application code does not depend on development orchestration. The default offline paper workspace does not depend on broker research or Dhan credentials.

```text
AlgoOptionX/
├── src/
│   ├── algooptionx/                 # Product application
│   │   ├── api/                    # HTTP composition and strict request contracts
│   │   ├── market/                 # Deterministic synthetic market
│   │   ├── paper/                  # Atomic paper-account workflow and risk checks
│   │   ├── research/               # Existing Dhan-backed research, signals and storage
│   │   └── paths.py                # Shared repository paths; no broker imports
│   └── algooptionx_harness/         # Development control plane, separate namespace
│       ├── agents/                 # Fourteen role contracts
│       ├── schemas/                # Generated strict JSON schemas
│       ├── examples/               # Task and trust-policy templates
│       └── *.py                    # Runner, reviews, approvals, dispatch and CLI
├── apps/web/
│   ├── src/
│   │   ├── app/                    # Workspace composition and application shell
│   │   ├── shared/                 # UI primitives and generic number/money formatting
│   │   ├── features/
│   │   │   ├── workspace/          # API client, types, formatting, panels and pages
│   │   │   └── research/           # Original research UI and its local dependencies
│   │   ├── styles/                 # Shared base styles
│   │   └── main.tsx                # Browser entry; selects workspace/research build
│   └── tests/                      # Functional browser tests and visual candidates
├── config/research.toml            # Non-secret research defaults
├── docs/
│   ├── architecture/               # Layout and architecture decisions
│   ├── development/                # Harness operating instructions
│   ├── guides/                     # User and research guides
│   ├── product/                    # Preserved product requirements
│   └── requirements/               # Acceptance criteria and traceability
├── scripts/windows/                # Workspace and research launchers
├── tests/
│   ├── architecture/               # Dependency, path and packaging boundaries
│   ├── paper/                      # Paper accounting, API, risk and replay
│   ├── research/                   # Existing signal/storage/worker regression suite
│   └── control_plane/              # Harness, approvals, evidence and recovery
├── .agents/skills/                 # Native reusable development skills
├── .github/                       # CI, visual evidence and review ownership
├── README.md                      # Start here
└── AGENTS.md                      # Repository development instructions
```

`data/`, `logs/`, `.env`, `.venv/`, `.harness/`, web dependencies and generated builds remain local/ignored. Database identities are unchanged: paper accounts stay in `data/paper.db`, research stays in `data/dhan_analyzer.db`. This refactor does not migrate, reset or reinterpret financial data.

## Boundaries

- `algooptionx.market` produces deterministic fixtures and has no account, broker or HTTP dependency.
- `algooptionx.paper` consumes those fixtures and owns atomic money/risk transitions. The existing engine and simulator formulas are preserved.
- `algooptionx.api` validates requests and composes the offline app. It never imports `algooptionx.research` or the development harness.
- `algooptionx.research` retains broker adapters, historical research, signals, persistence and the original research API/CLI as a cohesive optional workflow.
- `algooptionx_harness` is tooling, not part of a trading decision. Native skills remain in `.agents/skills/` because agent clients expect that location.
- Web shared UI has no broker access. Workspace API calls, DTOs, formatting and screen components live in their feature. Research-specific hooks, types, charts and styles stay with research.

## Command and path changes

| Previous | Current |
|---|---|
| `frontend/` | `apps/web/` |
| `dhan_analyzer.api.paper_app` | `algooptionx.api.app` |
| `dhan_analyzer.*` research imports | `algooptionx.research.*` |
| `harness.*` Python imports | `algooptionx_harness.*` |
| `harness/agents`, `schemas`, `examples` | `src/algooptionx_harness/{agents,schemas,examples}` |
| `settings.toml` | `config/research.toml` |
| `specs/` and root guides | `docs/architecture`, `docs/requirements`, `docs/guides`, `docs/product` |
| Root Windows launchers | `scripts/windows/start-workspace.bat`, `start-research.bat` |

The stable commands `uv run algooptionx` and `uv run algooptionx-harness` remain available. `uv run algooptionx-research` names the research terminal explicitly; `dhan-analyzer` is retained as a compatibility command. Update scripts that imported the old internal Python packages. Web HTTP routes and API contracts are unchanged.

Use `uv sync --frozen --extra dev` after this layout change to refresh editable imports and console scripts. Browser commands now use `npm --prefix apps/web ...`. The web test server resolves the root virtual environment and `src/` package location from `apps/web`.

Historical `.harness` baselines, evidence and approvals are retained, not rewritten. They describe their original source layout/commit and become stale for changed code. Capture a fresh task using the relocated template for new work. The user remains the sole human approver in chat; moving files does not grant approval or deployment authority.

When upgrading an existing flat-layout editable installation, a stale root-level `algooptionx.egg-info` can shadow the new installed metadata. Archive that generated directory outside import search paths (the current cloud instance retains it under `.harness/migration-backups/`) and rerun `uv sync`. The installed-entrypoint architecture test detects this condition. Fresh checkouts do not contain these ignored caches.

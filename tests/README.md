# Test organization

- `architecture/`: application/tooling dependency boundaries, repository paths and installed entrypoints.
- `paper/`: synthetic paper-account transactions, risk limits, API behavior and deterministic replay.
- `research/`: preserved Dhan research signal, storage and worker regression tests; no broker credentials needed for the suite.
- `control_plane/`: actual subprocess validation, signed and chat review contracts, handoffs, source/evidence integrity and fault recovery.

Run all Python tests from the repository root with `uv run pytest -q -rs`. Functional and visual browser tests are under `apps/web/tests`; run `npm --prefix apps/web run test:all`. Visual snapshots remain review candidates until the human approves them.

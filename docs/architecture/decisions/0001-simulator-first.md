# ADR 0001: AlgoOptionX simulator-first workspace

Status: implemented locally; external QA/release authorization not asserted.

The user authorized the revamp after a read-only audit. The current slice provides a usable offline paper workspace while retaining the original Dhan research implementation as a separate build/server.

Use a modular monolith: React → FastAPI command/state contracts → deterministic synthetic market and long-only transactional engine → SQLite. No LLM or broker can submit virtual fills. Inputs are strict; entries and fills share a `BEGIN IMMEDIATE` transaction, giving concurrent commands one account state. Each client command uses an idempotency key scoped to the account; a reused key with a different request is rejected.

State consists of accounts, active-account pointer, open positions, commands and append-only engine events. Financial changes and event records commit together. All money uses integer paise. The seed and market tick determine synthetic quotes; the explicit tick determines all trading decisions. No future bars are read. Session restart pauses playback; positions and events survive. One process/worker is supported, not distributed scheduling.

The rule is a fixture: every sixth bar, follow a five-bar spot move of at least five points using one long CE/PE fixture lot. The same risk boundary applies to manual and automatic entries. This is neither a trained model nor a claim of market edge. Spread, fixed slippage and fees are charged; partial execution, margin and exchange settlement are out of scope.

Replay uses a separate temporary engine/database. It closes positions at the replay end and reports actual generated results. The existing research ledger is never treated as executed virtual trades.

Local same-origin mutation checks are defense in depth, not authentication. Human-only approval authority, hosted authorization, licensing and production readiness are unverified. A future release requires an externally owned policy verifier and protected deployment credentials. No local `approved` file can replace that.

Rollback: stop the new process, retain/copy `data/paper.db`, rebuild the research frontend and run the original research server. Do not import paper events into research or discard financial history. Keep the new database with its corresponding application version when restoring.

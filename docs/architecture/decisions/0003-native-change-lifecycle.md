# ADR0003 — Additive native engineering change contracts

Status: Phase 1A implementation candidate; human acceptance pending.
Baseline: bdcdfc03be4dd9d9878608c1026ab38f1ab35ad7.

## Decision

Extend the existing Python harness with strict typed change contracts, a single
pinned governance catalog and read-only validation. Keep existing native task,
evidence, handoff and signature payloads unchanged. JSON schemas are derived
from Python models. No official OpenSpec tool or parallel runner is introduced.

The canonical entry point remains AGENTS.md; requirements are in
../../requirements/engineering-control-plane.md. The gate catalog is
config/engineering-governance.json; signer enrollment remains external TrustPolicy.

## Alternatives

A parallel orchestration framework duplicates task capture, source hashing,
execution, report parsing and approval checks already implemented. Markdown-only
status files cannot enforce contract consistency. The selected additive models
reuse those mechanisms without claiming that definitions execute a workflow.

## Trust boundary

A caller-supplied policy pin identifies reviewed bytes, not proof of adoption.
The read-only checker reports verified_contracts, not authorization. It does not
verify actual human decisions, external attestations, DAG execution or lifecycle
transitions. Writable local files cannot prevent an agent directly editing the
checkout. Protected runners, identities, keys and deployment enforcement remain
external and NOT VERIFIED here. Higher risk profiles preserve lower obligations.

## Future lifecycle, not activated

Phase 1B owns state transitions/dependencies; 1C binds native execution, historical
child evidence and fresh aggregate verification; 1D proves a small journal-filter
accessibility change. Parent acceptance must account for every required child.
Historical child results must not masquerade as current-source verification.
Archive/knowledge records go to ignored operational storage to avoid changing
accepted source; promoting durable documentation is a separately reviewed change.

## Compatibility and rollback

Existing CLI commands and eight schemas retain their definitions. The schemas
command adds three outputs and avoids rewriting unchanged schema bytes. Existing
role/skill files and signed payloads are untouched. Remove only additive contracts,
checker and CLI/document references on rollback; retain historical evidence and
financial history. No database migration or runtime/product behavior changes.

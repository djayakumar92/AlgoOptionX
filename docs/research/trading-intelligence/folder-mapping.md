# Proposed folder mapping without unnecessary services

Planning revision 1 · 28 October 2026 · Audited application baseline `ff8027ab8a9a54e6eed2deaef895eab91151145f`. These are concrete engineering proposals and source findings, not a claim of implemented intelligence, profitable models, licensed data rights or human approval. Application source, strategies, dependencies and financial history are unchanged by this package.

## Existing physical boundaries

Keep `src/algooptionx/{api,market,paper,research}`, `src/algooptionx_harness`, `apps/web/src/{app,shared,features}`, `.agents/skills`, existing test domains and docs. This plan creates only documentation artifacts under `docs/research/trading-intelligence`; it does not create an alternate `services/` tree or move databases.

| Proposed logical capability | Future minimal physical placement | Constraints |
|---|---|---|
| Pure market contracts and causal aggregation | `src/algooptionx/market/contracts.py`, `aggregation.py` | No broker SDK/auth imports; explicit availability/calendar |
| Analytical observations and decision contracts | `src/algooptionx/intelligence/{contracts,observations,decision}.py` only when needed | Domain module, not model runtime; no cash/order mutation |
| Verified candle morphology | `src/algooptionx/intelligence/patterns.py` | Approved definitions/sources first; causal complete inputs; no execution |
| Existing structure/regime/option research | Retain `src/algooptionx/research/signals/`; pure adapter only after dependency/semantic review | Avoid hidden imports from broker-connected pipeline into offline app |
| Versioned session risk and audit records | Extend `src/algooptionx/paper/` additively | Preserve integer paise, command idempotency and transaction boundary |
| Dataset/evaluation/model manifests | `src/algooptionx/research/evaluation/` or a scoped pure evaluation package after ADR | Licensed inputs and point-in-time lineage; no active model deployment |
| New UI evidence | Existing workspace feature pages/components and shared theme/UI primitives | Versioned API/client migration, full state specs, no broken routes |
| New tests | `tests/market/`, `tests/intelligence/` only with actual implementation | Selector's unknown-path fallback runs full discovery until explicitly mapped |
| Runtime evidence/baselines | Existing ignored `.harness/tasks`, `.harness/runs`, `.harness/agents` | Preserve immutable source binding; never commit secrets or DBs |
| Book and external references | `docs/references/` only when the actual licensed source is provided | Source missing; do not create a fake PDF or copy copyrighted figures |
| Future hosted/billing/adapters | ADR after demand/legal/security review | No scaffold or Postgres/queue deployment inferred from this map |

## Migration strategy

New paths appear only when an implementation task uses them. Keep packaging discovery and installed entrypoints checked. Any import or schema migration needs forward/backward compatibility evidence. Preserve actual `data/paper.db`, `data/dhan_analyzer.db`, event history, ignored credentials and old report artifacts; no mass renames to match a diagram. README/docs links must work from the final repository layout.

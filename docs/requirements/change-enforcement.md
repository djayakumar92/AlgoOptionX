# Phase 1C native change enforcement

This additive slice binds existing native tasks, selection, execution evidence,
role handoffs, approvals and local closure. It does not add a runner, external
identity service, adapter, broker integration or Phase 1D pilot.

| ID | Required behavior |
|---|---|
| CP1C-BINDINGS | Pin parent/child revisions, policy, template, selected role/skill identities, native task/baseline/candidate, evidence, environment, review, approval and rollback. Reject stale, mixed, duplicate or missing bindings. |
| CP1C-GATES | Use exact native impact selection and full selection at R2/R3. Retain critical tests/skips. Require mandatory gate-specific native role handoffs and native approval stages; unknown gates block. |
| CP1C-HISTORY | Reuse native artifact/outcome/command verification against explicitly pinned historical child snapshots. Do not interpret those as current evidence or authenticated execution. |
| CP1C-AGGREGATE | Account for every mandatory child, ordered dependencies and a contiguous sequential snapshot chain. Require fresh current aggregate evidence and separate declared reviewer, protecting child specifications. |
| CP1C-CLOSURE | Verify existing human decisions; never create them. Acceptance and subsequent archive/knowledge write only to new ignored operational paths. Archive before acceptance, stale inputs and history overwrite fail. |
| CP1C-BOUNDARY | Local chat is procedural only. Privileged purposes require signed external approvals. No deployment/broker authority or external attestation claim. Existing native current-source verifiers remain strict. |

## Threat and bypass classification

| Threat | Local check | External limit |
|---|---|---|
| Fake human approval | Native chat consistency or external Ed25519 signatures | Local chat cannot authenticate actual human origin; key custody external |
| Approval replay | Exact task, baseline/candidate/evidence binding, ordered stages | Protected storage/identity external |
| Unauthorized scope | Native validate_scope, pinned task template and parent scope | Writable filesystem bypass external |
| Missing required tests | Exact native impact selection, critical tests and explicit skips | Protected test runner external |
| Deleted/weakened validation | Pinned policy/template/role/skill inputs and mandatory selector contracts | Writable harness replacement external |
| Fabricated evidence | Native logs/report hashes, parsed outcomes, command identities | Wholesale locally fabricated coherent artifacts NOT VERIFIED |
| Stale evidence | Historical only for children; fresh current aggregate required | Trusted time/runner external |
| Same actor reviewing | Reject native implementer identity and require evidence-linked handoff | Alias/Sybil identity NOT VERIFIED |
| Dependency bypass | Exact child coverage, graph and ordered snapshot chain at closure; dependent dispatch blocked | Arbitrary direct native/tool execution external |
| Failed child acceptance | Native evidence status/outcomes and every-child verification | Protected evidence provenance external |
| Archive before acceptance | Must find exact previously verified acceptance record | Local file authenticity external |
| Broker execution | No broker invocation; privileged purposes require external signatures | Broker credentials/runtime boundary external |
| Financial risk downgrade | Conservative R2/R3 floors, full tests and financial/risk handoff | Protected policy adoption external |
| Market-data omission | Full elevated selection and causal-data review | Scientific correctness not proven by passing tests |
| Unsafe adapters | No adapter launch; existing signed native worker remains authoritative | Actual runtime sandbox external; other adapters unimplemented |
| Policy downgrade/conflict | Existing caller-reviewed policy pin and one catalog | Adoption and external TrustPolicy custody external |

Sequential child evidence is supported; parallel execution orchestration is not
activated. Child capture and independent-role dispatch prepare native inputs only.
Dependent dispatch requires a pinned DependencyProof containing verified native
predecessor runs ending at current source; missing/stale proofs block. Closure
verifies manually sequenced native task runs; no automatic worker scheduler is added.
Phase 1B history commands remain structural inspection, with no authority upgrade.

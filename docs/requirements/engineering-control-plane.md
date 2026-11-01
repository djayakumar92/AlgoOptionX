# Engineering Control Plane v1 — Phase 1A requirements

Status: Phase 1A contracts/inspection only; no lifecycle activation, release authority or product pilot.

| ID | Acceptance | Negative evidence |
|---|---|---|
| CP1A-01 | Strict versioned change, policy and operational-record contracts reject incomplete inputs; source/document/template identities are pinned | Extra/duplicate fields, boolean versions, unknown versions, malformed hashes and unsafe paths rejected |
| CP1A-02 | One governance policy path, explicitly pinned by caller, defines risk floors and mandatory gates; it is distinct from external signer TrustPolicy | Conflicting identity, stale policy pin and alternate authority rejected |
| CP1A-03 | Effective risk is the maximum of requested risk and all overlapping source rules; broad scopes include sensitive descendants | Self-declared R0 cannot hide R2/R3 paths; unknown scopes/components fail closed |
| CP1A-04 | Valid child templates are checked through existing Task v1, with parent scope, exact requirement coverage, role/skill discovery and protected change/policy inputs | Broadened child scope, missing Python/browser requirements or unprotected inputs rejected |
| CP1A-05 | Human approval obligations are checked as data, with actual authorization explicitly unverified; privileged automation requires signed-external requirements | Missing stages, incompatible assurance, self-review and completed blocking findings rejected |
| CP1A-06 | change-validate is read-only, bounded and source-stable; rejects invalid inputs without echoing payloads | Symlinks, oversized/duplicate JSON, source drift and sensitive malformed inputs fail |
| CP1A-07 | Existing Task/Evidence/Approval/Handoff models, signatures, eight schemas, roles and skills remain compatible | Golden schemas and existing control-plane suite remain passing; no signature rewriting |
| CP1A-08 | Report only verified contracts/required gates; no execution, lifecycle, archive, human-origin or external-enforcement claim | No transitions, child orchestration or pilot performed; missing external controls remain NOT VERIFIED |

## Canonical authority

AGENTS.md is the entry point. Product requirements and ADRs remain in docs/.
The machine gate/risk catalog is config/engineering-governance.json. Agent JSON
and native skills retain their existing authority. External TrustPolicy owns
signer enrollment; a repository policy cannot enroll humans or grant deployment.

The expected policy SHA-256 is an explicit caller input. A matching pin proves
bytes, not human adoption. Do not silently replace it with a candidate-derived
pin and call the candidate approved. Actual conversation approval is procedural;
external automation requires separately protected identity/key/runtime controls.

## Contract lifecycle and compatibility boundary

Changes have immutable IDs/revisions and pinned proposal, requirement, design
and child-template inputs under docs/changes/<ID>/r0001/. Child tasks use existing
native templates; capture and execution remain existing harness concerns.

Intent bindings exclude the eventual captured task digest; captured bindings
reference the intent and native task digests, avoiding circular identities.
Operational records express source/policy/evidence/review/approval/rollback/archive
references, but their schema validity does not establish event authenticity.

Lifecycle transition enforcement and full DAG validation are Phase 1B. Execution,
parent evidence aggregation and closure are Phase 1C. The UI pilot is Phase 1D.
Do not infer these capabilities from Phase 1A record schemas. A different actor
string alone does not prove independence; an attestation reference is not a
verified attestation. Archive/knowledge records must not rewrite accepted source.

Phase 0 evidence remains historical after its commit: canonical snapshots include
HEAD. Source equivalence is separate from trusted execution provenance.

## Validation and safety

Use existing isolated tasks/runs, filtered credential-free test subprocesses and
separate read-only review. Preserve failed checks/skips. No installs, broker APIs,
financial changes, migrations, commits, pushes or later-phase work are included.
Rollback reverses only these additive files/CLI/doc changes and preserves history.

# ADR0002 — Native specification authority and an explicit reference crosswalk

Date:29October2026. Status: implemented native crosswalk; OpenSpec CLI adoption deferred pending a separately reviewed tool evaluation. Scope:GOV-01.

## Context and evidence

AlgoOptionX already has requirements/ADRs, strict captured tasks, protected specification inputs, source snapshots, bounded validation, evidence hashes and independent handoffs. The master plan mentions OpenSpec and also says to preserve working technology unless an audit demonstrates a reason to replace it. The current environment has no `openspec` command on PATH, and the project's dependency manifests do not declare an OpenSpec toolchain. No OpenSpec package is installed, run or certified by this change.

The missing gap we can close now is traceability between exact requirement IDs, pinned document contents and the existing captured task. A second untrusted `approved:true` specification system would weaken rather than strengthen authority. Framework-specific change documents can contribute requirements without becoming a signer or another execution gate.

## Alternatives evaluated

| Alternative | Benefit | Cost / unresolved evidence | Decision |
|---|---|---|---|
| Replace native tasks/requirements with a new specification framework immediately | Potential standardized change/delta workflow | Requires tool/version/format evaluation, migration of evidence/approval bindings, duplicate-source resolution and new dependencies; no demonstrated current blocker | Do not replace working governance |
| Keep disconnected native documents without pinned mappings | No new tool | Requirement identity/source drift and optional task protection not independently cross-checked | Insufficient traceability |
| Native authoritative tasks plus a strict read-only reference crosswalk | Pin requirement ID/path/hash; verify captured-task coverage/protected inputs; preserve existing runtime and authority | Lexical/structural checks do not prove requirement quality or external format conformance | Implement now |

## Decision

Add `validate-spec-map` with a versioned JSON mapping. Each ID is unique and references a Markdown file under `docs/` or `openspec/` with an explicit SHA-256. Validate current bytes, bounded file size, safe contained paths, no symlinks and an exact ID token. Optionally bind to a real captured task: current baseline/scope must validate, requirement sets must match exactly, and mapped files must be protected inputs. Include source/task/mapping digests in output. No execution commands, signatures or approval flags can be supplied through this map.

`source_format: openspec-layout` is a descriptive label for a reference mapping, not a parser/certification of OpenSpec proposals, scenarios or deltas. Output explicitly records `external_tool_conformance: not_verified`. Native requirements and captured tasks remain authoritative. The checker proves references/hashes/bindings, not semantic completeness, legal validity, human identity or approval.

An eventual actual OpenSpec tool adapter requires a pinned version, verified upstream format, frozen dependency/tool installation review, a roundtrip example preserving IDs/protected inputs and independent evidence. It must not invent a second approval authority, silently change commands, or claim a deployment permission. That activation is not done here.

## Skills and responsibilities

Expand native packages from9 to23 while retaining all old names/workflows. All15 requested specializations now have explicit Inputs, Outputs, Allowed actions, Validation, Failure conditions and Evidence. Existing14 roles reference only relevant packages; sandbox values, allowed tools, forbidden actions and human_approval_authority remain unchanged. Logical requirements/options/DevOps responsibilities can be delegated through roles/skills without adding permanent agents or changing the strict role enum.

Configuration checking validates identity and required contract sections for referenced skills. This is a structural check, not proof that prose or an external agent obeys policy. Underlying sandbox, actual task scope, signed external gates where configured and real human decisions remain the authority boundary.

## Acceptance and rollback

Test reference roundtrip, stale hashes, absent/prefix-confused IDs, duplicate/extra fields, path traversal/symlinks, mismatched/unprotected task inputs, skill contract gaps and unchanged role privileges. Preserve command exit/report/hash verification and no self-issued approval. A verified mapping grants no deployment.

Rollback can remove the additive CLI/crosswalk and new skill routing, restoring prior role skill lists; retain captured tasks, evidence, requirement documents and all financial history. Old aliases are preserved to avoid gratuitous breakage. No application database, model, broker or active strategy is changed.

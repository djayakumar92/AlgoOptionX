# Development control-plane requirements

These requirements concern the development system, not a trading-model accuracy claim.

| ID | Acceptance predicate | Evidence |
|---|---|---|
| HARNESS-01 | Fourteen specialized roles have validated tool/sandbox boundaries and reusable skill instructions; writing workers need implementation authorization | configuration/schema tests, worker adapter tests |
| HARNESS-02 | Plan, architecture, UI when affected, implementation, independent AI QA and the user’s human release review are ordered and revision-bound; optional external signed gates reject tampering | real Ed25519 verification plus negative approval tests |
| HARNESS-03 | Required commands retain underlying exit status, test identities/skips, hashes and current source binding; stale/missing/zero-test results fail | real pytest process, report parsing, mutation/tamper/timeout/recovery tests |
| HARNESS-04 | Handoffs bind task, source, assigned role, requirements and artifact hashes; independent review cannot be the implementer or claim unresolved high-severity work complete | handoff and QA/release-gate tests |
| HARNESS-05 | Visual checks compare deterministic screenshots at desktop/tablet/mobile and dialog state, with explicit human design approval separate from baseline capture | 25 screenshot comparisons and baseline manifest; explicit human UI review in chat for local work; signed UI receipt for external release automation |

| HARNESS-06 | Git changes select conservative test suites, local watch mode initiates bounded tests after stable edits, and push/PR CI runs the same selection; rename/deletion/untracked paths, missing ancestry, unknown files, failures and stale evidence cannot silently skip validation | change-selection and watcher regression tests; source-bound harness and CI reports |

Trusted runtime, external policy/key custody, remote branch protection and deployment reviewer identity are prerequisites, not properties a local repository can prove. A local passing test or AI-authored manifest is never human approval. The repository must report external absence as BLOCKED/NOT VERIFIED, never auto-approve it.

The user has chosen to be the sole human approver in this chat. Conversation decisions are procedural records, not cryptographic identity attestations. A second human reviewer is optional and is not a prerequisite for local development. No future approval is inferred from this preference.

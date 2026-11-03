# Enterprise SaaS implementation — active work

The user authorized continuing the full enterprise SaaS roadmap on 3 November
2026. The existing local product changes remain uncommitted. Implementation is
proceeding in dependency order; validation is deferred until the implementation
batch is ready, following the user's instruction. Source presence is not runtime
readiness, human acceptance, commercial activation or deployment approval.

## Current implementation sequence

1. Accounts, recovery, verification, sessions, CSRF and tenant ownership.
2. Workspace memberships and isolated paper/demo engine routing.
3. Entitlements, usage-credit/payment ledgers and provider integration boundaries.
4. Server-persisted workspaces/strategy versions and richer charting.
5. Quote-driven paper order lifecycle, reservations and reconciliation.
6. Historical research/jobs, grounded AI and operational administration.
7. Broker credential lifecycle and production readiness assessment.

## External activation dependencies

- Verified production email delivery and public HTTPS origin.
- Payment provider credentials, approved prices, taxes and commercial policies.
- Licensed market/historical data and authoritative instrument/charge/margin rules.
- Broker account authorization and encryption-key management.
- Production database/hosting, security assessment and operational ownership.
- Separate deployment, payment activation and real-money execution authorization.

No production-readiness percentage or completion is inferred from local features.
SQLite-backed tenant runtimes are a local/single-process bridge; hosted scale and
PostgreSQL migration require their own verified delivery before SaaS activation.

## Current source implementation (3 November 2026)

- Customer signup/login, opaque sessions/CSRF, verification/recovery and optional
  encrypted TOTP enrollment with single-use recovery codes.
- Tenant membership/invitations, viewer restrictions, per-tenant engine routing,
  stale-tab identity checks and transaction-time account identity checks.
- Sandbox payment intents, signed capture/refund events, independent paid periods,
  balanced cash/credit postings, usage reservations and owner reconciliation.
  Checkout stays disabled without explicit test-provider configuration and prices.
- Tenant-owned chart layouts, validated drawings, multi-pane synthetic charts and
  immutable no-code strategy versions.
- A separate quote-cycle paper execution book: market/limit/stop/stop-limit orders,
  modeled one-lot partial fills, cancel/modify, closing/emergency controls, startup
  recovery, preserved accounts, ledger reconciliation and exports.
- Durable causal synthetic rule-replay jobs with input hashes, cancellation,
  source/version provenance and JSON export. These are not historical backtests.
- Optional grounded external AI narratives: consent, plan/credit checks, immutable
  evidence, citation validation, usage settlement and interrupted-job recovery.
  No provider is activated in this environment; model prose remains unverified.
- Encrypted user-owned Dhan credential lifecycle with an explicit read-only test;
  no live-order adapter, feed entitlement or provider revocation is inferred.
- Owner workspace operations view with truthful configuration/dependency status.

The 19 focused backend checks passed before the final source additions; a current
scoped validation run is still required. Python compilation, TypeScript checking
and the customer app build passed. Browser journeys, full current evidence and
independent final review remain pending; earlier local-product evidence does not
validate this enterprise batch.

## Implementation still required before enterprise completion

Production PostgreSQL migrations and shared-worker coordination; restore-tested
backups, retention and complete tenant audit logging; licensed historical datasets
and quote-driven historical/walk-forward evaluation; advanced strategy deployment,
OCO/trailing/expiry settlement and authoritative instrument/charges/margin rules;
parameterized chart indicators and incremental streaming; recurring billing,
finalized invoices/tax policy and approved plan limits; provider deployment,
security/load/accessibility testing and human operational acceptance. Model
training, drift evaluation and promotion controls remain separate research work.

These are actual outstanding engineering and external prerequisites. The local
source additions above do not make the full enterprise roadmap 100% complete.

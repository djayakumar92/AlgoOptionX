"""Tenant operator visibility. Never a cross-tenant platform-admin bypass."""
import os
from fastapi import APIRouter, Request
from .api import owner

router = APIRouter(prefix='/api/operations')


@router.get('/readiness')
def readiness(request: Request):
    user = owner(request)
    identity = request.app.state.identity
    with identity.tx() as c:
        members = c.execute('SELECT COUNT(*) FROM memberships WHERE tenant_id=? AND active=1', (user['tenant_id'],)).fetchone()[0]
        jobs = {row['status']: row['count'] for row in c.execute('SELECT status,COUNT(*) count FROM research_jobs WHERE tenant_id=? GROUP BY status', (user['tenant_id'],))}
        workspaces = c.execute('SELECT COUNT(*) FROM saved_workspaces WHERE tenant_id=? AND archived=0', (user['tenant_id'],)).fetchone()[0]
        strategies = c.execute('SELECT COUNT(*) FROM saved_strategies WHERE tenant_id=? AND archived=0', (user['tenant_id'],)).fetchone()[0]
        events = [dict(row) for row in c.execute('SELECT event,created_at FROM security_events WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT 100', (user['user_id'],))]
    runtime = request.app.state.tenants
    hosted = request.app.state.require_auth
    checks = [
        {'id': 'storage', 'status': 'local_only', 'detail': 'SQLite tenant databases and a single-process worker. Production PostgreSQL migration, shared worker coordination, backup restoration and retention verification are pending.'},
        {'id': 'authentication', 'status': 'configured' if hosted else 'local_evaluation', 'detail': 'Verified accounts are required for workspaces.' if hosted else 'Anonymous synthetic demo is permitted. Customer resources require a signed-in account.'},
        {'id': 'cookies', 'status': 'configured' if request.app.state.secure_cookies else 'local_only', 'detail': 'Secure cookie transport enabled.' if request.app.state.secure_cookies else 'Development HTTP cookies. HTTPS and secure cookies are required before hosting.'},
        {'id': 'email', 'status': 'configured_unverified' if identity.mail.mode == 'smtp' else 'local_only', 'detail': 'SMTP settings exist; end-to-end delivery requires verification.' if identity.mail.mode == 'smtp' else 'Protected local email outbox. No public email delivery is configured.'},
        {'id': 'encryption', 'status': 'configured_unverified' if os.environ.get('ALGOOPTIONX_SECRET_KEY') or os.environ.get('ALGOOPTIONX_SECRET_KEYS') else 'local_only', 'detail': 'Encryption-key configuration requires rotation and restore verification. Secret values are never returned.'},
        {'id': 'payments', 'status': 'sandbox_configured' if request.app.state.commerce.provider.configured else 'disabled', 'detail': 'Sandbox only. Live payments, recurring subscriptions and finalized tax invoices are unavailable.'},
        {'id': 'market_data', 'status': 'synthetic_only', 'detail': 'No licensed live/historical feed or authoritative exchange margin and settlement source is configured.'},
        {'id': 'paper_worker', 'status': 'degraded' if user['tenant_id'] in runtime.execution_errors or user['tenant_id'] in runtime.errors else 'available' if request.app.state.background_enabled else 'disabled', 'detail': runtime.execution_errors.get(user['tenant_id']) or runtime.errors.get(user['tenant_id']) or 'Local worker status; pending orders use modeled quote-cycle liquidity.'},
        {'id': 'research_worker', 'status': 'degraded' if request.app.state.job_worker_error else 'available' if request.app.state.background_enabled else 'disabled', 'detail': request.app.state.job_worker_error or 'Queued synthetic replays are processed from immutable input snapshots.'},
        {'id': 'ai', 'status': 'degraded' if request.app.state.ai_worker_error else 'configured_unverified' if request.app.state.ai.provider.configured else 'disabled', 'detail': request.app.state.ai_worker_error or 'External narrative processing requires configured provider/model, approved credit cost, an eligible plan and per-request consent. No execution tools exist.'},
        {'id': 'live_execution', 'status': 'disabled', 'detail': 'No live-order submission adapter or deployment authority is active.'},
    ]
    return {'tenant_name': user['tenant_name'], 'production_ready': False, 'checks': checks, 'counts': {'active_members': members, 'saved_layouts': workspaces, 'saved_strategies': strategies, 'research_jobs': jobs}, 'your_security_events': events, 'notice': 'Configuration and local consistency are not independent security, operational or release approval.'}

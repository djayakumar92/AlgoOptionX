"""AlgoOptionX offline paper workspace. Run with uvicorn ...paper_app:app."""

from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from algooptionx.api.contracts import Command, Replay, SessionRequest

from algooptionx.paths import PROJECT_ROOT
from algooptionx.paper.engine import Engine, PaperError
from algooptionx.demo.engine import DemoEngine, DemoError
from algooptionx.demo.api import router as demo_router
from algooptionx.saas.identity import IdentityStore, IdentityError
from algooptionx.saas.runtime import TenantRuntime
from algooptionx.saas.commerce import Commerce
from algooptionx.saas.resources import ResourceStore, router as resources_router
from algooptionx.saas.market_api import router as market_router
from algooptionx.saas.execution_api import router as execution_router
from algooptionx.saas.mfa import router as mfa_router
from algooptionx.saas.ai import AiStore, router as ai_router
from algooptionx.saas.operations import router as operations_router
from algooptionx.saas.jobs import JobStore, router as jobs_router
from algooptionx.saas.brokers import BrokerStore, router as brokers_router
from algooptionx.saas.billing_api import router as billing_router
from algooptionx.saas.api import router as identity_router, SESSION_COOKIE, csrf_valid, require_tenant_context


def create_app(db_path: str | Path | None = None, background: bool = True, demo_db_path: str | Path | None = None, identity_db_path: str | Path | None = None, require_auth: bool | None = None, secure_cookies: bool | None = None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.engine = Engine(
            db_path
            or os.environ.get("ALGOOPTIONX_DB", str(PROJECT_ROOT / "data" / "paper.db"))
        )
        paper_path = Path(app.state.engine.path)
        default_demo = PROJECT_ROOT / 'data' / 'demo.db' if paper_path.resolve() == (PROJECT_ROOT / 'data' / 'paper.db').resolve() else paper_path.with_name('demo-' + paper_path.name)
        app.state.demo = DemoEngine(demo_db_path or os.environ.get('ALGOOPTIONX_DEMO_DB') or default_demo,
            forbidden_paths=[paper_path, PROJECT_ROOT / 'data' / 'paper.db', PROJECT_ROOT / 'data' / 'dhan_analyzer.db'])
        app.state.identity = IdentityStore(identity_db_path or paper_path.with_name("identity-" + paper_path.name))
        app.state.commerce = Commerce(app.state.identity)
        app.state.resources = ResourceStore(app.state.identity)
        app.state.jobs = JobStore(app.state.identity)
        app.state.ai = AiStore(app.state.identity,app.state.commerce)
        app.state.brokers = BrokerStore(app.state.identity)
        app.state.tenants = TenantRuntime(paper_path.parent / ("tenants-" + paper_path.stem))
        app.state.require_auth = require_auth if require_auth is not None else os.environ.get("ALGOOPTIONX_REQUIRE_AUTH") == "1"
        app.state.identity.secure_keys_required = app.state.require_auth
        app.state.secure_cookies = secure_cookies if secure_cookies is not None else os.environ.get("ALGOOPTIONX_SECURE_COOKIES", "1" if app.state.require_auth else "0") == "1"
        with app.state.identity.tx() as c:
            tenant_ids = [row[0] for row in c.execute('SELECT id FROM tenants')]
        app.state.tenants.recover(tenant_ids)
        stop = threading.Event()

        def worker():
            while not stop.wait(2):
                try:
                    if not app.state.worker_error:
                        app.state.engine.pulse()
                except Exception:
                    # Fail closed: report degraded health and stop automatic playback.
                    app.state.worker_error = "Playback stopped after a storage or engine error. Restart after diagnosis."
                app.state.tenants.pulse()
                app.state.tenants.process_execution()
                try:
                    app.state.jobs.process()
                    app.state.job_worker_error = None
                except Exception:
                    app.state.job_worker_error = "Research worker unavailable. Queued inputs are preserved."

        def ai_worker():
            while not stop.wait(2):
                try:
                    app.state.ai.process()
                    app.state.ai_worker_error = None
                except Exception:
                    app.state.ai_worker_error = "AI worker stopped on an uncertain provider or storage outcome. Preserve reports and usage reservations for reconciliation."
                    return

        app.state.ai_worker_error = None
        app.state.background_enabled = background
        app.state.worker_error = None
        app.state.job_worker_error = None
        thread = threading.Thread(target=worker, daemon=True)
        ai_thread = threading.Thread(target=ai_worker, daemon=True)
        if background:
            thread.start()
            ai_thread.start()
        yield
        stop.set()
        if background:
            thread.join(timeout=20)
            ai_thread.join(timeout=25)

    app = FastAPI(title="AlgoOptionX", version="0.2.0", lifespan=lifespan)

    app.include_router(demo_router)
    app.include_router(identity_router)
    app.include_router(billing_router)
    app.include_router(resources_router)
    app.include_router(market_router)
    app.include_router(execution_router)
    app.include_router(mfa_router)
    app.include_router(brokers_router)
    app.include_router(jobs_router)
    app.include_router(operations_router)
    app.include_router(ai_router)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # Pydantic inputs can contain passwords/tokens. Never echo them in errors.
        return JSONResponse({"detail": "Invalid request fields.", "fields": [
            {"location": list(error["loc"]), "type": error["type"]} for error in exc.errors()
        ]}, status_code=422)

    @app.exception_handler(IdentityError)
    async def identity_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=exc.status)

    @app.exception_handler(DemoError)
    async def demo_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.middleware("http")
    async def local_commands(request: Request, call_next):
        # Same-origin mutation and opaque-session checks precede domain routing.
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            allowed = {request.headers.get("host")}
            if not app.state.require_auth:
                allowed.update({"127.0.0.1:5173", "localhost:5173"})
            if origin and urlsplit(origin).netloc not in allowed:
                return JSONResponse(
                    {"detail": "Cross-origin commands are not allowed."},
                    status_code=403,
                )
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse(
                    {"detail": "Cross-site commands are not allowed."}, status_code=403
                )
        token = request.cookies.get(SESSION_COOKIE)
        user = await run_in_threadpool(app.state.identity.authenticate, token)
        request.state.principal = user
        request.state.paper_engine = app.state.engine
        request.state.demo_engine = app.state.demo
        request.state.worker_error = app.state.worker_error
        path = request.url.path
        financial = path in {"/api/workspace", "/api/commands", "/api/sessions", "/api/replay", "/api/audit/export"} or (path.startswith("/api/demo/") and path != "/api/demo/health") or (path.startswith("/api/market/") and path != "/api/market/capabilities") or path.startswith("/api/execution/")
        mutation = request.method not in ("GET", "HEAD", "OPTIONS")
        identity_public = path == "/api/billing/webhook" or path in {"/api/identity/register", "/api/identity/login", "/api/identity/request-reset", "/api/identity/reset-password", "/api/identity/verify-email"}
        context_sensitive = path.startswith("/api/ai/") or path.startswith("/api/operations/") or path.startswith("/api/jobs") or financial or path.startswith("/api/brokers") or path.startswith("/api/execution/") or path.startswith("/api/resources/") or (path.startswith("/api/billing/") and path not in {"/api/billing/plans", "/api/billing/webhook"}) or (mutation and path.startswith("/api/identity/") and not identity_public)
        if context_sensitive and request.headers.get("x-algooptionx-client") == "browser-v1":
            expected_tenant = request.headers.get("x-expected-tenant")
            expected_user = request.headers.get("x-expected-user")
            if expected_tenant != (user["tenant_id"] if user else None) or expected_user != (user["user_id"] if user else None):
                headers = {"Cache-Control": "no-store"}
                if user:
                    headers.update({"X-AlgoOptionX-Tenant": user["tenant_id"], "X-AlgoOptionX-User": user["user_id"]})
                return JSONResponse({"detail": "Account or workspace changed in another tab. Reload and review this action again."}, status_code=409 if user else 401, headers=headers)
        if financial and not user and (token or app.state.require_auth):
            return JSONResponse({"detail": "Sign in to access your workspace."}, status_code=401)
        if user and mutation and path.startswith("/api/") and not identity_public and not csrf_valid(request, user):
            return JSONResponse({"detail": "Your security token is missing or expired. Reload before retrying."}, status_code=403)
        verified_workspace = financial or path.startswith(("/api/ai/", "/api/resources/", "/api/jobs", "/api/brokers"))
        if verified_workspace and user and app.state.require_auth and not user["email_verified"]:
            return JSONResponse({"detail": "Verify your email before accessing the workspace."}, status_code=403)
        if financial and user:
            if app.state.require_auth and not user["email_verified"]:
                return JSONResponse({"detail": "Verify your email before accessing the workspace."}, status_code=403)
            if mutation and user["role"] == "viewer" and path not in {"/api/demo/preview", "/api/demo/research", "/api/replay"}:
                return JSONResponse({"detail": "This workspace membership is read-only."}, status_code=403)
            request.state.paper_engine, request.state.demo_engine = await run_in_threadpool(app.state.tenants.get, user["tenant_id"])
            request.state.worker_error = app.state.tenants.errors.get(user["tenant_id"])
        response = await call_next(request)
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            if user:
                response.headers["X-AlgoOptionX-Tenant"] = user["tenant_id"]
                response.headers["X-AlgoOptionX-User"] = user["user_id"]
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.exception_handler(PaperError)
    async def domain_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.get("/api/health")
    def health():
        return {
            "status": "degraded" if app.state.worker_error else "ok",
            "name": "AlgoOptionX",
            "source": "SYNTHETIC",
            "mode": "PAPER",
        }

    @app.get("/api/workspace")
    def state(request: Request):
        return request.state.paper_engine.state() | {"worker_error": request.state.worker_error, "tenant_id": request.state.principal["tenant_id"] if request.state.principal else None}

    @app.post("/api/commands")
    def command(body: Command, request: Request):
        if request.state.worker_error:
            raise HTTPException(503, request.state.worker_error)
        require_tenant_context(request, body.expected_tenant_id)
        values = body.model_dump(exclude_none=True)
        values.pop("expected_tenant_id", None)
        expected_account = values.pop("expected_account_id", None)
        if request.state.principal and not expected_account:
            raise HTTPException(422, "The displayed account identity is required.")
        key, action = values.pop("key"), values.pop("action")
        fields = {
            "buy": {"instrument", "lots"},
            "close": {"position_id"},
            "advance": set(),
            "control": {"running", "autonomous", "killed"},
        }
        if action not in fields or set(values) - fields[action]:
            raise HTTPException(422, "Command fields do not match the action.")
        if (
            action == "buy"
            and "instrument" not in values
            or action == "close"
            and "position_id" not in values
        ):
            raise HTTPException(422, "Missing command target.")
        if expected_account is not None:
            values["expected_account_id"] = expected_account
        return request.state.paper_engine.command(key, action, **values)

    @app.post("/api/sessions")
    def new_session(request: Request, body: SessionRequest | None = None):
        require_tenant_context(request, body.expected_tenant_id if body else None)
        if request.state.principal and (not body or not body.expected_account_id):
            raise HTTPException(422, "The displayed account identity is required.")
        return request.state.paper_engine.new_session(expected_account_id=body.expected_account_id if body else None)

    @app.get("/api/audit/export")
    def export(request: Request):
        # Export the complete chain, not the paginated workspace feed.
        with request.state.paper_engine.tx() as c:
            account = request.state.paper_engine._account(c)
            import json

            events = [
                dict(e) | {"payload": json.loads(e["payload"])}
                for e in c.execute(
                    "SELECT * FROM events WHERE account_id=? ORDER BY seq",
                    (account["id"],),
                )
            ]
        return JSONResponse(
            {"name": "AlgoOptionX", "account_id": account["id"], "events": events},
            headers={
                "Content-Disposition": 'attachment; filename="algooptionx-audit.json"'
            },
        )

    @app.post("/api/replay")
    def replay(body: Replay, request: Request):
        require_tenant_context(request, body.expected_tenant_id)
        # Separate DB and account: replay cannot mutate the active paper session.
        with TemporaryDirectory(prefix="algooptionx-replay-") as tmp:
            engine = Engine(Path(tmp) / "replay.db")
            engine.command("auto", "control", autonomous=True)
            curve = []
            for index in range(body.bars):
                engine.command(f"bar-{index}", "advance")
                snapshot = engine.state()
                curve.append(
                    {"tick": index + 1, "equity": snapshot["account"]["equity"]}
                )
            for p in snapshot["positions"]:
                engine.command(f"close-{p['id']}", "close", position_id=p["id"])
            final = engine.state()
            curve[-1]["equity"] = final["account"]["equity"]
            exits = [
                e["payload"]["pnl"] for e in final["events"] if e["kind"] == "SELL"
            ]
            peak, drawdown = 50_000_000, 0
            for row in curve:
                peak = max(peak, row["equity"])
                drawdown = max(drawdown, peak - row["equity"])
            return {
                "source": "SYNTHETIC",
                "bars": body.bars,
                "seed": 17,
                "strategy": "SYNTHETIC_MOMENTUM_V1",
                "pnl": final["account"]["pnl"],
                "fees": final["account"]["fees"],
                "trades": len(exits),
                "wins": sum(p > 0 for p in exits),
                "max_drawdown": drawdown,
                "curve": curve,
                "disclaimer": "Synthetic fixture replay only. Not historical market performance. No predictive accuracy or profitability has been established.",
            }

    dist = (PROJECT_ROOT / "apps" / "web" / "dist").resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "Unknown API route.")
        candidate = (dist / path).resolve()
        if not candidate.is_relative_to(dist):
            raise HTTPException(404)
        if candidate.is_file():
            return FileResponse(candidate)
        if path.startswith("assets/") or Path(path).suffix:
            raise HTTPException(404)
        index = dist / "index.html"
        if not index.is_file():
            raise HTTPException(
                503, "Build the frontend with npm run build in apps/web/."
            )
        return FileResponse(index)

    return app


app = create_app()


def run():
    import uvicorn

    uvicorn.run("algooptionx.api.app:app", host="127.0.0.1", port=8000)

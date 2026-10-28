"""AlgoOptionX offline paper workspace. Run with uvicorn ...paper_app:app."""

from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from dhan_analyzer.config import PROJECT_ROOT
from dhan_analyzer.paper.engine import Engine, PaperError


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    key: str = Field(min_length=1, max_length=160)
    action: str
    instrument: str | None = None
    position_id: str | None = None
    lots: int | None = Field(default=None, ge=1, le=5)
    running: bool | None = None
    autonomous: bool | None = None
    killed: bool | None = None


class Replay(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    bars: int = Field(default=120, ge=6, le=374)


def create_app(db_path: str | Path | None = None, background: bool = True):
    @asynccontextmanager
    async def lifespan(app):
        app.state.engine = Engine(
            db_path
            or os.environ.get("ALGOOPTIONX_DB", str(PROJECT_ROOT / "data" / "paper.db"))
        )
        stop = threading.Event()

        def worker():
            while not stop.wait(2):
                try:
                    app.state.engine.pulse()
                    app.state.worker_error = None
                except Exception:
                    # Fail closed: report degraded health and stop automatic playback.
                    app.state.worker_error = "Playback stopped after a storage or engine error. Restart after diagnosis."
                    stop.set()

        app.state.worker_error = None
        thread = threading.Thread(target=worker, daemon=True)
        if background:
            thread.start()
        yield
        stop.set()
        if background:
            thread.join(timeout=20)

    app = FastAPI(title="AlgoOptionX", version="0.2.0", lifespan=lifespan)

    @app.middleware("http")
    async def local_commands(request: Request, call_next):
        # This is a local development application, not a hosted authentication system.
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if origin and urlsplit(origin).netloc not in {
                request.headers.get("host"),
                "127.0.0.1:5173",
                "localhost:5173",
            }:
                return JSONResponse(
                    {"detail": "Cross-origin commands are not allowed."},
                    status_code=403,
                )
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse(
                    {"detail": "Cross-site commands are not allowed."}, status_code=403
                )
        return await call_next(request)

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
    def state():
        return app.state.engine.state() | {"worker_error": app.state.worker_error}

    @app.post("/api/commands")
    def command(body: Command):
        if app.state.worker_error:
            raise HTTPException(503, app.state.worker_error)
        values = body.model_dump(exclude_none=True)
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
        return app.state.engine.command(key, action, **values)

    @app.post("/api/sessions")
    def new_session():
        return app.state.engine.new_session()

    @app.get("/api/audit/export")
    def export():
        # Export the complete chain, not the paginated workspace feed.
        with app.state.engine.tx() as c:
            account = app.state.engine._account(c)
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
    def replay(body: Replay):
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

    dist = (PROJECT_ROOT / "frontend" / "dist").resolve()

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
                503, "Build the frontend with npm run build in frontend/."
            )
        return FileResponse(index)

    return app


app = create_app()


def run():
    import uvicorn

    uvicorn.run("dhan_analyzer.api.paper_app:app", host="127.0.0.1", port=8000)

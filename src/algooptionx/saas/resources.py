"""Tenant-owned versioned workspace documents and immutable strategy revisions."""
from __future__ import annotations
import hashlib
import json
import time
import uuid
from typing import Annotated, Literal
from fastapi import APIRouter, HTTPException, Request
from pydantic import Field, model_validator
from .api import Record, principal, TenantContext, require_tenant_context

router = APIRouter(prefix="/api/resources")


class Drawing(Record):
    id: str = Field(min_length=1, max_length=80)
    pane: int = Field(default=0, ge=0, le=3)
    session_id: str = Field(min_length=1, max_length=160)
    kind: Literal["horizontal", "vertical", "trend", "rectangle", "fibonacci", "text", "measure"]
    time1: str = Field(max_length=40)
    price1: float = Field(gt=0, allow_inf_nan=False)
    time2: str | None = Field(default=None, max_length=40)
    price2: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    text: str = Field(default="", max_length=140)

    @model_validator(mode="after")
    def endpoints(self):
        from datetime import datetime
        start = datetime.fromisoformat(self.time1)
        if start.tzinfo is None:
            raise ValueError("Drawing timestamps require timezone offsets.")
        if self.kind in {"trend", "rectangle", "fibonacci", "measure"}:
            if not self.time2 or self.price2 is None:
                raise ValueError("This drawing requires two endpoints.")
            end = datetime.fromisoformat(self.time2)
            if end.tzinfo is None or int(start.timestamp()) == int(end.timestamp()):
                raise ValueError("Drawing endpoints require different aware timestamps.")
        return self


class WorkspaceDocument(Record):
    layout: Literal["single", "two-column", "three-column", "four-column", "grid"] = "single"
    timeframes: list[Literal["1", "3", "5", "15", "30", "60", "day", "week"]] = Field(default_factory=lambda: ["5"], min_length=1, max_length=4)
    chart_type: Literal["candlestick", "line", "area", "bar", "heikin"] = "candlestick"
    drawings: list[Drawing] = Field(default_factory=list, max_length=128)
    pane_weights: list[Annotated[float, Field(ge=0.5, le=3, allow_inf_nan=False)]] = Field(default_factory=lambda: [1,1,1,1], min_length=1, max_length=4)
    sync_symbol: bool = True
    sync_timeframe: bool = False
    sync_crosshair: bool = True
    sync_range: bool = False
    indicators: list[Literal["SMA", "EMA", "VWAP", "RSI", "MACD", "Bollinger", "ATR", "Supertrend", "Volume"]] = Field(default_factory=lambda: ["EMA", "VWAP", "Volume"], max_length=9)


    @model_validator(mode="after")
    def unique_elements(self):
        if len(set(self.indicators)) != len(self.indicators):
            raise ValueError("Indicators must be unique.")
        if len({drawing.id for drawing in self.drawings}) != len(self.drawings):
            raise ValueError("Drawing IDs must be unique within a layout.")
        return self


class WorkspaceWrite(TenantContext):
    name: str = Field(min_length=1, max_length=80)
    document: WorkspaceDocument
    expected_revision: int | None = Field(default=None, ge=1)


class Condition(Record):
    field: Literal["close", "ema9", "vwap", "volume", "direction", "gap", "change_30m"]
    timeframe: Literal["5", "30"] = "5"
    operator: Literal["gt", "gte", "lt", "lte", "eq"]
    value: float | str

    @model_validator(mode="after")
    def typed_value(self):
        import math
        if self.field == "direction":
            if self.operator != "eq" or self.value not in {"BULLISH", "BEARISH", "SIDEWAYS"}:
                raise ValueError("Direction rules require equality with BULLISH, BEARISH or SIDEWAYS.")
        elif type(self.value) not in (int, float) or not math.isfinite(self.value):
            raise ValueError("Numeric conditions require a finite numeric value.")
        return self


class RuleGroup(Record):
    operator: Literal["AND", "OR"] = "AND"
    conditions: list[Condition] = Field(min_length=1, max_length=16)


class StrategyDocument(Record):
    template: Literal["bull-put", "bear-call", "iron-condor"]
    lots: int = Field(default=1, ge=1, le=5)
    groups: list[RuleGroup] = Field(default_factory=list, max_length=4)
    group_operator: Literal["AND", "OR"] = "AND"
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def rules_required(self):
        if any(not group.conditions for group in self.groups):
            raise ValueError("Rule groups cannot be empty.")
        return self


class StrategyWrite(TenantContext):
    name: str = Field(min_length=1, max_length=80)
    document: StrategyDocument


class ResourceStore:
    def __init__(self, identity):
        self.identity = identity
        with identity.tx() as c:
            c.execute("CREATE TABLE IF NOT EXISTS saved_workspaces(id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL REFERENCES tenants(id),name TEXT NOT NULL,document TEXT NOT NULL,revision INTEGER NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),updated_at INTEGER NOT NULL,archived INTEGER NOT NULL DEFAULT 0)")
            c.execute("CREATE TABLE IF NOT EXISTS saved_strategies(id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL REFERENCES tenants(id),name TEXT NOT NULL,archived INTEGER NOT NULL DEFAULT 0,created_by TEXT NOT NULL REFERENCES users(id),created_at INTEGER NOT NULL,UNIQUE(id,tenant_id))")
            c.execute("CREATE TABLE IF NOT EXISTS strategy_versions(id TEXT PRIMARY KEY,strategy_id TEXT NOT NULL,tenant_id TEXT NOT NULL,version INTEGER NOT NULL,document TEXT NOT NULL,content_hash TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at INTEGER NOT NULL,UNIQUE(strategy_id,version),FOREIGN KEY(strategy_id,tenant_id) REFERENCES saved_strategies(id,tenant_id))")

    def workspace(self, user, body, resource_id=None):
        if user["role"] == "viewer":
            raise HTTPException(403, "This membership is read-only.")
        document = body.document.model_dump_json()
        name = body.name.strip()
        if not name:
            raise HTTPException(422, "Enter a workspace name.")
        with self.identity.tx() as c:
            if resource_id:
                old = c.execute("SELECT revision FROM saved_workspaces WHERE id=? AND tenant_id=? AND archived=0", (resource_id, user["tenant_id"])).fetchone()
                if not old:
                    raise HTTPException(404, "Workspace layout not found.")
                if body.expected_revision != old[0]:
                    raise HTTPException(409, "This workspace changed. Reload before saving.")
                c.execute("UPDATE saved_workspaces SET name=?,document=?,revision=revision+1,updated_at=? WHERE id=? AND tenant_id=?", (name, document, int(time.time()), resource_id, user["tenant_id"]))
                revision = old[0] + 1
            else:
                if c.execute("SELECT COUNT(*) FROM saved_workspaces WHERE tenant_id=? AND archived=0", (user["tenant_id"],)).fetchone()[0] >= 20:
                    raise HTTPException(409, "This release supports 20 saved layouts per workspace.")
                resource_id, revision = uuid.uuid4().hex, 1
                c.execute("INSERT INTO saved_workspaces VALUES(?,?,?,?,?,?,?,0)", (resource_id, user["tenant_id"], name, document, revision, user["user_id"], int(time.time())))
            self.identity.event(c, user["user_id"], "WORKSPACE_LAYOUT_SAVED")
        return {"id": resource_id, "revision": revision}

    def strategy(self, user, body, resource_id=None):
        if user["role"] == "viewer":
            raise HTTPException(403, "This membership is read-only.")
        name = body.name.strip()
        if not name:
            raise HTTPException(422, "Enter a strategy name.")
        document = body.document.model_dump_json()
        with self.identity.tx() as c:
            if resource_id:
                old = c.execute("SELECT id FROM saved_strategies WHERE id=? AND tenant_id=? AND archived=0", (resource_id, user["tenant_id"])).fetchone()
                if not old:
                    raise HTTPException(404, "Strategy not found.")
                version = c.execute("SELECT COALESCE(MAX(version),0)+1 FROM strategy_versions WHERE strategy_id=? AND tenant_id=?", (resource_id, user["tenant_id"])).fetchone()[0]
                c.execute("UPDATE saved_strategies SET name=? WHERE id=? AND tenant_id=?", (name, resource_id, user["tenant_id"]))
            else:
                if c.execute("SELECT COUNT(*) FROM saved_strategies WHERE tenant_id=? AND archived=0", (user["tenant_id"],)).fetchone()[0] >= 50:
                    raise HTTPException(409, "This release supports 50 saved strategies per workspace.")
                resource_id, version = uuid.uuid4().hex, 1
                c.execute("INSERT INTO saved_strategies VALUES(?,?,?,0,?,?)", (resource_id, user["tenant_id"], name, user["user_id"], int(time.time())))
            version_id = uuid.uuid4().hex
            c.execute("INSERT INTO strategy_versions VALUES(?,?,?,?,?,?,?,?)", (version_id, resource_id, user["tenant_id"], version, document, hashlib.sha256(document.encode()).hexdigest(), user["user_id"], int(time.time())))
            self.identity.event(c, user["user_id"], "STRATEGY_VERSION_SAVED")
        return {"id": resource_id, "version_id": version_id, "version": version}


@router.get("/workspaces")
def workspaces(request: Request):
    user = principal(request)
    with request.app.state.identity.tx() as c:
        rows = c.execute("SELECT id,name,document,revision,updated_at FROM saved_workspaces WHERE tenant_id=? AND archived=0 ORDER BY updated_at DESC", (user["tenant_id"],)).fetchall()
    return {"workspaces": [dict(row) | {"document": json.loads(row["document"])} for row in rows]}


@router.post("/workspaces")
def save_workspace(body: WorkspaceWrite, request: Request):
    require_tenant_context(request, body.expected_tenant_id)
    return request.app.state.resources.workspace(principal(request), body)


@router.post("/workspaces/{resource_id}")
def update_workspace(resource_id: str, body: WorkspaceWrite, request: Request):
    require_tenant_context(request, body.expected_tenant_id)
    return request.app.state.resources.workspace(principal(request), body, resource_id)


@router.get("/strategies")
def strategies(request: Request):
    user = principal(request)
    with request.app.state.identity.tx() as c:
        rows = c.execute("SELECT s.id,s.name,s.created_at,MAX(v.version) version FROM saved_strategies s JOIN strategy_versions v ON v.strategy_id=s.id AND v.tenant_id=s.tenant_id WHERE s.tenant_id=? AND s.archived=0 GROUP BY s.id ORDER BY s.created_at DESC", (user["tenant_id"],)).fetchall()
    return {"strategies": [dict(row) for row in rows]}


@router.post("/strategies")
def save_strategy(body: StrategyWrite, request: Request):
    require_tenant_context(request, body.expected_tenant_id)
    return request.app.state.resources.strategy(principal(request), body)


@router.post("/strategies/{resource_id}")
def version_strategy(resource_id: str, body: StrategyWrite, request: Request):
    require_tenant_context(request, body.expected_tenant_id)
    return request.app.state.resources.strategy(principal(request), body, resource_id)


@router.get("/strategies/{resource_id}/versions")
def versions(resource_id: str, request: Request):
    user = principal(request)
    with request.app.state.identity.tx() as c:
        owned = c.execute("SELECT id FROM saved_strategies WHERE id=? AND tenant_id=?", (resource_id, user["tenant_id"])).fetchone()
        if not owned:
            raise HTTPException(404, "Strategy not found.")
        rows = c.execute("SELECT id,version,document,content_hash,created_at FROM strategy_versions WHERE strategy_id=? AND tenant_id=? ORDER BY version DESC", (resource_id, user["tenant_id"])).fetchall()
    return {"versions": [dict(row) | {"document": json.loads(row["document"])} for row in rows]}

"""Identity routes. Passwords, session secrets and email tokens are never returned."""
from __future__ import annotations
import hmac
import time
from fastapi import APIRouter, HTTPException, Request, Response, BackgroundTasks
from pydantic import BaseModel, ConfigDict, Field
from .identity import IdentityError, digest

SESSION_COOKIE = "algooptionx_session"
CSRF_COOKIE = "algooptionx_csrf"
router = APIRouter(prefix="/api/identity")


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Credentials(Record):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)
    authentication_code: str | None = Field(default=None,min_length=6,max_length=40)


class Registration(Credentials):
    name: str = Field(min_length=1, max_length=80)


class EmailRequest(Record):
    email: str = Field(min_length=3, max_length=254)


class TokenRequest(Record):
    token: str = Field(min_length=20, max_length=128)


class ResetRequest(TokenRequest):
    password: str = Field(min_length=12, max_length=128)


class Profile(Record):
    name: str = Field(min_length=1, max_length=80)


def principal(request: Request):
    value = getattr(request.state, "principal", None)
    if not value:
        raise HTTPException(401, "Sign in to continue.")
    return value


def set_session(request: Request, response: Response, tokens):
    session, csrf = tokens
    options = dict(secure=request.app.state.secure_cookies, samesite="lax", path="/", max_age=7 * 86400)
    response.set_cookie(SESSION_COOKIE, session, httponly=True, **options)
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, **options)
    response.headers["Cache-Control"] = "no-store"


def clear_session(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def peer(request: Request):
    # Do not trust caller-provided forwarding headers.
    return request.client.host if request.client else "unknown"


def identity_response(request: Request, tokens):
    return {"user": request.app.state.identity.public(request.app.state.identity.authenticate(tokens[0])),
            "verification_required": request.app.state.require_auth,
            "email_delivery": request.app.state.identity.mail.mode}


@router.get("/me")
def me(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {"user": request.app.state.identity.public(getattr(request.state, "principal", None)),
            "verification_required": request.app.state.require_auth,
            "email_delivery": request.app.state.identity.mail.mode}


@router.post("/register")
def register(body: Registration, request: Request, response: Response, background: BackgroundTasks):
    tokens = request.app.state.identity.register(body.email, body.password, body.name, peer(request))
    set_session(request, response, tokens)
    background.add_task(deliver_recovery, request.app.state.identity, body.email, "verify", peer(request))
    return identity_response(request, tokens)


@router.post("/login")
def login(body: Credentials, request: Request, response: Response):
    tokens = request.app.state.identity.login(body.email, body.password, peer(request), body.authentication_code)
    set_session(request, response, tokens)
    return identity_response(request, tokens)


@router.post("/logout")
def logout(request: Request, response: Response):
    user = principal(request)
    with request.app.state.identity.tx() as c:
        c.execute("UPDATE sessions SET revoked=1 WHERE id=? AND user_id=?", (user["session_id"], user["user_id"]))
        request.app.state.identity.event(c, user["user_id"], "LOGOUT")
    clear_session(response)
    return {"ok": True}


@router.get("/sessions")
def sessions(request: Request, response: Response):
    user = principal(request)
    response.headers["Cache-Control"] = "no-store"
    with request.app.state.identity.tx() as c:
        rows = c.execute("SELECT id,created_at,last_seen,expires_at FROM sessions WHERE user_id=? AND revoked=0 AND expires_at>? AND last_seen>? ORDER BY created_at DESC", (user["user_id"], int(time.time()), int(time.time()) - 12 * 3600)).fetchall()
    return {"sessions": [dict(row) | {"current": row["id"] == user["session_id"]} for row in rows]}


@router.post("/sessions/{session_id}/revoke")
def revoke(session_id: str, request: Request, response: Response):
    user = principal(request)
    with request.app.state.identity.tx() as c:
        changed = c.execute("UPDATE sessions SET revoked=1 WHERE id=? AND user_id=?", (session_id, user["user_id"])).rowcount
        if not changed:
            raise HTTPException(404, "Session not found.")
        request.app.state.identity.event(c, user["user_id"], "SESSION_REVOKED")
    if session_id == user["session_id"]:
        clear_session(response)
    return {"ok": True}


@router.post("/profile")
def profile(body: Profile, request: Request):
    user = principal(request)
    if not body.name.strip():
        raise HTTPException(422, "Enter a name.")
    with request.app.state.identity.tx() as c:
        c.execute("UPDATE users SET name=? WHERE id=?", (body.name.strip(), user["user_id"]))
        request.app.state.identity.event(c, user["user_id"], "PROFILE_UPDATED")
    return {"ok": True}


def deliver_recovery(store, email: str, purpose: str, address: str):
    try:
        store.issue_email(email, purpose, address)
    except (IdentityError, OSError, TimeoutError):
        # Do not expose account existence or raw provider failures.
        return


@router.post("/request-reset")
def request_reset(body: EmailRequest, request: Request, background: BackgroundTasks):
    background.add_task(deliver_recovery, request.app.state.identity, body.email, "reset", peer(request))
    return {"message": "If an account matches, a recovery link will be sent through the configured email service."}


@router.post("/reset-password")
def reset_password(body: ResetRequest, request: Request, response: Response):
    request.app.state.identity.rate_limit("consume-reset:" + peer(request), 20)
    request.app.state.identity.consume_token(body.token, "reset", body.password)
    clear_session(response)
    return {"ok": True, "message": "Password reset. Sign in again on each device."}


@router.post("/request-verification")
def request_verification(request: Request):
    user = principal(request)
    request.app.state.identity.issue_email(user["email"], "verify", peer(request))
    return {"message": "Verification link sent through the configured email service."}


@router.post("/verify-email")
def verify_email(body: TokenRequest, request: Request):
    request.app.state.identity.rate_limit("consume-verify:" + peer(request), 20)
    request.app.state.identity.consume_token(body.token, "verify")
    return {"ok": True}


def csrf_valid(request: Request, user: dict) -> bool:
    value = request.headers.get("x-algooptionx-csrf", "")
    return bool(value) and len(value) <= 128 and hmac.compare_digest(digest(value), user["csrf_hash"])


class TenantContext(Record):
    expected_tenant_id: str = Field(pattern=r"^[a-f0-9]{32}$")


def require_tenant_context(request: Request, expected: str | None):
    user = getattr(request.state, "principal", None)
    if expected != (user["tenant_id"] if user else None):
        raise HTTPException(409, "Workspace changed in another tab. Reload and review this action again.")


class TenantName(Record):
    name: str = Field(min_length=1, max_length=80)


class TenantSelection(TenantContext):
    tenant_id: str = Field(pattern=r"^[a-f0-9]{32}$")


class Invitation(TenantContext):
    email: str = Field(min_length=3, max_length=254)
    role: str = Field(pattern=r"^(trader|viewer)$")


def owner(request: Request):
    user = principal(request)
    if request.app.state.require_auth and not user["email_verified"]:
        raise HTTPException(403, "Verify your email before managing workspace access or billing.")
    if user["role"] != "owner":
        raise HTTPException(403, "Workspace-owner permission is required.")
    return user


@router.get("/tenants")
def tenants(request: Request):
    user = principal(request)
    with request.app.state.identity.tx() as c:
        rows = c.execute("SELECT t.id,t.name,m.role FROM tenants t JOIN memberships m ON t.id=m.tenant_id WHERE m.user_id=? AND m.active=1 ORDER BY t.created_at", (user["user_id"],)).fetchall()
    return {"tenants": [dict(row) for row in rows]}


@router.post("/tenants")
def create_tenant(body: TenantName, request: Request):
    import uuid
    user = principal(request)
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Enter a workspace name.")
    with request.app.state.identity.tx() as c:
        count = c.execute("SELECT COUNT(*) FROM memberships WHERE user_id=? AND role='owner' AND active=1", (user["user_id"],)).fetchone()[0]
        if count >= 3:
            raise HTTPException(409, "This local release allows three owned workspaces per customer.")
        tenant_id = uuid.uuid4().hex
        c.execute("INSERT INTO tenants VALUES(?,?,?)", (tenant_id, name, int(time.time())))
        c.execute("INSERT INTO memberships(user_id,tenant_id,role) VALUES(?,?,'owner')", (user["user_id"], tenant_id))
        request.app.state.identity.event(c, user["user_id"], "TENANT_CREATED")
    return {"id": tenant_id, "name": name}


@router.post("/switch-tenant")
def switch_tenant(body: TenantSelection, request: Request):
    user = principal(request)
    require_tenant_context(request, body.expected_tenant_id)
    with request.app.state.identity.tx() as c:
        membership = c.execute("SELECT role FROM memberships WHERE user_id=? AND tenant_id=? AND active=1", (user["user_id"], body.tenant_id)).fetchone()
        if not membership:
            raise HTTPException(404, "Workspace not found.")
        c.execute("UPDATE sessions SET tenant_id=? WHERE id=? AND user_id=?", (body.tenant_id, user["session_id"], user["user_id"]))
        request.app.state.identity.event(c, user["user_id"], "TENANT_SWITCHED")
    return {"ok": True}


@router.get("/members")
def members(request: Request):
    user = owner(request)
    with request.app.state.identity.tx() as c:
        rows = c.execute("SELECT u.id,u.email,u.name,m.role FROM users u JOIN memberships m ON m.user_id=u.id WHERE m.tenant_id=? AND m.active=1 ORDER BY u.name", (user["tenant_id"],)).fetchall()
    return {"members": [dict(row) for row in rows]}


@router.post("/members/{user_id}/remove")
def remove_member(user_id: str, body: TenantContext, request: Request):
    user = owner(request)
    require_tenant_context(request, body.expected_tenant_id)
    with request.app.state.identity.tx() as c:
        target = c.execute("SELECT m.role,u.email FROM memberships m JOIN users u ON u.id=m.user_id WHERE m.user_id=? AND m.tenant_id=? AND m.active=1", (user_id, user["tenant_id"])).fetchone()
        if not target:
            raise HTTPException(404, "Member not found.")
        if target["role"] == "owner":
            raise HTTPException(409, "Owner membership cannot be removed through this operation.")
        c.execute("UPDATE memberships SET active=0 WHERE user_id=? AND tenant_id=?", (user_id, user["tenant_id"]))
        c.execute("UPDATE sessions SET revoked=1 WHERE user_id=? AND tenant_id=?", (user_id, user["tenant_id"]))
        c.execute("UPDATE tenant_invites SET used=1 WHERE email=? AND tenant_id=?", (target["email"], user["tenant_id"]))
        request.app.state.identity.event(c, user["user_id"], "MEMBER_REMOVED")
    return {"ok": True}


@router.post("/invite")
def invite(body: Invitation, request: Request):
    import secrets
    from .identity import normalize_email
    user = owner(request)
    require_tenant_context(request, body.expected_tenant_id)
    email = normalize_email(body.email)
    request.app.state.identity.rate_limit("invite:" + user["user_id"], 10, 3600)
    token = secrets.token_urlsafe(32)
    with request.app.state.identity.tx() as c:
        c.execute("UPDATE tenant_invites SET used=1 WHERE email=? AND tenant_id=?", (email, user["tenant_id"]))
        c.execute("INSERT INTO tenant_invites VALUES(?,?,?,?,?,0)", (digest(token), user["tenant_id"], email, body.role, int(time.time()) + 3 * 86400))
        request.app.state.identity.event(c, user["user_id"], "MEMBER_INVITED")
    request.app.state.identity.mail.send(email, "invite", token)
    return {"message": "Workspace invitation sent through the configured email service."}


@router.post("/accept-invite")
def accept_invite(body: TokenRequest, request: Request):
    user = principal(request)
    with request.app.state.identity.tx() as c:
        invitation = c.execute("SELECT * FROM tenant_invites WHERE token_hash=? AND used=0 AND expires_at>? AND email=?", (digest(body.token), int(time.time()), user["email"])).fetchone()
        if not invitation:
            raise HTTPException(400, "Invitation is invalid, expired or belongs to another email address.")
        c.execute("INSERT INTO memberships(user_id,tenant_id,role,active) VALUES(?,?,?,1) ON CONFLICT(user_id,tenant_id) DO UPDATE SET role=excluded.role,active=1 WHERE memberships.role!='owner'", (user["user_id"], invitation["tenant_id"], invitation["role"]))
        c.execute("UPDATE tenant_invites SET used=1 WHERE token_hash=?", (digest(body.token),))
        request.app.state.identity.event(c, user["user_id"], "INVITATION_ACCEPTED")
    return {"ok": True}

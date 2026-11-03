"""Opaque sessions and personal tenants. No financial or broker authority lives here."""
from __future__ import annotations

from contextlib import contextmanager
from email.message import EmailMessage
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import smtplib
import sqlite3
import time
import threading
import uuid


_password_slots = threading.BoundedSemaphore(2)


class IdentityError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}", email):
        raise IdentityError("Enter a valid email address.", 422)
    return email


def password_hash(value: str) -> str:
    if not 12 <= len(value) <= 128 or len(value.encode()) > 512:
        raise IdentityError("Use a password with 12–128 characters.", 422)
    salt = secrets.token_bytes(16)
    if not _password_slots.acquire(timeout=5):
        raise IdentityError("Authentication is busy. Try again shortly.", 429)
    try:
        digest = hashlib.scrypt(value.encode(), salt=salt, n=32768, r=8, p=1, maxmem=64 * 1024 * 1024)
    finally:
        _password_slots.release()
    return "scrypt$32768$" + salt.hex() + "$" + digest.hex()


def password_matches(value: str, encoded: str) -> bool:
    try:
        if len(value) > 128 or len(value.encode()) > 512:
            return False
        algorithm, cost, salt, expected = encoded.split("$")
        if algorithm != "scrypt" or cost != "32768":
            return False
        if not _password_slots.acquire(timeout=5):
            raise IdentityError("Authentication is busy. Try again shortly.", 429)
        try:
            actual = hashlib.scrypt(value.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=1, maxmem=64 * 1024 * 1024)
        finally:
            _password_slots.release()
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class MailDelivery:
    """SMTP in configured environments; restricted local outbox for development."""
    def __init__(self, folder: Path):
        self.folder = folder
        self.mode = os.environ.get("ALGOOPTIONX_MAIL_MODE", "file")
        self.origin = os.environ.get("ALGOOPTIONX_PUBLIC_ORIGIN", "http://127.0.0.1:8000").rstrip("/")

    def send(self, email: str, purpose: str, token: str):
        route, subject = {"verify": ("verify-email", "Verify your AlgoOptionX email"),
                          "reset": ("reset-password", "Reset your AlgoOptionX password"),
                          "invite": ("accept-invite", "Join an AlgoOptionX workspace")}[purpose]
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = os.environ.get("ALGOOPTIONX_MAIL_FROM", "noreply@localhost")
        message["To"] = email
        message.set_content(f"{subject}\n\n{self.origin}/{route}#token={token}\n\nIf you did not request this, ignore this message. This link expires and can be used once.")
        if self.mode == "smtp":
            host = os.environ.get("ALGOOPTIONX_SMTP_HOST", "")
            if not host:
                raise IdentityError("Email delivery is unavailable.", 503)
            try:
                with smtplib.SMTP_SSL(host, int(os.environ.get("ALGOOPTIONX_SMTP_PORT", "465")), timeout=10) as client:
                    username = os.environ.get("ALGOOPTIONX_SMTP_USER")
                    if username:
                        client.login(username, os.environ.get("ALGOOPTIONX_SMTP_PASSWORD", ""))
                    client.send_message(message)
            except (OSError, smtplib.SMTPException):
                raise IdentityError("Email delivery is unavailable. Try again later.", 503) from None
        elif self.mode == "file":
            self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            target = self.folder / f"{uuid.uuid4().hex}.eml"
            fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w") as stream:
                stream.write(message.as_string())
        else:
            raise IdentityError("Email delivery is unavailable.", 503)


class IdentityStore:
    def __init__(self, path: str | Path, mail: MailDelivery | None = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        os.chmod(self.path, 0o600)
        self.mail = mail or MailDelivery(self.path.parent / (self.path.stem + "-outbox"))
        with self.tx() as c:
            # Additive, separate database. Existing paper/research tables are never migrated here.
            for statement in (
                "CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,name TEXT NOT NULL,email_verified INTEGER NOT NULL DEFAULT 0,created_at INTEGER NOT NULL)",
                "CREATE TABLE IF NOT EXISTS tenants(id TEXT PRIMARY KEY,name TEXT NOT NULL,created_at INTEGER NOT NULL)",
                "CREATE TABLE IF NOT EXISTS memberships(user_id TEXT NOT NULL REFERENCES users(id),tenant_id TEXT NOT NULL REFERENCES tenants(id),role TEXT NOT NULL CHECK(role IN ('owner','trader','viewer')),active INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(user_id,tenant_id))",
                "CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,token_hash TEXT UNIQUE NOT NULL,csrf_hash TEXT NOT NULL,user_id TEXT NOT NULL,tenant_id TEXT NOT NULL,created_at INTEGER NOT NULL,last_seen INTEGER NOT NULL,expires_at INTEGER NOT NULL,revoked INTEGER NOT NULL DEFAULT 0,FOREIGN KEY(user_id,tenant_id) REFERENCES memberships(user_id,tenant_id))",
                "CREATE TABLE IF NOT EXISTS mfa_credentials(user_id TEXT PRIMARY KEY REFERENCES users(id),encrypted_secret TEXT NOT NULL,active INTEGER NOT NULL,last_step INTEGER NOT NULL)",
                "CREATE TABLE IF NOT EXISTS mfa_recovery(user_id TEXT NOT NULL REFERENCES users(id),code_hash TEXT NOT NULL,used INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(user_id,code_hash))",
                "CREATE TABLE IF NOT EXISTS identity_tokens(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),purpose TEXT NOT NULL,expires_at INTEGER NOT NULL,used INTEGER NOT NULL DEFAULT 0)",
                "CREATE TABLE IF NOT EXISTS auth_attempts(key TEXT NOT NULL,created_at INTEGER NOT NULL)",
                "CREATE INDEX IF NOT EXISTS auth_attempts_key ON auth_attempts(key,created_at)",
                "CREATE TABLE IF NOT EXISTS tenant_invites(token_hash TEXT PRIMARY KEY,tenant_id TEXT NOT NULL REFERENCES tenants(id),email TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('trader','viewer')),expires_at INTEGER NOT NULL,used INTEGER NOT NULL DEFAULT 0)",
                "CREATE TABLE IF NOT EXISTS security_events(id TEXT PRIMARY KEY,user_id TEXT,event TEXT NOT NULL,created_at INTEGER NOT NULL)",
            ):
                c.execute(statement)
            if "active" not in {row["name"] for row in c.execute("PRAGMA table_info(memberships)")}:
                c.execute("ALTER TABLE memberships ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
        self._dummy_password = password_hash(secrets.token_urlsafe(24))

    @contextmanager
    def tx(self):
        c = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        try:
            c.execute("BEGIN IMMEDIATE")
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def event(self, c, user_id, name):
        c.execute("INSERT INTO security_events VALUES(?,?,?,?)", (uuid.uuid4().hex, user_id, name, int(time.time())))

    def rate_limit(self, key: str, limit: int, window: int = 900):
        now = int(time.time())
        with self.tx() as c:
            c.execute("DELETE FROM auth_attempts WHERE created_at<?", (now - 86400,))
            count = c.execute("SELECT COUNT(*) FROM auth_attempts WHERE key=? AND created_at>?", (digest(key), now - window)).fetchone()[0]
            if count >= limit:
                raise IdentityError("Too many attempts. Try again later.", 429)
            c.execute("INSERT INTO auth_attempts VALUES(?,?)", (digest(key), now))

    def _session(self, c, user_id: str, tenant_id: str):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        now = int(time.time())
        c.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,0)",
                  (uuid.uuid4().hex, digest(token), digest(csrf), user_id, tenant_id, now, now, now + 7 * 86400))
        return token, csrf

    def register(self, email: str, password: str, name: str, peer: str):
        email = normalize_email(email)
        self.rate_limit("signup:" + peer, 10, 3600)
        encoded = password_hash(password)
        name = name.strip()
        if not 1 <= len(name) <= 80:
            raise IdentityError("Enter a name with 1–80 characters.", 422)
        user_id, tenant_id = uuid.uuid4().hex, uuid.uuid4().hex
        try:
            with self.tx() as c:
                now = int(time.time())
                c.execute("INSERT INTO users VALUES(?,?,?,?,0,?)", (user_id, email, encoded, name, now))
                c.execute("INSERT INTO tenants VALUES(?,?,?)", (tenant_id, name + "'s workspace", now))
                c.execute("INSERT INTO memberships(user_id,tenant_id,role) VALUES(?,?,'owner')", (user_id, tenant_id))
                result = self._session(c, user_id, tenant_id)
                self.event(c, user_id, "REGISTER")
        except sqlite3.IntegrityError:
            raise IdentityError("Unable to create an account with these details.", 409) from None
        return result

    def login(self, email: str, password: str, peer: str, code: str | None = None):
        email = normalize_email(email)
        self.rate_limit("login-ip:" + peer, 60)
        self.rate_limit("login-user:" + email, 10)
        with self.tx() as c:
            row = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        matched = password_matches(password, row["password_hash"] if row else self._dummy_password)
        if not row or not matched:
            raise IdentityError("Email or password is incorrect.", 401)
        with self.tx() as c:
            # Prevent a password-reset race between hash verification and session issuance.
            current = c.execute("SELECT password_hash FROM users WHERE id=?", (row["id"],)).fetchone()
            if not hmac.compare_digest(current[0], row["password_hash"]):
                raise IdentityError("Email or password is incorrect.", 401)
            from .mfa import validate_factor
            validate_factor(self,c,row["id"],code)
            tenant = c.execute("SELECT tenant_id FROM memberships WHERE user_id=? AND active=1 ORDER BY tenant_id LIMIT 1", (row["id"],)).fetchone()
            if not tenant:
                raise IdentityError("No active workspace membership. Contact your workspace owner.", 403)
            result = self._session(c, row["id"], tenant[0])
            self.event(c, row["id"], "LOGIN")
            return result

    def authenticate(self, token: str | None):
        if not token or len(token) > 128:
            return None
        now = int(time.time())
        with self.tx() as c:
            row = c.execute("""SELECT s.id session_id,s.csrf_hash,s.tenant_id,s.user_id,u.email,u.name,u.email_verified,m.role,t.name tenant_name
                FROM sessions s JOIN users u ON u.id=s.user_id
                JOIN memberships m ON m.user_id=s.user_id AND m.tenant_id=s.tenant_id
                JOIN tenants t ON t.id=s.tenant_id
                WHERE m.active=1 AND s.token_hash=? AND s.revoked=0 AND s.expires_at>? AND s.last_seen>?""", (digest(token), now, now - 12 * 3600)).fetchone()
            if not row:
                return None
            c.execute("UPDATE sessions SET last_seen=? WHERE id=?", (now, row["session_id"]))
            return dict(row)

    def issue_email(self, email: str, purpose: str, peer: str):
        email = normalize_email(email)
        self.rate_limit("email-ip:" + peer, 20)
        self.rate_limit("email-user:" + email, 5)
        token = secrets.token_urlsafe(32)
        with self.tx() as c:
            user = c.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
            if not user:
                return
            c.execute("UPDATE identity_tokens SET used=1 WHERE user_id=? AND purpose=?", (user[0], purpose))
            c.execute("INSERT INTO identity_tokens VALUES(?,?,?,?,0)", (digest(token), user[0], purpose, int(time.time()) + (3600 if purpose == "verify" else 900)))
        self.mail.send(email, purpose, token)

    def consume_token(self, token: str, purpose: str, password: str | None = None):
        encoded = password_hash(password) if password is not None else None
        with self.tx() as c:
            row = c.execute("SELECT * FROM identity_tokens WHERE token_hash=? AND purpose=? AND used=0 AND expires_at>?", (digest(token), purpose, int(time.time()))).fetchone()
            if not row:
                raise IdentityError("This link is invalid or expired.")
            c.execute("UPDATE identity_tokens SET used=1 WHERE token_hash=?", (digest(token),))
            if purpose == "verify":
                c.execute("UPDATE users SET email_verified=1 WHERE id=?", (row["user_id"],))
            elif purpose == "reset" and encoded:
                c.execute("UPDATE users SET password_hash=? WHERE id=?", (encoded, row["user_id"]))
                c.execute("UPDATE sessions SET revoked=1 WHERE user_id=?", (row["user_id"],))
                c.execute("UPDATE identity_tokens SET used=1 WHERE user_id=? AND purpose='reset'", (row["user_id"],))
            else:
                raise IdentityError("Invalid recovery operation.")
            self.event(c, row["user_id"], "EMAIL_VERIFIED" if purpose == "verify" else "PASSWORD_RESET")

    @staticmethod
    def public(principal):
        if not principal:
            return None
        return {key: principal[key] for key in ("user_id", "email", "name", "email_verified", "tenant_id", "tenant_name", "role", "session_id")}

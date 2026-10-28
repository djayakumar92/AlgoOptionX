"""Synthetic market and transactional long-only virtual account.

Amounts are integer paise. Each command owns one SQLite transaction. Synthetic
contracts/lot sizes are fixtures, not current exchange specifications.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import closing, contextmanager
from pathlib import Path

from algooptionx.market.simulator import LOT, MAX_TICK, market

CAPITAL = 50_000_000
FEE = 2_000


class PaperError(ValueError):
    pass


class Engine:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # executescript commits any pending transaction. Keep schema installation
        # separate from the transaction containing account/active/FUNDING writes.
        with closing(sqlite3.connect(self.path, timeout=15, isolation_level=None)) as c:
            c.executescript("""
            BEGIN IMMEDIATE;
            CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY, cash INTEGER NOT NULL, realized INTEGER NOT NULL DEFAULT 0,
                fees INTEGER NOT NULL DEFAULT 0, tick INTEGER NOT NULL DEFAULT 0, running INTEGER NOT NULL DEFAULT 0,
                autonomous INTEGER NOT NULL DEFAULT 0, killed INTEGER NOT NULL DEFAULT 0, seed INTEGER NOT NULL DEFAULT 17);
            CREATE TABLE IF NOT EXISTS active(id INTEGER PRIMARY KEY CHECK(id=1), account_id TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS positions(id TEXT PRIMARY KEY, account_id TEXT NOT NULL, instrument TEXT NOT NULL,
                quantity INTEGER NOT NULL, entry INTEGER NOT NULL, stop INTEGER NOT NULL, target INTEGER NOT NULL, opened_tick INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL, tick INTEGER NOT NULL,
                kind TEXT NOT NULL, payload TEXT NOT NULL, previous_hash TEXT NOT NULL, hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS commands(account_id TEXT NOT NULL, key TEXT NOT NULL, request TEXT NOT NULL, result TEXT NOT NULL,
                PRIMARY KEY(account_id,key));
            COMMIT;
            """)
        with self.tx() as c:
            active = c.execute("SELECT account_id FROM active WHERE id=1").fetchone()
            if not active:
                if c.execute("SELECT 1 FROM accounts").fetchone():
                    raise PaperError(
                        "Paper initialization is incomplete. Preserve the database and reconcile account history before restarting."
                    )
                self._new(c)
            elif (
                not c.execute(
                    "SELECT 1 FROM accounts WHERE id=?", (active["account_id"],)
                ).fetchone()
                or c.execute(
                    "SELECT COUNT(*) FROM events WHERE account_id=? AND kind='FUNDING'",
                    (active["account_id"],),
                ).fetchone()[0]
                != 1
            ):
                raise PaperError(
                    "Paper funding history is incomplete. Preserve the database for reconciliation; no funding event was inferred."
                )
            # A restart always pauses playback. Resume is an explicit action.
            c.execute("UPDATE accounts SET running=0")

    @contextmanager
    def tx(self):
        c = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        c.row_factory = sqlite3.Row
        try:
            c.execute("BEGIN IMMEDIATE")
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def _account(self, c):
        return dict(
            c.execute(
                "SELECT * FROM accounts WHERE id=(SELECT account_id FROM active WHERE id=1)"
            ).fetchone()
        )

    def _event(self, c, a, kind, payload):
        previous = c.execute(
            "SELECT hash FROM events WHERE account_id=? ORDER BY seq DESC LIMIT 1",
            (a["id"],),
        ).fetchone()
        prev = previous["hash"] if previous else ""
        body = json.dumps(
            {
                "account_id": a["id"],
                "tick": a["tick"],
                "kind": kind,
                "payload": payload,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256((prev + body).encode()).hexdigest()
        c.execute(
            "INSERT INTO events(account_id,tick,kind,payload,previous_hash,hash) VALUES(?,?,?,?,?,?)",
            (a["id"], a["tick"], kind, json.dumps(payload), prev, digest),
        )

    def _new(self, c):
        identity = str(uuid.uuid4())
        c.execute("INSERT INTO accounts(id,cash) VALUES(?,?)", (identity, CAPITAL))
        c.execute("INSERT OR REPLACE INTO active VALUES(1,?)", (identity,))
        self._event(
            c,
            {"id": identity, "tick": 0},
            "FUNDING",
            {"amount": CAPITAL, "message": "Virtual account funded with ₹5,00,000"},
        )
        return identity

    def _positions(self, c, a):
        quotes = {q["id"]: q for q in market(a["tick"], a["seed"])["contracts"]}
        return [
            dict(p)
            | {
                "mark": quotes[p["instrument"]]["mark"],
                "unrealized": (quotes[p["instrument"]]["bid"] - 5 - p["entry"])
                * p["quantity"]
                - FEE,
            }
            for p in c.execute("SELECT * FROM positions WHERE account_id=?", (a["id"],))
        ]

    def _trade(self, c, a, instrument, lots, origin):
        if a["killed"]:
            raise PaperError("Kill switch is active. New entries are blocked.")
        if a["tick"] >= MAX_TICK:
            raise PaperError(
                "Synthetic session has closed. Create a new session to continue."
            )
        if isinstance(lots, bool) or not isinstance(lots, int) or not 1 <= lots <= 5:
            raise PaperError("Choose between 1 and 5 whole lots.")
        q = next(
            (
                q
                for q in market(a["tick"], a["seed"])["contracts"]
                if q["id"] == instrument
            ),
            None,
        )
        if not q:
            raise PaperError("Unknown synthetic contract.")
        positions = self._positions(c, a)
        if len(positions) >= 3 or any(p["instrument"] == instrument for p in positions):
            raise PaperError(
                "Maximum three distinct open positions; duplicate contracts are blocked."
            )
        if (
            a["realized"] + sum(p["unrealized"] for p in positions)
            <= -CAPITAL * 2 // 100
        ):
            raise PaperError("Daily loss limit reached. New entries are blocked.")
        entry, quantity = q["ask"] + 5, lots * LOT
        stop, target = entry * 92 // 100, entry * 112 // 100
        risk = (entry - stop) * quantity + 2 * FEE
        if risk > CAPITAL // 100:
            raise PaperError("Trade exceeds the 1% stop-risk budget.")
        cost = entry * quantity + FEE
        exposure = sum(p["entry"] * p["quantity"] for p in positions)
        if cost > a["cash"] or exposure + entry * quantity > CAPITAL // 5:
            raise PaperError(
                "Insufficient cash or 20% premium exposure limit exceeded."
            )
        pid = str(uuid.uuid4())
        c.execute(
            "INSERT INTO positions VALUES(?,?,?,?,?,?,?,?)",
            (pid, a["id"], instrument, quantity, entry, stop, target, a["tick"]),
        )
        c.execute(
            "UPDATE accounts SET cash=cash-?,fees=fees+?,realized=realized-? WHERE id=?",
            (cost, FEE, FEE, a["id"]),
        )
        result = {
            "position_id": pid,
            "instrument": instrument,
            "quantity": quantity,
            "price": entry,
            "fee": FEE,
            "stop": stop,
            "target": target,
            "origin": origin,
            "message": f"Virtual buy · {instrument} · {quantity} units",
        }
        self._event(c, a, "BUY", result)
        return result

    def _close(self, c, a, pid, reason):
        p = c.execute(
            "SELECT * FROM positions WHERE id=? AND account_id=?", (pid, a["id"])
        ).fetchone()
        if not p:
            raise PaperError(
                "Position is already closed or does not belong to this session."
            )
        q = next(
            q
            for q in market(a["tick"], a["seed"])["contracts"]
            if q["id"] == p["instrument"]
        )
        price = q["bid"] - 5
        pnl = (price - p["entry"]) * p["quantity"] - FEE
        c.execute(
            "UPDATE accounts SET cash=cash+?,realized=realized+?,fees=fees+? WHERE id=?",
            (price * p["quantity"] - FEE, pnl, FEE, a["id"]),
        )
        c.execute("DELETE FROM positions WHERE id=?", (pid,))
        result = {
            "position_id": pid,
            "instrument": p["instrument"],
            "quantity": p["quantity"],
            "price": price,
            "pnl": pnl - FEE,
            "fee": FEE,
            "reason": reason,
            "message": f"Virtual exit · {reason} · {p['instrument']}",
        }
        self._event(c, a, "SELL", result)
        return result

    def command(self, key: str, action: str, **kwargs):
        try:
            return self._command(key, action, **kwargs)
        except PaperError as exc:
            # The failed financial transaction is rolled back first. Record the
            # refusal separately so manual as well as autonomous denials are visible.
            with self.tx() as c:
                self._event(
                    c,
                    self._account(c),
                    "REJECTED",
                    {"message": str(exc), "action": action},
                )
            raise

    def _command(self, key: str, action: str, **kwargs):
        if not key or len(key) > 160:
            raise PaperError("A valid idempotency key is required.")
        request = json.dumps({"action": action, **kwargs}, sort_keys=True)
        with self.tx() as c:
            a = self._account(c)
            old = c.execute(
                "SELECT * FROM commands WHERE account_id=? AND key=?", (a["id"], key)
            ).fetchone()
            if old:
                if old["request"] != request:
                    raise PaperError(
                        "Idempotency key was already used for a different command."
                    )
                return json.loads(old["result"])
            result = {"message": "Updated"}
            if action == "buy":
                result = self._trade(
                    c, a, kwargs.get("instrument"), kwargs.get("lots", 1), "MANUAL"
                )
            elif action == "close":
                result = self._close(c, a, kwargs.get("position_id"), "MANUAL")
            elif action == "control":
                allowed = {"running", "autonomous", "killed"}
                if (
                    not kwargs
                    or set(kwargs) - allowed
                    or any(not isinstance(v, bool) for v in kwargs.values())
                ):
                    raise PaperError("Invalid simulator controls.")
                if a["killed"] and kwargs.get("autonomous"):
                    raise PaperError(
                        "Release kill switch before enabling autonomous entries."
                    )
                for name, value in kwargs.items():
                    c.execute(
                        f"UPDATE accounts SET {name}=? WHERE id=?",
                        (int(value), a["id"]),
                    )
                if kwargs.get("killed"):
                    c.execute("UPDATE accounts SET autonomous=0 WHERE id=?", (a["id"],))
                    for p in self._positions(c, a):
                        self._close(c, a, p["id"], "KILL_SWITCH")
                self._event(
                    c, a, "CONTROL", kwargs | {"message": "Session controls updated"}
                )
            elif action == "advance":
                self._advance(c, a)
            else:
                raise PaperError("Unknown command.")
            c.execute(
                "INSERT INTO commands VALUES(?,?,?,?)",
                (a["id"], key, request, json.dumps(result)),
            )
            return result

    def _advance(self, c, a):
        if a["tick"] >= MAX_TICK:
            c.execute("UPDATE accounts SET running=0 WHERE id=?", (a["id"],))
            return
        a["tick"] += 1
        c.execute("UPDATE accounts SET tick=? WHERE id=?", (a["tick"], a["id"]))
        quotes = {q["id"]: q for q in market(a["tick"], a["seed"])["contracts"]}
        for p in self._positions(c, a):
            price = quotes[p["instrument"]]["bid"] - 5
            reason = (
                "SESSION_CLOSE"
                if a["tick"] == MAX_TICK
                else "STOP_LOSS"
                if price <= p["stop"]
                else "TAKE_PROFIT"
                if price >= p["target"]
                else None
            )
            if reason:
                self._close(c, a, p["id"], reason)
        a = self._account(c)
        if (
            a["autonomous"]
            and not a["killed"]
            and a["tick"] % 6 == 0
            and a["tick"] < MAX_TICK
        ):
            now = market(a["tick"], a["seed"])
            delta = now["spot"] - market(a["tick"] - 5, a["seed"])["spot"]
            right = "CE" if delta > 0 else "PE"
            candidates = [q for q in now["contracts"] if q["right"] == right]
            q = min(candidates, key=lambda q: abs(q["strike"] - now["spot"]))
            if abs(delta) < 5:
                self._event(
                    c,
                    a,
                    "DECISION",
                    {
                        "message": "NO TRADE · synthetic five-bar move below 5 points",
                        "delta": delta,
                    },
                )
            else:
                # Only the risk gate can turn this transparent fixture rule into a fill.
                try:
                    self._trade(c, a, q["id"], 1, "RULE_V1")
                except PaperError as exc:
                    self._event(c, a, "REJECTED", {"message": str(exc)})
        if a["tick"] == MAX_TICK:
            c.execute(
                "UPDATE accounts SET running=0,autonomous=0 WHERE id=?", (a["id"],)
            )

    def pulse(self):
        with self.tx() as c:
            a = self._account(c)
            if a["running"]:
                self._advance(c, a)

    def new_session(self):
        with self.tx() as c:
            a = self._account(c)
            if self._positions(c, a):
                raise PaperError("Close all positions before creating a new session.")
            c.execute(
                "UPDATE accounts SET running=0,autonomous=0 WHERE id=?", (a["id"],)
            )
            return {"account_id": self._new(c)}

    def state(self):
        with self.tx() as c:
            a = self._account(c)
            positions = self._positions(c, a)
            quotes = market(a["tick"], a["seed"])
            value = sum(p["mark"] * p["quantity"] for p in positions)
            equity = a["cash"] + value
            events = [
                dict(e) | {"payload": json.loads(e["payload"])}
                for e in c.execute(
                    "SELECT * FROM events WHERE account_id=? ORDER BY seq DESC LIMIT 150",
                    (a["id"],),
                )
            ]
            history = [
                {"tick": t, "spot": market(t, a["seed"])["spot"]}
                for t in range(max(0, a["tick"] - 90), a["tick"] + 1)
            ]
            delta = quotes["spot"] - market(max(0, a["tick"] - 5), a["seed"])["spot"]
            return {
                "name": "AlgoOptionX",
                "mode": "PAPER",
                "market": quotes,
                "history": history,
                "account": a
                | {
                    "capital": CAPITAL,
                    "equity": equity,
                    "pnl": equity - CAPITAL,
                    "unrealized": value
                    - sum(p["entry"] * p["quantity"] for p in positions),
                    "exposure": sum(p["entry"] * p["quantity"] for p in positions),
                },
                "positions": positions,
                "events": events,
                "decision": {
                    "action": "WAIT"
                    if abs(delta) < 5
                    else "BUY CE"
                    if delta > 0
                    else "BUY PE",
                    "change": round(delta, 2),
                    "version": "SYNTHETIC_MOMENTUM_V1",
                    "explanation": "Fixture rule: follow a five-bar move above 5 points. Checked every six bars; one lot, 8% stop, 12% target. No trained model or profitability claim.",
                },
                "risk": {
                    "max_positions": 3,
                    "max_exposure": CAPITAL // 5,
                    "max_trade_risk": CAPITAL // 100,
                    "max_daily_loss": CAPITAL * 2 // 100,
                    "fee_per_fill": FEE,
                    "lot_size": LOT,
                },
            }

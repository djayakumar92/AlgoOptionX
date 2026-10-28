"""Accounting, restart, risk, replay and adversarial command coverage."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from hypothesis import given, settings, strategies as st
from fastapi.testclient import TestClient

from algooptionx.api.app import create_app
from algooptionx.paper.engine import CAPITAL, FEE, Engine, PaperError, market


@pytest.fixture
def engine(tmp_path):
    return Engine(tmp_path / "paper.db")


def first_contract(engine):
    return engine.state()["market"]["contracts"][0]["id"]


def test_funding_restart_and_idempotency(engine):
    before = engine.state()
    q = first_contract(engine)
    order = engine.command("once", "buy", instrument=q)
    assert engine.command("once", "buy", instrument=q) == order
    with pytest.raises(PaperError, match="different command"):
        engine.command("once", "advance")
    restarted = Engine(engine.path)
    after = restarted.state()
    assert after["account"]["id"] == before["account"]["id"]
    assert len(after["positions"]) == 1
    assert sum(e["kind"] == "FUNDING" for e in after["events"]) == 1
    assert (
        after["account"]["cash"] == CAPITAL - order["price"] * order["quantity"] - FEE
    )


def test_round_trip_exact_money_and_history(engine):
    result = engine.command("buy", "buy", instrument=first_contract(engine))
    closed = engine.command("exit", "close", position_id=result["position_id"])
    a = engine.state()["account"]
    expected = (closed["price"] - result["price"]) * result["quantity"] - 2 * FEE
    assert a["cash"] == a["equity"] == CAPITAL + expected
    assert a["realized"] == expected == closed["pnl"]
    assert a["fees"] == 2 * FEE
    assert engine.state()["positions"] == []
    old_id = a["id"]
    engine.new_session()
    assert engine.state()["account"]["cash"] == CAPITAL
    with engine.tx() as c:
        assert (
            c.execute(
                "SELECT count(*) FROM events WHERE account_id=?", (old_id,)
            ).fetchone()[0]
            == 3
        )


def test_kill_flattens_and_blocks_entries(engine):
    engine.command("buy", "buy", instrument=first_contract(engine))
    engine.command("auto", "control", autonomous=True)
    engine.command("kill", "control", killed=True)
    state = engine.state()
    assert not state["positions"]
    assert not state["account"]["autonomous"]
    with pytest.raises(PaperError, match="Kill switch"):
        engine.command("new-buy", "buy", instrument=first_contract(engine))
    with pytest.raises(PaperError, match="Release kill"):
        engine.command("auto-again", "control", autonomous=True)
    assert any(e["payload"].get("reason") == "KILL_SWITCH" for e in state["events"])


def test_limits_and_failed_command_rollback(engine):
    q = first_contract(engine)
    for lots in (0, 6, True, 1.5):
        with pytest.raises(PaperError):
            engine.command(f"invalid-{lots}", "buy", instrument=q, lots=lots)
    before = engine.state()["account"]
    with pytest.raises(PaperError, match="Unknown"):
        engine.command("bad-id", "buy", instrument="nope")
    assert engine.state()["account"] == before
    engine.command("buy", "buy", instrument=q)
    with pytest.raises(PaperError):
        engine.new_session()
    with pytest.raises(PaperError, match="duplicate"):
        engine.command("duplicate", "buy", instrument=q)
    with engine.tx() as c:
        a = engine._account(c)
        c.execute(
            "UPDATE accounts SET realized=? WHERE id=?", (-CAPITAL * 2 // 100, a["id"])
        )
    other = engine.state()["market"]["contracts"][1]["id"]
    with pytest.raises(PaperError, match="Daily loss"):
        engine.command("daily-lock", "buy", instrument=other)


def test_concurrent_entry_limit(engine):
    qs = [q["id"] for q in engine.state()["market"]["contracts"]]

    def buy(item):
        index, instrument = item
        try:
            return engine.command(str(index), "buy", instrument=instrument)
        except PaperError:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(buy, enumerate(qs)))
    state = engine.state()
    assert sum(r is not None for r in results) == 3
    assert len(state["positions"]) == 3
    assert 0 <= state["account"]["exposure"] <= state["risk"]["max_exposure"]
    assert state["account"]["cash"] >= 0


def test_autonomous_exits_restart_and_session_close(engine):
    engine.command("start", "control", running=True, autonomous=True)
    for _ in range(50):
        engine.pulse()
    mid = engine.state()
    assert any(e["kind"] == "BUY" for e in mid["events"])
    restarted = Engine(engine.path)
    assert not restarted.state()["account"]["running"]
    tick = restarted.state()["market"]["tick"]
    restarted.pulse()
    assert restarted.state()["market"]["tick"] == tick
    for index in range(tick, 374):
        restarted.command(f"rest-{index}", "advance")
    final = restarted.state()
    assert not final["positions"]
    assert not final["account"]["running"]
    assert not final["account"]["autonomous"]
    assert final["market"]["tick"] == 374
    assert any(e["kind"] == "SELL" for e in final["events"])
    with pytest.raises(PaperError, match="closed"):
        restarted.command("late-buy", "buy", instrument=first_contract(restarted))


def test_hash_chain_reconstructs(engine):
    engine.command("buy", "buy", instrument=first_contract(engine))
    previous = ""
    for e in reversed(engine.state()["events"]):
        body = json.dumps(
            {
                "account_id": e["account_id"],
                "tick": e["tick"],
                "kind": e["kind"],
                "payload": e["payload"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        assert e["previous_hash"] == previous
        assert e["hash"] == hashlib.sha256((previous + body).encode()).hexdigest()
        previous = e["hash"]


@given(st.lists(st.integers(min_value=0, max_value=3), min_size=1, max_size=40))
@settings(max_examples=20, deadline=None)
def test_accounting_conservation(actions):
    from tempfile import TemporaryDirectory
    from pathlib import Path

    with TemporaryDirectory() as tmp:
        engine = Engine(Path(tmp) / "property.db")
        for index, action in enumerate(actions):
            state = engine.state()
            try:
                if action == 0:
                    engine.command(str(index), "advance")
                elif action == 1:
                    engine.command(
                        str(index),
                        "buy",
                        instrument=state["market"]["contracts"][index % 12]["id"],
                    )
                elif action == 2 and state["positions"]:
                    engine.command(
                        str(index), "close", position_id=state["positions"][0]["id"]
                    )
                else:
                    engine.command(str(index), "control", killed=True)
            except PaperError:
                pass
            state = engine.state()
            a = state["account"]
            cost = sum(p["entry"] * p["quantity"] for p in state["positions"])
            assert a["cash"] + cost == CAPITAL + a["realized"]
            assert a["pnl"] == a["realized"] + a["unrealized"]
            assert a["cash"] >= 0
            assert len(state["positions"]) <= 3


def test_api_offline_commands_replay_and_security(tmp_path):
    with TestClient(create_app(tmp_path / "api.db", background=False)) as client:
        assert client.get("/api/health").json()["source"] == "SYNTHETIC"
        before = client.get("/api/workspace").json()
        q = before["market"]["contracts"][0]["id"]
        assert (
            client.post(
                "/api/commands", json={"key": "buy", "action": "buy", "instrument": q}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/commands",
                json={"key": "bad", "action": "control", "running": "true"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/commands", json={"key": "bad", "action": "advance", "lots": 3}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/commands",
                json={"key": "x", "action": "advance"},
                headers={"Origin": "https://attacker.example"},
            ).status_code
            == 403
        )
        assert client.get("/api/not-real").status_code == 404
        assert client.get("/assets/%2e%2e/%2e%2e/pyproject.toml").status_code == 404
        assert client.post("/api/replay", json={"bars": 99999}).status_code == 422
        active = client.get("/api/workspace").json()
        first = client.post("/api/replay", json={"bars": 60}).json()
        second = client.post("/api/replay", json={"bars": 60}).json()
        assert first == second
        assert first["trades"] > 0
        assert client.get("/api/workspace").json() == active
        export = client.get("/api/audit/export")
        assert export.status_code == 200
        assert len(export.json()["events"]) == 2
        assert "attachment" in export.headers["content-disposition"]


def test_future_market_calls_cannot_change_past():
    original = market(10)
    market(300)
    assert market(10) == original


def test_event_failure_rolls_back_economic_effect(engine, monkeypatch):
    before = engine.state()

    def fail(*args):
        raise OSError("Simulated write failure")

    monkeypatch.setattr(engine, "_event", fail)
    with pytest.raises(OSError):
        engine.command("fault", "buy", instrument=first_contract(engine))
    after = engine.state()
    assert before == after


def test_entry_cash_boundary_and_denial_evidence(engine):
    quote = engine.state()["market"]["contracts"][0]
    cost = (quote["ask"] + 5) * quote["lot_size"] + FEE
    with engine.tx() as c:
        c.execute("UPDATE accounts SET cash=?", (cost - 1,))
    with pytest.raises(PaperError, match="Insufficient cash"):
        engine.command("one-paise-short", "buy", instrument=quote["id"])
    assert engine.state()["events"][0]["kind"] == "REJECTED"
    with engine.tx() as c:
        c.execute("UPDATE accounts SET cash=?", (cost,))
    engine.command("exact-cash", "buy", instrument=quote["id"])
    assert engine.state()["account"]["cash"] == 0


def test_stop_and_target_exit_at_executable_quote(engine):
    for reason, threshold in [("STOP_LOSS", "stop"), ("TAKE_PROFIT", "target")]:
        if engine.state()["positions"]:
            raise AssertionError("Previous virtual position did not close")
        buy = engine.command(f"buy-{reason}", "buy", instrument=first_contract(engine))
        # Force one risk threshold to be crossed at the next deterministic bar.
        with engine.tx() as c:
            c.execute(
                f"UPDATE positions SET {threshold}=? WHERE id=?",
                (10**9 if threshold == "stop" else 1, buy["position_id"]),
            )
        engine.command(f"advance-{reason}", "advance")
        assert engine.state()["events"][0]["payload"]["reason"] == reason
        assert (
            engine.state()["events"][0]["payload"]["price"]
            == engine.state()["market"]["contracts"][0]["bid"] - 5
        )

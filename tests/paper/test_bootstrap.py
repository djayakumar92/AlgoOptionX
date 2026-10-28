"""No partial or inferred initial funding, including failures and concurrent starts."""

from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from algooptionx.paper.engine import CAPITAL, Engine, PaperError


def counts(path):
    with sqlite3.connect(path) as c:
        return tuple(
            c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("accounts", "active", "events")
        )


@pytest.mark.parametrize("after_event", [False, True])
def test_funding_event_failure_rolls_back_account_pointer_and_event(
    tmp_path, monkeypatch, after_event
):
    p = tmp_path / "paper.db"
    original = Engine._event

    def fail(self, *args):
        if after_event:
            original(self, *args)
        raise RuntimeError("Injected bootstrap fault")

    with monkeypatch.context() as context:
        context.setattr(Engine, "_event", fail)
        with pytest.raises(RuntimeError, match="bootstrap fault"):
            Engine(p)
    assert counts(p) == (0, 0, 0)
    restarted = Engine(p)
    assert counts(p) == (1, 1, 1)
    state = restarted.state()
    assert state["account"]["cash"] == CAPITAL
    assert state["events"][0]["kind"] == "FUNDING"
    assert Engine(p).state()["account"]["id"] == state["account"]["id"]
    assert counts(p) == (1, 1, 1)


def test_failure_after_account_before_active_pointer_rolls_back(tmp_path, monkeypatch):
    p = tmp_path / "paper.db"

    def partial(self, c):
        c.execute("INSERT INTO accounts(id,cash) VALUES('partial',?)", (CAPITAL,))
        raise RuntimeError("account fault")

    with monkeypatch.context() as context:
        context.setattr(Engine, "_new", partial)
        with pytest.raises(RuntimeError):
            Engine(p)
    assert counts(p) == (0, 0, 0)
    Engine(p)
    assert counts(p) == (1, 1, 1)


def test_concurrent_initialization_funds_exactly_once(tmp_path):
    p = tmp_path / "paper.db"
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(lambda _: Engine(p).state()["account"]["id"], range(4)))
    assert len(set(ids)) == 1
    assert counts(p) == (1, 1, 1)


def test_old_partial_bootstrap_is_preserved_and_refused(tmp_path):
    p = tmp_path / "paper.db"
    Engine(p)
    with sqlite3.connect(p) as c:
        c.execute("DELETE FROM events")  # reproduce the old orphaned funding fixture
    before = counts(p)
    with pytest.raises(PaperError, match="funding history is incomplete"):
        Engine(p)
    assert counts(p) == before == (1, 1, 0)


def test_funded_history_positions_and_cash_survive_restart(tmp_path):
    p = tmp_path / "paper.db"
    e = Engine(p)
    e.command("buy-once", "buy", instrument=e.state()["market"]["contracts"][0]["id"])
    before = e.state()
    after = Engine(p).state()
    for key in ("account", "positions", "events"):
        assert before[key] == after[key]


@pytest.mark.parametrize(
    "corruption", ["orphan-account", "dangling-pointer", "duplicate-funding"]
)
def test_incomplete_existing_bootstrap_is_never_inferred_or_refunded(
    tmp_path, corruption
):
    p = tmp_path / "paper.db"
    Engine(p)
    with sqlite3.connect(p) as c:
        if corruption == "orphan-account":
            c.execute("DELETE FROM active")
        elif corruption == "dangling-pointer":
            c.execute("UPDATE active SET account_id='missing'")
        else:
            c.execute(
                "INSERT INTO events(account_id,tick,kind,payload,previous_hash,hash) SELECT account_id,tick,kind,payload,previous_hash,hash FROM events"
            )
    before = counts(p)
    with pytest.raises(PaperError, match="incomplete"):
        Engine(p)
    assert counts(p) == before

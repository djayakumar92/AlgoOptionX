"""The full loop end to end: evaluate -> record -> grade -> calibrate.

Uses an in-memory database and synthetic candles, so it exercises the wiring
between the signal modules, the ledger, and the repository without a broker
connection.
"""

import json
import sqlite3
from datetime import date, datetime, time, timedelta

import pandas as pd
import pytest

from algooptionx.research.api import prediction, serialize
from algooptionx.research.signals import calibration, setups
from algooptionx.research.storage import repository
from algooptionx.research.storage.models import SCHEMA

SYMBOL = "NIFTY"
EXPIRY = date(2026, 9, 8)  # a Tuesday
INTERVAL = 5


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    yield connection
    connection.close()


def _session_bars(session: date, opens_at: float, drift: float, bars: int = 60) -> list[dict]:
    """One session of 5-minute candles drifting steadily by `drift` per bar."""
    start = datetime.combine(session, time(9, 15))
    rows = []
    price = opens_at
    for i in range(bars):
        rows.append(
            {
                "ts": int((start + timedelta(minutes=5 * i)).timestamp()),
                "open": price,
                "high": price + 12,
                "low": price - 12,
                "close": price + drift,
                "volume": 10_000,
                "oi": None,
            }
        )
        price += drift
    return rows


def seed_candles(conn, sessions: int = 12, drift: float = 3.0) -> date:
    """A run of consecutive weekday sessions, newest returned."""
    day = date(2026, 8, 17)  # a Monday
    price = 24000.0
    last = day
    for _ in range(sessions):
        while day.weekday() >= 5:
            day += timedelta(days=1)
        rows = _session_bars(day, price, drift)
        repository.upsert_candles(conn, SYMBOL, str(INTERVAL), rows)
        price = rows[-1]["close"]
        last = day
        day += timedelta(days=1)
    return last


def seed_chain(conn, session: date, spot: float, straddle_half: float = 60.0) -> None:
    rows = []
    for offset in (-200, -100, 0, 100, 200):
        strike = round((spot + offset) / 50) * 50
        for option_type, delta in (("CE", 0.5), ("PE", -0.5)):
            rows.append(
                {
                    "strike": float(strike),
                    "option_type": option_type,
                    "ltp": straddle_half,
                    "oi": 500_000,
                    "prev_day_oi": 450_000,
                    "volume": 120_000,
                    "iv": 13.5,
                    "delta": delta,
                    "theta": -5.0,
                    "gamma": 0.0012,
                    "vega": 8.0,
                    "bid": straddle_half - 1,
                    "ask": straddle_half + 1,
                    "bid_qty": 100,
                    "ask_qty": 100,
                }
            )
    ts = int(datetime.combine(session, time(12, 0)).timestamp())
    repository.insert_option_chain_snapshot(conn, SYMBOL, EXPIRY, ts, rows)


# ---- build ---------------------------------------------------------------


def test_no_spot_price_yields_an_explanation_not_an_error(conn):
    read = prediction.build(
        conn, under_symbol=SYMBOL, tracked_expiry=EXPIRY, intraday_interval=INTERVAL, spot_price=None
    )
    assert read.regime is None
    assert read.signals == []
    assert "first market-data poll" in read.unavailable


def test_build_degrades_without_any_stored_history(conn):
    """An empty database must produce a read with warnings, not a crash --
    this is what the page looks like on a fresh install before the open."""
    read = prediction.build(
        conn, under_symbol=SYMBOL, tracked_expiry=EXPIRY, intraday_interval=INTERVAL,
        spot_price=24000.0, now=datetime(2026, 9, 4, 11, 30),
    )
    assert read.regime is not None
    assert read.regime.premium_pricing == "UNKNOWN"
    assert read.regime.warnings


def test_build_writes_nothing_to_the_ledger(conn):
    """A page refresh must not be able to alter the record."""
    last = seed_candles(conn)
    seed_chain(conn, last, 24000.0)
    prediction.build(
        conn, under_symbol=SYMBOL, tracked_expiry=EXPIRY, intraday_interval=INTERVAL,
        spot_price=24000.0, now=datetime.combine(last, time(12, 0)),
    )
    assert repository.get_daily_features(conn) == []
    assert repository.get_setup_events_for_date(conn, last.isoformat()) == []


def test_build_produces_the_whole_catalog(conn):
    last = seed_candles(conn)
    seed_chain(conn, last, 24100.0)
    read = prediction.build(
        conn, under_symbol=SYMBOL, tracked_expiry=EXPIRY, intraday_interval=INTERVAL,
        spot_price=24100.0, now=datetime.combine(last, time(12, 0)),
    )
    assert len(read.signals) >= 8
    assert {s.side for s in read.signals} == {setups.BUY_PREMIUM, setups.SELL_PREMIUM}
    assert read.gex is not None
    assert read.risk_assessment is not None


# ---- record --------------------------------------------------------------


def test_recording_is_idempotent_within_a_session(conn):
    """The worker re-evaluates every minute. A setup that stays armed for two
    hours must be recorded once, at the moment it first armed."""
    last = seed_candles(conn)
    seed_chain(conn, last, 24100.0)
    at = datetime.combine(last, time(12, 0))

    kwargs = dict(
        under_symbol=SYMBOL, tracked_expiry=EXPIRY, intraday_interval=INTERVAL, spot_price=24100.0
    )
    prediction.evaluate_and_record(conn, now=at, **kwargs)
    first = repository.get_setup_events_for_date(conn, last.isoformat())
    prediction.evaluate_and_record(conn, now=at + timedelta(minutes=30), **kwargs)
    second = repository.get_setup_events_for_date(conn, last.isoformat())

    assert len(first) == len(second)
    assert [row["armed_ts"] for row in first] == [row["armed_ts"] for row in second]


def test_recorded_event_keeps_the_full_signal_and_its_conditions(conn):
    last = seed_candles(conn)
    seed_chain(conn, last, 24100.0)
    read = prediction.evaluate_and_record(
        conn, under_symbol=SYMBOL, tracked_expiry=EXPIRY, intraday_interval=INTERVAL,
        spot_price=24100.0, now=datetime.combine(last, time(12, 0)),
    )
    armed = [s for s in read.signals if s.status == setups.ARMED]
    if not armed:
        pytest.skip("No setup armed on this synthetic session -- covered by other tests.")

    [row] = [r for r in repository.get_setup_events_for_date(conn, last.isoformat())][:1]
    assert row["assumption"]
    assert row["trigger_rule"]
    assert row["invalidation_rule"]
    assert row["structure_regime"]  # regime context copied onto the event
    assert json.loads(row["signal_json"])["evidence"]


def test_daily_features_records_the_engines_read(conn):
    last = seed_candles(conn)
    seed_chain(conn, last, 24100.0)
    prediction.evaluate_and_record(
        conn, under_symbol=SYMBOL, tracked_expiry=EXPIRY, intraday_interval=INTERVAL,
        spot_price=24100.0, now=datetime.combine(last, time(12, 0)),
    )
    [row] = repository.get_daily_features(conn)
    assert row["trade_date"] == last.isoformat()
    assert row["premium_stance"] in ("BUY_FAVORED", "SELL_FAVORED", "NEUTRAL")
    assert row["atm_iv"] == pytest.approx(13.5)
    assert json.loads(row["features_json"])["reasons"]


# ---- grade ---------------------------------------------------------------


def test_grading_fills_in_outcomes_and_the_sessions_own_result(conn):
    last = seed_candles(conn)
    seed_chain(conn, last, 24100.0)
    prediction.evaluate_and_record(
        conn, under_symbol=SYMBOL, tracked_expiry=EXPIRY, intraday_interval=INTERVAL,
        spot_price=24100.0, now=datetime.combine(last, time(11, 0)),
    )
    armed = repository.get_setup_events_for_date(conn, last.isoformat())
    if not armed:
        pytest.skip("No setup armed on this synthetic session -- covered by other tests.")

    graded = prediction.grade_finished_sessions(
        conn, under_symbol=SYMBOL, intraday_interval=INTERVAL, today=last + timedelta(days=1)
    )
    assert graded == len(armed)

    row = repository.get_daily_features(conn)[0]
    assert row["close"] is not None
    assert row["range_points"] > 0

    # ...and the record now feeds back into the setups' displayed confidence
    assert calibration.calibration_map(conn)


def test_grading_is_a_no_op_once_a_session_is_graded(conn):
    last = seed_candles(conn)
    seed_chain(conn, last, 24100.0)
    prediction.evaluate_and_record(
        conn, under_symbol=SYMBOL, tracked_expiry=EXPIRY, intraday_interval=INTERVAL,
        spot_price=24100.0, now=datetime.combine(last, time(11, 0)),
    )
    tomorrow = last + timedelta(days=1)
    prediction.grade_finished_sessions(
        conn, under_symbol=SYMBOL, intraday_interval=INTERVAL, today=tomorrow
    )
    again = prediction.grade_finished_sessions(
        conn, under_symbol=SYMBOL, intraday_interval=INTERVAL, today=tomorrow
    )
    assert again == 0


def test_the_current_session_is_never_graded_early(conn):
    """Grading a day that has not finished would score a setup against half a
    session and write that verdict permanently."""
    last = seed_candles(conn)
    seed_chain(conn, last, 24100.0)
    prediction.evaluate_and_record(
        conn, under_symbol=SYMBOL, tracked_expiry=EXPIRY, intraday_interval=INTERVAL,
        spot_price=24100.0, now=datetime.combine(last, time(11, 0)),
    )
    assert prediction.grade_finished_sessions(
        conn, under_symbol=SYMBOL, intraday_interval=INTERVAL, today=last
    ) == 0


def test_a_session_without_stored_candles_stays_ungraded(conn):
    """A holiday, or a day the app was not running: leave it ungraded rather
    than recording a verdict the data cannot support."""
    repository.record_setup_event(
        conn,
        {
            "trade_date": "2026-01-05", "setup_key": "IB_BREAKOUT_LONG", "armed_ts": 1,
            "spot_at_arm": 24000.0, "action": "BUY_CE", "side": "BUY_PREMIUM",
            "direction": "BULLISH", "score": 70.0, "grade": "C",
        },
    )
    assert prediction.grade_finished_sessions(
        conn, under_symbol=SYMBOL, intraday_interval=INTERVAL, today=date(2026, 9, 4)
    ) == 0
    assert len(repository.get_ungraded_setup_events(conn, "2026-09-04")) == 1


# ---- serialization -------------------------------------------------------


def test_the_payload_is_json_safe(conn):
    """numpy scalars leaking out of pandas have broken this endpoint before --
    a numpy bool is not JSON serializable and fails at response time, not at
    computation time."""
    last = seed_candles(conn)
    seed_chain(conn, last, 24100.0)
    read = prediction.build(
        conn, under_symbol=SYMBOL, tracked_expiry=EXPIRY, intraday_interval=INTERVAL,
        spot_price=24100.0, now=datetime.combine(last, time(12, 0)),
    )
    payload = serialize.serialize_prediction(read)
    json.dumps(payload)  # must not raise

    assert payload["signals"]
    assert "per_strike" not in (payload["gex"] or {})


def test_learning_payload_is_json_safe_on_an_empty_ledger(conn):
    payload = serialize.serialize_learning(
        calibration.all_setup_records(conn), calibration.regime_report(conn)
    )
    json.dumps(payload)
    assert payload["setups"] == []
    assert payload["regime_check"]["verdict"]


# ---- live-decision fields ------------------------------------------------


def test_key_levels_are_sorted_high_to_low_with_spot_in_place(conn):
    last = seed_candles(conn)
    seed_chain(conn, last, 24100.0)
    read = prediction.build(
        conn, under_symbol=SYMBOL, tracked_expiry=EXPIRY, intraday_interval=INTERVAL,
        spot_price=24100.0, now=datetime.combine(last, time(12, 0)),
    )
    prices = [level.price for level in read.key_levels]
    assert prices == sorted(prices, reverse=True)

    spot_levels = [level for level in read.key_levels if level.kind == "SPOT"]
    assert len(spot_levels) == 1
    assert spot_levels[0].distance_points == 0

    above = [level for level in read.key_levels if level.distance_points > 0]
    assert all(level.price > 24100.0 for level in above)


def test_key_levels_do_not_repeat_the_same_price(conn):
    """Several sources land on the same strike -- the heaviest call open
    interest and the heaviest gamma strike routinely agree. A ladder that
    prints one price twice is harder to read, not more informative."""
    last = seed_candles(conn)
    seed_chain(conn, last, 24100.0)
    read = prediction.build(
        conn, under_symbol=SYMBOL, tracked_expiry=EXPIRY, intraday_interval=INTERVAL,
        spot_price=24100.0, now=datetime.combine(last, time(12, 0)),
    )
    non_spot = [round(l.price) for l in read.key_levels if l.kind != "SPOT"]
    assert len(non_spot) == len(set(non_spot))


def test_every_key_level_explains_itself(conn):
    last = seed_candles(conn)
    seed_chain(conn, last, 24100.0)
    read = prediction.build(
        conn, under_symbol=SYMBOL, tracked_expiry=EXPIRY, intraday_interval=INTERVAL,
        spot_price=24100.0, now=datetime.combine(last, time(12, 0)),
    )
    assert read.key_levels
    assert all(level.label and level.detail for level in read.key_levels)


def test_every_signal_carries_a_readiness_verdict(conn):
    last = seed_candles(conn)
    seed_chain(conn, last, 24100.0)
    read = prediction.build(
        conn, under_symbol=SYMBOL, tracked_expiry=EXPIRY, intraday_interval=INTERVAL,
        spot_price=24100.0, now=datetime.combine(last, time(12, 0)),
    )
    valid = {setups.WAIT, setups.NOW, setups.MISSED, setups.READINESS_NA}
    for signal in read.signals:
        assert signal.readiness in valid
        assert signal.readiness_note


def test_levels_sharing_a_price_are_merged_not_dropped(conn):
    """An entry trigger derived from the opening-range low sits on exactly
    that price. Keeping only one label loses either the level's meaning or
    the fact that it is today's trigger."""
    last = seed_candles(conn)
    seed_chain(conn, last, 24100.0)
    read = prediction.build(
        conn, under_symbol=SYMBOL, tracked_expiry=EXPIRY, intraday_interval=INTERVAL,
        spot_price=24100.0, now=datetime.combine(last, time(12, 0)),
    )
    if read.best is None or read.best.entry_reference is None:
        pytest.skip("No armed setup with a level on this synthetic session.")

    trigger_price = round(read.best.entry_reference)
    matching = [l for l in read.key_levels if round(l.price) == trigger_price]
    assert len(matching) == 1
    assert "trigger" in matching[0].label.lower()

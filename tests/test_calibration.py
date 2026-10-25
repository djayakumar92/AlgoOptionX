import sqlite3

import pytest

from dhan_analyzer.signals import calibration
from dhan_analyzer.storage import repository
from dhan_analyzer.storage.models import SCHEMA


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    yield connection
    connection.close()


def add_event(conn, key: str, trade_date: str, **overrides) -> int:
    row = {
        "trade_date": trade_date,
        "setup_key": key,
        "armed_ts": 1,
        "spot_at_arm": 24000.0,
        "action": "BUY_CE",
        "side": "BUY_PREMIUM",
        "direction": "BULLISH",
        "score": 70.0,
        "grade": "C",
        "structure_regime": "TRENDING",
        "day_type": "TREND",
        "premium_pricing": "CHEAP",
        "gamma_regime": "NEGATIVE_GAMMA",
        "session_window": "MIDDAY",
        "is_expiry_day": 0,
    }
    row.update(overrides)
    return repository.record_setup_event(conn, row)


def add_outcome(conn, event_id: int, key: str, trade_date: str, result: str,
                points: float | None = 20.0, triggered: int = 1) -> None:
    repository.record_setup_outcome(
        conn,
        {
            "event_id": event_id,
            "trade_date": trade_date,
            "setup_key": key,
            "graded_ts": 1,
            "triggered": triggered,
            "trigger_ts": 1,
            "result": result,
            "underlying_points": points,
            "mfe_points": 30.0,
            "mae_points": 10.0,
            "hit_target": int(result == "WIN"),
            "hit_invalidation": int(result == "LOSS"),
            "note": "",
        },
    )


def seed(conn, key: str, results: list[str], regime: str = "TRENDING") -> None:
    for i, result in enumerate(results):
        trade_date = f"2026-09-{i + 1:02d}"
        event_id = add_event(conn, key, trade_date, structure_regime=regime)
        add_outcome(conn, event_id, key, trade_date, result)


# ---- dedupe --------------------------------------------------------------


def test_the_same_setup_cannot_be_recorded_twice_in_one_session():
    """The engine re-evaluates on every poll. Without the dedupe, one armed
    setup would write hundreds of rows and inflate every denominator."""
    assert add_event(conn=(c := _fresh()), key="A", trade_date="2026-09-01") is not None
    assert add_event(conn=c, key="A", trade_date="2026-09-01") is None
    assert add_event(conn=c, key="A", trade_date="2026-09-02") is not None


def _fresh() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    return connection


# ---- records -------------------------------------------------------------


def test_empty_ledger_yields_no_calibration_rather_than_a_default(conn):
    assert calibration.calibration_map(conn) == {}


def test_hit_rate_counts_only_decided_outcomes(conn):
    seed(conn, "K", ["WIN", "WIN", "LOSS", "FLAT"])
    record = calibration.setup_record(conn, "K")
    assert record.wins == 2 and record.losses == 1 and record.flats == 1
    assert record.hit_rate == pytest.approx(66.7, abs=0.1)


def test_not_triggered_events_are_excluded_from_the_hit_rate(conn):
    event_id = add_event(conn, "K", "2026-09-01")
    add_outcome(conn, event_id, "K", "2026-09-01", "NOT_TRIGGERED", points=None, triggered=0)
    seed_id = add_event(conn, "K", "2026-09-02")
    add_outcome(conn, seed_id, "K", "2026-09-02", "WIN")

    record = calibration.setup_record(conn, "K")
    assert record.armed == 2
    assert record.triggered == 1
    assert record.not_triggered == 1
    assert record.hit_rate == 100.0  # from the single decided outcome


def test_a_thin_sample_is_labelled_unreliable(conn):
    seed(conn, "K", ["WIN", "WIN", "WIN"])
    record = calibration.setup_record(conn, "K")
    assert record.hit_rate == 100.0
    assert record.reliable is False
    assert "indistinguishable from chance" in record.verdict


def test_a_full_sample_is_labelled_reliable(conn):
    seed(conn, "K", ["WIN"] * 14 + ["LOSS"] * 8)
    record = calibration.setup_record(conn, "K")
    assert record.reliable is True
    assert "real sample" in record.verdict


def test_results_are_sliced_by_the_regime_that_was_live(conn):
    seed(conn, "K", ["WIN", "WIN"], regime="TRENDING")
    for i, result in enumerate(["LOSS", "LOSS"]):
        trade_date = f"2026-10-{i + 1:02d}"
        event_id = add_event(conn, "K", trade_date, structure_regime="RANGING")
        add_outcome(conn, event_id, "K", trade_date, result)

    record = calibration.setup_record(conn, "K")
    by_regime = {s.label: s for s in record.by_regime}
    assert by_regime["Trending"].hit_rate == 100.0
    assert by_regime["Ranging"].hit_rate == 0.0


def test_calibration_map_feeds_setups_with_sample_size(conn):
    seed(conn, "IB_BREAKOUT_LONG", ["WIN", "LOSS", "WIN"])
    read = calibration.calibration_map(conn)["IB_BREAKOUT_LONG"]
    assert read.sample_size == 3
    assert read.wins == 2
    assert read.note


# ---- regime self-check ---------------------------------------------------


def add_day(conn, trade_date: str, regime_label: str, range_points: float) -> None:
    repository.upsert_daily_features(
        conn,
        {
            "trade_date": trade_date,
            "captured_ts": 1,
            "structure_regime": regime_label,
            "range_points": range_points,
        },
    )


def test_regime_report_needs_sessions_before_it_says_anything(conn):
    report = calibration.regime_report(conn)
    assert report.sessions == 0
    assert "cannot be checked" in report.verdict


def test_regime_report_confirms_a_label_that_separates(conn):
    for i in range(5):
        add_day(conn, f"2026-09-{i + 1:02d}", "TRENDING", 260.0)
        add_day(conn, f"2026-10-{i + 1:02d}", "RANGING", 90.0)
    report = calibration.regime_report(conn)
    assert report.separation_points == pytest.approx(170.0)
    assert "tracking something real" in report.verdict


def test_regime_report_calls_out_a_label_that_does_not_separate(conn):
    """If sessions called trending did not move further than contained ones,
    the label is decorative and must be reported as such."""
    for i in range(5):
        add_day(conn, f"2026-09-{i + 1:02d}", "TRENDING", 100.0)
        add_day(conn, f"2026-10-{i + 1:02d}", "RANGING", 130.0)
    report = calibration.regime_report(conn)
    assert report.separation_points < 0
    assert "not yet earning its place" in report.verdict


def test_daily_features_upsert_does_not_blank_the_earlier_write(conn):
    """Written twice a day -- the engine's read in the morning, the market's
    outcome after the close. Neither write may erase the other."""
    repository.upsert_daily_features(
        conn, {"trade_date": "2026-09-04", "captured_ts": 1, "structure_regime": "TRENDING"}
    )
    repository.upsert_daily_features(
        conn, {"trade_date": "2026-09-04", "captured_ts": 2, "range_points": 150.0}
    )
    [row] = repository.get_daily_features(conn)
    assert row["structure_regime"] == "TRENDING"
    assert row["range_points"] == 150.0

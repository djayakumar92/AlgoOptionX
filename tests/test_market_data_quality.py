from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from dhan_analyzer.ingestion.quality import (
    DataQualityError,
    is_regular_session,
    parse_candle_response,
    require_fresh_latest_bar,
    validate_option_chain,
)
from dhan_analyzer.storage import repository
from dhan_analyzer.storage.models import SCHEMA


IST = ZoneInfo("Asia/Kolkata")


def _ts(hour=9, minute=15, day=24):
    return int(datetime(2026, 8, day, hour, minute, tzinfo=IST).timestamp())


def _response(timestamps=None):
    timestamps = timestamps or [_ts(), _ts(9, 20)]
    return {
        "status": "success",
        "data": {
            "timestamp": timestamps,
            "open": [100.0] * len(timestamps),
            "high": [102.0] * len(timestamps),
            "low": [99.0] * len(timestamps),
            "close": [101.0] * len(timestamps),
            "volume": [20] * len(timestamps),
            "open_interest": [None] * len(timestamps),
        },
    }


def test_parser_validates_and_excludes_unfinished_intraday_bar():
    batch = parse_candle_response(_response(), interval_min=5, now_ts=_ts(9, 22))
    assert [row["ts"] for row in batch.rows] == [_ts()]
    assert batch.source_row_count == 2
    assert batch.excluded_incomplete_count == 1


def test_parser_records_stable_content_hash_and_provenance():
    first = parse_candle_response(_response(), interval_min=5, now_ts=_ts(9, 30))
    second = parse_candle_response(_response(), interval_min=5, now_ts=_ts(9, 30))
    assert first.content_sha256 == second.content_sha256
    assert len(first.content_sha256) == 64
    manifest = first.manifest("NIFTY", "5", "from", "to")
    assert manifest["source_id"] == "dhanhq"
    assert manifest["quality_status"] == "VALID"
    assert manifest["accepted_row_count"] == 2


def test_parser_rejects_array_length_mismatch():
    response = _response()
    response["data"]["close"] = [101.0]
    with pytest.raises(DataQualityError, match="inconsistent lengths"):
        parse_candle_response(response, interval_min=5, now_ts=_ts(9, 30))


def test_parser_rejects_malformed_empty_payload():
    with pytest.raises(DataQualityError, match="missing required candle fields"):
        parse_candle_response({"status": "success", "data": {}}, interval_min=5, now_ts=_ts(9, 30))


@pytest.mark.parametrize(
    ("timestamps", "message"),
    [
        ([_ts(), _ts()], "duplicate"),
        ([_ts(9, 20), _ts()], "out of order"),
        ([_ts(9, 15), _ts(9, 26)], "aligned"),
        ([_ts(9, 15), _ts(15, 30)], "outside"),
        ([_ts(9, 15), _ts(9, 20, day=23)], "out of order"),
    ],
)
def test_parser_rejects_invalid_timestamp_sequences(timestamps, message):
    with pytest.raises(DataQualityError, match=message):
        parse_candle_response(_response(timestamps), interval_min=5, now_ts=_ts(15, 30))


def test_parser_rejects_future_timestamp():
    with pytest.raises(DataQualityError, match="future"):
        parse_candle_response(_response([_ts(9, 25)]), interval_min=5, now_ts=_ts(9, 20))


def test_parser_rejects_invalid_ohlc_and_nonfinite_values():
    response = _response([_ts()])
    response["data"]["high"] = [98.0]
    with pytest.raises(DataQualityError, match="high"):
        parse_candle_response(response, interval_min=5, now_ts=_ts(9, 30))
    response = _response([_ts()])
    response["data"]["close"] = [float("nan")]
    with pytest.raises(DataQualityError, match="valid range"):
        parse_candle_response(response, interval_min=5, now_ts=_ts(9, 30))


def test_parser_accepts_provider_envelopes_and_empty_success():
    nested = {"status": "success", "data": {"status": "success", "data": _response()["data"]}}
    assert len(parse_candle_response(nested, interval_min=5, now_ts=_ts(9, 30)).rows) == 2
    empty = {"status": "success", "data": {"timestamp": [], "open": [], "high": [], "low": [], "close": [], "volume": []}}
    assert parse_candle_response(empty, interval_min=5, now_ts=_ts(9, 30)).rows == []


def test_freshness_gate_handles_regular_session_boundary():
    rows = [{"ts": _ts()}]  # bar ends at 09:20
    require_fresh_latest_bar(rows, 5, now_ts=_ts(9, 22), grace_sec=120)
    with pytest.raises(DataQualityError, match="stale"):
        require_fresh_latest_bar(rows, 5, now_ts=_ts(9, 23), grace_sec=120)
    assert is_regular_session(_ts(10, 0))
    assert not is_regular_session(_ts(8, 0))
    assert not is_regular_session(_ts(10, 0, day=23))  # Sunday


def test_option_chain_rejects_duplicate_or_crossed_quotes():
    good = [
        {"strike": 25000, "option_type": "CE", "ltp": 10, "bid": 9, "ask": 10},
        {"strike": 25000, "option_type": "PE", "ltp": 10, "bid": 9, "ask": 10},
    ]
    assert validate_option_chain(25001, good) == 25001
    with pytest.raises(DataQualityError, match="duplicate"):
        validate_option_chain(25001, good + [good[0]])
    crossed = [dict(good[0], bid=11), good[1]]
    with pytest.raises(DataQualityError, match="exceeds ask"):
        validate_option_chain(25001, crossed)


def test_persisted_candle_batch_has_hash_and_requested_window():
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    batch = parse_candle_response(_response(), interval_min=5, now_ts=_ts(9, 30))
    repository.upsert_candle_batch(
        conn,
        "NIFTY",
        "5",
        batch.rows,
        batch.manifest("NIFTY", "5", "2026-08-24 09:15:00", "2026-08-24 09:30:00"),
    )
    stored = repository.get_candle_ingestion_batches(conn, "NIFTY")
    assert len(stored) == 1
    assert stored[0]["content_sha256"] == batch.content_sha256
    assert stored[0]["requested_from"] == "2026-08-24 09:15:00"

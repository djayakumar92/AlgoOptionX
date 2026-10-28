from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, strategies as st

from algooptionx.market.contracts import Candle, CandleError, Session, validate_batch
from algooptionx.market.aggregation import aggregate_completed

OPEN = datetime(2026, 11, 2, 9, 15, tzinfo=ZoneInfo("Asia/Kolkata"))
SESSION = Session("sim-20261102", "fixture-v1", OPEN, OPEN + timedelta(minutes=375))


def minute(i, **kwargs):
    values = dict(
        instrument_id="SIM-NIFTY",
        source_id="fixture",
        data_version="v1",
        calendar_version=SESSION.calendar_version,
        session_id=SESSION.session_id,
        source_hash="a" * 64,
        open_at=OPEN + timedelta(minutes=i),
        close_at=OPEN + timedelta(minutes=i + 1),
        available_at=OPEN + timedelta(minutes=i + 1),
        open_paise=100 + i,
        high_paise=110 + i,
        low_paise=90 + i,
        close_paise=105 + i,
        volume=i,
    )
    return Candle(**(values | kwargs))


@pytest.mark.parametrize(
    "change",
    [
        {"open_paise": True},
        {"open_paise": 1.5},
        {"open_paise": float("nan")},
        {"high_paise": 50},
        {"low_paise": 999},
        {"close_paise": 0},
        {"volume": -1},
        {"volume": True},
        {"volume_kind": "CUMULATIVE"},
        {"instrument_id": ""},
        {"source_hash": "bad"},
        {"interval_minutes": True},
        {"open_at": OPEN.replace(tzinfo=None)},
        {"available_at": OPEN},
        {"close_at": OPEN + timedelta(seconds=30)},
    ],
)
def test_strict_candle_rejects_bad_values(change):
    with pytest.raises(CandleError):
        minute(0, **change)


def test_contract_is_immutable_and_normalizes_offsets():
    c = minute(0)
    assert c.open_at == OPEN
    assert c.open_at.utcoffset() == timedelta(0)
    with pytest.raises(FrozenInstanceError):
        c.volume = 1


@pytest.mark.parametrize(
    "bars",
    [
        lambda: [minute(0), minute(0)],
        lambda: [minute(1), minute(0)],
        lambda: [minute(0), minute(1, instrument_id="OTHER")],
        lambda: [minute(0), minute(1, data_version="v2")],
        lambda: [minute(0, session_id="OTHER")],
        lambda: [minute(0, calendar_version="different")],
        lambda: [minute(-1)],
        lambda: [minute(375)],
        lambda: [
            minute(
                0,
                open_at=OPEN + timedelta(seconds=1),
                close_at=OPEN + timedelta(seconds=61),
                available_at=OPEN + timedelta(seconds=61),
            )
        ],
    ],
)
def test_batch_rejects_identity_order_and_session_errors(bars):
    with pytest.raises(CandleError):
        validate_batch(bars(), SESSION, as_of=SESSION.close_at + timedelta(hours=1))


def test_batch_rejects_future_receipt_in_strict_mode():
    with pytest.raises(CandleError, match="not yet available"):
        validate_batch([minute(0)], SESSION, as_of=OPEN)


def test_first_confirmation_uses_only_completed_anchored_30_minutes():
    bars = [minute(i) for i in range(60)]
    early = aggregate_completed(
        bars, SESSION, as_of=OPEN + timedelta(minutes=30, microseconds=-1), minutes=30
    )
    assert early.status == "INSUFFICIENT_DATA" and early.bars == ()
    result = aggregate_completed(
        bars, SESSION, as_of=OPEN + timedelta(minutes=30), minutes=30
    )
    assert result.status == "READY" and len(result.bars) == 1
    b = result.bars[0]
    assert b.open_at == OPEN and b.close_at == OPEN + timedelta(minutes=30)
    assert (b.open_paise, b.high_paise, b.low_paise, b.close_paise, b.volume) == (
        100,
        139,
        90,
        134,
        sum(range(30)),
    )
    assert b.available_at == b.close_at and b.interval_minutes == 30


@pytest.mark.parametrize("minutes", [5, 30])
def test_missing_or_late_child_prevents_ready_and_never_forward_fills(minutes):
    bars = [minute(i) for i in range(minutes * 2) if i != 2]
    result = aggregate_completed(
        bars, SESSION, as_of=OPEN + timedelta(minutes=minutes * 2), minutes=minutes
    )
    assert result.status == "INSUFFICIENT_DATA" and len(result.bars) == 1
    assert result.incomplete[0].missing_minutes == (OPEN + timedelta(minutes=2),)
    late = [
        minute(i, available_at=OPEN + timedelta(minutes=minutes + 1))
        if i == 2
        else minute(i)
        for i in range(minutes)
    ]
    result = aggregate_completed(
        late, SESSION, as_of=OPEN + timedelta(minutes=minutes), minutes=minutes
    )
    assert result.status == "INSUFFICIENT_DATA" and not result.bars
    recovered = aggregate_completed(
        late, SESSION, as_of=OPEN + timedelta(minutes=minutes + 1), minutes=minutes
    )
    assert recovered.status == "READY" and recovered.bars[
        0
    ].available_at == OPEN + timedelta(minutes=minutes + 1)


def test_no_session_tail_is_promoted_to_a_short_30_minute_candle():
    result = aggregate_completed(
        [minute(i) for i in range(375)], SESSION, as_of=SESSION.close_at, minutes=30
    )
    assert result.status == "READY" and len(result.bars) == 12
    assert result.bars[-1].close_at == OPEN + timedelta(minutes=360)


@given(
    st.integers(min_value=5, max_value=120), st.integers(min_value=1, max_value=100000)
)
def test_future_perturbation_never_changes_prior_aggregates(cutoff, future_price):
    prefix = [minute(i) for i in range(cutoff)]
    future = [
        minute(
            i,
            open_paise=future_price,
            high_paise=future_price + 10,
            low_paise=max(1, future_price - 10),
            close_paise=future_price,
        )
        for i in range(cutoff, cutoff + 15)
    ]
    as_of = OPEN + timedelta(minutes=cutoff)
    for interval in (5, 30):
        assert aggregate_completed(
            prefix, SESSION, as_of=as_of, minutes=interval
        ) == aggregate_completed(
            prefix + future, SESSION, as_of=as_of, minutes=interval
        )


def test_aggregation_rejects_duplicate_input_and_wrong_interval():
    with pytest.raises(CandleError):
        aggregate_completed(
            [minute(0), minute(0)],
            SESSION,
            as_of=OPEN + timedelta(minutes=5),
            minutes=5,
        )
    with pytest.raises(CandleError):
        aggregate_completed([], SESSION, as_of=OPEN, minutes=15)
    with pytest.raises(CandleError):
        aggregate_completed(
            [
                replace(
                    minute(0),
                    interval_minutes=5,
                    close_at=OPEN + timedelta(minutes=5),
                    available_at=OPEN + timedelta(minutes=5),
                )
            ],
            SESSION,
            as_of=OPEN + timedelta(minutes=5),
            minutes=5,
        )


@pytest.mark.parametrize(
    "change",
    [
        {"close_at": OPEN},
        {"close_at": OPEN + timedelta(days=2)},
        {"close_at": OPEN + timedelta(seconds=90)},
        {"open_at": OPEN.replace(tzinfo=None)},
    ],
)
def test_session_rejects_invalid_or_unbounded_windows(change):
    with pytest.raises(CandleError):
        replace(SESSION, **change)


def test_empty_and_preopen_results_cannot_claim_ready():
    for as_of in (OPEN - timedelta(minutes=1), OPEN, OPEN + timedelta(minutes=30)):
        result = aggregate_completed([], SESSION, as_of=as_of, minutes=30)
        assert result.status == "INSUFFICIENT_DATA" and not result.bars

from dataclasses import replace
from datetime import timedelta
import json
import socket
import sqlite3
from unittest.mock import patch

import pytest
from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

from algooptionx.research import shadow
from algooptionx.research.shadow import (
    ChainSnapshot,
    OptionQuote,
    ShadowInput,
    demo_input,
    evaluate_shadow,
    main,
)
from algooptionx.market.aggregation import aggregate_completed
from algooptionx.research.signals import market_structure as ms


def changed(request, **values):
    return ShadowInput.model_validate(
        {name: getattr(request, name) for name in ShadowInput.model_fields} | values
    )


def test_demo_reuses_actual_analytics_on_complete_inputs():
    request = demo_input()
    with patch.object(ms, "find_swings", wraps=ms.find_swings) as structure_call:
        result = evaluate_shadow(request)
    assert structure_call.called
    assert result.shadow and result.candidate is None
    assert (
        result.strategy.model_version is None and result.uncertainty.probability is None
    )
    by_id = {(o.skill_id, o.metric, o.timeframe_minutes): o for o in result.evidence}
    for minutes in (5, 30):
        bars = aggregate_completed(
            request.candles, request.session, as_of=request.as_of, minutes=minutes
        ).bars
        expected = ms.classify_structure(ms.find_swings(shadow._frame(bars)))[0]
        observation = by_id[("F02", "structure", minutes)]
        assert observation.value == expected
        assert observation.available_at == max(c.available_at for c in bars)
        assert observation.event_at == bars[-1].close_at
    assert by_id[("O06", "pcr_oi", None)].value == 1.0
    assert (
        evaluate_shadow(ShadowInput.model_validate_json(request.model_dump_json()))
        == result
    )


def test_shadow_never_connects_network_or_database(monkeypatch, tmp_path):
    request = demo_input()

    def forbidden(*args, **kwargs):
        raise AssertionError("Shadow attempted side effect")

    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    before = request.model_dump_json()
    assert evaluate_shadow(request).candidate is None
    assert request.model_dump_json() == before


@pytest.mark.parametrize("minutes", [0, 10, 29, 30, 60])
def test_warmup_and_first_confirmation_do_not_invent_structure(minutes):
    request = demo_input()
    as_of = request.session.open_at + timedelta(minutes=minutes, seconds=1)
    result = evaluate_shadow(changed(request, as_of=as_of, chain=None))
    assert result.state == "INSUFFICIENT_DATA"
    assert result.candidate is None
    thirty = next(
        o for o in result.evidence if o.skill_id == "M04" and o.timeframe_minutes == 30
    )
    assert thirty.status == ("OBSERVED" if minutes >= 30 else "INSUFFICIENT_DATA")


def test_missing_minute_invalidates_confirmation_even_if_later_windows_complete():
    request = demo_input()
    result = evaluate_shadow(
        changed(request, candles=request.candles[:2] + request.candles[3:])
    )
    assert result.state == "INSUFFICIENT_DATA"
    assert {o.reason_codes for o in result.evidence if o.skill_id == "M04"} == {
        ("MISSING_OR_LATE_MINUTES",)
    }


@pytest.mark.parametrize("mode", ["stale", "metadata", "future", "absent"])
def test_unusable_chain_never_becomes_valid_evidence(mode):
    request = demo_input()
    chain = request.chain
    if mode == "stale":
        chain = ChainSnapshot.model_validate(
            chain.model_dump()
            | {
                "event_at": request.as_of - timedelta(minutes=2),
                "available_at": request.as_of - timedelta(minutes=1),
            }
        )
    elif mode == "metadata":
        chain = ChainSnapshot.model_validate(
            chain.model_dump() | {"instrument_version": "other"}
        )
    elif mode == "future":
        chain = ChainSnapshot.model_validate(
            chain.model_dump() | {"available_at": request.as_of + timedelta(minutes=1)}
        )
    else:
        chain = None
    result = evaluate_shadow(changed(request, chain=chain))
    assert result.state == "INSUFFICIENT_DATA"
    assert (
        next(o for o in result.evidence if o.skill_id == "O05").status
        == "INSUFFICIENT_DATA"
    )


def test_future_snapshot_is_indistinguishable_from_no_snapshot():
    request = demo_input()
    future = ChainSnapshot.model_validate(
        request.chain.model_dump()
        | {"available_at": request.as_of + timedelta(minutes=1)}
    )
    assert evaluate_shadow(changed(request, chain=future)) == evaluate_shadow(
        changed(request, chain=None)
    )


@given(
    st.integers(min_value=30, max_value=330), st.integers(min_value=1, max_value=100000)
)
@settings(max_examples=20, deadline=None)
def test_future_price_changes_cannot_rewrite_earlier_shadow_output(cutoff, price):
    request = demo_input()
    as_of = request.session.open_at + timedelta(minutes=cutoff, seconds=1)
    prefix = tuple(c for c in request.candles if c.available_at <= as_of)
    future = tuple(
        replace(
            c,
            open_paise=price,
            high_paise=price + 10,
            low_paise=max(1, price - 10),
            close_paise=price,
        )
        for c in request.candles
        if c.available_at > as_of
    )
    expected = evaluate_shadow(changed(request, candles=prefix, as_of=as_of))
    assert (
        evaluate_shadow(changed(request, candles=prefix + future, as_of=as_of))
        == expected
    )


def test_future_right_neighbors_are_not_backdated_into_pivot_evidence():
    request = demo_input()
    result = evaluate_shadow(request)
    for o in result.evidence:
        assert o.event_at <= o.available_at <= result.as_of
    changed_request = changed(
        request,
        candles=(
            replace(request.candles[0], close_paise=request.candles[0].close_paise + 1),
        )
        + request.candles[1:],
    )
    assert evaluate_shadow(changed_request).decision_id != result.decision_id


@pytest.mark.parametrize(
    "case", ["duplicate", "mixed", "wrong-instrument", "wrong-calendar"]
)
def test_invalid_candle_metadata_reports_insufficient_without_execution(case):
    request = demo_input()
    candles = request.candles
    if case == "duplicate":
        candles = (candles[0],) + candles
    if case == "mixed":
        candles = (replace(candles[0], data_version="other"),) + candles[1:]
    if case == "wrong-instrument":
        request = changed(request, instrument_id="OTHER")
    if case == "wrong-calendar":
        candles = (replace(candles[0], calendar_version="other"),) + candles[1:]
    result = evaluate_shadow(changed(request, candles=candles))
    assert result.state == "INSUFFICIENT_DATA" and result.candidate is None
    assert any(o.status == "INVALID_DATA" for o in result.evidence)


@pytest.mark.parametrize(
    "change",
    [
        {"oi": -1},
        {"volume": True},
        {"bid_paise": 9000},
        {"iv_percent": float("nan")},
        {"strike_paise": 1.5},
    ],
)
def test_chain_fields_reject_malformed_quote_data(change):
    quote = demo_input().chain.quotes[0]
    with pytest.raises(ValidationError):
        OptionQuote.model_validate(quote.model_dump() | change)


def test_chain_rejects_duplicate_one_sided_and_invalid_temporal_records():
    request = demo_input()
    values = request.chain.model_dump()
    for change in (
        {"quotes": (request.chain.quotes[0],) * 2},
        {"quotes": tuple(q for q in request.chain.quotes if q.right == "CE")},
        {"available_at": request.chain.event_at - timedelta(seconds=1)},
        {"expiry": request.chain.expiry - timedelta(days=20)},
    ):
        with pytest.raises(ValidationError):
            ChainSnapshot.model_validate(values | change)


def test_outside_session_abstains_and_never_represents_a_live_window():
    request = demo_input()
    assert (
        evaluate_shadow(
            changed(request, as_of=request.session.close_at + timedelta(minutes=1))
        ).state
        == "INSUFFICIENT_DATA"
    )


def test_cli_reports_json_refuses_overwrite_and_sanitizes_bad_input(tmp_path, capsys):
    output = tmp_path / "report.json"
    assert main(["--demo", "--output", str(output)]) == 0
    result = json.loads(output.read_text())
    assert result["shadow"] is True and result["candidate"] is None
    before = output.read_bytes()
    assert main(["--demo", "--output", str(output)]) == 2
    assert output.read_bytes() == before
    bad = tmp_path / "bad.json"
    bad.write_text('{"credential":"must-not-echo"}')
    assert main(["--input", str(bad)]) == 2
    assert "must-not-echo" not in capsys.readouterr().err
    source = tmp_path / "input.json"
    source.write_text(demo_input().model_dump_json())
    result_path = tmp_path / "input-report.json"
    assert main(["--input", str(source), "--output", str(result_path)]) == 0
    assert json.loads(result_path.read_text()) == result


def test_legacy_numeric_overflow_is_explicitly_invalid_data_and_sanitized(
    tmp_path, capsys
):
    request = demo_input()
    n = 10**400
    candles = (
        replace(
            request.candles[0], open_paise=n, high_paise=n, low_paise=n, close_paise=n
        ),
    ) + request.candles[1:]
    invalid = changed(request, candles=candles)
    result = evaluate_shadow(invalid)
    assert result.state == "INSUFFICIENT_DATA"
    assert any(o.status == "INVALID_DATA" for o in result.evidence)
    path = tmp_path / "huge.json"
    path.write_text(invalid.model_dump_json())
    assert main(["--input", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "INSUFFICIENT_DATA"


def test_quote_legacy_numeric_ranges_are_bounded():
    q = demo_input().chain.quotes[0].model_dump()
    for values in (
        {"oi": 10**30},
        {"volume": 10**30},
        {"strike_paise": 10**400},
        {"iv_percent": 1e300},
    ):
        with pytest.raises(ValidationError):
            OptionQuote.model_validate(q | values)


def test_expiry_respects_next_completed_window_and_session_end():
    request = demo_input()
    now = request.session.open_at + timedelta(minutes=357, seconds=1)
    d = evaluate_shadow(changed(request, as_of=now, chain=None))
    assert d.valid_until == request.session.open_at + timedelta(minutes=360)
    d = evaluate_shadow(
        changed(
            request, as_of=request.session.close_at - timedelta(seconds=1), chain=None
        )
    )
    assert d.valid_until == request.session.close_at


def test_cli_schemas_and_existing_input_are_preserved(tmp_path, capsys):
    assert main(["--schema", "input"]) == 0
    assert "candles" in json.loads(capsys.readouterr().out)["properties"]
    assert main(["--schema"]) == 0
    assert "state" in json.loads(capsys.readouterr().out)["properties"]
    p = tmp_path / "input.json"
    p.write_text(demo_input().model_dump_json())
    before = p.read_bytes()
    assert main(["--input", str(p), "--output", str(p)]) == 2
    assert p.read_bytes() == before

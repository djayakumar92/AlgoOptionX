from datetime import datetime, timedelta, timezone
import json

import pytest
from pydantic import ValidationError

from algooptionx.intelligence.contracts import (
    Candidate,
    Decision,
    Observation,
    Source,
    Uncertainty,
)
from algooptionx.intelligence.decision import compose_shadow

NOW = datetime(2026, 11, 2, 9, 45, tzinfo=timezone.utc)


def observation(skill, metric, value, *, tf=None, unit=None, status="OBSERVED"):
    return Observation(
        skill_id=skill,
        version="test-1",
        metric=metric,
        value=value,
        unit=unit,
        status=status,
        timeframe_minutes=tf,
        event_at=NOW - timedelta(seconds=1),
        available_at=NOW,
        source_hash="a" * 64,
    )


def evidence(five="BULLISH", thirty="BULLISH", regime="TRENDING"):
    return (
        observation("M04", "completion", True, tf=5),
        observation("M04", "completion", True, tf=30),
        observation("F02", "structure", five, tf=5, unit="direction"),
        observation("F02", "structure", thirty, tf=30, unit="direction"),
        observation("M01", "structure_regime", regime, unit="regime"),
        observation("O05", "chain_quality", True),
    )


def decision(items=None):
    return compose_shadow(
        instrument_id="SIM",
        as_of=NOW,
        source=Source(
            kind="SYNTHETIC",
            dataset_id="fixture",
            sha256="b" * 64,
            calendar_version="v1",
            instrument_version="v1",
        ),
        evidence=items or evidence(),
    )


@pytest.mark.parametrize(
    "five,thirty,regime,state",
    [
        ("BULLISH", "BULLISH", "TRENDING", "BULLISH"),
        ("BEARISH", "BEARISH", "TRENDING", "BEARISH"),
        ("UNCLEAR", "UNCLEAR", "RANGING", "SIDEWAYS"),
        ("BULLISH", "BEARISH", "TRENDING", "NO_TRADE"),
        ("UNCLEAR", "UNCLEAR", "TRANSITIONAL", "NO_TRADE"),
    ],
)
def test_five_state_composition_and_no_execution_authority(five, thirty, regime, state):
    result = decision(evidence(five, thirty, regime))
    assert result.state == state
    assert result.candidate is None and result.shadow is True
    assert (
        result.uncertainty.probability is None and result.strategy.model_version is None
    )
    assert Decision.model_validate_json(result.model_dump_json()) == result
    assert decision(evidence(five, thirty, regime)).decision_id == result.decision_id


def test_missing_required_evidence_is_explicit_insufficient_data():
    items = list(evidence())
    items[0] = observation("M04", "completion", None, tf=5, status="INSUFFICIENT_DATA")
    assert decision(tuple(items)).state == "INSUFFICIENT_DATA"
    with pytest.raises(ValueError, match="Required shadow observations"):
        decision(evidence()[:-1])


@pytest.mark.parametrize(
    "change",
    [
        {"extra": True},
        {"schema_version": True},
        {"shadow": 1},
        {"shadow": False},
        {"execution_mode": "LIVE"},
        {"as_of": NOW.replace(tzinfo=None)},
        {"available_at": NOW + timedelta(seconds=1)},
        {"valid_until": NOW},
        {"valid_until": NOW + timedelta(minutes=6)},
        {"evidence": []},
        {"invalidation": []},
        {"limitations": []},
    ],
)
def test_invalid_envelopes_fail_closed(change):
    payload = decision().model_dump()
    payload.update(change)
    with pytest.raises(ValidationError):
        Decision.model_validate(payload)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "0.9", True])
def test_numeric_observations_reject_nonfinite_or_misleading_units(value):
    with pytest.raises(ValidationError):
        observation("O06", "pcr", value, unit="ratio")


def test_probability_is_not_a_rule_confidence_score_or_promotion_receipt():
    with pytest.raises(ValidationError):
        Uncertainty(kind="UNVALIDATED_RULE", probability=0.9, reason_codes=("test",))
    with pytest.raises(ValidationError):
        Uncertainty(kind="CALIBRATED_MODEL", probability=0.9, reason_codes=("test",))
    payload = decision().model_dump()
    payload["uncertainty"] = dict(
        kind="CALIBRATED_MODEL",
        probability=0.9,
        calibration_id="study-1",
        reason_codes=("test",),
    )
    with pytest.raises(ValidationError, match="disabled"):
        Decision.model_validate(payload)
    payload["strategy"]["model_version"] = "model-1"
    with pytest.raises(ValidationError, match="disabled"):
        Decision.model_validate(payload)


@pytest.mark.parametrize(
    "state,right",
    [
        ("NO_TRADE", "CE"),
        ("SIDEWAYS", "CE"),
        ("INSUFFICIENT_DATA", "PE"),
        ("BULLISH", "PE"),
        ("BEARISH", "CE"),
    ],
)
def test_candidate_cannot_override_state(state, right):
    payload = decision().model_dump()
    payload["state"] = state
    payload["candidate"] = dict(
        instrument_id="option",
        right=right,
        lots=1,
        entry_paise=100,
        stop_paise=90,
        target_paise=120,
    )
    with pytest.raises(ValidationError):
        Decision.model_validate(payload)


@pytest.mark.parametrize(
    "change",
    [
        {"lots": True},
        {"lots": 0},
        {"entry_paise": 1.5},
        {"stop_paise": 110},
        {"target_paise": 100},
    ],
)
def test_candidate_is_strict_integer_long_only(change):
    payload = dict(
        instrument_id="option",
        right="CE",
        lots=1,
        entry_paise=100,
        stop_paise=90,
        target_paise=120,
    )
    with pytest.raises(ValidationError):
        Candidate.model_validate(payload | change)


def test_duplicate_identity_future_evidence_and_contradictory_direction_rejected():
    d = decision()
    payload = d.model_dump()
    payload["evidence"] = (d.evidence[0],) * 6
    with pytest.raises(ValidationError):
        Decision.model_validate(payload)
    payload = d.model_dump()
    payload["evidence"] = payload["evidence"][:-1]
    with pytest.raises(ValidationError, match="required evidence"):
        Decision.model_validate(payload)
    payload = d.model_dump()
    payload["evidence"][2]["value"] = "BEARISH"
    with pytest.raises(ValidationError, match="contradicts"):
        Decision.model_validate(payload)
    payload = d.model_dump()
    payload["evidence"][0]["available_at"] = NOW + timedelta(seconds=1)
    payload["available_at"] = NOW + timedelta(seconds=1)
    with pytest.raises(ValidationError, match="not yet available"):
        Decision.model_validate(payload)


def test_records_are_deeply_immutable_and_schema_exportable():
    d = decision()
    with pytest.raises(ValidationError):
        d.state = "BEARISH"
    with pytest.raises(ValidationError):
        d.evidence[0].value = False
    assert isinstance(d.evidence, tuple)
    assert (
        json.loads(json.dumps(Decision.model_json_schema()))["additionalProperties"]
        is False
    )


def test_expiry_is_bound_into_decision_identity():
    d = decision()
    second = compose_shadow(
        instrument_id=d.instrument_id,
        as_of=d.as_of,
        source=d.source,
        evidence=d.evidence,
        valid_until=d.as_of + timedelta(minutes=1),
    )
    assert second.decision_id != d.decision_id
    assert second.valid_until != d.valid_until


@pytest.mark.parametrize("tf", [5.0, "5", True])
def test_timeframe_is_an_exact_integer(tf):
    with pytest.raises(ValidationError):
        observation("M04", "completion", True, tf=tf)


@pytest.mark.parametrize(
    "change", [{"value": "UNKNOWN"}, {"unit": None}, {"timeframe_minutes": 5}]
)
def test_required_regime_cannot_mislabel_unknown_or_incompatible_evidence(change):
    row = observation("M01", "structure_regime", "TRENDING", unit="regime")
    with pytest.raises(ValidationError):
        Observation.model_validate(row.model_dump() | change)


def test_no_trade_cannot_hide_missing_required_inputs():
    d = decision()
    payload = d.model_dump()
    payload["state"] = "NO_TRADE"
    payload["evidence"] = payload["evidence"][:-1]
    with pytest.raises(ValidationError, match="required evidence"):
        Decision.model_validate(payload)
    items = list(evidence())
    items[0] = observation("M04", "completion", False, tf=5)
    assert decision(tuple(items)).state == "INSUFFICIENT_DATA"

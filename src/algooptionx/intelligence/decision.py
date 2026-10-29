"""Deterministic composition of already computed shadow observations, not a model."""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json

from algooptionx.intelligence.contracts import (
    Decision,
    Observation,
    Source,
    Strategy,
    Uncertainty,
    REQUIRED,
)
from algooptionx.market.contracts import utc


def compose_shadow(
    *,
    instrument_id: str,
    as_of: datetime,
    source: Source,
    evidence: tuple[Observation, ...],
    valid_until: datetime | None = None,
) -> Decision:
    as_of = utc(as_of)
    by_id = {(o.skill_id, o.metric, o.timeframe_minutes): o for o in evidence}
    if any(identity not in by_id for identity in REQUIRED):
        raise ValueError(
            "Required shadow observations must be explicitly recorded, including missing inputs."
        )
    required = [by_id[key] for key in REQUIRED]
    if any(o.status != "OBSERVED" for o in required) or any(
        by_id[key].value is not True for key in (REQUIRED[0], REQUIRED[1], REQUIRED[5])
    ):
        state, reason = "INSUFFICIENT_DATA", "MISSING_OR_INVALID_REQUIRED_EVIDENCE"
    else:
        five = by_id[("F02", "structure", 5)].value
        thirty = by_id[("F02", "structure", 30)].value
        regime = by_id[("M01", "structure_regime", None)].value
        if five == thirty and five in ("BULLISH", "BEARISH"):
            state, reason = five, "AGREEING_CONFIRMED_STRUCTURE"
        elif five == thirty == "UNCLEAR" and regime == "RANGING":
            state, reason = "SIDEWAYS", "RANGE_CONTEXT_WITHOUT_DIRECTION"
        else:
            state, reason = "NO_TRADE", "CONFLICTING_OR_UNCLEAR_STRUCTURE"
    expiry = (
        utc(valid_until) if valid_until is not None else as_of + timedelta(minutes=5)
    )
    strategy = Strategy(id="legacy-analytics-shadow", version="1", model_version=None)
    material = {
        "instrument_id": instrument_id,
        "as_of": as_of.isoformat(),
        "valid_until": expiry.isoformat(),
        "source": source.model_dump(mode="json"),
        "evidence": [o.model_dump(mode="json") for o in evidence],
        "strategy": strategy.model_dump(mode="json"),
        "state": state,
    }
    identity = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return Decision(
        decision_id=identity,
        state=state,
        instrument_id=instrument_id,
        as_of=as_of,
        available_at=max(o.available_at for o in evidence),
        valid_until=expiry,
        source=source,
        strategy=strategy,
        evidence=evidence,
        uncertainty=Uncertainty(
            kind="UNVALIDATED_RULE",
            reason_codes=(reason, "SHADOW_ONLY", "NOT_A_TRAINED_MODEL"),
        ),
        invalidation=(
            "New completed bar, source correction, session or policy change",
        ),
        candidate=None,
        limitations=(
            "Shadow-only legacy rules; no execution, calibrated prediction or model promotion.",
            "Single-session data does not establish historical or out-of-sample validity.",
            "Daily-history baseline and observed dealer positioning are unavailable.",
            "OI metrics are observations, not proof of institutional intent.",
        ),
    )

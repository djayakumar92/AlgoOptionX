"""Strict immutable analytical envelopes; schema validity is never trading permission."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from algooptionx.market.contracts import utc

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)
]
Hash = Annotated[
    str, StringConstraints(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
]
REQUIRED = (
    ("M04", "completion", 5),
    ("M04", "completion", 30),
    ("F02", "structure", 5),
    ("F02", "structure", 30),
    ("M01", "structure_regime", None),
    ("O05", "chain_quality", None),
)
State = Literal["BULLISH", "BEARISH", "SIDEWAYS", "NO_TRADE", "INSUFFICIENT_DATA"]


class Record(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        allow_inf_nan=False,
        revalidate_instances="always",
    )


class Source(Record):
    kind: Literal["SYNTHETIC", "HISTORICAL", "LICENSED_LIVE"]
    dataset_id: Name
    sha256: Hash
    calendar_version: Name
    instrument_version: Name


class Strategy(Record):
    id: Name
    version: Name
    model_version: Name | None = None


class Observation(Record):
    skill_id: Name
    version: Name
    metric: Name
    status: Literal[
        "OBSERVED", "INSUFFICIENT_DATA", "UNSUPPORTED", "CONFLICT", "INVALID_DATA"
    ]
    event_at: AwareDatetime
    available_at: AwareDatetime
    value: str | int | float | bool | None
    unit: (
        Literal[
            "direction", "regime", "ratio", "points", "percent", "rule-score", "count"
        ]
        | None
    )
    source_hash: Hash
    timeframe_minutes: Literal[5, 30] | None = None
    reason_codes: tuple[Name, ...] = ()

    @field_validator("timeframe_minutes", mode="before")
    @classmethod
    def exact_timeframe(cls, value):
        if value is not None and type(value) is not int:
            raise ValueError("Timeframe must be an integer or null.")
        return value

    @field_validator("event_at", "available_at")
    @classmethod
    def normalize_time(cls, value: datetime):
        return utc(value)

    @model_validator(mode="after")
    def meaning(self):
        if self.event_at > self.available_at:
            raise ValueError("Observation event time cannot follow availability.")
        if self.status == "OBSERVED" and self.value is None:
            raise ValueError("Observed evidence requires a value.")
        if (
            self.unit in ("ratio", "points", "percent", "rule-score", "count")
            and self.value is not None
            and type(self.value) not in (int, float)
        ):
            raise ValueError(
                "Numeric measurements require finite numeric values, not text or booleans."
            )
        if (
            self.unit in ("direction", "regime")
            and self.value is not None
            and not isinstance(self.value, str)
        ):
            raise ValueError("Categorical measurements require text.")
        key = (self.skill_id, self.metric)
        if key == ("M04", "completion"):
            if (
                self.timeframe_minutes not in (5, 30)
                or self.unit is not None
                or self.value is not None
                and type(self.value) is not bool
            ):
                raise ValueError(
                    "Completion evidence requires a5/30-minute boolean without a numeric unit."
                )
        if key == ("F02", "structure"):
            if (
                self.timeframe_minutes not in (5, 30)
                or self.unit != "direction"
                or self.value not in (None, "BULLISH", "BEARISH", "UNCLEAR")
            ):
                raise ValueError(
                    "Structure evidence has an invalid timeframe, value or unit."
                )
        if key == ("M01", "structure_regime"):
            if (
                self.timeframe_minutes is not None
                or self.unit != "regime"
                or self.status == "OBSERVED"
                and self.value not in ("TRENDING", "RANGING", "TRANSITIONAL")
            ):
                raise ValueError(
                    "An observed regime must be a known regime, not missing/UNKNOWN data."
                )
        if key == ("O05", "chain_quality"):
            if (
                self.timeframe_minutes is not None
                or self.unit is not None
                or self.value is not None
                and type(self.value) is not bool
            ):
                raise ValueError(
                    "Chain quality requires a boolean without a numeric unit."
                )
        if (
            self.unit == "count"
            and self.value is not None
            and (type(self.value) is not int or self.value < 0)
        ):
            raise ValueError("Counts must be nonnegative integers.")
        return self


class Uncertainty(Record):
    kind: Literal["UNVALIDATED_RULE", "CALIBRATED_MODEL", "UNKNOWN"]
    probability: float | None = Field(default=None, ge=0, le=1)
    calibration_id: Name | None = None
    reason_codes: tuple[Name, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def probability_kind(self):
        if self.kind != "CALIBRATED_MODEL" and (
            self.probability is not None or self.calibration_id is not None
        ):
            raise ValueError(
                "Rule/unknown uncertainty cannot claim a calibrated probability."
            )
        if self.kind == "CALIBRATED_MODEL" and (
            self.probability is None or self.calibration_id is None
        ):
            raise ValueError(
                "A calibrated measurement needs probability and calibration identity."
            )
        return self


class Candidate(Record):
    instrument_id: Name
    right: Literal["CE", "PE"]
    lots: int = Field(gt=0)
    entry_paise: int = Field(gt=0)
    stop_paise: int = Field(gt=0)
    target_paise: int = Field(gt=0)

    @model_validator(mode="after")
    def buying_only(self):
        if not self.stop_paise < self.entry_paise < self.target_paise:
            raise ValueError("Long-only candidates require stop < entry < target.")
        return self


class Decision(Record):
    schema_version: Literal[1] = 1
    decision_id: Name
    state: State
    instrument_id: Name
    as_of: AwareDatetime
    available_at: AwareDatetime
    valid_until: AwareDatetime
    source: Source
    strategy: Strategy
    evidence: tuple[Observation, ...] = Field(min_length=1)
    uncertainty: Uncertainty
    invalidation: tuple[Name, ...] = Field(min_length=1)
    candidate: Candidate | None = None
    execution_mode: Literal["PAPER"] = "PAPER"
    shadow: Literal[True] = True
    limitations: tuple[Name, ...] = Field(min_length=1)

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int:
            raise ValueError("schema_version must be the integer 1.")
        return value

    @field_validator("shadow", mode="before")
    @classmethod
    def exact_shadow(cls, value):
        if type(value) is not bool or value is not True:
            raise ValueError("This contract is shadow-only.")
        return value

    @field_validator("as_of", "available_at", "valid_until")
    @classmethod
    def normalize_time(cls, value: datetime):
        return utc(value)

    @model_validator(mode="after")
    def temporal_and_semantic_binding(self):
        if self.available_at != max(o.available_at for o in self.evidence):
            raise ValueError(
                "Decision availability must equal the latest observation availability."
            )
        if self.available_at > self.as_of:
            raise ValueError(
                "A decision cannot use evidence not yet available at as_of."
            )
        if not timedelta(0) < self.valid_until - self.as_of <= timedelta(minutes=5):
            raise ValueError("Decision TTL must be positive and at most five minutes.")
        if (
            self.state in ("SIDEWAYS", "NO_TRADE", "INSUFFICIENT_DATA")
            and self.candidate is not None
        ):
            raise ValueError(
                "Abstaining/range states cannot contain an execution candidate."
            )
        if self.candidate is not None:
            expected = "CE" if self.state == "BULLISH" else "PE"
            if self.candidate.right != expected:
                raise ValueError("Candidate right contradicts the directional state.")
        if (
            self.uncertainty.kind == "CALIBRATED_MODEL"
            or self.strategy.model_version is not None
        ):
            raise ValueError(
                "Calibrated model claims are disabled until a trusted model/calibration registry and promotion binding exist."
            )
        identities = [
            (o.skill_id, o.metric, o.timeframe_minutes) for o in self.evidence
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("Duplicate observation identities are ambiguous.")
        if self.state != "INSUFFICIENT_DATA":
            by_id = {
                (o.skill_id, o.metric, o.timeframe_minutes): o for o in self.evidence
            }
            if any(
                key not in by_id or by_id[key].status != "OBSERVED" for key in REQUIRED
            ):
                raise ValueError(
                    "Directional/range states require all current required evidence."
                )
            if any(
                by_id[key].value is not True
                for key in (REQUIRED[0], REQUIRED[1], REQUIRED[5])
            ):
                raise ValueError("Completed windows and a valid chain are required.")
        if self.state in ("BULLISH", "BEARISH", "SIDEWAYS"):
            expected = self.state if self.state != "SIDEWAYS" else "UNCLEAR"
            if any(by_id[key].value != expected for key in (REQUIRED[2], REQUIRED[3])):
                raise ValueError("State contradicts confirmed structure evidence.")
            if self.state == "SIDEWAYS" and by_id[REQUIRED[4]].value != "RANGING":
                raise ValueError("UNCLEAR structure alone does not prove a range.")
        return self

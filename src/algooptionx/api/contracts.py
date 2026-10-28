"""Strict request contracts for the paper-workspace API."""

from pydantic import BaseModel, ConfigDict, Field


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    key: str = Field(min_length=1, max_length=160)
    action: str
    instrument: str | None = None
    position_id: str | None = None
    lots: int | None = Field(default=None, ge=1, le=5)
    running: bool | None = None
    autonomous: bool | None = None
    killed: bool | None = None


class Replay(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    bars: int = Field(default=120, ge=6, le=374)

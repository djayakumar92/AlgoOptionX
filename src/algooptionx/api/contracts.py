"""Strict request contracts for the paper-workspace API."""

from pydantic import BaseModel, ConfigDict, Field


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_account_id: str | None = Field(default=None, min_length=1, max_length=80)
    expected_tenant_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
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
    expected_account_id: str | None = Field(default=None, min_length=1, max_length=80)
    expected_tenant_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    bars: int = Field(default=120, ge=6, le=374)


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_account_id: str | None = Field(default=None, min_length=1, max_length=80)
    expected_tenant_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from algooptionx.research.execution.policy import ExecutionPolicy, ExecutionPolicyError

from algooptionx.paths import PROJECT_ROOT, RESEARCH_SETTINGS
TOKEN_LIFETIME_HOURS = 24


class ConfigError(RuntimeError):
    """Raised when configuration is missing or invalid. Message is user-facing."""


@dataclass(frozen=True)
class UnderlyingConfig:
    symbol: str
    segment: str
    expiries_tracked: int
    strike_window: int


@dataclass(frozen=True)
class PollingConfig:
    option_chain_interval_sec: float
    historical_refresh_interval_sec: float


@dataclass(frozen=True)
class HistoricalConfig:
    intraday_interval_min: int
    backfill_days: int


@dataclass(frozen=True)
class HlcConfig:
    threshold_points: float


@dataclass(frozen=True)
class TradePlanConfig:
    target_points_per_day: float
    max_trades_per_day: int


@dataclass(frozen=True)
class RiskConfig:
    capital: float
    max_risk_pct_per_trade: float
    max_daily_loss_pct: float


@dataclass(frozen=True)
class Settings:
    client_id: str
    access_token: str
    token_issued_at: datetime
    underlying: UnderlyingConfig
    polling: PollingConfig
    historical: HistoricalConfig
    hlc: HlcConfig
    trade_plan: TradePlanConfig
    risk: RiskConfig
    execution: ExecutionPolicy
    db_path: Path
    retention_days: int
    log_level: str
    log_dir: Path

    @property
    def token_age_hours(self) -> float:
        return (datetime.now() - self.token_issued_at).total_seconds() / 3600

    @property
    def token_is_stale(self) -> bool:
        return self.token_age_hours >= TOKEN_LIFETIME_HOURS


def _load_toml(path: Path) -> dict:
    if not path.exists():
        raise ConfigError(
            f"Missing settings file: {path}\n"
            "This should have been created as part of project setup."
        )
    with path.open("rb") as f:
        return tomllib.load(f)


def load_settings(env_path: Path | None = None, settings_path: Path | None = None) -> Settings:
    load_dotenv(env_path or PROJECT_ROOT / ".env")

    client_id = os.environ.get("DHAN_CLIENT_ID", "").strip()
    access_token = os.environ.get("DHAN_ACCESS_TOKEN", "").strip()
    issued_at_raw = os.environ.get("DHAN_TOKEN_ISSUED_AT", "").strip()

    missing = [
        name
        for name, value in (
            ("DHAN_CLIENT_ID", client_id),
            ("DHAN_ACCESS_TOKEN", access_token),
            ("DHAN_TOKEN_ISSUED_AT", issued_at_raw),
        )
        if not value
    ]
    if missing:
        raise ConfigError(
            "Missing required settings in .env: " + ", ".join(missing) + "\n"
            "Copy .env.example to .env and fill in your DhanHQ credentials.\n"
            "Get a token at https://web.dhan.co -> profile -> Access DhanHQ APIs."
        )

    try:
        token_issued_at = datetime.fromisoformat(issued_at_raw)
    except ValueError as exc:
        raise ConfigError(
            f"DHAN_TOKEN_ISSUED_AT='{issued_at_raw}' is not a valid ISO timestamp "
            "(expected e.g. 2026-08-22T09:00:00)."
        ) from exc

    toml_data = _load_toml(settings_path or RESEARCH_SETTINGS)

    underlying = UnderlyingConfig(**toml_data["underlying"])
    polling = PollingConfig(**toml_data["polling"])
    historical = HistoricalConfig(**toml_data["historical"])
    hlc = HlcConfig(**toml_data["hlc"])
    trade_plan = TradePlanConfig(**toml_data["trade_plan"])
    risk = RiskConfig(**toml_data["risk"])

    try:
        execution = ExecutionPolicy.from_mapping(toml_data.get("execution", {}))
        environment_mode = os.environ.get("DHAN_EXECUTION_MODE")
        if environment_mode is not None:
            environment_policy = ExecutionPolicy(mode=environment_mode.strip())
            if environment_policy != execution:
                raise ExecutionPolicyError(
                    "DHAN_EXECUTION_MODE cannot override config/research.toml [execution].mode."
                )
    except ExecutionPolicyError as exc:
        raise ConfigError(f"Invalid paper-only execution configuration: {exc}") from exc

    if polling.option_chain_interval_sec < 3.0:
        raise ConfigError(
            "config/research.toml: polling.option_chain_interval_sec must be >= 3.0 "
            "(DhanHQ option chain rate limit is 1 request/3s)."
        )

    settings = Settings(
        client_id=client_id,
        access_token=access_token,
        token_issued_at=token_issued_at,
        underlying=underlying,
        polling=polling,
        historical=historical,
        hlc=hlc,
        trade_plan=trade_plan,
        risk=risk,
        execution=execution,
        db_path=PROJECT_ROOT / toml_data["storage"]["db_path"],
        retention_days=toml_data["storage"].get("retention_days", 14),
        log_level=toml_data["logging"]["level"],
        log_dir=PROJECT_ROOT / toml_data["logging"]["log_dir"],
    )

    if settings.token_is_stale:
        raise ConfigError(
            f"DhanHQ access token is {settings.token_age_hours:.1f}h old "
            f"(tokens expire after {TOKEN_LIFETIME_HOURS}h). "
            "Generate a fresh one at https://web.dhan.co -> profile -> Access DhanHQ APIs, "
            "then update DHAN_ACCESS_TOKEN and DHAN_TOKEN_ISSUED_AT in .env."
        )

    return settings


def load_settings_or_exit() -> Settings:
    try:
        return load_settings()
    except ConfigError as exc:
        print(f"Configuration error:\n{exc}", file=sys.stderr)
        raise SystemExit(1) from exc

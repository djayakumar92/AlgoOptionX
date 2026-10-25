from datetime import datetime
from pathlib import Path

import pytest

from dhan_analyzer.config import ConfigError, load_settings
from dhan_analyzer.execution.policy import ExecutionPolicy, ExecutionPolicyError


def test_execution_policy_defaults_to_paper():
    assert ExecutionPolicy.from_mapping({}) == ExecutionPolicy(mode="PAPER")


def test_execution_policy_accepts_only_paper():
    assert ExecutionPolicy.from_mapping({"mode": "PAPER"}).mode == "PAPER"
    with pytest.raises(ExecutionPolicyError, match="Only PAPER"):
        ExecutionPolicy.from_mapping({"mode": "LIVE"})


@pytest.mark.parametrize("value", [None, [], "PAPER", {"mode": 1}, {"mode": "PAPER", "allow_live": True}])
def test_execution_policy_rejects_malformed_or_unknown_settings(value):
    with pytest.raises(ExecutionPolicyError):
        ExecutionPolicy.from_mapping(value)


def _write_settings(path: Path, mode: str | None = "PAPER") -> None:
    project_root = Path(__file__).resolve().parents[1]
    source = (project_root / "settings.toml").read_text(encoding="utf-8")
    section = '\n[execution]\n# The only supported mode. Live execution is intentionally unavailable.\nmode = "PAPER"\n'
    if mode is None:
        source = source.replace(section, "\n")
    else:
        source = source.replace('mode = "PAPER"', f'mode = "{mode}"')
    path.write_text(source, encoding="utf-8")


def _set_dummy_credentials(monkeypatch):
    monkeypatch.setenv("DHAN_CLIENT_ID", "test-client")
    monkeypatch.setenv("DHAN_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("DHAN_TOKEN_ISSUED_AT", datetime.now().isoformat())
    monkeypatch.delenv("DHAN_EXECUTION_MODE", raising=False)


def test_load_settings_defaults_missing_execution_section_to_paper(tmp_path, monkeypatch):
    _set_dummy_credentials(monkeypatch)
    settings_path = tmp_path / "settings.toml"
    _write_settings(settings_path, mode=None)

    settings = load_settings(env_path=tmp_path / "missing.env", settings_path=settings_path)

    assert settings.execution == ExecutionPolicy(mode="PAPER")


def test_load_settings_rejects_live_mode_in_toml(tmp_path, monkeypatch):
    _set_dummy_credentials(monkeypatch)
    settings_path = tmp_path / "settings.toml"
    _write_settings(settings_path, mode="LIVE")

    with pytest.raises(ConfigError, match="paper-only"):
        load_settings(env_path=tmp_path / "missing.env", settings_path=settings_path)


def test_load_settings_rejects_live_mode_environment_override(tmp_path, monkeypatch):
    _set_dummy_credentials(monkeypatch)
    monkeypatch.setenv("DHAN_EXECUTION_MODE", "LIVE")
    settings_path = tmp_path / "settings.toml"
    _write_settings(settings_path, mode="PAPER")

    with pytest.raises(ConfigError, match="paper-only"):
        load_settings(env_path=tmp_path / "missing.env", settings_path=settings_path)

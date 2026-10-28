"""Shared repository paths without market-data or broker dependencies."""

import os
from pathlib import Path


def repository_root() -> Path:
    """Support editable source installs and an explicit root for packaged use."""
    configured = os.environ.get("ALGOOPTIONX_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    source_root = Path(__file__).resolve().parents[2]
    return (
        source_root
        if (source_root / "pyproject.toml").is_file()
        else Path.cwd().resolve()
    )


PROJECT_ROOT = repository_root()
WEB_ROOT = PROJECT_ROOT / "apps" / "web"
RESEARCH_SETTINGS = PROJECT_ROOT / "config" / "research.toml"
TRADING_GUIDE = PROJECT_ROOT / "docs" / "guides" / "trading-research.md"

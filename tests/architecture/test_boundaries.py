"""Guard the source-layout and dependency boundaries introduced by the refactor."""

import ast
from importlib.metadata import distribution
from pathlib import Path
import tomllib

from algooptionx.paths import PROJECT_ROOT, RESEARCH_SETTINGS, TRADING_GUIDE, WEB_ROOT


def test_offline_workspace_cannot_depend_on_broker_research_or_development_tools():
    forbidden = ("algooptionx.research", "algooptionx_harness")
    for folder in ("api", "market", "paper"):
        for path in (PROJECT_ROOT / "src" / "algooptionx" / folder).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                modules = []
                if isinstance(node, ast.ImportFrom):
                    modules = [node.module or ""]
                elif isinstance(node, ast.Import):
                    modules = [item.name for item in node.names]
                assert not any(module.startswith(forbidden) for module in modules), path


def test_repository_paths_keep_config_assets_and_existing_financial_storage():
    assert WEB_ROOT == PROJECT_ROOT / "apps" / "web"
    assert (WEB_ROOT / "package.json").is_file()
    assert RESEARCH_SETTINGS == PROJECT_ROOT / "config" / "research.toml"
    assert TRADING_GUIDE.is_file()
    with RESEARCH_SETTINGS.open("rb") as stream:
        settings = tomllib.load(stream)
    assert settings["storage"]["db_path"] == "data/dhan_analyzer.db"
    assert settings["execution"]["mode"] == "PAPER"


def test_installed_entrypoints_resolve_the_canonical_source_packages():
    entries = {
        entry.name: entry
        for entry in distribution("algooptionx").entry_points
        if entry.group == "console_scripts"
    }
    expected = {
        "algooptionx": "algooptionx.api.app:run",
        "algooptionx-harness": "algooptionx_harness.cli:main",
        "algooptionx-research": "algooptionx.research.main:run",
        "dhan-analyzer": "algooptionx.research.main:run",
    }
    for name, value in expected.items():
        assert entries[name].value == value
        assert callable(entries[name].load())


def test_shared_web_primitives_do_not_import_feature_modules():
    import re

    shared = WEB_ROOT / "src" / "shared"
    features = WEB_ROOT / "src" / "features"
    for path in [*shared.rglob("*.ts"), *shared.rglob("*.tsx")]:
        for imported in re.findall(
            r"""(?:from|import)\s*["']([^"']+)["']""", path.read_text()
        ):
            if imported.startswith("."):
                target = (path.parent / imported).resolve()
                assert not target.is_relative_to(features), path

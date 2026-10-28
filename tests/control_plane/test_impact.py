"""Git selection and automatic execution must not hide changed code or failing tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from algooptionx_harness import impact
from algooptionx_harness.cli import main
from algooptionx_harness.models import Check
from algooptionx_harness.workspace import HarnessError, digest, snapshot


def git(root, *args):
    return (
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
        .stdout.decode()
        .strip()
    )


def commit(root):
    git(root, "add", ".")
    git(
        root,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@invalid",
        "commit",
        "-qm",
        "fixture",
    )
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    (root / ".gitignore").write_text(
        ".harness/\n.env\n__pycache__/\n.pytest_cache/\n.venv/\n"
    )
    spec = root / "docs/requirements/development-harness.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("Never hide failed test evidence.\n")
    path = root / "src/algooptionx/paper/engine.py"
    path.parent.mkdir(parents=True)
    path.write_text("original\n")
    commit(root)
    return root


@pytest.mark.parametrize(
    "path,suites,browser",
    [
        ("src/algooptionx/paper/engine.py", ["architecture", "paper"], True),
        ("src/algooptionx/api/app.py", ["architecture", "paper"], True),
        ("src/algooptionx/market/simulator.py", ["architecture", "paper"], True),
        (
            "src/algooptionx/research/signals/risk.py",
            ["architecture", "research"],
            False,
        ),
        ("tests/research/test_risk.py", ["architecture", "research"], False),
        ("src/algooptionx_harness/runner.py", ["architecture", "control_plane"], False),
        (
            ".agents/skills/evidence-review/SKILL.md",
            ["architecture", "control_plane"],
            False,
        ),
        ("apps/web/src/shared/theme/useWorkspaceTheme.ts", ["architecture"], True),
        ("README.md", ["architecture"], False),
        ("pyproject.toml", list(impact.SUITES), True),
        ("uv.lock", list(impact.SUITES), True),
        (".github/workflows/ci.yml", list(impact.SUITES), True),
        ("src/algooptionx/paths.py", list(impact.SUITES), True),
        ("new_unknown_module.py", list(impact.SUITES), True),
        ("tests/conftest.py", list(impact.SUITES), True),
    ],
)
def test_conservative_component_selection(path, suites, browser):
    plan = impact.select_checks([path])
    assert plan["python_suites"] == suites
    assert plan["needs_browser"] == browser
    assert all("--update-snapshots" not in c["argv"] for c in plan["checks"])
    assert all(Check.model_validate(c) for c in plan["checks"])


def test_mixed_changes_union_suites_and_frontend_builds():
    plan = impact.select_checks(
        [
            "tests/paper/test_engine.py",
            "tests/control_plane/test_impact.py",
            "apps/web/src/features/research/ResearchApp.tsx",
        ]
    )
    assert plan["python_suites"] == ["architecture", "control_plane", "paper"]
    assert {c["id"] for c in plan["checks"]} == {
        "python",
        "config",
        "lint",
        "research-build",
        "build",
        "browser",
    }
    assert plan["visual_review_required"]


def test_detects_committed_staged_unstaged_renamed_deleted_and_untracked(repo):
    base = git(repo, "rev-parse", "HEAD")
    original = "src/algooptionx/paper/engine.py"
    renamed = "src/algooptionx/research/renamed.py"
    (repo / renamed).parent.mkdir(parents=True)
    git(repo, "mv", original, renamed)
    commit(repo)
    (repo / "staged.py").write_text("staged\n")
    git(repo, "add", "staged.py")
    (repo / renamed).write_text("unstaged\n")
    (repo / "new file.py").write_text("untracked\n")
    (repo / ".env").write_text("ignored\n")
    (repo / "docs/requirements/development-harness.md").unlink()
    plan = impact.plan_changes(repo, base)
    assert {
        original,
        renamed,
        "staged.py",
        "new file.py",
        "docs/requirements/development-harness.md",
    } <= set(plan["changed_files"])
    assert ".env" not in plan["changed_files"]
    assert set(plan["python_suites"]) == set(impact.SUITES)


def test_staged_change_is_not_hidden_by_worktree_reverting_to_head(repo):
    path = repo / "src/algooptionx/paper/engine.py"
    path.write_text("staged change\n")
    git(repo, "add", str(path))
    path.write_text("original\n")
    assert str(path.relative_to(repo)) in impact.plan_changes(repo)["changed_files"]


def test_empty_checkout_diff_does_not_claim_passing_tests(repo):
    plan = impact.plan_changes(repo)
    assert plan["status"] == "no_changes"
    assert not plan["checks"]
    result = impact.run_changes(repo, plan)
    assert result["status"] == "no_changes"
    assert result["tests_run"] is False


def test_bad_base_fails_and_explicit_full_runs_without_it(repo):
    with pytest.raises(HarnessError, match="base is unavailable"):
        impact.plan_changes(repo, "missing-ref")
    with pytest.raises(HarnessError, match="valid Git base"):
        impact.plan_changes(repo, "--help")
    assert impact.plan_changes(repo, "missing-ref", full=True)["mode"] == "full"


def test_disconnected_history_falls_back_to_all_tests(repo):
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "--orphan", "disconnected")
    git(repo, "rm", "-rf", ".")
    (repo / ".gitignore").write_text(".harness/\n")
    (repo / "new.md").write_text("unrelated\n")
    commit(repo)
    plan = impact.plan_changes(repo, base)
    assert plan["mode"] == "full" and plan["fallback"]
    assert plan["needs_browser"]


def test_stale_selection_cannot_run(repo):
    plan = impact.plan_changes(repo, full=True)
    (repo / "new.py").write_text("edited\n")
    with pytest.raises(HarnessError, match="changed after selection"):
        impact.run_changes(repo, plan)


@pytest.mark.parametrize("passes", [True, False])
def test_real_selected_execution_retains_and_verifies_exit_status(repo, passes):
    test_path = repo / "test_feature.py"
    test_path.write_text(f"def test_feature():\n    assert {passes}\n")
    plan = impact.plan_changes(repo)
    # A tiny real test command exercises the same subprocess/evidence path without recursively running this suite.
    plan["checks"] = [
        Check(
            id="python",
            kind="pytest",
            argv=[
                sys.executable,
                "-m",
                "pytest",
                "test_feature.py",
                "-q",
                "--junitxml={run_dir}/pytest.xml",
            ],
            report="{run_dir}/pytest.xml",
        ).model_dump(mode="json")
    ]
    plan["needs_browser"] = False
    result = impact.run_changes(repo, plan)
    assert result["status"] == ("passed" if passes else "failed")
    evidence = json.loads(Path(result["evidence"]).read_text())
    assert evidence["results"][0]["exit_code"] == (0 if passes else 1)
    assert evidence["source_digest"] == digest(snapshot(repo))
    assert (Path(result["task"]).parent / "baseline-files/test_feature.py").is_file()
    assert not result["human_approval"]


def test_watch_debounces_serializes_and_retests_edits_during_run(repo, monkeypatch):
    calls = []
    clock = [0.0]
    sleeps = [0]
    source = repo / "src/algooptionx/paper/engine.py"
    source.write_text("first edit\n")
    monkeypatch.setattr(impact.time, "monotonic", lambda: clock[0])

    def sleep(seconds):
        clock[0] += seconds
        sleeps[0] += 1
        if sleeps[0] == 1:
            source.write_text("second edit\n")
        if sleeps[0] > 9:
            raise KeyboardInterrupt

    def run(root, plan):
        calls.append(plan["source_digest"])
        if len(calls) == 1:
            source.write_text("changed while tests were running\n")
        return {"status": "passed"}

    monkeypatch.setattr(impact.time, "sleep", sleep)
    monkeypatch.setattr(impact, "run_changes", run)
    with pytest.raises(KeyboardInterrupt):
        impact.watch_changes(repo, "HEAD", interval=1, debounce=2)
    assert len(calls) == 2 and calls[0] != calls[1]


def test_watch_freezes_base_across_new_commits(repo, monkeypatch):
    bases = []
    original_base = git(repo, "rev-parse", "HEAD")

    def plan(root, base, **kwargs):
        bases.append(base)
        return {"status": "selected"}

    def run(*args):
        (repo / "new.py").write_text("new commit\n")
        commit(repo)
        return {"status": "passed"}

    sleeps = [0]

    def sleep(_):
        sleeps[0] += 1
        if sleeps[0] > 1:
            raise KeyboardInterrupt

    monkeypatch.setattr(impact, "plan_changes", plan)
    monkeypatch.setattr(impact, "run_changes", run)
    monkeypatch.setattr(impact.time, "sleep", sleep)
    with pytest.raises(KeyboardInterrupt):
        impact.watch_changes(repo, "HEAD", debounce=0)
    assert bases == [original_base, original_base]


def test_cli_plan_and_no_change_exit_codes(repo, capsys):
    assert main(["--root", str(repo), "test-changes", "--plan"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "no_changes"
    assert main(["--root", str(repo), "test-changes", "--base", "missing"]) == 2
    assert json.loads(capsys.readouterr().err)["status"] == "blocked"
    assert main(["--root", str(repo), "test-changes", "--plan", "--watch"]) == 2


def test_watch_interval_limits_and_symlink_safety(repo):
    with pytest.raises(HarnessError, match="interval"):
        impact.watch_changes(repo, "HEAD", interval=100)
    (repo / "symlink.py").symlink_to(repo / ".gitignore")
    with pytest.raises(HarnessError, match="Symlink"):
        impact.plan_changes(repo)


def test_full_fallback_uses_discovery_so_new_test_directories_are_included():
    plan = impact.select_checks(["tests/new_component/test_new.py"])
    assert plan["mode"] == "full"
    argv = plan["checks"][0]["argv"]
    assert not any(arg.startswith("tests/") for arg in argv)


def test_explicit_full_preserves_comparison_files(repo):
    base = git(repo, "rev-parse", "HEAD")
    (repo / "new.py").write_text("committed change\n")
    commit(repo)
    plan = impact.plan_changes(repo, base, full=True)
    assert "new.py" in plan["changed_files"]
    assert plan["base_commit"] == base

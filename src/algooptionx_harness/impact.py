"""Conservative Git-based test selection, using the existing evidence runner."""

from __future__ import annotations

import json
import subprocess
import time
import uuid
from pathlib import Path

from algooptionx_harness.models import Check, Evidence, Task
from algooptionx_harness.runner import run_task, verify_evidence
from algooptionx_harness.workspace import (
    HarnessError,
    capture_task,
    digest,
    git,
    relative_path,
    snapshot,
    write_json,
)

SKIP = (
    "tests.research.test_prediction.test_levels_sharing_a_price_are_merged_not_dropped"
)
SUITES = ("architecture", "control_plane", "paper", "research", "market", "intelligence")


def resolve_commit(root: Path, ref: str) -> str:
    if not ref or ref.startswith("-") or "\x00" in ref:
        raise HarnessError("Supply a valid Git base ref or commit.")
    try:
        return git(
            root, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"
        ).strip()
    except subprocess.CalledProcessError as exc:
        raise HarnessError(
            "Git base is unavailable; fetch it or explicitly use --full."
        ) from exc


def changed_files(root: Path, base: str) -> tuple[list[str], str | None]:
    """Include both rename sides, staged/unstaged/deleted and non-ignored new files."""
    try:
        ancestor = git(root, "merge-base", base, "HEAD").strip()
    except subprocess.CalledProcessError:
        # A shallow/disconnected history cannot justify a narrowed selection.
        return [], "No merge base is available; full validation is required."
    files = set()
    for args in (
        ("diff", "--name-only", "--no-renames", "-z", ancestor, "HEAD", "--"),
        ("diff", "--name-only", "--no-renames", "-z", "HEAD", "--"),
        ("diff", "--cached", "--name-only", "--no-renames", "-z", "HEAD", "--"),
        ("diff", "--name-only", "--no-renames", "-z", "--"),
        ("ls-files", "--others", "--exclude-standard", "-z"),
    ):
        files.update(filter(None, git(root, *args).split("\0")))
    for name in files:
        relative_path(name)
    return sorted(files), None


def select_checks(
    paths: list[str], *, full: bool = False, fallback: str | None = None
) -> dict:
    """Select suites, never individual test names or deleted test files."""
    suites = {"architecture"}
    web = browser = research_build = False
    reasons = {}
    for name in paths:
        relative_path(name)
        if name.startswith(
            ("src/algooptionx_harness/", "tests/control_plane/", ".agents/")
        ):
            suites.add("control_plane")
            reason = "Development harness and role contracts"
        elif name.startswith("src/algooptionx/market/"):
            suites.update(("market", "intelligence", "paper", "research"))
            browser = True
            reason = "Market contracts and all current paper/research/shadow consumers"
        elif name.startswith("src/algooptionx/intelligence/"):
            suites.update(("intelligence", "research"))
            reason = "Decision contracts and research shadow consumer"
        elif name == "src/algooptionx/research/shadow.py":
            suites.update(("market", "intelligence", "research"))
            reason = "Shadow adapter and causal inputs"
        elif name.startswith("src/algooptionx/research/signals/"):
            suites.update(("research", "intelligence"))
            reason = "Research signals and shadow consumer"
        elif name.startswith("tests/market/"):
            suites.add("market")
            reason = "Causal market-data tests"
        elif name.startswith("tests/intelligence/"):
            suites.add("intelligence")
            reason = "Decision and shadow tests"
        elif name.startswith(
            ("src/algooptionx/research/", "tests/research/", "config/")
        ):
            suites.add("research")
            reason = "Broker research rules, storage and configuration"
        elif name.startswith(
            (
                "src/algooptionx/api/",
                "src/algooptionx/paper/",
                "tests/paper/",
            )
        ):
            suites.add("paper")
            browser = True
            reason = "Paper/API/market behavior and browser journeys"
        elif name.startswith("apps/web/"):
            web = browser = research_build = True
            reason = "Frontend contracts, both builds and browser journeys"
        elif name.startswith("tests/architecture/"):
            reason = "Repository and dependency boundaries"
        elif (
            name == "README.md"
            or name.endswith(".md")
            and name.startswith(("docs/", "tests/"))
        ):
            reason = "Documentation: configuration and architecture smoke checks"
        else:
            full = True
            reason = "Shared configuration or unmapped path: full validation"
        reasons[name] = reason
    if full or fallback:
        suites = set(SUITES)
        web = browser = research_build = True
    # Backend browser journeys need a freshly built workspace.
    build = web or browser
    targets = [] if full or fallback else [f"tests/{s}" for s in SUITES if s in suites]
    checks = [
        Check(
            id="python",
            kind="pytest",
            argv=[
                ".venv/bin/python",
                "-m",
                "pytest",
                *targets,
                "-q",
                "-rs",
                "--junitxml={run_dir}/pytest.xml",
            ],
            report="{run_dir}/pytest.xml",
            timeout_seconds=180,
            allowed_skips=[SKIP] if "research" in suites else [],
            critical_tests=[
                *(
                    [
                        "tests.control_plane.test_workflow.test_real_human_signatures_and_complete_release_chain"
                    ]
                    if "control_plane" in suites
                    else []
                ),
                *(
                    ["tests.paper.test_engine.test_kill_flattens_and_blocks_entries"]
                    if "paper" in suites
                    else []
                ),
            ],
        ),
        Check(
            id="config",
            kind="command",
            argv=[
                ".venv/bin/python",
                "-m",
                "algooptionx_harness.cli",
                "validate-config",
            ],
        ),
    ]
    if web:
        checks.append(
            Check(
                id="lint",
                kind="command",
                argv=["npm", "--prefix", "apps/web", "run", "lint"],
            )
        )
    if research_build:
        checks.append(
            Check(
                id="research-build",
                kind="command",
                argv=["npm", "--prefix", "apps/web", "run", "build:research"],
            )
        )
    if build:
        checks.append(
            Check(
                id="build",
                kind="command",
                argv=["npm", "--prefix", "apps/web", "run", "build"],
            )
        )
    if browser:
        checks.append(
            Check(
                id="browser",
                kind="playwright",
                argv=["npm", "--prefix", "apps/web", "run", "test:e2e"],
                report="{run_dir}/browser/playwright.json",
                timeout_seconds=180,
                critical_tests=[
                    "workspace.spec.ts::buy, mark, close and export a virtual trade"
                ],
            )
        )
    return {
        "mode": "full" if full or fallback else "affected",
        "fallback": fallback,
        "changed_files": sorted(paths),
        "reasons": reasons,
        "python_suites": [s for s in SUITES if s in suites],
        "needs_node": build,
        "needs_browser": browser,
        "visual_review_required": web,
        "coverage_limits": [
            "The legacy research frontend has build/lint coverage; its broker journeys require separate credential-free fixtures."
        ],
        "checks": [check.model_dump(mode="json") for check in checks],
    }


def plan_changes(root: Path, base: str = "HEAD", *, full: bool = False) -> dict:
    root = root.resolve()
    if Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve() != root:
        raise HarnessError("Use the Git repository root with --root.")
    before = snapshot(root)
    try:
        resolved = resolve_commit(root, base)
    except HarnessError:
        if not full:
            raise
        # An explicitly requested full run is safe even before a base has been fetched.
        resolved = resolve_commit(root, "HEAD")
    files, fallback = changed_files(root, resolved)
    plan = select_checks(files, full=full, fallback=fallback)
    if digest(snapshot(root)) != digest(before):
        raise HarnessError(
            "Source changed during test selection; retry against the current files."
        )
    plan.update(
        schema_version=1,
        base_commit=resolved,
        source_commit=before["commit"],
        source_digest=digest(before),
    )
    plan["status"] = "selected" if files or full or fallback else "no_changes"
    if plan["status"] == "no_changes":
        plan["checks"] = []
    return plan


def run_changes(root: Path, plan: dict) -> dict:
    """Each automatic run captures its own recoverable task and verifies its evidence."""
    if plan["status"] == "no_changes":
        return {**plan, "tests_run": False, "human_approval": False}
    baseline = snapshot(root)
    if digest(baseline) != plan["source_digest"]:
        raise HarnessError("Source changed after selection; select tests again.")
    run_id = uuid.uuid4().hex
    task = Task(
        id=f"IMPACT-{run_id.upper()}",
        title="Validate Git-selected affected AlgoOptionX components",
        implementer="automation:change-testing",
        requirement_ids=["HARNESS-03", "HARNESS-06"],
        source_commit=baseline["commit"],
        baseline_digest=digest(baseline),
        allowed_paths=plan["changed_files"] or ["src/"],
        protected_inputs=["docs/requirements/development-harness.md"],
        ui_changes=plan["needs_browser"],
        checks=[Check.model_validate(c) for c in plan["checks"]],
        acceptance=[
            "Selected checks pass with current source and untampered reports.",
            f"Selection digest: {digest(plan)}",
        ],
        rollback="Preserve source and prior evidence; rerun against a fresh source snapshot after failures.",
    )
    destination = root / ".harness/tasks" / task.id
    capture_task(root, task, baseline, destination)
    write_json(destination / "selection.json", plan)
    if digest(snapshot(root)) != plan["source_digest"]:
        raise HarnessError(
            "Source changed while capturing the test task; select tests again."
        )
    path = run_task(root, task, baseline, root / ".harness/runs")
    evidence = Evidence.model_validate_json(path.read_text())
    if evidence.status == "passed":
        verify_evidence(root, task, baseline, path)
    return {
        "status": evidence.status,
        "tests_run": True,
        "task": str(destination / "task.json"),
        "selection": str(destination / "selection.json"),
        "evidence": str(path),
        "mode": plan["mode"],
        "changed_files": plan["changed_files"],
        "checks": [r.check_id for r in evidence.results],
        "human_approval": False,
        "deployment_performed": False,
    }


def watch_changes(
    root: Path,
    base: str,
    *,
    full: bool = False,
    interval: float = 2,
    debounce: float = 1,
):
    """One runner at a time. Edits during tests invalidate evidence and trigger another run."""
    if not 0.1 <= interval <= 30 or not 0 <= debounce <= 30:
        raise HarnessError(
            "Watch interval must be 0.1–30 seconds; debounce must be 0–30 seconds."
        )
    # Freeze the base so a commit made while watching cannot hide new work.
    try:
        resolved = resolve_commit(root, base)
    except HarnessError:
        if not full:
            raise
        resolved = resolve_commit(root, "HEAD")
    pending = last_attempt = None
    stable_since = time.monotonic()
    print(json.dumps({"status": "watching", "base_commit": resolved}), flush=True)
    while True:
        current = digest(snapshot(root))
        if current != pending:
            pending, stable_since = current, time.monotonic()
        if current != last_attempt and time.monotonic() - stable_since >= debounce:
            last_attempt = current
            try:
                plan = plan_changes(root, resolved, full=full)
                result = run_changes(root, plan)
                print(json.dumps(result), flush=True)
            except (HarnessError, OSError, subprocess.CalledProcessError) as exc:
                print(json.dumps({"status": "blocked", "reason": str(exc)}), flush=True)
        time.sleep(interval)

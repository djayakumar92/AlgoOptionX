"""Run bounded validation commands; retain exit status, test outcomes and hashes."""

from __future__ import annotations

import json
import os
import platform
import re
import selectors
import signal
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from harness.models import Artifact, Check, Evidence, Result, TestOutcome
from harness.workspace import (
    HarnessError,
    contained,
    digest,
    file_digest,
    snapshot,
    validate_scope,
    write_json,
)

MAX_OUTPUT = 2 * 1024 * 1024
SECRET_PATTERN = re.compile(
    rb"(?i)((?:access[_-]?token|api[_-]?key|password|secret)\s*[=:]\s*)[^\s,;\x22\x27]+"
)


def parse_report(check: Check, path: Path) -> list[TestOutcome]:
    if not path.is_file() or path.stat().st_size > 20 * 1024 * 1024:
        raise HarnessError("Report must be a regular file smaller than 20 MiB.")
    outcomes = []
    if check.kind == "pytest":
        for case in ET.parse(path).iter("testcase"):
            identity = f"{case.get('classname', '')}.{case.get('name', '')}"
            failure = case.find("failure")
            if failure is None:
                failure = case.find("error")
            skipped = case.find("skipped")
            status = (
                "failed"
                if failure is not None
                else "skipped"
                if skipped is not None
                else "passed"
            )
            reason = failure if failure is not None else skipped
            outcomes.append(
                TestOutcome(
                    id=identity,
                    status=status,
                    reason=reason.get("message", "") if reason is not None else "",
                )
            )
    elif check.kind == "playwright":
        data = json.loads(path.read_text())
        if data.get("errors"):
            raise HarnessError("Browser runner reported global errors.")

        def visit(suites):
            for suite in suites:
                for spec in suite.get("specs", []):
                    for test in spec.get("tests", []):
                        results = test.get("results", [])
                        identity = f"{spec.get('file', '')}::{spec.get('title', '')}"
                        if test.get("projectName"):
                            identity += f"::{test['projectName']}"
                        statuses = [r.get("status") for r in results]
                        if (
                            results
                            and all(s == "passed" for s in statuses)
                            and test.get("expectedStatus", "passed") == "passed"
                            and test.get("status") not in ("flaky", "unexpected")
                        ):
                            status = "passed"
                        elif statuses and all(s == "skipped" for s in statuses):
                            status = "skipped"
                        else:
                            status = "failed"
                        outcomes.append(
                            TestOutcome(
                                id=identity,
                                status=status,
                                reason=str(test.get("status", "")),
                            )
                        )
                visit(suite.get("suites", []))

        visit(data.get("suites", []))
    return outcomes


def enforce_outcomes(check: Check, outcomes: list[TestOutcome]):
    ids = [o.id for o in outcomes]
    if len(ids) != len(set(ids)):
        raise HarnessError("Duplicate test identities in evidence.")
    if not outcomes or not any(o.status == "passed" for o in outcomes):
        raise HarnessError("Zero passing tests do not validate a workflow.")
    failed = [o.id for o in outcomes if o.status == "failed"]
    unexpected_skips = [
        o.id
        for o in outcomes
        if o.status == "skipped" and o.id not in check.allowed_skips
    ]
    passed_ids = {o.id for o in outcomes if o.status == "passed"}
    missing = set(check.critical_tests) - passed_ids
    if failed or unexpected_skips or missing:
        raise HarnessError(
            f"Test gate failed: failures={failed}, unexpected_skips={unexpected_skips}, missing_critical={sorted(missing)}"
        )


def clean_environment(root: Path, run_dir: Path) -> dict[str, str]:
    # Validation code receives no inherited model, broker or GitHub credentials.
    env = {
        name: os.environ[name]
        for name in (
            "PATH",
            "SYSTEMROOT",
            "LANG",
            "LC_ALL",
            "PLAYWRIGHT_CHROMIUM_EXECUTABLE",
        )
        if name in os.environ
    }
    home = run_dir / "home"
    home.mkdir(parents=True)
    env.update(
        {
            "HOME": str(home),
            "TMPDIR": "/tmp",
            "CI": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "npm_config_cache": str(run_dir / "npm-cache"),
            "UV_CACHE_DIR": str(root / ".harness/cache"),
            "ALGOOPTIONX_EVIDENCE_DIR": str(run_dir),
            "ALGOOPTIONX_DB": str(run_dir / "paper.db"),
        }
    )
    return env


def execute(
    argv: list[str], cwd: Path, env: dict, timeout: int
) -> tuple[int | None, bool, bytes, str]:
    started = time.monotonic()
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    chunks, size, timed_out, problem = [], 0, False, ""
    try:
        while selector.get_map():
            if time.monotonic() - started > timeout:
                timed_out, problem = True, "Command exceeded its time budget."
                break
            for key, _ in selector.select(timeout=0.1):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                size += len(chunk)
                chunks.append(chunk[: max(0, MAX_OUTPUT - sum(map(len, chunks)))])
                if size > MAX_OUTPUT:
                    problem = "Command exceeded its output budget."
                    break
            if problem:
                break
        if not problem:
            try:
                process.wait(timeout=max(0.01, timeout - (time.monotonic() - started)))
            except subprocess.TimeoutExpired:
                timed_out, problem = True, "Command exceeded its time budget."
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        selector.close()
        process.stdout.close()
    output = b"".join(chunks)
    if SECRET_PATTERN.search(output):
        output = SECRET_PATTERN.sub(rb"\1[REDACTED]", output)
        problem = "Potential secret in command output; redacted and validation failed."
    return process.returncode, timed_out, output, problem


def run_task(root: Path, task, baseline: dict, output_root: Path) -> Path:
    root = root.resolve()
    before = snapshot(root)
    changed = validate_scope(task, baseline, before)
    run_id = str(uuid.uuid4())
    run_dir = output_root.resolve() / run_id
    if not run_dir.is_relative_to(root / ".harness/runs"):
        raise HarnessError(
            "Run output must be inside the ignored .harness/runs directory."
        )
    run_dir.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc)
    results = []
    for check in task.checks:
        cwd = contained(root, check.cwd, allow_root=True)
        argv = [arg.replace("{run_dir}", str(run_dir)) for arg in check.argv]
        if not cwd.is_dir():
            raise HarnessError("Check working directory does not exist.")
        check_started = time.monotonic()
        code, timed_out, output, problem = None, False, b"", ""
        outcomes, artifacts = [], []
        try:
            code, timed_out, output, problem = execute(
                argv,
                cwd,
                clean_environment(root, run_dir / check.id),
                check.timeout_seconds,
            )
        except (OSError, ValueError) as exc:
            problem = f"Runner could not execute command: {type(exc).__name__}"
        log = run_dir / f"{check.id}.log"
        try:
            contained(run_dir, log.name)
            with log.open("xb") as stream:
                stream.write(output)
        except (OSError, HarnessError):
            problem = (
                "Validation interfered with its command log; refusing to overwrite it."
            )
            log = run_dir / f"{check.id}-runner-{uuid.uuid4()}.log"
            with log.open("xb") as stream:
                stream.write(output)
        artifacts.append(Artifact(path=log.name, sha256=file_digest(log)))
        if code != 0 or timed_out:
            problem = problem or f"Underlying command exited with {code}."
        if check.report:
            try:
                report_value = check.report.replace("{run_dir}", str(run_dir))
                report = Path(report_value)
                if not report.is_absolute():
                    report = root / report
                if not report.resolve().is_relative_to(run_dir):
                    raise HarnessError(
                        "Test report must belong to this unique run directory."
                    )
                report = contained(run_dir, str(report.relative_to(run_dir)))
                outcomes = parse_report(check, report)
                artifacts.append(
                    Artifact(
                        path=str(report.relative_to(run_dir)),
                        sha256=file_digest(report),
                    )
                )
                enforce_outcomes(check, outcomes)
            except (OSError, ValueError, ET.ParseError) as exc:
                problem = (
                    problem + " " if problem else ""
                ) + f"Invalid test evidence: {exc}"
        if digest(snapshot(root)) != digest(before):
            problem = (
                "Validation command modified source; preserve changes and investigate."
            )
        results.append(
            Result(
                check_id=check.id,
                argv=argv,
                cwd=check.cwd,
                exit_code=code,
                timed_out=timed_out,
                status="failed" if problem else "passed",
                detail=problem,
                duration_seconds=float(round(time.monotonic() - check_started, 3)),
                artifacts=artifacts,
                outcomes=outcomes,
            )
        )
        write_json(
            run_dir / "checkpoint.json",
            {
                "task_id": task.id,
                "completed_checks": [r.model_dump(mode="json") for r in results],
                "status": "running",
            },
        )
        if digest(snapshot(root)) != digest(before):
            break
    after = snapshot(root)
    evidence = Evidence(
        run_id=run_id,
        task_id=task.id,
        task_digest=digest(task),
        source_digest=digest(before),
        final_source_digest=digest(after),
        source_commit=before["commit"],
        started_at=started,
        finished_at=datetime.now(timezone.utc),
        changed_paths=changed,
        status="passed"
        if len(results) == len(task.checks)
        and all(r.status == "passed" for r in results)
        and digest(before) == digest(after)
        else "failed",
        results=results,
        runtime={"python": sys.version.split()[0], "platform": platform.platform()},
    )
    write_json(run_dir / "evidence.json", evidence)
    write_json(
        run_dir / "checkpoint.json",
        {"task_id": task.id, "status": evidence.status, "evidence": "evidence.json"},
    )
    return run_dir / "evidence.json"


def verify_evidence(root: Path, task, baseline: dict, path: Path) -> Evidence:
    path = path.absolute()
    if path.is_symlink():
        raise HarnessError("Evidence manifest cannot be a symlink.")
    evidence = Evidence.model_validate_json(path.read_text())
    current = snapshot(root)
    changed = validate_scope(task, baseline, current)
    if evidence.task_id != task.id or evidence.task_digest != digest(task):
        raise HarnessError("Evidence belongs to another task revision.")
    if (
        evidence.source_digest != digest(current)
        or evidence.final_source_digest != digest(current)
        or evidence.changed_paths != changed
        or evidence.source_commit != current["commit"]
    ):
        raise HarnessError("Source changed after validation; rerun the checks.")
    if (
        evidence.started_at.tzinfo is None
        or evidence.finished_at.tzinfo is None
        or evidence.finished_at < evidence.started_at
        or evidence.finished_at > datetime.now(timezone.utc)
    ):
        raise HarnessError("Evidence timestamps are invalid.")
    if evidence.status != "passed" or [r.check_id for r in evidence.results] != [
        c.id for c in task.checks
    ]:
        raise HarnessError("Required checks did not all complete successfully.")
    for check, result in zip(task.checks, evidence.results, strict=True):
        if result.status != "passed" or result.exit_code != 0 or result.timed_out:
            raise HarnessError("Failed check cannot be presented as passing.")
        if (
            result.argv
            != [a.replace("{run_dir}", str(path.parent.resolve())) for a in check.argv]
            or result.cwd != check.cwd
        ):
            raise HarnessError("Executed command differs from the reviewed task.")
        for artifact in result.artifacts:
            candidate = contained(path.parent, artifact.path)
            if file_digest(candidate) != artifact.sha256:
                raise HarnessError("Evidence artifact was modified.")
        if not any(a.path == f"{check.id}.log" for a in result.artifacts):
            raise HarnessError("Command log is missing.")
        if check.report:
            report = Path(check.report.replace("{run_dir}", str(path.parent.resolve())))
            if not report.is_absolute():
                report = root / report
            if not report.resolve().is_relative_to(path.parent.resolve()):
                raise HarnessError("Report escapes evidence directory.")
            report = contained(path.parent, str(report.relative_to(path.parent)))
            if not any(
                a.path == str(report.relative_to(path.parent)) for a in result.artifacts
            ):
                raise HarnessError("Report is not included in hashed artifacts.")
            parsed = parse_report(check, report)
            enforce_outcomes(check, parsed)
            if parsed != result.outcomes:
                raise HarnessError("Reported test outcomes were changed.")
    return evidence

"""Content-address the actual checkout, including pre-existing uncommitted work."""

from __future__ import annotations
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

from algooptionx_harness.models import Task


class HarnessError(ValueError):
    pass


def canonical(value) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative_path(value: str, allow_root=False) -> str:
    path = PurePosixPath(value)
    if allow_root and value == ".":
        return value
    if (
        not value
        or path.is_absolute()
        or "\\" in value
        or any(part in ("..", ".") for part in value.split("/"))
        or "\x00" in value
    ):
        raise HarnessError(f"Unsafe relative path: {value!r}")
    return value


def contained(root: Path, value: str, allow_root=False) -> Path:
    relative_path(value, allow_root)
    root = root.resolve()
    candidate = root / value
    for parent in (candidate, *candidate.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise HarnessError(f"Symlink is not allowed: {value}")
    if not candidate.resolve().is_relative_to(root):
        raise HarnessError("Path escapes its permitted root.")
    return candidate


def git(root: Path, *args) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=True
    )
    return result.stdout.decode()


def snapshot(root: Path) -> dict:
    root = root.resolve()
    names = git(
        root, "ls-files", "-z", "--cached", "--others", "--exclude-standard"
    ).split("\0")
    files = {}
    for name in sorted(set(filter(None, names))):
        path = contained(root, name)
        if not path.exists():
            files[name] = {"deleted": True}
        elif not path.is_file():
            raise HarnessError(f"Unsupported checkout entry: {name}")
        else:
            files[name] = {
                "sha256": file_digest(path),
                "executable": bool(path.stat().st_mode & 0o111),
            }
    return {"commit": git(root, "rev-parse", "HEAD").strip(), "files": files}


def changed_paths(before: dict, after: dict) -> list[str]:
    return sorted(
        name
        for name in set(before["files"]) | set(after["files"])
        if before["files"].get(name) != after["files"].get(name)
    )


def validate_scope(task: Task, baseline: dict, current: dict) -> list[str]:
    if (
        digest(baseline) != task.baseline_digest
        or baseline["commit"] != task.source_commit
    ):
        raise HarnessError(
            "Task baseline was modified or does not match its approved commit."
        )
    if current["commit"] != task.source_commit:
        raise HarnessError("HEAD changed; create and review a new task baseline.")
    for name in task.allowed_paths:
        relative_path(name.rstrip("/"))
    changed = changed_paths(baseline, current)
    for name in changed:
        if not any(
            name == prefix or prefix.endswith("/") and name.startswith(prefix)
            for prefix in task.allowed_paths
        ):
            raise HarnessError(f"Out-of-scope change: {name}")
    for name in task.protected_inputs:
        relative_path(name)
        if name not in baseline["files"] or name in changed:
            raise HarnessError(
                f"Approved specification input missing or changed: {name}"
            )
    return changed


def load_task(path: Path) -> tuple[Task, dict]:
    task = Task.model_validate_json(path.read_text())
    baseline_path = path.with_name("baseline.json")
    if baseline_path.is_symlink():
        raise HarnessError("Baseline cannot be a symlink.")
    baseline = json.loads(baseline_path.read_text())
    if digest(baseline) != task.baseline_digest:
        raise HarnessError("Task baseline digest mismatch.")
    return task, baseline


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=path.name + ".", suffix=".tmp", delete=False
    ) as stream:
        tmp = Path(stream.name)
        stream.write(canonical(value) + b"\n")
    os.replace(tmp, path)

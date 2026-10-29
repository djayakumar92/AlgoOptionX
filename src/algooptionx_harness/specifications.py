"""Read-only, hash-pinned requirement references. Not a new approval framework."""

from __future__ import annotations

import re
import hashlib
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import Field, field_validator, model_validator

from algooptionx_harness.models import Contract
from algooptionx_harness.workspace import (
    HarnessError,
    contained,
    digest,
    load_task,
    snapshot,
    validate_scope,
)


class RequirementReference(Contract):
    id: str = Field(pattern=r"^[A-Z][A-Z0-9-]{2,63}$")
    path: str
    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")

    @field_validator("path")
    @classmethod
    def specification_path(cls, value):
        if str(PurePosixPath(value)) != value:
            raise ValueError("Use one canonical relative specification path.")
        if not value.startswith(("docs/", "openspec/")) or not value.endswith(".md"):
            raise ValueError(
                "Specification references must be Markdown inside docs/ or openspec/."
            )
        return value


class SpecificationMap(Contract):
    schema_version: Literal[1] = 1
    change_id: str = Field(pattern=r"^[A-Z][A-Z0-9-]{2,63}$")
    source_format: Literal["native", "openspec-layout"] = "native"
    requirements: list[RequirementReference] = Field(min_length=1, max_length=100)

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int:
            raise ValueError("Use an integer schema version.")
        return value

    @model_validator(mode="after")
    def unique_requirements(self):
        names = [r.id for r in self.requirements]
        if len(set(names)) != len(names):
            raise ValueError("Requirement IDs must be unique.")
        return self


def check_specifications(
    root: Path, mapping: SpecificationMap, task_path: Path | None = None
) -> dict:
    root = root.resolve()
    before = snapshot(root)
    references = []
    documents = {}
    for ref in mapping.requirements:
        path = contained(root, ref.path)
        if path not in documents:
            if not path.is_file():
                raise HarnessError("Specification must be a regular Markdown file.")
            with path.open("rb") as stream:
                raw = stream.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise HarnessError("Specification exceeds1MiB.")
            documents[path] = (hashlib.sha256(raw).hexdigest(), raw.decode("utf-8"))
        document_digest, text = documents[path]
        if document_digest != ref.sha256:
            raise HarnessError(
                f"Specification changed: {ref.path}; prepare a new reviewed mapping/task revision."
            )
        if not re.search(
            r"(?<![A-Za-z0-9_-])" + re.escape(ref.id) + r"(?![A-Za-z0-9_-])", text
        ):
            raise HarnessError(
                f"Requirement {ref.id} is not present in its pinned specification."
            )
        references.append({"id": ref.id, "path": ref.path, "sha256": ref.sha256})
    task_binding = None
    if task_path is not None:
        target = task_path.absolute()
        if not target.is_relative_to(root / ".harness/tasks"):
            raise HarnessError("Bind only captured task files inside .harness/tasks.")
        contained(root, str(target.relative_to(root)))
        task, baseline = load_task(target)
        validate_scope(task, baseline, before)
        if set(task.requirement_ids) != {r.id for r in mapping.requirements}:
            raise HarnessError(
                "Mapping must cover exactly the captured task's requirement IDs."
            )
        if not {r.path for r in mapping.requirements} <= set(task.protected_inputs):
            raise HarnessError(
                "Every mapped specification must be a protected input of the captured task."
            )
        task_binding = {"task_id": task.id, "task_digest": digest(task)}
    if digest(snapshot(root)) != digest(before):
        raise HarnessError(
            "Source changed during specification checking; retry against a stable revision."
        )
    return {
        "status": "verified_references",
        "mapping_digest": digest(mapping),
        "source_digest": digest(before),
        "source_commit": before["commit"],
        "requirements": references,
        "task_binding": task_binding,
        "source_format": mapping.source_format,
        "external_tool_conformance": "not_verified",
        "human_approval": False,
        "deployment_performed": False,
    }

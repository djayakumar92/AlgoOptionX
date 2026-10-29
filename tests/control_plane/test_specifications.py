"""Pinned traceability is read-only and grants no approval or deployment authority."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from algooptionx_harness.cli import main
from algooptionx_harness.models import Check, Task
from algooptionx_harness.orchestration import validate_configuration
from algooptionx_harness.specifications import (
    RequirementReference,
    SpecificationMap,
    check_specifications,
)
from algooptionx_harness.workspace import HarnessError, capture_task, digest, snapshot

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = {
    "requirement-analysis",
    "requirement-validation",
    "architecture-review",
    "ui-design-validation",
    "react-development",
    "fastapi-development",
    "options-domain-analysis",
    "quant-backtesting",
    "market-data-validation",
    "risk-control-testing",
    "ml-leakage-prevention",
    "security-review",
    "playwright-testing",
    "evidence-verification",
    "release-readiness",
}


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".gitignore").write_text(".harness/\n")
    (root / "docs").mkdir()
    spec = root / "docs/spec.md"
    spec.write_text("# Requirements\n\nGOV-01 and HARNESS-03\n")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    return root


def mapping(root, ids=("GOV-01", "HARNESS-03"), **kwargs):
    sha = hashlib.sha256((root / "docs/spec.md").read_bytes()).hexdigest()
    return SpecificationMap(
        change_id="TRACE-001",
        requirements=[
            RequirementReference(id=id, path="docs/spec.md", sha256=sha) for id in ids
        ],
        **kwargs,
    )


def task(root, **kwargs):
    base = snapshot(root)
    data = dict(
        id="TRACE-001",
        title="Trace verified requirements without approval",
        implementer="agent:test",
        requirement_ids=["GOV-01", "HARNESS-03"],
        source_commit=base["commit"],
        baseline_digest=digest(base),
        allowed_paths=["docs/"],
        protected_inputs=["docs/spec.md"],
        checks=[
            Check(id="python", kind="pytest", argv=["pytest"], report="{run_dir}/x.xml")
        ],
        acceptance=["All reference identities and hashes are current."],
        rollback="Preserve evidence; restore reviewed specification revision.",
    )
    captured = Task(**(data | kwargs))
    p = root / ".harness/tasks/TRACE-001"
    capture_task(root, captured, base, p)
    return p / "task.json"


def test_native_mapping_roundtrip_and_binding_are_read_only(project):
    spec = mapping(project)
    p = task(project)
    before = snapshot(project)
    result = check_specifications(project, spec, p)
    assert (
        result["status"] == "verified_references"
        and result["task_binding"]["task_id"] == "TRACE-001"
    )
    assert not result["human_approval"] and not result["deployment_performed"]
    assert SpecificationMap.model_validate_json(spec.model_dump_json()) == spec
    assert snapshot(project) == before


def test_stale_specification_and_misassigned_id_fail(project):
    spec = mapping(project)
    (project / "docs/spec.md").write_text("GOV-01 HARNESS-03 changed\n")
    with pytest.raises(HarnessError, match="changed"):
        check_specifications(project, spec)
    with pytest.raises(HarnessError, match="not present"):
        check_specifications(project, mapping(project, ids=("MISSING-01",)))
    (project / "docs/spec.md").write_text("GOV-010 HARNESS-03\n")
    with pytest.raises(HarnessError, match="not present"):
        check_specifications(project, mapping(project))


def test_missing_requirement_or_unprotected_document_cannot_bind(project):
    p = task(project)
    with pytest.raises(HarnessError, match="exactly"):
        check_specifications(project, mapping(project, ids=("GOV-01",)), p)
    copy = project / "docs/duplicate.md"
    copy.write_text((project / "docs/spec.md").read_text())
    refs = [
        RequirementReference(id=r.id, path="docs/duplicate.md", sha256=r.sha256)
        for r in mapping(project).requirements
    ]
    with pytest.raises(HarnessError, match="protected"):
        check_specifications(
            project, SpecificationMap(change_id="TRACE-001", requirements=refs), p
        )


@pytest.mark.parametrize(
    "path",
    ["../outside.md", "docs/../../private.md", "/tmp/private.md", "docs/link.md"],
)
def test_unsafe_or_linked_source_paths_are_rejected(project, path, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("GOV-01")
    (project / "docs/link.md").symlink_to(outside)
    payload = dict(
        change_id="TRACE-001",
        requirements=[
            dict(
                id="GOV-01",
                path=path,
                sha256=hashlib.sha256(outside.read_bytes()).hexdigest(),
            )
        ],
    )
    with pytest.raises((HarnessError, ValidationError)):
        check_specifications(project, SpecificationMap.model_validate(payload))


def test_duplicate_ids_extra_authority_and_bool_version_are_invalid(project):
    data = mapping(project).model_dump()
    for change in (
        {"requirements": data["requirements"] * 2},
        {"human_approval": True},
        {"schema_version": True},
    ):
        with pytest.raises(ValidationError):
            SpecificationMap.model_validate(data | change)


def test_openspec_layout_is_reference_only_not_tool_conformance(project):
    spec = mapping(project, source_format="openspec-layout")
    result = check_specifications(project, spec)
    assert result["external_tool_conformance"] == "not_verified"
    assert result["task_binding"] is None and result["human_approval"] is False


def test_cli_works_and_does_not_echo_untrusted_payload(project, capsys):
    p = project / "mapping.json"
    p.write_text(mapping(project).model_dump_json())
    assert main(["--root", str(project), "validate-spec-map", str(p)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "verified_references"
    p.write_text('{"secret":"do-not-echo"}')
    assert main(["--root", str(project), "validate-spec-map", str(p)]) == 2
    assert "do-not-echo" not in capsys.readouterr().err


def test_all_requested_skills_are_routed_and_keep_role_authority():
    roles = [
        json.loads(p.read_text())
        for p in (ROOT / "src/algooptionx_harness/agents").glob("*.json")
    ]
    skills = {s for r in roles for s in r["skills"]}
    assert REQUIRED <= skills and len(skills) == 23 and len(roles) == 14
    assert all(r["human_approval_authority"] is False for r in roles)
    for name in skills:
        text = (ROOT / f".agents/skills/{name}/SKILL.md").read_text()
        for heading in [
            "Inputs",
            "Outputs",
            "Allowed actions",
            "Validation",
            "Failure conditions",
            "Evidence",
        ]:
            assert f"## {heading}\n" in text


def test_missing_skill_sections_fail_config_validation(tmp_path):
    root = tmp_path / "repo"
    shutil.copytree(
        ROOT / "src/algooptionx_harness/agents", root / "src/algooptionx_harness/agents"
    )
    shutil.copytree(ROOT / ".agents/skills", root / ".agents/skills")
    p = root / ".agents/skills/react-development/SKILL.md"
    p.write_text(p.read_text().replace("## Evidence", "## Removed evidence"))
    with pytest.raises(HarnessError, match="missing Evidence"):
        validate_configuration(root)


def test_requirement_lookup_uses_the_same_bytes_whose_hash_was_pinned(
    project, monkeypatch
):
    # Model an edit/ABA between independent byte and text reads: the pinned
    # document lacks GOV-01, while a later text view would contain it.
    spec = project / "docs/spec.md"
    spec.write_text("GOV-010 HARNESS-03\n")
    pinned = mapping(project)
    original = Path.read_text

    def changed_text(path, *args, **kwargs):
        if path == spec:
            return "GOV-01 HARNESS-03\n"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", changed_text)
    with pytest.raises(HarnessError, match="not present"):
        check_specifications(project, pinned)


def test_one_document_cannot_satisfy_conflicting_pinned_versions(project):
    refs = list(mapping(project).requirements)
    refs[1] = RequirementReference(
        id="HARNESS-03", path="docs/spec.md", sha256="a" * 64
    )
    with pytest.raises(HarnessError, match="changed"):
        check_specifications(
            project, SpecificationMap(change_id="TRACE-001", requirements=refs)
        )


def test_reference_and_mapping_byte_limits_are_enforced(project, capsys):
    spec = project / "docs/spec.md"
    spec.write_bytes(b"GOV-01 HARNESS-03\n" + b"x" * (1024 * 1024))
    with pytest.raises(HarnessError, match="exceeds"):
        check_specifications(project, mapping(project))
    path = project / "mapping.json"
    path.write_bytes(b" " * (1024 * 1024 + 1))
    assert main(["--root", str(project), "validate-spec-map", str(path)]) == 2
    assert json.loads(capsys.readouterr().err)["status"] == "blocked"


def test_reference_path_aliases_are_not_separate_spec_versions(project):
    ref = mapping(project).requirements[0].model_dump()
    with pytest.raises(ValidationError, match="canonical"):
        RequirementReference.model_validate(ref | {"path": "docs//spec.md"})

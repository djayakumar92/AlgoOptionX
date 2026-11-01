"""Read-only contract/policy checking, not execution or approval authority."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from algooptionx_harness.changes import ChangeSpec, GovernancePolicy, safe_path
from algooptionx_harness.models import Task
from algooptionx_harness.orchestration import load_role
from algooptionx_harness.specifications import SpecificationMap, check_specifications
from algooptionx_harness.workspace import HarnessError, contained, digest, snapshot

POLICY_PATH = "config/engineering-governance.json"
MAX_INPUT = 1024 * 1024
RISKS = ("R0", "R1", "R2", "R3")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise HarnessError("Duplicate JSON authority field.")
        result[key] = value
    return result


def _read(root: Path, name: str) -> bytes:
    try:
        safe_path(name)
        path = contained(root, name)
        if not path.is_file():
            raise HarnessError("Change inputs must be regular files.")
        with path.open("rb") as stream:
            raw = stream.read(MAX_INPUT + 1)
        if len(raw) > MAX_INPUT:
            raise HarnessError("Change input exceeds the size limit.")
        return raw
    except (OSError, ValueError):
        raise HarnessError("Change input unavailable, oversized or unsafe.") from None


def _json(raw: bytes):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, RecursionError):
        raise HarnessError("Invalid change JSON input.") from None


def _pinned(root: Path, reference) -> bytes:
    raw = _read(root, reference.path)
    if hashlib.sha256(raw).hexdigest() != reference.sha256:
        raise HarnessError("Pinned change input is stale.")
    return raw


def load_governance_policy(root: Path, expected_sha256: str) -> GovernancePolicy:
    """The caller's explicit pin identifies bytes; it does not prove adoption.

    There is one repository policy path. A candidate cannot silently substitute
    a second policy or replace the caller's previously reviewed pin.
    """
    if not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
        raise HarnessError("An exact governance policy SHA-256 pin is required.")
    raw = _read(root, POLICY_PATH)
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise HarnessError("Governance policy changed; review a new policy revision.")
    return GovernancePolicy.model_validate(_json(raw))


def _covers(parent: str, child: str) -> bool:
    return child == parent or parent.endswith("/") and child.startswith(parent)


def resolve_obligations(policy, requested_risk, scopes, declared_components, *, ui_changes=False, purpose="local-development"):
    """Conservative maximum across all overlapping rules, including subtrees.

    A scope needs a rule covering it completely. Descendant high-risk rules
    still contribute to broad scopes, so a directory cannot hide risky files.
    """
    level = RISKS.index(requested_risk)
    gates, components = set(), set()
    for scope in scopes:
        safe_path(scope, directory=True)
        if not any(_covers(rule.prefix, scope) for rule in policy.path_rules):
            raise HarnessError("Unknown source scope is blocked.")
        matches = [rule for rule in policy.path_rules if _covers(rule.prefix, scope) or _covers(scope, rule.prefix)]
        for rule in matches:
            level = max(level, RISKS.index(rule.minimum_risk))
            gates.update(rule.gates)
            components.add(rule.component)
    if set(declared_components) != components:
        raise HarnessError("Declared components conflict with resolved source scope.")
    if purpose != "local-development":
        level = 3
    risk = RISKS[level]
    profile = policy.profiles[risk]
    gates.update(profile.gates)
    stages = set(profile.approval_stages)
    if purpose in ("release", "deployment", "broker-execution"):
        stages.add("release")
    if ui_changes:
        gates.update(("TYPE-BUILD", "LINT", "BROWSER"))
        stages.add("ui")
    if not gates <= {item.id for item in policy.gates}:
        raise HarnessError("Mandatory gate is absent from the accepted catalog.")
    return {"effective_risk": risk, "required_gates": sorted(gates),
            "required_approval_stages": [s for s in ("plan", "architecture", "ui", "implementation", "qa", "release") if s in stages],
            "components": sorted(components), "independent_review_required": True}


def validate_change(root: Path, path: Path, expected_policy_sha256: str) -> dict:
    """Check definitions and references without capture, execution or transitions.

    Historical approval provenance and DAG/lifecycle execution are deliberately
    not certified here. Valid contract data is not an approved change.
    """
    root = root.resolve()
    before = snapshot(root)
    try:
        name = str(path.absolute().relative_to(root))
    except ValueError:
        raise HarnessError("Change definitions must be inside the checkout.") from None
    if not name.startswith("docs/changes/") or not name.endswith("/change.json"):
        raise HarnessError("Use the canonical change definition location.")
    raw = _read(root, name)
    change = ChangeSpec.model_validate(_json(raw))
    expected_name = f"docs/changes/{change.id}/r{change.revision:04d}/change.json"
    if name != expected_name:
        raise HarnessError("Change identity and revision location conflict.")
    policy = load_governance_policy(root, expected_policy_sha256)
    if (change.policy.id, change.policy.revision, change.policy.sha256) != (policy.id, policy.revision, expected_policy_sha256):
        raise HarnessError("Conflicting governance authority reference.")
    _pinned(root, change.proposal)
    _pinned(root, change.design)
    check_specifications(root, SpecificationMap(change_id=change.id, requirements=change.requirements))
    tasks, contract_inputs = [], {name, POLICY_PATH, change.proposal.path, change.design.path}
    contract_inputs.update(ref.path for ref in change.requirements)
    role_skills = {}
    for child in change.children:
        if not child.task_template.path.startswith(str(Path(name).parent) + "/tasks/"):
            raise HarnessError("Child template must belong to this change revision.")
        template = _json(_pinned(root, child.task_template))
        if not isinstance(template, dict) or {"source_commit", "baseline_digest"} & template.keys():
            raise HarnessError("Task template must not supply captured source authority.")
        task = Task.model_validate({**template, "source_commit": before["commit"], "baseline_digest": digest(before)})
        if task.id != child.id or set(task.requirement_ids) != set(child.requirement_ids):
            raise HarnessError("Child and native task identity/requirements conflict.")
        for scope in task.allowed_paths:
            safe_path(scope, directory=True)
            if not any(_covers(parent, scope) for parent in change.allowed_paths):
                raise HarnessError("Child scope exceeds its parent.")
        protected = contract_inputs | {child.task_template.path}
        if not protected <= set(task.protected_inputs):
            raise HarnessError("Native task must protect its change and policy inputs.")
        for protected_name in task.protected_inputs:
            safe_path(protected_name)
            if protected_name not in before["files"] or before["files"][protected_name].get("deleted"):
                raise HarnessError("A protected input is absent from the source snapshot.")
        skills = set(child.skills)
        for role in child.roles:
            contract = load_role(root, role)
            skills.update(contract["skills"])
            role_skills[f"role:{role}"] = digest(contract)
        for skill in sorted(skills):
            text = _read(root, f".agents/skills/{skill}/SKILL.md")
            if f"name: {skill}\n".encode() not in text:
                raise HarnessError("Required skill identity is invalid.")
            role_skills[f"skill:{skill}"] = hashlib.sha256(text).hexdigest()
        tasks.append(task)
    obligations = resolve_obligations(policy, change.requested_risk, change.allowed_paths, change.affected_components,
                                      ui_changes=any(task.ui_changes for task in tasks), purpose=change.purpose)
    if not set(obligations["required_approval_stages"]) <= set(change.approvals.stages):
        raise HarnessError("Mandatory human approval requirements are missing.")
    if digest(snapshot(root)) != digest(before):
        raise HarnessError("Source changed during contract checking.")
    return {"status": "verified_contracts", "change_id": change.id, "change_revision": change.revision,
            "change_digest": digest(change), "change_file_sha256": hashlib.sha256(raw).hexdigest(),
            "source_commit": before["commit"], "source_digest": digest(before),
            "policy_sha256": expected_policy_sha256, "policy_assurance": "caller-pinned-not-authenticated",
            "role_skill_digests": role_skills, **obligations,
            "approval_requirements_complete": True, "human_approval_verified": False,
            "execution_readiness": "not_implemented", "dependency_dag_verified": False,
            "lifecycle_transitions_verified": False, "external_controls": "not_verified",
            "authorization": "not_granted", "deployment_performed": False}

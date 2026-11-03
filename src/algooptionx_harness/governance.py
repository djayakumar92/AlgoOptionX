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


def _validate_change_v1(root: Path, path: Path, expected_policy_sha256: str) -> dict:
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


def v2_scope_graph(change, scopes):
    """Use the contract's exact serial order, ancestor closure and native scope rules."""
    from algooptionx_harness.changes import NativeImplementationV2, _v2_ancestors
    nodes = {c.id:c for c in change.children}
    order = [r.id for r in change.execution_order]
    if set(scopes) != set(order) or sum(len(p) for p in scopes.values()) > 1000:
        raise HarnessError('V2 scope inventory differs or exceeds its budget.')
    for name, paths in scopes.items():
        if len(paths)>200 or len(paths)!=len(set(paths)):
            raise HarnessError('V2 scopes must be unique and bounded.')
        if isinstance(nodes[name],NativeImplementationV2) != bool(paths):
            raise HarnessError('Only native implementation children may declare writes.')
        for path in paths:
            safe_path(path,directory=True)
    ancestors={name:_v2_ancestors(nodes,name) for name in order}
    writers=[name for name in order if scopes[name]]
    for i,left in enumerate(writers):
        for right in writers[i+1:]:
            if any(_covers(a,b) or _covers(b,a) for a in scopes[left] for b in scopes[right]) and left not in ancestors[right]:
                raise HarnessError('Overlapping writers require an explicit dependency.')
    return {'order':order,'ancestors':{name:sorted(ancestors[name]) for name in order}}


def _change_definition(root,path):
    """Secure version probe when supported; legacy fallback is platform-only."""
    from algooptionx_harness.changes import parse_change,ChangeSpecV2
    from algooptionx_harness.designs import _Reader,_name,_decode,DesignError
    root=root.resolve();name=_name(root,path);reader=_Reader(root,name)
    try:
        raw=reader.raw(name)
    except DesignError as error:
        if error.code!='UXD_PLATFORM':raise
        # Keep existing v1 platform semantics; this never enables v2 inspection.
        reader=None;raw=_read(root,name)
    change=parse_change(_decode(raw) if reader is not None else _json(raw))
    if isinstance(change,ChangeSpecV2) and reader is None:
        raise DesignError('UXD_PLATFORM')
    if reader is not None:reader.finish()
    return change,reader,name


def validate_change(root: Path, path: Path, expected_policy_sha256: str) -> dict:
    """Version-dispatched read-only contracts; v2 never enables native enforcement."""
    from algooptionx_harness.changes import ChangeSpecV2
    root=root.resolve();change,reader,name=_change_definition(root,path)
    if not isinstance(change,ChangeSpecV2):
        return _validate_change_v1(root,root/name,expected_policy_sha256)
    return _validate_change_v2(root,name,change,expected_policy_sha256,reader)


def _validate_change_v2(root,name,change,expected_policy_sha256,reader):
    from algooptionx_harness.changes import parse_change, NativeImplementationV2
    from algooptionx_harness.designs import (
        _bounded_snapshot, _decode, DesignReference, DesignSpec, _spec_artifacts,
    )
    from algooptionx_harness.models import AgentRole
    _reject_legacy_v2_history(root,change)
    before=_bounded_snapshot(root)
    if name!=f'docs/changes/{change.id}/r{change.revision:04d}/change.json':
        raise HarnessError('V2 change location differs from its identity.')
    policy=reader.model(DesignReference(path=POLICY_PATH,sha256=expected_policy_sha256),GovernancePolicy)
    if (change.policy.id,change.policy.revision,change.policy.sha256)!=(policy.id,policy.revision,expected_policy_sha256):
        raise HarnessError('V2 policy identity differs from the reviewed pin.')
    for ref in (change.proposal,change.design,*change.requirements):
        raw=reader.pin(DesignReference(path=ref.path,sha256=ref.sha256))
        if hasattr(ref,'id'):
            try:text=raw.decode('utf-8')
            except UnicodeError:raise HarnessError('Requirement must be UTF-8.') from None
            if not re.search(r'(?<![A-Z0-9-])'+re.escape(ref.id)+r'(?![A-Z0-9-])',text):
                raise HarnessError('V2 requirement identifier is absent.')
    spec=None
    if change.design_link:
        link=change.design_link
        spec=reader.model(DesignReference(path=link.reference.path,sha256=link.reference.sha256),DesignSpec)
        if (spec.id,spec.revision,digest(spec),spec.parent_change_id,spec.parent_change_revision)!=(link.id,link.revision,link.record_digest,change.id,change.revision):
            raise HarnessError('Frozen design identity differs.')
        if {r.id:(r.path,r.sha256) for r in spec.requirements}!={r.id:(r.path,r.sha256) for r in change.requirements}:
            raise HarnessError('Frozen design requirement references differ.')
        _spec_artifacts(reader,spec)
        obligations=change.design_obligations
        if obligations.case_ids!=[case.id for case in spec.validation_cases] or not set(obligations.required_areas)<={area for case in spec.validation_cases for area in case.checks}:
            raise HarnessError('Frozen design validation obligations differ.')
    # Bounded, strictly decreasing supersession, including legacy predecessors.
    prior_ref=change.supersedes;prior_revision=change.revision;depth=0
    while prior_ref:
        depth+=1
        if depth>4:raise HarnessError('Supersession depth exceeds four.')
        prior=parse_change(_decode(reader.pin(DesignReference(path=prior_ref.path,sha256=prior_ref.sha256),json_file=True)))
        if prior.id!=change.id or prior.revision>=prior_revision or prior_ref.path!=f'docs/changes/{prior.id}/r{prior.revision:04d}/change.json':
            raise HarnessError('Supersession must identify an older canonical revision.')
        prior_revision=prior.revision;prior_ref=getattr(prior,'supersedes',None)
    # Superseded history is not a protected input of a new implementation task.
    protected={name,POLICY_PATH,change.proposal.path,change.design.path,*(r.path for r in change.requirements)}
    if spec:
        protected.update([change.design_link.reference.path,spec.fixture.reference.path,*(r.path for r in spec.token_references),*(a.reference.path for a in spec.artifacts)])
    selected={r.id for r in change.selected_children}
    tasks={};role_skills={};scopes={}
    for child in change.children:
        for role in child.roles:
            role_name=f'src/algooptionx_harness/agents/{role}.json'
            raw=reader.raw(role_name,native=True)
            contract=AgentRole.model_validate_json(raw)
            if contract.id!=role:raise HarnessError('Role identity differs.')
            role_skills[f'role:{role}']=digest(contract)
            for skill in set(child.skills)|set(contract.skills):
                raw_skill=reader.raw(f'.agents/skills/{skill}/SKILL.md',native=True)
                if f'name: {skill}\n'.encode() not in raw_skill:raise HarnessError('Skill identity differs.')
                role_skills[f'skill:{skill}']=hashlib.sha256(raw_skill).hexdigest()
        if not isinstance(child,NativeImplementationV2):
            if child.id in selected:scopes[child.id]=[]
            continue
        if not child.task_template.path.startswith(str(Path(name).parent)+'/tasks/'):
            raise HarnessError('Native template belongs to another revision.')
        template=_decode(reader.pin(DesignReference(path=child.task_template.path,sha256=child.task_template.sha256),json_file=True))
        if not isinstance(template,dict) or {'source_commit','baseline_digest'}&template.keys():
            raise HarnessError('Native template cannot supply captured authority.')
        task=Task.model_validate({**template,'source_commit':before['commit'],'baseline_digest':digest(before)})
        if task.id!=child.id or set(task.requirement_ids)!=set(child.requirement_ids):
            raise HarnessError('Native child/template identity differs.')
        for scope in task.allowed_paths:
            safe_path(scope,directory=True)
            if not any(_covers(parent,scope) for parent in change.allowed_paths):raise HarnessError('Native scope exceeds parent.')
        if not protected|{child.task_template.path} <= set(task.protected_inputs):
            raise HarnessError('Native task omits immutable change/design inputs.')
        for path in task.protected_inputs:
            safe_path(path)
            if path not in before['files'] or before['files'][path].get('deleted'):
                raise HarnessError('Native protected input is missing.')
        tasks[child.id]=task
        if child.id in selected:scopes[child.id]=task.allowed_paths
    graph=v2_scope_graph(change,scopes)
    ui_changes=any(t.ui_changes for name,t in tasks.items() if name in selected)
    resolved=resolve_obligations(policy,change.requested_risk,change.allowed_paths,change.affected_components,ui_changes=ui_changes,purpose=change.purpose)
    design_required=ui_changes or 'WEB' in resolved['components'] or spec is not None
    if design_required and spec is None:raise HarnessError('UI applicability requires a frozen design.')
    if design_required:
        resolved=resolve_obligations(policy,change.requested_risk,change.allowed_paths,change.affected_components,ui_changes=True,purpose=change.purpose)
    if not set(resolved['required_approval_stages'])<=set(change.approvals.stages):
        raise HarnessError('V2 approval declarations omit mandatory stages.')
    reader.finish()
    _reject_legacy_v2_history(root,change)
    if _bounded_snapshot(root)!=before:raise HarnessError('Source changed during v2 validation.')
    return {'status':'verified_contracts','change_schema_version':2,'change_id':change.id,'change_revision':change.revision,'change_digest':digest(change),'change_file_sha256':reader.files[name][0],'source_commit':before['commit'],'source_digest':digest(before),'policy_sha256':expected_policy_sha256,'policy_assurance':'caller-pinned-not-authenticated','role_skill_digests':role_skills,**resolved,'design_required':design_required,'design_id':spec.id if spec else None,'design_revision':spec.revision if spec else None,'dependency_graph':graph,'dependency_dag_verified':True,'human_approval_verified':False,'execution_verified':False,'execution_readiness':'v2-requires-uiux-phase1c','transition_permitted':False,'authorization':'not_granted','deployment_performed':False}


def _reject_legacy_v2_history(root,change):
    """A version namespace cannot hide an already used legacy parent revision."""
    base=f'.harness/changes/{change.id}/r{change.revision:04d}'
    for suffix in ('events','closure'):
        path=contained(root,base+'/'+suffix)
        if path.exists() and (not path.is_dir() or next(path.iterdir(),None) is not None):
            raise HarnessError('Legacy operational records exist; create a new parent revision.')


def _check_v2_protected(change,task,baseline,reader,candidate=None):
    """Bind captured immutable inputs to actual frozen bytes, not mutual claims."""
    from algooptionx_harness.designs import _bounded_snapshot,DesignSpec,DesignReference
    source=_bounded_snapshot(reader.root)
    required={f'docs/changes/{change.id}/r{change.revision:04d}/change.json',POLICY_PATH,change.proposal.path,change.design.path,*(r.path for r in change.requirements)}
    if change.design_link:
        link=change.design_link
        spec=reader.model(DesignReference(path=link.reference.path,sha256=link.reference.sha256),DesignSpec)
        required.update([link.reference.path,spec.fixture.reference.path,*(r.path for r in spec.token_references),*(a.reference.path for a in spec.artifacts)])
    native=next((c for c in change.children if c.id==task.id and hasattr(c,'task_template')),None)
    if native:required.add(native.task_template.path)
    if not required<=set(task.protected_inputs) or len(task.protected_inputs)>4096 or len(task.protected_inputs)!=len(set(task.protected_inputs)):
        raise HarnessError('Captured task omits frozen parent/design inputs.')
    if baseline.commit!=task.source_commit or digest(baseline)!=task.baseline_digest:
        raise HarnessError('Captured baseline differs from native task.')
    for name in task.protected_inputs:
        safe_path(name)
        entry=baseline.files.get(name)
        metadata=entry.model_dump(mode='json') if entry else None
        if metadata is None or metadata.get('deleted') or source['files'].get(name)!=metadata:
            raise HarnessError('Captured protected input differs from actual frozen source.')
        if candidate is not None and candidate.files.get(name)!=entry:
            raise HarnessError('Candidate modified a captured protected input.')


def execution_context(root,path,policy_sha256):
    """V2 execution prerequisites; structural change validation remains read-only."""
    from algooptionx_harness.changes import ChangeSpecV2
    from algooptionx_harness.ui_validation import load_plan
    obligations=validate_change(root,path,policy_sha256)
    change,reader,name=_change_definition(root,path)
    if not isinstance(change,ChangeSpecV2):raise HarnessError('V2 execution context required.')
    plan=spec=None;protected=set()
    if obligations['design_required']:
        plan,spec,protected=load_plan(root,change)
    writers=[i for i,r in enumerate(change.execution_order) if any(c.id==r.id and isinstance(c,__import__('algooptionx_harness.changes',fromlist=['NativeImplementationV2']).NativeImplementationV2) for c in change.children)]
    if writers:
        for i,r in enumerate(change.execution_order):
            c=next(c for c in change.children if c.id==r.id)
            if c.kind=='test-evidence' and i<max(writers):raise HarnessError('Candidate tests must follow all source writers.')
    if reader:reader.finish()
    return change,obligations,plan,protected


def execution_checks(scopes,obligations,plan):
    from algooptionx_harness.impact import select_governed_checks
    return select_governed_checks(scopes,obligations,plan)

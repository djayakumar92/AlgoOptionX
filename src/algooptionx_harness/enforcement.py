"""Native change bindings and local closure checks, never a second executor.

Local hashes/chat records do not authenticate human origin or protected execution.
Historical verification is explicitly separated from fresh aggregate verification.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

from typing import Literal
from pydantic import Field

from algooptionx_harness import chat
from algooptionx_harness.approvals import load_policy, verify_gate
from algooptionx_harness.changes import (
    AcceptanceRecord, ArchiveRecord, CapturedBinding, ChangeSpec, IntentBinding,
    KnowledgeRecord, RecordBase, Revision, Identity, SourceIdentity, StoredReference,
    Versioned,
)
from algooptionx_harness.governance import _json, _pinned, _read, validate_change
from algooptionx_harness.impact import select_checks
from algooptionx_harness.lifecycle import dependency_graph
from algooptionx_harness.models import Approval, ChatDecision, ChatRequest, Evidence, Handoff, Task
from algooptionx_harness.orchestration import (
    accept_handoff, accept_historical_handoff, dispatch,
)
from algooptionx_harness.runner import verify_evidence, verify_historical_evidence
from algooptionx_harness.workspace import (
    HarnessError, canonical, capture_task, contained, digest, file_digest, snapshot, validate_scope,
    write_json,
)

# Gate opinions reuse native role handoffs; no writable "passed" gate flags.
REVIEW_ROLES = {
    'REFERENCES': 'requirements-validator', 'ARCHITECTURE': 'architect',
    'SECURITY': 'security-engineer', 'FINANCIAL': 'risk-engineer',
    'CAUSAL-DATA': 'quant-researcher', 'GOVERNANCE': 'release-governor',
    'ROLLBACK': 'test-engineer',
}
AUTOMATIC = {'PYTHON', 'CONFIG', 'EVIDENCE', 'INDEPENDENT-REVIEW', 'TYPE-BUILD', 'LINT', 'BROWSER'}


class ChatPair(Versioned):
    request: StoredReference
    decision: StoredReference


class ApprovalSet(Versioned):
    chat: list[ChatPair] = Field(default_factory=list, max_length=6)
    signed: list[StoredReference] = Field(default_factory=list, max_length=100)


class NativeRun(Versioned):
    task: StoredReference
    baseline: StoredReference
    candidate: StoredReference
    evidence: StoredReference
    review: StoredReference
    approvals: ApprovalSet
    gate_reviews: dict[str, StoredReference] = Field(default_factory=dict, max_length=100)


class ChildRun(RecordBase):
    child_id: Identity
    child_revision: Revision
    intent: StoredReference
    captured: StoredReference
    native: NativeRun


class ChangeBundle(RecordBase):
    children: list[ChildRun] = Field(min_length=1, max_length=100)
    aggregate: NativeRun
    rollback_reference: StoredReference


class DependencyProof(RecordBase):
    children: list[ChildRun] = Field(min_length=1, max_length=100)


class Inputs:
    """Bounded reads, exact pins, repeat-read and source-race detection."""
    def __init__(self, root):
        self.root = root.resolve()
        self.source = snapshot(self.root)
        self.pins = {}
        self.artifacts = {}

    def raw(self, ref):
        raw = _pinned(self.root, ref)
        if ref.path in self.pins and self.pins[ref.path] != raw:
            raise HarnessError('Pinned input changed during verification.')
        self.pins[ref.path] = raw
        if sum(map(len, self.pins.values())) > 32 * 1024 * 1024:
            raise HarnessError('Change evidence input budget exceeded (32 MiB).')
        return raw

    def model(self, ref, cls):
        raw = self.raw(ref)
        _json(raw)  # Duplicate keys rejected before strict JSON datetime parsing.
        return cls.model_validate_json(raw)

    def value(self, ref):
        return _json(self.raw(ref))

    def artifact(self, name, sha256):
        path = contained(self.root, name)
        if not path.is_file() or path.stat().st_size > 20 * 1024 * 1024 or file_digest(path) != sha256:
            raise HarnessError('Native artifact changed during verification.')
        if name in self.artifacts and self.artifacts[name] != sha256:
            raise HarnessError('Conflicting native artifact pin.')
        self.artifacts[name] = sha256
        if len(self.artifacts) > 2000:
            raise HarnessError('Native artifact count budget exceeded.')

    def finish(self):
        for name, sha256 in self.artifacts.items():
            path = contained(self.root, name)
            if not path.is_file() or path.stat().st_size > 20 * 1024 * 1024 or file_digest(path) != sha256:
                raise HarnessError('Native artifact changed during verification.')
        if any(_read(self.root, name) != raw for name, raw in self.pins.items()):
            raise HarnessError('Evidence inputs changed during verification.')
        if snapshot(self.root) != self.source:
            raise HarnessError('Source changed during enforcement verification.')


def _reference(root, path):
    name = str(path.absolute().relative_to(root.resolve()))
    raw = _read(root, name)
    return StoredReference(path=name, sha256=hashlib.sha256(raw).hexdigest())


def _context(inputs, path, policy_sha256):
    root = inputs.root
    path = path if path.is_absolute() else root / path
    obligations = validate_change(root, path, policy_sha256)
    raw = _read(root, str(path.relative_to(root)))
    change = ChangeSpec.model_validate(_json(raw))
    if digest(inputs.source) != obligations['source_digest'] or digest(change) != obligations['change_digest']:
        raise HarnessError('Change context changed during verification.')
    scopes = {c.id: _json(_pinned(root, c.task_template))['allowed_paths'] for c in change.children}
    graph = dependency_graph(change, scopes)
    return change, obligations, graph


def _identity(record, change, obligations, source=None):
    if (record.change_id, record.change_revision, record.change_digest, record.policy_digest) != (
        change.id, change.revision, digest(change), obligations['policy_sha256'],
    ) or source is not None and record.source != source:
        raise HarnessError('Stale change, policy, revision or source binding.')


def _checks(task, obligations):
    selection = select_checks(task.allowed_paths, full=obligations['effective_risk'] in {'R2', 'R3'})
    expected = selection['checks']
    # Exact native selector contracts prevent test omission, injected commands,
    # skip broadening, weakened critical tests and arbitrary adapters in this slice.
    if [c.model_dump() for c in task.checks] != expected:
        raise HarnessError('Task checks differ from mandatory native impact selection.')
    gates = set(obligations['required_gates'])
    if not gates <= AUTOMATIC | set(REVIEW_ROLES):
        raise HarnessError('Unknown required gate has no native enforcement mapping.')
    checks = {c.id for c in task.checks}
    for gate, required in {'PYTHON': {'python'}, 'CONFIG': {'config'}, 'TYPE-BUILD': {'build', 'research-build'}, 'LINT': {'lint'}, 'BROWSER': {'browser'}}.items():
        if gate in gates and not required <= checks:
            raise HarnessError('Required gate lacks mandatory native checks.')


def _task(inputs, native):
    task = inputs.model(native.task, Task)
    baseline = inputs.value(native.baseline)
    candidate = inputs.value(native.candidate)
    if Path(native.task.path).parent != Path(native.baseline.path).parent or Path(native.baseline.path).name != 'baseline.json' or Path(native.task.path).name != 'task.json':
        raise HarnessError('Native task and baseline locations conflict.')
    for ref in (native.task, native.baseline, native.candidate, native.evidence, native.review):
        if not ref.path.startswith('.harness/'):
            raise HarnessError('Operational native bindings must be under .harness/.')
    validate_scope(task, baseline, candidate)
    return task, baseline, candidate


def _approvals(inputs, change, task, native, candidate, evidence, review, *, final, trust_policy):
    if 'ui' in change.approvals.stages and not task.ui_changes:
        raise HarnessError('Declared UI approval is incompatible with a non-UI native task.')
    stage = 'release' if 'release' in change.approvals.stages and final else 'qa' if final else 'implementation'
    binding = digest({'validation': digest(evidence), 'independent_review': native.review.sha256}) if final else None
    if change.approvals.mode == 'signed-external':
        if native.approvals.chat or trust_policy is None:
            raise HarnessError('Signed approvals require independently supplied external TrustPolicy.')
        receipts = [inputs.model(ref, Approval) for ref in native.approvals.signed]
        result = verify_gate(task, stage, receipts, load_policy(trust_policy, inputs.root), digest(candidate), binding,
                             evidence.finished_at if final else None)
        return result
    if change.purpose != 'local-development' or native.approvals.signed:
        raise HarnessError('Chat cannot authorize privileged or mixed approval modes.')
    needed = ['plan', 'architecture', *(['ui'] if task.ui_changes else []), 'implementation', *(['qa'] if final else [])]
    if final and 'release' in change.approvals.stages:
        needed.append('release')
    pairs = [(inputs.model(pair.request, ChatRequest), inputs.model(pair.decision, ChatDecision)) for pair in native.approvals.chat]
    if [request.stage for request, _ in pairs] != needed:
        raise HarnessError('Missing, duplicated or unordered native chat approval stages.')
    last = None
    for request, decision in pairs:
        if decision.recorded_at > datetime.now(timezone.utc) + timedelta(seconds=30):
            raise HarnessError('Approval decision is future-dated.')
        if last and request.requested_at < last:
            raise HarnessError('Approval stages are not chronologically ordered.')
        if request.stage in {'qa', 'release'}:
            if request.evidence_path != str((inputs.root / native.evidence.path).absolute()) or request.review_path != str((inputs.root / native.review.path).absolute()):
                raise HarnessError('QA chat request evidence locations differ.')
            if request.requested_at < evidence.finished_at:
                raise HarnessError('QA approval predates final evidence.')
        result = chat.verify_record(task, request, decision, digest(candidate), binding if request.stage in {'qa', 'release'} else None)
        if result['status'] != 'recorded':
            raise HarnessError('Human rejected a mandatory stage.')
        last = decision.recorded_at
    return {'status': 'recorded', 'verification': 'operator-recorded-chat',
            'human_origin_cryptographically_verified': False, 'grants_deployment': False}


def _verify_run(inputs, change, obligations, native, *, current, trust_policy=None):
    task, baseline, candidate = _task(inputs, native)
    _checks(task, obligations)
    path = inputs.root / native.evidence.path
    parsed_evidence = inputs.model(native.evidence, Evidence)
    parsed_review = inputs.model(native.review, Handoff)
    for result in parsed_evidence.results:
        for artifact in result.artifacts:
            inputs.artifact(str(Path(native.evidence.path).parent / artifact.path), artifact.sha256)
    for artifact in parsed_review.artifacts:
        inputs.artifact(artifact.path, artifact.sha256)
    evidence = verify_evidence(inputs.root, task, baseline, path) if current else verify_historical_evidence(inputs.root, task, baseline, path, candidate)
    review_path = inputs.root / native.review.path
    review = accept_handoff(inputs.root, task, baseline, review_path, 'independent-validator') if current else accept_historical_handoff(inputs.root, task, baseline, review_path, 'independent-validator', candidate)
    for result in evidence.results:
        for artifact in result.artifacts:
            inputs.artifact(str(Path(native.evidence.path).parent / artifact.path), artifact.sha256)
    for artifact in review.artifacts:
        inputs.artifact(artifact.path, artifact.sha256)
    # Pin before native verifier reads and recheck everything at completion.
    if inputs.raw(native.evidence) != path.read_bytes() or inputs.raw(native.review) != review_path.read_bytes():
        raise HarnessError('Native evidence changed during verification.')
    if current and candidate != inputs.source:
        raise HarnessError('Aggregate candidate must be the current exact source.')
    if not any(a.path == native.evidence.path and a.sha256 == native.evidence.sha256 for a in review.artifacts):
        raise HarnessError('Independent review does not reference this exact native evidence.')
    if review.status != 'completed' or not {'python', 'platform'} <= set(evidence.runtime):
        raise HarnessError('Missing completed independent review or environment identity.')
    # Native consistency is local integrity. A role string does not attest runtime independence.
    needed_reviews = set(obligations['required_gates']) & set(REVIEW_ROLES)
    if set(native.gate_reviews) != needed_reviews:
        raise HarnessError('Missing or unexpected elevated gate review.')
    for gate, ref in native.gate_reviews.items():
        parsed_gate = inputs.model(ref, Handoff)
        for artifact in parsed_gate.artifacts:
            inputs.artifact(artifact.path, artifact.sha256)
        handoff = accept_historical_handoff(inputs.root, task, baseline, inputs.root/ref.path, REVIEW_ROLES[gate], candidate)
        for artifact in handoff.artifacts:
            inputs.artifact(artifact.path, artifact.sha256)
        if not any(a.path == native.evidence.path and a.sha256 == native.evidence.sha256 for a in handoff.artifacts):
            raise HarnessError('Gate review does not reference this exact native evidence.')
        if handoff.status != 'completed' or handoff.actor == task.implementer or any(f.severity in {'high', 'critical'} for f in handoff.findings):
            raise HarnessError('Required gate review is incomplete or self-authored.')
    approval = _approvals(inputs, change, task, native, candidate, evidence, review, final=True, trust_policy=trust_policy)
    return task, baseline, candidate, evidence, approval


def _verified_child(inputs, change, obligations, child, plan, trust_policy=None):
    _identity(child, change, obligations)
    if child.child_revision != plan.revision:
        raise HarnessError('Stale child revision.')
    intent = inputs.model(child.intent, IntentBinding)
    captured = inputs.model(child.captured, CapturedBinding)
    task, baseline, candidate, evidence, _ = _verify_run(inputs, change, obligations, child.native, current=False, trust_policy=trust_policy)
    baseline_source = SourceIdentity(commit=baseline['commit'], source_digest=digest(baseline))
    _identity(intent, change, obligations, baseline_source)
    _identity(captured, change, obligations, baseline_source)
    _identity(child, change, obligations, SourceIdentity(commit=candidate['commit'], source_digest=digest(candidate)))
    template = _json(_pinned(inputs.root, plan.task_template))
    expected_task = Task.model_validate({**template, 'source_commit': baseline['commit'], 'baseline_digest': digest(baseline)})
    if task != expected_task or (intent.child_id, intent.child_revision, intent.template_digest, intent.purpose, intent.role_skill_digests) != (
        plan.id, plan.revision, plan.task_template.sha256, change.purpose, obligations['role_skill_digests'],
    ) or captured.intent_digest != digest(intent) or captured.native_task_digest != digest(task) or captured.baseline_digest != digest(baseline):
        raise HarnessError('Intent, capture or native task template binding differs.')
    return baseline, candidate


def _verify_bundle_v1_entry(root: Path, change_path: Path, policy_sha256: str, bundle_path: Path,
                  trust_policy: Path | None = None) -> dict:
    return _verify_bundle(Inputs(root), change_path, policy_sha256, bundle_path, trust_policy)


def _verify_bundle(inputs, change_path, policy_sha256, bundle_path, trust_policy=None):
    change, obligations, graph = _context(inputs, change_path, policy_sha256)
    bundle_path = bundle_path if bundle_path.is_absolute() else inputs.root / bundle_path
    bundle_ref = _reference(inputs.root, bundle_path)
    bundle = inputs.model(bundle_ref, ChangeBundle)
    current_identity = SourceIdentity(commit=inputs.source['commit'], source_digest=digest(inputs.source))
    _identity(bundle, change, obligations, current_identity)
    expected = {child.id: child for child in change.children}
    if len(bundle.children) != len(expected) or {child.child_id for child in bundle.children} != set(expected):
        raise HarnessError('Every mandatory child must appear exactly once.')
    aggregate_task, aggregate_baseline, aggregate_candidate = _task(inputs, bundle.aggregate)
    if (aggregate_task.id != f'{change.id}-AGGREGATE' or aggregate_task.allowed_paths != change.allowed_paths
        or set(aggregate_task.requirement_ids) != {ref.id for ref in change.requirements}):
        raise HarnessError('Aggregate task does not exactly cover the parent change.')
    previous = aggregate_baseline
    completed = set()
    for child in bundle.children:
        plan = expected[child.child_id]
        _identity(child, change, obligations)
        if child.child_revision != plan.revision or not set(plan.depends_on) <= completed:
            raise HarnessError('Stale child revision or dependency bypass.')
        baseline, candidate = _verified_child(inputs, change, obligations, child, plan, trust_policy)
        if baseline != previous:
            raise HarnessError('Child snapshot chain is discontinuous; recapture sequentially.')
        previous = candidate
        completed.add(plan.id)
    if previous != aggregate_candidate:
        raise HarnessError('Aggregate source does not match completed child snapshot chain.')
    # Aggregate must protect every specification/role/skill input protected by children.
    protected = {name for child in bundle.children for name in inputs.model(child.native.task, Task).protected_inputs}
    if not protected <= set(aggregate_task.protected_inputs):
        raise HarnessError('Aggregate task omits protected child inputs.')
    _, _, _, evidence, approval = _verify_run(inputs, change, obligations, bundle.aggregate, current=True, trust_policy=trust_policy)
    inputs.raw(bundle.rollback_reference)
    inputs.finish()
    return {'status': 'verified_local_acceptance', 'change_id': change.id, 'change_revision': change.revision,
            'change_digest': digest(change), 'policy_digest': policy_sha256,
            'source': current_identity.model_dump(), 'bundle_digest': digest(bundle),
            'bundle_sha256': bundle_ref.sha256, 'aggregate_task_digest': digest(aggregate_task),
            'aggregate_evidence_digest': digest(evidence), 'children': sorted(completed),
            'dependency_graph': graph, 'required_gates': obligations['required_gates'],
            'approval': approval, 'historical_child_evidence': 'local-consistency-only',
            'independent_review_provenance': 'declared-separate-context-not-externally-attested',
            'protected_execution_provenance': 'NOT VERIFIED', 'external_controls': 'NOT VERIFIED',
            'grants_deployment': False}


def _capture_child_v1(root: Path, change_path: Path, policy_sha256: str, child_id: str) -> dict:
    """Capture only: never execution/approval. Dependencies are checked at closure.

    Native dispatch/worker signing gates remain authoritative for execution.
    """
    inputs = Inputs(root)
    change, obligations, graph = _context(inputs, change_path, policy_sha256)
    plan = next((c for c in change.children if c.id == child_id), None)
    if plan is None:
        raise HarnessError('Unknown child task.')
    template = _json(_pinned(inputs.root, plan.task_template))
    task = Task.model_validate({**template, 'source_commit': inputs.source['commit'], 'baseline_digest': digest(inputs.source)})
    _checks(task, obligations)
    source = SourceIdentity(commit=inputs.source['commit'], source_digest=digest(inputs.source))
    base = {'change_id':change.id, 'change_revision':change.revision,'change_digest':digest(change),'policy_digest':policy_sha256,'source':source}
    intent = IntentBinding(**base, kind='intent', child_id=plan.id, child_revision=plan.revision,
                           template_digest=plan.task_template.sha256, role_skill_digests=obligations['role_skill_digests'], purpose=change.purpose)
    captured = CapturedBinding(**base, kind='captured', intent_digest=digest(intent), native_task_digest=digest(task), baseline_digest=digest(inputs.source))
    destination = contained(inputs.root, f'.harness/tasks/{change.id}-r{change.revision:04d}-{plan.id}-r{plan.revision:04d}')
    inputs.finish()
    capture_task(inputs.root, task, inputs.source, destination)
    write_json(destination/'intent.json', intent)
    write_json(destination/'captured.json', captured)
    return {'status':'captured-not-authorized','task':str(destination/'task.json'), 'intent_digest':digest(intent),
            'captured_digest':digest(captured),'dependencies':graph['ancestors'][plan.id],
            'execution':'use existing native approval/dispatch/worker gates; capture does not satisfy dependencies'}


def _dispatch_child_v1(root: Path, change_path: Path, policy_sha256: str, child_id: str, role: str, dependencies: Path | None = None, trust_policy: Path | None = None) -> dict:
    """Prepare the existing native role bundle, never launch an adapter."""
    inputs=Inputs(root);change,obligations,graph=_context(inputs,change_path,policy_sha256)
    plan=next((c for c in change.children if c.id==child_id),None)
    if plan is None or role not in plan.roles:
        raise HarnessError('Role is not assigned to this child.')
    directory=contained(inputs.root,f'.harness/tasks/{change.id}-r{change.revision:04d}-{plan.id}-r{plan.revision:04d}')
    task=inputs.model(_reference(inputs.root,directory/'task.json'),Task)
    baseline=inputs.value(_reference(inputs.root,directory/'baseline.json'))
    expected=Task.model_validate({**_json(_pinned(inputs.root,plan.task_template)),'source_commit':baseline['commit'],'baseline_digest':digest(baseline)})
    if task!=expected:
        raise HarnessError('Captured dispatch task differs from pinned template.')
    _checks(task,obligations)
    source=SourceIdentity(commit=baseline['commit'],source_digest=digest(baseline))
    intent=inputs.model(_reference(inputs.root,directory/'intent.json'),IntentBinding)
    captured=inputs.model(_reference(inputs.root,directory/'captured.json'),CapturedBinding)
    _identity(intent,change,obligations,source);_identity(captured,change,obligations,source)
    if (intent.child_id,intent.child_revision,intent.template_digest,intent.role_skill_digests,intent.purpose)!=(plan.id,plan.revision,plan.task_template.sha256,obligations['role_skill_digests'],change.purpose) or captured.intent_digest!=digest(intent) or captured.native_task_digest!=digest(task) or captured.baseline_digest!=digest(baseline):
        raise HarnessError('Dispatch intent/capture binding differs.')
    if plan.depends_on:
        if dependencies is None:
            raise HarnessError('Dependent dispatch requires verified predecessor evidence.')
        proof_path = dependencies if dependencies.is_absolute() else inputs.root/dependencies
        proof = inputs.model(_reference(inputs.root,proof_path),DependencyProof)
        _identity(proof,change,obligations,SourceIdentity(commit=inputs.source['commit'],source_digest=digest(inputs.source)))
        completed=set();previous=None
        plans={child.id:child for child in change.children}
        for child in proof.children:
            if child.child_id not in plans or child.child_id==plan.id or child.child_id in completed:
                raise HarnessError('Invalid predecessor proof inventory.')
            child_plan=plans[child.child_id]
            if not set(child_plan.depends_on)<=completed:
                raise HarnessError('Predecessor dependency bypass.')
            predecessor_baseline,candidate=_verified_child(inputs,change,obligations,child,child_plan,trust_policy)
            if previous is not None and predecessor_baseline!=previous:
                raise HarnessError('Predecessor snapshot chain is discontinuous.')
            previous=candidate;completed.add(child.child_id)
        if not set(graph['ancestors'][plan.id])<=completed or previous!=inputs.source:
            raise HarnessError('Missing or stale predecessor source evidence.')

    result=dispatch(inputs.root,task,baseline,role)
    selected={skill['id'] for skill in result['skills']}
    for skill in plan.skills:
        if skill not in selected:
            raw=_read(inputs.root,f'.agents/skills/{skill}/SKILL.md')
            sha=hashlib.sha256(raw).hexdigest()
            if sha!=obligations['role_skill_digests'][f'skill:{skill}']:
                raise HarnessError('Selected child skill changed during dispatch.')
            result['skills'].append({'id':skill,'sha256':sha,'instructions':raw.decode('utf-8')})
    inputs.finish()
    result['change_binding']={'id':change.id,'revision':change.revision,'digest':digest(change),'authorization':'not_granted'}
    return result


def _close_change_v1(root: Path, change_path: Path, policy_sha256: str, bundle_path: Path,
                 *, archive: bool = False, trust_policy: Path | None = None) -> dict:
    """Verified local acceptance/archive records in a new ignored directory only.

    No human decision is created here. All decisions must already be native
    verified inputs. Never writes accepted source or claims deployment approval.
    """
    before = snapshot(root)
    inputs = Inputs(root)
    result = _verify_bundle(inputs, change_path, policy_sha256, bundle_path, trust_policy)
    bundle_path = bundle_path if bundle_path.is_absolute() else inputs.root/bundle_path
    bundle = inputs.model(_reference(inputs.root,bundle_path), ChangeBundle)
    if digest(bundle) != result['bundle_digest'] or snapshot(root) != before:
        raise HarnessError('Verified bundle changed before closure.')
    base = {key:result[key] for key in ('change_id','change_revision','change_digest','policy_digest','source')}
    directory=contained(inputs.root,f".harness/changes/{result['change_id']}/r{result['change_revision']:04d}/closure/{result['bundle_digest']}")
    acceptance=AcceptanceRecord(**base,kind='acceptance',aggregate_task_digest=result['aggregate_task_digest'],
        aggregate_evidence=bundle.aggregate.evidence,review=bundle.aggregate.review,
        human_decision=bundle.aggregate.approvals.chat[-1].decision if bundle.aggregate.approvals.chat else next(ref for ref in bundle.aggregate.approvals.signed if inputs.model(ref,Approval).stage==result['approval']['stage']),
        approval_mode='operator-recorded-chat' if bundle.aggregate.approvals.chat else 'signed-external',grants_deployment=False)
    # Acceptance and archive are distinct checkpoints; never archive before acceptance.
    inputs.finish()
    if archive:
        acceptance_ref = _reference(inputs.root,directory/'acceptance.json')
        existing = inputs.model(acceptance_ref, AcceptanceRecord)
        if existing != acceptance:
            raise HarnessError('Archive acceptance differs from the verified bundle.')
        if (directory/'archive.json').exists() or (directory/'knowledge.json').exists():
            raise HarnessError('Archive already exists; never overwrite closure history.')
    else:
        directory.mkdir(parents=True,exist_ok=False)
        _exclusive_json(directory/'acceptance.json',acceptance)
    if archive:
        inputs.finish()
        record=ArchiveRecord(**base,kind='archive',acceptance=acceptance_ref,
            child_evidence=[child.native.evidence for child in bundle.children],rollback_reference=bundle.rollback_reference,
            artifacts=[_reference(inputs.root,bundle_path),bundle.aggregate.evidence,bundle.aggregate.review])
        _exclusive_json(directory/'archive.json',record)
        knowledge=KnowledgeRecord(**base,kind='knowledge',finding='Local native evidence and recorded human decisions passed change closure verification.',
            classification='PARTIALLY VERIFIED',owner='operator:change-closure',evidence=[acceptance_ref],
            freshness_conditions=['Exact accepted source, task, policy and evidence bindings remain unchanged.'],
            invalidation_conditions=['Any source, policy, task, review or approval change requires fresh verification.'])
        _exclusive_json(directory/'knowledge.json',knowledge)
    inputs.finish()
    if snapshot(root)!=before:
        raise HarnessError('Source changed during closure; preserve incomplete output for investigation.')
    return {**result,'closure_path':str(directory),'archived':archive,'source_unchanged':True}


def _exclusive_json(path, value):
    # O_EXCL: an existing or concurrently created record is never replaced.
    with path.open('xb') as stream:
        stream.write(canonical(value) + b'\n')


# Additive v2 runtime records; native public schemas/signature payloads unchanged.
from algooptionx_harness.changes import VersionedV2, Sha256, ChangeSpecV2, NativeImplementationV2


class GovernedCaptureV2(VersionedV2):
    kind: Literal['governed-capture']
    change: StoredReference
    change_digest: Sha256
    policy_digest: Sha256
    child_id: Identity
    child_revision: Revision
    task_digest: Sha256
    baseline_digest: Sha256
    ui_plan: StoredReference | None = None


def _capture_dir(change,child):
    return f'.harness/tasks/{change.id}-r{change.revision:04d}-{child.id}-r{child.revision:04d}-v2'


def _v2_context(root,path,policy_sha256):
    from algooptionx_harness.governance import execution_context
    return execution_context(root.resolve(),path,policy_sha256)


def _v2_task(root,change,obligations,plan,protected,child,source):
    from algooptionx_harness.governance import execution_checks
    from algooptionx_harness.ui_validation import pin as ui_pin, UIReference
    from algooptionx_harness.designs import _Reader, _decode
    template=_decode(ui_pin(_Reader(root,''),UIReference(path=child.task_template.path,sha256=child.task_template.sha256)))
    task=Task.model_validate({**template,'source_commit':source['commit'],'baseline_digest':digest(source)})
    if task.id!=child.id or set(task.requirement_ids)!=set(child.requirement_ids) or not protected<=set(task.protected_inputs):
        raise HarnessError('Native task omits frozen UI execution inputs.')
    if [c.model_dump(mode='json') for c in task.checks]!=execution_checks(task.allowed_paths,obligations,plan):
        raise HarnessError('Native task checks differ from governed mandatory selection.')
    if plan and not task.ui_changes:raise HarnessError('Governed UI task cannot suppress UI approval.')
    return task


def _capture_v2(root,path,policy_sha256,child_id):
    from algooptionx_harness.ui_validation import plan_name
    from algooptionx_harness.designs import _bounded_snapshot
    root=root.resolve();source=_bounded_snapshot(root)
    change,obligations,plan,protected=_v2_context(root,path,policy_sha256)
    aggregate=child_id==f'{change.id}-AGGREGATE'
    child=next((c for c in change.children if c.id==child_id and c.id in {r.id for r in change.selected_children}),None)
    if aggregate:
        from types import SimpleNamespace
        child=SimpleNamespace(id=child_id,revision=change.revision)
        task=aggregate_task(root,change,obligations,plan,protected,source)
    else:
        if not isinstance(child,NativeImplementationV2):raise HarnessError('Non-native children do not receive fabricated native tasks.')
        task=_v2_task(root,change,obligations,plan,protected,child,source)
    name=path.relative_to(root).as_posix() if path.is_absolute() else path.as_posix()
    context=GovernedCaptureV2(schema_version=2,kind='governed-capture',change=_v2_reference(root,name),change_digest=digest(change),policy_digest=policy_sha256,child_id=child.id,child_revision=child.revision,task_digest=digest(task),baseline_digest=digest(source),ui_plan=_v2_reference(root,plan_name(change)) if plan else None)
    if _bounded_snapshot(root)!=source:raise HarnessError('Source changed during governed capture.')
    destination=root/f'.harness/tasks/{change.id}-AGGREGATE-v2' if aggregate else root/_capture_dir(change,child)
    capture_task(root,task,source,destination)
    _exclusive_json(destination/'governed.json',context)
    return {'status':'captured-not-authorized','task':str(destination/'task.json'),'context':str(destination/'governed.json'),'task_digest':digest(task),'baseline_digest':digest(source),'authorization':'not_granted','deployment_performed':False}


def capture_child(root: Path,change_path: Path,policy_sha256: str,child_id: str)->dict:
    from algooptionx_harness.governance import _change_definition
    change,_,_=_change_definition(root.resolve(),change_path)
    if isinstance(change,ChangeSpecV2):return _capture_v2(root,change_path,policy_sha256,child_id)
    return _capture_child_v1(root,change_path,policy_sha256,child_id)


class InputsV2:
    """Reuse secure design reads for v2 operational inputs; preserve v1 IO."""
    def __init__(self,root):
        from algooptionx_harness.designs import _Reader,_bounded_snapshot
        self.root=root.resolve();self.source=_bounded_snapshot(self.root);self.reader=_Reader(self.root,'')
    def raw(self,ref):
        from algooptionx_harness.ui_validation import pin,UIReference
        return pin(self.reader,UIReference(path=ref.path,sha256=ref.sha256))
    def model(self,ref,cls):
        from algooptionx_harness.designs import _decode
        raw=self.raw(ref);_decode(raw);return cls.model_validate_json(raw)
    def value(self,ref):
        from algooptionx_harness.designs import _decode
        return _decode(self.raw(ref))
    def artifact(self,name,sha):
        self.raw(StoredReference(path=name,sha256=sha))
    def finish(self):
        from algooptionx_harness.designs import _bounded_snapshot
        self.reader.finish()
        if _bounded_snapshot(self.root)!=self.source:raise HarnessError('Source changed during governed verification.')


def _v2_reference(root,name):
    from algooptionx_harness.designs import _Reader
    raw=_Reader(root,'').raw(name,ui=True)
    return StoredReference(path=name,sha256=hashlib.sha256(raw).hexdigest())


class ExecutionRequestV2(VersionedV2):
    kind: Literal['execution-request']
    capture: StoredReference
    approvals: ApprovalSet
    predecessors: list[StoredReference] = Field(default_factory=list,max_length=100)


def _captured_v2(inputs,change,obligations,plan,protected,child):
    from algooptionx_harness.designs import _Baseline
    from algooptionx_harness.governance import _check_v2_protected
    base=_capture_dir(change,child)
    task=inputs.model(_v2_reference(inputs.root,base+'/task.json'),Task)
    baseline=inputs.model(_v2_reference(inputs.root,base+'/baseline.json'),_Baseline)
    capture=inputs.model(_v2_reference(inputs.root,base+'/governed.json'),GovernedCaptureV2)
    expected=_v2_task(inputs.root,change,obligations,plan,protected,child,baseline.model_dump(mode='json'))
    if task!=expected or (capture.child_id,capture.child_revision,capture.task_digest,capture.baseline_digest,capture.change_digest,capture.policy_digest)!=(child.id,child.revision,digest(task),digest(baseline),digest(change),change.policy.sha256):
        raise HarnessError('Governed capture is stale.')
    actual=inputs.model(capture.change,ChangeSpecV2)
    if actual!=change:raise HarnessError('Governed capture parent differs.')
    if plan:
        from algooptionx_harness.ui_validation import UIExecutionPlan,plan_name
        if capture.ui_plan is None or capture.ui_plan.path!=plan_name(change) or inputs.model(capture.ui_plan,UIExecutionPlan)!=plan:
            raise HarnessError('Governed capture UI execution plan differs.')
    elif capture.ui_plan is not None:raise HarnessError('Unexpected UI execution context.')
    _check_v2_protected(change,task,baseline,inputs.reader)
    return task,baseline.model_dump(mode='json'),capture


def _approvals_v2(inputs,change,task,approvals,plan,*,stage,source,evidence=None,review=None,review_ref=None,trust_policy=None,before_execution=None):
    """Existing native receipts/queue only; no writable authorization shortcuts."""
    from algooptionx_harness.ui_validation import review_summary
    final=stage in {'qa','release'}
    binding=digest({'validation':digest(evidence),'independent_review':review_ref.sha256}) if final else None
    if change.approvals.mode=='signed-external':
        if approvals.chat or trust_policy is None:raise HarnessError('External signed mode needs an external TrustPolicy.')
        receipts=[inputs.model(ref,Approval) for ref in approvals.signed]
        result=verify_gate(task,stage,receipts,load_policy(trust_policy,inputs.root),digest(source),binding,evidence.finished_at if final else None)
        if before_execution and any(r.stage in {'plan','architecture','ui','implementation'} and r.issued_at>before_execution for r in receipts):
            raise HarnessError('Implementation approval postdates execution.')
        return result
    if change.purpose!='local-development' or approvals.signed:raise HarnessError('Privileged or mixed approval mode is blocked.')
    needed=['plan','architecture',*(['ui'] if task.ui_changes else []),'implementation']
    if final:needed.append('qa')
    if stage=='release':needed.append('release')
    pairs=[(inputs.model(p.request,ChatRequest),inputs.model(p.decision,ChatDecision)) for p in approvals.chat]
    if [r.stage for r,d in pairs]!=needed:raise HarnessError('Missing/duplicated/out-of-order approval stages.')
    last=None
    for request,decision in pairs:
        if last and request.requested_at<last or decision.recorded_at>datetime.now(timezone.utc)+timedelta(seconds=30):raise HarnessError('Approval chronology differs.')
        if request.stage=='ui' and (plan is None or request.summary!=review_summary(task,plan,inputs.root)):
            raise HarnessError('UI approval does not present the exact frozen review packet.')
        if request.stage in {'qa','release'} and (request.requested_at<evidence.finished_at or request.evidence_path!=str((inputs.root/inputs.current_evidence.path).absolute()) or request.review_path!=str((inputs.root/review_ref.path).absolute())):
            raise HarnessError('Final decision does not bind the fresh evidence and review.')
        if before_execution and request.stage not in {'qa','release'} and decision.recorded_at>before_execution:raise HarnessError('Implementation approval postdates execution.')
        checked=chat.verify_record(task,request,decision,digest(source),binding if request.stage in {'qa','release'} else None)
        if checked['status']!='recorded':raise HarnessError('Human rejected a required stage.')
        last=decision.recorded_at
    return {'status':'recorded','verification':'operator-recorded-chat','human_origin_cryptographically_verified':False,'stage':stage,'grants_deployment':False}


def authorize_v2(root,path,policy_sha256,child_id,request_path,*,trust_policy=None,require_current=True):
    inputs=InputsV2(root);change,obligations,plan,protected=_v2_context(inputs.root,path,policy_sha256)
    child=next((c for c in change.children if c.id==child_id and c.id in {r.id for r in change.selected_children}),None)
    if not isinstance(child,NativeImplementationV2):raise HarnessError('Only selected native source writers are dispatchable.')
    task,baseline,capture=_captured_v2(inputs,change,obligations,plan,protected,child)
    request=inputs.model(_v2_reference(inputs.root,request_path.relative_to(inputs.root).as_posix() if request_path.is_absolute() else request_path.as_posix()),ExecutionRequestV2)
    if inputs.model(request.capture,GovernedCaptureV2)!=capture:raise HarnessError('Authorization belongs to another capture.')
    if require_current and inputs.source!=baseline:raise HarnessError('Writing dispatch requires the exact captured baseline.')
    checked=_approvals_v2(inputs,change,task,request.approvals,plan,stage='implementation',source=baseline,trust_policy=trust_policy)
    # Sequential predecessor verification is completed by the v2 bundle verifier.
    if plan:
        from algooptionx_harness.ui_validation import verify_measurement
        _,spec,_=__import__('algooptionx_harness.ui_validation',fromlist=['load_plan']).load_plan(inputs.root,change)
        verify_measurement(inputs.root,plan,spec)
    if child.depends_on:
        _verify_predecessors_v2(inputs,change,obligations,plan,request.predecessors,child,trust_policy)
    elif request.predecessors:raise HarnessError('Unexpected predecessor assertions.')
    inputs.finish()
    return {'status':checked['status'],'stage':'implementation','task_id':task.id,'task_digest':digest(task),'baseline_digest':digest(baseline),'source_digest':digest(inputs.source),'governed_request':str(request_path),'governed_change':str(path),'governed_policy_sha256':policy_sha256,'governed_trust_policy':str(trust_policy) if trust_policy else None,'verification':checked,'grants_deployment':False}


def dispatch_child(root: Path,change_path: Path,policy_sha256: str,child_id: str,role: str,dependencies: Path | None=None,trust_policy: Path | None=None)->dict:
    from algooptionx_harness.governance import _change_definition
    change,_,_=_change_definition(root.resolve(),change_path)
    if not isinstance(change,ChangeSpecV2):return _dispatch_child_v1(root,change_path,policy_sha256,child_id,role,dependencies,trust_policy)
    if dependencies is None:raise HarnessError('V2 dispatch needs an actual execution request, approvals and predecessor proof.')
    auth=authorize_v2(root,change_path,policy_sha256,child_id,dependencies,trust_policy=trust_policy)
    child=next(c for c in change.children if c.id==child_id)
    if role not in child.roles:raise HarnessError('Role is not assigned to this child.')
    from algooptionx_harness.workspace import load_task
    task,baseline=load_task(root/_capture_dir(change,child)/'task.json')
    bundle=dispatch(root,task,baseline,role)
    bundle['governed_authorization']=auth
    return bundle


class ChildExecutionV2(VersionedV2):
    kind: Literal['child-execution']
    completion: StoredReference
    capture: StoredReference | None = None
    approvals: ApprovalSet | None = None
    ui_evidence: StoredReference | None = None
    handoff: StoredReference | None = None


class BundleV2(VersionedV2):
    kind: Literal['change-bundle']
    change_id: Identity
    change_revision: Revision
    change_digest: Sha256
    policy_digest: Sha256
    source: SourceIdentity
    children: list[ChildExecutionV2] = Field(min_length=1,max_length=100)
    aggregate: NativeRun
    ui_evidence: StoredReference | None = None
    rollback_reference: StoredReference


def aggregate_task(root,change,obligations,plan,protected,baseline):
    from algooptionx_harness.governance import execution_checks
    inputs={f'docs/changes/{change.id}/r{change.revision:04d}/change.json','config/engineering-governance.json',change.proposal.path,change.design.path,*(r.path for r in change.requirements),*protected}
    for child in change.children:
        if isinstance(child,NativeImplementationV2) and child.id in {r.id for r in change.selected_children}:
            template=_json(_pinned(root,child.task_template));inputs.update(template['protected_inputs']);inputs.add(child.task_template.path)
    return Task(schema_version=1,id=f'{change.id}-AGGREGATE',title=f'Fresh aggregate validation for {change.id}/r{change.revision}',implementer='agent:aggregate-validator',requirement_ids=[r.id for r in change.requirements],source_commit=baseline['commit'],baseline_digest=digest(baseline),allowed_paths=change.allowed_paths,protected_inputs=sorted(inputs),ui_changes=plan is not None,checks=execution_checks(change.allowed_paths,obligations,plan),acceptance=[a.predicate for a in change.acceptance],rollback=change.rollback.instructions)


def _native_v2(inputs,change,obligations,plan,native,*,current,trust_policy=None,final=False,ui_ref=None):
    task=inputs.model(native.task,Task);baseline=inputs.value(native.baseline);candidate=inputs.value(native.candidate)
    validate_scope(task,baseline,candidate)
    from algooptionx_harness.governance import execution_checks,_check_v2_protected
    from algooptionx_harness.designs import _Baseline
    if [c.model_dump(mode='json') for c in task.checks]!=execution_checks(task.allowed_paths,obligations,plan):raise HarnessError('Native governed checks or critical inventory weakened.')
    _check_v2_protected(change,task,_Baseline.model_validate(baseline),inputs.reader,_Baseline.model_validate(candidate))
    parsed=inputs.model(native.evidence,Evidence)
    for result in parsed.results:
        for artifact in result.artifacts:inputs.artifact(str(Path(native.evidence.path).parent/artifact.path),artifact.sha256)
    evidence=verify_evidence(inputs.root,task,baseline,inputs.root/native.evidence.path) if current else verify_historical_evidence(inputs.root,task,baseline,inputs.root/native.evidence.path,candidate)
    if current and candidate!=inputs.source:raise HarnessError('Aggregate is not the exact current source.')
    pre=native.approvals
    if final:
        pre=ApprovalSet(chat=[p for p in native.approvals.chat if inputs.model(p.request,ChatRequest).stage not in {'qa','release'}],signed=[ref for ref in native.approvals.signed if inputs.model(ref,Approval).stage not in {'qa','release'}])
    _approvals_v2(inputs,change,task,pre,plan,stage='implementation',source=baseline,trust_policy=trust_policy,before_execution=evidence.started_at)
    if plan:
        _verify_ui_v2(inputs,change,plan,task,evidence,native.evidence,ui_ref)
    if final:
        review=inputs.model(native.review,Handoff)
        for artifact in review.artifacts:inputs.artifact(artifact.path,artifact.sha256)
        accepted=accept_handoff(inputs.root,task,baseline,inputs.root/native.review.path,'independent-validator') if current else accept_historical_handoff(inputs.root,task,baseline,inputs.root/native.review.path,'independent-validator',candidate)
        required=[native.evidence,*([ui_ref] if ui_ref else [])]
        if accepted.status!='completed' or any(not any(a.path==ref.path and a.sha256==ref.sha256 for a in accepted.artifacts) for ref in required):raise HarnessError('Independent review does not bind complete native/UI evidence.')
        gates=set(obligations['required_gates'])&set(REVIEW_ROLES)
        if set(native.gate_reviews)!=gates:raise HarnessError('Required elevated gate review missing or unexpected.')
        for gate,ref in native.gate_reviews.items():
            handoff=inputs.model(ref,Handoff)
            for a in handoff.artifacts:inputs.artifact(a.path,a.sha256)
            handoff=accept_historical_handoff(inputs.root,task,baseline,inputs.root/ref.path,REVIEW_ROLES[gate],candidate)
            if handoff.status!='completed' or handoff.actor==task.implementer or not any(a.path==native.evidence.path and a.sha256==native.evidence.sha256 for a in handoff.artifacts):raise HarnessError('Elevated gate review incomplete or self-authored.')
        inputs.current_evidence=native.evidence
        _approvals_v2(inputs,change,task,native.approvals,plan,stage='qa',source=candidate,evidence=evidence,review=accepted,review_ref=native.review,trust_policy=trust_policy)
    return task,baseline,candidate,evidence


def _verify_ui_v2(inputs,change,plan,task,evidence,native_ref,ui_ref):
    from algooptionx_harness.designs import UIValidationEvidence,DesignSpec,DesignReference
    from algooptionx_harness.ui_validation import UIReference,verify_ui_run
    if ui_ref is None:raise HarnessError('Genuine executed UI evidence is mandatory.')
    ui=inputs.model(ui_ref,UIValidationEvidence)
    if inputs.model(ui.native_task_reference,Task)!=task:raise HarnessError('UI evidence referenced task differs from actual native task.')
    spec=inputs.reader.model(DesignReference(path=plan.design.reference.path,sha256=plan.design.reference.sha256),DesignSpec)
    if (ui.change_id,ui.change_revision,ui.change_digest,ui.policy_digest,ui.source,ui.native_task_digest)!=(change.id,change.revision,digest(change),change.policy.sha256,SourceIdentity(commit=evidence.source_commit,source_digest=evidence.source_digest),digest(task)):
        raise HarnessError('UI evidence parent/candidate/task mismatch.')
    if ui.design.id!=plan.design.id or ui.design.revision!=plan.design.revision or ui.design.reference.path!=plan.design.reference.path or ui.design.reference.sha256!=plan.design.reference.sha256 or ui.native_evidence_reference.path!=native_ref.path or ui.native_evidence_reference.sha256!=native_ref.sha256:raise HarnessError('UI evidence design/native binding differs.')
    report_path=str(Path(native_ref.path).parent/'ui-governance/ui-report.json')
    matches=[a for result in evidence.results for a in result.artifacts if str(Path(native_ref.path).parent/a.path)==report_path]
    if len(matches)!=1:raise HarnessError('Native UI run report missing.')
    plan_sha=inputs.source['files'][__import__('algooptionx_harness.ui_validation',fromlist=['plan_name']).plan_name(change)]['sha256']
    cases=verify_ui_run(inputs.root,plan,spec,task,evidence,Path(native_ref.path),UIReference(path=report_path,sha256=matches[0].sha256),expected_plan_sha=plan_sha)
    if ui.expected_cases!=[c.id for c in spec.validation_cases] or [c.case_id for c in ui.executed_cases]!=ui.expected_cases:raise HarnessError('UI expected/executed cases differ.')
    for declared,actual in zip(ui.executed_cases,cases,strict=True):
        if declared.status!='passed' or declared.results!=actual.results:raise HarnessError('UI declarations differ from actually parsed native reports.')
    return ui


def _child_v2(inputs,change,obligations,plan,item,aggregate_task_value,aggregate_baseline,implementers,trust_policy):
    from algooptionx_harness.lifecycle import _v2_completion,NativeCompletionV2,TestCompletionV2,ReviewCompletionV2
    from algooptionx_harness.designs import _Baseline
    from algooptionx_harness.changes import ReviewRecord
    # Parse strict completion once to locate its selected child, then reproduce its checks.
    from algooptionx_harness.lifecycle import CompletionRecordV2
    parsed=inputs.model(item.completion,CompletionRecordV2).root
    child=next((c for c in change.children if c.id==parsed.child_id and c.id in {r.id for r in change.selected_children}),None)
    if child is None:raise HarnessError('Unknown/unselected child execution.')
    record=_v2_completion(inputs.reader,change,child,item.completion,implementers)
    if isinstance(record,NativeCompletionV2):
        if item.capture is None or item.approvals is None:raise HarnessError('Native child lacks capture and genuine approval references.')
        _,_,_,protected=_v2_context(inputs.root,Path(f'docs/changes/{change.id}/r{change.revision:04d}/change.json'),change.policy.sha256)
        expected_task,before,capture=_captured_v2(inputs,change,obligations,plan,protected,child)
        if inputs.model(item.capture,GovernedCaptureV2)!=capture or inputs.model(record.task,Task)!=expected_task:raise HarnessError('Child task/capture differs.')
        native=NativeRun(task=record.task,baseline=record.baseline,candidate=record.candidate,evidence=record.evidence,review=record.evidence,approvals=item.approvals)
        _,before,after,_=_native_v2(inputs,change,obligations,plan,native,current=False,trust_policy=trust_policy,ui_ref=item.ui_evidence)
        return child.id,record.before,record.after
    if item.capture is not None or item.approvals is not None:raise HarnessError('Non-native child cannot smuggle native authorization.')
    if isinstance(record,TestCompletionV2):
        task=inputs.model(record.task,Task);baseline=inputs.value(record.baseline)
        evidence=inputs.model(record.evidence,Evidence)
        for result in evidence.results:
            for a in result.artifacts:inputs.artifact(str(Path(record.evidence.path).parent/a.path),a.sha256)
        if record.after!=SourceIdentity(commit=inputs.source['commit'],source_digest=digest(inputs.source)):raise HarnessError('Test child does not target final candidate.')
        verify_historical_evidence(inputs.root,task,baseline,inputs.root/record.evidence.path,inputs.source)
        if plan:_verify_ui_v2(inputs,change,plan,task,evidence,record.evidence,record.ui_evidence)
    if isinstance(record,ReviewCompletionV2):
        if item.handoff is None:raise HarnessError('Review declaration lacks actual independent native handoff.')
        handoff=inputs.model(item.handoff,Handoff);review=inputs.model(record.review,ReviewRecord)
        for a in handoff.artifacts:inputs.artifact(a.path,a.sha256)
        if review.provenance!='declared-separate-context':raise HarnessError('Protected reviewer attestation is not implemented; do not trust a label.')
        candidate=inputs.source if record.subject=='candidate' else aggregate_baseline
        accepted=accept_historical_handoff(inputs.root,aggregate_task_value,aggregate_baseline,inputs.root/item.handoff.path,'independent-validator',candidate)
        if accepted.status!='completed' or accepted.actor!=review.actor or accepted.actor in implementers:raise HarnessError('Independent context collision or incomplete review.')
        if record.subject=='design':
            required=change.design_link.reference
            if not any(a.path==required.path and a.sha256==required.sha256 for a in accepted.artifacts):raise HarnessError('Design review omits frozen design package.')
    return child.id,record.before,record.after


def _verify_predecessors_v2(inputs,change,obligations,plan,refs,child,trust_policy):
    # Until the complete prefix can be verified, no dependent writer is released.
    if not refs:raise HarnessError('Mandatory predecessor execution results missing.')
    aggregate_dir=inputs.root/f'.harness/tasks/{change.id}-AGGREGATE-v2'
    from algooptionx_harness.workspace import load_task
    task,baseline=load_task(aggregate_dir/'task.json')
    from algooptionx_harness.ui_validation import load_plan
    protected=load_plan(inputs.root,change)[2] if plan else set()
    if task!=aggregate_task(inputs.root,change,obligations,plan,protected,baseline):raise HarnessError('Predecessor aggregate anchor is stale.')
    order=[r.id for r in change.execution_order];expected=order[:order.index(child.id)]
    if len(refs)!=len(expected):raise HarnessError('Exact serial predecessor prefix required.')
    cursor=SourceIdentity(commit=baseline['commit'],source_digest=digest(baseline))
    implementers={_json(_pinned(inputs.root,c.task_template))['implementer'] for c in change.children if isinstance(c,NativeImplementationV2)}
    for name,ref in zip(expected,refs,strict=True):
        result=_child_v2(inputs,change,obligations,plan,inputs.model(ref,ChildExecutionV2),task,baseline,implementers,trust_policy)
        if result[0]!=name or result[1]!=cursor:raise HarnessError('Predecessor source chain or order differs.')
        cursor=result[2]
    if cursor!=SourceIdentity(commit=inputs.source['commit'],source_digest=digest(inputs.source)):raise HarnessError('Predecessor result is stale.')


def _bundle_v2(root,path,policy_sha256,bundle_path,trust_policy=None):
    inputs=InputsV2(root);change,obligations,plan,protected=_v2_context(inputs.root,path,policy_sha256)
    bundle_name=bundle_path.relative_to(inputs.root).as_posix() if bundle_path.is_absolute() else bundle_path.as_posix()
    bundle=inputs.model(_v2_reference(inputs.root,bundle_name),BundleV2)
    source=SourceIdentity(commit=inputs.source['commit'],source_digest=digest(inputs.source))
    if (bundle.change_id,bundle.change_revision,bundle.change_digest,bundle.policy_digest,bundle.source)!=(change.id,change.revision,digest(change),policy_sha256,source):raise HarnessError('Bundle identity or candidate stale.')
    aggregate=inputs.model(bundle.aggregate.task,Task);baseline=inputs.value(bundle.aggregate.baseline)
    if aggregate!=aggregate_task(inputs.root,change,obligations,plan,protected,baseline):raise HarnessError('Aggregate does not cover exact parent/check/protected inventory.')
    order=[r.id for r in change.execution_order]
    if len(bundle.children)!=len(order):raise HarnessError('Mandatory selected child missing.')
    implementers={_json(_pinned(inputs.root,c.task_template))['implementer'] for c in change.children if isinstance(c,NativeImplementationV2)}
    cursor=SourceIdentity(commit=baseline['commit'],source_digest=digest(baseline))
    for name,item in zip(order,bundle.children,strict=True):
        cid,before,after=_child_v2(inputs,change,obligations,plan,item,aggregate,baseline,implementers,trust_policy)
        if name==change.candidate_review_child and item.handoff!=bundle.aggregate.review:raise HarnessError('Final candidate review must be the actual aggregate independent handoff.')
        if cid!=name or before!=cursor:raise HarnessError('Exact sequential child source chain required.')
        cursor=after
    if cursor!=source:raise HarnessError('Completed children do not reach final aggregate candidate.')
    review=inputs.model(bundle.aggregate.review,Handoff)
    required=[bundle.aggregate.evidence,bundle.rollback_reference,*([bundle.ui_evidence] if bundle.ui_evidence else [])]
    for item in bundle.children:
        required.append(item.completion)
        if item.capture:required.append(item.capture)
        if item.ui_evidence:required.append(item.ui_evidence)
        if item.approvals:
            required.extend(item.approvals.signed)
            for pair in item.approvals.chat:required.extend([pair.request,pair.decision])
    if any(not any(a.path==ref.path and a.sha256==ref.sha256 for a in review.artifacts) for ref in required):raise HarnessError('Aggregate review omits exact child/approval/rollback evidence.')
    if review.actor in implementers:raise HarnessError('Aggregate reviewer is a source implementer.')
    _native_v2(inputs,change,obligations,plan,bundle.aggregate,current=True,trust_policy=trust_policy,final=True,ui_ref=bundle.ui_evidence)
    inputs.raw(bundle.rollback_reference);inputs.finish()
    return inputs,change,bundle,{'status':'verified_local_acceptance','change_id':change.id,'change_revision':change.revision,'change_digest':digest(change),'source':source.model_dump(mode='json'),'policy_digest':policy_sha256,'bundle_digest':digest(bundle),'children':order,'native_evidence_consistency_verified':True,'human_decision_assurance':change.approvals.mode,'protected_execution_provenance':'NOT VERIFIED','grants_deployment':False}


def verify_bundle(root: Path,change_path: Path,policy_sha256: str,bundle_path: Path,trust_policy: Path | None=None)->dict:
    from algooptionx_harness.governance import _change_definition
    change,_,_=_change_definition(root.resolve(),change_path)
    if isinstance(change,ChangeSpecV2):return _bundle_v2(root,change_path,policy_sha256,bundle_path,trust_policy)[3]
    return _verify_bundle_v1_entry(root,change_path,policy_sha256,bundle_path,trust_policy)


def close_change(root: Path,change_path: Path,policy_sha256: str,bundle_path: Path,*,archive: bool=False,trust_policy: Path | None=None)->dict:
    from algooptionx_harness.governance import _change_definition
    change,_,_=_change_definition(root.resolve(),change_path)
    if not isinstance(change,ChangeSpecV2):return _close_change_v1(root,change_path,policy_sha256,bundle_path,archive=archive,trust_policy=trust_policy)
    inputs,change,bundle,result=_bundle_v2(root,change_path,policy_sha256,bundle_path,trust_policy)
    from algooptionx_harness.workspace import contained
    directory=contained(inputs.root,f'.harness/changes/{change.id}/r{change.revision:04d}/v2/closure/{digest(bundle)}')
    acceptance={'schema_version':2,'kind':'acceptance','change_id':change.id,'change_revision':change.revision,'change_digest':digest(change),'policy_digest':policy_sha256,'source':result['source'],'aggregate_evidence':bundle.aggregate.evidence.model_dump(mode='json'),'review':bundle.aggregate.review.model_dump(mode='json'),'ui_evidence':bundle.ui_evidence.model_dump(mode='json') if bundle.ui_evidence else None,'human_decision':(bundle.aggregate.approvals.chat[-1].decision if bundle.aggregate.approvals.chat else next(r for r in bundle.aggregate.approvals.signed if inputs.model(r,Approval).stage=='qa')).model_dump(mode='json'),'grants_deployment':False}
    if archive:
        prior=inputs.value(_v2_reference(inputs.root,str((directory/'acceptance.json').relative_to(inputs.root))))
        if prior!=acceptance:raise HarnessError('Archive acceptance differs.')
        if (directory/'archive.json').exists():raise HarnessError('Archive immutable; cannot overwrite/reopen.')
    else:
        _secure_v2_record(inputs.root,directory/'acceptance.json',acceptance,new_directory=True)
    if archive:_secure_v2_record(inputs.root,directory/'archive.json',{'schema_version':2,'kind':'archive','acceptance':_v2_reference(inputs.root,str((directory/'acceptance.json').relative_to(inputs.root))).model_dump(mode='json'),'bundle':_v2_reference(inputs.root,bundle_path.relative_to(inputs.root).as_posix() if bundle_path.is_absolute() else bundle_path.as_posix()).model_dump(mode='json'),'rollback':bundle.rollback_reference.model_dump(mode='json'),'grants_deployment':False})
    inputs.finish()
    return {**result,'closure_path':str(directory),'archived':archive,'source_unchanged':True}


def _secure_v2_record(root,path,value,*,new_directory=False):
    """Open every ancestor by descriptor; never follow replaced directory links."""
    import os
    from algooptionx_harness.workspace import relative_path
    name=path.relative_to(root).as_posix();relative_path(name)
    parts=Path(name).parts
    flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW
    directory=os.open(root,flags)
    try:
        for index,part in enumerate(parts[:-1]):
            try:os.mkdir(part,mode=0o700,dir_fd=directory)
            except FileExistsError:
                if new_directory and index==len(parts)-2:raise HarnessError('Closure directory already exists.')
            child=os.open(part,flags,dir_fd=directory)
            os.close(directory);directory=child
        leaf=os.open(parts[-1],os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
        with os.fdopen(leaf,'wb') as stream:stream.write(canonical(value)+b'\n')
    except OSError as exc:raise HarnessError('Unsafe or unavailable closure output path.') from exc
    finally:os.close(directory)

"""Native change bindings and local closure checks, never a second executor.

Local hashes/chat records do not authenticate human origin or protected execution.
Historical verification is explicitly separated from fresh aggregate verification.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

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


def verify_bundle(root: Path, change_path: Path, policy_sha256: str, bundle_path: Path,
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


def capture_child(root: Path, change_path: Path, policy_sha256: str, child_id: str) -> dict:
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


def dispatch_child(root: Path, change_path: Path, policy_sha256: str, child_id: str, role: str, dependencies: Path | None = None, trust_policy: Path | None = None) -> dict:
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


def close_change(root: Path, change_path: Path, policy_sha256: str, bundle_path: Path,
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

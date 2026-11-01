"""Read-only lifecycle structure and DAG checks; native gate verification is 1C.

A valid history is a sequence of assertions, never authenticated authorization.
No function here persists events, captures tasks, runs workers or grants gates.
"""
from __future__ import annotations

from itertools import combinations
from pathlib import Path
from typing import Literal

from pydantic import Field

from algooptionx_harness.changes import (
    ChangeContract, ChangeSpec, Identity, Revision, SourceIdentity, StoredReference,
    TransitionRecord, Versioned, safe_path,
)
from algooptionx_harness.governance import _covers, _json, _pinned, _read, validate_change
from algooptionx_harness.models import Role
from algooptionx_harness.workspace import HarnessError, contained, digest, snapshot

PROGRESSION = (
    'draft', 'requirements-validated', 'design-reviewed', 'tasks-planned',
    'awaiting-human-approval', 'approved-for-scoped-implementation', 'in-progress',
    'validation-pending', 'independently-reviewed', 'awaiting-human-acceptance',
    'accepted', 'archived',
)
TERMINAL = {'archived', 'cancelled', 'superseded'}


class ChildOutcome(ChangeContract):
    id: Identity
    revision: Revision
    status: Literal['pending', 'in-progress', 'completed', 'failed', 'blocked', 'cancelled', 'superseded']
    source: SourceIdentity
    evidence: StoredReference | None = None
    review: StoredReference | None = None


class LifecycleEvent(Versioned):
    transition: TransitionRecord
    actor_role: Role | Literal['human-owner']
    operation: Literal['advance', 'reject', 'rework', 'cancel', 'supersede', 'fail', 'rollback'] = 'advance'
    children: list[ChildOutcome] = Field(default_factory=list, max_length=100)
    successor: StoredReference | None = None
    rollback: StoredReference | None = None


def dependency_graph(change: ChangeSpec, scopes: dict[str, list[str]]) -> dict:
    """Stable topological order and transitive write-conflict exclusion."""
    nodes = {child.id: child for child in change.children}
    if set(scopes) != set(nodes):
        raise HarnessError('Child scope inventory must be exact.')
    if sum(len(paths) for paths in scopes.values()) > 1000:
        raise HarnessError('Dependency scope budget exceeded (1000 total).')
    for paths in scopes.values():
        if len(paths) > 200 or len(paths) != len(set(paths)):
            raise HarnessError('Child scopes must be unique and bounded (200 per child).')
        if not paths:
            raise HarnessError('Empty child write scope.')
        for path in paths:
            safe_path(path, directory=True)
    ancestors: dict[str, set[str]] = {}
    remaining = set(nodes)
    order = []
    for child in nodes.values():
        if not set(child.depends_on) <= set(nodes):
            raise HarnessError('A dependency is missing.')
    while remaining:
        ready = sorted(name for name in remaining if set(nodes[name].depends_on) <= set(order))
        if not ready:
            raise HarnessError('Dependency cycle rejected.')
        for name in ready:
            ancestors[name] = set(nodes[name].depends_on)
            for parent in nodes[name].depends_on:
                ancestors[name].update(ancestors[parent])
            order.append(name)
            remaining.remove(name)
    for left, right in combinations(sorted(nodes), 2):
        overlap = any(_covers(a, b) or _covers(b, a) for a in scopes[left] for b in scopes[right])
        if overlap and left not in ancestors[right] and right not in ancestors[left]:
            raise HarnessError('Overlapping child writers require dependency ordering.')
    return {'order': order, 'ancestors': {name: sorted(ancestors[name]) for name in order}}


def child_summary(change: ChangeSpec, children: list[ChildOutcome], graph: dict) -> dict:
    expected = {child.id: child.revision for child in change.children}
    actual = {child.id: child for child in children}
    if len(actual) != len(children) or set(actual) != set(expected):
        raise HarnessError('Every mandatory child must appear exactly once.')
    for name, child in actual.items():
        if child.revision != expected[name]:
            raise HarnessError('Stale child revision rejected.')
        if child.status == 'completed' and (child.evidence is None or child.review is None):
            raise HarnessError('Completed child requires evidence and review references.')
        if child.status in {'in-progress', 'completed'} and any(
            actual[parent].status != 'completed' for parent in graph['ancestors'][name]
        ):
            raise HarnessError('Child started before its dependencies completed.')
    return {
        'all_completed': all(child.status == 'completed' for child in children),
        'not_completed': sorted(name for name, child in actual.items() if child.status != 'completed'),
        'ready': sorted(name for name, child in actual.items() if child.status == 'pending' and all(
            actual[parent].status == 'completed' for parent in graph['ancestors'][name]
        )),
        'evidence_verified': False,
    }


def _actor(change: ChangeSpec, event: LifecycleEvent):
    record = event.transition
    if event.actor_role == 'human-owner' and record.actor != change.owner:
        raise HarnessError('Owner identity does not match the change.')
    human = event.operation in {'cancel', 'supersede', 'rollback', 'reject'} or record.to_state in {
        'approved-for-scoped-implementation', 'accepted',
    }
    if human and event.actor_role != 'human-owner':
        raise HarnessError('This decision requires the declared human owner.')
    role_targets = {
        'requirements-validated': {'requirements-validator', 'independent-validator'},
        'design-reviewed': {'architect', 'independent-validator'},
        'independently-reviewed': {'independent-validator'},
        'archived': {'release-governor'},
        'in-progress': {role for child in change.children for role in child.roles},
    }
    if not human and record.to_state in role_targets and event.actor_role not in role_targets[record.to_state]:
        raise HarnessError('Actor role is incompatible with the transition.')


def transition_requirements(event: LifecycleEvent, obligations: dict) -> list[str]:
    """Obligations only; names are not receipts, signatures or executed gates."""
    target = event.transition.to_state
    requirements = {
        'draft': [],
        'requirements-validated': ['gate:REFERENCES', 'gate:INDEPENDENT-REVIEW'],
        'design-reviewed': ['gate:ARCHITECTURE', 'gate:INDEPENDENT-REVIEW'],
        'tasks-planned': ['gate:CONFIG'],
        'awaiting-human-approval': ['gate:REFERENCES'],
        'approved-for-scoped-implementation': [f'approval:{stage}' for stage in obligations['required_approval_stages'] if stage not in {'qa', 'release'}],
        'in-progress': ['approval:implementation'],
        'validation-pending': ['approval:implementation', 'native:candidate-scope'],
    }.get(target, [])
    if target in {'independently-reviewed', 'awaiting-human-acceptance', 'accepted', 'archived'}:
        requirements += [f'gate:{gate}' for gate in obligations['required_gates']]
        requirements += ['native:all-child-results']
    if target in {'accepted', 'archived'}:
        requirements += [f'approval:{stage}' for stage in obligations['required_approval_stages']]
    if target == 'archived':
        requirements += ['native:acceptance-and-archive-completeness']
    if event.operation != 'advance':
        requirements += ['native:decision']
    if event.operation == 'rework':
        requirements += ['approval:implementation']
    if event.operation == 'rollback':
        requirements += ['native:rollback']
    return sorted(set(requirements))


def check_event(change: ChangeSpec, event: LifecycleEvent, previous: LifecycleEvent | None,
                *, change_digest: str, policy_digest: str, graph: dict) -> None:
    """Validate one structural edge; deliberately does not authenticate any gate."""
    record = event.transition
    if (record.change_id, record.change_revision, record.change_digest, record.policy_digest) != (
        change.id, change.revision, change_digest, policy_digest,
    ):
        raise HarnessError('Immutable change or policy identity differs.')
    before = previous.transition if previous else None
    if record.previous_record_digest != (digest(previous) if previous else None):
        raise HarnessError('History digest chain differs.')
    if record.from_state != (before.to_state if before else None):
        raise HarnessError('Transition source state differs.')
    if before and record.recorded_at <= before.recorded_at:
        raise HarnessError('History timestamps must increase.')
    if before and before.to_state in TERMINAL:
        raise HarnessError('Terminal changes cannot resume.')
    source_changed = before and record.source != before.source
    if source_changed and not (
        event.operation == 'advance' and record.from_state == 'in-progress' and record.to_state == 'validation-pending'
        or event.operation == 'rollback'
    ):
        raise HarnessError('Source identity changed outside candidate freeze or rollback.')
    _actor(change, event)
    start, end = record.from_state, record.to_state
    if event.operation == 'advance':
        if start is None:
            legal = end == 'draft'
        else:
            legal = start in PROGRESSION[:-1] and end == PROGRESSION[PROGRESSION.index(start) + 1]
    elif event.operation == 'reject':
        legal = start in PROGRESSION[1:6] and end == 'draft'
    elif event.operation == 'rework':
        legal = start in {'validation-pending', 'independently-reviewed', 'awaiting-human-acceptance', 'failed'} and end == 'in-progress'
    elif event.operation == 'cancel':
        legal = start is not None and start not in {'accepted', *TERMINAL} and end == 'cancelled'
    elif event.operation == 'supersede':
        legal = start is not None and start not in TERMINAL and end == 'superseded' and event.successor is not None
    elif event.operation == 'rollback':
        legal = start == 'accepted' and end == 'failed' and event.rollback is not None
    else:  # fail
        legal = start in {'in-progress', 'validation-pending', 'independently-reviewed', 'awaiting-human-acceptance'} and end == 'failed'
    if not legal:
        raise HarnessError('Illegal lifecycle edge or missing decision reference.')
    if event.operation != 'supersede' and event.successor is not None:
        raise HarnessError('Unexpected successor reference.')
    if event.operation != 'rollback' and event.rollback is not None:
        raise HarnessError('Unexpected rollback reference.')
    summary = child_summary(change, event.children, graph)
    if end in PROGRESSION[:6] and any(child.status != 'pending' for child in event.children):
        raise HarnessError('Children cannot execute before scoped implementation.')
    if previous:
        old_children = {child.id: child for child in previous.children}
        old = {name: child.status for name, child in old_children.items()}
        for child in event.children:
            prior = old_children[child.id]
            if prior.status == 'in-progress' and child.status == 'pending' and event.operation != 'rework':
                raise HarnessError('Started children reset only through explicit rework.')
            if prior.status == 'completed' and child.status == 'completed' and child != prior:
                raise HarnessError('Completed child bindings cannot be rewritten without invalidating completion.')
            if old[child.id] in {'failed', 'blocked', 'cancelled', 'superseded'} and child.status != old[child.id] and event.operation != 'rework':
                raise HarnessError('Child recovery requires explicit rework.')
            if old[child.id] == 'completed' and child.status != 'completed' and event.operation not in {'rework', 'rollback'}:
                raise HarnessError('Child completion cannot silently regress.')
            if event.operation == 'rework' and old[child.id] != 'completed' and child.status == 'completed':
                raise HarnessError('Rework cannot assert recovered completion immediately.')
    if end in {'independently-reviewed', 'awaiting-human-acceptance', 'accepted', 'archived'} and not summary['all_completed']:
        raise HarnessError('Incomplete or failed children block parent completion.')
    if end == 'archived' and not record.evidence:
        raise HarnessError('Archive manifest reference required.')


def _references(event: LifecycleEvent):
    yield from event.transition.evidence
    for child in event.children:
        for ref in (child.evidence, child.review):
            if ref is not None:
                yield ref
    for ref in (event.successor, event.rollback):
        if ref is not None:
            yield ref


def _inspect_lifecycle_v1(root: Path, change_path: Path, policy_sha256: str,
                      request: Path | None = None) -> dict:
    """No mutation, no verifier plugin/Boolean override, no gate authorization."""
    root = root.resolve()
    initial = snapshot(root)
    change_path = change_path if change_path.is_absolute() else root / change_path
    obligations = validate_change(root, change_path, policy_sha256)
    name = str(change_path.relative_to(root)) if change_path.is_absolute() else change_path.as_posix()
    change = ChangeSpec.model_validate(_json(_read(root, name)))
    if digest(initial) != obligations['source_digest']:
        raise HarnessError('Source changed during contract validation.')
    scopes = {child.id: _json(_pinned(root, child.task_template))['allowed_paths'] for child in change.children}
    graph = dependency_graph(change, scopes)
    namespace = f'.harness/changes/{change.id}/r{change.revision:04d}'
    history_name = namespace + '/events'
    history_dir = contained(root, history_name)

    def listing():
        contained(root, history_name)
        if not history_dir.exists():
            return []
        if not history_dir.is_dir():
            raise HarnessError('History must be a directory.')
        names = sorted(item.name for item in history_dir.iterdir())
        if len(names) > 1000 or names != [f'{i:06d}.json' for i in range(1, len(names) + 1)]:
            raise HarnessError('History requires contiguous numbered JSON events (limit 1000).')
        return names

    names = listing()
    pinned = {}
    events = []
    ids = set()

    def pin(path, raw):
        if path in pinned and pinned[path] != raw:
            raise HarnessError('Repeated operational input changed.')
        pinned[path] = raw
        if sum(len(value) for value in pinned.values()) > 16 * 1024 * 1024:
            raise HarnessError('Operational input budget exceeded (16 MiB).')

    def load_event(path):
        raw = _read(root, path)
        pin(path, raw)
        _json(raw)  # Reject duplicate keys before strict JSON-mode datetime parsing.
        event = LifecycleEvent.model_validate_json(raw)
        for ref in _references(event):
            pin(ref.path, _pinned(root, ref))
        if event.successor:
            successor = ChangeSpec.model_validate(_json(_pinned(root, event.successor)))
            if successor.id != change.id or successor.revision <= change.revision:
                raise HarnessError('Supersession requires a newer revision of the same change.')
        return event

    for filename in names:
        event = load_event(f'{history_name}/{filename}')
        if event.transition.event_id in ids:
            raise HarnessError('Duplicate lifecycle event identity.')
        ids.add(event.transition.event_id)
        check_event(change, event, events[-1] if events else None,
                    change_digest=obligations['change_digest'], policy_digest=policy_sha256, graph=graph)
        events.append(event)
    current_source = SourceIdentity(commit=initial['commit'], source_digest=digest(initial))
    last = events[-1] if events else None
    output = {
        **obligations, 'status': 'verified_structure', 'dependency_dag_verified': True,
        'lifecycle_transitions_verified': False, 'history_structure_verified': True,
        'history_gates_verified': False, 'recorded_state': last.transition.to_state if last else None,
        'record_count': len(events), 'dependency_graph': graph,
        'history_current_source': last.transition.source == current_source if last else None,
        'native_integration': 'requires-phase1c-integration', 'authorization': 'not_granted',
    }
    if last:
        output['children'] = child_summary(change, last.children, graph)
    if request is not None:
        request_name = str(request.relative_to(root)) if request.is_absolute() else request.as_posix()
        if not request_name.startswith(namespace + '/requests/') or not request_name.endswith('.json'):
            raise HarnessError('Request must be JSON in this change revision requests directory.')
        event = load_event(request_name)
        if event.transition.event_id in ids:
            raise HarnessError('Duplicate lifecycle event identity.')
        if event.transition.source != current_source:
            raise HarnessError('Requested transition source is stale.')
        check_event(change, event, last, change_digest=obligations['change_digest'], policy_digest=policy_sha256, graph=graph)
        requirements = transition_requirements(event, obligations)
        # Historical declarations do not prove their prerequisites either.
        if events:
            requirements += ['native:verified-history-gates']
        output.update(status='blocked' if requirements else 'verified_structure',
                      requested_state=event.transition.to_state,
                      missing_prerequisites=sorted(set(requirements)),
                      transition_permitted=False)
    if listing() != names or any(_read(root, path) != raw for path, raw in pinned.items()):
        raise HarnessError('Operational inputs changed during lifecycle inspection.')
    if snapshot(root) != initial:
        raise HarnessError('Source changed during lifecycle inspection.')
    return output


# Private operational v2 wrappers; the public v1 schemas/payloads remain intact.
from typing import Annotated
import json
from pydantic import model_validator, RootModel
from algooptionx_harness.changes import (
    VersionedV2, Sha256, NativeImplementationV2, IndependentReviewV2,
    DesignValidationV2, TestEvidenceV2, ChangeSpecV2, ReviewRecord, parse_change,
)


class CompletionV2(VersionedV2):
    change_id: Identity
    change_revision: Revision
    change_digest: Sha256
    policy_digest: Sha256
    child_id: Identity
    child_revision: Revision
    before: SourceIdentity
    after: SourceIdentity
    design_record_digest: Sha256 | None = None


class NativeCompletionV2(CompletionV2):
    kind: Literal['native-implementation']
    task: StoredReference
    baseline: StoredReference
    candidate: StoredReference
    evidence: StoredReference


class DesignCompletionV2(CompletionV2):
    kind: Literal['design-validation']
    report: StoredReference


class TestCompletionV2(CompletionV2):
    kind: Literal['test-evidence']
    baseline: StoredReference
    task: StoredReference
    evidence: StoredReference
    ui_evidence: StoredReference | None = None


class ReviewCompletionV2(CompletionV2):
    kind: Literal['independent-review']
    subject: Literal['design', 'candidate']
    review: StoredReference


TypedCompletionV2 = Annotated[
    NativeCompletionV2 | DesignCompletionV2 | TestCompletionV2 | ReviewCompletionV2,
    Field(discriminator='kind'),
]


class CompletionRecordV2(RootModel[TypedCompletionV2]):
    pass


class ChildOutcomeV2(ChangeContract):
    id: Identity
    revision: Revision
    status: Literal['pending','in-progress','completed','failed','blocked','cancelled','superseded']
    completion: StoredReference | None = None

    @model_validator(mode='after')
    def completion_required(self):
        if (self.status=='completed') != (self.completion is not None):
            raise ValueError('Only completed children carry a typed completion reference.')
        return self


class LifecycleEventV2(VersionedV2):
    kind: Literal['lifecycle-event']
    transition: TransitionRecord
    actor_role: Role | Literal['human-owner']
    operation: Literal['advance','reject','rework','cancel','supersede','fail','rollback']='advance'
    children: list[ChildOutcomeV2] = Field(max_length=100)
    successor: StoredReference | None = None
    rollback: StoredReference | None = None


def _v2_completion(reader,change,plan,ref,implementers):
    from algooptionx_harness.designs import (
        _decode, _Baseline, DesignReference, _native_evidence_claims, validate_design,
    )
    from algooptionx_harness.models import Task, Evidence
    from algooptionx_harness.workspace import validate_scope
    value=_decode(reader.pin(DesignReference(path=ref.path,sha256=ref.sha256),json_file=True))
    record=CompletionRecordV2.model_validate_json(json.dumps(value)).root
    if (record.change_id,record.change_revision,record.change_digest,record.policy_digest,record.child_id,record.child_revision,record.kind)!=(change.id,change.revision,digest(change),change.policy.sha256,plan.id,plan.revision,plan.kind):
        raise HarnessError('Typed completion belongs to another parent, child or policy.')
    if record.design_record_digest!=(change.design_link.record_digest if change.design_link else None):
        raise HarnessError('Completion design revision is stale.')
    def model(ref,cls):
        return reader.model(DesignReference(path=ref.path,sha256=ref.sha256),cls)
    if not isinstance(record,NativeCompletionV2) and record.before!=record.after:
        raise HarnessError('Read-only child changed source.')
    if isinstance(record,(NativeCompletionV2,TestCompletionV2)):
        task=model(record.task,Task)
        baseline=model(record.baseline,_Baseline)
        from algooptionx_harness.governance import _check_v2_protected
        _check_v2_protected(change,task,baseline,reader)
        if not set(plan.requirement_ids)<=set(task.requirement_ids):
            raise HarnessError('Native evidence does not cover child requirements.')
        evidence=model(record.evidence,Evidence)
        if (evidence.task_id,evidence.task_digest,evidence.source_commit,evidence.source_digest,evidence.final_source_digest)!=(task.id,digest(task),record.after.commit,record.after.source_digest,record.after.source_digest) or task.source_commit!=record.after.commit:
            raise HarnessError('Native evidence source or task identity differs.')
        if evidence.status!='passed':raise HarnessError('Nonpassing native declarations cannot complete a child.')
        _native_evidence_claims(task,evidence,record.evidence.path,reader.root)
        for result in evidence.results:
            for artifact in result.artifacts:
                reader.pin(DesignReference(path=str(Path(record.evidence.path).parent/artifact.path),sha256=artifact.sha256))
        if isinstance(record,NativeCompletionV2):
            candidate=model(record.candidate,_Baseline)
            _check_v2_protected(change,task,baseline,reader,candidate)
            if (baseline.commit,digest(baseline),candidate.commit,digest(candidate))!=(record.before.commit,record.before.source_digest,record.after.commit,record.after.source_digest):
                raise HarnessError('Native completion snapshots differ.')
            template=_decode(reader.pin(DesignReference(path=plan.task_template.path,sha256=plan.task_template.sha256),json_file=True))
            expected=Task.model_validate({**template,'source_commit':baseline.commit,'baseline_digest':digest(baseline)})
            if task!=expected:raise HarnessError('Captured native task differs from frozen template.')
            changed=validate_scope(task,baseline.model_dump(mode='json'),candidate.model_dump(mode='json'))
            if changed!=evidence.changed_paths:raise HarnessError('Native changed-path declaration differs.')
        else:
            designated=change.design_obligations and plan.id in change.design_obligations.candidate_evidence_children
            if designated and record.ui_evidence is None:raise HarnessError('Design validation obligations require UI evidence.')
            if record.ui_evidence:
                raw=reader.pin(DesignReference(path=record.ui_evidence.path,sha256=record.ui_evidence.sha256),json_file=True)
                from algooptionx_harness.designs import UIValidationEvidence
                ui=UIValidationEvidence.model_validate_json(raw)
                if (ui.change_id,ui.change_revision,ui.change_digest,ui.policy_digest,ui.source)!=(change.id,change.revision,digest(change),change.policy.sha256,record.after) or ui.native_task_digest!=digest(task) or ui.native_evidence_reference.path!=record.evidence.path or ui.native_evidence_reference.sha256!=record.evidence.sha256:
                    raise HarnessError('UI evidence targets another candidate or native run.')
                result=validate_design(reader.root,Path(record.ui_evidence.path),change.policy.sha256)
                if result['case_declarations']['passed']!=len(ui.expected_cases):raise HarnessError('Missing or nonpassing UI cases block completion.')
    elif isinstance(record,DesignCompletionV2):
        if change.design_link is None:raise HarnessError('Design completion requires a frozen design.')
        value=_decode(reader.pin(DesignReference(path=record.report.path,sha256=record.report.sha256),json_file=True))
        expected=validate_design(reader.root,Path(change.design_link.reference.path),change.policy.sha256)
        observed={'source_commit':record.before.commit,'source_digest':record.before.source_digest}
        expected.update(observed)
        if value!=expected:raise HarnessError('Design validator declaration differs from the frozen package.')
    else:
        if record.subject!=plan.subject:raise HarnessError('Review subject differs.')
        review=model(record.review,ReviewRecord)
        if (review.change_id,review.change_revision,review.change_digest,review.policy_digest,review.source)!=(change.id,change.revision,digest(change),change.policy.sha256,record.after) or review.status!='completed':
            raise HarnessError('Review is stale or incomplete.')
        if review.actor in implementers or not implementers<=set(review.implementer_contexts):
            raise HarnessError('Review omits implementation contexts or reviews itself.')
    return record


def _v2_children(change,event,previous,graph,completions,initial_source):
    plans={c.id:c for c in change.children};outcomes={c.id:c for c in event.children}
    order=graph['order']
    if len(outcomes)!=len(event.children) or set(outcomes)!=set(order):raise HarnessError('Selected child inventory must be exact.')
    cursor=initial_source
    complete=set()
    for name in order:
        child=outcomes[name];plan=plans[name]
        if child.revision!=plan.revision:raise HarnessError('Stale child revision.')
        if child.status in {'in-progress','completed'} and set(order[:order.index(name)])-complete:
            raise HarnessError('Sequential children cannot bypass preceding children.')
        if child.status=='completed':
            record=completions[name]
            if record.before!=cursor:raise HarnessError('Child snapshot chain is discontinuous.')
            cursor=record.after;complete.add(name)
        planning=event.transition.to_state in PROGRESSION[:6]
        readonly_design=isinstance(plan,DesignValidationV2) or isinstance(plan,IndependentReviewV2) and plan.subject=='design'
        if planning and not readonly_design and child.status!='pending':raise HarnessError('Implementation/test children cannot execute during planning.')
        if isinstance(plan,TestEvidenceV2) and child.status=='completed' and event.transition.to_state in PROGRESSION[:7]:
            raise HarnessError('Candidate tests require candidate freeze.')
        if isinstance(plan,IndependentReviewV2) and plan.subject=='candidate' and child.status=='completed' and event.transition.to_state in PROGRESSION[:8]:
            raise HarnessError('Candidate review requires validation completion.')
    if previous:
        old={c.id:c for c in previous.children}
        for name,child in outcomes.items():
            prior=old[name]
            if event.operation!='advance' and prior.status!='completed' and child.status=='completed':raise HarnessError('Decision operations cannot invent completion.')
            if prior.status=='completed' and child.status=='completed' and child!=prior:raise HarnessError('Completed bindings cannot be rewritten.')
            if prior.status=='completed' and child.status!='completed' and event.operation not in {'rework','rollback'}:raise HarnessError('Completion regression requires explicit invalidation.')
            if prior.status in {'failed','blocked','cancelled','superseded'} and child!=prior and event.operation!='rework':raise HarnessError('Recovery requires rework.')
            if prior.status=='in-progress' and child.status=='pending' and event.operation!='rework':raise HarnessError('Started child reset requires rework.')
            if event.operation=='rework' and prior.status!='completed' and child.status=='completed':raise HarnessError('Rework cannot invent recovered completion.')
    target=event.transition.to_state
    if target in {'design-reviewed',*PROGRESSION[3:]} and change.design_obligations:
        design_ids=set(change.design_obligations.validation_children)|{change.design_obligations.design_review_child}
        if not design_ids<=complete:raise HarnessError('Design validation/review declarations are incomplete.')
    if target in PROGRESSION[8:] and complete!=set(order):raise HarnessError('Incomplete selected children block parent readiness.')
    if target in PROGRESSION[7:] and any(isinstance(plans[n],TestEvidenceV2) and n in complete and completions[n].after!=cursor for n in order):
        raise HarnessError('Candidate test evidence predates the final writer.')
    if target in PROGRESSION[7:] and (any(isinstance(plans[n],NativeImplementationV2) and n not in complete for n in order) or event.transition.source!=cursor):
        raise HarnessError('Candidate source does not match the sequential writer chain.')
    return {'all_completed':complete==set(order),'not_completed':sorted(set(order)-complete),'structural_completion_only':True,'evidence_execution_verified':False,'chain_source':cursor.model_dump(mode='json')}


def _v2_event(change,event,previous,graph,completions,initial_source):
    record=event.transition;before=previous.transition if previous else None
    if (record.change_id,record.change_revision,record.change_digest,record.policy_digest)!=(change.id,change.revision,digest(change),change.policy.sha256):raise HarnessError('V2 history identity differs.')
    if record.previous_record_digest!=(digest(previous) if previous else None) or record.from_state!=(before.to_state if before else None):raise HarnessError('V2 history digest/state chain differs.')
    if before and (record.recorded_at<=before.recorded_at or before.to_state in TERMINAL):raise HarnessError('History time or terminal state differs.')
    if before and record.source!=before.source and not (event.operation=='advance' and record.from_state=='in-progress' and record.to_state=='validation-pending' or event.operation=='rollback'):
        raise HarnessError('Source changed outside candidate freeze or rollback.')
    _actor(change,event)
    start,end=record.from_state,record.to_state
    if event.operation=='advance':legal=end=='draft' if start is None else start in PROGRESSION[:-1] and end==PROGRESSION[PROGRESSION.index(start)+1]
    elif event.operation=='reject':legal=start in PROGRESSION[1:6] and end=='draft'
    elif event.operation=='rework':legal=start in {'validation-pending','independently-reviewed','awaiting-human-acceptance','failed'} and end=='in-progress' and (not previous or previous.operation!='rollback')
    elif event.operation=='cancel':legal=start is not None and start not in {'accepted',*TERMINAL} and end=='cancelled'
    elif event.operation=='supersede':legal=start is not None and start not in TERMINAL and end=='superseded' and event.successor is not None
    elif event.operation=='rollback':legal=start=='accepted' and end=='failed' and event.rollback is not None
    else:legal=start in {'in-progress','validation-pending','independently-reviewed','awaiting-human-acceptance'} and end=='failed'
    if not legal or (event.operation=='supersede')!=(event.successor is not None) or (event.operation=='rollback')!=(event.rollback is not None):raise HarnessError('Illegal v2 lifecycle edge or decision reference.')
    if end=='archived' and not record.evidence:raise HarnessError('Archive declaration requires a manifest reference.')
    return _v2_children(change,event,previous,graph,completions,initial_source)


def inspect_lifecycle(root: Path,change_path: Path,policy_sha256: str,request: Path | None=None,*,bundle: Path | None=None,trust_policy: Path | None=None)->dict:
    root=root.resolve();path=change_path if change_path.is_absolute() else root/change_path
    obligations=validate_change(root,path,policy_sha256)
    if obligations.get('change_schema_version')!=2:
        return _inspect_lifecycle_v1(root,path,policy_sha256,request)
    output=_inspect_lifecycle_v2(root,path,policy_sha256,request,obligations)
    output.update(design_aware_enforcement_available=True,acceptance_readiness='NOT VERIFIED: no execution bundle supplied')
    if bundle is not None:
        from algooptionx_harness.enforcement import verify_bundle
        verified=verify_bundle(root,path,policy_sha256,bundle,trust_policy)
        output.update(acceptance_readiness='verified_local_prerequisites',verified_bundle=verified,native_evidence_consistency_verified=True,native_integration='design-aware-enforcement')
        if 'missing_prerequisites' in output:
            output['missing_prerequisites']=[x for x in output['missing_prerequisites'] if x!='uiux:v2-enforcement-not-implemented']
    return output


def _inspect_lifecycle_v2(root,path,policy_sha256,request,obligations):
    from algooptionx_harness.designs import _Reader,_decode,_bounded_snapshot,DesignReference
    reader=_Reader(root,path.relative_to(root).as_posix());before=_bounded_snapshot(root)
    change=parse_change(_decode(reader.raw(path.relative_to(root).as_posix())))
    if not isinstance(change,ChangeSpecV2) or digest(change)!=obligations['change_digest'] or digest(before)!=obligations['source_digest']:raise HarnessError('V2 lifecycle context changed.')
    from algooptionx_harness.governance import _reject_legacy_v2_history
    _reject_legacy_v2_history(root,change)
    graph=obligations['dependency_graph'];plans={c.id:c for c in change.children}
    implementers=set()
    for c in change.children:
        if isinstance(c,NativeImplementationV2):
            template=_decode(reader.pin(DesignReference(path=c.task_template.path,sha256=c.task_template.sha256),json_file=True));implementers.add(template['implementer'])
    namespace=f'.harness/changes/{change.id}/r{change.revision:04d}/v2'
    folder=contained(root,namespace+'/events')
    def listing():
        contained(root,namespace+'/events')
        if not folder.exists():return []
        if not folder.is_dir():raise HarnessError('History must be a directory.')
        # Bound enumeration before sorting/allocation, unlike untrusted glob loading.
        names=[]
        for item in folder.iterdir():
            names.append(item.name)
            if len(names)>1000:raise HarnessError('History event budget exceeded.')
        names.sort()
        if names!=[f'{i:06d}.json' for i in range(1,len(names)+1)]:raise HarnessError('V2 history must be contiguous numbered JSON.')
        return names
    def load(name):
        raw=reader.raw(name);_decode(raw)
        event=LifecycleEventV2.model_validate_json(raw)
        comps={}
        for child in event.children:
            if child.id not in plans:raise HarnessError('Unknown child outcome.')
            if child.completion:comps[child.id]=_v2_completion(reader,change,plans[child.id],child.completion,implementers)
        for ref in [*event.transition.evidence,*([event.rollback] if event.rollback else [])]:
            reader.pin(DesignReference(path=ref.path,sha256=ref.sha256))
        if event.successor:
            successor=parse_change(_decode(reader.pin(DesignReference(path=event.successor.path,sha256=event.successor.sha256),json_file=True)))
            if not isinstance(successor,ChangeSpecV2) or successor.id!=change.id or successor.revision<=change.revision or event.successor.path!=f'docs/changes/{successor.id}/r{successor.revision:04d}/change.json':raise HarnessError('Successor must be a newer canonical v2 revision.')
        return event,comps
    names=listing();events=[];ids=set();summary=None;initial_source=None
    for filename in names:
        event,comps=load(namespace+'/events/'+filename)
        if event.transition.event_id in ids:raise HarnessError('Duplicate v2 event identity.')
        ids.add(event.transition.event_id)
        initial_source=initial_source or event.transition.source
        summary=_v2_event(change,event,events[-1] if events else None,graph,comps,initial_source)
        events.append(event)
    last=events[-1] if events else None
    output={**obligations,'status':'verified_structure','recorded_state':last.transition.to_state if last else None,'record_count':len(events),'history_structure_verified':True,'history_gates_verified':False,'lifecycle_transitions_verified':False,'history_current_source':last.transition.source==SourceIdentity(commit=before['commit'],source_digest=digest(before)) if last else None,'children':summary,'transition_permitted':False,'authorization':'not_granted','execution_verified':False,'native_integration':'v2-requires-uiux-phase1c'}
    if request is not None:
        name=request.relative_to(root).as_posix() if request.is_absolute() else request.as_posix()
        if not name.startswith(namespace+'/requests/') or not name.endswith('.json'):raise HarnessError('V2 request must be in its canonical requests namespace.')
        event,comps=load(name)
        if event.transition.event_id in ids:raise HarnessError('Duplicate requested event identity.')
        if event.transition.source!=SourceIdentity(commit=before['commit'],source_digest=digest(before)):raise HarnessError('Requested source is stale.')
        summary=_v2_event(change,event,last,graph,comps,initial_source or event.transition.source)
        required=transition_requirements(event,obligations)+['uiux:v2-enforcement-not-implemented']
        if change.design_link:required+=['design:exact-frozen-revision','design:typed-validation-and-review','approval:ui']
        output.update(status='blocked',requested_state=event.transition.to_state,children=summary,missing_prerequisites=sorted(set(required)))
    reader.finish()
    _reject_legacy_v2_history(root,change)
    if listing()!=names or _bounded_snapshot(root)!=before:raise HarnessError('V2 history or source changed during inspection.')
    return output

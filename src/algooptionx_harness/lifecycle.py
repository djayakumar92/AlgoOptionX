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


def inspect_lifecycle(root: Path, change_path: Path, policy_sha256: str,
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

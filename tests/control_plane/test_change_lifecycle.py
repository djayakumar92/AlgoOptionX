"""Synthetic lifecycle structures are not execution or human approval evidence."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from algooptionx_harness.changes import ChangeSpec
from algooptionx_harness.cli import main
from algooptionx_harness.lifecycle import (
    ChildOutcome, LifecycleEvent, PROGRESSION, check_event, child_summary,
    dependency_graph, inspect_lifecycle, transition_requirements,
)
from algooptionx_harness.workspace import HarnessError, digest, snapshot
from tests.control_plane.test_change_contracts import make_change, save_change, write_json

SHA = 'a' * 64
SOURCE = {'commit': 'b' * 40, 'source_digest': 'c' * 64}
REF = {'path': '.harness/fixture/review.json', 'sha256': SHA}


def spec_fixture(tmp_path):
    root, raw, pin, _ = make_change(tmp_path)
    return root, ChangeSpec.model_validate(raw), pin


def graph(change):
    return dependency_graph(change, {child.id: ['docs/' + child.id + '.md'] for child in change.children})


def event(change, target='draft', previous=None, *, operation='advance', source=None, completed=False, actor_role=None):
    roles = {'requirements-validated': 'requirements-validator', 'design-reviewed': 'architect',
             'approved-for-scoped-implementation': 'human-owner', 'in-progress': 'backend-engineer',
             'independently-reviewed': 'independent-validator', 'accepted': 'human-owner', 'archived': 'release-governor'}
    role = actor_role or ('human-owner' if operation in {'reject', 'cancel', 'supersede', 'rollback'} else roles.get(target, 'product'))
    stamp = previous.transition.recorded_at + timedelta(seconds=1) if previous else datetime(2026, 1, 1, tzinfo=timezone.utc)
    raw = {'transition': {'kind': 'transition', 'change_id': change.id, 'change_revision': change.revision,
        'change_digest': digest(change), 'policy_digest': change.policy.sha256, 'source': source or (previous.transition.source.model_dump() if previous else SOURCE),
        'event_id': f'event-{stamp.isoformat()}', 'previous_record_digest': digest(previous) if previous else None,
        'from_state': previous.transition.to_state if previous else None, 'to_state': target,
        'actor': change.owner if role == 'human-owner' else 'agent:synthetic', 'recorded_at': stamp,
        'reason': 'Synthetic structural test only.', 'evidence': [REF] if target == 'archived' else []},
        'actor_role': role, 'operation': operation,
        'children': [{'id': c.id, 'revision': c.revision, 'status': 'completed' if completed else 'pending',
                      'source': SOURCE, 'evidence': REF if completed else None, 'review': REF if completed else None} for c in change.children]}
    return LifecycleEvent.model_validate(raw)


def checked(change, current, previous=None):
    check_event(change, current, previous, change_digest=digest(change), policy_digest=change.policy.sha256, graph=graph(change))


def progression(change, stop='accepted'):
    previous = None
    for target in PROGRESSION:
        current = event(change, target, previous, completed=target in PROGRESSION[7:])
        checked(change, current, previous)
        previous = current
        if target == stop:
            return previous


def test_complete_structural_progression_requires_real_gates_later(tmp_path):
    _, change, _ = spec_fixture(tmp_path)
    last = progression(change, 'archived')
    obligations = {'required_gates': ['PYTHON', 'INDEPENDENT-REVIEW'], 'required_approval_stages': ['plan', 'implementation', 'qa']}
    assert set(transition_requirements(last, obligations)) == {
        'gate:PYTHON', 'gate:INDEPENDENT-REVIEW', 'approval:plan', 'approval:implementation',
        'approval:qa', 'native:all-child-results', 'native:acceptance-and-archive-completeness'}


@pytest.mark.parametrize('issue', ['missing', 'cycle', 'conflict'])
def test_dag_rejects_missing_cycles_and_parallel_writers(tmp_path, issue):
    _, change, _ = spec_fixture(tmp_path)
    raw = change.model_dump()
    child = copy.deepcopy(raw['children'][0]); child['id'] = 'CHILD-002'
    raw['children'].append(child)
    if issue == 'missing': raw['children'][0]['depends_on'] = ['CHILD-404']
    if issue == 'cycle':
        raw['children'][0]['depends_on'] = ['CHILD-002']; raw['children'][1]['depends_on'] = ['CHILD-001']
    change = ChangeSpec.model_validate(raw)
    with pytest.raises(HarnessError):
        dependency_graph(change, {c.id: ['docs/'] for c in change.children})


def test_transitive_order_and_independent_child_readiness(tmp_path):
    _, change, _ = spec_fixture(tmp_path)
    raw = change.model_dump()
    for num in range(2, 5):
        child = copy.deepcopy(raw['children'][0]); child['id'] = f'CHILD-00{num}'
        child['depends_on'] = [f'CHILD-00{num-1}'] if num < 4 else []
        raw['children'].append(child)
    change = ChangeSpec.model_validate(raw)
    scopes = {c.id: ['docs/shared/'] if c.id != 'CHILD-004' else ['docs/separate.md'] for c in change.children}
    dag = dependency_graph(change, scopes)
    assert dag['ancestors']['CHILD-003'] == ['CHILD-001', 'CHILD-002']
    children = event(change).children
    assert child_summary(change, children, dag)['ready'] == ['CHILD-001', 'CHILD-004']
    children[-1] = children[-1].model_copy(update={'status': 'completed', 'evidence': event(change, 'archived', completed=True).children[0].evidence, 'review': event(change, 'archived', completed=True).children[0].review})
    assert child_summary(change, children, dag)['not_completed'] == ['CHILD-001', 'CHILD-002', 'CHILD-003']
    children[2] = children[2].model_copy(update={'status': 'in-progress'})
    with pytest.raises(HarnessError, match='dependencies'):
        child_summary(change, children, dag)


@pytest.mark.parametrize('field,value', [('change_id','CHANGE-OTHER'), ('change_revision',2), ('change_digest','d'*64), ('policy_digest','e'*64), ('previous_record_digest','f'*64), ('from_state','accepted'), ('recorded_at',datetime(2020,1,1,tzinfo=timezone.utc)), ('source', {'commit':'d'*40,'source_digest':'e'*64}), ('actor','human:impostor')])
def test_identity_chain_time_and_owner_fail_closed(tmp_path, field, value):
    _, change, _ = spec_fixture(tmp_path)
    previous = progression(change, 'awaiting-human-approval')
    current = event(change, 'approved-for-scoped-implementation', previous)
    raw = current.model_dump(); raw['transition'][field] = value
    with pytest.raises(HarnessError): checked(change, LifecycleEvent.model_validate(raw), previous)


@pytest.mark.parametrize('target', ['accepted', 'archived', 'in-progress', 'failed'])
def test_invalid_first_transition_rejected(tmp_path, target):
    _, change, _ = spec_fixture(tmp_path)
    with pytest.raises(HarnessError): checked(change, event(change, target, completed=True))


@pytest.mark.parametrize('terminal', ['cancelled', 'superseded', 'archived'])
def test_terminal_cannot_resume(tmp_path, terminal):
    _, change, _ = spec_fixture(tmp_path)
    previous = progression(change, 'archived' if terminal == 'archived' else 'in-progress')
    if terminal != 'archived':
        current = event(change, terminal, previous, operation='cancel' if terminal == 'cancelled' else 'supersede')
        if terminal == 'superseded': current = current.model_copy(update={'successor': event(change, 'archived').transition.evidence[0]})
        checked(change, current, previous); previous = current
    with pytest.raises(HarnessError): checked(change, event(change, 'in-progress', previous, operation='rework'), previous)


@pytest.mark.parametrize('status', ['pending', 'in-progress', 'failed', 'blocked', 'cancelled', 'superseded'])
def test_all_noncompleted_child_states_block_parent(tmp_path, status):
    _, change, _ = spec_fixture(tmp_path)
    previous = progression(change, 'validation-pending')
    current = event(change, 'independently-reviewed', previous, completed=True)
    current.children[0].status = status
    with pytest.raises(HarnessError): checked(change, current, previous)


@pytest.mark.parametrize('issue', ['missing', 'duplicate', 'unknown', 'revision', 'evidence', 'review'])
def test_child_inventory_and_references_required(tmp_path, issue):
    _, change, _ = spec_fixture(tmp_path)
    children = event(change, completed=True).children
    if issue == 'missing': children = []
    if issue == 'duplicate': children += [children[0]]
    if issue == 'unknown': children[0].id = 'CHILD-404'
    if issue == 'revision': children[0].revision = 2
    if issue in {'evidence', 'review'}: setattr(children[0], issue, None)
    with pytest.raises(HarnessError): child_summary(change, children, graph(change))


def test_rework_rejection_failure_and_rollback_are_explicit(tmp_path):
    _, change, _ = spec_fixture(tmp_path)
    planning = progression(change, 'awaiting-human-approval')
    checked(change, event(change, 'draft', planning, operation='reject'), planning)
    working = progression(change, 'in-progress')
    failure = event(change, 'failed', working, operation='fail'); failure.children[0].status = 'failed'
    checked(change, failure, working)
    with pytest.raises(HarnessError): checked(change, event(change, 'in-progress', failure), failure)
    rework = event(change, 'in-progress', failure, operation='rework')
    checked(change, rework, failure)
    accepted = progression(change)
    rollback = event(change, 'failed', accepted, operation='rollback', source={'commit':'d'*40,'source_digest':'e'*64})
    with pytest.raises(HarnessError): checked(change, rollback, accepted)
    rollback.rollback = accepted.children[0].evidence
    checked(change, rollback, accepted)


def test_source_freeze_and_archive_manifest(tmp_path):
    _, change, _ = spec_fixture(tmp_path)
    working = progression(change, 'in-progress')
    freeze = event(change, 'validation-pending', working, source={'commit':'d'*40,'source_digest':'e'*64}, completed=True)
    checked(change, freeze, working)
    accepted = progression(change)
    archive = event(change, 'archived', accepted, completed=True); archive.transition.evidence = []
    with pytest.raises(HarnessError): checked(change, archive, accepted)


def test_completed_children_cannot_silently_regress(tmp_path):
    _, change, _ = spec_fixture(tmp_path)
    previous = progression(change, 'validation-pending')
    fail = event(change, 'failed', previous, operation='fail')
    with pytest.raises(HarnessError, match='regress'): checked(change, fail, previous)


def persist(root, change, ev, location):
    name = f'.harness/changes/{change.id}/r{change.revision:04d}/{location}'
    write_json(root / name, ev.model_dump(mode='json'))
    return Path(name)


def test_cli_read_only_status_draft_and_gated_request(tmp_path, capsys):
    root, change, pin = spec_fixture(tmp_path)
    path = Path(f'docs/changes/{change.id}/r0001/change.json')
    before = snapshot(root)
    result = inspect_lifecycle(root, path, pin)
    assert result['recorded_state'] is None and result['authorization'] == 'not_granted'
    source = {'commit': before['commit'], 'source_digest': digest(before)}
    draft = event(change, source=source)
    request = persist(root, change, draft, 'requests/draft.json')
    assert inspect_lifecycle(root, path, pin, request)['transition_permitted'] is False
    persist(root, change, draft, 'events/000001.json')
    next_event = event(change, 'requirements-validated', draft)
    request = persist(root, change, next_event, 'requests/next.json')
    result = inspect_lifecycle(root, path, pin, request)
    assert result['status'] == 'blocked'
    assert 'gate:REFERENCES' in result['missing_prerequisites']
    assert 'native:verified-history-gates' in result['missing_prerequisites']
    files_before = {str(p.relative_to(root)): p.read_bytes() for p in (root / '.harness').rglob('*') if p.is_file()}
    assert main(['--root', str(root), 'change-check-transition', str(path), '--policy-sha256', pin, '--request', str(request)]) == 2
    assert 'requires-phase1c-integration' in capsys.readouterr().out
    assert main(['--root', str(root), 'change-status', str(path), '--policy-sha256', pin]) == 0
    assert snapshot(root) == before
    assert files_before == {str(p.relative_to(root)): p.read_bytes() for p in (root / '.harness').rglob('*') if p.is_file()}


@pytest.mark.parametrize('issue', ['gap', 'symlink', 'duplicate-json', 'oversize', 'unsafe-request', 'stale-source', 'wrong-revision', 'fake-approval', 'bad-reference', 'duplicate-event'])
def test_cli_rejects_malformed_operational_inputs(tmp_path, capsys, issue):
    root, change, pin = spec_fixture(tmp_path)
    path = Path('docs/changes/CHANGE-001/r0001/change.json')
    snap = snapshot(root); draft = event(change, source={'commit':snap['commit'],'source_digest':digest(snap)})
    request = persist(root, change, draft, 'requests/draft.json')
    if issue == 'gap': persist(root, change, draft, 'events/000002.json')
    if issue == 'symlink':
        target = root / request; target.unlink(); target.symlink_to(root / path)
    if issue == 'duplicate-json': (root / request).write_text('{"secret":"SENSITIVE_SENTINEL", "secret":2}')
    if issue == 'oversize': (root / request).write_bytes(b'x' * (1024*1024+1))
    if issue == 'unsafe-request': request = Path('../SENSITIVE_SENTINEL.json')
    if issue == 'stale-source':
        draft.transition.source.source_digest = SHA; persist(root, change, draft, 'requests/draft.json')
    if issue == 'wrong-revision': draft.transition.change_revision = 2; persist(root, change, draft, 'requests/draft.json')
    if issue == 'fake-approval':
        raw = draft.model_dump(mode='json'); raw['approved'] = True; write_json(root/request, raw)
    if issue == 'bad-reference': draft.transition.evidence.append(event(change,'archived').transition.evidence[0]); persist(root,change,draft,'requests/draft.json')
    if issue == 'duplicate-event': persist(root,change,draft,'events/000001.json')
    assert main(['--root',str(root),'change-check-transition',str(path),'--policy-sha256',pin,'--request',str(request)]) == 2
    assert 'SENSITIVE_SENTINEL' not in capsys.readouterr().out


def test_ignored_history_race_rejected(tmp_path, monkeypatch):
    import algooptionx_harness.lifecycle as module
    root, change, pin = spec_fixture(tmp_path)
    snap = snapshot(root); draft = event(change, source={'commit':snap['commit'],'source_digest':digest(snap)})
    request = persist(root, change, draft, 'requests/draft.json')
    original = module.check_event
    def mutate(*args, **kwargs):
        original(*args, **kwargs)
        (root/request).write_text('{}')
    monkeypatch.setattr(module,'check_event',mutate)
    with pytest.raises(HarnessError,match='Operational inputs changed'):
        inspect_lifecycle(root,Path('docs/changes/CHANGE-001/r0001/change.json'),pin,request)


def test_source_race_rejected(tmp_path, monkeypatch):
    import algooptionx_harness.lifecycle as module
    root, change, pin = spec_fixture(tmp_path)
    original = module.dependency_graph
    def mutate(*args, **kwargs):
        result = original(*args, **kwargs); (root/'unexpected.txt').write_text('drift'); return result
    monkeypatch.setattr(module,'dependency_graph',mutate)
    with pytest.raises(HarnessError,match='Source changed'):
        inspect_lifecycle(root,Path('docs/changes/CHANGE-001/r0001/change.json'),pin)


@pytest.mark.parametrize('field,value', [('actor_role','super-admin'),('operation','resume'),('schema_version',True)])
def test_wrapper_rejects_unknown_roles_operations_and_coercion(tmp_path, field, value):
    _, change, _ = spec_fixture(tmp_path)
    raw = event(change).model_dump(); raw[field] = value
    with pytest.raises(ValidationError): LifecycleEvent.model_validate(raw)


@pytest.mark.parametrize('state', PROGRESSION[:6])
def test_planning_failure_cannot_skip_implementation_prerequisites(tmp_path, state):
    _, change, _ = spec_fixture(tmp_path)
    previous = progression(change, state)
    with pytest.raises(HarnessError, match='Illegal lifecycle'):
        checked(change, event(change, 'failed', previous, operation='fail'), previous)


def test_started_child_reset_requires_explicit_rework(tmp_path):
    _, change, _ = spec_fixture(tmp_path)
    previous = progression(change, 'in-progress')
    previous.children[0].status = 'in-progress'
    with pytest.raises(HarnessError, match='Started children'):
        checked(change, event(change, 'validation-pending', previous), previous)
    failure = event(change, 'failed', previous, operation='fail')
    failure.children[0].status = 'failed'; checked(change, failure, previous)
    checked(change, event(change, 'in-progress', failure, operation='rework'), failure)


@pytest.mark.parametrize('binding', ['source', 'evidence', 'review'])
@pytest.mark.parametrize('operation', ['advance', 'rework'])
def test_completed_child_binding_changes_require_completion_invalidation(tmp_path, binding, operation):
    _, change, _ = spec_fixture(tmp_path)
    previous = progression(change, 'validation-pending')
    current = event(change, 'independently-reviewed' if operation == 'advance' else 'in-progress', previous, operation=operation, completed=True)
    raw = current.model_dump()
    if binding == 'source': raw['children'][0]['source']['source_digest'] = 'e' * 64
    else: raw['children'][0][binding]['sha256'] = 'f' * 64
    with pytest.raises(HarnessError, match='bindings'):
        checked(change, LifecycleEvent.model_validate(raw), previous)
    # Explicitly invalidating the old completion during rework is structurally valid.
    rework = event(change, 'in-progress', previous, operation='rework')
    checked(change, rework, previous)


@pytest.mark.parametrize('issue', ['per-child', 'total', 'duplicate'])
def test_dependency_scope_budgets_fail_closed_before_pairwise_scan(tmp_path, issue):
    _, change, _ = spec_fixture(tmp_path)
    raw = change.model_dump()
    if issue == 'total':
        for num in range(2, 7):
            child = copy.deepcopy(raw['children'][0]); child['id'] = f'CHILD-00{num}'
            raw['children'].append(child)
    change = ChangeSpec.model_validate(raw)
    paths = ['docs/repeated.md'] * 2 if issue == 'duplicate' else [f'docs/path-{i}.md' for i in range(201 if issue == 'per-child' else 200)]
    with pytest.raises(HarnessError, match='bounded|budget'):
        dependency_graph(change, {c.id: paths for c in change.children})

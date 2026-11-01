"""Native UI gates: synthetic consistency fixtures are never approval provenance."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from algooptionx_harness.changes import ChangeSpec, StoredReference
from algooptionx_harness.designs import DesignError, validate_design
from algooptionx_harness.enforcement import Inputs, ChatPair, _ui_design
from algooptionx_harness.workspace import HarnessError
from tests.control_plane.test_design_contracts import make_design


def run_gate(f, *, native=True):
    binding = f['binding']
    inputs = Inputs(f['root'])
    native_run = SimpleNamespace(
        ui_evidence=StoredReference(**f['evidence_ref']),
        evidence=StoredReference(**f['evidence']['native_evidence_reference']),
        approvals=SimpleNamespace(chat=[ChatPair(request=binding['approvals'][0]['request'], decision=binding['approvals'][0]['decision'])], signed=[]),
    ) if native else None
    _ui_design(inputs, ChangeSpec.model_validate(f['change']), {'policy_sha256': f['policy_pin']},
               f['task'], StoredReference(**binding['native_task_reference']),
               StoredReference(**binding['baseline_reference']), StoredReference(**f['binding_ref']),
               native=native_run, candidate=f['baseline'] if native else None)
    inputs.finish()


def test_ui_dispatch_and_closure_compose_existing_design_records(tmp_path):
    f = make_design(tmp_path)
    run_gate(f, native=False)
    from tests.control_plane.test_ui_execution import executed_report
    from algooptionx_harness.ui_execution import browser_cases
    from algooptionx_harness.designs import DesignBinding
    import json
    native = executed_report(f['root'], {'task': f['binding']['native_task_reference'], 'evidence': f['evidence']['native_evidence_reference']}, f['spec'])
    f['evidence']['native_evidence_reference'] = native['evidence']
    f['evidence']['executed_cases'] = browser_cases(Inputs(f['root']), f['task'], StoredReference(**native['evidence']), DesignBinding.model_validate_json(json.dumps(f['binding'])).design)
    f['evidence_ref'] = f['put']('.harness/ui-evidence.json',f['evidence'])
    run_gate(f)


@pytest.mark.parametrize('status', ['failed', 'skipped', 'missing', 'unverified'])
def test_ui_closure_rejects_each_nonpassing_case(tmp_path, status):
    f = make_design(tmp_path)
    # Retain a structurally valid nonpassing record: contract validity alone
    # must never promote this declaration into readiness.
    case = f['evidence']['executed_cases'][0]
    case['status'] = status
    for area in case['results']:
        area['status'] = status
        area['measurements'] = []
    f['evidence_ref'] = f['put']('.harness/ui-evidence.json', f['evidence'])
    with pytest.raises((HarnessError, DesignError)):
        run_gate(f)


def test_ui_closure_rejects_omitted_cases(tmp_path):
    f = make_design(tmp_path)
    f['evidence']['executed_cases'] = []
    f['evidence_ref'] = f['put']('.harness/ui-evidence.json', f['evidence'])
    with pytest.raises(HarnessError, match='incomplete or nonpassing'):
        run_gate(f)


@pytest.mark.parametrize('mutation', ['no-approval', 'wrong-source', 'wrong-task', 'wrong-native-evidence'])
def test_ui_bindings_fail_closed(tmp_path, mutation):
    f = make_design(tmp_path)
    if mutation == 'no-approval':
        f['binding']['approvals'] = []
        # Avoid fixture helper's approval extraction; exercise dispatch directly.
        f['binding_ref'] = f['put']('.harness/binding.json', f['binding'])
        with pytest.raises(HarnessError, match='exactly one'):
            _ui_design(Inputs(f['root']), ChangeSpec.model_validate(f['change']),
                       {'policy_sha256': f['policy_pin']}, f['task'],
                       StoredReference(**f['binding']['native_task_reference']),
                       StoredReference(**f['binding']['baseline_reference']),
                       StoredReference(**f['binding_ref']))
        return
    if mutation == 'wrong-source':
        f['binding']['source']['source_digest'] = 'f' * 64
    elif mutation == 'wrong-task':
        f['binding']['native_task_digest'] = 'f' * 64
    else:
        f['evidence']['native_evidence_reference'] = f['put']('.harness/other-evidence.json', {'not': 'native evidence'})
        f['evidence_ref'] = f['put']('.harness/ui-evidence.json', f['evidence'])
    f['binding_ref'] = f['put']('.harness/binding.json', f['binding'])
    with pytest.raises((HarnessError, DesignError, ValueError)):
        run_gate(f)


def test_ui_dispatch_rejects_absent_binding(tmp_path):
    f = make_design(tmp_path)
    with pytest.raises(HarnessError, match='requires a frozen design'):
        _ui_design(Inputs(f['root']), ChangeSpec.model_validate(f['change']),
                   {'policy_sha256': f['policy_pin']}, f['task'],
                   StoredReference(**f['binding']['native_task_reference']),
                   StoredReference(**f['binding']['baseline_reference']), None)


def test_aggregate_design_binding_has_exact_parent_scope(tmp_path):
    f = make_design(tmp_path)
    task = f['task'].model_copy(update={'id': 'CHANGE-001-AGGREGATE'})
    f['binding']['native_task_reference'] = f['put']('.harness/aggregate/task.json', task)
    f['binding']['baseline_reference'] = f['put']('.harness/aggregate/baseline.json', f['baseline'])
    from algooptionx_harness.workspace import digest
    f['binding']['native_task_digest'] = digest(task)
    f['binding']['approvals'] = []
    ref = f['put']('.harness/aggregate-binding.json', f['binding'])
    assert validate_design(f['root'], Path(ref['path']), f['policy_pin'])['status'] == 'DESIGN CONTRACT VALID'
    # Aggregate identity cannot be used to smuggle a smaller write scope.
    task = task.model_copy(update={'allowed_paths': ['docs/narrow.md']})
    f['binding']['native_task_reference'] = f['put']('.harness/aggregate/task.json', task)
    f['binding']['native_task_digest'] = digest(task)
    ref = f['put']('.harness/aggregate-binding.json', f['binding'])
    with pytest.raises(DesignError):
        validate_design(f['root'], Path(ref['path']), f['policy_pin'])


def test_native_dispatch_blocks_ui_writer_but_allows_readonly_design_review(tmp_path):
    from tests.control_plane.test_change_contracts import make_change, save_change
    from algooptionx_harness.enforcement import capture_child, dispatch_child
    from algooptionx_harness.impact import select_checks
    root, change, pin, template = make_change(tmp_path)
    template['ui_changes'] = True
    template['allowed_paths'] = ['apps/web/src/fixture.tsx']
    change['allowed_paths'] = template['allowed_paths']
    change['affected_components'] = ['WEB']
    template['checks'] = select_checks(template['allowed_paths'])['checks']
    change['approvals']['stages'].insert(2, 'ui')
    change['children'][0]['roles'].append('ui-designer')
    path = save_change(root, change, template)
    capture_child(root, path, pin, 'CHILD-001')
    with pytest.raises(HarnessError, match='requires a frozen design'):
        dispatch_child(root, path, pin, 'CHILD-001', 'backend-engineer')
    result = dispatch_child(root, path, pin, 'CHILD-001', 'ui-designer')
    assert result['change_binding']['authorization'] == 'not_granted'


def ui_bundle(tmp_path):
    """Full native chain with synthetic records; not executed UI provenance."""
    from datetime import timedelta
    from algooptionx_harness import chat
    from algooptionx_harness.changes import IntentBinding, CapturedBinding
    from algooptionx_harness.impact import select_checks
    from algooptionx_harness.models import Task, ChatRequest
    from algooptionx_harness.governance import validate_change
    from algooptionx_harness.workspace import digest, snapshot, file_digest
    from tests.control_plane.test_change_contracts import save_change
    from tests.control_plane.test_change_enforcement import native_fixture
    f = make_design(tmp_path)
    root, raw, template = f['root'], f['change'], f['template']
    template['allowed_paths'] = ['apps/web/src/fixture.tsx']
    raw['allowed_paths'] = template['allowed_paths']
    raw['affected_components'] = ['WEB']
    template['checks'] = select_checks(template['allowed_paths'])['checks']
    path = save_change(root, raw, template)
    baseline = snapshot(root)
    task = Task.model_validate({**template, 'source_commit': baseline['commit'], 'baseline_digest': digest(baseline)})
    obligations = validate_change(root, path, f['policy_pin'])
    base = {'schema_version': 1, 'change_id': raw['id'], 'change_revision': 1, 'change_digest': digest(raw),
            'policy_digest': f['policy_pin'], 'source': {'commit': baseline['commit'], 'source_digest': digest(baseline)}}
    intent = IntentBinding(**base, kind='intent', child_id='CHILD-001', child_revision=1,
        template_digest=raw['children'][0]['task_template']['sha256'],
        role_skill_digests=obligations['role_skill_digests'], purpose='local-development')
    captured = CapturedBinding(**base, kind='captured', intent_digest=digest(intent),
                              native_task_digest=digest(task), baseline_digest=digest(baseline))
    def native_ui(native_task, label):
        native = native_fixture(root, native_task, baseline, baseline, label, obligations['required_gates'])
        # Insert a UI approval chronologically between architecture and implementation.
        architecture = ChatRequest.model_validate_json((root/native['approvals']['chat'][1]['request']['path']).read_text())
        request = chat.request(native_task, 'ui', native_task.baseline_digest)
        request = request.model_copy(update={'requested_at': architecture.requested_at + timedelta(seconds=1.2)})
        decision = chat.record(request, 'approved', 'operator:synthetic-test')
        decision = decision.model_copy(update={'recorded_at': request.requested_at + timedelta(seconds=.1)})
        pair = {'request': f['put'](f'.harness/{label}-ui-request.json', request),
                'decision': f['put'](f'.harness/{label}-ui-decision.json', decision)}
        native['approvals']['chat'].insert(2, pair)
        from tests.control_plane.test_ui_execution import executed_report
        native = executed_report(root, native, f['spec'])
        binding = {**base, 'kind': 'design-binding', 'design': f['binding']['design'],
            'policy': raw['policy'], 'change_reference': {'path': str(path.relative_to(root)), 'sha256': file_digest(path)},
            'native_task_reference': native['task'], 'native_task_digest': digest(native_task),
            'baseline_reference': native['baseline'], 'baseline_digest': digest(baseline),
            'approvals': [{'id': 'UI-APPROVAL', 'mode': 'operator-recorded-chat', **pair}]}
        native['design_binding'] = f['put'](f'.harness/{label}-binding.json', binding)
        evidence = {**f['evidence'], **base, 'native_task_reference': native['task'],
            'native_task_digest': digest(native_task), 'native_evidence_reference': native['evidence']}
        from algooptionx_harness.ui_execution import browser_cases
        from algooptionx_harness.designs import DesignBinding
        import json
        evidence['executed_cases'] = browser_cases(Inputs(root), native_task, StoredReference(**native['evidence']), DesignBinding.model_validate_json(json.dumps(binding)).design)
        native['ui_evidence'] = f['put'](f'.harness/{label}-ui-evidence.json', evidence)
        return native
    child = {**base, 'child_id': 'CHILD-001', 'child_revision': 1,
             'intent': f['put']('.harness/ui-intent.json', intent),
             'captured': f['put']('.harness/ui-captured.json', captured), 'native': native_ui(task, 'ui-child')}
    aggregate = task.model_copy(update={'id': 'CHANGE-001-AGGREGATE'})
    bundle = {**base, 'children': [child], 'aggregate': native_ui(aggregate, 'ui-aggregate'),
              'rollback_reference': f['put']('.harness/ui-rollback.json', {'instructions': 'Reverse scoped fixture only.'})}
    bundle_ref = f['put']('.harness/full-ui-bundle.json', bundle)
    return f, path, bundle, root/bundle_ref['path']


def test_actual_ui_bundle_verification_and_closure(tmp_path):
    from algooptionx_harness.enforcement import verify_bundle, close_change
    f, path, bundle, bundle_path = ui_bundle(tmp_path)
    result = verify_bundle(f['root'], path, f['policy_pin'], bundle_path)
    assert result['status'] == 'verified_local_acceptance'
    assert result['grants_deployment'] is False
    accepted = close_change(f['root'], path, f['policy_pin'], bundle_path)
    assert Path(accepted['closure_path'], 'acceptance.json').is_file()


@pytest.mark.parametrize('location,field', [
    ('child', 'design_binding'), ('child', 'ui_evidence'),
    ('aggregate', 'design_binding'), ('aggregate', 'ui_evidence'),
])
def test_actual_ui_bundle_rejects_missing_records(tmp_path, location, field):
    from algooptionx_harness.enforcement import verify_bundle
    f, path, bundle, bundle_path = ui_bundle(tmp_path)
    run = bundle['children'][0]['native'] if location == 'child' else bundle['aggregate']
    run.pop(field)
    f['put'](str(bundle_path.relative_to(f['root'])), bundle)
    with pytest.raises(HarnessError):
        verify_bundle(f['root'], path, f['policy_pin'], bundle_path)


def test_absent_ui_fields_preserve_legacy_native_run_digest(tmp_path):
    from algooptionx_harness.enforcement import NativeRun
    from algooptionx_harness.workspace import digest
    from tests.control_plane.test_change_enforcement import fixture
    root, path, pin, bundle, bundle_path = fixture(tmp_path)
    legacy = bundle['aggregate']
    assert digest(NativeRun.model_validate(legacy)) == digest({'schema_version': 1, **legacy, 'approvals': {'schema_version': 1, **legacy['approvals'], 'chat': [{'schema_version': 1, **pair} for pair in legacy['approvals']['chat']], 'signed': []}})


def test_nested_ui_artifact_change_is_detected_at_final_boundary(tmp_path):
    from tests.control_plane.test_ui_execution import fixture, derive
    f = fixture(tmp_path)
    f['evidence']['executed_cases'] = derive(f)
    f['evidence_ref'] = f['put']('.harness/ui-evidence.json', f['evidence'])
    inputs = Inputs(f['root'])
    binding = f['binding']
    native = SimpleNamespace(ui_evidence=StoredReference(**f['evidence_ref']),
        evidence=StoredReference(**f['evidence']['native_evidence_reference']),
        approvals=SimpleNamespace(chat=[ChatPair(request=binding['approvals'][0]['request'], decision=binding['approvals'][0]['decision'])], signed=[]))
    _ui_design(inputs, ChangeSpec.model_validate(f['change']), {'policy_sha256': f['policy_pin']},
        f['task'], StoredReference(**binding['native_task_reference']),
        StoredReference(**binding['baseline_reference']), StoredReference(**f['binding_ref']),
        native=native, candidate=f['baseline'])
    (f['root']/'.harness/run/ui/CASE-001/screenshot.png').write_bytes(b'tampered after first verification')
    with pytest.raises((DesignError, HarnessError)):
        inputs.finish()

"""Phase 1A contracts are strict data, never execution/approval authority."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from pydantic import ValidationError

from algooptionx_harness.changes import (
    ChangeSpec, GovernancePolicy, ChangeRecord, RollbackObligation, RiskProfile,
)
from algooptionx_harness.cli import main
from algooptionx_harness.models import Task

ROOT = Path(__file__).resolve().parents[2]
SHA = 'a' * 64


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_change(tmp_path):
    root = tmp_path / 'checkout'
    root.mkdir()
    (root / '.gitignore').write_text('.harness/\n__pycache__/\n.pytest_cache/\n')
    folder = root / 'docs/changes/CHANGE-001/r0001'
    folder.mkdir(parents=True)
    refs = {}
    for name, text in [('proposal', '# Bounded documentation proposal'), ('design', '# Design and recovery boundaries'), ('requirements', '# REQ-001\nAn inspectable documented outcome')]:
        p = folder / f'{name}.md'
        p.write_text(text + '\n')
        refs[name] = {'path': str(p.relative_to(root)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
    policy_path = root / 'config/engineering-governance.json'
    policy = json.loads((ROOT / 'config/engineering-governance.json').read_text())
    pin = write_json(policy_path, policy)
    template_path = folder / 'tasks/CHILD-001.template.json'
    protected = [str((folder / 'change.json').relative_to(root)), 'config/engineering-governance.json', *(r['path'] for r in refs.values()), str(template_path.relative_to(root))]
    template = {'schema_version': 1, 'id': 'CHILD-001', 'title': 'Scoped documentation contract fixture', 'implementer': 'agent:fixture', 'requirement_ids': ['REQ-001'], 'allowed_paths': ['docs/guide.md'], 'protected_inputs': protected, 'ui_changes': False,
                'checks': [{'id': 'python', 'kind': 'pytest', 'argv': [sys.executable, '-m', 'pytest'], 'report': '{run_dir}/pytest.xml'}, {'id': 'config', 'kind': 'command', 'argv': [sys.executable, '-m', 'algooptionx_harness.cli', 'validate-config']}],
                'acceptance': ['A bounded documented outcome is reviewed.'], 'rollback': 'Reverse only fixture changes and preserve all evidence.'}
    template_pin = write_json(template_path, template)
    change = {'schema_version': 1, 'id': 'CHANGE-001', 'revision': 1, 'title': 'Inspect bounded documentation change', 'owner': 'human:owner', 'purpose': 'local-development', 'proposal': refs['proposal'], 'design': refs['design'],
              'requirements': [{'id': 'REQ-001', **refs['requirements']}], 'acceptance': [{'id': 'ACC-001', 'requirement_id': 'REQ-001', 'predicate': 'The documented outcome is independently reviewed.', 'negative_case': 'Missing review blocks acceptance.', 'evidence_kind': 'review'}],
              'requested_risk': 'R0', 'allowed_paths': ['docs/guide.md'], 'affected_components': ['DOCUMENTATION'],
              'children': [{'id': 'CHILD-001', 'revision': 1, 'depends_on': [], 'requirement_ids': ['REQ-001'], 'task_template': {'path': str(template_path.relative_to(root)), 'sha256': template_pin}, 'roles': ['backend-engineer'], 'skills': ['implementation']}],
              'policy': {'id': policy['id'], 'revision': policy['revision'], 'sha256': pin}, 'approvals': {'mode': 'operator-recorded-chat', 'assurance': 'procedural', 'stages': ['plan', 'architecture', 'implementation', 'qa']},
              'independent_review_required': True, 'rollback': {'instructions': 'Reverse only approved patches while preserving history.', 'preserve_history': True, 'data_impact': 'none'}, 'archive_required': True}
    write_json(folder / 'change.json', change)
    shutil.copytree(ROOT / 'src/algooptionx_harness/agents', root / 'src/algooptionx_harness/agents')
    shutil.copytree(ROOT / '.agents/skills', root / '.agents/skills')
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Contract Fixture', '-c', 'user.email=fixture@invalid', 'commit', '-qm', 'fixture'], check=True)
    return root, change, pin, template


def save_change(root, change, template=None):
    if template is not None:
        ref = change['children'][0]['task_template']
        ref['sha256'] = write_json(root / ref['path'], template)
    path = root / 'docs/changes/CHANGE-001/r0001/change.json'
    write_json(path, change)
    return path


def test_valid_change_and_policy_contracts(tmp_path):
    root, change, pin, template = make_change(tmp_path)
    assert ChangeSpec.model_validate(change).policy.sha256 == pin
    policy = GovernancePolicy.model_validate_json((root / 'config/engineering-governance.json').read_text())
    assert set(policy.profiles) == {'R0', 'R1', 'R2', 'R3'}
    # Native v1 still validates independently; no model/signature migration.
    native = Task.model_validate({**template, 'source_commit': 'b' * 40, 'baseline_digest': SHA})
    assert native.schema_version == 1


@pytest.mark.parametrize('mutation', ['extra-authority', 'missing-owner', 'bool-version', 'future-version', 'bool-revision', 'no-review', 'duplicate-child', 'missing-coverage', 'acceptance-coverage', 'unsafe-scope', 'fake-role', 'unsigned-automation'])
def test_invalid_change_contracts_rejected(tmp_path, mutation):
    _, change, _, _ = make_change(tmp_path)
    if mutation == 'extra-authority': change['approved'] = True
    elif mutation == 'missing-owner': del change['owner']
    elif mutation == 'bool-version': change['schema_version'] = True
    elif mutation == 'future-version': change['schema_version'] = 2
    elif mutation == 'bool-revision': change['revision'] = True
    elif mutation == 'no-review': change['independent_review_required'] = False
    elif mutation == 'duplicate-child': change['children'].append(copy.deepcopy(change['children'][0]))
    elif mutation == 'missing-coverage': change['children'][0]['requirement_ids'] = ['REQ-OTHER']
    elif mutation == 'acceptance-coverage': change['acceptance'][0]['requirement_id'] = 'REQ-OTHER'
    elif mutation == 'unsafe-scope': change['allowed_paths'] = ['docs/../.env']
    elif mutation == 'fake-role': change['children'][0]['roles'] = ['super-admin']
    elif mutation == 'unsigned-automation': change['purpose'] = 'deployment'
    with pytest.raises((ValidationError, ValueError)):
        ChangeSpec.model_validate(change)


@pytest.mark.parametrize('mutation', ['profile-absent', 'gate-absent', 'duplicate-rule', 'lower-obligations', 'approval-absent', 'second-authority', 'unknown-allowed'])
def test_invalid_policy_contracts_rejected(mutation):
    policy = json.loads((ROOT / 'config/engineering-governance.json').read_text())
    if mutation == 'profile-absent': del policy['profiles']['R3']
    elif mutation == 'gate-absent': policy['gates'] = [g for g in policy['gates'] if g['id'] != 'PYTHON']
    elif mutation == 'duplicate-rule': policy['path_rules'].append(copy.deepcopy(policy['path_rules'][0]))
    elif mutation == 'lower-obligations': policy['profiles']['R3']['gates'].remove('SECURITY')
    elif mutation == 'approval-absent': policy['profiles']['R0']['approval_stages'].remove('implementation')
    elif mutation == 'second-authority': policy['signer_authority'] = 'repository-owner-agent'
    elif mutation == 'unknown-allowed': policy['unknown_scope'] = 'allow'
    with pytest.raises(ValidationError): GovernancePolicy.model_validate(policy)


def record_base(kind):
    return {'schema_version': 1, 'kind': kind, 'change_id': 'CHANGE-001', 'change_revision': 1, 'change_digest': SHA, 'policy_digest': SHA, 'source': {'commit': 'b' * 40, 'source_digest': SHA}}


def test_record_union_strictness_and_no_approval_authority():
    ref = {'path': '.harness/runs/fixture/evidence.json', 'sha256': SHA}
    record = {**record_base('acceptance'), 'aggregate_task_digest': SHA, 'aggregate_evidence': ref, 'review': ref, 'human_decision': ref, 'approval_mode': 'operator-recorded-chat', 'grants_deployment': False}
    assert ChangeRecord.model_validate(record).root.grants_deployment is False
    with pytest.raises(ValidationError): ChangeRecord.model_validate({**record, 'grants_deployment': True})
    with pytest.raises(ValidationError): ChangeRecord.model_validate({**record, 'kind': 'self-authorized'})
    with pytest.raises(ValidationError): ChangeRecord.model_validate({**record, 'schema_version': True})


def test_review_actor_and_blocking_findings_are_not_accepted():
    record = {**record_base('review'), 'actor': 'agent:reviewer', 'implementer_contexts': ['agent:writer'], 'status': 'completed', 'reproduced_checks': [], 'findings': [], 'limitations': ['Local context identity is not externally attested.'], 'provenance': 'declared-separate-context', 'attestation': None}
    assert ChangeRecord.model_validate(record).root.status == 'completed'
    for update in [{'actor': 'agent:writer'}, {'provenance': 'externally-attested'}, {'findings': [{'severity': 'high', 'description': 'Unresolved security defect.'}]}]:
        with pytest.raises(ValidationError): ChangeRecord.model_validate({**record, **update})


def test_transition_timestamps_and_archive_references_are_required():
    event = {**record_base('transition'), 'event_id': 'event-0001', 'previous_record_digest': None, 'from_state': None, 'to_state': 'draft', 'actor': 'human:owner', 'recorded_at': '2026-10-31T10:00:00Z', 'reason': 'Initial contract preparation', 'evidence': []}
    assert ChangeRecord.model_validate_json(json.dumps(event)).root.to_state == 'draft'
    with pytest.raises(ValidationError): ChangeRecord.model_validate_json(json.dumps({**event, 'recorded_at': '2026-10-31T10:00:00'}))
    with pytest.raises(ValidationError): ChangeRecord.model_validate(record_base('archive'))


def test_schema_generation_is_additive_and_legacy_outputs_untouched(tmp_path, capsys):
    names = ['task', 'handoff', 'approval', 'trust-policy', 'evidence', 'agent', 'chat-request', 'chat-decision']
    folder = tmp_path / 'src/algooptionx_harness/schemas'
    folder.mkdir(parents=True)
    for name in names: shutil.copyfile(ROOT / 'src/algooptionx_harness/schemas' / f'{name}.schema.json', folder / f'{name}.schema.json')
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in folder.iterdir()}
    assert main(['--root', str(tmp_path), 'schemas']) == 0
    assert json.loads(capsys.readouterr().out)['schemas'] == 11
    assert before == {name: ((folder / name).read_bytes(), (folder / name).stat().st_mtime_ns) for name in before}
    for name, model in [('change', ChangeSpec), ('governance-policy', GovernancePolicy), ('change-record', ChangeRecord)]:
        assert json.loads((folder / f'{name}.schema.json').read_text()) == model.model_json_schema()
        assert json.loads((ROOT / 'src/algooptionx_harness/schemas' / f'{name}.schema.json').read_text()) == model.model_json_schema()


@pytest.mark.parametrize('value', [0, 1, 'true', 'false'])
def test_governance_flags_reject_coerced_booleans(tmp_path, value):
    _, change, _, _ = make_change(tmp_path)
    for field in ['independent_review_required', 'archive_required']:
        with pytest.raises(ValidationError): ChangeSpec.model_validate({**change, field: value})
    with pytest.raises(ValidationError):
        RollbackObligation.model_validate({**change['rollback'], 'preserve_history': value})
    policy = GovernancePolicy.model_validate_json((ROOT / 'config/engineering-governance.json').read_text())
    profile = policy.profiles['R0'].model_dump()
    with pytest.raises(ValidationError):
        RiskProfile.model_validate({**profile, 'independent_review_required': value})
    ref = {'path': '.harness/fixture.json', 'sha256': SHA}
    record = {**record_base('acceptance'), 'aggregate_task_digest': SHA, 'aggregate_evidence': ref, 'review': ref, 'human_decision': ref, 'approval_mode': 'operator-recorded-chat', 'grants_deployment': value}
    with pytest.raises(ValidationError): ChangeRecord.model_validate(record)


def test_all_record_variants_roundtrip_without_claiming_execution():
    ref = {'path': '.harness/fixture.json', 'sha256': SHA}
    payloads = {
        'intent': {'child_id': 'CHILD-001', 'child_revision': 1, 'template_digest': SHA, 'role_skill_digests': {'role:product': SHA}, 'purpose': 'local-development'},
        'captured': {'intent_digest': SHA, 'native_task_digest': SHA, 'baseline_digest': SHA},
        'evidence': {'captured_binding_digest': SHA, 'native_task_digest': SHA, 'native_evidence': ref, 'candidate_snapshot': ref, 'required_gates': ['PYTHON'], 'environment_report': ref, 'reviewer': ref, 'approval': ref, 'rollback_reference': ref},
        'archive': {'acceptance': ref, 'child_evidence': [ref], 'rollback_reference': ref, 'artifacts': [ref]},
        'knowledge': {'finding': 'A bounded source responsibility was inspected.', 'classification': 'VERIFIED', 'owner': 'role:architect', 'evidence': [ref], 'freshness_conditions': ['Source unchanged'], 'invalidation_conditions': ['Relevant source changed']},
    }
    for kind, fields in payloads.items():
        original = ChangeRecord.model_validate({**record_base(kind), **fields})
        assert ChangeRecord.model_validate_json(original.model_dump_json()) == original

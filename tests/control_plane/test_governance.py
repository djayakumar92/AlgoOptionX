"""Read-only verification rejects stale/unsafe contracts without executing them."""
from __future__ import annotations

import copy
import hashlib
import json

import pytest
from pydantic import ValidationError

from algooptionx_harness import governance
from algooptionx_harness.changes import GovernancePolicy
from algooptionx_harness.cli import main
from algooptionx_harness.workspace import HarnessError, digest, snapshot
from tests.control_plane.test_change_contracts import make_change, save_change, write_json


def test_valid_checker_is_read_only_and_conveys_no_authority(tmp_path, capsys, monkeypatch):
    root, change, pin, _ = make_change(tmp_path)
    before = digest(snapshot(root))
    # Any attempt to execute a subprocess after fixture capture is a defect.
    # The checker legitimately invokes read-only git through snapshot, so guard
    # execution entry points rather than confusing inspection with test runs.
    import algooptionx_harness.runner as runner
    monkeypatch.setattr(runner, 'run_task', lambda *a, **k: pytest.fail('Validation must not execute tasks'))
    assert main(['--root', str(root), 'change-validate', str(root / 'docs/changes/CHANGE-001/r0001/change.json'), '--policy-sha256', pin]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'verified_contracts'
    assert result['effective_risk'] == 'R0'
    assert {'PYTHON', 'CONFIG', 'INDEPENDENT-REVIEW', 'EVIDENCE'} <= set(result['required_gates'])
    assert result['authorization'] == 'not_granted'
    assert result['human_approval_verified'] is False
    assert result['dependency_dag_verified'] is False
    assert result['lifecycle_transitions_verified'] is False
    assert result['execution_readiness'] == 'not_implemented'
    assert result['external_controls'] == 'not_verified'
    assert result['policy_assurance'] == 'caller-pinned-not-authenticated'
    assert result['deployment_performed'] is False
    assert digest(snapshot(root)) == before
    assert not (root / '.harness').exists()


@pytest.mark.parametrize('scope,components,risk,gates', [
    ('src/algooptionx/paper/engine.py', ['APPLICATION', 'FINANCE'], 'R2', {'FINANCIAL', 'SECURITY'}),
    ('src/algooptionx/market/', ['APPLICATION', 'MARKET'], 'R2', {'CAUSAL-DATA'}),
    ('src/algooptionx_harness/runner.py', ['GOVERNANCE'], 'R3', {'GOVERNANCE'}),
    ('docs/', ['DOCUMENTATION', 'GOVERNANCE'], 'R3', {'GOVERNANCE'}),
    ('apps/web/', ['WEB', 'DEPENDENCIES'], 'R3', {'GOVERNANCE', 'BROWSER'}),
])
def test_risk_floor_and_sensitive_descendants_cannot_be_hidden(tmp_path, scope, components, risk, gates):
    root, _, pin, _ = make_change(tmp_path)
    policy = governance.load_governance_policy(root, pin)
    result = governance.resolve_obligations(policy, 'R0', [scope], components)
    assert result['effective_risk'] == risk
    assert gates <= set(result['required_gates'])


@pytest.mark.parametrize('scope,components', [('unknown/component.py', ['UNKNOWN']), ('src/', ['APPLICATION']), ('docs/guide.md', ['GOVERNANCE']), ('.env', ['APPLICATION']), ('.git/config', ['GOVERNANCE'])])
def test_unknown_or_unsafe_scope_fails_closed(tmp_path, scope, components):
    root, _, pin, _ = make_change(tmp_path)
    with pytest.raises((HarnessError, ValueError)):
        governance.resolve_obligations(governance.load_governance_policy(root, pin), 'R0', [scope], components)


def test_policy_change_does_not_silently_update_reviewed_pin(tmp_path):
    root, change, pin, _ = make_change(tmp_path)
    policy_path = root / 'config/engineering-governance.json'
    policy = json.loads(policy_path.read_text())
    policy['path_rules'][0]['minimum_risk'] = 'R1'
    write_json(policy_path, policy)
    with pytest.raises(HarnessError, match='policy changed'):
        governance.validate_change(root, root / 'docs/changes/CHANGE-001/r0001/change.json', pin)
    # Even a newly supplied valid pin remains caller-pinned, not adopted authority.
    new_pin = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    change['policy']['sha256'] = new_pin
    path = save_change(root, change)
    result = governance.validate_change(root, path, new_pin)
    assert result['policy_assurance'] == 'caller-pinned-not-authenticated'
    assert result['human_approval_verified'] is False


@pytest.mark.parametrize('attack', ['wrong-policy', 'missing-stages', 'child-scope', 'unprotected-input', 'captured-authority', 'no-python', 'stale-document', 'stale-template', 'missing-role', 'missing-skill', 'wrong-child-id', 'wrong-template-location'])
def test_invalid_change_bindings_are_rejected(tmp_path, attack):
    root, change, pin, template = make_change(tmp_path)
    if attack == 'wrong-policy': change['policy']['revision'] = 2
    elif attack == 'missing-stages': change['approvals']['stages'] = ['implementation', 'qa']
    elif attack == 'child-scope': template['allowed_paths'] = ['src/algooptionx/paper/']
    elif attack == 'unprotected-input': template['protected_inputs'].remove('config/engineering-governance.json')
    elif attack == 'captured-authority': template['source_commit'] = 'a' * 40
    elif attack == 'no-python': template['checks'] = [template['checks'][1]]
    elif attack == 'stale-document': (root / change['design']['path']).write_text('changed design')
    elif attack == 'stale-template': change['children'][0]['task_template']['sha256'] = 'a' * 64
    elif attack == 'missing-role': (root / 'src/algooptionx_harness/agents/backend-engineer.json').unlink()
    elif attack == 'missing-skill': change['children'][0]['skills'] = ['nonexistent-skill']
    elif attack == 'wrong-child-id': template['id'] = 'OTHER-001'
    elif attack == 'wrong-template-location': change['children'][0]['task_template']['path'] = 'docs/changes/OTHER/r0001/tasks/CHILD-001.template.json'
    path = save_change(root, change, template if attack in {'child-scope', 'unprotected-input', 'captured-authority', 'no-python', 'wrong-child-id'} else None)
    with pytest.raises((HarnessError, ValidationError, OSError)):
        governance.validate_change(root, path, pin)


def test_ui_scope_cannot_omit_native_browser_or_ui_approval(tmp_path):
    root, change, pin, template = make_change(tmp_path)
    change['allowed_paths'] = template['allowed_paths'] = ['apps/web/src/features/workspace/components/ActivityPanel.tsx']
    change['affected_components'] = ['WEB']
    path = save_change(root, change, template)
    with pytest.raises(ValidationError): governance.validate_change(root, path, pin)
    template['ui_changes'] = True
    template['checks'].append({'id': 'browser', 'kind': 'playwright', 'argv': ['npm', 'run', 'test:e2e'], 'report': '{run_dir}/browser/playwright.json'})
    path = save_change(root, change, template)
    with pytest.raises(HarnessError, match='approval requirements'): governance.validate_change(root, path, pin)
    change['approvals']['stages'].append('ui')
    path = save_change(root, change)
    result = governance.validate_change(root, path, pin)
    assert {'TYPE-BUILD', 'LINT', 'BROWSER'} <= set(result['required_gates'])
    assert 'ui' in result['required_approval_stages']


@pytest.mark.parametrize('attack', ['duplicate-json', 'oversize', 'symlink', 'traversal', 'bad-pin', 'deep-json', 'requirement-path'])
def test_cli_rejects_unsafe_inputs_without_echoing_payloads(tmp_path, capsys, attack):
    root, change, pin, _ = make_change(tmp_path)
    path = root / 'docs/changes/CHANGE-001/r0001/change.json'
    marker = 'PRIVATE_SYNTHETIC_INPUT_VALUE'
    if attack == 'duplicate-json': path.write_text('{"owner":"' + marker + '","owner":"second"}')
    elif attack == 'oversize': path.write_text(marker * 100000)
    elif attack == 'symlink':
        target = tmp_path / 'external.json'
        target.write_text(marker)
        path.unlink()
        path.symlink_to(target)
    elif attack == 'traversal': path = root / 'docs/changes/../outside/change.json'
    elif attack == 'bad-pin': pin = marker
    elif attack == 'deep-json': path.write_text('[' * 10000 + '0' + ']' * 10000)
    elif attack == 'requirement-path':
        change['requirements'][0]['path'] = 'docs/../' + marker + '.md'
        save_change(root, change)
    assert main(['--root', str(root), 'change-validate', str(path), '--policy-sha256', pin]) == 2
    captured = capsys.readouterr()
    assert marker not in captured.out + captured.err
    assert json.loads(captured.err)['status'] == 'blocked'


def test_source_drift_during_check_is_rejected(tmp_path, monkeypatch):
    root, _, pin, _ = make_change(tmp_path)
    real = governance.snapshot
    count = [0]
    def changing(r):
        result = real(r)
        count[0] += 1
        if count[0] > 1: result = {**result, 'commit': 'f' * 40}
        return result
    monkeypatch.setattr(governance, 'snapshot', changing)
    with pytest.raises(HarnessError, match='Source changed'):
        governance.validate_change(root, root / 'docs/changes/CHANGE-001/r0001/change.json', pin)


@pytest.mark.parametrize('purpose', ['release', 'deployment', 'broker-execution'])
def test_privileged_purposes_require_release_approval(tmp_path, purpose):
    root, change, pin, _ = make_change(tmp_path)
    change['purpose'] = purpose
    change['approvals'].update(mode='signed-external', assurance='signed')
    path = save_change(root, change)
    with pytest.raises(HarnessError, match='approval requirements'):
        governance.validate_change(root, path, pin)
    change['approvals']['stages'].append('release')
    path = save_change(root, change)
    result = governance.validate_change(root, path, pin)
    assert result['effective_risk'] == 'R3'
    assert 'release' in result['required_approval_stages']
    assert result['authorization'] == 'not_granted'


def test_unattended_write_requires_signed_requirements_but_not_release(tmp_path):
    root, change, pin, _ = make_change(tmp_path)
    change['purpose'] = 'unattended-write'
    change['approvals'].update(mode='signed-external', assurance='signed')
    result = governance.validate_change(root, save_change(root, change), pin)
    assert 'implementation' in result['required_approval_stages']
    assert 'release' not in result['required_approval_stages']
    assert result['human_approval_verified'] is False

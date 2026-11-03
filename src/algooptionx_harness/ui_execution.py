"""Map the existing native browser runner to frozen UI cases; no second executor."""
from __future__ import annotations

import hashlib
from pathlib import Path

from algooptionx_harness.designs import (
    DesignBinding, DesignSpec, UIValidationEvidence, validate_design,
)
from algooptionx_harness.governance import _json
from algooptionx_harness.models import Evidence, Task
from algooptionx_harness.runner import verify_evidence
from algooptionx_harness.workspace import HarnessError, contained, digest, canonical


def browser_cases(inputs, task: Task, evidence_ref, design):
    """Derive only from exact, passing, unretried native browser test results."""
    from algooptionx_harness.designs import _Reader
    reader = _Reader(inputs.root, '.harness/ui-collector-input.json')
    spec = inputs.model(design.reference, DesignSpec)
    evidence = inputs.model(evidence_ref, Evidence)
    if evidence.task_id != task.id or evidence.task_digest != digest(task):
        raise HarnessError('UI browser report belongs to another task.')
    checks = {check.id: check for check in task.checks if check.kind == 'playwright'}
    reports = []
    for result in evidence.results:
        if result.check_id not in checks:
            continue
        check = checks[result.check_id]
        if result.status != 'passed' or result.exit_code != 0 or result.timed_out or not check.report:
            raise HarnessError('UI browser execution did not pass.')
        directory = inputs.root / Path(evidence_ref.path).parent
        report_path = Path(check.report.replace('{run_dir}', str(directory)))
        report_path = report_path if report_path.is_absolute() else inputs.root/report_path
        name = str(report_path.relative_to(inputs.root))
        artifact = next((a for a in result.artifacts if directory/a.path == report_path), None)
        if artifact is None:
            raise HarnessError('UI browser report is not in native hashed artifacts.')
        inputs.artifact(name, artifact.sha256)
        report_bytes = reader.raw(name, 20 * 1024 * 1024)
        if hashlib.sha256(report_bytes).hexdigest() != artifact.sha256:
            raise HarnessError('Native browser report changed during inspection.')
        reports.append((report_path, _json(report_bytes)))
    if not reports:
        raise HarnessError('UI cases require an executed native Playwright report.')
    expected = {case.id: case for case in spec.validation_cases}
    found = {}

    def specs(suite):
        yield from suite.get('specs', [])
        for child in suite.get('suites', []):
            yield from specs(child)

    for report_path, report in reports:
        if report.get('errors'):
            raise HarnessError('Browser report has global errors.')
        for suite in report.get('suites', []):
            for entry in specs(suite):
                title = entry.get('title', '')
                if not title.startswith('UI::'):
                    continue
                case_id = title.removeprefix('UI::')
                if case_id not in expected or case_id in found:
                    raise HarnessError('Unexpected or duplicated executed UI case.')
                tests = entry.get('tests', [])
                if len(tests) != 1 or tests[0].get('expectedStatus') != 'passed':
                    raise HarnessError('UI case must be one ordinary passing test.')
                results = tests[0].get('results', [])
                if len(results) != 1 or results[0].get('status') != 'passed' or results[0].get('retry', 0) != 0 or results[0].get('errors'):
                    raise HarnessError('Failed, retried or skipped UI execution is not passing evidence.')
                attachments = {}
                for attachment in results[0].get('attachments', []):
                    name = attachment.get('name', '')
                    if not name.startswith('ui-'):
                        continue
                    if name in attachments or 'path' not in attachment:
                        raise HarnessError('UI attachments must be unique files.')
                    raw_path = Path(attachment['path'])
                    path = raw_path if raw_path.is_absolute() else report_path.parent/raw_path
                    try:
                        relative = path.absolute().relative_to(report_path.parent.absolute())
                        # Reject traversal, symlinks and files outside the native report folder.
                        clean = contained(report_path.parent, relative.as_posix())
                        data = reader.raw(str(clean.relative_to(inputs.root)), 20 * 1024 * 1024)
                        ref = {'path': str(clean.relative_to(inputs.root)), 'sha256': hashlib.sha256(data).hexdigest()}
                        inputs.artifact(ref['path'], ref['sha256'])
                    except (ValueError, OSError):
                        raise HarnessError('Unsafe or unavailable UI attachment.') from None
                    attachments[name] = (ref, data)

                def value(name):
                    if name not in attachments:
                        raise HarnessError('Required UI browser attachment is missing.')
                    return _json(attachments[name][1])

                case = expected[case_id]
                viewport = next(v for v in spec.viewports if v.id == case.viewport_id)
                context = {'renderer': spec.renderer.model_dump(mode='json'),
                           'fixture': spec.fixture.model_dump(mode='json'),
                           'viewport': viewport.model_dump(mode='json'), 'theme': case.theme}
                if value('ui-context') != context:
                    raise HarnessError('UI renderer, fixture, viewport or theme differs from frozen design.')
                areas = []
                required_attachments = {'ui-context'}
                for area in case.checks:
                    report_name = f'ui-{area}'
                    body = value(report_name)
                    if 'areas' in body:
                        packed = body['areas']
                        if body.get('case_id') != case_id or not isinstance(packed, dict) or set(packed) != set(case.checks):
                            raise HarnessError('Packed UI areas differ from frozen case requirements.')
                        body = packed[area]
                        if not isinstance(body, dict):
                            raise HarnessError('Packed UI area must be an object.')
                    required_attachments.add(report_name)
                    if body.get('status') != 'passed' or body.get('case_id') != case_id or body.get('area') != area:
                        raise HarnessError('Executed UI area did not pass for this case.')
                    refs = [{'kind': 'report', 'reference': attachments[report_name][0]}]
                    if area == 'visual':
                        for name, kind in [('ui-screenshot', 'screenshot'), ('ui-comparison', 'comparison')]:
                            if name not in attachments:
                                raise HarnessError('Visual execution lacks screenshot/comparison.')
                            required_attachments.add(name)
                            refs.append({'kind': kind, 'reference': attachments[name][0]})
                        comparison = value('ui-comparison')
                        if comparison.get('status') != 'passed' or comparison.get('case_id') != case_id or comparison.get('screenshot_sha256') != attachments['ui-screenshot'][0]['sha256']:
                            raise HarnessError('Visual comparison failed or references a different screenshot.')
                    areas.append({'area': area, 'status': 'passed',
                                  'notes': 'Derived from exact passing native browser case attachments.',
                                  'artifacts': refs, 'measurements': body.get('measurements', [])})
                if set(attachments) != required_attachments:
                    raise HarnessError('UI attachment areas differ from frozen case requirements.')
                found[case_id] = {'case_id': case_id, 'status': 'passed', 'results': areas}
    if set(found) != set(expected):
        raise HarnessError('Native browser case coverage is incomplete.')
    reader.finish()
    return [found[case.id] for case in spec.validation_cases]


def collect_ui_evidence(root, binding_path, evidence_path, policy_sha256, output_path):
    """Verify native execution and exclusively write a derived evidence record."""
    from algooptionx_harness.enforcement import Inputs, _reference
    root = root.resolve()
    inputs = Inputs(root)
    binding_path = binding_path if binding_path.is_absolute() else root/binding_path
    evidence_path = evidence_path if evidence_path.is_absolute() else root/evidence_path
    binding = inputs.model(_reference(root, binding_path), DesignBinding)
    checked = validate_design(root, binding_path, policy_sha256)
    inputs.design_checks.append((str(binding_path.relative_to(root)), policy_sha256, checked['record_digest']))
    task = inputs.model(binding.native_task_reference, Task)
    baseline = inputs.value(binding.baseline_reference)
    evidence_ref = _reference(root, evidence_path)
    inputs.model(evidence_ref, Evidence)
    verify_evidence(root, task, baseline, evidence_path)
    cases = browser_cases(inputs, task, evidence_ref, binding.design)
    from algooptionx_harness.changes import SourceIdentity
    record = UIValidationEvidence(kind='ui-validation-evidence', change_id=binding.change_id,
        change_revision=binding.change_revision, change_digest=binding.change_digest,
        policy_digest=binding.policy_digest,
        source=SourceIdentity(commit=inputs.source['commit'], source_digest=digest(inputs.source)),
        design=binding.design, native_task_reference=binding.native_task_reference,
        native_task_digest=digest(task), native_evidence_reference=evidence_ref.model_dump(),
        expected_cases=[c['case_id'] for c in cases], executed_cases=cases)
    output_path = output_path if output_path.is_absolute() else root/output_path
    name = str(output_path.absolute().relative_to(root))
    if not name.startswith('.harness/') or not name.endswith('.json'):
        raise HarnessError('UI collection output must be a new .harness JSON file.')
    destination = contained(root, name)
    inputs.finish()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as stream:
        stream.write(canonical(record) + b'\n')
    try:
        validate_design(root, destination, policy_sha256)
        inputs.finish()
    except Exception:
        # Preserve incomplete output for diagnosis; it never confers readiness.
        raise
    return {'status': 'collected-native-ui-evidence', 'path': name,
            'cases': len(cases), 'human_acceptance': False, 'grants_deployment': False}

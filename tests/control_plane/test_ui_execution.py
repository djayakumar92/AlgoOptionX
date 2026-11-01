"""Adversarial synthetic browser-report bindings, not execution attestation."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import json

import pytest

from algooptionx_harness.enforcement import Inputs
from algooptionx_harness.changes import StoredReference
from algooptionx_harness.designs import DesignBinding
from algooptionx_harness.models import Task, Evidence
from algooptionx_harness.runner import parse_report
from algooptionx_harness.ui_execution import browser_cases, collect_ui_evidence
from algooptionx_harness.workspace import HarnessError, digest, file_digest, write_json
from tests.control_plane.test_design_contracts import make_design


def executed_report(root, native, spec):
    """Add a declared UI case to synthetic native execution records."""
    def put(path, value):
        write_json(root/path, value)
        return {'path': path, 'sha256': file_digest(root/path)}
    evidence_path = root/native['evidence']['path']
    evidence = Evidence.model_validate_json(evidence_path.read_text())
    task = Task.model_validate_json((root/native['task']['path']).read_text())
    check = next(c for c in task.checks if c.kind == 'playwright')
    result = next(r for r in evidence.results if r.check_id == check.id)
    report_path = Path(check.report.replace('{run_dir}', str(evidence_path.parent)))
    report = json.loads(report_path.read_text())
    for case in spec['validation_cases']:
        cid = case['id']; attachments = []
        def attach(name, value):
            path = report_path.parent/'ui'/cid/(name+'.json')
            put(str(path.relative_to(root)), value)
            attachments.append({'name': name, 'path': str(path), 'contentType': 'application/json'})
        attach('ui-context', {'renderer': spec['renderer'], 'fixture': spec['fixture'],
            'viewport': next(v for v in spec['viewports'] if v['id'] == case['viewport_id']), 'theme': case['theme']})
        for area in case['checks']:
            body = {'case_id': cid, 'area': area, 'status': 'passed'}
            if area == 'performance':
                body['measurements'] = [{'budget_id': b['id'], 'observed': 10.0, 'samples': b['samples']} for b in spec['performance_budgets']]
            attach('ui-'+area, body)
        if 'visual' in case['checks']:
            path = report_path.parent/'ui'/cid/'screenshot.png'; path.write_bytes(b'\x89PNG\r\n\x1a\nsynthetic-declaration')
            attachments.append({'name':'ui-screenshot','path':str(path),'contentType':'image/png'})
            attach('ui-comparison', {'status':'passed','case_id':cid,'screenshot_sha256':file_digest(path),'label':'Synthetic comparison declaration, not actual rendering.'})
        report.setdefault('suites', []).append({'specs':[{'file':'ui.spec.ts','title':'UI::'+cid,
            'tests':[{'expectedStatus':'passed','results':[{'status':'passed','retry':0,'attachments':attachments}]}]}]})
    write_json(report_path, report)
    result.artifacts = [a.model_copy(update={'sha256':file_digest(report_path)}) if a.path == str(report_path.relative_to(evidence_path.parent)) else a for a in result.artifacts]
    result.outcomes = parse_report(check, report_path)
    native['evidence'] = put(str(evidence_path.relative_to(root)), evidence)
    # Native closure fixtures bind each reviewer and QA decision to exact evidence.
    if 'review' in native:
        for ref in [native['review'], *native.get('gate_reviews', {}).values()]:
            value = json.loads((root/ref['path']).read_text())
            value['artifacts'] = [native['evidence']]
            new_ref = put(ref['path'], value); ref.update(new_ref)
        from algooptionx_harness.models import ChatRequest
        validation_binding = digest({'validation': digest(evidence), 'independent_review': native['review']['sha256']})
        for pair in native['approvals']['chat']:
            request = json.loads((root/pair['request']['path']).read_text())
            if request['stage'] != 'qa':
                continue
            request['evidence_digest'] = validation_binding
            pair['request'] = put(pair['request']['path'], request)
            decision = json.loads((root/pair['decision']['path']).read_text())
            decision['request_digest'] = digest(ChatRequest.model_validate_json(json.dumps(request)))
            pair['decision'] = put(pair['decision']['path'], decision)
    return native


def fixture(tmp_path):
    f = make_design(tmp_path)
    native = executed_report(f['root'], {'task': f['binding']['native_task_reference'],
        'evidence': f['evidence']['native_evidence_reference']}, f['spec'])
    f['evidence']['native_evidence_reference'] = native['evidence']
    f['native'] = native
    return f


def derive(f):
    inputs = Inputs(f['root'])
    result = browser_cases(inputs, f['task'], StoredReference(**f['native']['evidence']),
                           DesignBinding.model_validate_json(json.dumps(f['binding'])).design)
    inputs.finish()
    return result


def test_collects_native_browser_cases_without_granting_approval(tmp_path):
    f = fixture(tmp_path)
    cases = derive(f)
    assert [c['case_id'] for c in cases] == ['CASE-001']
    result = collect_ui_evidence(f['root'], Path(f['binding_ref']['path']),
        Path(f['native']['evidence']['path']), f['policy_pin'], Path('.harness/collected.json'))
    assert result['cases'] == 1 and result['human_acceptance'] is False
    with pytest.raises(FileExistsError):
        collect_ui_evidence(f['root'], Path(f['binding_ref']['path']),
            Path(f['native']['evidence']['path']), f['policy_pin'], Path('.harness/collected.json'))


@pytest.mark.parametrize('mutation', ['missing','duplicate','unknown','failed','skipped','retried','wrong-profile','outside-attachment','global-error','missing-area','failed-comparison','wrong-screenshot','fifo'])
def test_browser_execution_mismatches_fail_closed(tmp_path, mutation):
    f = fixture(tmp_path); root = f['root']
    evidence = Evidence.model_validate_json((root/f['native']['evidence']['path']).read_text())
    report_path = root/'.harness/run/browser.json'; report = json.loads(report_path.read_text())
    entry = report['suites'][-1]['specs'][0]; result = entry['tests'][0]['results'][0]
    if mutation == 'missing': report['suites'].pop()
    elif mutation == 'duplicate': report['suites'].append(copy.deepcopy(report['suites'][-1]))
    elif mutation == 'unknown': entry['title'] = 'UI::CASE-UNKNOWN'
    elif mutation in {'failed','skipped'}: result['status'] = mutation
    elif mutation == 'retried': result['retry'] = 1
    elif mutation == 'wrong-profile':
        path = Path(result['attachments'][0]['path']); value = json.loads(path.read_text()); value['theme'] = 'dark'; write_json(path,value)
    elif mutation == 'outside-attachment': result['attachments'][0]['path'] = str(root/'docs/fixture.json')
    elif mutation == 'global-error': report['errors'] = [{'message':'browser failure'}]
    elif mutation == 'missing-area': result['attachments'].pop(1)
    elif mutation in {'failed-comparison','wrong-screenshot'}:
        path = Path(next(a['path'] for a in result['attachments'] if a['name'] == 'ui-comparison')); value = json.loads(path.read_text())
        value['status' if mutation == 'failed-comparison' else 'screenshot_sha256'] = 'failed' if mutation == 'failed-comparison' else 'f'*64
        write_json(path,value)
    elif mutation == 'fifo':
        import os
        path = report_path.parent/'fifo.json'; os.mkfifo(path); result['attachments'][0]['path'] = str(path)
    write_json(report_path, report)
    # Rehash to challenge semantic checks, not just trivial stale-hash rejection.
    browser = next(r for r in evidence.results if r.check_id == 'browser')
    browser.artifacts = [a.model_copy(update={'sha256':file_digest(report_path)}) if a.path == 'browser.json' else a for a in browser.artifacts]
    f['native']['evidence'] = f['put']('.harness/run/evidence.json', evidence)
    with pytest.raises(HarnessError): derive(f)


def test_grouped_review_retains_required_stages_and_one_actual_reply(tmp_path):
    from algooptionx_harness import chat
    f=make_design(tmp_path);requests=chat.request_group(f['task'])
    assert [r.stage for r in requests] == ['plan','architecture','ui','implementation']
    decisions=chat.record_group(requests,'Approved','operator:synthetic-fixture')
    for request,decision in zip(requests,decisions):
        assert chat.verify_record(f['task'],request,decision,f['task'].baseline_digest)['status']=='recorded'
    assert all(chat.same_review_group(requests[i-1],decisions[i-1],requests[i],decisions[i]) for i in range(1,len(requests)))
    changed=decisions[1].model_copy(update={'user_message':'yes'})
    assert not chat.same_review_group(requests[0],decisions[0],requests[1],changed)
    with pytest.raises(HarnessError):chat.record_group(requests[1:],'Approved','operator:synthetic-fixture')
    qa=requests[-1].model_copy(update={'stage':'qa'})
    assert not chat.same_review_group(requests[-1],decisions[-1],qa,decisions[-1])


@pytest.mark.parametrize('corrupt', [False, True])
def test_grouped_review_verifies_through_actual_ui_change_bundle(tmp_path, corrupt):
    from algooptionx_harness import chat
    from algooptionx_harness.models import Handoff
    from algooptionx_harness.enforcement import verify_bundle
    from tests.control_plane.test_ui_enforcement import ui_bundle
    f,path,bundle,bundle_path=ui_bundle(tmp_path);root=f['root']
    for native in [bundle['children'][0]['native'],bundle['aggregate']]:
        task=Task.model_validate_json((root/native['task']['path']).read_text())
        requests=chat.request_group(task);decisions=chat.record_group(requests,'Approved','operator:synthetic-fixture')
        if corrupt:decisions[1]=decisions[1].model_copy(update={'user_message':'yes'})
        folder=Path(native['task']['path']).parent
        pairs=[{'request':f['put'](str(folder/f'group-{r.stage}-request.json'),r),'decision':f['put'](str(folder/f'group-{r.stage}-decision.json'),d)} for r,d in zip(requests,decisions)]
        evidence=Evidence.model_validate_json((root/native['evidence']['path']).read_text())
        binding=digest({'validation':digest(evidence),'independent_review':native['review']['sha256']})
        request=chat.request(task,'qa',evidence.source_digest,binding,str(root/native['evidence']['path']),str(root/native['review']['path']))
        decision=chat.record(request,'Approved','operator:synthetic-fixture')
        pairs.append({'request':f['put'](str(folder/'group-qa-request.json'),request),'decision':f['put'](str(folder/'group-qa-decision.json'),decision)})
        native['approvals']['chat']=pairs
        value=json.loads((root/native['design_binding']['path']).read_text())
        value['approvals']=[{'id':'UI-GROUP-REFERENCE','mode':'operator-recorded-chat',**pairs[2]}]
        native['design_binding']=f['put'](native['design_binding']['path'],value)
    f['put'](str(bundle_path.relative_to(root)),bundle)
    if corrupt:
        with pytest.raises(HarnessError):verify_bundle(root,path,f['policy_pin'],bundle_path)
    else:
        assert verify_bundle(root,path,f['policy_pin'],bundle_path)['status']=='verified_local_acceptance'

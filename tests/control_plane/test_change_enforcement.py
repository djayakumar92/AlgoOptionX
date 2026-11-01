"""Synthetic native artifacts test consistency, never trusted execution provenance."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from algooptionx_harness import chat
from algooptionx_harness.changes import ChangeSpec, IntentBinding, CapturedBinding
from algooptionx_harness.enforcement import (
    ChangeBundle, NativeRun, Inputs, capture_child, dispatch_child, verify_bundle,
    close_change, REVIEW_ROLES, _checks,
)
from algooptionx_harness.governance import validate_change
from algooptionx_harness.impact import select_checks
from algooptionx_harness.models import Task, Evidence, Handoff, Result, Artifact, TestOutcome as Outcome
from algooptionx_harness.runner import verify_evidence, verify_historical_evidence
from algooptionx_harness.workspace import HarnessError, snapshot, digest, file_digest, write_json as native_write
from algooptionx_harness.cli import main
from tests.control_plane.test_change_contracts import make_change, save_change, write_json


def ref(root, path):
    return {'path':str(path.relative_to(root)), 'sha256':file_digest(path)}


def store(root, name, value):
    path=root/name
    native_write(path,value)
    return ref(root,path)


def native_fixture(root, task, baseline, candidate, name, gates=None):
    """Coherent synthetic run; no subprocess execution is claimed by this fixture."""
    folder=root/'.harness/fixtures'/name
    task_ref=store(root,str((folder/'task.json').relative_to(root)),task)
    baseline_ref=store(root,str((folder/'baseline.json').relative_to(root)),baseline)
    candidate_ref=store(root,str((folder/'candidate.json').relative_to(root)),candidate)
    results=[]
    for check in task.checks:
        artifacts=[];outcomes=[]
        log=folder/f'{check.id}.log';log.write_text('Synthetic consistency fixture; no executed command claim.\n')
        artifacts.append(Artifact(path=log.name,sha256=file_digest(log)))
        if check.kind=='pytest':
            ids=check.critical_tests or ['tests.fixture.test_consistency']
            import xml.etree.ElementTree as ET
            suite=ET.Element('testsuite')
            for identity in ids:
                classname,case=identity.rsplit('.',1);ET.SubElement(suite,'testcase',classname=classname,name=case)
                outcomes.append(Outcome(id=identity,status='passed'))
            report=folder/'pytest.xml';report.write_bytes(ET.tostring(suite))
            artifacts.append(Artifact(path=report.name,sha256=file_digest(report)))
        if check.kind=='playwright':
            specs=[]
            for identity in check.critical_tests or ['fixture.spec.ts::synthetic']:
                filename,title=identity.split('::',1)
                specs.append({'file':filename,'title':title,'tests':[{'expectedStatus':'passed','results':[{'status':'passed'}]}]})
                outcomes.append(Outcome(id=identity,status='passed'))
            report=folder/'browser/playwright.json';native_write(report,{'suites':[{'specs':specs}]})
            artifacts.append(Artifact(path='browser/playwright.json',sha256=file_digest(report)))
        results.append(Result(check_id=check.id,argv=[a.replace('{run_dir}',str(folder)) for a in check.argv],cwd=check.cwd,exit_code=0,timed_out=False,status='passed',detail='',duration_seconds=0.01,artifacts=artifacts,outcomes=outcomes))
    now=datetime.now(timezone.utc)-timedelta(minutes=10)
    from algooptionx_harness.workspace import changed_paths
    evidence=Evidence(run_id=name,task_id=task.id,task_digest=digest(task),source_digest=digest(candidate),final_source_digest=digest(candidate),source_commit=candidate['commit'],started_at=now,finished_at=now+timedelta(seconds=1),status='passed',changed_paths=changed_paths(baseline,candidate),results=results,runtime={'python':'synthetic','platform':'synthetic'})
    evidence_ref=store(root,str((folder/'evidence.json').relative_to(root)),evidence)
    def handoff(role):
        model=Handoff(task_id=task.id,task_digest=digest(task),source_digest=digest(candidate),role=role,actor=f'agent:fixture:{role}',requirement_ids=task.requirement_ids,status='completed',summary='Synthetic evidence-linked declared role review fixture.',artifacts=[Artifact(**evidence_ref)],findings=[])
        return store(root,str((folder/f'{role}.json').relative_to(root)),model)
    review_ref=handoff('independent-validator')
    binding=digest({'validation':digest(evidence),'independent_review':review_ref['sha256']})
    pairs=[]
    for index,stage in enumerate(['plan','architecture','implementation','qa']):
        request=chat.request(task,stage,digest(candidate) if stage=='qa' else task.baseline_digest,binding if stage=='qa' else None,str(root/evidence_ref['path']) if stage=='qa' else None,str(root/review_ref['path']) if stage=='qa' else None)
        request=request.model_copy(update={'requested_at':now+timedelta(seconds=2+index*2)})
        decision=chat.record(request,'approved','operator:synthetic-test')
        decision=decision.model_copy(update={'recorded_at':now+timedelta(seconds=3+index*2)})
        pairs.append({'request':store(root,str((folder/f'{stage}-request.json').relative_to(root)),request),'decision':store(root,str((folder/f'{stage}-decision.json').relative_to(root)),decision)})
    return {'task':task_ref,'baseline':baseline_ref,'candidate':candidate_ref,'evidence':evidence_ref,'review':review_ref,'approvals':{'chat':pairs},'gate_reviews':{gate:handoff(REVIEW_ROLES[gate]) for gate in (gates or ['REFERENCES']) if gate in REVIEW_ROLES}}


def fixture(tmp_path, *, changed=False, risk='R0'):
    root,raw,pin,template=make_change(tmp_path)
    raw['requested_risk']=risk
    template['checks']=select_checks(template['allowed_paths'],full=risk in {'R2','R3'})['checks']
    path=save_change(root,raw,template)
    change=ChangeSpec.model_validate(raw)
    before=snapshot(root)
    obligations=validate_change(root,path,pin)
    task=Task.model_validate({**template,'source_commit':before['commit'],'baseline_digest':digest(before)})
    if changed:
        (root/'docs/guide.md').write_text('Bounded child fixture result.\n')
    candidate=snapshot(root)
    source={'commit':before['commit'],'source_digest':digest(before)}
    base={'change_id':change.id,'change_revision':change.revision,'change_digest':digest(change),'policy_digest':pin,'source':source}
    intent=IntentBinding(**base,kind='intent',child_id='CHILD-001',child_revision=1,template_digest=change.children[0].task_template.sha256,role_skill_digests=obligations['role_skill_digests'],purpose='local-development')
    captured=CapturedBinding(**base,kind='captured',intent_digest=digest(intent),native_task_digest=digest(task),baseline_digest=digest(before))
    child={**base,'source':{'commit':candidate['commit'],'source_digest':digest(candidate)},'child_id':'CHILD-001','child_revision':1,'intent':store(root,'.harness/fixtures/intent.json',intent),'captured':store(root,'.harness/fixtures/captured.json',captured),'native':native_fixture(root,task,before,candidate,'child',obligations['required_gates'])}
    aggregate=task.model_copy(update={'id':'CHANGE-001-AGGREGATE'})
    bundle={**base,'source':{'commit':candidate['commit'],'source_digest':digest(candidate)},'children':[child],'aggregate':native_fixture(root,aggregate,before,candidate,'aggregate',obligations['required_gates']),'rollback_reference':store(root,'.harness/fixtures/rollback.json',{'instructions':'Reverse scoped fixture only; preserve all records.'})}
    bundle_path=root/'.harness/fixtures/bundle.json';native_write(bundle_path,bundle)
    return root,path,pin,bundle,bundle_path


def rewrite(root, reference, mutate):
    import json
    path=root/reference['path'];raw=json.loads(path.read_text());mutate(raw);native_write(path,raw);reference['sha256']=file_digest(path)


def test_valid_native_bundle_and_distinct_acceptance_archive_checkpoints(tmp_path):
    root,path,pin,bundle,bundle_path=fixture(tmp_path,changed=True)
    before=snapshot(root)
    result=verify_bundle(root,path,pin,bundle_path)
    assert result['status']=='verified_local_acceptance'
    assert result['approval']['human_origin_cryptographically_verified'] is False
    assert result['protected_execution_provenance']=='NOT VERIFIED'
    with pytest.raises((HarnessError,OSError)):
        close_change(root,path,pin,bundle_path,archive=True)
    accepted=close_change(root,path,pin,bundle_path)
    directory=Path(accepted['closure_path']);assert (directory/'acceptance.json').is_file()
    with pytest.raises(FileExistsError): close_change(root,path,pin,bundle_path)
    archived=close_change(root,path,pin,bundle_path,archive=True)
    assert archived['archived'] and (directory/'knowledge.json').is_file()
    with pytest.raises(HarnessError):close_change(root,path,pin,bundle_path,archive=True)
    assert snapshot(root)==before


@pytest.mark.parametrize('issue', ['parent-revision','policy','child-revision','missing-child','duplicate-child','chain','template','intent-skills','captured','aggregate-scope','aggregate-id','aggregate-protected','source'])
def test_stale_or_incomplete_change_bindings_fail_closed(tmp_path, issue):
    root,path,pin,bundle,bundle_path=fixture(tmp_path)
    child=bundle['children'][0]
    if issue=='parent-revision':bundle['change_revision']=2
    if issue=='policy':bundle['policy_digest']='d'*64
    if issue=='child-revision':child['child_revision']=2
    if issue=='missing-child':bundle['children']=[]
    if issue=='duplicate-child':bundle['children'].append(copy.deepcopy(child))
    if issue=='chain':rewrite(root,bundle['aggregate']['baseline'],lambda raw:raw['files'].pop('docs/changes/CHANGE-001/r0001/proposal.md'))
    if issue=='template':rewrite(root,child['native']['task'],lambda raw:raw.update(title='Unexpected changed native task title'))
    if issue=='intent-skills':rewrite(root,child['intent'],lambda raw:raw.update(role_skill_digests={'role:backend-engineer':'a'*64}))
    if issue=='captured':rewrite(root,child['captured'],lambda raw:raw.update(native_task_digest='d'*64))
    if issue=='aggregate-scope':rewrite(root,bundle['aggregate']['task'],lambda raw:raw.update(allowed_paths=['docs/']))
    if issue=='aggregate-id':rewrite(root,bundle['aggregate']['task'],lambda raw:raw.update(id='OTHER-001'))
    if issue=='aggregate-protected':rewrite(root,bundle['aggregate']['task'],lambda raw:raw.update(protected_inputs=['config/engineering-governance.json']))
    if issue=='source':bundle['source']['source_digest']='d'*64
    native_write(bundle_path,bundle)
    with pytest.raises((HarnessError,ValidationError)):verify_bundle(root,path,pin,bundle_path)


@pytest.mark.parametrize('issue', ['fake-reply','rejection','missing-stage','duplicate-stage','replayed-source','future-decision','qa-location','qa-evidence','qa-predates','signed-required'])
def test_native_human_decision_checks_and_boundaries(tmp_path, issue):
    root,path,pin,bundle,bundle_path=fixture(tmp_path)
    native=bundle['aggregate'];pairs=native['approvals']['chat']
    if issue=='fake-reply':rewrite(root,pairs[-1]['decision'],lambda raw:raw.update(user_message='I never approved this'))
    if issue=='rejection':rewrite(root,pairs[-1]['decision'],lambda raw:raw.update(user_message='reject',decision='reject'))
    if issue=='missing-stage':pairs.pop(0)
    if issue=='duplicate-stage':pairs[1]=copy.deepcopy(pairs[0])
    if issue=='replayed-source':rewrite(root,pairs[-1]['decision'],lambda raw:raw.update(source_digest='d'*64))
    if issue=='future-decision':rewrite(root,pairs[-1]['decision'],lambda raw:raw.update(recorded_at='2099-01-01T00:00:00Z'))
    if issue=='qa-location':rewrite(root,pairs[-1]['request'],lambda raw:raw.update(evidence_path='/tmp/other.json'))
    if issue=='qa-evidence':rewrite(root,pairs[-1]['request'],lambda raw:raw.update(evidence_digest='e'*64))
    if issue=='qa-predates':rewrite(root,pairs[-1]['request'],lambda raw:raw.update(requested_at='2000-01-01T00:00:00Z'))
    if issue=='signed-required':native['approvals']={'signed':[]}
    native_write(bundle_path,bundle)
    with pytest.raises(HarnessError):verify_bundle(root,path,pin,bundle_path)


@pytest.mark.parametrize('issue',['failed','forged-outcomes','missing-log','mutated-log','self-review','missing-evidence-link','gate-review','missing-gate','unknown-gate','missing-test','weaken-skip'])
def test_evidence_review_and_test_omissions_rejected(tmp_path,issue):
    root,path,pin,bundle,bundle_path=fixture(tmp_path)
    native=bundle['children'][0]['native']
    if issue=='failed':rewrite(root,native['evidence'],lambda raw:raw.update(status='failed'))
    if issue=='forged-outcomes':rewrite(root,native['evidence'],lambda raw:raw['results'][0]['outcomes'][0].update(status='failed'))
    if issue=='missing-log':rewrite(root,native['evidence'],lambda raw:raw['results'][0].update(artifacts=[]))
    if issue=='mutated-log':(root/Path(native['evidence']['path']).parent/'python.log').write_text('tampered')
    if issue=='self-review':rewrite(root,native['review'],lambda raw:raw.update(actor='agent:fixture'))
    if issue=='missing-evidence-link':rewrite(root,native['review'],lambda raw:raw.update(artifacts=[]))
    if issue=='gate-review':rewrite(root,native['gate_reviews']['REFERENCES'],lambda raw:raw.update(status='blocked'))
    if issue=='missing-gate':native['gate_reviews']={}
    if issue=='unknown-gate':native['gate_reviews']['UNKNOWN-GATE']=native['review']
    if issue=='missing-test':rewrite(root,native['task'],lambda raw:raw.update(checks=raw['checks'][:1]))
    if issue=='weaken-skip':rewrite(root,native['task'],lambda raw:raw['checks'][0].update(allowed_skips=['tests.fixture.test_consistency']))
    native_write(bundle_path,bundle)
    with pytest.raises((HarnessError,ValidationError)):verify_bundle(root,path,pin,bundle_path)


def test_historical_child_never_passes_current_verifier(tmp_path):
    root,path,pin,bundle,bundle_path=fixture(tmp_path,changed=True)
    native=bundle['children'][0]['native'];inputs=Inputs(root)
    task=inputs.model(NativeRun.model_validate(native).task,Task)
    baseline=inputs.value(NativeRun.model_validate(native).baseline)
    candidate=inputs.value(NativeRun.model_validate(native).candidate)
    (root/'docs/guide.md').write_text('Newer source.\n')
    assert verify_historical_evidence(root,task,baseline,root/native['evidence']['path'],candidate).status=='passed'
    with pytest.raises(HarnessError):verify_evidence(root,task,baseline,root/native['evidence']['path'])
    with pytest.raises(HarnessError):verify_bundle(root,path,pin,bundle_path)


def test_capture_and_dispatch_reuse_native_contracts_without_authority(tmp_path):
    root,path,pin,bundle,bundle_path=fixture(tmp_path)
    before=snapshot(root)
    captured=capture_child(root,path,pin,'CHILD-001')
    assert captured['status']=='captured-not-authorized'
    result=dispatch_child(root,path,pin,'CHILD-001','backend-engineer')
    assert result['change_binding']['authorization']=='not_granted'
    with pytest.raises(HarnessError):dispatch_child(root,path,pin,'CHILD-001','release-governor')
    with pytest.raises(HarnessError):capture_child(root,path,pin,'CHILD-404')
    with pytest.raises(HarnessError):capture_child(root,path,pin,'CHILD-001')
    assert snapshot(root)==before


def test_source_race_and_operational_pin_race(tmp_path,monkeypatch):
    import algooptionx_harness.enforcement as module
    root,path,pin,bundle,bundle_path=fixture(tmp_path)
    original=module._verify_run
    def mutate(*args,**kwargs):
        value=original(*args,**kwargs)
        if kwargs['current']:(root/'unexpected.txt').write_text('source race')
        return value
    monkeypatch.setattr(module,'_verify_run',mutate)
    with pytest.raises(HarnessError,match='Source changed'):verify_bundle(root,path,pin,bundle_path)


@pytest.mark.parametrize('issue',['duplicate-json','symlink','oversize','unknown-fields','traversal'])
def test_cli_sanitizes_bad_bundle_inputs(tmp_path,capsys,issue):
    root,path,pin,bundle,bundle_path=fixture(tmp_path)
    if issue=='duplicate-json':bundle_path.write_text('{"SENSITIVE_SENTINEL":1,"SENSITIVE_SENTINEL":2}')
    if issue=='symlink':bundle_path.unlink();bundle_path.symlink_to(path)
    if issue=='oversize':bundle_path.write_bytes(b'x'*(1024*1024+1))
    if issue=='unknown-fields':bundle['approved']=True;native_write(bundle_path,bundle)
    if issue=='traversal':bundle_path=Path('../SENSITIVE_SENTINEL.json')
    assert main(['--root',str(root),'change-verify',str(path),'--policy-sha256',pin,'--bundle',str(bundle_path)])==2
    assert 'SENSITIVE_SENTINEL' not in capsys.readouterr().out


def test_explicit_additional_ui_approval_cannot_be_ignored(tmp_path):
    import algooptionx_harness.enforcement as module
    root,path,pin,bundle,bundle_path=fixture(tmp_path)
    inputs=Inputs(root);native=NativeRun.model_validate(bundle['aggregate'])
    change,_,_=module._context(inputs,path,pin)
    change.approvals.stages.append('ui')
    task,_,candidate=module._task(inputs,native)
    evidence=inputs.model(native.evidence,Evidence)
    review=inputs.model(native.review,Handoff)
    with pytest.raises(HarnessError,match='UI approval'):
        module._approvals(inputs,change,task,native,candidate,evidence,review,final=True,trust_policy=None)


def test_late_native_log_mutation_rejected(tmp_path,monkeypatch):
    import algooptionx_harness.enforcement as module
    root,path,pin,bundle,bundle_path=fixture(tmp_path)
    original=module._approvals
    def mutate(*args,**kwargs):
        value=original(*args,**kwargs)
        (root/Path(bundle['aggregate']['evidence']['path']).parent/'python.log').write_text('late mutation')
        return value
    monkeypatch.setattr(module,'_approvals',mutate)
    with pytest.raises(HarnessError,match='artifact changed'):verify_bundle(root,path,pin,bundle_path)


def test_acceptance_mutation_during_archive_rejected(tmp_path,monkeypatch):
    import algooptionx_harness.enforcement as module
    root,path,pin,bundle,bundle_path=fixture(tmp_path)
    accepted=close_change(root,path,pin,bundle_path)
    acceptance=Path(accepted['closure_path'])/'acceptance.json'
    original=module.Inputs.model
    def mutate(self,reference,cls):
        value=original(self,reference,cls)
        if cls.__name__=='AcceptanceRecord':acceptance.write_text('{}')
        return value
    monkeypatch.setattr(module.Inputs,'model',mutate)
    with pytest.raises(HarnessError,match='inputs changed'):close_change(root,path,pin,bundle_path,archive=True)
    assert not acceptance.with_name('archive.json').exists()


def test_concurrently_created_archive_is_never_overwritten(tmp_path,monkeypatch):
    import algooptionx_harness.enforcement as module
    root,path,pin,bundle,bundle_path=fixture(tmp_path)
    accepted=close_change(root,path,pin,bundle_path);archive=Path(accepted['closure_path'])/'archive.json'
    original=module._exclusive_json
    def race(path,value):
        if path.name=='archive.json':path.write_text('concurrent record')
        original(path,value)
    monkeypatch.setattr(module,'_exclusive_json',race)
    with pytest.raises(FileExistsError):close_change(root,path,pin,bundle_path,archive=True)
    assert archive.read_text()=='concurrent record'


@pytest.mark.skipif(not hasattr(__import__('os'), 'mkfifo'), reason='POSIX FIFO test')
def test_bundle_fifo_rejected_before_hash_or_blocking_read(tmp_path):
    import os
    root,path,pin,bundle,bundle_path=fixture(tmp_path)
    bundle_path.unlink();os.mkfifo(bundle_path)
    with pytest.raises(HarnessError):verify_bundle(root,path,pin,bundle_path)


def test_bundle_is_bounded_before_file_digest(tmp_path,monkeypatch):
    import algooptionx_harness.enforcement as module
    root,path,pin,bundle,bundle_path=fixture(tmp_path)
    bundle_path.write_bytes(b'x'*(1024*1024+1))
    monkeypatch.setattr(module,'file_digest',lambda path: (_ for _ in ()).throw(AssertionError('unbounded hash called')))
    with pytest.raises(HarnessError):verify_bundle(root,path,pin,bundle_path)


def multi_fixture(tmp_path, *, second_changes=True):
    root,raw,pin,template=make_change(tmp_path)
    raw['allowed_paths'].append('docs/second.md')
    second=copy.deepcopy(raw['children'][0]);second['id']='CHILD-002';second['depends_on']=['CHILD-001']
    template2=copy.deepcopy(template);template2['id']='CHILD-002';template2['allowed_paths']=['docs/second.md']
    second_path=root/'docs/changes/CHANGE-001/r0001/tasks/CHILD-002.template.json'
    for task_raw in (template,template2):
        task_raw['checks']=select_checks(task_raw['allowed_paths'])['checks']
        task_raw['protected_inputs'].append(str(second_path.relative_to(root)))
    second['task_template']={'path':str(second_path.relative_to(root)),'sha256':write_json(second_path,template2)}
    raw['children'].append(second);path=save_change(root,raw,template)
    change=ChangeSpec.model_validate(raw);obligations=validate_change(root,path,pin)
    initial=snapshot(root);previous=initial;children=[]
    for index,(plan,template_raw) in enumerate(zip(change.children,[template,template2],strict=True)):
        task=Task.model_validate({**template_raw,'source_commit':previous['commit'],'baseline_digest':digest(previous)})
        if index==0 or second_changes:(root/task.allowed_paths[0]).write_text(f'Bounded child {index} output.\n')
        candidate=snapshot(root)
        base={'change_id':change.id,'change_revision':1,'change_digest':digest(change),'policy_digest':pin,'source':{'commit':previous['commit'],'source_digest':digest(previous)}}
        intent=IntentBinding(**base,kind='intent',child_id=plan.id,child_revision=1,template_digest=plan.task_template.sha256,role_skill_digests=obligations['role_skill_digests'],purpose='local-development')
        captured=CapturedBinding(**base,kind='captured',intent_digest=digest(intent),native_task_digest=digest(task),baseline_digest=digest(previous))
        children.append({**base,'source':{'commit':candidate['commit'],'source_digest':digest(candidate)},'child_id':plan.id,'child_revision':1,'intent':store(root,f'.harness/fixtures/intent-{index}.json',intent),'captured':store(root,f'.harness/fixtures/captured-{index}.json',captured),'native':native_fixture(root,task,previous,candidate,f'child-{index}')})
        previous=candidate
    aggregate=Task.model_validate({**template,'id':'CHANGE-001-AGGREGATE','allowed_paths':change.allowed_paths,'source_commit':initial['commit'],'baseline_digest':digest(initial)})
    bundle={**base,'source':{'commit':previous['commit'],'source_digest':digest(previous)},'children':children,'aggregate':native_fixture(root,aggregate,initial,previous,'aggregate'),'rollback_reference':store(root,'.harness/fixtures/rollback.json',{'instructions':'Reverse scoped fixture outputs only.'})}
    bundle_path=root/'.harness/fixtures/bundle.json';native_write(bundle_path,bundle)
    return root,path,pin,bundle,bundle_path


def test_two_children_sequence_dependency_order_and_fresh_aggregate(tmp_path):
    root,path,pin,bundle,bundle_path=multi_fixture(tmp_path)
    assert verify_bundle(root,path,pin,bundle_path)['children']==['CHILD-001','CHILD-002']
    bundle['children'].reverse();native_write(bundle_path,bundle)
    with pytest.raises(HarnessError,match='dependency'):verify_bundle(root,path,pin,bundle_path)


def test_dependent_dispatch_needs_verified_current_predecessors(tmp_path):
    root,path,pin,bundle,bundle_path=multi_fixture(tmp_path,second_changes=False)
    capture_child(root,path,pin,'CHILD-002')
    with pytest.raises(HarnessError,match='predecessor'):dispatch_child(root,path,pin,'CHILD-002','backend-engineer')
    proof={key:bundle[key] for key in ['change_id','change_revision','change_digest','policy_digest','source']}
    proof['children']=[bundle['children'][0]]
    proof_ref=store(root,'.harness/fixtures/dependencies.json',proof)
    assert dispatch_child(root,path,pin,'CHILD-002','backend-engineer',Path(proof_ref['path']))['change_binding']['authorization']=='not_granted'
    (root/'docs/guide.md').write_text('New unverified predecessor source.\n')
    with pytest.raises(HarnessError):dispatch_child(root,path,pin,'CHILD-002','backend-engineer',Path(proof_ref['path']))


@pytest.mark.parametrize('risk',['R2','R3'])
def test_elevated_risks_require_full_selection_and_all_role_reviews(tmp_path,risk):
    root,path,pin,bundle,bundle_path=fixture(tmp_path,risk=risk)
    assert verify_bundle(root,path,pin,bundle_path)['status']=='verified_local_acceptance'
    bundle['children'][0]['native']['gate_reviews'].pop('SECURITY')
    native_write(bundle_path,bundle)
    with pytest.raises(HarnessError,match='gate review'):verify_bundle(root,path,pin,bundle_path)


def signed_fixture(tmp_path):
    import base64
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
    from algooptionx_harness.approvals import signing_payload
    from algooptionx_harness.models import Approval
    root,path,pin,bundle,bundle_path=fixture(tmp_path)
    import json
    raw=json.loads(path.read_text());raw['approvals']['mode']='signed-external';raw['approvals']['assurance']='signed';native_write(path,raw)
    # Rebuild immutable source/change bindings after the fixture's explicit revision preparation.
    change=ChangeSpec.model_validate(raw);new_source=snapshot(root)
    template=json.loads((root/change.children[0].task_template.path).read_text())
    obligations=validate_change(root,path,pin)
    task=Task.model_validate({**template,'source_commit':new_source['commit'],'baseline_digest':digest(new_source)})
    base={'change_id':change.id,'change_revision':1,'change_digest':digest(change),'policy_digest':pin,'source':{'commit':new_source['commit'],'source_digest':digest(new_source)}}
    intent=IntentBinding(**base,kind='intent',child_id='CHILD-001',child_revision=1,template_digest=change.children[0].task_template.sha256,role_skill_digests=obligations['role_skill_digests'],purpose='local-development')
    captured=CapturedBinding(**base,kind='captured',intent_digest=digest(intent),native_task_digest=digest(task),baseline_digest=digest(new_source))
    child={**base,'child_id':'CHILD-001','child_revision':1,'intent':store(root,'.harness/signed/intent.json',intent),'captured':store(root,'.harness/signed/captured.json',captured),'native':native_fixture(root,task,new_source,new_source,'signed-child')}
    aggregate=task.model_copy(update={'id':'CHANGE-001-AGGREGATE'})
    bundle={**base,'children':[child],'aggregate':native_fixture(root,aggregate,new_source,new_source,'signed-aggregate'),'rollback_reference':bundle['rollback_reference']}
    private=Ed25519PrivateKey.generate();public=base64.b64encode(private.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode()
    policy=tmp_path/'external-policy.json';native_write(policy,{'schema_version':1,'keys':{'fixture-human':{'subject':'human:owner','actor_type':'human','public_key':public,'stages':['plan','architecture','implementation','qa']}},'max_approval_age_hours':24,'max_evidence_age_hours':24,'require_distinct_qa_release':False})
    for item in [child['native'],bundle['aggregate']]:
        native=NativeRun.model_validate(item);task=Task.model_validate_json((root/native.task.path).read_text());e=Evidence.model_validate_json((root/native.evidence.path).read_text())
        binding=digest({'validation':digest(e),'independent_review':native.review.sha256});receipts=[]
        for index,stage in enumerate(['plan','architecture','implementation','qa']):
            receipt=Approval(receipt_id=f'receipt-{task.id}-{stage}',task_id=task.id,task_digest=digest(task),stage=stage,source_digest=digest(new_source),evidence_digest=binding if stage=='qa' else None,subject='human:owner',actor_type='human',key_id='fixture-human',decision='approve',issued_at=e.finished_at+timedelta(seconds=2+index),expires_at=datetime.now(timezone.utc)+timedelta(hours=1),nonce=f'nonce-{task.id}-{stage}',signature='placeholder')
            receipt=receipt.model_copy(update={'signature':base64.b64encode(private.sign(signing_payload(receipt))).decode()})
            receipts.append(store(root,f'.harness/signed/{task.id}-{stage}.json',receipt))
        item['approvals']={'signed':receipts}
    native_write(bundle_path,bundle)
    return root,path,pin,bundle,bundle_path,policy


def test_signed_native_bridge_and_closure_requires_external_trust_and_valid_signatures(tmp_path):
    root,path,pin,bundle,bundle_path,policy=signed_fixture(tmp_path)
    with pytest.raises(HarnessError):verify_bundle(root,path,pin,bundle_path)
    result=verify_bundle(root,path,pin,bundle_path,policy)
    assert result['approval']['status']=='verified'
    close_change(root,path,pin,bundle_path,trust_policy=policy)
    close_change(root,path,pin,bundle_path,archive=True,trust_policy=policy)
    rewrite(root,bundle['aggregate']['approvals']['signed'][-1],lambda raw:raw.update(signature='invalid-signature'))
    native_write(bundle_path,bundle)
    with pytest.raises(HarnessError):verify_bundle(root,path,pin,bundle_path,policy)


def test_dispatch_task_capsule_mutation_is_detected(tmp_path,monkeypatch):
    import algooptionx_harness.enforcement as module
    root,path,pin,bundle,bundle_path=fixture(tmp_path)
    captured=capture_child(root,path,pin,'CHILD-001');task_path=Path(captured['task'])
    original=module.dispatch
    def mutate(*args,**kwargs):
        result=original(*args,**kwargs);task_path.write_text('{}');return result
    monkeypatch.setattr(module,'dispatch',mutate)
    with pytest.raises(HarnessError,match='inputs changed'):dispatch_child(root,path,pin,'CHILD-001','backend-engineer')


def test_dispatch_includes_explicit_child_skills_beyond_role_defaults(tmp_path):
    root,raw,pin,template=make_change(tmp_path)
    raw['children'][0]['skills'].append('security-review')
    template['checks']=select_checks(template['allowed_paths'])['checks']
    path=save_change(root,raw,template)
    capture_child(root,path,pin,'CHILD-001')
    result=dispatch_child(root,path,pin,'CHILD-001','backend-engineer')
    assert 'security-review' in {skill['id'] for skill in result['skills']}

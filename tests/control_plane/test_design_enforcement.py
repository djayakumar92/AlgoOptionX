"""Design execution contracts are data until native evidence and decisions verify."""
import copy,json,base64
from pathlib import Path
import pytest
from pydantic import ValidationError
from algooptionx_harness.changes import parse_change
from algooptionx_harness.designs import DesignSpec
from algooptionx_harness.governance import execution_checks,validate_change
from algooptionx_harness.ui_validation import UIExecutionPlan,load_plan,plan_name
from algooptionx_harness.enforcement import capture_child
from algooptionx_harness.workspace import digest,snapshot,HarnessError
from tests.control_plane.test_design_lifecycle import make_v2


def execution_fixture(tmp_path):
    f=make_v2(tmp_path);c=f['change'];spec=copy.deepcopy(f['spec'])
    spec['performance_budgets'][0].update(metric='interaction-latency',unit='ms',method='raf-theme-toggle-v1')
    spec['fixture']['reference']=f['put']('docs/fixture.json',{'adapter':'workspace-session-v1','seed':1,'label':'Synthetic fixed workspace session; no broker access.'})
    c['design_link']['reference']=f['put']('docs/design-package.json',spec)
    c['design_link']['record_digest']=digest(DesignSpec.model_validate_json(json.dumps(spec)))
    image=f['put']('apps/web/tests/visual-baselines/fixture/ready.png',base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jZQAAAABJRU5ErkJggg=='))
    manifest=f['put']('apps/web/tests/visual-baselines/fixture/manifest.json',{'schema_version':1,'approval_status':'pending_human_review','files':[{'path':'fixture/ready.png','sha256':image['sha256']}]})
    plan={'schema_version':1,'kind':'ui-execution','change_id':c['id'],'change_revision':1,'design':c['design_link'],'mode':'measure','renderer':spec['renderer'],'baseline_manifest':manifest,'cases':[{'id':'CASE-001','scenario':'workspace-overview','baseline':image}],'measurement_baseline':None,'adapter':'workspace-ui-v1','environment_sha256':__import__('algooptionx_harness.ui_validation',fromlist=['runtime_platform']).runtime_platform()}
    measured=f['put']('docs/measurement-plan.json',plan)
    plan=copy.deepcopy(plan);plan.update(mode='verify',measurement_baseline={'task':f['binding']['native_task_reference'],'baseline':f['binding']['baseline_reference'],'candidate':f['binding']['baseline_reference'],'evidence':f['evidence']['native_evidence_reference'],'report':f['put']('.harness/measurement.json',{'status':'synthetic-declaration-only'}),'plan':measured})
    f['put'](f'docs/changes/{c["id"]}/r0001/ui-execution.json',plan)
    f['put']('docs/changes/CHANGE-001/r0001/change.json',c)
    obligations=validate_change(f['root'],f['root']/'docs/changes/CHANGE-001/r0001/change.json',f['policy_pin'])
    template=f['template'];template['checks']=execution_checks(template['allowed_paths'],obligations,UIExecutionPlan.model_validate_json(json.dumps(plan)))
    template['protected_inputs']=sorted(set(template['protected_inputs'])|{plan_name(parse_change(c)),image['path'],manifest['path']})
    c['children'][2]['task_template']=f['put'](c['children'][2]['task_template']['path'],template)
    f['put']('docs/changes/CHANGE-001/r0001/change.json',c)
    f.update(change=c,spec=spec,plan=plan)
    return f


def test_frozen_capture_does_not_grant_authority(tmp_path):
    f=execution_fixture(tmp_path);root=f['root'];before=snapshot(root)
    out=capture_child(root,Path('docs/changes/CHANGE-001/r0001/change.json'),f['policy_pin'],'CHILD-001')
    assert out['status']=='captured-not-authorized'
    assert out['authorization']=='not_granted'
    assert Path(out['task']).exists()
    assert snapshot(root)==before


@pytest.mark.parametrize('issue',['version','extra-authority','duplicate-case','unknown-adapter','missing-measurement','unsafe-image'])
def test_plan_contract_rejects_spoofing(tmp_path,issue):
    f=execution_fixture(tmp_path);plan=copy.deepcopy(f['plan'])
    if issue=='version':plan['schema_version']=True
    elif issue=='extra-authority':plan['approved']=True
    elif issue=='duplicate-case':plan['cases'].append(copy.deepcopy(plan['cases'][0]))
    elif issue=='unknown-adapter':plan['adapter']='execute-document'
    elif issue=='missing-measurement':plan['measurement_baseline']=None
    else:plan['cases'][0]['baseline']['path']='apps/web/tests/visual-baselines/../secret.png'
    with pytest.raises(ValidationError):UIExecutionPlan.model_validate_json(json.dumps(plan))


def test_changed_baseline_is_rejected(tmp_path):
    f=execution_fixture(tmp_path);p=f['root']/f['plan']['cases'][0]['baseline']['path'];p.write_bytes(b'changed')
    with pytest.raises(HarnessError):load_plan(f['root'],parse_change(f['change']))


from datetime import datetime,timezone,timedelta
from algooptionx_harness import chat
from algooptionx_harness.enforcement import InputsV2,ApprovalSet,ChatPair,_approvals_v2
from algooptionx_harness.models import Task
from algooptionx_harness.workspace import load_task
from algooptionx_harness.ui_validation import review_summary


def approval_fixture(tmp_path):
    f=execution_fixture(tmp_path);root=f['root'];out=capture_child(root,Path('docs/changes/CHANGE-001/r0001/change.json'),f['policy_pin'],'CHILD-001')
    task,baseline=load_task(Path(out['task']));plan=UIExecutionPlan.model_validate_json(json.dumps(f['plan']))
    pairs=[]
    for stage in ['plan','architecture','ui','implementation']:
        request=chat.request(task,stage,task.baseline_digest,review_summary=review_summary(task,plan,root) if stage=='ui' else None)
        decision=chat.record(request,'approved','operator:synthetic-test')
        pairs.append({'request':f['put'](f'.harness/approvals/{stage}-request.json',request),'decision':f['put'](f'.harness/approvals/{stage}-decision.json',decision)})
    f.update(task=task,baseline=baseline,approvals=ApprovalSet.model_validate({'chat':pairs,'signed':[]}),parsed_plan=plan)
    return f


def test_actual_chat_contracts_remain_procedural(tmp_path):
    f=approval_fixture(tmp_path);inputs=InputsV2(f['root'])
    result=_approvals_v2(inputs,parse_change(f['change']),f['task'],f['approvals'],f['parsed_plan'],stage='implementation',source=f['baseline'])
    assert result['status']=='recorded' and result['human_origin_cryptographically_verified'] is False
    assert result['grants_deployment'] is False
    inputs.finish()


@pytest.mark.parametrize('issue',['fake-decision','missing-ui','stale-source','wrong-summary','post-execution','duplicate','signed-without-policy'])
def test_design_approval_rejects_spoofing(tmp_path,issue):
    f=approval_fixture(tmp_path);approvals=f['approvals'];kwargs={}
    if issue=='missing-ui':approvals=approvals.model_copy(update={'chat':[p for i,p in enumerate(approvals.chat) if i!=2]})
    elif issue=='duplicate':approvals=approvals.model_copy(update={'chat':[*approvals.chat,approvals.chat[0]]})
    elif issue=='post-execution':kwargs['before_execution']=datetime.now(timezone.utc)-timedelta(hours=1)
    elif issue=='signed-without-policy':f['change']['approvals']={'mode':'signed-external','assurance':'signed','stages':['plan','architecture','ui','implementation','qa']}
    else:
        pair=approvals.chat[2]
        if issue=='fake-decision':pair.decision.sha256='a'*64
        elif issue=='stale-source':
            value=json.loads((f['root']/pair.decision.path).read_text());value['source_digest']='a'*64
            pair.decision=type(pair.decision).model_validate(f['put'](pair.decision.path,value))
        else:
            request=json.loads((f['root']/pair.request.path).read_text());request['summary']='Approved without showing the actual design packet.'
            pair.request=type(pair.request).model_validate(f['put'](pair.request.path,request))
    with pytest.raises((HarnessError,ValidationError)):
        _approvals_v2(InputsV2(f['root']),parse_change(f['change']),f['task'],approvals,f['parsed_plan'],stage='implementation',source=f['baseline'],**kwargs)


def test_ui_schema_is_additive_and_exact():
    from algooptionx_harness.ui_validation import UIExecutionPlan
    root=Path(__file__).resolve().parents[2]
    assert json.loads((root/'src/algooptionx_harness/schemas/ui-execution.schema.json').read_text())==UIExecutionPlan.model_json_schema()


def test_measurement_declaration_is_not_native_execution(tmp_path):
    from algooptionx_harness.ui_validation import verify_measurement
    f=execution_fixture(tmp_path);plan,spec,_=load_plan(f['root'],parse_change(f['change']))
    with pytest.raises((HarnessError,ValidationError,ValueError)):
        verify_measurement(f['root'],plan,spec)


def test_native_ui_measurement_actually_executes(tmp_path,monkeypatch):
    """Actual isolated synthetic browser run, not a human-approved baseline/pilot."""
    import shutil,subprocess,os
    from algooptionx_harness.ui_validation import font_fingerprint,ui_check,verify_ui_run,UIReference
    from algooptionx_harness.runner import run_task,verify_evidence
    from algooptionx_harness.models import Check
    from algooptionx_harness.workspace import file_digest,write_json
    source=Path(__file__).resolve().parents[2]
    f=execution_fixture(tmp_path);root=f['root']
    with (root/'.gitignore').open('a') as stream:stream.write('\nnode_modules\n.venv\napps/web/dist/\napps/web/playwright-report/\napps/web/test-results/\n')
    shutil.copy(source/'pyproject.toml',root/'pyproject.toml')
    shutil.copytree(source/'src/algooptionx',root/'src/algooptionx')
    for name in ['src','tests','dist']:
        shutil.copytree(source/'apps/web'/name,root/'apps/web'/name,dirs_exist_ok=True)
    shutil.copy(source/'apps/web/package.json',root/'apps/web/package.json')
    shutil.copy(source/'apps/web/playwright.config.ts',root/'apps/web/playwright.config.ts')
    (root/'apps/web/node_modules').symlink_to(source/'apps/web/node_modules',target_is_directory=True)
    (root/'.venv').symlink_to(source/'.venv',target_is_directory=True)
    browser=os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE') or subprocess.check_output(['node','-e',"process.stdout.write(require('playwright').chromium.executablePath())"],cwd=source/'apps/web',text=True).strip()
    version=subprocess.check_output([browser,'--version'],text=True).split()[1]
    spec=f['spec'];spec['renderer'].update(version=version,fonts_sha256=font_fingerprint());spec['performance_budgets'][0].update(maximum=10000.0,method='raf-theme-toggle-v1')
    f['change']['design_link']['reference']=f['put']('docs/design-package.json',spec)
    f['change']['design_link']['record_digest']=digest(DesignSpec.model_validate_json(json.dumps(spec)))
    plan=copy.deepcopy(f['plan']);plan.update(mode='measure',measurement_baseline=None,renderer=spec['renderer'],design=f['change']['design_link'])
    f['put']('docs/changes/CHANGE-001/r0001/ui-execution.json',plan);f['put']('docs/changes/CHANGE-001/r0001/change.json',f['change'])
    f['put']('tests/test_ui_contract.py',"from pathlib import Path\nfrom algooptionx_harness.ui_validation import read_plan\ndef test_measurement_is_not_approval():\n p,r=read_plan(Path.cwd(),Path('docs/changes/CHANGE-001/r0001/ui-execution.json'))\n assert p.mode=='measure'\n r.finish()\n")
    baseline=snapshot(root);parsed=UIExecutionPlan.model_validate_json(json.dumps(plan))
    checks=[Check(id='python',kind='pytest',argv=[str(source/'.venv/bin/python'),'-m','pytest','tests/test_ui_contract.py','-q','--junitxml={run_dir}/pytest.xml'],report='{run_dir}/pytest.xml'),ui_check(parsed)]
    task=Task(schema_version=1,id='MEASURE-UI',title='Actual isolated synthetic measurement, no human approval',implementer='agent:synthetic-test',requirement_ids=['REQ-001'],source_commit=baseline['commit'],baseline_digest=digest(baseline),allowed_paths=['docs/guide.md'],protected_inputs=['docs/design-package.json','docs/changes/CHANGE-001/r0001/ui-execution.json','apps/web/tests/visual-baselines/fixture/manifest.json','apps/web/tests/visual-baselines/fixture/ready.png'],ui_changes=True,checks=checks,acceptance=['Measure a synthetic scenario without accepting visual or performance budgets.'],rollback='Preserve synthetic evidence; remove only temporary fixture work.')
    monkeypatch.setenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE',browser)
    evidence_path=run_task(root,task,baseline,root/'.harness/runs')
    evidence=verify_evidence(root,task,baseline,evidence_path)
    report=evidence_path.parent/'ui-governance/ui-report.json'
    cases=verify_ui_run(root,parsed,DesignSpec.model_validate_json(json.dumps(spec)),task,evidence,evidence_path.relative_to(root),UIReference(path=report.relative_to(root).as_posix(),sha256=file_digest(report)),expected_plan_sha=file_digest(root/'docs/changes/CHANGE-001/r0001/ui-execution.json'))
    assert len(cases)==1 and cases[0].mode=='measure'
    assert next(a for a in cases[0].results if a.area=='visual').status=='unverified'
    assert next(a for a in cases[0].results if a.area=='performance').measurements[0].samples==2


def test_aggregate_capture_is_real_task_not_artifact_child(tmp_path):
    f=execution_fixture(tmp_path);root=f['root']
    out=capture_child(root,Path('docs/changes/CHANGE-001/r0001/change.json'),f['policy_pin'],'CHANGE-001-AGGREGATE')
    task,baseline=load_task(Path(out['task']))
    assert task.id=='CHANGE-001-AGGREGATE'
    assert task.allowed_paths==f['change']['allowed_paths']
    assert out['authorization']=='not_granted'
    with pytest.raises(HarnessError):capture_child(root,Path('docs/changes/CHANGE-001/r0001/change.json'),f['policy_pin'],'DESIGN-CHECK')


def test_ui_scope_cannot_map_research_change_to_unrelated_workspace(tmp_path):
    f=execution_fixture(tmp_path);change=copy.deepcopy(f['change']);change['allowed_paths']=['apps/web/src/features/research/pages/LivePage.tsx']
    with pytest.raises(HarnessError,match='UI_SCOPE_UNSUPPORTED'):load_plan(f['root'],parse_change(change))


def test_genuine_native_evidence_required_for_v2_acceptance(tmp_path):
    from algooptionx_harness.enforcement import verify_bundle,close_change
    f=execution_fixture(tmp_path);root=f['root']
    fake=f['put']('.harness/fake-bundle.json',{'schema_version':2,'kind':'change-bundle','approved':True,'status':'completed'})
    before=snapshot(root)
    for function in [verify_bundle,close_change]:
        with pytest.raises((HarnessError,ValidationError,ValueError)):
            function(root,Path('docs/changes/CHANGE-001/r0001/change.json'),f['policy_pin'],Path(fake['path']))
    assert snapshot(root)==before


def test_ui_schema_success_never_approves_execution(tmp_path):
    f=execution_fixture(tmp_path);plan=UIExecutionPlan.model_validate_json(json.dumps(f['plan']))
    assert not hasattr(plan,'approved')
    from algooptionx_harness.enforcement import ExecutionRequestV2
    with pytest.raises(ValidationError):ExecutionRequestV2.model_validate({'schema_version':2,'kind':'execution-request','approved':True})


def nonui_bundle_fixture(tmp_path):
    from algooptionx_harness.enforcement import aggregate_task,REVIEW_ROLES
    from algooptionx_harness.governance import execution_context
    from tests.control_plane.test_change_enforcement import native_fixture,store,ref
    from algooptionx_harness.models import Evidence,Handoff,ChatRequest,ChatDecision
    f=make_v2(tmp_path);root=f['root'];c=f['change'];c.update(design_link=None,design_obligations=None)
    c['children']=[c['children'][2],c['children'][3],c['children'][4]];c['children'][0]['depends_on']=[]
    c['children'][-1]['depends_on']=[{'id':x,'revision':1} for x in ['CHILD-001','TEST-CHECK']]
    c['selected_children']=c['execution_order']=[{'id':x['id'],'revision':1} for x in c['children']]
    template=f['template'];template['ui_changes']=False
    obligations=validate_change(root,root/'docs/changes/CHANGE-001/r0001/change.json',f['policy_pin'])
    from algooptionx_harness.governance import execution_checks
    template['checks']=execution_checks(template['allowed_paths'],obligations,None)
    c['children'][0]['task_template']=f['put'](c['children'][0]['task_template']['path'],template)
    f['put']('docs/changes/CHANGE-001/r0001/change.json',c)
    path=Path('docs/changes/CHANGE-001/r0001/change.json');change,obligations,plan,protected=execution_context(root,path,f['policy_pin'])
    child_capture=capture_child(root,path,f['policy_pin'],'CHILD-001')
    agg_capture=capture_child(root,path,f['policy_pin'],'CHANGE-001-AGGREGATE')
    task,baseline=load_task(Path(child_capture['task']));aggregate,_=load_task(Path(agg_capture['task']))
    child=native_fixture(root,task,baseline,baseline,'v2-child',obligations['required_gates'])
    agg=native_fixture(root,aggregate,baseline,baseline,'v2-aggregate',obligations['required_gates'])
    def fix_pre(native):
        evidence=Evidence.model_validate_json((root/native['evidence']['path']).read_text())
        for i,pair in enumerate(native['approvals']['chat'][:3]):
            request=ChatRequest.model_validate_json((root/pair['request']['path']).read_text()).model_copy(update={'requested_at':evidence.started_at-timedelta(seconds=30-i*5)})
            pair['request']=f['put'](pair['request']['path'],request)
            decision=chat.record(request,'approved','operator:synthetic-test').model_copy(update={'recorded_at':request.requested_at+timedelta(seconds=1)})
            pair['decision']=f['put'](pair['decision']['path'],decision)
    fix_pre(child);fix_pre(agg)
    source={'commit':baseline['commit'],'source_digest':digest(baseline)}
    common={'schema_version':2,'change_id':change.id,'change_revision':change.revision,'change_digest':digest(change),'policy_digest':change.policy.sha256,'before':source,'after':source,'child_revision':1,'design_record_digest':None}
    native_completion=f['put']('.harness/v2-child-completion.json',{**common,'kind':'native-implementation','child_id':'CHILD-001','task':child['task'],'baseline':child['baseline'],'candidate':child['candidate'],'evidence':child['evidence']})
    test_completion=f['put']('.harness/v2-test-completion.json',{**common,'kind':'test-evidence','child_id':'TEST-CHECK','task':child['task'],'baseline':child['baseline'],'evidence':child['evidence'],'ui_evidence':None})
    review=Handoff.model_validate_json((root/agg['review']['path']).read_text())
    record=f['put']('.harness/v2-review-record.json',{'schema_version':1,'kind':'review','change_id':change.id,'change_revision':1,'change_digest':digest(change),'policy_digest':change.policy.sha256,'source':source,'actor':review.actor,'implementer_contexts':[task.implementer,aggregate.implementer],'status':'completed','reproduced_checks':['Synthetic native consistency, not protected execution.'],'findings':[],'limitations':['Synthetic test decisions are not real human approval.'],'provenance':'declared-separate-context','attestation':None})
    review_completion=f['put']('.harness/v2-review-completion.json',{**common,'kind':'independent-review','subject':'candidate','child_id':'FINAL-REVIEW','review':record})
    bundle={'schema_version':2,'kind':'change-bundle','change_id':change.id,'change_revision':1,'change_digest':digest(change),'policy_digest':change.policy.sha256,'source':source,'children':[{'schema_version':2,'kind':'child-execution','completion':native_completion,'capture':ref(root,Path(child_capture['context'])),'approvals':{'chat':child['approvals']['chat'][:3]}},{'schema_version':2,'kind':'child-execution','completion':test_completion},{'schema_version':2,'kind':'child-execution','completion':review_completion,'handoff':agg['review']}],'aggregate':agg,'ui_evidence':None,'rollback_reference':f['put']('.harness/v2-rollback.json',{'instructions':'Reverse this temporary synthetic fixture only; preserve reports.'})}
    # QA binds a review which transitively pins all selected child evidence.
    review_value=Handoff.model_validate_json((root/agg['review']['path']).read_text())
    required=[agg['evidence'],bundle['rollback_reference']]
    for item in bundle['children']:
        required.append(item['completion'])
        if item.get('capture'):required.append(item['capture'])
        for pair in item.get('approvals',{}).get('chat',[]):required.extend([pair['request'],pair['decision']])
    from algooptionx_harness.models import Artifact
    review_value=review_value.model_copy(update={'artifacts':[Artifact(**ref) for ref in required]})
    agg['review'].update(f['put'](agg['review']['path'],review_value))
    evidence_model=Evidence.model_validate_json((root/agg['evidence']['path']).read_text())
    qa=agg['approvals']['chat'][-1]
    request=ChatRequest.model_validate_json((root/qa['request']['path']).read_text()).model_copy(update={'evidence_digest':digest({'validation':digest(evidence_model),'independent_review':agg['review']['sha256']})})
    qa['request']=f['put'](qa['request']['path'],request)
    decision=chat.record(request,'approved','operator:synthetic-test').model_copy(update={'recorded_at':request.requested_at+timedelta(seconds=1)})
    qa['decision']=f['put'](qa['decision']['path'],decision)
    bundle_ref=f['put']('.harness/v2-bundle.json',bundle)
    f.update(bundle=bundle,bundle_ref=bundle_ref,path=path)
    return f


def test_v2_typed_acceptance_and_archive_are_distinct_local_checks(tmp_path):
    from algooptionx_harness.enforcement import verify_bundle,close_change
    f=nonui_bundle_fixture(tmp_path);root=f['root'];before=snapshot(root);args=(root,f['path'],f['policy_pin'],Path(f['bundle_ref']['path']))
    result=verify_bundle(*args)
    assert result['status']=='verified_local_acceptance' and result['grants_deployment'] is False
    assert result['protected_execution_provenance']=='NOT VERIFIED'
    with pytest.raises((HarnessError,OSError)):close_change(*args,archive=True)
    accepted=close_change(*args)
    assert (Path(accepted['closure_path'])/'acceptance.json').is_file()
    assert close_change(*args,archive=True)['archived'] is True
    with pytest.raises((HarnessError,OSError)):close_change(*args,archive=True)
    assert snapshot(root)==before


@pytest.mark.parametrize('issue',['missing-child','reordered','wrong-source','fake-reply','qa-before-evidence','same-reviewer','old-capture','omitted-critical','failed-evidence'])
def test_v2_acceptance_rejects_native_bypasses(tmp_path,issue):
    from algooptionx_harness.enforcement import verify_bundle
    from tests.control_plane.test_change_enforcement import rewrite
    f=nonui_bundle_fixture(tmp_path);b=f['bundle'];root=f['root']
    if issue=='missing-child':b['children'].pop()
    elif issue=='reordered':b['children'].reverse()
    elif issue=='wrong-source':b['source']['source_digest']='a'*64
    elif issue=='fake-reply':rewrite(root,b['aggregate']['approvals']['chat'][-1]['decision'],lambda x:x.update(user_message='I never approved this'))
    elif issue=='qa-before-evidence':rewrite(root,b['aggregate']['approvals']['chat'][-1]['request'],lambda x:x.update(requested_at='2000-01-01T00:00:00Z'))
    elif issue=='same-reviewer':rewrite(root,b['aggregate']['review'],lambda x:x.update(actor='agent:fixture'))
    elif issue=='old-capture':b['children'][0]['capture']['sha256']='a'*64
    elif issue=='omitted-critical':rewrite(root,b['aggregate']['task'],lambda x:x['checks'].pop())
    else:rewrite(root,b['aggregate']['evidence'],lambda x:x.update(status='failed'))
    f['put'](f['bundle_ref']['path'],b)
    with pytest.raises((HarnessError,ValidationError,ValueError)):
        verify_bundle(root,f['path'],f['policy_pin'],Path(f['bundle_ref']['path']))


def test_readiness_requires_verified_bundle_not_state_label(tmp_path):
    from algooptionx_harness.lifecycle import inspect_lifecycle
    f=nonui_bundle_fixture(tmp_path);root=f['root']
    plain=inspect_lifecycle(root,f['path'],f['policy_pin'])
    assert plain['acceptance_readiness'].startswith('NOT VERIFIED')
    verified=inspect_lifecycle(root,f['path'],f['policy_pin'],bundle=Path(f['bundle_ref']['path']))
    assert verified['acceptance_readiness']=='verified_local_prerequisites'
    assert verified['transition_permitted'] is False and verified['authorization']=='not_granted'


def test_financial_frontend_policy_is_conservative():
    source=Path(__file__).resolve().parents[2]
    policy=json.loads((source/'config/engineering-governance.json').read_text())
    rule=next(r for r in policy['path_rules'] if r['prefix']=='apps/web/src/')
    assert rule['minimum_risk']=='R2'
    assert set(rule['gates'])=={'FINANCIAL','SECURITY','CAUSAL-DATA'}


def test_metric_method_cannot_claim_unexecuted_algorithm(tmp_path):
    f=execution_fixture(tmp_path)
    f['spec']['performance_budgets'][0]['method']='unexecuted-arbitrary-algorithm'
    f['change']['design_link']['reference']=f['put']('docs/design-package.json',f['spec'])
    f['change']['design_link']['record_digest']=digest(DesignSpec.model_validate_json(json.dumps(f['spec'])))
    f['plan']['design']=f['change']['design_link']
    f['put']('docs/changes/CHANGE-001/r0001/ui-execution.json',f['plan'])
    with pytest.raises(HarnessError,match='method differs'):load_plan(f['root'],parse_change(f['change']))


def test_closure_rejects_symlinked_output_ancestor(tmp_path):
    from algooptionx_harness.enforcement import close_change
    f=nonui_bundle_fixture(tmp_path);root=f['root'];outside=tmp_path/'outside';outside.mkdir()
    target=root/'.harness/changes/CHANGE-001'
    assert not target.exists()
    target.parent.mkdir(parents=True,exist_ok=True)
    target.symlink_to(outside,target_is_directory=True)
    with pytest.raises(HarnessError):close_change(root,f['path'],f['policy_pin'],Path(f['bundle_ref']['path']))
    assert list(outside.iterdir())==[]


def test_secure_closure_writer_rejects_nested_symlink(tmp_path):
    from algooptionx_harness.enforcement import _secure_v2_record
    root=tmp_path/'root';root.mkdir();outside=tmp_path/'outside';outside.mkdir()
    (root/'link').symlink_to(outside,target_is_directory=True)
    with pytest.raises(HarnessError):_secure_v2_record(root,root/'link/acceptance.json',{'status':'synthetic'})
    assert list(outside.iterdir())==[]


@pytest.mark.parametrize('which',['task','baseline'])
def test_worker_rejects_authorized_task_or_baseline_substitution(tmp_path,monkeypatch,which):
    from algooptionx_harness import orchestration,enforcement
    f=execution_fixture(tmp_path);root=f['root']
    out=capture_child(root,Path('docs/changes/CHANGE-001/r0001/change.json'),f['policy_pin'],'CHILD-001')
    task,baseline=load_task(Path(out['task']))
    monkeypatch.setattr(orchestration,'dispatch',lambda *a,**k:{'role':{'sandbox':'workspace-write'},'instruction':''})
    auth={'governed_request':'synthetic-request.json','governed_change':'synthetic-change.json','governed_policy_sha256':'0'*64}
    checked={'status':'verified','task_digest':digest(task),'baseline_digest':digest(baseline)}
    checked[which+'_digest']='f'*64
    monkeypatch.setattr(enforcement,'authorize_v2',lambda *a,**k:checked)
    with pytest.raises(HarnessError,match='task/baseline differs'):
        orchestration.codex_worker(root,task,baseline,'frontend-engineer',root/'.harness/agents/synthetic',auth)


def test_failed_ui_attachments_are_hashed_without_passing_index(tmp_path):
    from algooptionx_harness.ui_validation import collect_ui_artifacts
    from algooptionx_harness.workspace import write_json,file_digest
    root=tmp_path/'root';run=root/'.harness/runs/failure';run.mkdir(parents=True)
    trace=run/'trace.zip';trace.write_bytes(b'PK synthetic failed trace')
    image=run/'diff.png';image.write_bytes(b'\x89PNG synthetic failed diff')
    report=run/'playwright.json'
    write_json(report,{'suites':[{'specs':[{'tests':[{'results':[{'status':'failed','attachments':[{'name':'trace','path':str(trace)},{'name':'diff','path':str(image)}]}]}]}]}]})
    artifacts=collect_ui_artifacts(root,None,None,{'cases':[{'id':'NOT-COMPLETED'}]},run,report,successful=False)
    assert {a.path:a.sha256 for a in artifacts}=={'trace.zip':file_digest(trace),'diff.png':file_digest(image)}
    assert not (run/'ui-report.json').exists()

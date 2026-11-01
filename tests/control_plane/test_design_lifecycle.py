"""UI/UX v2 declaration tests. Synthetic records are never approval or execution."""
from __future__ import annotations
import copy
import json
import subprocess
from pathlib import Path
import pytest
from pydantic import ValidationError
from algooptionx_harness.changes import ChangeSpec, ChangeSpecV2, parse_change
from algooptionx_harness.designs import DesignSpec, validate_design
from algooptionx_harness.governance import validate_change
from algooptionx_harness.workspace import digest, snapshot, file_digest, write_json, HarnessError
from tests.control_plane.test_design_contracts import make_design

ROOT = Path(__file__).resolve().parents[2]


def make_v2(tmp_path):
    f = make_design(tmp_path)
    change = copy.deepcopy(f['change'])
    native = change['children'][0]
    native.update(kind='native-implementation', required=True, acceptance_ids=['ACC-001'], depends_on=[{'id':'DESIGN-REVIEW','revision':1}])
    common = {'revision':1,'required':True,'requirement_ids':['REQ-001'],'acceptance_ids':['ACC-001'],'skills':['implementation']}
    children = [
        {**common,'id':'DESIGN-CHECK','kind':'design-validation','roles':['ui-designer'],'depends_on':[]},
        {**common,'id':'DESIGN-REVIEW','kind':'independent-review','subject':'design','roles':['independent-validator'],'depends_on':[{'id':'DESIGN-CHECK','revision':1}]},
        native,
        {**common,'id':'TEST-CHECK','kind':'test-evidence','roles':['test-engineer'],'depends_on':[{'id':native['id'],'revision':1}]},
        {**common,'id':'FINAL-REVIEW','kind':'independent-review','subject':'candidate','roles':['independent-validator'],'depends_on':[{'id':c,'revision':1} for c in ['DESIGN-CHECK','DESIGN-REVIEW',native['id'],'TEST-CHECK']]},
    ]
    selected=[{'id':c['id'],'revision':1} for c in children]
    change.update(schema_version=2,kind='change-spec',children=children,selected_children=selected,execution_order=copy.deepcopy(selected),candidate_review_child='FINAL-REVIEW',design_link={'id':f['spec']['id'],'revision':1,'reference':f['spec_ref'],'record_digest':digest(DesignSpec.model_validate_json(json.dumps(f['spec'])))},design_obligations={'case_ids':['CASE-001'],'required_areas':['accessibility','responsive','visual','performance'],'validation_children':['DESIGN-CHECK'],'design_review_child':'DESIGN-REVIEW','candidate_evidence_children':['TEST-CHECK']})
    template=f['template']
    template['protected_inputs']=sorted(set(template['protected_inputs'])|{'docs/wireframe.svg','docs/fixture.json','apps/web/src/tokens.css'})
    native['task_template']=f['put'](native['task_template']['path'],template)
    f['change']=change
    f['put']('docs/changes/CHANGE-001/r0001/change.json',change)
    return f


def test_v2_and_v1_contract_compatibility(tmp_path):
    f=make_v2(tmp_path)
    assert isinstance(parse_change(f['change']),ChangeSpecV2)
    (tmp_path/'legacy').mkdir()
    f1=make_design(tmp_path/'legacy')
    assert isinstance(parse_change(f1['change']),ChangeSpec)
    no_version=copy.deepcopy(f1['change']);no_version.pop('schema_version',None)
    assert isinstance(parse_change(no_version),ChangeSpec)
    schema=json.loads((ROOT/'src/algooptionx_harness/schemas/change-v2.schema.json').read_text())
    assert schema==ChangeSpecV2.model_json_schema()
    for p in (ROOT/'src/algooptionx_harness/schemas').glob('*.json'):
        if p.name!='change-v2.schema.json':
            assert p.read_bytes()==subprocess.check_output(['git','-C',str(ROOT),'show','HEAD:'+p.relative_to(ROOT).as_posix()])


@pytest.mark.parametrize('issue',['version','bool-version','missing-version','extra','bool-revision','bool-required','unknown-kind','missing-child','cycle','missing-dependency','stale-dependency','order','selection','unselected-dependency','duplicate-child','unknown-requirement','unknown-acceptance','missing-review','review-subject','review-dependencies','missing-design','design-digest','design-obligations','design-type','design-review-order'])
def test_v2_invalid_contracts(tmp_path,issue):
    f=make_v2(tmp_path);c=copy.deepcopy(f['change'])
    if issue=='version':c['schema_version']=3
    elif issue=='bool-version':c['schema_version']=True
    elif issue=='missing-version':del c['schema_version']
    elif issue=='extra':c['approved']=True
    elif issue=='bool-revision':c['revision']=True
    elif issue=='bool-required':c['children'][0]['required']=1
    elif issue=='unknown-kind':c['children'][0]['kind']='execute-design'
    elif issue=='missing-child':c['children'].pop()
    elif issue=='cycle':c['children'][0]['depends_on']=[{'id':'FINAL-REVIEW','revision':1}]
    elif issue=='missing-dependency':c['children'][0]['depends_on']=[{'id':'CHILD-404','revision':1}]
    elif issue=='stale-dependency':c['children'][1]['depends_on'][0]['revision']=2
    elif issue=='order':c['execution_order'].reverse()
    elif issue=='selection':c['selected_children'].pop()
    elif issue=='unselected-dependency':
        c['children'][0]['required']=False;c['selected_children'].pop(0);c['execution_order'].pop(0)
    elif issue=='duplicate-child':c['children'].append(copy.deepcopy(c['children'][0]))
    elif issue=='unknown-requirement':c['children'][0]['requirement_ids']=['REQ-OTHER']
    elif issue=='unknown-acceptance':c['children'][0]['acceptance_ids']=['ACC-OTHER']
    elif issue=='missing-review':c['candidate_review_child']='CHILD-404'
    elif issue=='review-subject':c['children'][-1]['subject']='design'
    elif issue=='review-dependencies':c['children'][-1]['depends_on']=[]
    elif issue=='missing-design':c['design_link']=None
    elif issue=='design-digest':c['design_link']['record_digest']='bad'
    elif issue=='design-obligations':c['design_obligations']['required_areas']=['visual']
    elif issue=='design-type':c['design_obligations']['validation_children']=['CHILD-001']
    elif issue=='design-review-order':c['children'][2]['depends_on']=[]
    with pytest.raises((ValidationError,ValueError)):
        parse_change(c)


def test_optional_selection_is_explicit(tmp_path):
    f=make_v2(tmp_path);c=f['change'];optional=copy.deepcopy(c['children'][3]);optional.update(id='OPTIONAL-CHECK',required=False)
    c['children'].append(optional)
    assert 'OPTIONAL-CHECK' not in {x.id for x in parse_change(c).selected_children}
    changed=copy.deepcopy(c);changed['selected_children'].insert(-1,{'id':'OPTIONAL-CHECK','revision':1});changed['execution_order'].insert(-1,{'id':'OPTIONAL-CHECK','revision':1})
    changed['children'][4]['depends_on'].append({'id':'OPTIONAL-CHECK','revision':1})
    assert digest(parse_change(changed))!=digest(parse_change(c))


def captured_v2(f):
    from algooptionx_harness.models import Task
    baseline=snapshot(f['root'])
    task=Task.model_validate({**f['template'],'source_commit':baseline['commit'],'baseline_digest':digest(baseline)})
    task_ref=f['put']('.harness/task/task.json',task)
    baseline_ref=f['put']('.harness/task/baseline.json',baseline)
    source={'commit':baseline['commit'],'source_digest':digest(baseline)}
    binding=copy.deepcopy(f['binding'])
    binding.update(change_digest=digest(parse_change(f['change'])),source=source,native_task_reference=task_ref,native_task_digest=digest(task),baseline_reference=baseline_ref,baseline_digest=digest(baseline),approvals=[],change_reference={'path':'docs/changes/CHANGE-001/r0001/change.json','sha256':file_digest(f['root']/'docs/changes/CHANGE-001/r0001/change.json')})
    f['put']('.harness/binding.json',binding)
    native=json.loads((f['root']/f['evidence']['native_evidence_reference']['path']).read_text())
    native.update(task_digest=digest(task),source_digest=digest(baseline),final_source_digest=digest(baseline),source_commit=baseline['commit'])
    evidence=copy.deepcopy(f['evidence'])
    evidence.update(change_digest=digest(parse_change(f['change'])),source=source,native_task_reference=task_ref,native_task_digest=digest(task),native_evidence_reference=f['put']('.harness/run/evidence.json',native))
    f['put']('.harness/ui-evidence.json',evidence)
    f.update(task=task,baseline=baseline,binding=binding,evidence=evidence)
    return f


def validate_fixture(f):
    return validate_change(f['root'],f['root']/'docs/changes/CHANGE-001/r0001/change.json',f['policy_pin'])


def test_v2_pinned_design_and_existing_bindings(tmp_path):
    f=captured_v2(make_v2(tmp_path))
    result=validate_fixture(f)
    assert result['change_schema_version']==2
    assert result['dependency_graph']['order']==[x['id'] for x in f['change']['execution_order']]
    assert result['authorization']=='not_granted'
    for path in ['.harness/binding.json','.harness/ui-evidence.json']:
        result=validate_design(f['root'],Path(path),f['policy_pin'])
        assert result['status']=='DESIGN CONTRACT VALID'
        assert result['implementation_authorized'] is False


@pytest.mark.parametrize('issue',['design-hash','design-digest','design-revision','requirement','mockup','missing-artifact','policy','cases','areas','protected','template-authority','scope','native-id','self-reference'])
def test_v2_linkage_rejects_stale_inputs(tmp_path,issue):
    f=make_v2(tmp_path);c=f['change']
    if issue=='design-hash':c['design_link']['reference']['sha256']='a'*64
    elif issue=='design-digest':c['design_link']['record_digest']='b'*64
    elif issue=='design-revision':c['design_link']['revision']=2
    elif issue=='requirement':
        ref=f['put']('docs/alternative.md','# REQ-001\nA different requirement with the same ID.')
        c['requirements'][0].update(ref)
    elif issue=='mockup':(f['root']/'docs/wireframe.svg').write_text('Changed after capture')
    elif issue=='missing-artifact':(f['root']/'docs/wireframe.svg').unlink()
    elif issue=='policy':c['policy']['revision']=2
    elif issue=='cases':c['design_obligations']['case_ids']=['CASE-OTHER']
    elif issue=='areas':
        spec=copy.deepcopy(f['spec']);spec['validation_cases'][0]['checks']=['visual']
        c['design_link']['reference']=f['put']('docs/design-package.json',spec)
        c['design_link']['record_digest']=digest(DesignSpec.model_validate_json(json.dumps(spec)))
    elif issue in {'protected','template-authority','scope','native-id'}:
        template=copy.deepcopy(f['template'])
        if issue=='protected':template['protected_inputs'].remove('docs/wireframe.svg')
        elif issue=='template-authority':template['baseline_digest']='a'*64
        elif issue=='scope':template['allowed_paths']=['src/algooptionx/paper/engine.py']
        elif issue=='native-id':template['id']='CHILD-OTHER'
        c['children'][2]['task_template']=f['put'](c['children'][2]['task_template']['path'],template)
    elif issue=='self-reference':c['design_link']['reference']['path']='docs/changes/CHANGE-001/r0001/change.json'
    f['put']('docs/changes/CHANGE-001/r0001/change.json',c)
    with pytest.raises((HarnessError,ValidationError,ValueError)):
        validate_fixture(f)


def test_v2_non_ui_and_web_cannot_hide_design(tmp_path):
    f=make_v2(tmp_path);c=f['change']
    c.update(design_link=None,design_obligations=None)
    c['children']=[c['children'][2],c['children'][3],c['children'][4]]
    c['children'][0]['depends_on']=[]
    c['children'][-1]['depends_on']=[{'id':x,'revision':1} for x in ['CHILD-001','TEST-CHECK']]
    c['selected_children']=c['execution_order']=[{'id':x['id'],'revision':1} for x in c['children']]
    template=copy.deepcopy(f['template']);template['ui_changes']=False
    c['children'][0]['task_template']=f['put'](c['children'][0]['task_template']['path'],template)
    f['put']('docs/changes/CHANGE-001/r0001/change.json',c)
    assert validate_fixture(f)['design_required'] is False
    c['allowed_paths']=['docs/guide.md','apps/web/'];c['affected_components']=['DOCUMENTATION','WEB']
    f['put']('docs/changes/CHANGE-001/r0001/change.json',c)
    with pytest.raises(HarnessError):validate_fixture(f)


from datetime import datetime, timedelta, timezone
from algooptionx_harness.lifecycle import inspect_lifecycle, LifecycleEventV2, PROGRESSION
from algooptionx_harness.models import Task


def completed_fixture(tmp_path,writer_change=False):
    f=captured_v2(make_v2(tmp_path));root=f['root'];change=parse_change(f['change'])
    before={'commit':f['baseline']['commit'],'source_digest':digest(f['baseline'])}
    design_report=validate_design(root,Path('docs/design-package.json'),f['policy_pin'])
    if writer_change:(root/'docs/guide.md').write_text('A scoped synthetic implementation result.\n')
    candidate=snapshot(root);after={'commit':candidate['commit'],'source_digest':digest(candidate)}
    native=json.loads((root/'.harness/run/evidence.json').read_text())
    native.update(source_digest=digest(candidate),final_source_digest=digest(candidate),changed_paths=['docs/guide.md'] if writer_change else [])
    native_ref=f['put']('.harness/run/evidence.json',native)
    ui=copy.deepcopy(f['evidence']);ui.update(source=after,native_evidence_reference=native_ref)
    ui_ref=f['put']('.harness/ui-evidence.json',ui)
    candidate_ref=f['put']('.harness/task/candidate.json',candidate)
    task_ref={'path':'.harness/task/task.json','sha256':file_digest(root/'.harness/task/task.json')}
    baseline_ref={'path':'.harness/task/baseline.json','sha256':file_digest(root/'.harness/task/baseline.json')}
    common={'schema_version':2,'change_id':change.id,'change_revision':change.revision,'change_digest':digest(change),'policy_digest':change.policy.sha256,'design_record_digest':change.design_link.record_digest}
    def review(subject,source):
        return f['put'](f'.harness/{subject}-review.json',{'schema_version':1,'kind':'review','change_id':change.id,'change_revision':change.revision,'change_digest':digest(change),'policy_digest':change.policy.sha256,'source':source,'actor':'agent:separate-synthetic-reviewer','implementer_contexts':['agent:fixture'],'status':'completed','reproduced_checks':['Synthetic declarations only; no actual execution.'],'findings':[],'limitations':['No protected identity or trusted execution; synthetic fixture only.'],'provenance':'declared-separate-context','attestation':None})
    records={
        'DESIGN-CHECK':{**common,'kind':'design-validation','before':before,'after':before,'report':f['put']('.harness/design-report.json',design_report)},
        'DESIGN-REVIEW':{**common,'kind':'independent-review','subject':'design','before':before,'after':before,'review':review('design',before)},
        'CHILD-001':{**common,'kind':'native-implementation','before':before,'after':after,'task':task_ref,'baseline':baseline_ref,'candidate':candidate_ref,'evidence':native_ref},
        'TEST-CHECK':{**common,'kind':'test-evidence','before':after,'after':after,'baseline':baseline_ref,'task':task_ref,'evidence':native_ref,'ui_evidence':ui_ref},
        'FINAL-REVIEW':{**common,'kind':'independent-review','subject':'candidate','before':after,'after':after,'review':review('candidate',after)},
    }
    refs={}
    for cid,record in records.items():
        record.update(child_id=cid,child_revision=1)
        refs[cid]=f['put'](f'.harness/completions/{cid}.json',record)
    f.update(records=records,completion_refs=refs,before=before,after=after)
    return f


def history(f,stop='accepted',mutate=None):
    c=parse_change(f['change']);previous=None;events=[]
    role_map={'requirements-validated':'requirements-validator','design-reviewed':'architect','approved-for-scoped-implementation':'human-owner','in-progress':'backend-engineer','independently-reviewed':'independent-validator','accepted':'human-owner','archived':'release-governor'}
    for index,target in enumerate(PROGRESSION):
        role=role_map.get(target,'product')
        done=set()
        if index>=2:done|={'DESIGN-CHECK','DESIGN-REVIEW'}
        if index>=6:done.add('CHILD-001')
        if index>=7:done.add('TEST-CHECK')
        if index>=8:done.add('FINAL-REVIEW')
        raw={'schema_version':2,'kind':'lifecycle-event','transition':{'schema_version':1,'kind':'transition','change_id':c.id,'change_revision':c.revision,'change_digest':digest(c),'policy_digest':c.policy.sha256,'source':f['after'] if index>=7 else f['before'],'event_id':f'fixture-event-{index:06d}','previous_record_digest':digest(previous) if previous else None,'from_state':previous.transition.to_state if previous else None,'to_state':target,'actor':c.owner if role=='human-owner' else 'agent:synthetic-fixture','recorded_at':(datetime.now(timezone.utc)-timedelta(hours=1)+timedelta(seconds=index)).isoformat(),'reason':'Synthetic structural history only; no authority.','evidence':[]},'actor_role':role,'operation':'advance','children':[{'id':ref.id,'revision':ref.revision,'status':'completed' if ref.id in done else 'pending','completion':f['completion_refs'][ref.id] if ref.id in done else None} for ref in c.selected_children]}
        if mutate:mutate(raw,index)
        event=LifecycleEventV2.model_validate_json(json.dumps(raw));events.append(event)
        f['put'](f'.harness/changes/{c.id}/r{c.revision:04d}/v2/events/{index+1:06d}.json',event)
        previous=event
        if target==stop:break
    return events


@pytest.mark.parametrize('writer_change',[False,True])
def test_complete_v2_history_is_structure_only(tmp_path,writer_change):
    f=completed_fixture(tmp_path,writer_change);history(f)
    before=snapshot(f['root'])
    result=inspect_lifecycle(f['root'],Path('docs/changes/CHANGE-001/r0001/change.json'),f['policy_pin'])
    assert result['recorded_state']=='accepted'
    assert result['children']['all_completed'] is True
    assert result['history_gates_verified'] is False
    assert result['execution_verified'] is False
    assert result['transition_permitted'] is False
    assert result['authorization']=='not_granted'
    assert snapshot(f['root'])==before


@pytest.mark.parametrize('issue',['wrong-kind','wrong-child','wrong-parent','wrong-policy','wrong-design','readonly-write','native-baseline','native-evidence','native-task','missing-ui','missing-cases','fake-report','self-review','omitted-implementer','failed-review','unknown-field'])
def test_typed_completion_rejects_spoofing(tmp_path,issue):
    f=completed_fixture(tmp_path);cid='CHILD-001';rec=f['records'][cid]
    if issue=='wrong-kind':rec['kind']='test-evidence'
    elif issue=='wrong-child':rec['child_id']='CHILD-OTHER'
    elif issue=='wrong-parent':rec['change_digest']='a'*64
    elif issue=='wrong-policy':rec['policy_digest']='a'*64
    elif issue=='wrong-design':rec['design_record_digest']='a'*64
    elif issue=='readonly-write':cid='TEST-CHECK';rec=f['records'][cid];rec['after']['source_digest']='a'*64
    elif issue=='native-baseline':rec['baseline']['sha256']='a'*64
    elif issue=='native-evidence':
        value=json.loads((f['root']/rec['evidence']['path']).read_text());value['results']=[]
        rec['evidence']=f['put']('.harness/run/evidence.json',value)
    elif issue=='native-task':rec['task']['sha256']='a'*64
    elif issue=='missing-ui':cid='TEST-CHECK';rec=f['records'][cid];rec['ui_evidence']=None
    elif issue=='missing-cases':
        cid='TEST-CHECK';rec=f['records'][cid];ui=copy.deepcopy(f['evidence']);ui['executed_cases']=[]
        rec['ui_evidence']=f['put']('.harness/ui-evidence.json',ui)
    elif issue=='fake-report':cid='DESIGN-CHECK';rec=f['records'][cid];rec['report']=f['put']('.harness/fake-report.json',{'status':'passed','approved':True})
    elif issue in {'self-review','omitted-implementer','failed-review'}:
        cid='FINAL-REVIEW';rec=f['records'][cid];review=json.loads((f['root']/rec['review']['path']).read_text())
        if issue=='self-review':review['actor']='agent:fixture'
        elif issue=='omitted-implementer':review['implementer_contexts']=['agent:someone-else']
        else:review['status']='blocked'
        rec['review']=f['put']('.harness/candidate-review.json',review)
    elif issue=='unknown-field':rec['approved']=True
    f['completion_refs'][cid]=f['put'](f'.harness/completions/{cid}.json',rec)
    history(f)
    with pytest.raises((HarnessError,ValidationError,ValueError)):
        inspect_lifecycle(f['root'],Path('docs/changes/CHANGE-001/r0001/change.json'),f['policy_pin'])


@pytest.mark.parametrize('issue',['missing-child','duplicate-child','child-revision','design-bypass','early-implementation','fake-completion','digest-chain','owner','illegal-edge','stale-source','rewritten-completion'])
def test_v2_history_rejects_invalid_edges(tmp_path,issue):
    f=completed_fixture(tmp_path)
    def mutate(raw,index):
        if issue=='missing-child' and index==0:raw['children'].pop()
        elif issue=='duplicate-child' and index==0:raw['children'].append(copy.deepcopy(raw['children'][0]))
        elif issue=='child-revision' and index==0:raw['children'][0]['revision']=2
        elif issue=='design-bypass' and index==2:
            for child in raw['children']:child.update(status='pending',completion=None)
        elif issue=='early-implementation' and index==2:raw['children'][2].update(status='completed',completion=f['completion_refs']['CHILD-001'])
        elif issue=='fake-completion' and index==6:raw['children'][2]['completion']=f['put']('.harness/fake-completion.json',{'status':'completed'})
        elif issue=='digest-chain' and index==1:raw['transition']['previous_record_digest']='a'*64
        elif issue=='owner' and index==5:raw['transition']['actor']='human:impostor'
        elif issue=='illegal-edge' and index==1:raw['transition']['to_state']='accepted'
        elif issue=='stale-source' and index==1:raw['transition']['source']={**raw['transition']['source'],'source_digest':'a'*64}
        elif issue=='rewritten-completion' and index==3:
            raw['children'][0]['completion']=f['put']('.harness/renamed-completion.json',f['records']['DESIGN-CHECK'])
    history(f,mutate=mutate)
    with pytest.raises((HarnessError,ValidationError,ValueError)):
        inspect_lifecycle(f['root'],Path('docs/changes/CHANGE-001/r0001/change.json'),f['policy_pin'])


def test_v2_transition_request_remains_blocked(tmp_path):
    f=make_v2(tmp_path);c=parse_change(f['change']);f.update(before={'commit':snapshot(f['root'])['commit'],'source_digest':digest(snapshot(f['root']))},after={'commit':snapshot(f['root'])['commit'],'source_digest':digest(snapshot(f['root']))},completion_refs={})
    event=history(f,stop='draft')[0]
    (f['root']/'.harness/changes/CHANGE-001/r0001/v2/events/000001.json').unlink()
    req=f['put']('.harness/changes/CHANGE-001/r0001/v2/requests/draft.json',event)
    result=inspect_lifecycle(f['root'],Path('docs/changes/CHANGE-001/r0001/change.json'),f['policy_pin'],Path(req['path']))
    assert result['status']=='blocked'
    assert 'uiux:v2-enforcement-not-implemented' in result['missing_prerequisites']


@pytest.mark.parametrize('issue',['legacy-event','unsupported-event','duplicate-event','missing-number','symlink-event','oversized-event'])
def test_v2_history_input_security(tmp_path,issue):
    f=completed_fixture(tmp_path);events=history(f,stop='requirements-validated')
    folder=f['root']/'.harness/changes/CHANGE-001/r0001/v2/events';path=folder/'000002.json'
    if issue=='legacy-event':
        value=events[-1].model_dump(mode='json');value['schema_version']=1;f['put'](str(path.relative_to(f['root'])),value)
    elif issue=='unsupported-event':
        value=events[-1].model_dump(mode='json');value['schema_version']=3;f['put'](str(path.relative_to(f['root'])),value)
    elif issue=='duplicate-event':
        value=events[-1].model_dump(mode='json');value['transition']['event_id']=events[0].transition.event_id;f['put'](str(path.relative_to(f['root'])),value)
    elif issue=='missing-number':path.rename(folder/'000003.json')
    elif issue=='symlink-event':path.unlink();path.symlink_to('/etc/passwd')
    else:path.write_bytes(b' '*(1024*1024+1))
    with pytest.raises((HarnessError,ValidationError,ValueError)):
        inspect_lifecycle(f['root'],Path('docs/changes/CHANGE-001/r0001/change.json'),f['policy_pin'])


def test_failed_child_is_visible_and_blocks_completion(tmp_path):
    f=completed_fixture(tmp_path)
    def fail(raw,index):
        if index==6:raw['children'][2].update(status='failed',completion=None)
    history(f,stop='in-progress',mutate=fail)
    result=inspect_lifecycle(f['root'],Path('docs/changes/CHANGE-001/r0001/change.json'),f['policy_pin'])
    assert result['children']['all_completed'] is False
    assert 'CHILD-001' in result['children']['not_completed']


@pytest.mark.parametrize('operation',['cancel','supersede','rollback'])
def test_v2_terminal_decisions_are_only_declarations(tmp_path,operation):
    f=completed_fixture(tmp_path);events=history(f,stop='accepted' if operation=='rollback' else 'in-progress');previous=events[-1];c=parse_change(f['change'])
    raw=previous.model_dump(mode='json');raw['operation']=operation;raw['actor_role']='human-owner'
    tr=raw['transition'];tr.update(event_id='synthetic-terminal-decision',previous_record_digest=digest(previous),from_state=previous.transition.to_state,to_state={'cancel':'cancelled','supersede':'superseded','rollback':'failed'}[operation],actor=c.owner,recorded_at=(previous.transition.recorded_at+timedelta(seconds=1)).isoformat())
    if operation=='supersede':
        successor=copy.deepcopy(f['change']);successor['revision']=2
        raw['successor']=f['put']('docs/changes/CHANGE-001/r0002/change.json',successor)
    if operation=='rollback':raw['rollback']=f['put']('.harness/rollback.md','Synthetic narrow rollback instructions; no rollback executed.')
    f['put'](f'.harness/changes/CHANGE-001/r0001/v2/events/{len(events)+1:06d}.json',raw)
    result=inspect_lifecycle(f['root'],Path('docs/changes/CHANGE-001/r0001/change.json'),f['policy_pin'])
    assert result['recorded_state']==tr['to_state']
    assert result['authorization']=='not_granted'
    assert result['execution_verified'] is False


from algooptionx_harness.cli import main


@pytest.mark.parametrize('command',['change-validate','change-status'])
def test_v2_readonly_cli(tmp_path,capsys,command):
    f=make_v2(tmp_path);root=f['root'];before=snapshot(root)
    mtimes={p.relative_to(root):p.stat().st_mtime_ns for p in root.rglob('*') if p.is_file()}
    assert main(['--root',str(root),command,'docs/changes/CHANGE-001/r0001/change.json','--policy-sha256',f['policy_pin']])==0
    output=json.loads(capsys.readouterr().out)
    assert output['change_schema_version']==2 and output['authorization']=='not_granted'
    assert output['execution_verified'] is False and output['transition_permitted'] is False
    assert snapshot(root)==before
    assert {p.relative_to(root):p.stat().st_mtime_ns for p in root.rglob('*') if p.is_file()}==mtimes


@pytest.mark.parametrize('command',['change-capture','change-dispatch','change-verify','change-accept','change-archive'])
def test_v2_enforcement_cli_is_blocked_before_writes(tmp_path,capsys,command):
    f=make_v2(tmp_path);root=f['root'];before={p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    argv=['--root',str(root),command,'docs/changes/CHANGE-001/r0001/change.json','--policy-sha256',f['policy_pin']]
    if command in {'change-capture','change-dispatch'}:argv+=['--child','CHILD-001']
    else:argv+=['--bundle','.harness/nonexistent.json']
    if command=='change-dispatch':argv+=['--role','backend-engineer']
    assert main(argv)==2
    output=json.loads(capsys.readouterr().out)
    assert output['diagnostic_code']=='UXL_V2_ENFORCEMENT_UNSUPPORTED'
    assert {p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()}==before


@pytest.mark.parametrize('command',['capture','dispatch','verify','accept','archive'])
def test_v2_direct_legacy_enforcement_rejects_before_write(tmp_path,monkeypatch,command):
    from algooptionx_harness import enforcement
    f=make_v2(tmp_path);root=f['root'];path=Path('docs/changes/CHANGE-001/r0001/change.json');before=snapshot(root)
    def forbidden(*args,**kwargs):raise AssertionError('V2 attempted a native write')
    monkeypatch.setattr(enforcement,'capture_task',forbidden);monkeypatch.setattr(enforcement,'write_json',forbidden)
    with pytest.raises((HarnessError,ValidationError,ValueError)):
        if command=='capture':enforcement.capture_child(root,path,f['policy_pin'],'CHILD-001')
        elif command=='dispatch':enforcement.dispatch_child(root,path,f['policy_pin'],'CHILD-001','backend-engineer')
        elif command=='verify':enforcement.verify_bundle(root,path,f['policy_pin'],Path('.harness/nonexistent.json'))
        else:enforcement.close_change(root,path,f['policy_pin'],Path('.harness/nonexistent.json'),archive=command=='archive')
    assert snapshot(root)==before


def test_v2_cli_errors_do_not_echo_sensitive_metadata(tmp_path,capsys):
    f=make_v2(tmp_path);f['change']['approved']='synthetic-sensitive-marker'
    f['put']('docs/changes/CHANGE-001/r0001/change.json',f['change'])
    assert main(['--root',str(f['root']),'change-validate','docs/changes/CHANGE-001/r0001/change.json','--policy-sha256',f['policy_pin']])==2
    assert 'synthetic-sensitive-marker' not in capsys.readouterr().out


def test_v2_explicit_schema_export_preserves_defaults(tmp_path,capsys):
    assert main(['--root',str(tmp_path),'schemas'])==0
    assert json.loads(capsys.readouterr().out)['schemas']==11
    folder=tmp_path/'src/algooptionx_harness/schemas';before={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in folder.glob('*.json')}
    assert main(['--root',str(tmp_path),'schemas','--include-design','--include-change-v2'])==0
    assert json.loads(capsys.readouterr().out)['schemas']==13
    for name,old in before.items():assert ((folder/name).read_bytes(),(folder/name).stat().st_mtime_ns)==old
    assert json.loads((folder/'change-v2.schema.json').read_text())==ChangeSpecV2.model_json_schema()


@pytest.mark.parametrize('command',['change-capture','change-dispatch','change-verify','change-accept','change-archive'])
def test_enforcement_version_guard_sanitizes_errors(tmp_path,capsys,command):
    f=make_v2(tmp_path);f['change']['approved']='synthetic-sensitive-guard-marker'
    f['put']('docs/changes/CHANGE-001/r0001/change.json',f['change'])
    argv=['--root',str(f['root']),command,'docs/changes/CHANGE-001/r0001/change.json','--policy-sha256',f['policy_pin']]
    if command in {'change-capture','change-dispatch'}:argv+=['--child','CHILD-001']
    else:argv+=['--bundle','.harness/nonexistent.json']
    if command=='change-dispatch':argv+=['--role','backend-engineer']
    assert main(argv)==2
    out=capsys.readouterr()
    assert 'synthetic-sensitive-guard-marker' not in out.out+out.err


# Regressions from the actual distinct-context review, retained red before fixes.
def test_v1_validation_preserves_legacy_platform_support(tmp_path,monkeypatch,capsys):
    import os
    f=make_design(tmp_path);root=f['root'];path=root/'docs/changes/CHANGE-001/r0001/change.json'
    monkeypatch.setattr(os,'supports_dir_fd',set())
    assert validate_change(root,path,f['policy_pin'])['status']=='verified_contracts'
    assert main(['--root',str(root),'change-status',str(path),'--policy-sha256',f['policy_pin']])==0
    assert json.loads(capsys.readouterr().out)['authorization']=='not_granted'


@pytest.mark.parametrize('namespace',['events','closure'])
def test_v2_cannot_shadow_legacy_revision(tmp_path,namespace):
    f=make_v2(tmp_path)
    f['put'](f'.harness/changes/CHANGE-001/r0001/{namespace}/000001.json',{'label':'Synthetic immutable legacy record'})
    with pytest.raises(HarnessError):
        inspect_lifecycle(f['root'],Path('docs/changes/CHANGE-001/r0001/change.json'),f['policy_pin'])


@pytest.mark.parametrize('protected',['docs/changes/CHANGE-001/r0001/change.json','config/engineering-governance.json','docs/design-package.json','docs/wireframe.svg','docs/changes/CHANGE-001/r0001/tasks/CHILD-001.template.json'])
def test_native_completion_rejects_wrong_protected_snapshot(tmp_path,protected):
    from algooptionx_harness.lifecycle import _v2_completion
    from algooptionx_harness.designs import _Reader
    f=completed_fixture(tmp_path);root=f['root'];c=parse_change(f['change']);rec=copy.deepcopy(f['records']['CHILD-001'])
    fake=copy.deepcopy(f['baseline']);fake['files'][protected]['sha256']='a'*64
    task=f['task'].model_copy(update={'baseline_digest':digest(fake)})
    rec.update(before={'commit':fake['commit'],'source_digest':digest(fake)},after={'commit':fake['commit'],'source_digest':digest(fake)},task=f['put']('.harness/task/task.json',task),baseline=f['put']('.harness/task/baseline.json',fake),candidate=f['put']('.harness/task/candidate.json',fake))
    native=json.loads((root/rec['evidence']['path']).read_text());native.update(task_digest=digest(task),source_digest=digest(fake),final_source_digest=digest(fake))
    rec['evidence']=f['put']('.harness/run/evidence.json',native)
    ref=f['put']('.harness/completions/CHILD-001.json',rec)
    from algooptionx_harness.changes import StoredReference
    with pytest.raises(HarnessError):
        _v2_completion(_Reader(root,'docs/changes/CHANGE-001/r0001/change.json'),c,c.children[2],StoredReference.model_validate(ref),{'agent:fixture'})


@pytest.mark.parametrize('covers_requirements',[False,True])
def test_nonui_test_completion_rejects_unrelated_requirements(tmp_path,covers_requirements):
    from algooptionx_harness.lifecycle import _v2_completion
    from algooptionx_harness.designs import _Reader
    from algooptionx_harness.changes import StoredReference
    f=make_v2(tmp_path);c=f['change'];c.update(design_link=None,design_obligations=None)
    c['children']=[c['children'][2],c['children'][3],c['children'][4]];c['children'][0]['depends_on']=[]
    c['children'][-1]['depends_on']=[{'id':x,'revision':1} for x in ['CHILD-001','TEST-CHECK']]
    c['selected_children']=c['execution_order']=[{'id':x['id'],'revision':1} for x in c['children']]
    template=f['template'];template['ui_changes']=False
    c['children'][0]['task_template']=f['put'](c['children'][0]['task_template']['path'],template)
    f['put']('docs/changes/CHANGE-001/r0001/change.json',c);f=captured_v2(f);root=f['root'];change=parse_change(c)
    task=f['task'].model_copy(update={'id':'OTHER-TEST','requirement_ids':['REQ-001'] if covers_requirements else ['REQ-UNRELATED']})
    task_ref=f['put']('.harness/other/task.json',task)
    baseline_ref=f['put']('.harness/other/baseline.json',f['baseline'])
    native=json.loads((root/'.harness/run/evidence.json').read_text());native.update(task_id=task.id,task_digest=digest(task))
    evidence=f['put']('.harness/run/evidence.json',native)
    source={'commit':f['baseline']['commit'],'source_digest':digest(f['baseline'])}
    record={'schema_version':2,'kind':'test-evidence','change_id':change.id,'change_revision':change.revision,'change_digest':digest(change),'policy_digest':change.policy.sha256,'child_id':'TEST-CHECK','child_revision':1,'before':source,'after':source,'design_record_digest':None,'task':task_ref,'evidence':evidence,'ui_evidence':None}
    record['baseline']=baseline_ref
    ref=f['put']('.harness/unrelated-test-completion.json',record)
    if covers_requirements:
        assert _v2_completion(_Reader(root,'docs/changes/CHANGE-001/r0001/change.json'),change,change.children[1],StoredReference.model_validate(ref),{'agent:fixture'}).kind=='test-evidence'
    else:
        with pytest.raises(HarnessError):
            _v2_completion(_Reader(root,'docs/changes/CHANGE-001/r0001/change.json'),change,change.children[1],StoredReference.model_validate(ref),{'agent:fixture'})


def test_v1_enforcement_dispatch_guard_does_not_require_posix(tmp_path,monkeypatch,capsys):
    import os
    from algooptionx_harness import enforcement
    f=make_design(tmp_path)
    monkeypatch.setattr(os,'supports_dir_fd',set())
    calls=[]
    def captured(*args,**kwargs):
        calls.append(True)
        return {'status':'synthetic-dispatch-only-no-write'}
    monkeypatch.setattr(enforcement,'capture_child',captured)
    assert main(['--root',str(f['root']),'change-capture','docs/changes/CHANGE-001/r0001/change.json','--policy-sha256',f['policy_pin'],'--child','CHILD-001'])==0
    assert calls==[True]
    assert json.loads(capsys.readouterr().out)['status']=='synthetic-dispatch-only-no-write'


@pytest.mark.parametrize('command',['validate','capture'])
def test_v2_version_probe_never_uses_ordinary_open(tmp_path,monkeypatch,capsys,command):
    from algooptionx_harness import governance
    f=make_v2(tmp_path)
    def forbidden(*args,**kwargs):raise AssertionError('V2 reached legacy ordinary-open probe')
    monkeypatch.setattr(governance,'_read',forbidden)
    if command=='validate':assert validate_fixture(f)['change_schema_version']==2
    else:
        assert main(['--root',str(f['root']),'change-capture','docs/changes/CHANGE-001/r0001/change.json','--policy-sha256',f['policy_pin'],'--child','CHILD-001'])==2
        assert json.loads(capsys.readouterr().out)['diagnostic_code']=='UXL_V2_ENFORCEMENT_UNSUPPORTED'


def test_v2_version_probe_fifo_swap_cannot_block(tmp_path):
    import sys
    script=r'''
import sys,os
from pathlib import Path
from tests.control_plane.test_design_lifecycle import make_v2,validate_fixture
f=make_v2(Path(sys.argv[1]));target=f['root']/'docs/changes/CHANGE-001/r0001/change.json'
original=Path.is_file
armed=True
def racing(path):
    global armed
    result=original(path)
    if path==target and armed and result:
        armed=False
        target.unlink();os.mkfifo(target)
        print('CHECKED_REGULAR_REPLACED_WITH_FIFO',flush=True)
        return True
    return result
Path.is_file=racing
print(validate_fixture(f)['change_schema_version'],flush=True)
'''
    result=subprocess.run([sys.executable,'-B','-c',script,str(tmp_path)],cwd=ROOT,capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='2'


@pytest.mark.parametrize('unsafe',['symlink','fifo'])
def test_version_probe_never_falls_back_on_unsafe_inputs(tmp_path,monkeypatch,unsafe):
    import os
    from algooptionx_harness import governance
    f=make_v2(tmp_path);path=f['root']/'docs/changes/CHANGE-001/r0001/change.json';path.unlink()
    if unsafe=='symlink':path.symlink_to('/etc/passwd')
    else:os.mkfifo(path)
    def forbidden(*args,**kwargs):raise AssertionError('Unsafe read fell back to ordinary open')
    monkeypatch.setattr(governance,'_read',forbidden)
    with pytest.raises(HarnessError):validate_fixture(f)

"""Synthetic contract consistency and adversarial read-only tests; no UI certification."""
import copy
import os
import subprocess
import pytest
from pydantic import ValidationError
from algooptionx_harness import designs
from algooptionx_harness.designs import DesignRecord, DesignSpec, DesignError, validate_design
from algooptionx_harness.cli import main

def seed():
    sha='a'*64
    ref=lambda path:{'path':path,'sha256':sha}
    states=[{'id':'STATE-'+name.upper(),'name':name,'applicability':'applicable' if name=='ready' else 'not-applicable','expectation':'State behavior is explicitly described.','non_applicability_reason':None if name=='ready' else 'The bounded fixture does not expose this interaction state.'} for name in ['loading','empty','ready','error','stale','disabled','permission']]
    return {'schema_version':1,'kind':'design-spec','id':'DESIGN-001','revision':1,'parent_change_id':'CHANGE-001','parent_change_revision':1,'title':'Scoped synthetic journal design contract','requirements':[{'id':'REQ-001',**ref('docs/requirements.md')}],'user_goals':[{'id':'GOAL-001','description':'Inspect an accessible synthetic journal.'}],'journeys':[{'id':'JOURNEY-001','goal_ids':['GOAL-001'],'requirement_ids':['REQ-001'],'component_ids':['COMP-001'],'steps':['Open the synthetic journal fixture.']}],'screens':[{'id':'SCREEN-001','component_ids':['COMP-001'],'requirement_ids':['REQ-001']}],'components':[{'id':'COMP-001','screen_id':'SCREEN-001','requirement_ids':['REQ-001'],'props':[{'name':'events','description':'Synthetic display-only fixture events.'}],'states':states,'keyboard':'Native Enter and Space behavior.','focus':'Keep a visible and stable keyboard focus.','accessible_names':['The Activity filters group has a clear name.']}],'artifacts':[{'id':'ART-001','kind':'wireframe','reference':ref('docs/wireframe.svg'),'requirement_ids':['REQ-001'],'component_ids':['COMP-001'],'state_ids':['STATE-READY']}],'token_references':[ref('apps/web/src/tokens.css')],'viewports':[{'id':'VIEW-001','width':390,'height':844}],'themes':['light'],'renderer':{'id':'RENDER-001','engine':'chromium','version':'154.0','operating_system':'linux','fonts_sha256':sha,'locale':'en-IN','timezone':'Asia/Kolkata','device_scale_factor':1.0,'reduced_motion':'reduce'},'fixture':{'id':'FIXTURE-001','reference':ref('docs/fixture.json'),'source':'synthetic','clock':'2026-11-01T00:00:00Z','seed':1},'accessibility':{'standard':'WCAG-2.2-AA','criteria':['2.1.1'],'expectations':['Native keyboard interaction must remain available.']},'performance_budgets':[{'id':'BUDGET-001','metric':'filter-interaction','unit':'ms','maximum':100.0,'samples':2,'method':'Fixed synthetic journal and stable renderer.','declaration':'proposed'}],'validation_cases':[{'id':'CASE-001','component_id':'COMP-001','state_id':'STATE-READY','viewport_id':'VIEW-001','theme':'light','checks':['accessibility','responsive','visual','performance']}]}

from pathlib import Path
import json,hashlib
from datetime import datetime,timezone,timedelta
from tests.control_plane.test_change_contracts import make_change,save_change
from algooptionx_harness.workspace import write_json,snapshot,digest,file_digest
from algooptionx_harness.models import Task,Evidence,Result,Artifact,TestOutcome as NativeOutcome
from algooptionx_harness import chat

def make_design(tmp_path):
    root,change,pin,template=make_change(tmp_path)
    def put(name,content):
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
        if isinstance(content,str):path.write_text(content)
        elif isinstance(content,bytes):path.write_bytes(content)
        else:write_json(path,content)
        return {'path':name,'sha256':file_digest(path)}
    spec=seed();spec['requirements']=change['requirements']
    spec['artifacts'][0]['reference']=put('docs/wireframe.svg','<svg xmlns="http://www.w3.org/2000/svg"><text>Synthetic wireframe</text></svg>')
    spec['token_references']=[put('apps/web/src/tokens.css',':root { --fixture-color: #000; }')]
    spec['fixture']['reference']=put('docs/fixture.json',{'label':'Synthetic display-only contract fixture'})
    spec_ref=put('docs/design-package.json',spec)
    template['protected_inputs'].append(spec_ref['path'])
    template['ui_changes']=True
    template['checks'].append({'id':'browser','kind':'playwright','argv':['fixture-browser'],'report':'{run_dir}/browser.json'})
    change['approvals']['stages'].insert(2,'ui')
    change_path=save_change(root,change,template)
    baseline=snapshot(root)
    task=Task.model_validate({**template,'source_commit':baseline['commit'],'baseline_digest':digest(baseline)})
    task_ref=put('.harness/task/task.json',task)
    baseline_ref=put('.harness/task/baseline.json',baseline)
    source={'commit':baseline['commit'],'source_digest':digest(baseline)}
    base={'schema_version':1,'change_id':change['id'],'change_revision':1,'change_digest':digest(change),'policy_digest':pin,'source':source}
    pointer={'id':spec['id'],'revision':1,'reference':spec_ref}
    request=chat.request(task,'ui',task.baseline_digest);request_ref=put('.harness/approval/request.json',request)
    decision=chat.record(request,'approved','operator:synthetic-fixture');decision_ref=put('.harness/approval/decision.json',decision)
    binding={**base,'kind':'design-binding','design':pointer,'policy':change['policy'],'change_reference':{'path':str(change_path.relative_to(root)),'sha256':file_digest(change_path)},'native_task_reference':task_ref,'native_task_digest':digest(task),'baseline_reference':baseline_ref,'baseline_digest':digest(baseline),'approvals':[{'id':'APREF-001','mode':'operator-recorded-chat','request':request_ref,'decision':decision_ref}]}
    binding_ref=put('.harness/binding.json',binding)
    now=datetime.now(timezone.utc)-timedelta(minutes=1)
    results=[]
    for check in task.checks:
        log_ref=put(f'.harness/run/{check.id}.log','Synthetic record fixture, not actual execution evidence.')
        artifacts=[Artifact(path=f'{check.id}.log',sha256=log_ref['sha256'])]
        outcomes=[]
        if check.kind=='pytest':
            report=put('.harness/run/pytest.xml','<testsuite><testcase classname="tests.synthetic" name="test_declaration" /></testsuite>')
            artifacts.append(Artifact(path='pytest.xml',sha256=report['sha256']))
            outcomes=[NativeOutcome(id='tests.synthetic.test_declaration',status='passed')]
        if check.kind=='playwright':
            report=put('.harness/run/browser.json',{'suites':[{'specs':[{'file':'synthetic.spec.ts','title':'declaration','tests':[{'results':[{'status':'passed'}]}]}]}]})
            artifacts.append(Artifact(path='browser.json',sha256=report['sha256']))
            outcomes=[NativeOutcome(id='synthetic.spec.ts::declaration',status='passed')]
        results.append(Result(check_id=check.id,argv=[a.replace('{run_dir}',str(root/'.harness/run')) for a in check.argv],cwd=check.cwd,exit_code=0,timed_out=False,status='passed',detail='',duration_seconds=0.01,artifacts=artifacts,outcomes=outcomes))
    native=Evidence(run_id='synthetic-run',task_id=task.id,task_digest=digest(task),source_digest=digest(baseline),final_source_digest=digest(baseline),source_commit=baseline['commit'],started_at=now,finished_at=now+timedelta(seconds=1),status='passed',changed_paths=[],results=results,runtime={'python':'synthetic','platform':'synthetic'})
    native_ref=put('.harness/run/evidence.json',native)
    report=put('.harness/run/report.json',{'label':'Synthetic result, not rendering or certification'})
    screenshot=put('.harness/run/screenshot.png',b'\x89PNG\r\n\x1a\nsynthetic-fixture')
    comparison=put('.harness/run/comparison.json',{'label':'Synthetic comparison declaration only'})
    areas=[{'area':a,'status':'passed','notes':'Synthetic consistency declaration only.','artifacts':[{'kind':'report','reference':report}]} for a in ['accessibility','responsive']]
    areas.append({'area':'visual','status':'passed','notes':'Synthetic visual declaration only.','artifacts':[{'kind':'screenshot','reference':screenshot},{'kind':'comparison','reference':comparison}]})
    areas.append({'area':'performance','status':'passed','notes':'Synthetic numeric declaration only.','measurements':[{'budget_id':'BUDGET-001','observed':10.0,'samples':2}]})
    evidence={**base,'kind':'ui-validation-evidence','design':pointer,'native_task_reference':task_ref,'native_task_digest':digest(task),'native_evidence_reference':native_ref,'expected_cases':['CASE-001'],'executed_cases':[{'case_id':'CASE-001','status':'passed','results':areas}]}
    evidence_ref=put('.harness/ui-evidence.json',evidence)
    return {'root':root,'spec':spec,'spec_ref':spec_ref,'change':change,'template':template,'task':task,'baseline':baseline,'binding':binding,'binding_ref':binding_ref,'evidence':evidence,'evidence_ref':evidence_ref,'policy_pin':pin,'put':put}


def inspect(f, key='spec_ref'):
    return validate_design(f['root'], Path(f[key]['path']), f['policy_pin'])


def save_record(f, value, name='.harness/probe.json'):
    f['put'](name, value)
    return Path(name)


@pytest.mark.parametrize('key', ['spec_ref', 'binding_ref', 'evidence_ref'])
def test_valid_records_are_read_only_not_authority(tmp_path, key):
    f = make_design(tmp_path)
    before = {p.relative_to(f['root']): (p.read_bytes(), p.stat().st_mtime_ns)
              for p in f['root'].rglob('*') if p.is_file()}
    result = inspect(f, key)
    assert result['status'] == 'DESIGN CONTRACT VALID'
    assert result['source_digest'] == digest(snapshot(f['root']))
    for flag in ('human_design_approved', 'implementation_authorized', 'ui_visually_verified',
                 'accessibility_certified', 'performance_accepted', 'native_execution_authenticated',
                 'release_authorized', 'policy_adoption_authenticated'):
        assert result[flag] is False
    after = {p.relative_to(f['root']): (p.read_bytes(), p.stat().st_mtime_ns)
             for p in f['root'].rglob('*') if p.is_file()}
    assert before == after


def change_at(value, keys, replacement):
    for key in keys[:-1]:
        value = value[key]
    value[keys[-1]] = replacement


@pytest.mark.parametrize(('keys', 'value'), [
    (['kind'], 'approved'), (['schema_version'], 2), (['schema_version'], True),
    (['revision'], True), (['revision'], '1'), (['revision'], 0),
    (['id'], 'bad id'), (['title'], None), (['approved'], True),
    (['artifacts', 0, 'reference', 'sha256'], 'wrong'),
    (['components', 0, 'states', 0, 'id'], 'STATE-READY'),
    (['components', 0, 'states', 0, 'non_applicability_reason'], None),
    (['components', 0, 'states', 2, 'applicability'], 'not-applicable'),
    (['components', 0, 'screen_id'], 'SCREEN-OTHER'),
    (['components', 0, 'requirement_ids'], ['REQ-UNKNOWN']),
    (['screens', 0, 'component_ids'], ['COMP-OTHER']),
    (['journeys', 0, 'goal_ids'], ['GOAL-OTHER']),
    (['artifacts', 0, 'state_ids'], ['STATE-LOADING']),
    (['validation_cases', 0, 'state_id'], 'STATE-OTHER'),
    (['validation_cases', 0, 'checks'], ['visual', 'visual']),
    (['themes'], ['light', 'dark']),
    (['renderer', 'engine'], 'shell'), (['renderer', 'version'], 'latest'),
    (['renderer', 'device_scale_factor'], float('inf')),
    (['renderer', 'device_scale_factor'], True),
    (['performance_budgets', 0, 'maximum'], float('nan')),
    (['performance_budgets', 0, 'maximum'], -1.0),
    (['performance_budgets', 0, 'samples'], True),
    (['performance_budgets', 0, 'declaration'], 'approved'),
    (['viewports', 0, 'width'], True),
    (['fixture', 'clock'], '2026-01-01T00:00:00'),
    (['fixture', 'source'], 'broker'),
    (['artifacts', 0, 'reference', 'path'], 'docs/../secret.svg'),
    (['artifacts', 0, 'reference', 'path'], '/etc/passwd'),
    (['artifacts', 0, 'reference', 'path'], 'https://example.invalid/a.svg'),
    (['artifacts', 0, 'reference', 'path'], 'docs/.env.svg'),
    (['artifacts', 0, 'reference', 'path'], 'docs/.git/a.svg'),
    (['artifacts', 0, 'reference', 'path'], 'docs/script.sh'),
])
def test_strict_spec_rejections(keys, value):
    record = seed()
    change_at(record, keys, value)
    with pytest.raises(ValidationError):
        DesignRecord.model_validate(record)


@pytest.mark.parametrize('field', ['requirements', 'components', 'artifacts', 'screens', 'validation_cases'])
def test_duplicates_rejected(field):
    record = seed()
    record[field].append(copy.deepcopy(record[field][0]))
    with pytest.raises(ValidationError):
        DesignSpec.model_validate(record)


def test_missing_and_excessive_collections_rejected():
    record = seed()
    del record['user_goals']
    with pytest.raises(ValidationError):
        DesignRecord.model_validate(record)
    record = seed()
    record['artifacts'] *= 201
    with pytest.raises(ValidationError):
        DesignRecord.model_validate(record)


@pytest.mark.parametrize(('mutation', 'code'), [
    ('hash', 'UXD_HASH'), ('missing', 'UXD_MISSING'), ('version', 'UXD_VERSION'),
    ('variant', 'UXD_VARIANT'), ('extra', 'UXD_SCHEMA'), ('timezone', 'UXD_SCHEMA'),
    ('locale', 'UXD_SCHEMA'), ('os', 'UXD_SCHEMA'), ('fixture-list', 'UXD_TYPE'),
    ('requirement', 'UXD_BINDING'),
])
def test_filesystem_spec_rejections(tmp_path, mutation, code):
    f = make_design(tmp_path)
    spec = copy.deepcopy(f['spec'])
    if mutation == 'hash': (f['root'] / 'docs/wireframe.svg').write_text('Changed after pin capture')
    elif mutation == 'missing': (f['root'] / 'docs/wireframe.svg').unlink()
    elif mutation == 'version': spec['schema_version'] = 99
    elif mutation == 'variant': spec['kind'] = 'fake-success'
    elif mutation == 'extra': spec['approved'] = True
    elif mutation == 'timezone': spec['renderer']['timezone'] = 'Invalid/Zone'
    elif mutation == 'locale': spec['renderer']['locale'] = 'anything'
    elif mutation == 'os': spec['renderer']['operating_system'] = 'shell'
    elif mutation == 'fixture-list': spec['fixture']['reference'] = f['put']('docs/fixture.json', [])
    elif mutation == 'requirement': spec['requirements'][0].update(f['put']('docs/requirements.md', '# REQ-001-OTHER\nNo exact requirement identifier.'))
    f['put']('docs/probe.json', spec)
    with pytest.raises(DesignError, match=designs.DIAGNOSTICS[code].replace('.', r'\.')) as error:
        validate_design(f['root'], Path('docs/probe.json'))
    assert error.value.code == code


@pytest.mark.parametrize('mutation', ['parent', 'change-digest', 'task-digest', 'baseline-digest', 'stale-revision', 'policy', 'fake-approval', 'approval-stage', 'self-reference', 'duplicate-approval'])
def test_binding_identity_and_spoof_rejections(tmp_path, mutation):
    f = make_design(tmp_path)
    record = copy.deepcopy(f['binding'])
    if mutation == 'parent': record['change_id'] = 'CHANGE-OTHER'
    elif mutation == 'change-digest': record['change_digest'] = 'b' * 64
    elif mutation == 'task-digest': record['native_task_digest'] = 'b' * 64
    elif mutation == 'baseline-digest': record['baseline_digest'] = 'b' * 64
    elif mutation == 'stale-revision': record['design']['revision'] = 2
    elif mutation == 'policy': record['policy']['revision'] = 2
    elif mutation == 'fake-approval': record['approvals'][0]['decision'] = f['put']('.harness/fake.json', {'approved': True})
    elif mutation == 'approval-stage':
        req = json.loads((f['root'] / record['approvals'][0]['request']['path']).read_text())
        req['stage'] = 'implementation'
        record['approvals'][0]['request'] = f['put']('.harness/fake-request.json', req)
    elif mutation == 'self-reference': record['baseline_reference']['path'] = '.harness/probe.json'
    elif mutation == 'duplicate-approval':
        item = copy.deepcopy(record['approvals'][0]); item['id'] = 'APREF-002'; record['approvals'].append(item)
    with pytest.raises(DesignError):
        validate_design(f['root'], save_record(f, record), f['policy_pin'])


@pytest.mark.parametrize('key', ['binding_ref', 'evidence_ref'])
def test_policy_pin_required(tmp_path, key):
    f = make_design(tmp_path)
    with pytest.raises(DesignError) as error:
        validate_design(f['root'], Path(f[key]['path']))
    assert error.value.code == 'UXD_POLICY'


@pytest.mark.parametrize('mutation', ['empty-success', 'nonzero', 'timed-out', 'argv', 'log-missing', 'artifact-hash', 'failed-native', 'stale-source', 'missing-report'])
def test_native_evidence_cannot_claim_inconsistent_success(tmp_path, mutation):
    f = make_design(tmp_path)
    record = copy.deepcopy(f['evidence'])
    path = f['root'] / record['native_evidence_reference']['path']
    native = json.loads(path.read_text())
    if mutation == 'empty-success': native['results'] = []
    elif mutation == 'nonzero': native['results'][0]['exit_code'] = 1
    elif mutation == 'timed-out': native['results'][0]['timed_out'] = True
    elif mutation == 'argv': native['results'][0]['argv'] = ['false']
    elif mutation == 'log-missing': native['results'][0]['artifacts'] = native['results'][0]['artifacts'][1:]
    elif mutation == 'artifact-hash': native['results'][0]['artifacts'][0]['sha256'] = 'b' * 64
    elif mutation == 'failed-native': native['status'] = 'failed'
    elif mutation == 'stale-source': native['final_source_digest'] = 'b' * 64
    elif mutation == 'missing-report': native['results'][0]['artifacts'] = native['results'][0]['artifacts'][:1]
    record['native_evidence_reference'] = f['put'](str(path.relative_to(f['root'])), native)
    with pytest.raises(DesignError):
        validate_design(f['root'], save_record(f, record), f['policy_pin'])


@pytest.mark.parametrize('status', ['missing', 'failed', 'skipped', 'unverified'])
def test_nonpassing_results_are_visible_data(tmp_path, status):
    f = make_design(tmp_path)
    record = copy.deepcopy(f['evidence'])
    case = record['executed_cases'][0]
    case['status'] = status
    for area in case['results']:
        area['status'] = status
        area['artifacts'] = []
        area['measurements'] = []
        if area['area'] == 'performance' and status == 'failed':
            area['measurements'] = [{'budget_id': 'BUDGET-001', 'observed': 101.0, 'samples': 2}]
    result = validate_design(f['root'], save_record(f, record), f['policy_pin'])
    assert result['case_declarations'][status] == 1
    assert result['case_declarations']['passed'] == 0


def test_missing_case_and_performance_contradiction(tmp_path):
    f = make_design(tmp_path)
    record = copy.deepcopy(f['evidence'])
    record['executed_cases'] = []
    result = validate_design(f['root'], save_record(f, record), f['policy_pin'])
    assert result['case_declarations']['missing'] == 1
    record = copy.deepcopy(f['evidence'])
    record['executed_cases'][0]['results'][-1]['measurements'][0]['observed'] = 101.0
    with pytest.raises(DesignError):
        validate_design(f['root'], save_record(f, record), f['policy_pin'])


def test_case_success_cannot_hide_failed_area(tmp_path):
    f = make_design(tmp_path)
    record = copy.deepcopy(f['evidence'])
    record['executed_cases'][0]['results'][0]['status'] = 'failed'
    with pytest.raises(ValidationError):
        DesignRecord.model_validate(record)


@pytest.mark.parametrize('mode', ['leaf-symlink', 'parent-symlink', 'fifo', 'oversize-input', 'oversize-artifact'])
def test_unsafe_files_fail_without_reading_or_hanging(tmp_path, mode):
    f = make_design(tmp_path)
    root = f['root']
    if mode == 'oversize-input':
        path = root / 'docs/probe.json'; path.write_bytes(b' ' * (designs.MAX_JSON + 1))
    else:
        path = root / 'docs/wireframe.svg'
        path.unlink()
        if mode == 'leaf-symlink': path.symlink_to('/etc/passwd')
        elif mode == 'parent-symlink':
            target = tmp_path / 'outside'; target.mkdir(); (target / 'wireframe.svg').write_text('Outside')
            (root / 'docs/link').symlink_to(target, target_is_directory=True)
            spec = copy.deepcopy(f['spec']); spec['artifacts'][0]['reference']['path'] = 'docs/link/wireframe.svg'
            f['put']('docs/design-package.json', spec)
        elif mode == 'fifo': os.mkfifo(path)
        elif mode == 'oversize-artifact': path.write_bytes(b'x' * (designs.MAX_ARTIFACT + 1))
        path = root / f['spec_ref']['path']
    with pytest.raises(DesignError) as error:
        validate_design(root, path)
    assert error.value.code in {'UXD_PATH', 'UXD_TYPE', 'UXD_LIMIT'}


@pytest.mark.parametrize('raw', ['{"schema_version":1,"schema_version":1}', '{"secret":"fixture-sensitive-marker",', '[' * 100 + '0' + ']' * 100, '{"value":NaN}'])
def test_malformed_json_and_sensitive_errors_sanitized(tmp_path, capsys, raw):
    f = make_design(tmp_path)
    f['put']('docs/probe.json', raw)
    assert main(['--root', str(f['root']), 'design-validate', 'docs/probe.json']) == 2
    output = capsys.readouterr().out
    assert 'fixture-sensitive-marker' not in output
    assert json.loads(output)['diagnostic_code'] in {'UXD_JSON', 'UXD_LIMIT'}


def test_cli_success_commands_are_inert_and_no_authority(tmp_path, capsys):
    f = make_design(tmp_path)
    spec = copy.deepcopy(f['spec'])
    sentinel = tmp_path / 'must-not-exist'
    spec['title'] = f'$(touch {sentinel}) ; execute no commands'
    spec['performance_budgets'][0]['declaration'] = 'approval-claimed'
    f['put']('docs/probe.json', spec)
    assert main(['--root', str(f['root']), 'design-validate', 'docs/probe.json']) == 0
    output = json.loads(capsys.readouterr().out)
    assert output['status'] == 'DESIGN CONTRACT VALID'
    assert output['performance_accepted'] is False
    assert not sentinel.exists()


@pytest.mark.parametrize('path', ['../secret.json', '/etc/passwd', 'https://example.invalid/spec.json', 'docs/.env.json', 'docs/.git/a.json'])
def test_unsafe_input_paths(tmp_path, path):
    f = make_design(tmp_path)
    with pytest.raises(DesignError) as error:
        validate_design(f['root'], Path(path))
    assert error.value.code == 'UXD_PATH'


def test_reference_and_total_limits(tmp_path, monkeypatch):
    f = make_design(tmp_path)
    monkeypatch.setattr(designs, 'MAX_REFERENCES', 2)
    with pytest.raises(DesignError) as error:
        inspect(f)
    assert error.value.code == 'UXD_LIMIT'
    monkeypatch.setattr(designs, 'MAX_REFERENCES', 512)
    monkeypatch.setattr(designs, 'MAX_TOTAL', 128)
    with pytest.raises(DesignError) as error:
        inspect(f)
    assert error.value.code == 'UXD_LIMIT'


def test_secure_platform_required(tmp_path, monkeypatch):
    f = make_design(tmp_path)
    monkeypatch.setattr(os, 'supports_dir_fd', set())
    with pytest.raises(DesignError) as error:
        inspect(f)
    assert error.value.code == 'UXD_PLATFORM'


def test_change_during_inspection_rejected(tmp_path, monkeypatch):
    f = make_design(tmp_path)
    original = designs._Reader.finish
    def changed(reader):
        (reader.root / 'docs/wireframe.svg').write_text('Changed during inspection')
        original(reader)
    monkeypatch.setattr(designs._Reader, 'finish', changed)
    with pytest.raises(DesignError) as error:
        inspect(f)
    assert error.value.code == 'UXD_CHANGED'


def test_valid_supersession_and_self_reference(tmp_path):
    f = make_design(tmp_path)
    spec = copy.deepcopy(f['spec']); spec['revision'] = 2
    spec['supersedes'] = {'id': spec['id'], 'revision': 1, 'reference': f['spec_ref']}
    f['put']('docs/revision2.json', spec)
    assert validate_design(f['root'], Path('docs/revision2.json'))['design_revision'] == 2
    spec['supersedes']['reference']['path'] = 'docs/revision2.json'
    f['put']('docs/revision2.json', spec)
    with pytest.raises(DesignError) as error:
        validate_design(f['root'], Path('docs/revision2.json'))
    assert error.value.code == 'UXD_CYCLE'


def test_schema_export_preserves_legacy_defaults(tmp_path, capsys):
    assert main(['--root', str(tmp_path), 'schemas']) == 0
    assert json.loads(capsys.readouterr().out)['schemas'] == 11
    schemas = tmp_path / 'src/algooptionx_harness/schemas'
    before = {p.name: p.read_bytes() for p in schemas.glob('*.json')}
    assert 'design-record.schema.json' not in before
    assert main(['--root', str(tmp_path), 'schemas', '--include-design']) == 0
    assert json.loads(capsys.readouterr().out)['schemas'] == 12
    for name, raw in before.items():
        assert (schemas / name).read_bytes() == raw
    root = Path(__file__).resolve().parents[2]
    assert json.loads((root / 'src/algooptionx_harness/schemas/design-record.schema.json').read_text()) == DesignRecord.model_json_schema()
    for name in before:
        path = 'src/algooptionx_harness/schemas/' + name
        assert (root / path).read_bytes() == subprocess.check_output(['git', '-C', str(root), 'show', f'HEAD:{path}'])


def test_actual_checkout_native_snapshot_equivalence():
    root = Path(__file__).resolve().parents[2]
    native = snapshot(root)
    assert designs._bounded_snapshot(root) == native
    assert digest(designs._Baseline.model_validate(native)) == digest(native)


def test_binding_rejects_different_requirement_bytes_with_same_id(tmp_path):
    f = make_design(tmp_path)
    spec = copy.deepcopy(f['spec'])
    spec['requirements'][0].update(f['put']('docs/alternative.md', '# REQ-001\nA completely different requirement.'))
    spec_ref = f['put']('docs/design-package.json', spec)
    baseline = snapshot(f['root'])
    task = f['task'].model_copy(update={'baseline_digest': digest(baseline)})
    binding = copy.deepcopy(f['binding'])
    binding.update(design={**binding['design'], 'reference': spec_ref},
                   native_task_reference=f['put']('.harness/task/task.json', task),
                   native_task_digest=digest(task),
                   baseline_reference=f['put']('.harness/task/baseline.json', baseline),
                   baseline_digest=digest(baseline),
                   source={'commit': baseline['commit'], 'source_digest': digest(baseline)}, approvals=[])
    with pytest.raises(DesignError) as error:
        validate_design(f['root'], save_record(f, binding), f['policy_pin'])
    assert error.value.code == 'UXD_BINDING'


@pytest.mark.parametrize('mode', ['output', 'timeout'])
def test_git_inventory_bounded(tmp_path, monkeypatch, mode):
    f = make_design(tmp_path)
    if mode == 'output':
        monkeypatch.setattr(designs, 'MAX_GIT_OUTPUT', 1)
    else:
        monkeypatch.setattr(designs, 'GIT_TIMEOUT', 0.0)
    with pytest.raises(DesignError) as error:
        designs._bounded_snapshot(f['root'])
    assert error.value.code == 'UXD_LIMIT'

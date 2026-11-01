"""Frozen UI execution data and bounded native adapters; never approval authority."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal
from pydantic import Field, field_validator, model_validator
from algooptionx_harness.changes import (
    Versioned, ChangeContract, FrozenDesignV2, Identity, Revision, Sha256,
    SourceIdentity, StoredReference, safe_path, unique,
)
from algooptionx_harness.designs import (
    _Reader, _decode, _bounded_snapshot, DesignReference, DesignSpec,
    RendererProfile, _spec_artifacts,
)
from algooptionx_harness.workspace import HarnessError, digest

AREAS={'accessibility','responsive','visual','performance'}
SCENARIOS={'workspace-overview','workspace-order-dialog','workspace-activity'}


class UIReference(ChangeContract):
    path: str
    sha256: Sha256

    @field_validator('path')
    @classmethod
    def artifact_path(cls,value):
        safe_path(value)
        if any(p=='.git' or p.startswith('.env') for p in PurePosixPath(value).parts):
            raise ValueError('Git/environment artifacts forbidden.')
        if not value.startswith(('docs/','.harness/','apps/web/tests/visual-baselines/')) or PurePosixPath(value).suffix not in {'.json','.png','.xml','.log','.txt','.zip'}:
            raise ValueError('Use a supported local UI input.')
        return value


class CaseExecution(ChangeContract):
    id: Identity
    scenario: Literal['workspace-overview','workspace-order-dialog','workspace-activity']
    baseline: UIReference | None = None

    @field_validator('baseline')
    @classmethod
    def source_baseline(cls,value):
        if value is not None and (not value.path.startswith('apps/web/tests/visual-baselines/') or not value.path.endswith('.png')):
            raise ValueError('Baseline must be a source-controlled visual PNG.')
        return value


class MeasurementProof(ChangeContract):
    task: StoredReference
    baseline: StoredReference
    candidate: StoredReference
    evidence: StoredReference
    report: UIReference
    plan: UIReference


class UIExecutionPlan(Versioned):
    schema_version: Literal[1]
    kind: Literal['ui-execution']
    change_id: Identity
    change_revision: Revision
    design: FrozenDesignV2
    mode: Literal['measure','verify']
    renderer: RendererProfile
    environment_sha256: Sha256
    baseline_manifest: UIReference
    cases: list[CaseExecution] = Field(min_length=1,max_length=256)
    measurement_baseline: MeasurementProof | None = None
    adapter: Literal['workspace-ui-v1']

    @model_validator(mode='after')
    def inventory(self):
        unique([c.id for c in self.cases],'UI cases')
        unique([c.baseline.path for c in self.cases if c.baseline],'UI baseline mappings')
        if self.mode=='verify' and self.measurement_baseline is None:
            raise ValueError('Verified UI runs need an actual measured baseline.')
        if self.mode=='measure' and self.measurement_baseline is not None:
            raise ValueError('Measurement runs cannot claim an approved performance baseline.')
        return self


def plan_name(change):
    return f'docs/changes/{change.id}/r{change.revision:04d}/ui-execution.json'


def pin(reader,ref):
    raw=reader.raw(ref.path,1024*1024 if ref.path.endswith('.json') else 4*1024*1024,ui=True,reference=True)
    if hashlib.sha256(raw).hexdigest()!=ref.sha256:
        raise HarnessError('UI input digest differs from frozen bytes.')
    return raw


def read_plan(root,path,expected_sha=None,reader=None):
    root=root.resolve();name=path.relative_to(root).as_posix() if path.is_absolute() else path.as_posix()
    reader=reader or _Reader(root,'')
    raw=reader.raw(name,ui=True)
    if expected_sha is not None and hashlib.sha256(raw).hexdigest()!=expected_sha:raise HarnessError('UI execution plan changed.')
    _decode(raw)
    return UIExecutionPlan.model_validate_json(raw),reader


def load_plan(root,change,*,verification=True):
    reader=_Reader(root,'');before=_bounded_snapshot(root)
    plan,reader=read_plan(root,Path(plan_name(change)),reader=reader)
    if plan.mode!='verify' and verification:raise HarnessError('Measurement-only plan cannot authorize governed execution.')
    if (plan.change_id,plan.change_revision,plan.design)!=(change.id,change.revision,change.design_link):raise HarnessError('UI plan parent/design binding differs.')
    spec=reader.model(DesignReference(path=plan.design.reference.path,sha256=plan.design.reference.sha256),DesignSpec)
    if digest(spec)!=plan.design.record_digest or plan.renderer!=spec.renderer:raise HarnessError('UI plan frozen design/profile differs.')
    _spec_artifacts(reader,spec)
    if [c.id for c in plan.cases]!=[c.id for c in spec.validation_cases]:raise HarnessError('UI execution inventory differs from design.')
    # Capability constraints only add blockers; policy/risk still has one authority.
    capabilities={
        'apps/web/src/features/workspace/pages/OverviewPage.tsx':'workspace-overview',
        'apps/web/src/features/workspace/pages/MarketTerminalPage.tsx':'workspace-order-dialog',
        'apps/web/src/features/workspace/components/ActivityPanel.tsx':'workspace-activity',
    }
    selected_scenarios={c.scenario for c in plan.cases}
    for scope in change.allowed_paths:
        if scope.startswith('apps/web/src/') or scope in {'apps/web/','apps/web/src/'}:
            if scope not in capabilities or capabilities[scope] not in selected_scenarios:
                raise HarnessError('UI_SCOPE_UNSUPPORTED: no complete fixed adapter for affected source scope.')

    manifest=_decode(pin(reader,plan.baseline_manifest))
    if not isinstance(manifest,dict) or manifest.get('schema_version')!=1 or not isinstance(manifest.get('files'),list) or len(manifest['files'])>512:
        raise HarnessError('Malformed baseline manifest.')
    known={}
    for entry in manifest['files']:
        if not isinstance(entry,dict) or set(entry)!={'path','sha256'}:raise HarnessError('Malformed baseline entry.')
        name=entry['path'];safe_path(name)
        if name in known:raise HarnessError('Duplicate baseline inventory.')
        known[name]=entry['sha256']
    if len(known)!=len(manifest['files']):raise HarnessError('Ambiguous baseline inventory.')
    for case,definition in zip(plan.cases,spec.validation_cases,strict=True):
        state=next(s for c in spec.components for s in c.states if s.id==definition.state_id)
        if state.name not in {'ready','empty'}:raise HarnessError('No executed adapter for the required interaction state; do not skip it.')
        if 'visual' in definition.checks:
            if case.baseline is None:raise HarnessError('Expected screenshot baseline missing.')
            image=pin(reader,case.baseline)
            if not image.startswith(b'\x89PNG\r\n\x1a\n'):raise HarnessError('Baseline is not a PNG.')
            relative=case.baseline.path.removeprefix('apps/web/tests/visual-baselines/')
            if known.get(relative)!=case.baseline.sha256:raise HarnessError('Baseline manifest/image mapping differs.')
    if plan.renderer.operating_system!='linux' or plan.renderer.engine!='chromium':raise HarnessError('Initial native UI adapter supports Linux Chromium only.')
    for budget in spec.performance_budgets:
        if budget.metric not in {'interaction-latency','bundle-bytes'} or budget.unit not in {'ms','bytes'} or budget.samples>100:
            raise HarnessError('Unsupported measured budget method; no arbitrary substitute.')
        if (budget.metric=='interaction-latency')!=(budget.unit=='ms'):raise HarnessError('Budget metric/unit differs.')
        if budget.method!={'interaction-latency':'raf-theme-toggle-v1','bundle-bytes':'workspace-js-bytes-v1'}[budget.metric]:raise HarnessError('Budget method differs from executed adapter.')
    if plan.measurement_baseline:
        proof=plan.measurement_baseline
        for ref in [proof.task,proof.baseline,proof.candidate,proof.evidence,proof.report,proof.plan]:pin(reader,UIReference(path=ref.path,sha256=ref.sha256))
    reader.finish()
    if _bounded_snapshot(root)!=before:raise HarnessError('Source changed during UI plan inspection.')
    protected={plan_name(change),plan.design.reference.path,plan.baseline_manifest.path,*(c.baseline.path for c in plan.cases if c.baseline)}
    return plan,spec,protected


def ui_check(plan):
    from algooptionx_harness.models import Check
    return Check(id='ui-governance',kind='playwright',argv=['npm','--prefix','apps/web','run','test:governance'],report='{run_dir}/ui-governance/playwright.json',timeout_seconds=180,critical_tests=[f'design-governance.spec.ts::@design {c.id}' for c in plan.cases])


def review_summary(task,plan,root=None):
    packet=''
    if root is not None:
        reader=_Reader(root,'')
        spec=reader.model(DesignReference(path=plan.design.reference.path,sha256=plan.design.reference.sha256),DesignSpec)
        packet=' REVIEW PACKET '+json.dumps({'renderer':plan.renderer.model_dump(mode='json'),'viewports':[v.model_dump(mode='json') for v in spec.viewports],'themes':spec.themes,'budgets':[b.model_dump(mode='json') for b in spec.performance_budgets],'images':[c.baseline.model_dump(mode='json') for c in plan.cases if c.baseline],'measurement_evidence':plan.measurement_baseline.evidence.model_dump(mode='json') if plan.measurement_baseline else None},sort_keys=True)
        reader.finish()
    return f'UI REVIEW {task.id} task={digest(task)} baseline={task.baseline_digest} design={plan.design.id}/r{plan.design.revision} design_digest={plan.design.record_digest} execution_plan={digest(plan)} baseline_manifest={plan.baseline_manifest.sha256}. Review exact images, renderer, all cases and measured performance budgets; no release authorization.'+packet


from algooptionx_harness.designs import AreaResult,Number
from algooptionx_harness.models import Task,Evidence,Artifact


class UICaseReport(Versioned):
    schema_version: Literal[1]
    kind: Literal['ui-case']
    case_id: Identity
    mode: Literal['measure','verify']
    plan_sha256: Sha256
    source: SourceIdentity
    task_digest: Sha256
    renderer: RendererProfile
    fixture_sha256: Sha256
    environment_sha256: Sha256
    results: list[AreaResult] = Field(min_length=1,max_length=4)
    samples: dict[Identity,list[Number]] = Field(default_factory=dict,max_length=30)

    @model_validator(mode='after')
    def unambiguous(self):
        unique([a.area for a in self.results],'executed UI areas')
        if any(not values or len(values)>100 for values in self.samples.values()):raise ValueError('Bounded nonempty performance samples required.')
        return self


class UIRunReport(Versioned):
    schema_version: Literal[1]
    kind: Literal['ui-run']
    mode: Literal['measure','verify']
    plan_sha256: Sha256
    source: SourceIdentity
    task_digest: Sha256
    cases: list[UIReference] = Field(min_length=1,max_length=256)


def font_fingerprint():
    """Bounded fixed OS font inventory, including distro-owned font aliases."""
    import os
    roots=[Path(p) for p in ['/usr/share/fonts','/usr/local/share/fonts','/usr/share/texmf','/usr/share/texlive','/usr/share/poppler','/usr/share/X11','/usr/share/ghostscript']]
    pending=[Path(p) for p in ['/usr/share/fonts','/usr/local/share/fonts'] if Path(p).exists()]
    visited=set();files={};total=0;entries=0
    while pending:
        folder=pending.pop().resolve()
        if folder in visited:continue
        if not any(folder.is_relative_to(r) for r in roots):raise HarnessError('Font alias escapes fixed system font roots.')
        visited.add(folder)
        if len(visited)>2048:raise HarnessError('Font directory budget exceeded.')
        with os.scandir(folder) as listing:
            for entry in listing:
                entries+=1
                if entries>8192:raise HarnessError('Font inventory budget exceeded.')
                target=Path(entry.path).resolve()
                if not any(target.is_relative_to(r) for r in roots):raise HarnessError('Font alias escapes fixed system font roots.')
                if target.is_dir():pending.append(target);continue
                if str(target) in files:continue
                raw,_=_Reader(target.parent,'')._bytes(target.name,64*1024*1024)
                total+=len(raw)
                if total>512*1024*1024 or len(files)>=4096:raise HarnessError('Font inventory byte/count budget exceeded.')
                files[str(target)]=hashlib.sha256(raw).hexdigest()
    if not files:raise HarnessError('System font inventory unavailable.')
    return digest(files)


def runtime_platform():
    import platform
    return digest({'platform':platform.platform(),'machine':platform.machine(),'libc':platform.libc_ver()})


def runtime_context(root,task,baseline):
    """Derived by the native runner, never inherited from caller environment."""
    from algooptionx_harness.changes import parse_change
    paths=[p for p in task.protected_inputs if p.endswith('/ui-execution.json')]
    if len(paths)!=1:raise HarnessError('UI runner requires one protected execution plan.')
    p=paths[0];meta=baseline['files'].get(p)
    if not meta or meta.get('deleted'):raise HarnessError('Execution plan absent from captured source.')
    plan,reader=read_plan(root,Path(p),meta['sha256'])
    parent=f'docs/changes/{plan.change_id}/r{plan.change_revision:04d}/change.json'
    raw=reader.raw(parent)
    change=parse_change(_decode(raw))
    plan,spec,protected=load_plan(root,change,verification=False)
    if not protected<=set(task.protected_inputs):raise HarnessError('UI execution inputs are not protected.')
    from algooptionx_harness.governance import execution_checks
    if not any(c.id=='ui-governance' and c==ui_check(plan) for c in task.checks):raise HarnessError('UI adapter command or inventory weakened.')
    if runtime_platform()!=plan.environment_sha256:raise HarnessError('Actual OS profile differs from the frozen environment.')
    if spec.fixture.seed!=1:raise HarnessError('Only deterministic workspace seed1 is supported.')
    fixture=_decode(reader.pin(spec.fixture.reference,json_file=True))
    if fixture.get('adapter')!='workspace-session-v1' or fixture.get('seed')!=1:raise HarnessError('Unsupported deterministic fixture; no silent replacement.')
    if font_fingerprint()!=plan.renderer.fonts_sha256:raise HarnessError('Actual font profile differs; review the renderer.')
    if plan.mode=='verify':verify_measurement(root,plan,spec)
    definitions={c.id:c for c in spec.validation_cases};viewports={v.id:v for v in spec.viewports}
    states={s.id:s for c in spec.components for s in c.states}
    asset_root=root/'apps/web/dist/assets'
    assets={};bundle_bytes=0
    if not asset_root.is_dir():raise HarnessError('Fresh frontend build assets unavailable.')
    for asset_file in sorted(asset_root.iterdir()):
        if asset_file.suffix!='.js':continue
        raw,_=_Reader(asset_root,'')._bytes(asset_file.name,16*1024*1024)
        bundle_bytes+=len(raw);assets[asset_file.name]=hashlib.sha256(raw).hexdigest()
        if len(assets)>1024 or bundle_bytes>128*1024*1024:raise HarnessError('Bundle measurement budget exceeded.')
    if not assets:raise HarnessError('No workspace JavaScript assets.')
    current=_bounded_snapshot(root)
    result={'schema_version':1,'root':str(root),'plan_path':p,'plan_sha256':meta['sha256'],'task_digest':digest(task),'source':{'commit':current['commit'],'source_digest':digest(current)},'renderer':plan.renderer.model_dump(mode='json'),'environment_sha256':plan.environment_sha256,'fixture_sha256':spec.fixture.reference.sha256,'fixture_clock':spec.fixture.clock.isoformat(),'mode':plan.mode,'bundle_bytes':bundle_bytes,'bundle_manifest':assets,'budgets':[b.model_dump(mode='json') for b in spec.performance_budgets],'cases':[{'id':c.id,'scenario':c.scenario,'baseline':c.baseline.model_dump(mode='json') if c.baseline else None,'definition':definitions[c.id].model_dump(mode='json'),'viewport':viewports[definitions[c.id].viewport_id].model_dump(mode='json'),'state':states[definitions[c.id].state_id].name} for c in plan.cases]}
    reader.finish()
    return result


def _case_result(reader,plan,spec,report,expected_source,task_digest):
    definitions={c.id:c for c in spec.validation_cases}
    if report.case_id not in definitions or report.mode!=plan.mode or report.source!=expected_source or report.task_digest!=task_digest or report.renderer!=plan.renderer or report.environment_sha256!=plan.environment_sha256 or report.fixture_sha256!=spec.fixture.reference.sha256:
        raise HarnessError('UI report candidate/profile/fixture differs.')
    case=definitions[report.case_id]
    if {a.area for a in report.results}!=set(case.checks):raise HarnessError('UI report omits required checks.')
    budgets={b.id:b for b in spec.performance_budgets}
    for area in report.results:
        for artifact in area.artifacts:pin(reader,UIReference(path=artifact.reference.path,sha256=artifact.reference.sha256))
        if plan.mode=='verify' and area.status!='passed':raise HarnessError('Nonpassing UI result blocks governed acceptance.')
        if area.area=='performance':
            if set(report.samples)!=set(budgets) or {m.budget_id for m in area.measurements}!=set(budgets):raise HarnessError('Performance inventory incomplete.')
            for m in area.measurements:
                samples=report.samples[m.budget_id];b=budgets[m.budget_id]
                if len(samples)<b.samples or m.samples!=len(samples) or m.observed!=max(samples):raise HarnessError('Performance declaration differs from measured samples.')
                if plan.mode=='verify' and m.observed>b.maximum:raise HarnessError('Approved performance budget exceeded.')
        if area.area=='visual' and plan.mode=='verify':
            baseline=next(c.baseline for c in plan.cases if c.id==report.case_id)
            comparison=next((a for a in area.artifacts if a.kind=='comparison'),None)
            screenshot=next((a for a in area.artifacts if a.kind=='screenshot'),None)
            if not baseline or not comparison or not screenshot:raise HarnessError('Visual comparison artifacts missing.')
            value=_decode(pin(reader,UIReference(path=comparison.reference.path,sha256=comparison.reference.sha256)))
            if value!={'baseline_sha256':baseline.sha256,'actual_sha256':screenshot.reference.sha256,'maxDiffPixels':0,'engine':'playwright'}:raise HarnessError('Visual baseline/comparison binding differs.')
    return report


def verify_ui_run(root,plan,spec,task,evidence,evidence_path,report_ref,*,expected_plan_sha):
    reader=_Reader(root,'')
    raw=pin(reader,report_ref);_decode(raw);run=UIRunReport.model_validate_json(raw)
    expected=SourceIdentity(commit=evidence.source_commit,source_digest=evidence.source_digest)
    if run.mode!=plan.mode or run.plan_sha256!=expected_plan_sha or run.source!=expected or run.task_digest!=digest(task):raise HarnessError('UI run does not bind exact native execution.')
    result=next((r for r in evidence.results if r.check_id=='ui-governance'),None)
    check=next((c for c in task.checks if c.id=='ui-governance'),None)
    if result is None or check!=ui_check(plan) or result.status!='passed':raise HarnessError('Expected native UI check did not pass.')
    from algooptionx_harness.workspace import relative_path
    inventory={str(Path(evidence_path).parent/a.path):a.sha256 for r in evidence.results for a in r.artifacts}
    if inventory.get(report_ref.path)!=report_ref.sha256:raise HarnessError('UI report is not hashed by native evidence.')
    cases=[]
    for ref in run.cases:
        if inventory.get(ref.path)!=ref.sha256:raise HarnessError('Case report is not in native artifacts.')
        value=pin(reader,ref);_decode(value);case=UICaseReport.model_validate_json(value)
        if case.plan_sha256!=expected_plan_sha:raise HarnessError('Case uses another plan revision.')
        _case_result(reader,plan,spec,case,expected,digest(task))
        for area in case.results:
            for artifact in area.artifacts:
                if inventory.get(artifact.reference.path)!=artifact.reference.sha256:raise HarnessError('UI attachment omitted from native artifact manifest.')
        cases.append(case)
    if [c.case_id for c in cases]!=[c.id for c in plan.cases]:raise HarnessError('Missing, duplicated or unexpected executed UI cases.')
    reader.finish()
    return cases


def verify_measurement(root,plan,spec):
    """Reparse actual native evidence; a typed JSON declaration alone is insufficient."""
    from algooptionx_harness.runner import verify_historical_evidence
    from algooptionx_harness.designs import _Baseline
    proof=plan.measurement_baseline
    if proof is None:raise HarnessError('Measured baseline proof missing.')
    reader=_Reader(root,'')
    def model(ref,cls):
        raw=pin(reader,UIReference(path=ref.path,sha256=ref.sha256));_decode(raw);return cls.model_validate_json(raw)
    task=model(proof.task,Task);baseline=model(proof.baseline,_Baseline);candidate=model(proof.candidate,_Baseline)
    old,old_reader=read_plan(root,Path(proof.plan.path),proof.plan.sha256,reader)
    old_spec=old_reader.model(DesignReference(path=old.design.reference.path,sha256=old.design.reference.sha256),DesignSpec)
    if old.mode!='measure' or old.renderer!=plan.renderer or old.environment_sha256!=plan.environment_sha256 or old_spec.fixture!=spec.fixture or old.cases!=plan.cases or old_spec.validation_cases!=spec.validation_cases:
        raise HarnessError('Measurement method/profile/fixture/scenarios differ.')
    if [(b.id,b.metric,b.unit,b.method,b.samples) for b in old_spec.performance_budgets]!=[(b.id,b.metric,b.unit,b.method,b.samples) for b in spec.performance_budgets]:raise HarnessError('Measured budget method/sample definitions differ.')
    pin(reader,UIReference(path=proof.evidence.path,sha256=proof.evidence.sha256))
    evidence=verify_historical_evidence(root,task,baseline.model_dump(mode='json'),root/proof.evidence.path,candidate.model_dump(mode='json'))
    cases=verify_ui_run(root,old,old_spec,task,evidence,Path(proof.evidence.path),proof.report,expected_plan_sha=proof.plan.sha256)
    reader.finish()
    return cases


def collect_ui_artifacts(root,task,baseline,context,run_dir,report_path,*,successful=True):
    """Native runner attachment collector. No arbitrary directory scan or fetch."""
    from algooptionx_harness.workspace import contained,write_json,file_digest
    reader=_Reader(root,'');data=_decode(reader.raw(report_path.relative_to(root).as_posix(),ui=True));refs={};cases={}
    def add(path):
        absolute=Path(path)
        if not absolute.is_absolute():absolute=report_path.parent/absolute
        try:name=absolute.relative_to(run_dir).as_posix()
        except ValueError:raise HarnessError('UI attachment escapes the native run.') from None
        from algooptionx_harness.workspace import relative_path
        relative_path(name)
        raw=reader.raw(absolute.relative_to(root).as_posix(),4*1024*1024,ui=True)
        ref=UIReference(path=absolute.relative_to(root).as_posix(),sha256=hashlib.sha256(raw).hexdigest())
        raw=pin(reader,ref);refs[ref.path]=ref
        return raw,ref
    def visit(suites):
        for suite in suites:
            for item in suite.get('specs',[]):
                for test in item.get('tests',[]):
                    for result in test.get('results',[]):
                        for attachment in result.get('attachments',[]):
                            if 'path' not in attachment:continue
                            raw,ref=add(attachment['path'])
                            if attachment.get('name')=='ui-case':
                                _decode(raw);case=UICaseReport.model_validate_json(raw)
                                if case.case_id in cases:raise HarnessError('Duplicated UI case attachment.')
                                cases[case.case_id]=(case,ref)
            visit(suite.get('suites',[]))
    visit(data.get('suites',[]))
    if not successful:
        for case,ref in cases.values():
            for area in case.results:
                for artifact in area.artifacts:add(root/artifact.reference.path)
        reader.finish()
        return [Artifact(path=str((root/ref.path).relative_to(run_dir)),sha256=ref.sha256) for ref in refs.values()]
    if set(cases)!={c['id'] for c in context['cases']}:raise HarnessError('UI execution case inventory incomplete.')
    plan,reader=read_plan(root,Path(context['plan_path']),context['plan_sha256'],reader)
    spec=reader.model(DesignReference(path=plan.design.reference.path,sha256=plan.design.reference.sha256),DesignSpec)
    for cid in [c.id for c in plan.cases]:
        case,ref=cases[cid]
        _case_result(reader,plan,spec,case,SourceIdentity.model_validate(context['source']),context['task_digest'])
        for area in case.results:
            for artifact in area.artifacts:add(root/artifact.reference.path)
    index=UIRunReport(schema_version=1,kind='ui-run',mode=plan.mode,plan_sha256=context['plan_sha256'],source=SourceIdentity.model_validate(context['source']),task_digest=digest(task),cases=[cases[c.id][1] for c in plan.cases])
    dest=report_path.parent/'ui-report.json';write_json(dest,index)
    refs[dest.relative_to(root).as_posix()]=UIReference(path=dest.relative_to(root).as_posix(),sha256=file_digest(dest))
    reader.finish()
    return [Artifact(path=str((root/ref.path).relative_to(run_dir)),sha256=ref.sha256) for ref in refs.values()]


def emit_ui_evidence(root,task,baseline,evidence_path):
    """After native evidence, before review; never hash this back into its parent."""
    from algooptionx_harness.models import Evidence
    from algooptionx_harness.changes import parse_change
    from algooptionx_harness.designs import UIValidationEvidence
    from algooptionx_harness.workspace import write_json,file_digest
    evidence=Evidence.model_validate_json(evidence_path.read_text())
    paths=[p for p in task.protected_inputs if p.endswith('/ui-execution.json')]
    if len(paths)!=1 or evidence.status!='passed':return None
    plan,reader=read_plan(root,Path(paths[0]),baseline['files'][paths[0]]['sha256'])
    if plan.mode!='verify':return None
    parent=f'docs/changes/{plan.change_id}/r{plan.change_revision:04d}/change.json'
    change=parse_change(_decode(reader.raw(parent)))
    spec=reader.model(DesignReference(path=plan.design.reference.path,sha256=plan.design.reference.sha256),DesignSpec)
    report=evidence_path.parent/'ui-governance/ui-report.json'
    cases=verify_ui_run(root,plan,spec,task,evidence,evidence_path.relative_to(root),UIReference(path=report.relative_to(root).as_posix(),sha256=file_digest(report)),expected_plan_sha=baseline['files'][paths[0]]['sha256'])
    write_json(evidence_path.parent/'task.json',task);write_json(evidence_path.parent/'baseline.json',baseline)
    ref=lambda p:{'path':p.relative_to(root).as_posix(),'sha256':file_digest(p)}
    ui=UIValidationEvidence.model_validate_json(json.dumps({'schema_version':1,'kind':'ui-validation-evidence','change_id':change.id,'change_revision':change.revision,'change_digest':digest(change),'policy_digest':change.policy.sha256,'source':{'commit':evidence.source_commit,'source_digest':evidence.source_digest},'design':{'id':plan.design.id,'revision':plan.design.revision,'reference':plan.design.reference.model_dump(mode='json')},'native_task_reference':ref(evidence_path.parent/'task.json'),'native_task_digest':digest(task),'native_evidence_reference':ref(evidence_path),'expected_cases':[c.id for c in spec.validation_cases],'executed_cases':[{'case_id':c.case_id,'status':'passed','results':[a.model_dump(mode='json') for a in c.results]} for c in cases]}))
    output=evidence_path.parent/'ui-validation.json';write_json(output,ui);reader.finish()
    return output

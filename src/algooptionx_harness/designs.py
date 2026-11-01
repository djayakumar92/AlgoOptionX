"""Additive UI/UX declarations. Contract validity never grants approval or execution."""
from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import AwareDatetime, ConfigDict, Field, RootModel, field_validator, model_validator

from algooptionx_harness.changes import (
    ChangeContract, Identity, PolicyReference, RecordBase, Revision, Sha256,
    SourceIdentity, Versioned, safe_path, unique,
)
from algooptionx_harness.specifications import RequirementReference

Text = Annotated[str, Field(min_length=8, max_length=2000)]
Label = Annotated[str, Field(min_length=1, max_length=200)]
Number = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
Area = Literal['accessibility', 'responsive', 'visual', 'performance']
Outcome = Literal['passed', 'failed', 'skipped', 'missing', 'unverified']
StateName = Literal['loading', 'empty', 'ready', 'error', 'stale', 'disabled', 'permission']
STATE_NAMES = {'loading', 'empty', 'ready', 'error', 'stale', 'disabled', 'permission'}
SUFFIXES = {'.md', '.json', '.svg', '.png', '.jpg', '.jpeg', '.webp', '.css', '.txt', '.xml', '.log'}


class DesignReference(ChangeContract):
    path: str
    sha256: Sha256

    @field_validator('path')
    @classmethod
    def local_artifact(cls, value):
        safe_path(value)
        if any(part == '.git' or part.startswith('.env') for part in PurePosixPath(value).parts):
            raise ValueError('Environment/Git paths are forbidden.')
        if not value.startswith(('docs/', '.harness/', 'apps/web/src/')) and value != 'config/engineering-governance.json':
            raise ValueError('Use a bounded local design artifact root.')
        if PurePosixPath(value).suffix.lower() not in SUFFIXES:
            raise ValueError('Unsupported design artifact extension.')
        return value


class DesignPointer(ChangeContract):
    id: Identity
    revision: Revision
    reference: DesignReference

    @field_validator('reference')
    @classmethod
    def spec_document(cls, value):
        if not value.path.startswith('docs/') or not value.path.endswith('.json'):
            raise ValueError('Frozen design packages are JSON under docs/.')
        return value


class UserGoal(ChangeContract):
    id: Identity
    description: Text


class Journey(ChangeContract):
    id: Identity
    goal_ids: list[Identity] = Field(min_length=1, max_length=30)
    requirement_ids: list[Identity] = Field(min_length=1, max_length=50)
    component_ids: list[Identity] = Field(min_length=1, max_length=20)
    steps: list[Text] = Field(min_length=1, max_length=30)


class InteractionState(ChangeContract):
    id: Identity
    name: StateName
    applicability: Literal['applicable', 'not-applicable']
    expectation: Text
    non_applicability_reason: Text | None = None

    @model_validator(mode='after')
    def justified(self):
        if (self.applicability == 'not-applicable') != (self.non_applicability_reason is not None):
            raise ValueError('Only non-applicable states require a justification.')
        return self


class PropContract(ChangeContract):
    name: Annotated[str, Field(pattern=r'^[A-Za-z][A-Za-z0-9_]{0,63}$')]
    description: Text


class ComponentContract(ChangeContract):
    id: Identity
    screen_id: Identity
    requirement_ids: list[Identity] = Field(min_length=1, max_length=50)
    props: list[PropContract] = Field(default_factory=list, max_length=30)
    states: list[InteractionState] = Field(min_length=7, max_length=7)
    keyboard: Text
    focus: Text
    accessible_names: list[Text] = Field(min_length=1, max_length=30)

    @model_validator(mode='after')
    def state_inventory(self):
        unique([state.id for state in self.states], 'component state identities')
        unique([state.name for state in self.states], 'component state names')
        unique([prop.name for prop in self.props], 'component prop names')
        if {state.name for state in self.states} != STATE_NAMES:
            raise ValueError('Declare all seven interaction state names.')
        return self


class ScreenContract(ChangeContract):
    id: Identity
    component_ids: list[Identity] = Field(min_length=1, max_length=20)
    requirement_ids: list[Identity] = Field(min_length=1, max_length=50)


class DesignArtifact(ChangeContract):
    id: Identity
    kind: Literal['wireframe', 'mockup']
    reference: DesignReference
    requirement_ids: list[Identity] = Field(min_length=1, max_length=50)
    component_ids: list[Identity] = Field(min_length=1, max_length=20)
    state_ids: list[Identity] = Field(min_length=1, max_length=140)

    @field_validator('reference')
    @classmethod
    def static_wireframe(cls, value):
        if PurePosixPath(value.path).suffix.lower() not in {'.md', '.svg', '.png', '.jpg', '.jpeg', '.webp'}:
            raise ValueError('Wireframes/mockups must be static documents or images.')
        return value


class Viewport(ChangeContract):
    id: Identity
    width: Annotated[int, Field(strict=True, ge=240, le=7680)]
    height: Annotated[int, Field(strict=True, ge=192, le=4320)]


class RendererProfile(ChangeContract):
    id: Identity
    engine: Literal['chromium', 'firefox', 'webkit']
    version: Annotated[str, Field(pattern=r'^\d+(?:\.\d+){0,3}$')]
    operating_system: Label
    fonts_sha256: Sha256
    locale: Label
    timezone: Label
    device_scale_factor: Annotated[float, Field(strict=True, gt=0, le=4, allow_inf_nan=False)]
    reduced_motion: Literal['reduce']


class FixtureProfile(ChangeContract):
    id: Identity
    reference: DesignReference
    source: Literal['synthetic']
    clock: AwareDatetime
    seed: Annotated[int, Field(strict=True, ge=0, le=2**32-1)]


class AccessibilityTarget(ChangeContract):
    standard: Literal['WCAG-2.2-AA']
    criteria: list[Annotated[str, Field(pattern=r'^\d\.\d\.\d$')]] = Field(min_length=1, max_length=50)
    expectations: list[Text] = Field(min_length=1, max_length=50)


class PerformanceBudget(ChangeContract):
    id: Identity
    metric: Annotated[str, Field(pattern=r'^[a-z][a-z0-9-]{1,63}$')]
    unit: Literal['ms', 'bytes', 'ratio']
    maximum: Number
    samples: Annotated[int, Field(strict=True, ge=1, le=10000)]
    method: Text
    declaration: Literal['proposed', 'approval-claimed']


class ValidationCase(ChangeContract):
    id: Identity
    component_id: Identity
    state_id: Identity
    viewport_id: Identity
    theme: Literal['light', 'dark']
    checks: list[Area] = Field(min_length=1, max_length=4)


class DesignSpec(Versioned):
    kind: Literal['design-spec']
    id: Identity
    revision: Revision
    parent_change_id: Identity
    parent_change_revision: Revision
    title: Text
    requirements: list[RequirementReference] = Field(min_length=1, max_length=50)
    user_goals: list[UserGoal] = Field(min_length=1, max_length=30)
    journeys: list[Journey] = Field(min_length=1, max_length=30)
    screens: list[ScreenContract] = Field(min_length=1, max_length=20)
    components: list[ComponentContract] = Field(min_length=1, max_length=20)
    artifacts: list[DesignArtifact] = Field(min_length=1, max_length=200)
    token_references: list[DesignReference] = Field(min_length=1, max_length=8)
    viewports: list[Viewport] = Field(min_length=1, max_length=8)
    themes: list[Literal['light', 'dark']] = Field(min_length=1, max_length=2)
    renderer: RendererProfile
    fixture: FixtureProfile
    accessibility: AccessibilityTarget
    performance_budgets: list[PerformanceBudget] = Field(min_length=1, max_length=30)
    validation_cases: list[ValidationCase] = Field(min_length=1, max_length=256)
    supersedes: DesignPointer | None = None

    @model_validator(mode='after')
    def coverage(self):
        for values, label in [
            ([r.id for r in self.requirements], 'requirements'),
            ([r.id for r in self.user_goals], 'goals'),
            ([r.id for r in self.journeys], 'journeys'),
            ([r.id for r in self.screens], 'screens'),
            ([r.id for r in self.components], 'components'),
            ([r.id for r in self.artifacts], 'artifacts'),
            ([r.reference.path for r in self.artifacts], 'artifact paths'),
            ([r.path for r in self.token_references], 'token references'),
            ([r.id for r in self.viewports], 'viewports'),
            (self.themes, 'themes'),
            ([r.id for r in self.performance_budgets], 'performance budgets'),
            ([r.id for r in self.validation_cases], 'validation cases'),
            (self.accessibility.criteria, 'accessibility criteria'),
        ]:
            unique(values, label)
        reqs = {r.id for r in self.requirements}
        goals = {g.id for g in self.user_goals}
        components = {c.id: c for c in self.components}
        screens = {s.id: s for s in self.screens}
        states = {state.id: (c.id, state) for c in self.components for state in c.states}
        if len(states) != sum(len(c.states) for c in self.components):
            raise ValueError('State identities must be globally unambiguous.')
        for ref in self.requirements:
            DesignReference(path=ref.path, sha256=ref.sha256)
        if any(PurePosixPath(ref.path).suffix.lower() not in {'.css', '.json'} for ref in self.token_references):
            raise ValueError('Token references use existing CSS or JSON.')
        if not self.fixture.reference.path.endswith('.json'):
            raise ValueError('Fixtures are pinned JSON declarations.')
        for component in self.components:
            unique(component.requirement_ids, 'component requirements')
            if component.screen_id not in screens or not set(component.requirement_ids) <= reqs:
                raise ValueError('Component has unknown screen or requirement.')
        for screen in self.screens:
            unique(screen.component_ids, 'screen components')
            unique(screen.requirement_ids, 'screen requirements')
            expected = {c.id for c in self.components if c.screen_id == screen.id}
            covered = {req for cid in expected for req in components[cid].requirement_ids}
            if set(screen.component_ids) != expected or set(screen.requirement_ids) != covered:
                raise ValueError('Screen/component ownership or coverage differs.')
        for journey in self.journeys:
            for values in (journey.goal_ids, journey.requirement_ids, journey.component_ids):
                unique(values, 'journey mapping')
            if not set(journey.goal_ids) <= goals or not set(journey.requirement_ids) <= reqs or not set(journey.component_ids) <= components.keys():
                raise ValueError('Journey has unknown mappings.')
            if not set(journey.requirement_ids) <= {q for cid in journey.component_ids for q in components[cid].requirement_ids}:
                raise ValueError('Journey requirements are unrelated to its components.')
        if {q for c in self.components for q in c.requirement_ids} != reqs or {q for j in self.journeys for q in j.requirement_ids} != reqs or {g for j in self.journeys for g in j.goal_ids} != goals:
            raise ValueError('Requirements and goals must be completely traced.')
        covered_states = set()
        for artifact in self.artifacts:
            for values in (artifact.requirement_ids, artifact.component_ids, artifact.state_ids):
                unique(values, 'artifact mapping')
            if not set(artifact.component_ids) <= components.keys() or not set(artifact.requirement_ids) <= reqs or not set(artifact.state_ids) <= states.keys():
                raise ValueError('Artifact has unknown mappings.')
            for sid in artifact.state_ids:
                cid, state = states[sid]
                if cid not in artifact.component_ids or state.applicability != 'applicable':
                    raise ValueError('Artifact state mapping is inconsistent.')
                covered_states.add(sid)
            if not set(artifact.requirement_ids) <= {q for cid in artifact.component_ids for q in components[cid].requirement_ids}:
                raise ValueError('Artifact requirements are unrelated to components.')
        applicable = {sid for sid, (_, state) in states.items() if state.applicability == 'applicable'}
        if covered_states != applicable:
            raise ValueError('Applicable states need wireframe/mockup coverage.')
        expected = {(cid, sid, viewport.id, theme) for sid, (cid, state) in states.items() if state.applicability == 'applicable' for viewport in self.viewports for theme in self.themes}
        actual = {(c.component_id, c.state_id, c.viewport_id, c.theme) for c in self.validation_cases}
        if len(expected) > 256 or len(actual) != len(self.validation_cases) or actual != expected:
            raise ValueError('Validation cases must cover the bounded state/viewport/theme matrix exactly.')
        for case in self.validation_cases:
            unique(case.checks, 'case checks')
        if self.supersedes and (self.supersedes.id != self.id or self.supersedes.revision >= self.revision):
            raise ValueError('Supersession must reference an older revision of the same design.')
        return self


class ChatApprovalReference(ChangeContract):
    id: Identity
    mode: Literal['operator-recorded-chat']
    request: DesignReference
    decision: DesignReference


class SignedApprovalReference(ChangeContract):
    id: Identity
    mode: Literal['signed-external']
    receipt: DesignReference


ApprovalReference = Annotated[ChatApprovalReference | SignedApprovalReference, Field(discriminator='mode')]


class DesignBinding(RecordBase):
    kind: Literal['design-binding']
    design: DesignPointer
    policy: PolicyReference
    change_reference: DesignReference
    native_task_reference: DesignReference
    native_task_digest: Sha256
    baseline_reference: DesignReference
    baseline_digest: Sha256
    approvals: list[ApprovalReference] = Field(default_factory=list, max_length=6)

    @model_validator(mode='after')
    def policy_identity(self):
        unique([a.id for a in self.approvals], 'approval references')
        if self.policy.sha256 != self.policy_digest or self.source.source_digest != self.baseline_digest:
            raise ValueError('Policy or baseline binding differs.')
        return self


class ResultArtifact(ChangeContract):
    kind: Literal['screenshot', 'comparison', 'report']
    reference: DesignReference

    @model_validator(mode='after')
    def artifact_type(self):
        suffix = PurePosixPath(self.reference.path).suffix.lower()
        if self.kind == 'screenshot' and suffix not in {'.png', '.jpg', '.jpeg', '.webp'}:
            raise ValueError('Screenshots must be static images.')
        if self.kind == 'comparison' and suffix not in {'.png', '.json'}:
            raise ValueError('Comparisons are PNG or JSON artifacts.')
        if self.kind == 'report' and suffix not in {'.json', '.txt', '.xml', '.log'}:
            raise ValueError('Reports must use supported data formats.')
        return self


class Measurement(ChangeContract):
    budget_id: Identity
    observed: Number
    samples: Annotated[int, Field(strict=True, ge=1, le=10000)]


class AreaResult(ChangeContract):
    area: Area
    status: Outcome
    notes: Text
    artifacts: list[ResultArtifact] = Field(default_factory=list, max_length=8)
    measurements: list[Measurement] = Field(default_factory=list, max_length=30)

    @model_validator(mode='after')
    def coherent_area(self):
        unique([a.reference.path for a in self.artifacts], 'result artifact paths')
        unique([m.budget_id for m in self.measurements], 'measurement budgets')
        if self.area != 'performance' and self.measurements:
            raise ValueError('Only performance has measurements.')
        if self.status == 'passed' and self.area == 'visual' and not {'screenshot', 'comparison'} <= {a.kind for a in self.artifacts}:
            raise ValueError('Passing visual declarations need screenshot and comparison artifacts.')
        if self.status == 'passed' and self.area in {'accessibility', 'responsive'} and not any(a.kind == 'report' for a in self.artifacts):
            raise ValueError('Passing accessibility/responsive declarations need a report.')
        return self


class CaseResult(ChangeContract):
    case_id: Identity
    status: Outcome
    results: list[AreaResult] = Field(min_length=1, max_length=4)

    @model_validator(mode='after')
    def coherent_status(self):
        unique([r.area for r in self.results], 'result areas')
        statuses = {r.status for r in self.results}
        expected = next((s for s in ('failed', 'missing', 'unverified', 'skipped') if s in statuses), 'passed')
        if self.status != expected:
            raise ValueError('Case status contradicts its area declarations.')
        return self


class UIValidationEvidence(RecordBase):
    kind: Literal['ui-validation-evidence']
    design: DesignPointer
    native_task_reference: DesignReference
    native_task_digest: Sha256
    native_evidence_reference: DesignReference
    expected_cases: list[Identity] = Field(min_length=1, max_length=256)
    executed_cases: list[CaseResult] = Field(default_factory=list, max_length=256)

    @model_validator(mode='after')
    def case_inventory(self):
        unique(self.expected_cases, 'expected case identities')
        unique([case.case_id for case in self.executed_cases], 'executed cases')
        if not {case.case_id for case in self.executed_cases} <= set(self.expected_cases):
            raise ValueError('Unexpected executed case.')
        return self


DesignValue = Annotated[DesignSpec | DesignBinding | UIValidationEvidence, Field(discriminator='kind')]


class DesignRecord(RootModel[DesignValue]):
    model_config = ConfigDict(strict=True)

# Read-only inspection. No transition, rendering, approval or execution adapter.
import base64
import errno
import hashlib
import math
import os
import stat
import subprocess
import selectors
import time

from pydantic import ValidationError

from algooptionx_harness.changes import ChangeSpec, GovernancePolicy
from algooptionx_harness.governance import _json, _covers
from algooptionx_harness.models import Approval, ChatDecision, ChatRequest, Evidence, Task
from algooptionx_harness import chat
from algooptionx_harness.workspace import HarnessError, digest, relative_path

MAX_JSON = 1024 * 1024
MAX_ARTIFACT = 4 * 1024 * 1024
MAX_TOTAL = 16 * 1024 * 1024
MAX_REFERENCES = 512
MAX_DEPTH = 32
MAX_SOURCE_FILE = 16 * 1024 * 1024
MAX_SOURCE_TOTAL = 128 * 1024 * 1024
MAX_SOURCE_FILES = 4096
POLICY_PATH = 'config/engineering-governance.json'
DIAGNOSTICS = {
    'UXD_PATH': 'Use canonical local references under the documented artifact roots; symlinks are forbidden.',
    'UXD_MISSING': 'A required local record or artifact is unavailable; restore the pinned input.',
    'UXD_TYPE': 'Use regular files and the documented artifact formats.',
    'UXD_LIMIT': 'Reduce input size, nesting, collection size or total referenced bytes.',
    'UXD_JSON': 'Use valid JSON without duplicate keys, non-finite numbers or excessive nesting.',
    'UXD_VERSION': 'Use supported exact integer schema_version 1.',
    'UXD_VARIANT': 'Use one of the three supported design record kinds.',
    'UXD_SCHEMA': 'Correct required fields, strict types and unambiguous coverage mappings.',
    'UXD_HASH': 'A pinned artifact digest differs; review a new revision rather than changing the pin silently.',
    'UXD_BINDING': 'Align design, parent, policy, task, baseline and evidence identities.',
    'UXD_APPROVAL_REFERENCE': 'Supply structurally consistent native UI approval references; authority is not verified here.',
    'UXD_CYCLE': 'Remove self/circular references; bind the task after freezing its design specification.',
    'UXD_CHANGED': 'Source or referenced inputs changed during inspection; retry with stable inputs.',
    'UXD_PLATFORM': 'Secure directory-relative no-follow reads are required on this platform.',
    'UXD_POLICY': 'Supply the previously reviewed policy SHA-256 and matching fixed repository policy.',
}


class DesignError(HarnessError):
    def __init__(self, code):
        self.code = code
        super().__init__(DIAGNOSTICS[code])


def _fail(code):
    raise DesignError(code)


def _decode(raw):
    try:
        value = _json(raw)
        stack = [(value, 0)]
        count = 0
        while stack:
            item, depth = stack.pop()
            count += 1
            if depth > MAX_DEPTH or count > 20000:
                _fail('UXD_LIMIT')
            if isinstance(item, dict):
                stack.extend((child, depth + 1) for child in item.values())
            elif isinstance(item, list):
                stack.extend((child, depth + 1) for child in item)
            elif isinstance(item, float) and not math.isfinite(item):
                _fail('UXD_JSON')
        return value
    except DesignError:
        raise
    except (HarnessError, ValueError, RecursionError):
        _fail('UXD_JSON')


def _name(root, path):
    try:
        path = Path(path)
        name = path.relative_to(root).as_posix() if path.is_absolute() else path.as_posix()
        DesignReference(path=name, sha256='0' * 64)
        return name
    except (ValueError, HarnessError):
        _fail('UXD_PATH')


def _fingerprint(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_mode


class _Reader:
    def __init__(self, root, input_name):
        self.root = root
        self.input_name = input_name
        self.files = {}
        self.cache = {}
        self.total = 0
        self.active = set()
        self.reads = 0

    def _bytes(self, name, limit):
        # Directory descriptors plus O_NOFOLLOW protect every path component.
        # O_NONBLOCK and fstat prevent FIFO/device reads from hanging inspection.
        if os.open not in os.supports_dir_fd or not all(hasattr(os, key) for key in ('O_NOFOLLOW', 'O_DIRECTORY', 'O_NONBLOCK')):
            _fail('UXD_PLATFORM')
        directory = leaf = None
        try:
            directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            parts = PurePosixPath(name).parts
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                os.close(directory)
                directory = child
            leaf = os.open(parts[-1], os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=directory)
            before = os.fstat(leaf)
            if not stat.S_ISREG(before.st_mode):
                _fail('UXD_TYPE')
            if before.st_size > limit:
                _fail('UXD_LIMIT')
            chunks = []
            remaining = limit + 1
            while remaining:
                chunk = os.read(leaf, min(65536, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b''.join(chunks)
            if len(raw) > limit:
                _fail('UXD_LIMIT')
            after = os.fstat(leaf)
            if _fingerprint(before) != _fingerprint(after):
                _fail('UXD_CHANGED')
            return raw, _fingerprint(after)
        except DesignError:
            raise
        except OSError as error:
            _fail('UXD_MISSING' if error.errno == errno.ENOENT else 'UXD_PATH')
        finally:
            if leaf is not None:
                os.close(leaf)
            if directory is not None:
                os.close(directory)

    def raw(self, name, limit=MAX_JSON, *, reference=False, native=False):
        if native:
            # Only fixed role/skill inputs can bypass design artifact namespaces.
            relative_path(name)
            if not (name.startswith('src/algooptionx_harness/agents/') and name.endswith('.json') or name.startswith('.agents/skills/') and name.endswith('/SKILL.md')):
                _fail('UXD_PATH')
        else:
            name = _name(self.root, name)
        if reference and name == self.input_name:
            _fail('UXD_CYCLE')
        self.reads += 1
        if self.reads > 2048:
            _fail('UXD_LIMIT')
        if name not in self.files and len(self.files) >= MAX_REFERENCES:
            _fail('UXD_LIMIT')
        if name in self.cache:
            if len(self.cache[name]) > limit:
                _fail('UXD_LIMIT')
            return self.cache[name]
        raw, fingerprint = self._bytes(name, limit)
        sha = hashlib.sha256(raw).hexdigest()
        if name in self.files:
            if self.files[name] != (sha, fingerprint, limit):
                # A repeated file may be requested with a stricter size bound.
                old_sha, old_fingerprint, _ = self.files[name]
                if (sha, fingerprint) != (old_sha, old_fingerprint):
                    _fail('UXD_CHANGED')
        else:
            if self.total + len(raw) > MAX_TOTAL:
                _fail('UXD_LIMIT')
            self.total += len(raw)
            self.files[name] = sha, fingerprint, limit
            self.cache[name] = raw
        return raw

    def pin(self, ref, *, json_file=False):
        limit = MAX_JSON if json_file or ref.path.endswith('.json') else MAX_ARTIFACT
        raw = self.raw(ref.path, limit, reference=True)
        if self.files[ref.path][0] != ref.sha256:
            _fail('UXD_HASH')
        return raw

    def model(self, ref, cls, *, approval=False):
        raw = self.pin(ref, json_file=True)
        value = _decode(raw)
        try:
            if not isinstance(value, dict) or type(value.get('schema_version', 1)) is not int:
                raise ValueError('Native contract version must be exact.')
            return cls.model_validate_json(raw)
        except (ValueError, ValidationError, RecursionError):
            _fail('UXD_APPROVAL_REFERENCE' if approval else 'UXD_BINDING')

    def finish(self):
        for name, (sha, fingerprint, limit) in self.files.items():
            raw, after = self._bytes(name, limit)
            if hashlib.sha256(raw).hexdigest() != sha or after != fingerprint:
                _fail('UXD_CHANGED')


MAX_GIT_OUTPUT = 2 * 1024 * 1024
GIT_TIMEOUT = 10.0


def _bounded_git(root, *args):
    # Only fixed read-only native snapshot commands, never document-provided argv.
    if args not in {('rev-parse', 'HEAD'), ('ls-files', '-z', '--cached', '--others', '--exclude-standard')}:
        _fail('UXD_CHANGED')
    process = None
    try:
        process = subprocess.Popen(['git', '--no-optional-locks', '-C', str(root), *args],
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + GIT_TIMEOUT
        chunks, size = [], 0
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    _fail('UXD_LIMIT')
                events = selector.select(remaining)
                if not events:
                    _fail('UXD_LIMIT')
                chunk = os.read(process.stdout.fileno(), min(65536, MAX_GIT_OUTPUT + 1 - size))
                if not chunk:
                    selector.unregister(process.stdout)
                    break
                size += len(chunk)
                if size > MAX_GIT_OUTPUT:
                    _fail('UXD_LIMIT')
                chunks.append(chunk)
        if process.wait(timeout=max(0.001, deadline - time.monotonic())) != 0:
            _fail('UXD_CHANGED')
        return b''.join(chunks).decode('utf-8')
    except DesignError:
        raise
    except subprocess.TimeoutExpired:
        _fail('UXD_LIMIT')
    except (OSError, ValueError):
        _fail('UXD_CHANGED')
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
                process.wait()
            if process.stdout is not None:
                process.stdout.close()


def _bounded_snapshot(root):
    """Same canonical file-map convention as workspace.snapshot, bounded reads."""
    def inventory():
        names = sorted(set(filter(None, _bounded_git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').split('\0'))))
        if len(names) > MAX_SOURCE_FILES:
            _fail('UXD_LIMIT')
        for name in names:
            relative_path(name)
        return names
    try:
        commit = _bounded_git(root, 'rev-parse', 'HEAD').strip()
        names = inventory()
        reader = _Reader(root, '')
        files, total = {}, 0
        for name in names:
            try:
                raw, fingerprint = reader._bytes(name, MAX_SOURCE_FILE)
            except DesignError as error:
                if error.code == 'UXD_MISSING':
                    files[name] = {'deleted': True}
                    continue
                raise
            total += len(raw)
            if total > MAX_SOURCE_TOTAL:
                _fail('UXD_LIMIT')
            files[name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'executable': bool(fingerprint[-1] & 0o111)}
        if inventory() != names or _bounded_git(root, 'rev-parse', 'HEAD').strip() != commit:
            _fail('UXD_CHANGED')
        return {'commit': commit, 'files': files}
    except DesignError:
        raise
    except (ValueError, OSError, subprocess.CalledProcessError):
        _fail('UXD_CHANGED')


class _FileContent(ChangeContract):
    sha256: Sha256
    executable: bool


class _DeletedFile(ChangeContract):
    deleted: Literal[True]

    @field_validator('deleted', mode='before')
    @classmethod
    def exact_deleted(cls, value):
        if type(value) is not bool:
            raise ValueError('Deletion flags are booleans.')
        return value


class _Baseline(ChangeContract):
    commit: Annotated[str, Field(pattern=r'^[a-f0-9]{40,64}$')]
    files: dict[str, _FileContent | _DeletedFile] = Field(max_length=4096)

    @field_validator('files')
    @classmethod
    def source_names(cls, values):
        for name in values:
            relative_path(name)
        return values


def _load_spec(reader, pointer, *, depth=0):
    if depth > 4 or pointer.reference.path in reader.active:
        _fail('UXD_CYCLE')
    reader.active.add(pointer.reference.path)
    try:
        spec = reader.model(pointer.reference, DesignSpec)
        if (spec.id, spec.revision) != (pointer.id, pointer.revision):
            _fail('UXD_BINDING')
        _spec_artifacts(reader, spec, depth=depth)
        return spec
    finally:
        reader.active.remove(pointer.reference.path)


def _spec_artifacts(reader, spec, *, depth=0):
    import re
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    if spec.renderer.operating_system not in {'linux', 'windows', 'macos'} or not re.fullmatch(r'[a-z]{2,3}(?:-[A-Z]{2})?', spec.renderer.locale):
        _fail('UXD_SCHEMA')
    try:
        ZoneInfo(spec.renderer.timezone)
    except (ValueError, ZoneInfoNotFoundError):
        _fail('UXD_SCHEMA')
    for requirement in spec.requirements:
        raw = reader.pin(DesignReference(path=requirement.path, sha256=requirement.sha256))
        try:
            text = raw.decode('utf-8')
        except UnicodeError:
            _fail('UXD_TYPE')
        if not re.search(r'(?<![A-Z0-9-])' + re.escape(requirement.id) + r'(?![A-Z0-9-])', text):
            _fail('UXD_BINDING')
    for artifact in spec.artifacts:
        reader.pin(artifact.reference)
    for ref in spec.token_references:
        raw = reader.pin(ref)
        if ref.path.endswith('.json') and not isinstance(_decode(raw), dict):
            _fail('UXD_TYPE')
    if not isinstance(_decode(reader.pin(spec.fixture.reference, json_file=True)), dict):
        _fail('UXD_TYPE')
    if spec.supersedes:
        prior = _load_spec(reader, spec.supersedes, depth=depth + 1)
        if prior.parent_change_id != spec.parent_change_id or prior.parent_change_revision > spec.parent_change_revision:
            _fail('UXD_BINDING')


def _task(reader, reference, expected_digest):
    task = reader.model(reference, Task)
    if not reference.path.startswith('.harness/') or not reference.path.endswith('/task.json') or digest(task) != expected_digest:
        _fail('UXD_BINDING')
    return task


def _approval_refs(reader, binding, task):
    identities = set()
    for approval in binding.approvals:
        if isinstance(approval, ChatApprovalReference):
            request = reader.model(approval.request, ChatRequest, approval=True)
            decision = reader.model(approval.decision, ChatDecision, approval=True)
            try:
                consistent = (
                    request.stage == decision.stage == 'ui'
                    and task.ui_changes
                    and request.task_id == decision.task_id == task.id
                    and request.task_digest == decision.task_digest == digest(task)
                    and request.source_digest == decision.source_digest == task.baseline_digest
                    and decision.request_id == request.request_id
                    and decision.request_digest == digest(request)
                    and request.requested_at <= decision.recorded_at
                    and chat.record(request, decision.user_message, decision.recorded_by).decision == decision.decision
                )
            except (ValueError, TypeError):
                consistent = False
            identity = request.request_id
        else:
            receipt = reader.model(approval.receipt, Approval, approval=True)
            try:
                signature = base64.b64decode(receipt.signature, validate=True)
            except ValueError:
                signature = b''
            consistent = (
                receipt.stage == 'ui' and task.ui_changes
                and receipt.task_id == task.id and receipt.task_digest == digest(task)
                and receipt.source_digest == task.baseline_digest
                and receipt.evidence_digest is None and len(signature) == 64
                and receipt.issued_at < receipt.expires_at
                and not receipt.subject.lower().startswith(('agent:', 'bot:'))
                and receipt.subject != task.implementer
            )
            identity = receipt.receipt_id
        if not consistent or identity in identities:
            _fail('UXD_APPROVAL_REFERENCE')
        identities.add(identity)


def _binding(reader, binding, spec):
    from algooptionx_harness.changes import parse_change, ChangeSpecV2, NativeImplementationV2
    change = parse_change(_decode(reader.pin(binding.change_reference, json_file=True)))
    if isinstance(change, ChangeSpecV2):
        if change.design_link is None or (change.design_link.id, change.design_link.revision, change.design_link.reference.path, change.design_link.reference.sha256, change.design_link.record_digest) != (spec.id, spec.revision, binding.design.reference.path, binding.design.reference.sha256, digest(spec)):
            _fail('UXD_BINDING')
    if (change.id, change.revision, digest(change)) != (binding.change_id, binding.change_revision, binding.change_digest):
        _fail('UXD_BINDING')
    if (spec.parent_change_id, spec.parent_change_revision) != (change.id, change.revision):
        _fail('UXD_BINDING')
    if {r.id: (r.path, r.sha256) for r in spec.requirements} != {r.id: (r.path, r.sha256) for r in change.requirements}:
        _fail('UXD_BINDING')
    if binding.policy != change.policy:
        _fail('UXD_BINDING')
    actual_policy = reader.model(DesignReference(path=POLICY_PATH, sha256=binding.policy_digest), GovernancePolicy)
    if (binding.policy.id, binding.policy.revision) != (actual_policy.id, actual_policy.revision):
        _fail('UXD_POLICY')
    task = _task(reader, binding.native_task_reference, binding.native_task_digest)
    baseline = reader.model(binding.baseline_reference, _Baseline)
    if Path(binding.baseline_reference.path).parent != Path(binding.native_task_reference.path).parent or not binding.baseline_reference.path.endswith('/baseline.json'):
        _fail('UXD_BINDING')
    if reader.input_name in baseline.files or reader.input_name in task.protected_inputs:
        _fail('UXD_CYCLE')
    if (baseline.commit, digest(baseline), task.baseline_digest) != (task.source_commit, binding.baseline_digest, binding.baseline_digest) or binding.source.commit != baseline.commit:
        _fail('UXD_BINDING')
    for path, sha in [(binding.design.reference.path, binding.design.reference.sha256), (binding.change_reference.path, binding.change_reference.sha256), (POLICY_PATH, binding.policy_digest)]:
        metadata = baseline.files.get(path)
        if not isinstance(metadata, _FileContent) or metadata.sha256 != sha or path not in task.protected_inputs:
            _fail('UXD_BINDING')
    plan = next((child for child in change.children if child.id == task.id), None)
    if plan is None or isinstance(change, ChangeSpecV2) and (not isinstance(plan, NativeImplementationV2) or plan.id not in {r.id for r in change.selected_children}) or set(task.requirement_ids) != set(plan.requirement_ids):
        _fail('UXD_BINDING')
    try:
        for scope in task.allowed_paths:
            safe_path(scope, directory=True)
            if not any(_covers(parent, scope) for parent in change.allowed_paths):
                _fail('UXD_BINDING')
        for name in task.protected_inputs:
            safe_path(name)
            if not isinstance(baseline.files.get(name), _FileContent):
                _fail('UXD_BINDING')
    except ValueError:
        _fail('UXD_BINDING')
    if isinstance(change, ChangeSpecV2):
        from algooptionx_harness.governance import _check_v2_protected
        _check_v2_protected(change, task, baseline, reader)
    template = _decode(reader.pin(DesignReference(path=plan.task_template.path, sha256=plan.task_template.sha256), json_file=True))
    try:
        expected = Task.model_validate({**template, 'source_commit': baseline.commit, 'baseline_digest': digest(baseline)})
    except (ValueError, TypeError):
        _fail('UXD_BINDING')
    if task != expected:
        _fail('UXD_BINDING')
    _approval_refs(reader, binding, task)


def _native_evidence_claims(task, evidence, evidence_path, root):
    from datetime import datetime, timezone, timedelta
    from algooptionx_harness.runner import enforce_outcomes
    if evidence.started_at.tzinfo is None or evidence.finished_at.tzinfo is None or evidence.finished_at < evidence.started_at or evidence.finished_at > datetime.now(timezone.utc) + timedelta(seconds=30):
        _fail('UXD_BINDING')
    if evidence.status != 'passed':
        return
    if [result.check_id for result in evidence.results] != [check.id for check in task.checks]:
        _fail('UXD_BINDING')
    directory = root / PurePosixPath(evidence_path).parent
    for check, result in zip(task.checks, evidence.results, strict=True):
        if result.status != 'passed' or result.exit_code != 0 or result.timed_out or result.cwd != check.cwd or result.argv != [arg.replace('{run_dir}', str(directory)) for arg in check.argv]:
            _fail('UXD_BINDING')
        if not any(artifact.path == f'{check.id}.log' for artifact in result.artifacts):
            _fail('UXD_BINDING')
        if check.report:
            path = Path(check.report.replace('{run_dir}', str(directory)))
            if not path.is_absolute():
                path = root / path
            try:
                name = path.relative_to(directory).as_posix()
                safe_path(name)
            except ValueError:
                _fail('UXD_BINDING')
            if not any(artifact.path == name for artifact in result.artifacts):
                _fail('UXD_BINDING')
            try:
                enforce_outcomes(check, result.outcomes)
            except ValueError:
                _fail('UXD_BINDING')


def _ui_evidence(reader, record, spec):
    if (record.change_id, record.change_revision) != (spec.parent_change_id, spec.parent_change_revision):
        _fail('UXD_BINDING')
    task = _task(reader, record.native_task_reference, record.native_task_digest)
    # The native task already pins its sibling baseline canonically; use that
    # snapshot to recover the parent/package references without circular records.
    baseline_name = str(PurePosixPath(record.native_task_reference.path).parent / 'baseline.json')
    baseline_raw = reader.raw(baseline_name, reference=True)
    baseline_ref = DesignReference(path=baseline_name, sha256=hashlib.sha256(baseline_raw).hexdigest())
    baseline = reader.model(baseline_ref, _Baseline)
    change_name = f'docs/changes/{record.change_id}/r{record.change_revision:04d}/change.json'
    metadata = baseline.files.get(change_name)
    if not isinstance(metadata, _FileContent):
        _fail('UXD_BINDING')
    change_ref = DesignReference(path=change_name, sha256=metadata.sha256)
    from algooptionx_harness.changes import parse_change
    change = parse_change(_decode(reader.pin(change_ref, json_file=True)))
    derived = DesignBinding(
        kind='design-binding', change_id=record.change_id,
        change_revision=record.change_revision, change_digest=record.change_digest,
        policy_digest=record.policy_digest,
        source=SourceIdentity(commit=baseline.commit, source_digest=task.baseline_digest),
        design=record.design, policy=change.policy, change_reference=change_ref,
        native_task_reference=record.native_task_reference,
        native_task_digest=record.native_task_digest, baseline_reference=baseline_ref,
        baseline_digest=task.baseline_digest, approvals=[],
    )
    _binding(reader, derived, spec)
    evidence = reader.model(record.native_evidence_reference, Evidence)
    if not record.native_evidence_reference.path.startswith('.harness/'):
        _fail('UXD_BINDING')
    if record.source.commit != task.source_commit:
        _fail('UXD_BINDING')
    if (evidence.task_id, evidence.task_digest, evidence.source_commit, evidence.source_digest, evidence.final_source_digest) != (task.id, digest(task), record.source.commit, record.source.source_digest, record.source.source_digest):
        _fail('UXD_BINDING')
    _native_evidence_claims(task, evidence, record.native_evidence_reference.path, reader.root)
    # Validate native artifact bytes; this is not runner/authentication verification.
    for result in evidence.results:
        for artifact in result.artifacts:
            try:
                ref = DesignReference(path=str(PurePosixPath(record.native_evidence_reference.path).parent / artifact.path), sha256=artifact.sha256)
            except ValueError:
                _fail('UXD_PATH')
            reader.pin(ref)
    expected = {case.id: case for case in spec.validation_cases}
    if record.expected_cases != [case.id for case in spec.validation_cases]:
        _fail('UXD_BINDING')
    budgets = {budget.id: budget for budget in spec.performance_budgets}
    for case in record.executed_cases:
        required = expected[case.case_id]
        if {area.area for area in case.results} != set(required.checks):
            _fail('UXD_BINDING')
        for area in case.results:
            for artifact in area.artifacts:
                reader.pin(artifact.reference)
            if area.area == 'performance' and area.status in {'passed', 'failed'}:
                if {m.budget_id for m in area.measurements} != budgets.keys():
                    _fail('UXD_BINDING')
                failed = False
                for measurement in area.measurements:
                    budget = budgets[measurement.budget_id]
                    if measurement.samples < budget.samples:
                        _fail('UXD_BINDING')
                    failed |= measurement.observed > budget.maximum
                if (area.status == 'failed') != failed:
                    _fail('UXD_BINDING')
            elif area.measurements:
                _fail('UXD_BINDING')
        if case.status == 'passed' and evidence.status != 'passed':
            _fail('UXD_BINDING')
    summary = {status: sum(case.status == status for case in record.executed_cases) for status in ('passed', 'failed', 'skipped', 'missing', 'unverified')}
    summary['missing'] += len(set(record.expected_cases) - {case.case_id for case in record.executed_cases})
    return summary


def validate_design(root: Path, path: Path, expected_policy_sha256: str | None = None) -> dict:
    """Validate local declarations and byte pins, never readiness or approval."""
    root = root.resolve()
    name = _name(root, path)
    reader = _Reader(root, name)
    raw = reader.raw(name)
    before = _bounded_snapshot(root)
    value = _decode(raw)
    if not isinstance(value, dict):
        _fail('UXD_SCHEMA')
    if type(value.get('schema_version')) is not int or value.get('schema_version') != 1:
        _fail('UXD_VERSION')
    if value.get('kind') not in {'design-spec', 'design-binding', 'ui-validation-evidence'}:
        _fail('UXD_VARIANT')
    try:
        record = DesignRecord.model_validate_json(raw).root
    except (ValueError, ValidationError, RecursionError):
        _fail('UXD_SCHEMA')
    if isinstance(record, DesignSpec):
        if not name.startswith('docs/') or not name.endswith('.json'):
            _fail('UXD_PATH')
        reader.active.add(name)
        _spec_artifacts(reader, record)
        reader.active.remove(name)
        spec = record
    else:
        if not name.startswith('.harness/') or not name.endswith('.json'):
            _fail('UXD_PATH')
        spec = _load_spec(reader, record.design)
        if not expected_policy_sha256 or expected_policy_sha256 != record.policy_digest:
            _fail('UXD_POLICY')
    if expected_policy_sha256 is not None:
        try:
            ref = DesignReference(path=POLICY_PATH, sha256=expected_policy_sha256)
            policy = reader.model(ref, GovernancePolicy)
        except (ValueError, ValidationError):
            _fail('UXD_POLICY')
        if isinstance(record, DesignBinding) and (record.policy.id, record.policy.revision) != (policy.id, policy.revision):
            _fail('UXD_POLICY')
    cases = None
    if isinstance(record, DesignBinding):
        _binding(reader, record, spec)
    elif isinstance(record, UIValidationEvidence):
        cases = _ui_evidence(reader, record, spec)
    reader.finish()
    try:
        if _bounded_snapshot(root) != before:
            _fail('UXD_CHANGED')
    except (ValueError, OSError, subprocess.CalledProcessError):
        _fail('UXD_CHANGED')
    return {
        'status': 'DESIGN CONTRACT VALID', 'diagnostic_code': 'UXD_OK',
        'record_kind': record.kind, 'record_digest': digest(record),
        'record_file_sha256': hashlib.sha256(raw).hexdigest(),
        'design_id': spec.id, 'design_revision': spec.revision,
        'source_commit': before['commit'], 'source_digest': digest(before),
        'artifact_files_checked': len(reader.files), 'referenced_bytes_checked': reader.total,
        'case_declarations': cases, 'policy_pin_checked': expected_policy_sha256 is not None,
        'policy_adoption_authenticated': False, 'human_design_approved': False,
        'implementation_authorized': False, 'ui_visually_verified': False,
        'accessibility_certified': False, 'performance_accepted': False,
        'native_execution_authenticated': False, 'release_authorized': False,
        'phase1b_1c_design_enforcement': 'NOT IMPLEMENTED',
    }

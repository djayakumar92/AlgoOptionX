"""Additive change contracts; v1 native tasks/signature payloads stay unchanged.

These structures express obligations and references. They do not authenticate
humans, execute transitions, or confer implementation/release authority.
"""
from __future__ import annotations

from typing import Annotated, Literal
from pathlib import PurePosixPath

from pydantic import AwareDatetime, ConfigDict, Field, RootModel, field_validator, model_validator

from algooptionx_harness.models import Contract, Finding, Role, Stage
from algooptionx_harness.specifications import RequirementReference
from algooptionx_harness.workspace import relative_path

Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Identity = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9-]{2,63}$")]
Revision = Annotated[int, Field(strict=True, ge=1)]
Risk = Literal["R0", "R1", "R2", "R3"]
Purpose = Literal["local-development", "unattended-write", "release", "deployment", "broker-execution"]
State = Literal[
    "draft", "requirements-validated", "design-reviewed", "tasks-planned",
    "awaiting-human-approval", "approved-for-scoped-implementation", "in-progress",
    "validation-pending", "independently-reviewed", "awaiting-human-acceptance",
    "accepted", "archived", "cancelled", "superseded", "failed",
]
EvidenceKind = Literal["test-report", "command-log", "reference-check", "review", "human-decision"]


def safe_path(value: str, *, directory: bool = False) -> str:
    candidate = value[:-1] if directory and value.endswith("/") else value
    relative_path(candidate)
    if str(PurePosixPath(candidate)) != candidate:
        raise ValueError("Use one canonical relative path.")
    if candidate.split("/")[0] == ".git" or PurePosixPath(candidate).name.startswith(".env"):
        raise ValueError("Git metadata and environment files are not change inputs.")
    return value


def unique(values, label: str):
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate {label}.")
    return values


class ChangeContract(Contract):
    @field_validator("preserve_history", "independent_review_required", "archive_required", "grants_deployment", mode="before", check_fields=False)
    @classmethod
    def exact_boolean(cls, value):
        # Literal booleans otherwise accept 0/1 even with strict model config.
        if type(value) is not bool:
            raise ValueError("Governance flags must be exact booleans.")
        return value


class Versioned(ChangeContract):
    schema_version: Literal[1] = 1

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int:
            raise ValueError("Schema version must be an integer.")
        return value


class DocumentReference(ChangeContract):
    path: str
    sha256: Sha256

    @field_validator("path")
    @classmethod
    def document_path(cls, value):
        safe_path(value)
        if not value.startswith("docs/") or not value.endswith(".md"):
            raise ValueError("Documents must be Markdown under docs/.")
        return value


class TemplateReference(ChangeContract):
    path: str
    sha256: Sha256

    @field_validator("path")
    @classmethod
    def template_path(cls, value):
        safe_path(value)
        if not value.startswith("docs/changes/") or "/tasks/" not in value or not value.endswith(".template.json"):
            raise ValueError("Use a native task template under a change's tasks/ directory.")
        return value


class StoredReference(ChangeContract):
    path: str
    sha256: Sha256

    @field_validator("path")
    @classmethod
    def stored_path(cls, value):
        safe_path(value)
        if not value.startswith((".harness/", "docs/")):
            raise ValueError("Record artifacts must be scoped harness or document references.")
        return value


class PolicyReference(ChangeContract):
    id: Identity
    revision: Revision
    sha256: Sha256


class AcceptanceCriterion(ChangeContract):
    id: Identity
    requirement_id: Identity
    predicate: str = Field(min_length=12, max_length=2000)
    negative_case: str = Field(min_length=8, max_length=2000)
    evidence_kind: EvidenceKind


class ApprovalRequirements(ChangeContract):
    mode: Literal["operator-recorded-chat", "signed-external"]
    assurance: Literal["procedural", "signed"]
    stages: list[Stage] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def consistent(self):
        unique(self.stages, "approval stages")
        if (self.mode == "signed-external") != (self.assurance == "signed"):
            raise ValueError("Approval mode and assurance conflict.")
        return self


class RollbackObligation(ChangeContract):
    instructions: str = Field(min_length=20, max_length=4000)
    preserve_history: Literal[True]
    data_impact: Literal["none", "additive", "separate-design"]


class ChildPlan(ChangeContract):
    id: Identity
    revision: Revision
    depends_on: list[Identity] = Field(default_factory=list, max_length=100)
    requirement_ids: list[Identity] = Field(min_length=1, max_length=100)
    task_template: TemplateReference
    roles: list[Role] = Field(min_length=1, max_length=14)
    skills: list[Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")]] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def identities(self):
        for name in ("depends_on", "requirement_ids", "roles", "skills"):
            unique(getattr(self, name), name)
        if self.id in self.depends_on:
            raise ValueError("A task cannot depend on itself.")
        return self


class ChangeSpec(Versioned):
    id: Identity
    revision: Revision
    title: str = Field(min_length=8, max_length=300)
    owner: str = Field(min_length=3, max_length=200)
    purpose: Purpose
    proposal: DocumentReference
    design: DocumentReference
    requirements: list[RequirementReference] = Field(min_length=1, max_length=100)
    acceptance: list[AcceptanceCriterion] = Field(min_length=1, max_length=100)
    requested_risk: Risk
    allowed_paths: list[str] = Field(min_length=1, max_length=200)
    affected_components: list[Identity] = Field(min_length=1, max_length=100)
    children: list[ChildPlan] = Field(min_length=1, max_length=100)
    policy: PolicyReference
    approvals: ApprovalRequirements
    independent_review_required: Literal[True]
    rollback: RollbackObligation
    archive_required: Literal[True]

    @field_validator("requirements")
    @classmethod
    def requirement_paths(cls, values):
        for reference in values:
            safe_path(reference.path)
        return values

    @field_validator("allowed_paths")
    @classmethod
    def paths(cls, values):
        for value in values:
            safe_path(value, directory=True)
        return unique(values, "allowed paths")

    @model_validator(mode="after")
    def coverage(self):
        reqs = [ref.id for ref in self.requirements]
        unique(reqs, "requirement IDs")
        unique([item.id for item in self.acceptance], "acceptance IDs")
        if {item.requirement_id for item in self.acceptance} != set(reqs):
            raise ValueError("Acceptance criteria must cover exactly the requirements.")
        unique([child.id for child in self.children], "child IDs")
        unique(self.affected_components, "components")
        covered = {item for child in self.children for item in child.requirement_ids}
        if covered != set(reqs):
            raise ValueError("Children must cover exactly the parent requirements.")
        if self.purpose != "local-development" and self.approvals.mode != "signed-external":
            raise ValueError("Privileged automation requires signed external approval requirements.")
        return self


class GateDefinition(ChangeContract):
    id: Identity
    evidence_kind: EvidenceKind
    description: str = Field(min_length=8, max_length=1000)


class RiskProfile(ChangeContract):
    gates: list[Identity] = Field(min_length=1, max_length=100)
    approval_stages: list[Stage] = Field(min_length=1, max_length=6)
    independent_review_required: Literal[True]

    @model_validator(mode="after")
    def complete(self):
        unique(self.gates, "gate IDs")
        unique(self.approval_stages, "approval stages")
        if not {"implementation", "qa"} <= set(self.approval_stages):
            raise ValueError("Implementation authorization and acceptance are mandatory.")
        if not {"PYTHON", "CONFIG"} <= set(self.gates):
            raise ValueError("Existing native Python/config obligations cannot be removed.")
        return self


class PathRule(ChangeContract):
    prefix: str
    component: Identity
    minimum_risk: Risk
    gates: list[Identity] = Field(default_factory=list, max_length=100)

    @field_validator("prefix")
    @classmethod
    def prefix_path(cls, value):
        return safe_path(value, directory=True)

    @field_validator("gates")
    @classmethod
    def gate_ids(cls, values):
        return unique(values, "path gates")


class GovernancePolicy(Versioned):
    id: Identity
    revision: Revision
    authority: Literal["repository-governance"]
    signer_authority: Literal["external-trust-policy"]
    unknown_scope: Literal["block"]
    profiles: dict[Risk, RiskProfile]
    gates: list[GateDefinition] = Field(min_length=1, max_length=100)
    path_rules: list[PathRule] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def references(self):
        if set(self.profiles) != {"R0", "R1", "R2", "R3"}:
            raise ValueError("All four risk profiles must be defined.")
        unique([gate.id for gate in self.gates], "catalog gates")
        unique([rule.prefix for rule in self.path_rules], "path authority rules")
        known = {gate.id for gate in self.gates}
        used = {gate for profile in self.profiles.values() for gate in profile.gates}
        used.update(gate for rule in self.path_rules for gate in rule.gates)
        if not used <= known:
            raise ValueError("A required gate is absent from the catalog.")
        # Higher profiles may add obligations, never silently remove lower ones.
        previous_gates, previous_stages = set(), set()
        for risk in ("R0", "R1", "R2", "R3"):
            profile = self.profiles[risk]
            if not previous_gates <= set(profile.gates) or not previous_stages <= set(profile.approval_stages):
                raise ValueError("Risk profiles must preserve lower-profile obligations.")
            previous_gates, previous_stages = set(profile.gates), set(profile.approval_stages)
        return self


class SourceIdentity(ChangeContract):
    commit: Annotated[str, Field(pattern=r"^[a-f0-9]{40,64}$")]
    source_digest: Sha256


class RecordBase(Versioned):
    change_id: Identity
    change_revision: Revision
    change_digest: Sha256
    policy_digest: Sha256
    source: SourceIdentity


class IntentBinding(RecordBase):
    kind: Literal["intent"]
    child_id: Identity
    child_revision: Revision
    template_digest: Sha256
    role_skill_digests: dict[str, Sha256] = Field(min_length=1)
    purpose: Purpose


class CapturedBinding(RecordBase):
    kind: Literal["captured"]
    intent_digest: Sha256
    native_task_digest: Sha256
    baseline_digest: Sha256


class TransitionRecord(RecordBase):
    kind: Literal["transition"]
    event_id: str = Field(min_length=8, max_length=100)
    previous_record_digest: Sha256 | None
    from_state: State | None
    to_state: State
    actor: str = Field(min_length=3, max_length=200)
    recorded_at: AwareDatetime
    reason: str = Field(min_length=8, max_length=2000)
    evidence: list[StoredReference] = Field(max_length=100)


class ChangeEvidenceBinding(RecordBase):
    kind: Literal["evidence"]
    captured_binding_digest: Sha256
    native_task_digest: Sha256
    native_evidence: StoredReference
    candidate_snapshot: StoredReference
    required_gates: list[Identity] = Field(min_length=1, max_length=100)
    environment_report: StoredReference
    reviewer: StoredReference
    approval: StoredReference
    rollback_reference: StoredReference


class ReviewRecord(RecordBase):
    kind: Literal["review"]
    actor: str = Field(min_length=3, max_length=200)
    implementer_contexts: list[str] = Field(min_length=1, max_length=100)
    status: Literal["completed", "blocked", "failed"]
    reproduced_checks: list[str] = Field(max_length=100)
    findings: list[Finding] = Field(max_length=100)
    limitations: list[str] = Field(min_length=1, max_length=100)
    provenance: Literal["declared-separate-context", "externally-attested"]
    attestation: StoredReference | None

    @model_validator(mode="after")
    def independence_claim(self):
        if self.actor in self.implementer_contexts:
            raise ValueError("An implementer cannot be its reviewer.")
        if self.provenance == "externally-attested" and self.attestation is None:
            raise ValueError("External provenance requires an attestation reference.")
        if self.status == "completed" and any(f.severity in ("high", "critical") for f in self.findings):
            raise ValueError("Blocking findings cannot be completed.")
        return self


class AcceptanceRecord(RecordBase):
    kind: Literal["acceptance"]
    aggregate_task_digest: Sha256
    aggregate_evidence: StoredReference
    review: StoredReference
    human_decision: StoredReference
    approval_mode: Literal["operator-recorded-chat", "signed-external"]
    grants_deployment: Literal[False]


class ArchiveRecord(RecordBase):
    kind: Literal["archive"]
    acceptance: StoredReference
    child_evidence: list[StoredReference] = Field(min_length=1, max_length=100)
    rollback_reference: StoredReference
    artifacts: list[StoredReference] = Field(min_length=1, max_length=1000)


class KnowledgeRecord(RecordBase):
    kind: Literal["knowledge"]
    finding: str = Field(min_length=12, max_length=4000)
    classification: Literal["VERIFIED", "PARTIALLY VERIFIED", "NOT VERIFIED", "MISSING", "PROPOSED"]
    owner: str = Field(min_length=3, max_length=200)
    evidence: list[StoredReference] = Field(min_length=1, max_length=100)
    freshness_conditions: list[str] = Field(min_length=1, max_length=100)
    invalidation_conditions: list[str] = Field(min_length=1, max_length=100)


Record = Annotated[
    IntentBinding | CapturedBinding | TransitionRecord | ChangeEvidenceBinding |
    ReviewRecord | AcceptanceRecord | ArchiveRecord | KnowledgeRecord,
    Field(discriminator="kind"),
]


class ChangeRecord(RootModel[Record]):
    model_config = ConfigDict(strict=True)


# UI/UX v2 is additive. Never change Versioned/ChangeSpec/ChangeRecord v1.
class VersionedV2(ChangeContract):
    schema_version: Literal[2]

    @field_validator('schema_version', mode='before')
    @classmethod
    def exact_v2(cls, value):
        if type(value) is not int or value != 2:
            raise ValueError('Use exact integer schema version 2.')
        return value


class ChildIdentityV2(ChangeContract):
    id: Identity
    revision: Revision


class ChildPlanV2(ChangeContract):
    id: Identity
    revision: Revision
    required: bool
    depends_on: list[ChildIdentityV2] = Field(default_factory=list, max_length=100)
    requirement_ids: list[Identity] = Field(min_length=1, max_length=100)
    acceptance_ids: list[Identity] = Field(min_length=1, max_length=100)
    roles: list[Role] = Field(min_length=1, max_length=14)
    skills: list[Annotated[str, Field(pattern=r'^[a-z][a-z0-9-]{1,63}$')]] = Field(min_length=1, max_length=64)

    @model_validator(mode='after')
    def unique_mappings(self):
        for field in ('requirement_ids', 'acceptance_ids', 'roles', 'skills'):
            unique(getattr(self, field), field)
        unique([ref.id for ref in self.depends_on], 'dependency identities')
        if self.id in {ref.id for ref in self.depends_on}:
            raise ValueError('Self dependency rejected.')
        return self


class NativeImplementationV2(ChildPlanV2):
    kind: Literal['native-implementation']
    task_template: TemplateReference


class DesignValidationV2(ChildPlanV2):
    kind: Literal['design-validation']


class TestEvidenceV2(ChildPlanV2):
    kind: Literal['test-evidence']


class IndependentReviewV2(ChildPlanV2):
    kind: Literal['independent-review']
    subject: Literal['design', 'candidate']


TypedChildV2 = Annotated[
    NativeImplementationV2 | DesignValidationV2 | TestEvidenceV2 | IndependentReviewV2,
    Field(discriminator='kind'),
]


class FrozenDesignV2(ChangeContract):
    id: Identity
    revision: Revision
    reference: StoredReference
    record_digest: Sha256

    @field_validator('reference')
    @classmethod
    def frozen_json(cls, value):
        if not value.path.startswith('docs/') or not value.path.endswith('.json'):
            raise ValueError('Frozen design is JSON under docs/.')
        return value


class DesignObligationsV2(ChangeContract):
    case_ids: list[Identity] = Field(min_length=1, max_length=256)
    required_areas: list[Literal['accessibility', 'responsive', 'visual', 'performance']] = Field(min_length=4, max_length=4)
    validation_children: list[Identity] = Field(min_length=1, max_length=100)
    design_review_child: Identity
    candidate_evidence_children: list[Identity] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def inventories(self):
        for field in ('case_ids', 'required_areas', 'validation_children', 'candidate_evidence_children'):
            unique(getattr(self, field), field)
        return self


class ChangeSpecV2(VersionedV2):
    kind: Literal['change-spec']
    id: Identity
    revision: Revision
    title: str = Field(min_length=8, max_length=300)
    owner: str = Field(min_length=3, max_length=200)
    purpose: Purpose
    proposal: DocumentReference
    design: DocumentReference
    requirements: list[RequirementReference] = Field(min_length=1, max_length=100)
    acceptance: list[AcceptanceCriterion] = Field(min_length=1, max_length=100)
    requested_risk: Risk
    allowed_paths: list[str] = Field(min_length=1, max_length=200)
    affected_components: list[Identity] = Field(min_length=1, max_length=100)
    children: list[TypedChildV2] = Field(min_length=1, max_length=100)
    selected_children: list[ChildIdentityV2] = Field(min_length=1, max_length=100)
    execution_order: list[ChildIdentityV2] = Field(min_length=1, max_length=100)
    candidate_review_child: Identity
    design_link: FrozenDesignV2 | None = None
    design_obligations: DesignObligationsV2 | None = None
    policy: PolicyReference
    approvals: ApprovalRequirements
    independent_review_required: Literal[True]
    rollback: RollbackObligation
    archive_required: Literal[True]
    supersedes: StoredReference | None = None

    @model_validator(mode='after')
    def v2_invariants(self):
        for field in ('allowed_paths', 'affected_components'):
            unique(getattr(self, field), field)
        for path in self.allowed_paths:
            safe_path(path, directory=True)
        for ref in self.requirements:
            safe_path(ref.path)
        reqs = {r.id for r in self.requirements}
        unique([r.id for r in self.requirements], 'requirements')
        unique([a.id for a in self.acceptance], 'acceptance')
        acceptance = {a.id: a for a in self.acceptance}
        if {a.requirement_id for a in self.acceptance} != reqs:
            raise ValueError('Acceptance must cover exact requirements.')
        unique([c.id for c in self.children], 'children')
        nodes = {c.id: c for c in self.children}
        selected = {c.id for c in self.selected_children}
        unique([c.id for c in self.selected_children], 'selected children')
        unique([c.id for c in self.execution_order], 'execution order')
        if {c.id for c in self.execution_order} != selected or not {c.id for c in self.children if c.required} <= selected:
            raise ValueError('Selection/order must include every mandatory child exactly once.')
        for ref in [*self.selected_children, *self.execution_order, *(r for c in self.children for r in c.depends_on)]:
            if ref.id not in nodes or ref.revision != nodes[ref.id].revision:
                raise ValueError('Missing or stale child reference.')
        for c in self.children:
            if not set(c.requirement_ids) <= reqs or not set(c.acceptance_ids) <= acceptance.keys():
                raise ValueError('Unknown child coverage.')
            if any(acceptance[aid].requirement_id not in c.requirement_ids for aid in c.acceptance_ids):
                raise ValueError('Acceptance and child requirement coverage differ.')
        if {q for cid in selected for q in nodes[cid].requirement_ids} != reqs or {a for cid in selected for a in nodes[cid].acceptance_ids} != acceptance.keys():
            raise ValueError('Selected children must cover every requirement and acceptance condition.')
        # Validate all nodes, even unselected optional definitions, without execution.
        remaining, visited = set(nodes), set()
        while remaining:
            ready = {name for name in remaining if {r.id for r in nodes[name].depends_on} <= visited}
            if not ready:
                raise ValueError('Dependency cycle rejected.')
            remaining -= ready
            visited |= ready
        seen = set()
        for ref in self.execution_order:
            if not {r.id for r in nodes[ref.id].depends_on} <= seen:
                raise ValueError('Selected order must be dependency-closed and topological.')
            seen.add(ref.id)
        review = nodes.get(self.candidate_review_child)
        if not isinstance(review, IndependentReviewV2) or review.subject != 'candidate' or review.id not in selected or not review.required:
            raise ValueError('Mandatory selected candidate review required.')
        ancestors = set()
        def collect(name):
            for ref in nodes[name].depends_on:
                if ref.id not in ancestors:
                    ancestors.add(ref.id); collect(ref.id)
        collect(review.id)
        if not selected - {review.id} <= ancestors:
            raise ValueError('Candidate review must depend on all other selected children.')
        if (self.design_link is None) != (self.design_obligations is None):
            raise ValueError('Design linkage and obligations must appear together.')
        if self.design_obligations:
            o = self.design_obligations
            expected = [(cid, DesignValidationV2) for cid in o.validation_children]
            expected += [(cid, TestEvidenceV2) for cid in o.candidate_evidence_children]
            expected += [(o.design_review_child, IndependentReviewV2)]
            for cid, cls in expected:
                if cid not in selected or not isinstance(nodes.get(cid), cls) or not nodes[cid].required:
                    raise ValueError('Design obligations require mandatory selected children of the correct kind.')
            dr = nodes[o.design_review_child]
            if dr.subject != 'design' or not set(o.validation_children) <= {r.id for r in dr.depends_on}:
                raise ValueError('Design review must depend on design validation.')
            for c in self.children:
                if isinstance(c, NativeImplementationV2) and c.id in selected and o.design_review_child not in _v2_ancestors(nodes, c.id):
                    raise ValueError('Implementation must depend on design review.')
        elif any(isinstance(c, DesignValidationV2) or isinstance(c, IndependentReviewV2) and c.subject == 'design' for c in self.children):
            raise ValueError('Design children require a frozen design link.')
        if self.purpose != 'local-development' and self.approvals.mode != 'signed-external':
            raise ValueError('Privileged purposes require existing signed approval mode.')
        return self


def _v2_ancestors(nodes, name):
    found, pending = set(), [r.id for r in nodes[name].depends_on]
    while pending:
        parent = pending.pop()
        if parent not in found:
            found.add(parent); pending.extend(r.id for r in nodes[parent].depends_on)
    return found


def parse_change(value) -> ChangeSpec | ChangeSpecV2:
    """Strict version dispatch; preserve legacy missing-version behavior only for v1."""
    if not isinstance(value, dict) or type(value.get('schema_version', 1)) is not int:
        raise ValueError('Change version must be an exact integer.')
    version = value.get('schema_version', 1)
    if version == 1:
        return ChangeSpec.model_validate(value)
    if version == 2:
        return ChangeSpecV2.model_validate(value)
    raise ValueError('Unsupported change schema version.')

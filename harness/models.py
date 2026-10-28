"""Strict, versioned contracts shared by agents, runners and human verifiers."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Digest = str
Stage = Literal["plan", "architecture", "ui", "implementation", "qa", "release"]
Role = Literal[
    "product",
    "requirements-validator",
    "architect",
    "ui-designer",
    "frontend-engineer",
    "backend-engineer",
    "quant-researcher",
    "ml-engineer",
    "risk-engineer",
    "security-engineer",
    "test-engineer",
    "e2e-engineer",
    "independent-validator",
    "release-governor",
]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Check(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    kind: Literal["command", "pytest", "playwright"]
    argv: list[str] = Field(min_length=1, max_length=50)
    cwd: str = "."
    timeout_seconds: int = Field(default=120, ge=1, le=900)
    report: str | None = None
    allowed_skips: list[str] = []
    critical_tests: list[str] = []

    @model_validator(mode="after")
    def report_required(self):
        if self.kind != "command" and not self.report:
            raise ValueError(
                "Test checks require a report in the unique run directory."
            )
        if self.kind == "command" and (self.allowed_skips or self.critical_tests):
            raise ValueError("Only test checks can declare test outcomes.")
        if any("\x00" in arg for arg in self.argv):
            raise ValueError("NUL is forbidden in command arguments.")
        return self


class Task(Contract):
    schema_version: Literal[1] = 1
    id: str = Field(pattern=r"^[A-Z][A-Z0-9-]{2,63}$")
    title: str = Field(min_length=8, max_length=300)
    implementer: str = Field(min_length=3)
    requirement_ids: list[str] = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[a-f0-9]{40,64}$")
    baseline_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    allowed_paths: list[str] = Field(min_length=1)
    protected_inputs: list[str] = Field(min_length=1)
    ui_changes: bool = False
    checks: list[Check] = Field(min_length=1)
    acceptance: list[str] = Field(min_length=1)
    rollback: str = Field(min_length=10)

    @model_validator(mode="after")
    def unique_checks(self):
        ids = [c.id for c in self.checks]
        if len(ids) != len(set(ids)):
            raise ValueError("Check IDs must be unique.")
        if not any(c.kind == "pytest" for c in self.checks):
            raise ValueError(
                "At least one failure-sensitive Python test check is required."
            )
        if (
            any(path.startswith("frontend/") for path in self.allowed_paths)
            and not self.ui_changes
        ):
            raise ValueError(
                "Frontend scope requires explicit UI approval and browser checks."
            )
        if self.ui_changes and not any(c.kind == "playwright" for c in self.checks):
            raise ValueError("UI tasks require browser evidence.")
        return self


class Artifact(Contract):
    path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class TestOutcome(Contract):
    id: str
    status: Literal["passed", "failed", "skipped"]
    reason: str = ""


class Result(Contract):
    check_id: str
    argv: list[str]
    cwd: str
    exit_code: int | None
    timed_out: bool
    status: Literal["passed", "failed"]
    detail: str
    duration_seconds: float
    artifacts: list[Artifact]
    outcomes: list[TestOutcome]


class Evidence(Contract):
    schema_version: Literal[1] = 1
    run_id: str
    task_id: str
    task_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    final_source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_commit: str
    started_at: datetime
    finished_at: datetime
    status: Literal["passed", "failed"]
    changed_paths: list[str]
    results: list[Result]
    runtime: dict[str, str]


class Approval(Contract):
    schema_version: Literal[1] = 1
    receipt_id: str = Field(min_length=8)
    task_id: str
    task_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    stage: Stage
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    subject: str = Field(min_length=3)
    actor_type: Literal["human"]
    decision: Literal["approve", "reject"]
    issued_at: datetime
    expires_at: datetime
    nonce: str = Field(min_length=16)
    key_id: str
    signature: str

    @field_validator("issued_at", "expires_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("Approval timestamps must include a timezone.")
        return value


class Principal(Contract):
    subject: str
    public_key: str
    actor_type: Literal["human"]
    stages: list[Stage] = Field(min_length=1)


class TrustPolicy(Contract):
    schema_version: Literal[1] = 1
    max_approval_age_hours: int = Field(default=72, ge=1, le=168)
    max_evidence_age_hours: int = Field(default=24, ge=1, le=168)
    keys: dict[str, Principal]
    require_distinct_qa_release: bool = False


class Finding(Contract):
    severity: Literal["critical", "high", "medium", "low", "info"]
    description: str = Field(min_length=8)
    requirement_id: str | None = None


class Handoff(Contract):
    schema_version: Literal[1] = 1
    task_id: str
    task_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    role: Role
    actor: str = Field(min_length=3)
    requirement_ids: list[str] = Field(min_length=1)
    status: Literal["completed", "blocked", "failed"]
    summary: str = Field(min_length=20)
    artifacts: list[Artifact]
    findings: list[Finding]
    next_role: Role | None = None


class AgentRole(Contract):
    schema_version: Literal[1] = 1
    id: Role
    title: str = Field(min_length=5)
    purpose: str = Field(min_length=20)
    sandbox: Literal["read-only", "workspace-write"]
    allowed_tools: list[str] = Field(min_length=1)
    forbidden_actions: list[str] = Field(min_length=1)
    skills: list[str] = Field(min_length=1)
    default_next_role: Role
    human_approval_authority: Literal[False]


class ChatRequest(Contract):
    schema_version: Literal[1] = 1
    request_id: str
    task_id: str
    task_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    stage: Stage
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_digest: str | None = None
    summary: str = Field(min_length=8)
    requested_at: datetime
    approval_text: str
    evidence_path: str | None = None
    review_path: str | None = None
    grants_deployment: Literal[False] = False


class ChatDecision(Contract):
    schema_version: Literal[1] = 1
    request_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_id: str
    task_id: str
    task_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    stage: Stage
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: Literal["approve", "reject"]
    user_message: str = Field(min_length=1)
    recorded_by: str = Field(min_length=3)
    recorded_at: datetime
    verification: Literal["operator-recorded-chat"] = "operator-recorded-chat"
    grants_deployment: Literal[False] = False

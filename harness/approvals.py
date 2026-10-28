"""Verify detached Ed25519 receipts against an externally managed trust policy.

Public key verification is real. Local filesystem placement cannot establish
that an agent lacks admin access; the deployment boundary must enforce that.
"""

from __future__ import annotations
import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from harness.models import Approval, Task, TrustPolicy
from harness.workspace import HarnessError, canonical, digest

PRE_STAGES = ["plan", "architecture", "ui", "implementation"]


def signing_payload(receipt: Approval) -> bytes:
    return canonical(receipt.model_dump(mode="json", exclude={"signature"}))


def load_policy(path: Path, root: Path) -> TrustPolicy:
    if path.is_symlink() or path.resolve().is_relative_to(root.resolve()):
        raise HarnessError(
            "Approval trust policy must be external to the agent checkout, never repository-authored."
        )
    policy = TrustPolicy.model_validate_json(path.read_text())
    if not policy.keys:
        raise HarnessError(
            "No externally enrolled human approvers. Gates remain blocked."
        )
    return policy


def verify_receipt(
    receipt: Approval,
    task: Task,
    policy: TrustPolicy,
    source_digest: str,
    evidence_digest: str | None,
    now: datetime,
):
    principal = policy.keys.get(receipt.key_id)
    if principal is None or principal.subject != receipt.subject:
        raise HarnessError("Unknown key or key/subject mismatch.")
    if receipt.subject == task.implementer or receipt.subject.lower().startswith(
        ("agent:", "bot:")
    ):
        raise HarnessError("An implementer or agent cannot approve this task.")
    if receipt.stage not in principal.stages:
        raise HarnessError("Signer is not authorized for this stage.")
    if receipt.task_id != task.id or receipt.task_digest != digest(task):
        raise HarnessError("Approval belongs to another task or task revision.")
    if (
        receipt.source_digest != source_digest
        or receipt.evidence_digest != evidence_digest
    ):
        raise HarnessError("Approval source/evidence binding is stale.")
    if receipt.issued_at > now + timedelta(seconds=30) or receipt.expires_at <= now:
        raise HarnessError("Approval is expired or future-dated.")
    if receipt.expires_at <= receipt.issued_at or now - receipt.issued_at > timedelta(
        hours=policy.max_approval_age_hours
    ):
        raise HarnessError("Approval validity interval is invalid or too old.")
    try:
        public = base64.b64decode(principal.public_key, validate=True)
        signature = base64.b64decode(receipt.signature, validate=True)
        Ed25519PublicKey.from_public_bytes(public).verify(
            signature, signing_payload(receipt)
        )
    except (InvalidSignature, ValueError) as exc:
        raise HarnessError("Invalid human approval signature.") from exc
    if receipt.decision != "approve":
        raise HarnessError("Human rejected this stage.")


def verify_gate(
    task: Task,
    stage: str,
    receipts: list[Approval],
    policy: TrustPolicy,
    current_source: str,
    evidence_digest: str | None = None,
    evidence_finished_at: datetime | None = None,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    stages = [s for s in PRE_STAGES if s != "ui" or task.ui_changes]
    if stage in ("qa", "release"):
        stages.append("qa")
    if stage == "release":
        stages.append("release")
    if stage not in stages:
        raise HarnessError("Stage is not applicable to this task.")
    stages = stages[: stages.index(stage) + 1]
    if stage == "implementation" and current_source != task.baseline_digest:
        raise HarnessError(
            "Implementation authorization applies only to the reviewed baseline."
        )
    if stage in ("qa", "release"):
        if not evidence_digest or not evidence_finished_at:
            raise HarnessError("QA/release require verified passing evidence.")
        if evidence_finished_at > now or now - evidence_finished_at > timedelta(
            hours=policy.max_evidence_age_hours
        ):
            raise HarnessError("Validation evidence is stale or future-dated.")
    seen_ids, seen_nonces, by_stage = set(), set(), {}
    for receipt in receipts:
        if receipt.receipt_id in seen_ids or receipt.nonce in seen_nonces:
            raise HarnessError("Duplicate receipt ID or replayed approval nonce.")
        seen_ids.add(receipt.receipt_id)
        seen_nonces.add(receipt.nonce)
        if receipt.stage in by_stage:
            raise HarnessError(
                "Conflicting receipts: resolve the stage through the external approval service."
            )
        by_stage[receipt.stage] = receipt
    previous_time = None
    for required in stages:
        receipt = by_stage.get(required)
        if receipt is None:
            raise HarnessError(f"Missing signed human {required} approval.")
        post = required in ("qa", "release")
        verify_receipt(
            receipt,
            task,
            policy,
            current_source if post else task.baseline_digest,
            evidence_digest if post else None,
            now,
        )
        if previous_time and receipt.issued_at < previous_time:
            raise HarnessError("Approval sequence is out of order.")
        if post and receipt.issued_at < evidence_finished_at:
            raise HarnessError("Human approval predates the validation evidence.")
        previous_time = receipt.issued_at
    if (
        stage == "release"
        and policy.require_distinct_qa_release
        and by_stage["qa"].subject == by_stage["release"].subject
    ):
        raise HarnessError(
            "Independent QA and release authorization require different humans."
        )
    return {
        "status": "verified",
        "task_id": task.id,
        "stage": stage,
        "source_digest": current_source,
        "evidence_digest": evidence_digest,
        "receipt_ids": [by_stage[s].receipt_id for s in stages],
        "deployment_performed": False,
    }

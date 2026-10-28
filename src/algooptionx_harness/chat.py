"""Conversation-first review queue. Records decisions; never fabricates signatures.

The trusted chat assistant must observe the real human reply before recording
it. These portable files alone cannot prove a message's human origin and are
never accepted by the cryptographic/deployment gate.
"""

from datetime import datetime, timezone
import uuid

from algooptionx_harness.models import ChatRequest, ChatDecision
from algooptionx_harness.workspace import HarnessError, digest


def request(
    task,
    stage,
    source_digest,
    evidence_digest=None,
    evidence_path=None,
    review_path=None,
):
    if stage == "ui" and not task.ui_changes:
        raise HarnessError("No UI approval is required for this task.")
    if stage in ("qa", "release") and not evidence_digest:
        raise HarnessError(
            "QA/release review needs verified evidence and independent review."
        )
    identity = str(uuid.uuid4())
    return ChatRequest(
        request_id=identity,
        task_id=task.id,
        task_digest=digest(task),
        stage=stage,
        source_digest=source_digest,
        evidence_digest=evidence_digest,
        summary=task.title,
        requested_at=datetime.now(timezone.utc),
        evidence_path=evidence_path,
        review_path=review_path,
        approval_text=f"APPROVE {task.id} {stage} {identity}",
    )


def record(review: ChatRequest, message: str, recorded_by: str):
    normalized = " ".join(message.strip().lower().split())
    if normalized in (
        "approve",
        "approved",
        "yes",
        "i approve",
        "i approve this",
        review.approval_text.lower(),
    ):
        decision = "approve"
    elif normalized in ("reject", "rejected", "no", "do not approve", "i reject"):
        decision = "reject"
    else:
        raise HarnessError(
            "Ambiguous reply: preserve it in the conversation and ask for an explicit approval/rejection."
        )
    return ChatDecision(
        request_digest=digest(review),
        request_id=review.request_id,
        task_id=review.task_id,
        task_digest=review.task_digest,
        stage=review.stage,
        source_digest=review.source_digest,
        decision=decision,
        user_message=message,
        recorded_by=recorded_by,
        recorded_at=datetime.now(timezone.utc),
    )


def verify_record(
    task,
    review: ChatRequest,
    decision: ChatDecision,
    current_digest: str,
    current_evidence_digest=None,
):
    if (
        review.task_id != task.id
        or review.task_digest != digest(task)
        or decision.task_digest != digest(task)
    ):
        raise HarnessError("Chat review belongs to another task revision.")
    if (
        decision.request_digest != digest(review)
        or decision.request_id != review.request_id
        or decision.stage != review.stage
    ):
        raise HarnessError("Chat decision does not match this review request.")
    expected = (
        current_digest if review.stage in ("qa", "release") else task.baseline_digest
    )
    if review.source_digest != expected or decision.source_digest != expected:
        raise HarnessError(
            "Chat review is stale; prepare a new request for the changed source."
        )
    if (
        review.stage in ("qa", "release")
        and review.evidence_digest != current_evidence_digest
    ):
        raise HarnessError(
            "Chat review evidence changed; prepare a new review request."
        )
    if decision.recorded_at.tzinfo is None or review.requested_at.tzinfo is None:
        raise HarnessError("Chat decision timestamps must include timezones.")
    if decision.recorded_at < review.requested_at:
        raise HarnessError("Decision cannot predate the review request.")
    if (
        record(review, decision.user_message, decision.recorded_by).decision
        != decision.decision
    ):
        raise HarnessError("Recorded decision contradicts the human reply.")
    return {
        "status": "recorded" if decision.decision == "approve" else "rejected",
        "stage": review.stage,
        "verification": "operator-recorded-chat",
        "human_origin_cryptographically_verified": False,
        "grants_deployment": False,
    }


def queue(root, task, baseline, current_digest):
    import json
    from pathlib import Path
    from algooptionx_harness.runner import verify_evidence
    from algooptionx_harness.orchestration import accept_handoff
    from algooptionx_harness.workspace import file_digest

    requests = []
    for path in (root / ".harness/requests").glob("*.json"):
        raw = json.loads(path.read_text())
        if raw.get("task_id") == task.id and "approval_text" in raw:
            requests.append(ChatRequest.model_validate_json(path.read_text()))
    decisions = [
        ChatDecision.model_validate_json(path.read_text())
        for path in (root / ".harness/chat-decisions").glob("*.json")
    ]
    states = []
    previous_approved = True
    for stage in [
        "plan",
        "architecture",
        *(["ui"] if task.ui_changes else []),
        "implementation",
        "qa",
        "release",
    ]:
        candidates = [item for item in requests if item.stage == stage]
        state = {"stage": stage, "status": "waiting_for_human_in_chat"}
        if candidates:
            review = max(candidates, key=lambda item: item.requested_at)
            matches = [
                item for item in decisions if item.request_id == review.request_id
            ]
            if len(matches) > 1:
                state = {
                    "stage": stage,
                    "status": "blocked",
                    "reason": "Conflicting chat decisions; resolve explicitly with the human.",
                }
            elif matches:
                try:
                    binding = None
                    if stage in ("qa", "release"):
                        if not review.evidence_path or not review.review_path:
                            raise HarnessError(
                                "Post-implementation review lacks evidence locations."
                            )
                        evidence = verify_evidence(
                            root, task, baseline, Path(review.evidence_path)
                        )
                        independent = accept_handoff(
                            root,
                            task,
                            baseline,
                            Path(review.review_path),
                            "independent-validator",
                        )
                        if independent.status != "completed":
                            raise HarnessError("Independent review is not complete.")
                        binding = digest(
                            {
                                "validation": digest(evidence),
                                "independent_review": file_digest(
                                    Path(review.review_path)
                                ),
                            }
                        )
                    state = verify_record(
                        task, review, matches[0], current_digest, binding
                    )
                    if state["status"] == "recorded" and not previous_approved:
                        state = {
                            "stage": stage,
                            "status": "blocked",
                            "reason": "An earlier review stage has not been approved.",
                        }
                except (HarnessError, OSError, ValueError) as exc:
                    state = {"stage": stage, "status": "blocked", "reason": str(exc)}
            state["request_id"] = review.request_id
        states.append(state)
        previous_approved = previous_approved and state["status"] == "recorded"
    return {
        "task_id": task.id,
        "approval_mode": "chat",
        "human_approver": "the user in the current conversation",
        "stages": states,
        "technical_human_identity_enforcement": "NOT VERIFIED",
        "deployment_performed": False,
    }

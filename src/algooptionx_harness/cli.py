from __future__ import annotations
import argparse
import json
import sys
import uuid
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import ValidationError

from algooptionx_harness.approvals import load_policy, verify_gate
from algooptionx_harness import chat
from algooptionx_harness.models import (
    Approval,
    Evidence,
    Handoff,
    Task,
    TrustPolicy,
    AgentRole,
    ChatRequest,
    ChatDecision,
)
from algooptionx_harness.orchestration import (
    accept_handoff,
    codex_worker,
    dispatch,
    validate_configuration,
)
from algooptionx_harness.runner import run_task, verify_evidence
from algooptionx_harness.workspace import (
    HarnessError,
    capture_task,
    contained,
    digest,
    load_task,
    snapshot,
    validate_scope,
    write_json,
    file_digest,
)


def gate(
    root,
    task,
    baseline,
    stage,
    policy_path,
    receipt_dir,
    evidence_path=None,
    review_path=None,
):
    current = snapshot(root)
    validate_scope(task, baseline, current)
    policy = load_policy(policy_path, root)
    receipts = [
        Approval.model_validate_json(p.read_text())
        for p in sorted(receipt_dir.glob("*.json"))
    ]
    evidence = (
        verify_evidence(root, task, baseline, evidence_path) if evidence_path else None
    )
    evidence_binding = digest(evidence) if evidence else None
    if stage in ("qa", "release"):
        if not evidence or not review_path:
            raise HarnessError(
                "QA/release require current evidence and an independent-validator handoff."
            )
        review = accept_handoff(
            root, task, baseline, review_path, "independent-validator"
        )
        if review.status != "completed":
            raise HarnessError("Independent review is not complete.")
        evidence_binding = digest(
            {
                "validation": digest(evidence),
                "independent_review": file_digest(review_path),
            }
        )
    return verify_gate(
        task,
        stage,
        receipts,
        policy,
        digest(current),
        evidence_binding,
        evidence.finished_at if evidence else None,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="algooptionx-harness")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser(
        "init", help="Capture current checkout without overwriting existing work."
    )
    init.add_argument("template", type=Path)
    init.add_argument("--output", type=Path, required=True)
    for name in (
        "run",
        "verify-evidence",
        "dispatch",
        "accept-handoff",
        "worker",
        "gate",
        "status",
        "approval-request",
        "chat-request",
    ):
        cmd = sub.add_parser(name)
        cmd.add_argument("task", type=Path)
        if name in ("verify-evidence",):
            cmd.add_argument("evidence", type=Path)
        if name in ("dispatch", "accept-handoff", "worker"):
            cmd.add_argument("--role", required=True)
        if name == "accept-handoff":
            cmd.add_argument("handoff", type=Path)
        if name in ("gate", "status", "worker", "approval-request", "chat-request"):
            cmd.add_argument("--policy", type=Path)
            cmd.add_argument("--receipts", type=Path)
            cmd.add_argument("--evidence", type=Path)
            cmd.add_argument("--review", type=Path)
        if name == "worker":
            cmd.add_argument("--timeout", type=int, default=300)
        if name == "approval-request":
            cmd.add_argument("--subject", required=True)
            cmd.add_argument("--key-id", required=True)
            cmd.add_argument("--output", type=Path, required=True)
        if name == "chat-request":
            cmd.add_argument("--output", type=Path, required=True)
        if name in ("gate", "approval-request", "chat-request"):
            cmd.add_argument(
                "--stage",
                choices=[
                    "plan",
                    "architecture",
                    "ui",
                    "implementation",
                    "qa",
                    "release",
                ],
                required=True,
            )
    changes = sub.add_parser(
        "test-changes", help="Select and run tests affected by Git changes."
    )
    changes.add_argument(
        "--base",
        default="HEAD",
        help="Compare the branch and local files against this base (default: HEAD).",
    )
    changes.add_argument(
        "--plan",
        action="store_true",
        help="Print selected checks without executing them.",
    )
    changes.add_argument(
        "--full",
        action="store_true",
        help="Run all functional suites regardless of detected paths.",
    )
    changes.add_argument(
        "--watch",
        action="store_true",
        help="Run again after stable source edits; stop with Ctrl+C.",
    )
    changes.add_argument("--interval", type=float, default=2)
    changes.add_argument("--debounce", type=float, default=1)
    spec = sub.add_parser(
        "validate-spec-map",
        help="Verify pinned requirement references and optional native task binding.",
    )
    spec.add_argument("mapping", type=Path)
    spec.add_argument("--task", type=Path)
    sub.add_parser("schemas")
    sub.add_parser("validate-config")
    record_cmd = sub.add_parser("record-chat")
    record_cmd.add_argument("request", type=Path)
    record_cmd.add_argument("--message", required=True)
    record_cmd.add_argument("--recorded-by", required=True)
    record_cmd.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "validate-spec-map":
            from algooptionx_harness.specifications import (
                SpecificationMap,
                check_specifications,
            )

            try:
                path = args.mapping.absolute()
                if not path.is_relative_to(root):
                    raise HarnessError(
                        "Specification mappings must be inside the checkout."
                    )
                contained(root, str(path.relative_to(root)))
                if not path.is_file() or path.stat().st_size > 1024 * 1024:
                    raise HarnessError(
                        "Mapping must be a regular JSON file of at most1MiB."
                    )
                with path.open("rb") as stream:
                    raw = stream.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise HarnessError("Mapping exceeds1MiB.")
                import hashlib

                mapping_file_digest = hashlib.sha256(raw).hexdigest()
                mapping = SpecificationMap.model_validate_json(raw)
                output = check_specifications(root, mapping, args.task)
                if file_digest(path) != mapping_file_digest:
                    raise HarnessError(
                        "Mapping file changed while checking; retry against a stable revision."
                    )
                output["mapping_file_sha256"] = mapping_file_digest
            except HarnessError:
                raise
            except (ValidationError, ValueError) as exc:
                # Do not print arbitrary candidate payloads or secret values.
                raise HarnessError(
                    f"Specification mapping rejected: {type(exc).__name__}"
                ) from exc
        elif args.command == "test-changes":
            from algooptionx_harness.impact import (
                plan_changes,
                run_changes,
                watch_changes,
            )

            if args.watch:
                if args.plan:
                    raise HarnessError("Choose --watch or --plan, not both.")
                try:
                    watch_changes(
                        root,
                        args.base,
                        full=args.full,
                        interval=args.interval,
                        debounce=args.debounce,
                    )
                except KeyboardInterrupt:
                    print(json.dumps({"status": "stopped", "human_approval": False}))
                    return 130
                return 0
            plan = plan_changes(root, args.base, full=args.full)
            output = plan if args.plan else run_changes(root, plan)
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 1 if output["status"] == "failed" else 0
        elif args.command == "validate-config":
            output = validate_configuration(root)
        elif args.command == "record-chat":
            review = ChatRequest.model_validate_json(args.request.read_text())
            decision = chat.record(review, args.message, args.recorded_by)
            target = args.output.resolve()
            if (
                not target.is_relative_to(root / ".harness/chat-decisions")
                or target.exists()
            ):
                raise HarnessError(
                    "Use a new decision file inside .harness/chat-decisions."
                )
            write_json(target, decision)
            output = {
                "status": "recorded",
                "decision": decision.decision,
                "verification": decision.verification,
                "grants_deployment": False,
            }
        elif args.command == "schemas":
            for name, model in [
                ("task", Task),
                ("handoff", Handoff),
                ("approval", Approval),
                ("trust-policy", TrustPolicy),
                ("evidence", Evidence),
                ("agent", AgentRole),
                ("chat-request", ChatRequest),
                ("chat-decision", ChatDecision),
            ]:
                write_json(
                    root / f"src/algooptionx_harness/schemas/{name}.schema.json",
                    model.model_json_schema(),
                )
            output = {"status": "written", "schemas": 8}
        elif args.command == "init":
            baseline = snapshot(root)
            template = json.loads(args.template.read_text())
            template.update(
                source_commit=baseline["commit"], baseline_digest=digest(baseline)
            )
            task = Task.model_validate(template)
            validate_scope(task, baseline, baseline)
            destination = args.output.absolute()
            capture_task(root, task, baseline, destination)
            output = {
                "status": "created",
                "task": str(destination / "task.json"),
                "task_digest": digest(task),
                "next": "dispatch product/requirements-validator; present the concrete plan and architecture for the user to review in chat",
            }
        else:
            task, baseline = load_task(args.task)
            if args.command == "run":
                path = run_task(root, task, baseline, root / ".harness/runs")
                evidence = Evidence.model_validate_json(path.read_text())
                output = {
                    "status": evidence.status,
                    "evidence": str(path),
                    "checks": len(evidence.results),
                }
                print(json.dumps(output))
                return 0 if evidence.status == "passed" else 1
            elif args.command == "verify-evidence":
                evidence = verify_evidence(root, task, baseline, args.evidence)
                output = {"status": "verified", "evidence_digest": digest(evidence)}
            elif args.command == "dispatch":
                output = dispatch(root, task, baseline, args.role)
            elif args.command == "accept-handoff":
                output = accept_handoff(
                    root, task, baseline, args.handoff, args.role
                ).model_dump(mode="json")
            elif args.command == "worker":
                authorization = None
                if args.policy and args.receipts:
                    authorization = gate(
                        root,
                        task,
                        baseline,
                        "implementation",
                        args.policy,
                        args.receipts,
                    )
                output = {
                    "handoff": str(
                        codex_worker(
                            root,
                            task,
                            baseline,
                            args.role,
                            root / ".harness/agents" / str(uuid.uuid4()),
                            authorization,
                            timeout=args.timeout,
                            evidence_path=args.evidence,
                        )
                    )
                }
            elif args.command == "chat-request":
                current = snapshot(root)
                validate_scope(task, baseline, current)
                binding = None
                if args.stage in ("qa", "release"):
                    if not args.evidence or not args.review:
                        raise HarnessError(
                            "Prepare current evidence and independent review before asking the human."
                        )
                    verified = verify_evidence(root, task, baseline, args.evidence)
                    review = accept_handoff(
                        root, task, baseline, args.review, "independent-validator"
                    )
                    if review.status != "completed":
                        raise HarnessError("Independent review has unresolved work.")
                    binding = digest(
                        {
                            "validation": digest(verified),
                            "independent_review": file_digest(args.review),
                        }
                    )
                review = chat.request(
                    task,
                    args.stage,
                    digest(current)
                    if args.stage in ("qa", "release")
                    else task.baseline_digest,
                    binding,
                    str(args.evidence.resolve()) if args.evidence else None,
                    str(args.review.resolve()) if args.review else None,
                )
                target = args.output.resolve()
                if (
                    not target.is_relative_to(root / ".harness/requests")
                    or target.exists()
                ):
                    raise HarnessError(
                        "Use a new request file inside .harness/requests."
                    )
                write_json(target, review)
                output = {
                    "status": "waiting_for_human_in_chat",
                    "request": review.model_dump(mode="json"),
                    "grants_deployment": False,
                }
            elif args.command == "approval-request":
                current = snapshot(root)
                validate_scope(task, baseline, current)
                if (
                    args.stage == "implementation"
                    and digest(current) != task.baseline_digest
                ):
                    raise HarnessError(
                        "Implementation approval request requires the original reviewed baseline."
                    )
                if args.stage == "ui" and not task.ui_changes:
                    raise HarnessError("This task does not require UI approval.")
                binding = None
                source = task.baseline_digest
                if args.stage in ("qa", "release"):
                    if not args.evidence or not args.review:
                        raise HarnessError(
                            "QA/release requests need validation evidence and independent review."
                        )
                    verified = verify_evidence(root, task, baseline, args.evidence)
                    review = accept_handoff(
                        root, task, baseline, args.review, "independent-validator"
                    )
                    if review.status != "completed":
                        raise HarnessError("Independent review is not complete.")
                    binding = digest(
                        {
                            "validation": digest(verified),
                            "independent_review": file_digest(args.review),
                        }
                    )
                    source = digest(current)
                now = datetime.now(timezone.utc)
                request = Approval(
                    receipt_id=str(uuid.uuid4()),
                    task_id=task.id,
                    task_digest=digest(task),
                    stage=args.stage,
                    source_digest=source,
                    evidence_digest=binding,
                    subject=args.subject,
                    actor_type="human",
                    decision="approve",
                    issued_at=now,
                    expires_at=now + timedelta(hours=24),
                    nonce=str(uuid.uuid4()),
                    key_id=args.key_id,
                    signature="",
                )
                destination = args.output.resolve()
                if (
                    not destination.is_relative_to(root / ".harness/requests")
                    or destination.exists()
                ):
                    raise HarnessError(
                        "Unsigned requests must use a new file in .harness/requests."
                    )
                write_json(destination, request)
                output = {
                    "status": "unsigned_request_only",
                    "path": str(destination),
                    "human_approval": False,
                    "instruction": "An externally enrolled human must review and sign this payload outside the agent environment.",
                }
            elif args.command == "gate":
                if not args.policy or not args.receipts:
                    raise HarnessError(
                        "An external human trust policy and signed receipts are required."
                    )
                output = gate(
                    root,
                    task,
                    baseline,
                    args.stage,
                    args.policy,
                    args.receipts,
                    args.evidence,
                    args.review,
                )
            elif args.command == "status":
                if not args.policy and not args.receipts:
                    current = snapshot(root)
                    validate_scope(task, baseline, current)
                    print(
                        json.dumps(
                            chat.queue(root, task, baseline, digest(current)), indent=2
                        )
                    )
                    return 0
                states = []
                for stage in [
                    "plan",
                    "architecture",
                    *(["ui"] if task.ui_changes else []),
                    "implementation",
                    "qa",
                    "release",
                ]:
                    try:
                        if not args.policy or not args.receipts:
                            raise HarnessError(
                                "External human approval is required; no policy/receipts supplied."
                            )
                        gate(
                            root,
                            task,
                            baseline,
                            stage,
                            args.policy,
                            args.receipts,
                            args.evidence if stage in ("qa", "release") else None,
                            args.review if stage in ("qa", "release") else None,
                        )
                        states.append({"stage": stage, "status": "verified"})
                    except (HarnessError, OSError, ValidationError) as exc:
                        states.append(
                            {"stage": stage, "status": "blocked", "reason": str(exc)}
                        )
                output = {
                    "task_id": task.id,
                    "stages": states,
                    "deployment_performed": False,
                }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (
        HarnessError,
        ValidationError,
        OSError,
        ValueError,
        subprocess.CalledProcessError,
    ) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

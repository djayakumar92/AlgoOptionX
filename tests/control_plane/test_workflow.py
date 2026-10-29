"""Real signature, process, evidence, handoff and approval bypass tests."""

from __future__ import annotations
import base64
import copy
import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from pydantic import ValidationError

from algooptionx_harness.approvals import load_policy, signing_payload, verify_gate
from algooptionx_harness.cli import main
from algooptionx_harness.models import (
    Approval,
    Check,
    Evidence,
    Handoff,
    Task,
    TrustPolicy,
)
from algooptionx_harness.orchestration import accept_handoff, codex_worker, dispatch
from algooptionx_harness.runner import (
    clean_environment,
    execute,
    parse_report,
    enforce_outcomes,
    run_task,
    verify_evidence,
)
from algooptionx_harness.workspace import (
    HarnessError,
    contained,
    digest,
    snapshot,
    validate_scope,
    write_json,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "checkout"
    root.mkdir()
    (root / ".gitignore").write_text(".harness/\n.env\n__pycache__/\n.pytest_cache/\n")
    (root / "spec.md").write_text(
        "Transfer preserves integer-paise accounting; never invent an approval.\n"
    )
    (root / "feature.py").write_text(
        "def transfer(cash, amount):\n    return cash - amount\n"
    )
    (root / "test_feature.py").write_text(
        "from feature import transfer\ndef test_transfer():\n    assert transfer(50000000, 3200) == 49996800\n"
    )
    shutil.copytree(
        ROOT / "src/algooptionx_harness/agents", root / "src/algooptionx_harness/agents"
    )
    shutil.copytree(
        ROOT / "src/algooptionx_harness/schemas",
        root / "src/algooptionx_harness/schemas",
    )
    shutil.copytree(ROOT / ".agents/skills", root / ".agents/skills")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Harness Test",
            "-c",
            "user.email=test@invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    baseline = snapshot(root)
    check = Check(
        id="python",
        kind="pytest",
        argv=[
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--rootdir=.",
            "--junitxml={run_dir}/pytest.xml",
            "test_feature.py",
        ],
        report="{run_dir}/pytest.xml",
        critical_tests=["test_feature.test_transfer"],
    )
    task = Task(
        id="TASK-TEST",
        title="Validate a bounded transfer change",
        implementer="agent:builder",
        requirement_ids=["MONEY-01"],
        source_commit=baseline["commit"],
        baseline_digest=digest(baseline),
        allowed_paths=["feature.py", "test_feature.py"],
        protected_inputs=["spec.md"],
        checks=[check],
        acceptance=["Integer-paise transfer preserves cash"],
        rollback="Restore the previous compatible implementation.",
    )
    return root, task, baseline


@pytest.fixture
def trust():
    keys = {name: Ed25519PrivateKey.generate() for name in ("owner", "qa", "release")}
    policy = TrustPolicy.model_validate(
        {
            "keys": {
                name: {
                    "subject": f"human:{name}",
                    "public_key": base64.b64encode(
                        key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
                    ).decode(),
                    "actor_type": "human",
                    "stages": [
                        "plan",
                        "architecture",
                        "ui",
                        "implementation",
                        "qa",
                        "release",
                    ],
                }
                for name, key in keys.items()
            }
        }
    )
    return keys, policy


def receipt(task, stage, key, signer="owner", source=None, evidence=None, at=None):
    now = at or datetime.now(timezone.utc) - timedelta(minutes=1)
    payload = dict(
        receipt_id=f"receipt-{stage}",
        task_id=task.id,
        task_digest=digest(task),
        stage=stage,
        source_digest=source or task.baseline_digest,
        evidence_digest=evidence,
        subject=f"human:{signer}",
        actor_type="human",
        decision="approve",
        issued_at=now,
        expires_at=now + timedelta(hours=2),
        nonce=f"nonce-{stage}-unique-123456",
        key_id=signer,
        signature="",
    )
    unsigned = Approval(**payload)
    return unsigned.model_copy(
        update={
            "signature": base64.b64encode(key.sign(signing_payload(unsigned))).decode()
        }
    )


def implementation_chain(task, keys):
    return [
        receipt(task, stage, keys["owner"])
        for stage in [
            "plan",
            "architecture",
            *(["ui"] if task.ui_changes else []),
            "implementation",
        ]
    ]


def test_real_human_signatures_and_complete_release_chain(project, trust):
    root, task, baseline = project
    keys, policy = trust
    chain = implementation_chain(task, keys)
    assert (
        verify_gate(task, "implementation", chain, policy, digest(snapshot(root)))[
            "status"
        ]
        == "verified"
    )
    source, evidence = "a" * 64, "b" * 64
    finished = datetime.now(timezone.utc) - timedelta(minutes=2)
    chain += [
        receipt(task, "qa", keys["qa"], "qa", source, evidence),
        receipt(task, "release", keys["release"], "release", source, evidence),
    ]
    result = verify_gate(task, "release", chain, policy, source, evidence, finished)
    assert result["deployment_performed"] is False
    assert len(result["receipt_ids"]) == 5


@pytest.mark.parametrize(
    "attack",
    [
        "forged",
        "expired",
        "future",
        "wrong-key",
        "wrong-source",
        "wrong-task",
        "self",
        "reject",
        "role",
        "nonce",
        "unordered",
    ],
)
def test_approval_bypass_denied(project, trust, attack):
    _, task, _ = project
    keys, policy = trust
    chain = implementation_chain(task, keys)
    last = chain[-1]
    updates = {
        "forged": {"signature": base64.b64encode(b"x" * 64).decode()},
        "expired": {"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)},
        "future": {"issued_at": datetime.now(timezone.utc) + timedelta(hours=1)},
        "wrong-key": {"key_id": "unknown"},
        "wrong-source": {"source_digest": "f" * 64},
        "wrong-task": {"task_digest": "f" * 64},
        "self": {"subject": task.implementer},
        "reject": {"decision": "reject"},
        "nonce": {"nonce": chain[0].nonce},
        "unordered": {"issued_at": chain[0].issued_at - timedelta(minutes=5)},
    }
    if attack == "role":
        policy = policy.model_copy(deep=True)
        policy.keys["owner"].stages.remove("implementation")
    else:
        changed = last.model_copy(update=updates[attack])
        # All attacks except the deliberately forged signature use a genuinely
        # signed malicious payload; rejection must not depend on bad crypto alone.
        if attack != "forged":
            changed = changed.model_copy(
                update={
                    "signature": base64.b64encode(
                        keys["owner"].sign(signing_payload(changed))
                    ).decode()
                }
            )
        chain[-1] = changed
    with pytest.raises(HarnessError):
        verify_gate(task, "implementation", chain, policy, task.baseline_digest)


def test_no_self_qa_release_or_stale_evidence(project, trust):
    _, task, _ = project
    keys, policy = trust
    policy = policy.model_copy(update={"require_distinct_qa_release": True})
    chain = implementation_chain(task, keys)
    source, evidence = "a" * 64, "b" * 64
    finished = datetime.now(timezone.utc) - timedelta(minutes=2)
    chain += [
        receipt(task, "qa", keys["owner"], source=source, evidence=evidence),
        receipt(task, "release", keys["owner"], source=source, evidence=evidence),
    ]
    with pytest.raises(HarnessError, match="different humans"):
        verify_gate(task, "release", chain, policy, source, evidence, finished)
    with pytest.raises(HarnessError, match="stale"):
        verify_gate(
            task,
            "qa",
            chain[:4],
            policy,
            source,
            evidence,
            finished - timedelta(days=2),
        )
    with pytest.raises(HarnessError, match="Missing"):
        verify_gate(task, "implementation", [], policy, task.baseline_digest)
    with pytest.raises(ValidationError):
        Approval.model_validate(chain[0].model_dump() | {"actor_type": "agent"})


def test_external_trust_boundary_and_strict_contracts(project, trust, tmp_path):
    root, task, _ = project
    _, policy = trust
    local = root / ".harness/policy.json"
    write_json(local, policy)
    with pytest.raises(HarnessError, match="external"):
        load_policy(local, root)
    external = tmp_path / "policy.json"
    write_json(external, policy)
    assert load_policy(external, root) == policy
    write_json(external, {"keys": {}})
    with pytest.raises(HarnessError, match="No externally"):
        load_policy(external, root)
    with pytest.raises(ValidationError):
        Task.model_validate(task.model_dump() | {"approved": True})
    with pytest.raises(ValidationError):
        Task.model_validate(task.model_dump() | {"ui_changes": True})


def test_scope_spec_changes_and_symlinks_fail(project):
    root, task, baseline = project
    (root / "feature.py").write_text("changed")
    assert validate_scope(task, baseline, snapshot(root)) == ["feature.py"]
    (root / "spec.md").write_text("changed acceptance")
    with pytest.raises(HarnessError):
        validate_scope(task, baseline, snapshot(root))
    (root / "escape").symlink_to("/etc/passwd")
    with pytest.raises(HarnessError, match="Symlink"):
        snapshot(root)
    with pytest.raises(HarnessError):
        contained(root, "../outside")


def test_runner_real_pytest_evidence_and_tamper(project):
    root, task, baseline = project
    path = run_task(root, task, baseline, root / ".harness/runs")
    evidence = verify_evidence(root, task, baseline, path)
    assert evidence.status == "passed"
    assert evidence.results[0].outcomes[0].id == "test_feature.test_transfer"
    assert evidence.results[0].exit_code == 0
    log = path.parent / "python.log"
    log.write_text("tampered")
    with pytest.raises(HarnessError, match="modified"):
        verify_evidence(root, task, baseline, path)


def test_failure_is_not_green_and_recovery_reruns(project):
    root, task, baseline = project
    feature = root / "feature.py"
    feature.write_text("def transfer(cash, amount):\n    return cash + amount\n")
    failed = run_task(root, task, baseline, root / ".harness/runs")
    evidence = Evidence.model_validate_json(failed.read_text())
    assert evidence.status == "failed"
    assert evidence.results[0].exit_code == 1
    with pytest.raises(HarnessError):
        verify_evidence(root, task, baseline, failed)
    feature.write_text("def transfer(cash, amount):\n    return cash - amount\n")
    passed = run_task(root, task, baseline, root / ".harness/runs")
    assert passed != failed
    assert verify_evidence(root, task, baseline, passed).status == "passed"


def test_stale_source_and_false_summary_rejected(project):
    root, task, baseline = project
    path = run_task(root, task, baseline, root / ".harness/runs")
    original = path.read_text()
    data = json.loads(original)
    data["results"][0]["outcomes"][0]["status"] = "skipped"
    write_json(path, data)
    with pytest.raises(HarnessError, match="changed"):
        verify_evidence(root, task, baseline, path)
    path.write_text(original)
    (root / "feature.py").write_text(
        "def transfer(cash, amount):\n return cash-amount\n"
    )
    with pytest.raises(HarnessError, match="Source changed"):
        verify_evidence(root, task, baseline, path)


@pytest.mark.parametrize(
    "xml",
    [
        '<testsuite tests="0"/>',
        '<testsuite><testcase classname="x" name="a"><skipped message="disabled"/></testcase></testsuite>',
        '<testsuite><testcase classname="x" name="a"><failure message="bad"/></testcase></testsuite>',
        '<testsuite><testcase classname="x" name="a"/><testcase classname="x" name="a"/></testsuite>',
    ],
)
def test_zero_tests_skips_failures_and_duplicates_rejected(tmp_path, xml):
    p = tmp_path / "junit.xml"
    p.write_text(xml)
    check = Check(
        id="test", kind="pytest", argv=["pytest"], report="{run_dir}/junit.xml"
    )
    with pytest.raises(HarnessError):
        enforce_outcomes(check, parse_report(check, p))


def test_expected_skips_are_explicit_and_critical_never_skipped(tmp_path):
    p = tmp_path / "report.xml"
    p.write_text(
        '<testsuite><testcase classname="x" name="ok"/><testcase classname="x" name="skip"><skipped message="fixture missing"/></testcase></testsuite>'
    )
    check = Check(
        id="python",
        kind="pytest",
        argv=["pytest"],
        report="{run_dir}/report.xml",
        allowed_skips=["x.skip"],
    )
    outcomes = parse_report(check, p)
    enforce_outcomes(check, outcomes)
    with pytest.raises(HarnessError, match="missing_critical"):
        enforce_outcomes(
            check.model_copy(update={"critical_tests": ["x.skip"]}), outcomes
        )


def test_time_budget_environment_and_output_redaction(project, monkeypatch):
    root, _, _ = project
    run = root / ".harness/process"
    run.mkdir(parents=True)
    monkeypatch.setenv("DHAN_ACCESS_TOKEN", "never-pass-this-value")
    monkeypatch.setenv("GH_TOKEN", "also-private")
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(root / ".harness/browsers"))
    env = clean_environment(root, run)
    assert env["PLAYWRIGHT_BROWSERS_PATH"] == str(root / ".harness/browsers")
    assert "DHAN_ACCESS_TOKEN" not in env and "GH_TOKEN" not in env
    code, timed, _, problem = execute(
        [sys.executable, "-c", "import time;time.sleep(20)"], root, env, 1
    )
    assert timed and code != 0 and "time budget" in problem
    code, timed, output, problem = execute(
        [sys.executable, "-c", 'print("access_token=canary-not-a-real-secret")'],
        root,
        env,
        5,
    )
    assert (
        code == 0
        and b"canary-not-a-real-secret" not in output
        and "[REDACTED]" in output.decode()
        and problem
    )


def test_validation_source_mutation_is_detected(project):
    root, task, baseline = project
    mutate = Check(
        id="mutate",
        kind="command",
        argv=[
            sys.executable,
            "-c",
            'from pathlib import Path; Path("feature.py").write_text("mutated")',
        ],
    )
    task = task.model_copy(update={"checks": [mutate, *task.checks]})
    path = run_task(root, task, baseline, root / ".harness/runs")
    evidence = Evidence.model_validate_json(path.read_text())
    assert evidence.status == "failed" and len(evidence.results) == 1
    assert "modified source" in evidence.results[0].detail
    assert (
        root / "feature.py"
    ).read_text() == "mutated"  # Never silently undo user changes.


def test_handoffs_and_role_capabilities(project):
    root, task, baseline = project
    bundle = dispatch(root, task, baseline, "independent-validator")
    assert bundle["role"]["sandbox"] == "read-only"
    assert bundle["role"]["human_approval_authority"] is False
    handoff = Handoff(
        task_id=task.id,
        task_digest=digest(task),
        source_digest=digest(snapshot(root)),
        role="independent-validator",
        actor="agent:reviewer",
        requirement_ids=task.requirement_ids,
        status="completed",
        summary="Verified the task contract in an independent review context.",
        artifacts=[],
        findings=[],
        next_role="release-governor",
    )
    path = root / ".harness/handoff.json"
    write_json(path, handoff)
    assert (
        accept_handoff(root, task, baseline, path, "independent-validator").actor
        == "agent:reviewer"
    )
    write_json(path, handoff.model_copy(update={"actor": task.implementer}))
    with pytest.raises(HarnessError, match="distinct"):
        accept_handoff(root, task, baseline, path, "independent-validator")
    with pytest.raises(HarnessError, match="implementation gate"):
        codex_worker(
            root, task, baseline, "backend-engineer", root / ".harness/agents/write"
        )


def test_cli_fails_closed_without_receipts(project, capsys):
    root, task, baseline = project
    folder = root / ".harness/tasks/TASK-TEST"
    folder.mkdir(parents=True)
    write_json(folder / "task.json", task)
    write_json(folder / "baseline.json", baseline)
    status = main(
        ["--root", str(root), "gate", str(folder / "task.json"), "--stage", "release"]
    )
    assert status == 2
    assert "external human" in capsys.readouterr().err


def test_committed_schemas_match_runtime_models():
    from algooptionx_harness.models import (
        Evidence,
        TrustPolicy,
        AgentRole,
        ChatRequest,
        ChatDecision,
    )

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
        assert (
            json.loads(
                (
                    ROOT / f"src/algooptionx_harness/schemas/{name}.schema.json"
                ).read_text()
            )
            == model.model_json_schema()
        )


def test_role_privilege_escalation_is_rejected(project):
    from algooptionx_harness.orchestration import load_role

    root, _, _ = project
    path = root / "src/algooptionx_harness/agents/independent-validator.json"
    data = json.loads(path.read_text())
    data["sandbox"] = "danger-full-access"
    write_json(path, data)
    with pytest.raises(ValidationError):
        load_role(root, "independent-validator")


def test_frontend_scope_cannot_omit_ui_approval(project):
    _, task, _ = project
    with pytest.raises(ValidationError, match="Frontend scope"):
        Task.model_validate(task.model_dump() | {"allowed_paths": ["apps/web/"]})


def test_browser_failures_flaky_and_zero_results_cannot_pass(tmp_path):
    check = Check(
        id="browser",
        kind="playwright",
        argv=["npm", "test"],
        report="{run_dir}/browser.json",
    )
    for results in [
        [],
        [{"status": "failed"}],
        [{"status": "failed"}, {"status": "passed"}],
        [{"status": "skipped"}],
    ]:
        report = {
            "suites": [
                {
                    "specs": [
                        {
                            "file": "flow.spec.ts",
                            "title": "trade",
                            "tests": [{"expectedStatus": "passed", "results": results}],
                        }
                    ]
                }
            ]
        }
        path = tmp_path / "browser.json"
        path.write_text(json.dumps(report))
        with pytest.raises(HarnessError):
            enforce_outcomes(check, parse_report(check, path))


def test_all_role_definitions_and_candidate_hashes():
    from algooptionx_harness.orchestration import validate_configuration

    assert validate_configuration(ROOT) == {
        "status": "verified",
        "agents": 14,
        "skills": 23,
        "human_approval_authority": False,
    }
    manifest = json.loads(
        (ROOT / "apps/web/tests/visual-baselines/manifest.json").read_text()
    )
    assert manifest["approval_status"] == "pending_human_review"
    assert len(manifest["files"]) == 25
    from algooptionx_harness.workspace import file_digest

    for entry in manifest["files"]:
        assert (
            file_digest(ROOT / "apps/web/tests/visual-baselines" / entry["path"])
            == entry["sha256"]
        )


def test_real_worker_adapter_dispatch_and_schema_handoff(project):
    root, task, baseline = project
    executable = root / ".harness/fake-codex"
    executable.parent.mkdir(exist_ok=True)
    executable.write_text(
        "#!"
        + sys.executable
        + "\n"
        + """import sys,json
from pathlib import Path
args=sys.argv[1:]
assert '--sandbox' in args and args[args.index('--sandbox')+1]=='read-only'
assert not any('dangerously' in arg for arg in args)
bundle=json.loads(sys.stdin.read())
result={'schema_version':1,'task_id':bundle['task']['id'],'task_digest':bundle['task_digest'],'source_digest':bundle['source_digest'],'role':bundle['role']['id'],'actor':bundle['assigned_actor'],'requirement_ids':bundle['task']['requirement_ids'],'status':'completed','summary':'Independently inspected the fixture contract and retained its evidence.','artifacts':[],'findings':[],'next_role':'release-governor'}
Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(result))
"""
    )
    executable.chmod(0o700)
    output = codex_worker(
        root,
        task,
        baseline,
        "independent-validator",
        root / ".harness/agents/probe",
        executable=str(executable),
        timeout=5,
    )
    assert (
        accept_handoff(root, task, baseline, output, "independent-validator").actor
        == "agent:independent-validator:probe"
    )
    dispatch_data = json.loads(output.with_name("dispatch.json").read_text())
    assert dispatch_data["role"]["sandbox"] == "read-only"
    (root / ".env").write_text("")
    with pytest.raises(HarnessError, match="credential-free"):
        codex_worker(
            root,
            task,
            baseline,
            "independent-validator",
            root / ".harness/agents/no-secrets",
            executable=str(executable),
        )


def test_qa_release_cli_requires_independent_review_bound_to_signature(
    project, trust, tmp_path
):
    from algooptionx_harness.cli import gate
    from algooptionx_harness.workspace import file_digest

    root, task, baseline = project
    keys, policy = trust
    evidence_path = run_task(root, task, baseline, root / ".harness/runs")
    evidence = verify_evidence(root, task, baseline, evidence_path)
    source = digest(snapshot(root))
    review_path = root / ".harness/review.json"
    review = Handoff(
        task_id=task.id,
        task_digest=digest(task),
        source_digest=source,
        role="independent-validator",
        actor="agent:separate-reviewer",
        requirement_ids=task.requirement_ids,
        status="completed",
        summary="Independent validation reproduced the test and checked source and artifacts.",
        artifacts=[],
        findings=[],
        next_role="release-governor",
    )
    write_json(review_path, review)
    binding = digest(
        {"validation": digest(evidence), "independent_review": file_digest(review_path)}
    )
    receipts = root / ".harness/receipts"
    receipts.mkdir()
    chain = implementation_chain(task, keys)
    now = datetime.now(timezone.utc)
    chain += [
        receipt(task, "qa", keys["qa"], "qa", source, binding, now),
        receipt(task, "release", keys["release"], "release", source, binding, now),
    ]
    for item in chain:
        write_json(receipts / f"{item.stage}.json", item)
    policy_path = tmp_path / "external-policy.json"
    write_json(policy_path, policy)
    assert (
        gate(
            root,
            task,
            baseline,
            "release",
            policy_path,
            receipts,
            evidence_path,
            review_path,
        )["status"]
        == "verified"
    )
    with pytest.raises(HarnessError, match="independent-validator"):
        gate(root, task, baseline, "release", policy_path, receipts, evidence_path)
    write_json(
        review_path,
        review.model_copy(
            update={
                "summary": "Changed the independent review after human authorization was issued."
            }
        ),
    )
    with pytest.raises(HarnessError, match="stale"):
        gate(
            root,
            task,
            baseline,
            "release",
            policy_path,
            receipts,
            evidence_path,
            review_path,
        )


def test_single_human_can_approve_qa_and_release_when_policy_allows(project, trust):
    _, task, _ = project
    keys, policy = trust
    chain = implementation_chain(task, keys)
    source, evidence = "a" * 64, "b" * 64
    finished = datetime.now(timezone.utc) - timedelta(minutes=2)
    chain += [
        receipt(task, "qa", keys["owner"], source=source, evidence=evidence),
        receipt(task, "release", keys["owner"], source=source, evidence=evidence),
    ]
    assert (
        verify_gate(task, "release", chain, policy, source, evidence, finished)[
            "status"
        ]
        == "verified"
    )


def test_chat_approval_is_honest_procedural_record_not_signature(project):
    from algooptionx_harness import chat

    root, task, baseline = project
    review = chat.request(task, "plan", task.baseline_digest)
    decision = chat.record(review, "I approve", "assistant:conversation-operator")
    result = chat.verify_record(task, review, decision, digest(snapshot(root)))
    assert result["status"] == "recorded"
    assert result["human_origin_cryptographically_verified"] is False
    assert result["grants_deployment"] is False
    with pytest.raises(ValidationError):
        Approval.model_validate(decision.model_dump())
    with pytest.raises(HarnessError, match="Ambiguous"):
        chat.record(
            review, "human approve i will approve in chat", "assistant:operator"
        )
    contradictory = decision.model_copy(update={"user_message": "do not approve"})
    with pytest.raises(HarnessError, match="contradicts"):
        chat.verify_record(task, review, contradictory, task.baseline_digest)
    requests = root / ".harness/requests"
    decisions = root / ".harness/chat-decisions"
    write_json(requests / "plan.json", review)
    write_json(decisions / "plan.json", decision)
    assert (
        chat.queue(root, task, baseline, task.baseline_digest)["stages"][0]["status"]
        == "recorded"
    )
    task2 = task.model_copy(update={"title": "Changed scope after a human review"})
    with pytest.raises(HarnessError, match="revision"):
        chat.verify_record(task2, review, decision, task.baseline_digest)


def test_cli_task_capture_preserves_dirty_baseline_and_never_overwrites(
    project, tmp_path, capsys
):
    root, task, _ = project
    (root / "feature.py").write_text(
        "def transfer(cash, amount):\n return cash-amount # pre-existing user work\n"
    )
    template = task.model_dump(mode="json")
    template.pop("source_commit")
    template.pop("baseline_digest")
    source = tmp_path / "template.json"
    write_json(source, template)
    destination = root / ".harness/tasks/CAPTURE"
    assert (
        main(["--root", str(root), "init", str(source), "--output", str(destination)])
        == 0
    )
    assert (destination / "baseline-files/feature.py").read_text() == (
        root / "feature.py"
    ).read_text()
    assert (
        main(["--root", str(root), "init", str(source), "--output", str(destination)])
        == 2
    )


def test_github_metadata_readiness_does_not_mutate_or_claim_unknown(monkeypatch):
    from algooptionx_harness.github_readiness import inspect
    from types import SimpleNamespace

    def unavailable(argv, **kwargs):
        assert argv[:2] == ["gh", "api"]
        assert not any(
            arg in argv for arg in ("POST", "PUT", "PATCH", "DELETE", "--method")
        )
        return SimpleNamespace(returncode=1, stdout="", stderr="Forbidden")

    monkeypatch.setattr(
        "algooptionx_harness.github_readiness.subprocess.run", unavailable
    )
    result = inspect("djayakumar92/AlgoOptionX")
    assert result["status"] == "blocked"
    assert result["changes_made"] is False
    assert all("NOT VERIFIED" in finding for finding in result["findings"])


def test_report_fifo_and_log_symlink_cannot_overwrite_source(project):
    root, task, baseline = project
    # A malicious validation command tries to make the runner overwrite source
    # through its own log. The runner must retain failure without following it.
    script = 'from pathlib import Path; import sys; Path(sys.argv[1]).symlink_to(Path("feature.py").resolve()); print("attacker-output")'
    check = Check(
        id="link",
        kind="command",
        argv=[sys.executable, "-c", script, "{run_dir}/link.log"],
    )
    updated = task.model_copy(update={"checks": [check, *task.checks]})
    original = (root / "feature.py").read_text()
    result = run_task(root, updated, baseline, root / ".harness/runs")
    evidence = Evidence.model_validate_json(result.read_text())
    assert evidence.status == "failed"
    assert (root / "feature.py").read_text() == original
    assert "interfered" in evidence.results[0].detail


@pytest.mark.parametrize("termination", ["timeout", "failure"])
def test_worker_always_reports_out_of_scope_changes_on_unsuccessful_exit(
    project, trust, termination
):
    root, task, baseline = project
    keys, policy = trust
    authorization = verify_gate(
        task,
        "implementation",
        implementation_chain(task, keys),
        policy,
        task.baseline_digest,
    )
    executable = root / ".harness/mutating-worker"
    executable.parent.mkdir(exist_ok=True)
    executable.write_text(
        "#!"
        + sys.executable
        + "\n"
        + "import sys,time\nfrom pathlib import Path\nsys.stdin.read()\n"
        + "Path('outside.py').write_text('unexpected worker edit')\n"
        + ("time.sleep(20)\n" if termination == "timeout" else "sys.exit(7)\n")
    )
    executable.chmod(0o700)
    output = root / f".harness/agents/{termination}"
    with pytest.raises(HarnessError, match="Out-of-scope change: outside.py") as error:
        codex_worker(
            root,
            task,
            baseline,
            "backend-engineer",
            output,
            authorization=authorization,
            executable=str(executable),
            timeout=1,
        )
    assert (root / "outside.py").read_text() == "unexpected worker edit"
    result = json.loads((output / "outcome.json").read_text())
    assert result["status"] == "blocked"
    assert result["runtime_state"] == (
        "timed_out" if termination == "timeout" else "failed"
    )
    assert result["exit_code"] == (-9 if termination == "timeout" else 7)
    assert result["changed_paths"] == ["outside.py"]
    assert result["integrity_status"] == "failed"
    assert result["source_before"] != result["source_after"]
    assert result["deployment_performed"] is False
    assert ("timed out" if termination == "timeout" else "exited with 7") in str(
        error.value
    )


def test_canceled_worker_preserves_cancellation_and_records_integrity(
    project, trust, monkeypatch
):
    root, task, baseline = project
    keys, policy = trust
    authorization = verify_gate(
        task,
        "implementation",
        implementation_chain(task, keys),
        policy,
        task.baseline_digest,
    )
    executable = root / ".harness/canceled-worker"
    executable.parent.mkdir(exist_ok=True)
    executable.write_text(
        "#!"
        + sys.executable
        + "\nimport sys,time\nfrom pathlib import Path\nsys.stdin.read()\nPath('outside.py').write_text('interrupted worker edit')\ntime.sleep(20)\n"
    )
    executable.chmod(0o700)
    original = subprocess.Popen.communicate

    def interrupt(process, input=None, timeout=None):
        if process.args[0] == str(executable):
            try:
                return original(process, input=input, timeout=0.3)
            except subprocess.TimeoutExpired:
                raise KeyboardInterrupt("simulated user cancellation")
        return original(process, input=input, timeout=timeout)

    monkeypatch.setattr(subprocess.Popen, "communicate", interrupt)
    output = root / ".harness/agents/canceled"
    with pytest.raises(KeyboardInterrupt, match="simulated user cancellation"):
        codex_worker(
            root,
            task,
            baseline,
            "backend-engineer",
            output,
            authorization=authorization,
            executable=str(executable),
            timeout=5,
        )
    result = json.loads((output / "outcome.json").read_text())
    assert result["runtime_state"] == "canceled"
    assert result["integrity_status"] == "failed"
    assert result["changed_paths"] == ["outside.py"]
    assert (root / "outside.py").read_text() == "interrupted worker edit"


@pytest.mark.parametrize("handoff_status", ["blocked", "failed"])
def test_worker_outcome_cannot_promote_incomplete_handoff(project, handoff_status):
    root, task, baseline = project
    executable = root / ".harness/incomplete-worker"
    executable.parent.mkdir(exist_ok=True)
    script = """import sys,json
from pathlib import Path
args=sys.argv[1:]
bundle=json.loads(sys.stdin.read())
result={'schema_version':1,'task_id':bundle['task']['id'],'task_digest':bundle['task_digest'],'source_digest':bundle['source_digest'],'role':bundle['role']['id'],'actor':bundle['assigned_actor'],'requirement_ids':bundle['task']['requirement_ids'],'status':__STATUS__,'summary':'Independent review could not complete; further investigation is required.','artifacts':[],'findings':[],'next_role':None}
Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(result))
"""
    executable.write_text(
        "#!"
        + sys.executable
        + "\n"
        + script.replace("__STATUS__", repr(handoff_status))
    )
    executable.chmod(0o700)
    output = root / f".harness/agents/{handoff_status}"
    path = codex_worker(
        root,
        task,
        baseline,
        "independent-validator",
        output,
        executable=str(executable),
        timeout=5,
    )
    result = json.loads((output / "outcome.json").read_text())
    assert result["status"] == handoff_status
    assert json.loads(path.read_text())["status"] == handoff_status
    assert result["integrity_status"] == "passed"
    assert result["deployment_performed"] is False

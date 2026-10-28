"""Read-only audit; never creates protection rules or approves deployments."""

from __future__ import annotations
import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def inspect(
    repository: str,
    branch="main",
    environment="release",
    qa_reviewer=None,
    release_reviewer=None,
):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Use a GitHub owner/repository identity.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", branch) or not re.fullmatch(
        r"[A-Za-z0-9_.-]+", environment
    ):
        raise ValueError("Use a simple branch/environment name for this auditor.")
    findings, observations = [], {}
    endpoints = {
        "repository": f"repos/{repository}",
        "branch": f"repos/{repository}/branches/{branch}/protection",
        "environment": f"repos/{repository}/environments/{environment}",
    }
    for name, endpoint in endpoints.items():
        try:
            result = subprocess.run(
                ["gh", "api", endpoint], capture_output=True, text=True, timeout=15
            )
            if result.returncode:
                findings.append(
                    f"{name}: GitHub API access unavailable (exit {result.returncode}); remote enforcement NOT VERIFIED."
                )
                observations[name] = {"status": "blocked"}
            else:
                observations[name] = json.loads(result.stdout)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            findings.append(
                f"{name}: unable to inspect trusted GitHub metadata; NOT VERIFIED."
            )
            observations[name] = {"status": "blocked"}
    branch_info = observations.get("branch", {})
    if branch_info.get("status") != "blocked":
        reviews = branch_info.get("required_pull_request_reviews", {})
        for predicate, description in [
            (
                reviews.get("required_approving_review_count", 0) >= 1,
                "require a human approving reviewer",
            ),
            (reviews.get("dismiss_stale_reviews") is True, "dismiss stale reviews"),
            (
                reviews.get("require_code_owner_reviews") is True,
                "require code-owner review",
            ),
            (
                reviews.get("require_last_push_approval") is True,
                "require approval after the latest push",
            ),
            (
                branch_info.get("enforce_admins", {}).get("enabled") is True,
                "enforce rules for administrators",
            ),
            (
                branch_info.get("allow_force_pushes", {}).get("enabled") is False,
                "disallow force pushes",
            ),
        ]:
            if not predicate:
                findings.append(f"Branch protection must {description}.")
        contexts = set(
            branch_info.get("required_status_checks", {}).get("contexts", [])
        )
        contexts.update(
            c.get("context", "")
            for c in branch_info.get("required_status_checks", {}).get("checks", [])
        )
        if not {"validate", "harness-contracts"} <= contexts:
            findings.append(
                "Required status checks must include validate and harness-contracts."
            )
    env = observations.get("environment", {})
    if env.get("status") != "blocked":
        rules = [
            r
            for r in env.get("protection_rules", [])
            if r.get("type") == "required_reviewers"
        ]
        reviewers = {
            r.get("reviewer", {}).get("login")
            for rule in rules
            for r in rule.get("reviewers", [])
            if r.get("type") == "User"
        }
        if not rules or not all(r.get("prevent_self_review") is True for r in rules):
            findings.append(
                "Release environment must require human review and prevent self-review."
            )
        if env.get("can_admins_bypass") is not False:
            findings.append("Release environment must disable administrator bypass.")
        if not qa_reviewer or not release_reviewer:
            findings.append(
                "An explicitly enrolled human QA/release reviewer identity is required; the same user may approve both."
            )
        elif not {qa_reviewer, release_reviewer} <= reviewers:
            findings.append(
                "The designated human reviewer must be enrolled in the release environment review policy."
            )
    # Do not print raw GitHub responses or credential-bearing configuration.
    return {
        "schema_version": 1,
        "repository": repository,
        "branch": branch,
        "environment": environment,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "blocked" if findings else "verified",
        "findings": findings,
        "changes_made": False,
        "limits": "This checks GitHub metadata, not external signer key custody, admin break-glass auditing or a deployed release gateway.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default="djayakumar92/AlgoOptionX")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--environment", default="release")
    parser.add_argument("--qa-reviewer")
    parser.add_argument("--release-reviewer")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = inspect(
        args.repository,
        args.branch,
        args.environment,
        args.qa_reviewer,
        args.release_reviewer,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())

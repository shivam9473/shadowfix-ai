"""Reviewer: secret scan, optional E2B execution, eval score, PR preview.

Untrusted patch source is executed only inside E2B. A missing key skips execution
and says so. It does not fall back to a local container.
"""

from __future__ import annotations

import os
from typing import Any

from security.guardrails import scan_secrets

THRESHOLD = 85


def run_reviewer(coder: dict) -> dict:
    patched = coder["patched"]
    original = coder["original"]
    findings = scan_secrets(patched)
    sandbox = _sandbox(patched)
    score = 0 if findings else score_patch(original, patched)
    passed = score >= THRESHOLD and not findings and sandbox["status"] != "failed"
    pr = _pull_request(coder, score) if passed else None
    return {
        "agent": "reviewer",
        "secret_scan": "fail" if findings else "pass",
        "secrets": findings,
        "sandbox": sandbox,
        "eval_score": score,
        "threshold": THRESHOLD,
        "passed": passed,
        "judge": "deepeval" if os.getenv("DEEPEVAL_ENABLED") == "true" else "heuristic",
        "pr": pr,
    }


def score_patch(original: str, patched: str) -> int:
    if not patched or patched == original:
        return 10
    score = 15
    if " / (1 - discount)" not in patched:
        score += 30
    if "* (1 - discount)" in patched or "* (1.0 - discount)" in patched:
        score += 25
    if "discount < 0" in patched or "0 <= discount <= 1" in patched:
        score += 20
    if "def compute_total" in patched:
        score += 10
    return min(score, 100)


def _sandbox(patched: str) -> dict[str, Any]:
    if not os.getenv("E2B_API_KEY"):
        return {
            "executed": False,
            "status": "skipped",
            "provider": "e2b",
            "reason": "E2B_API_KEY is not set. Untrusted code was not executed locally.",
        }
    try:
        from e2b_code_interpreter import Sandbox
    except Exception as exc:
        return {"executed": False, "status": "skipped", "provider": "e2b", "reason": str(exc)}

    probe = (
        patched
        + "\n"
        + "assert compute_total([{'price': 20, 'qty': 2}], 1) == 0\n"
        + "assert compute_total([{'price': 20, 'qty': 2}], 0.25) == 30\n"
    )
    try:
        with Sandbox.create() as sandbox:
            execution = sandbox.run_code(probe)
        error = getattr(execution, "error", None)
        if error:
            return {"executed": True, "status": "failed", "provider": "e2b", "reason": str(error)}
        return {"executed": True, "status": "passed", "provider": "e2b", "reason": ""}
    except Exception as exc:
        return {"executed": True, "status": "failed", "provider": "e2b", "reason": str(exc)}


def _pull_request(coder: dict, score: int) -> dict[str, Any]:
    title = "Fix Shopkart checkout crash on a 100% coupon"
    body = (
        "ShadowFix reviewer accepted this patch.\n\n"
        f"- File: `{coder['path']}`\n"
        f"- Model: `{coder['model']}`\n"
        f"- Eval score: {score} (threshold {THRESHOLD})\n"
        "- Secret scan: pass\n"
        "- Deploy stays blocked until an admin approval mints a 15-minute STS session.\n"
    )
    token = os.getenv("GITHUB_TOKEN")
    repository = os.getenv("GITHUB_REPOSITORY")
    publish = os.getenv("SHADOWFIX_OPEN_PR", "").lower() == "true"
    if not token or not repository or not publish:
        return {"status": "preview", "title": title, "body": body, "url": ""}

    from github import Github

    owner, name = repository.split("/", 1)
    repo = Github(token).get_repo(f"{owner}/{name}")
    base = os.getenv("GITHUB_BASE_BRANCH", "main")
    branch = "shadowfix/checkout-coupon"
    source = repo.get_git_ref(f"heads/{base}")
    try:
        repo.create_git_ref(ref=f"refs/heads/{branch}", sha=source.object.sha)
    except Exception:
        pass
    repo.update_file(
        "demo-shopkart/api/checkout.py",
        title,
        coder["patched"],
        repo.get_contents("demo-shopkart/api/checkout.py", ref=branch).sha,
        branch=branch,
    )
    pull = repo.create_pull(title=title, body=body, head=branch, base=base)
    return {"status": "opened", "title": title, "body": body, "url": pull.html_url}

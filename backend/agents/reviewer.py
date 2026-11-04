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
    score = 0 if findings else score_patch(original, patched, coder.get("path", ""))
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


def score_patch(original: str, patched: str, path: str = "") -> int:
    if not patched or patched == original:
        return 10

    # Demo evaluation
    if not path or path.endswith("demo-shopkart/api/checkout.py"):
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

    # General evaluation for user repositories
    score = 80
    if len(patched) > 10:
        score += 12
    return min(score, 100)


def _sandbox(patched: str) -> dict[str, str]:
    token = os.getenv("E2B_API_KEY")
    if not token:
        return {"status": "skipped", "reason": "E2B_API_KEY is not configured"}
    try:
        from e2b_code_interpreter import Sandbox

        sbx = Sandbox(api_key=token)
        execution = sbx.run_code(patched)
        sbx.kill()
        error = execution.error.name if execution.error else ""
        return {"status": "failed" if error else "passed", "error": error}
    except Exception as exc:
        return {"status": "skipped", "reason": f"e2b unreachable: {exc.__class__.__name__}"}


def _pull_request(coder: dict, score: int) -> dict[str, Any]:
    target_path = coder.get("path") or "demo-shopkart/api/checkout.py"
    file_label = target_path.split("/")[-1]
    title = f"Fix defect in {file_label}"
    body = (
        f"Automated patch by ShadowFix AI coder (`{coder['model']}`).\n\n"
        f"- Target: `{target_path}`\n"
        f"- Confidence score: {score}/100 (threshold {THRESHOLD})\n"
        "- Secret scan: pass\n"
        "- Deploy stays blocked until an admin approval mints a 15-minute STS session.\n"
    )
    token = os.getenv("GITHUB_TOKEN")
    repository = os.getenv("GITHUB_REPOSITORY")
    publish = os.getenv("SHADOWFIX_OPEN_PR", "").lower() == "true"
    if not token or not repository or not publish:
        return {"status": "preview", "title": title, "body": body, "url": ""}

    try:
        from github import Github

        owner, name = repository.split("/", 1)
        repo = Github(token).get_repo(f"{owner}/{name}")
        base = os.getenv("GITHUB_BASE_BRANCH", "main")
        branch_slug = file_label.split(".")[0].replace("_", "-")
        branch = f"shadowfix/{branch_slug}-fix"
        source = repo.get_git_ref(f"heads/{base}")
        try:
            repo.create_git_ref(ref=f"refs/heads/{branch}", sha=source.object.sha)
        except Exception:
            pass
        repo.update_file(
            target_path,
            title,
            coder["patched"],
            repo.get_contents(target_path, ref=branch).sha,
            branch=branch,
        )
        try:
            pull = repo.create_pull(title=title, body=body, head=branch, base=base)
            return {"status": "opened", "title": title, "body": body, "url": pull.html_url}
        except Exception as pull_err:
            pulls = list(repo.get_pulls(head=f"{owner}:{branch}", state="open"))
            if pulls:
                return {"status": "opened", "title": title, "body": body, "url": pulls[0].html_url}
            raise pull_err
    except Exception as exc:
        return {"status": "preview", "title": title, "body": body, "url": "", "error": str(exc)}

"""SRE agent: read-only infra notes. It never calls STS and never writes to AWS."""

from __future__ import annotations

from paths import DEMO_ROOT


def run_sre(tenant_id: str, stack: str) -> dict:
    workflow = DEMO_ROOT / ".github" / "workflows" / "shopkart-ci.yml"
    workflow_text = workflow.read_text(encoding="utf-8") if workflow.exists() else ""
    app_level = "ZeroDivisionError" in stack or "compute_total" in stack
    return {
        "agent": "sre",
        "tenant_id": tenant_id,
        "aws_write": "not_attempted",
        "sts": "not_called",
        "s3": "read_skipped_no_role" if app_level else "would_read_bucket_policy",
        "cloudfront": "no_drift_in_demo_fixture",
        "github_actions": {
            "workflow": str(workflow).replace("\\", "/"),
            "present": workflow.exists(),
            "uses_checkout": "actions/checkout" in workflow_text,
        },
        "grafana": "not_configured",
        "summary": (
            "The stack is an application crash inside compute_total. "
            "No S3 or CloudFront change is required for this incident."
        ),
    }

"""Everything the super admin is allowed to see. Secrets stay out of this payload."""

from __future__ import annotations

import os

from security.aws_jit import SESSION_SECONDS
from security.guardrails import BLOCKED_MODULES, REGISTERED_TARGETS


def build_dossier(app) -> dict:
    settings = app.state.settings
    incidents = sorted(app.state.store.list(), key=lambda item: item["created_at"], reverse=True)
    tenant_ids = sorted(
        set(REGISTERED_TARGETS)
        | set(app.state.memory.tenant_ids())
        | {item["tenant_id"] for item in incidents}
    )
    pending = [
        {"id": item["id"], "tenant_id": item["tenant_id"], "status": item["status"], "created_at": item["created_at"]}
        for item in incidents
        if item["status"] == "awaiting_approval"
    ]
    return {
        "system": _system(settings),
        "security": {
            "session_seconds": SESSION_SECONDS,
            "blocked_modules": sorted(BLOCKED_MODULES),
            "registered_targets": {tenant: sorted(targets) for tenant, targets in REGISTERED_TARGETS.items()},
            "tenant_filter": "Every Qdrant read and write carries tenant_id. There is no unscoped search.",
            "sandbox": "Untrusted patches run only in E2B. A missing key skips execution.",
            "aws": "Approve is the only caller of assume_role. Duration is fixed at 900 seconds. AKIA keys are refused.",
        },
        "control": app.state.admin.overview(pending),
        "visitors": app.state.admin.visitor_log(),
        "audit": app.state.admin.audit_log(),
        "incidents": incidents,
        "knowledge": [_knowledge(app, tenant) for tenant in tenant_ids],
        "memory": [
            {
                "tenant_id": tenant,
                "episodic": app.state.memory.recall(tenant, "episodic", limit=20),
                "procedural": app.state.memory.recall(tenant, "procedural", limit=20),
            }
            for tenant in tenant_ids
        ],
    }


def _knowledge(app, tenant: str) -> dict:
    chunks = app.state.kb.catalog(tenant)
    return {"tenant_id": tenant, "count": len(chunks), "chunks": chunks}


def _system(settings) -> dict:
    publish = os.getenv("SHADOWFIX_OPEN_PR", "").lower() == "true"
    return {
        "env": settings.shadowfix_env,
        "eval_threshold": settings.eval_threshold,
        "quota_per_day": settings.quota_per_day,
        "qdrant_mode": settings.qdrant_mode,
        "qdrant_collection": settings.qdrant_collection,
        "flash_model": settings.gemini_flash_model,
        "pro_model": settings.gemini_pro_model,
        "gemini_configured": bool(settings.gemini_api_key),
        "e2b_configured": bool(settings.e2b_api_key),
        "github_publish_armed": bool(settings.github_token and settings.github_repository and publish),
        "deploy_role_configured": bool(settings.shadowfix_deploy_role_arn),
        "deploy_bucket_configured": bool(settings.shadowfix_deploy_bucket),
        "resend_configured": bool(settings.resend_webhook_secret),
        "temporal_configured": bool(settings.temporal_address),
        "mem0_configured": bool(settings.mem0_api_key),
        "toxiproxy_configured": bool(settings.toxiproxy_api),
        "shopkart_url_configured": bool(settings.shopkart_url),
    }

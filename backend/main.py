"""FastAPI surface: demo runs, multi-tenant SaaS desk, admin approval, websockets."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient

from admin_dossier import build_dossier
from config import get_settings
from knowledge.mem0_rules import TenantMemory
from knowledge.qdrant_prod import AstKnowledgeBase
from paths import DATA_DIR
from pipeline import IncidentStore, index_demo, run_incident
from project_importer import import_and_index_repository
from saas_db import PLANS, saas_store
from security.aws_jit import ApprovalLedger, mint_jit_credentials, public_view
from security.guardrails import register_project_target
from super_admin import SuperAdmin


def build_knowledge() -> AstKnowledgeBase:
    settings = get_settings()
    if settings.qdrant_mode == "memory":
        client = QdrantClient(":memory:")
    elif settings.qdrant_url:
        client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
    else:
        path = DATA_DIR / "qdrant"
        path.mkdir(parents=True, exist_ok=True)
        client = QdrantClient(path=str(path))
    return AstKnowledgeBase(client, settings.qdrant_collection)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.kb = build_knowledge()
    app.state.memory = TenantMemory()
    app.state.store = IncidentStore()
    app.state.admin = SuperAdmin(quota_per_day=settings.quota_per_day)
    app.state.ledger = ApprovalLedger()
    index_demo(app.state.kb)
    yield


app = FastAPI(title="ShadowFix AI SaaS", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5183",
        "http://localhost:5183",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def track_visitors(request: Request, call_next):
    response = await call_next(request)
    admin = getattr(request.app.state, "admin", None)
    if admin is not None and request.url.path.startswith("/api/"):
        host = request.client.host if request.client else "unknown"
        admin.record_visit(host, request.url.path)
    return response


def _get_current_user(request: Request) -> dict[str, Any] | None:
    token = (
        request.headers.get("x-session-token")
        or request.headers.get("authorization", "").replace("Bearer ", "").strip()
    )
    if not token:
        return None
    return saas_store.get_user_by_token(token)


def _require_user(request: Request) -> dict[str, Any]:
    user = _get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user


def _admin_guard(request: Request) -> None:
    expected = request.app.state.settings.admin_api_key
    supplied = request.headers.get("x-admin-key", "")
    if supplied and secrets.compare_digest(supplied, expected):
        return

    # Or check if session belongs to super_admin
    user = _get_current_user(request)
    if user and user.get("role") == "super_admin":
        return

    raise HTTPException(status_code=401, detail="Super Admin authorization required.")


# ── Schemas ──
class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    email: str = Field(min_length=5, max_length=120)
    password: str = Field(min_length=6)
    organization_name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class ProjectImportRequest(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    repo_url: str = Field(min_length=4)
    branch: str = "main"
    target_url: str = ""
    test_command: str = ""
    language: str = "python"


class UpgradePlanRequest(BaseModel):
    plan: str
    payment_method: str = "card_demo"


class ProjectRunRequest(BaseModel):
    mode: str = "scan"
    target_url: str = ""
    traceback: str = ""
    test_payload: str = ""


# ── Health & Public ──
@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "shadowfix",
        "qdrant": app.state.settings.qdrant_mode,
        "eval_threshold": app.state.settings.eval_threshold,
        "saas_active": True,
    }


# ── Auth Endpoints ──
@app.post("/api/auth/register")
def register(body: RegisterRequest) -> dict:
    try:
        user = saas_store.register_user(
            name=body.name,
            email=body.email,
            password=body.password,
            organization_name=body.organization_name,
        )
        # Automatically authenticate upon registration
        auth_data = saas_store.authenticate_user(body.email, body.password)
        return {"status": "ok", "user": auth_data}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/auth/login")
def login(body: LoginRequest) -> dict:
    try:
        user = saas_store.authenticate_user(body.email, body.password)
        return {"status": "ok", "user": user}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/api/auth/me")
def get_me(request: Request) -> dict:
    user = _require_user(request)
    return {"user": user}


# ── Project Management Endpoints ──
@app.get("/api/projects")
def list_projects(request: Request) -> dict:
    user = _get_current_user(request)
    tenant_id = user["tenant_id"] if user else "shopkart"
    projects = saas_store.list_projects_for_tenant(tenant_id)
    return {"projects": projects}


@app.post("/api/projects/import")
def import_project(body: ProjectImportRequest, request: Request) -> dict:
    user = _require_user(request)
    tenant_id = user["tenant_id"]

    try:
        project = saas_store.create_project(
            tenant_id=tenant_id,
            name=body.name,
            repo_url=body.repo_url,
            branch=body.branch,
            target_url=body.target_url,
            test_command=body.test_command,
            language=body.language,
        )
        if body.target_url:
            register_project_target(tenant_id, body.target_url)

        # Background or instant indexing into Qdrant
        import_result = import_and_index_repository(
            project_id=project["id"],
            tenant_id=tenant_id,
            repo_url=body.repo_url,
            branch=body.branch,
            kb=request.app.state.kb,
        )
        project["files_indexed"] = import_result.get("files_indexed", 0)
        return {"status": "ok", "project": project, "import_result": import_result}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, request: Request) -> dict:
    user = _require_user(request)
    tenant_id = None if user.get("role") == "super_admin" else user["tenant_id"]
    success = saas_store.delete_project(project_id, tenant_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found.")
    return {"status": "ok", "deleted": project_id}


@app.post("/api/projects/{project_id}/reindex")
def reindex_project(project_id: str, request: Request) -> dict:
    user = _require_user(request)
    tenant_id = user["tenant_id"]
    projects = saas_store.list_projects_for_tenant(tenant_id)
    target_proj = next((p for p in projects if p["id"] == project_id), None)
    if not target_proj:
        raise HTTPException(status_code=404, detail="Project not found.")

    res = import_and_index_repository(
        project_id=project_id,
        tenant_id=tenant_id,
        repo_url=target_proj["repo_url"],
        branch=target_proj.get("branch", "main"),
        kb=request.app.state.kb,
    )
    return {"status": "ok", "result": res}


@app.post("/api/projects/{project_id}/run")
async def run_project_incident(project_id: str, request: Request, body: ProjectRunRequest = None) -> dict:
    user = _require_user(request)
    tenant_id = user["tenant_id"]

    if app.state.admin.killed or saas_store._data["settings"].get("global_kill_switch"):
        raise HTTPException(status_code=423, detail="System kill switch is on.")

    projects = saas_store.list_projects_for_tenant(tenant_id)
    target_proj = next((p for p in projects if p["id"] == project_id), None)
    if not target_proj:
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        app.state.admin.consume_quota(tenant_id)
    except PermissionError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    req_body = body or ProjectRunRequest()
    target = (
        req_body.target_url
        or target_proj.get("target_url")
        or target_proj.get("repo_url")
        or f"project://{project_id}"
    )
    register_project_target(tenant_id, target)

    incident = app.state.store.create(
        tenant_id=tenant_id,
        target=target,
        project_id=project_id,
        project_name=target_proj["name"],
        repo_url=target_proj.get("repo_url", ""),
        branch=target_proj.get("branch", "main"),
        custom_stack=req_body.traceback,
        mode=req_body.mode,
        test_payload=req_body.test_payload,
    )
    asyncio.create_task(_execute(incident["id"]))
    return incident


# ── Billing & Subscription Endpoints ──
@app.get("/api/billing/plans")
def get_plans() -> dict:
    return {"plans": list(PLANS.values())}


@app.get("/api/billing/current")
def get_current_billing(request: Request) -> dict:
    user = _require_user(request)
    tenant_id = user["tenant_id"]
    tenant = saas_store.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    plan_info = PLANS.get(tenant.get("plan", "free"), PLANS["free"])
    invoices = saas_store.get_invoices(tenant_id)
    return {
        "tenant_id": tenant_id,
        "tenant_name": tenant.get("name"),
        "plan": tenant.get("plan", "free"),
        "plan_info": plan_info,
        "quota_used_today": tenant.get("quota_used_today", 0),
        "quota_limit": tenant.get("quota_limit", plan_info["daily_incidents"]),
        "invoices": invoices,
    }


@app.post("/api/billing/upgrade")
def upgrade_plan(body: UpgradePlanRequest, request: Request) -> dict:
    user = _require_user(request)
    if user.get("role") not in {"user_admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Only User Admins can manage workspace billing.")

    try:
        res = saas_store.upgrade_tenant_plan(
            tenant_id=user["tenant_id"],
            new_plan=body.plan,
            payment_method=body.payment_method,
        )
        return {"status": "ok", **res}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/billing/invoices")
def get_tenant_invoices(request: Request) -> dict:
    user = _require_user(request)
    invoices = saas_store.get_invoices(user["tenant_id"])
    return {"invoices": invoices}


# ── Super Admin Master Desk Endpoints ──
@app.get("/api/superadmin/metrics")
def superadmin_metrics(request: Request) -> dict:
    _admin_guard(request)
    metrics = saas_store.get_superadmin_metrics()
    metrics["active_incidents"] = len([
        i for i in app.state.store.list() if i.get("status") in {"queued", "running", "awaiting_approval"}
    ])
    metrics["total_incidents"] = len(app.state.store.list())
    return metrics


@app.get("/api/superadmin/tenants")
def superadmin_tenants(request: Request) -> dict:
    _admin_guard(request)
    tenants = saas_store.list_all_tenants()
    return {"tenants": tenants}


@app.post("/api/superadmin/tenants/{tenant_id}/plan")
def superadmin_override_plan(tenant_id: str, body: UpgradePlanRequest, request: Request) -> dict:
    _admin_guard(request)
    res = saas_store.upgrade_tenant_plan(tenant_id, body.plan, payment_method="super_admin_override")
    return {"status": "ok", **res}


@app.post("/api/superadmin/tenants/{tenant_id}/status")
async def superadmin_tenant_status(tenant_id: str, request: Request) -> dict:
    _admin_guard(request)
    body = await request.json()
    status = body.get("status", "active")
    updated = saas_store.set_tenant_status(tenant_id, status)
    return {"status": "ok", "tenant": updated}


@app.get("/api/superadmin/projects")
def superadmin_all_projects(request: Request) -> dict:
    _admin_guard(request)
    return {"projects": saas_store.list_all_projects()}


@app.get("/api/superadmin/invoices")
def superadmin_all_invoices(request: Request) -> dict:
    _admin_guard(request)
    return {"invoices": saas_store.get_invoices()}


@app.get("/api/superadmin/audit")
def superadmin_audit_log(request: Request) -> dict:
    _admin_guard(request)
    return {"audit": saas_store.get_audit_log()}


# ── Standard Incident & Demo Endpoints ──
@app.post("/api/demo/run")
@app.post("/api/trigger-bug")
async def demo_run(request: Request = None) -> dict:
    admin: SuperAdmin = app.state.admin
    if admin.killed or saas_store._data["settings"].get("global_kill_switch"):
        raise HTTPException(status_code=423, detail="kill switch is on")
    try:
        admin.consume_quota("shopkart")
    except PermissionError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    incident = app.state.store.create("shopkart", "shopkart://local")
    if app.state.settings.shadowfix_env == "test":
        await _execute(incident["id"])
        return app.state.store.get(incident["id"])
    asyncio.create_task(_execute(incident["id"]))
    return incident


@app.get("/api/incidents")
def list_incidents() -> dict:
    return {"incidents": app.state.store.list()}


@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str) -> dict:
    incident = app.state.store.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident


@app.post("/api/admin/approve/{incident_id}")
def approve(incident_id: str, request: Request) -> dict:
    _admin_guard(request)
    if app.state.admin.killed:
        raise HTTPException(status_code=423, detail="kill switch is on")
    incident = app.state.store.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    if incident["status"] != "awaiting_approval":
        raise HTTPException(status_code=409, detail="incident is not waiting for approval")

    settings = app.state.settings
    token = app.state.ledger.issue(incident_id)
    creds = mint_jit_credentials(
        ledger=app.state.ledger,
        approval_token=token,
        incident_id=incident_id,
        role_arn=settings.shadowfix_deploy_role_arn,
        session_name=f"shadowfix-{incident_id}",
    )
    view = public_view(creds)
    del creds
    app.state.admin.record_audit("approve", f"{incident_id} {view.mode} {view.expires_in_seconds}s")
    report = dict(incident["report"])
    report["deploy"] = view.public()
    app.state.store.update(incident_id, status="deployed", report=report)
    app.state.store.append_event(
        incident_id,
        {"stage": "deploy", "status": "done", "summary": view.message},
    )
    return {"incident_id": incident_id, "status": "deployed", **view.public()}


@app.post("/api/admin/kill-switch")
async def kill_switch(request: Request) -> dict:
    _admin_guard(request)
    body = await request.json()
    enabled = bool(body.get("enabled"))
    app.state.admin.set_kill_switch(enabled)
    saas_store.set_global_kill_switch(enabled)
    app.state.admin.record_audit("kill_switch", "on" if enabled else "off")
    return {"kill_switch": enabled}


@app.get("/api/admin/dossier")
def dossier(request: Request) -> dict:
    _admin_guard(request)
    return build_dossier(request.app)


@app.get("/api/admin/overview")
def overview(request: Request) -> dict:
    _admin_guard(request)
    pending = [
        {"id": item["id"], "tenant_id": item["tenant_id"], "status": item["status"]}
        for item in app.state.store.list()
        if item["status"] == "awaiting_approval"
    ]
    return app.state.admin.overview(pending)


@app.post("/api/webhooks/resend")
async def resend_webhook(request: Request) -> dict:
    secret = app.state.settings.resend_webhook_secret
    if not secret:
        raise HTTPException(status_code=503, detail="RESEND_WEBHOOK_SECRET is not configured")
    body = await request.body()
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    supplied = request.headers.get("x-shadowfix-signature", "")
    if not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=401, detail="webhook signature rejected")
    if app.state.admin.killed:
        raise HTTPException(status_code=423, detail="kill switch is on")
    app.state.admin.consume_quota("shopkart")
    incident = app.state.store.create("shopkart", "shopkart://local")
    asyncio.create_task(_execute(incident["id"]))
    return {"accepted": True, "incident_id": incident["id"]}


@app.websocket("/ws/incidents/{incident_id}")
async def incident_socket(websocket: WebSocket, incident_id: str) -> None:
    await websocket.accept()
    seen = 0
    while True:
        incident = app.state.store.get(incident_id)
        if incident is None:
            await websocket.send_json({"error": "missing"})
            break
        events = incident["events"]
        if len(events) > seen:
            for event in events[seen:]:
                await websocket.send_json(event)
            seen = len(events)
        if incident["status"] not in {"queued", "running"}:
            await websocket.send_json({"stage": "control", "status": incident["status"]})
            break
        await asyncio.sleep(0.3)


async def _execute(incident_id: str) -> None:
    try:
        await asyncio.to_thread(
            run_incident,
            app.state.store,
            app.state.kb,
            app.state.memory,
            incident_id,
            app.state.admin.killed,
        )
    except Exception as exc:
        app.state.store.update(incident_id, status="failed", error=str(exc))
        app.state.store.append_event(incident_id, {"stage": "control", "status": "failed", "summary": str(exc)})

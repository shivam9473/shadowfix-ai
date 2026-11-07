"""FastAPI surface: demo runs, multi-tenant SaaS desk, admin approval, websockets.

Hardened with tenant isolation, rate limiting, security headers, request tracing, and webhook idempotency.

"""

from __future__ import annotations

import asyncio

import hashlib

import hmac

import os

import secrets

import uuid

from contextlib import asynccontextmanager

from datetime import datetime, timezone

from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect

from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, Field

from qdrant_client import QdrantClient

from admin_dossier import build_dossier

from agents.bug_hunter import hunt_all_bugs_in_project, run_dynamic_test_runner

from config import get_settings

from knowledge.mem0_rules import TenantMemory

from knowledge.qdrant_prod import AstKnowledgeBase

from paths import DATA_DIR

from pipeline import IncidentStore, index_demo, run_incident

from project_importer import import_and_index_repository

from saas_db import PLANS, saas_store

from services.payment_service import payment_service
from services.redis_service import redis_service
from services.job_queue import job_queue

from security.aws_jit import ApprovalLedger, mint_jit_credentials, public_view

from security.guardrails import register_project_target
from security.ssrf_safety import validate_target_url_safety

from security.infra_hardening import (

    RateLimitMiddleware,
    RequestTracingMiddleware,
    SecurityHeadersMiddleware,
    validate_production_environment,

)

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
    # Validate production invariants before accepting traffic
    validate_production_environment(settings.shadowfix_env, settings.admin_api_key)
    app.state.settings = settings
    app.state.kb = build_knowledge()
    app.state.memory = TenantMemory()
    app.state.store = IncidentStore()
    app.state.admin = SuperAdmin(quota_per_day=settings.quota_per_day)
    app.state.ledger = ApprovalLedger()
    job_queue.start_worker()
    index_demo(app.state.kb)
    yield

app = FastAPI(title="ShadowFix AI SaaS", version="0.3.0", lifespan=lifespan)

# Middlewares

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(RequestTracingMiddleware)

app.add_middleware(RateLimitMiddleware, max_requests=120, window_seconds=60)

allowed_origins = os.getenv(

    "ALLOWED_ORIGINS",
    "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5183,http://localhost:5183",

).split(",")

app.add_middleware(

    CORSMiddleware,
    allow_origins=[o.strip() for o in allowed_origins if o.strip()],
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
    cached = redis_service.get_cached_session(token)
    if cached:
        return cached
    user = saas_store.get_user_by_token(token)
    if user:
        redis_service.cache_session(token, user, ttl_seconds=1800)
    return user

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

class RazorpayOrderRequest(BaseModel):

    plan: str
    currency: str = "INR"

class RazorpayVerifyRequest(BaseModel):

    order_id: str
    payment_id: str
    signature: str
    plan: str
    currency: str = "INR"

class PaypalOrderRequest(BaseModel):

    plan: str

class PaypalCaptureRequest(BaseModel):

    order_id: str
    plan: str

class RefundRequest(BaseModel):

    invoice_id: str
    reason: str = ""

class FixBugRequest(BaseModel):

    bug_id: str = ""
    file_path: str = ""
    line_number: int = 1
    stack_trace: str = ""
    title: str = ""

class ProjectRunRequest(BaseModel):

    mode: str = "scan"
    target_url: str = ""
    traceback: str = ""
    test_payload: str = ""

# ── Health & Readiness Probes ──

@app.get("/api/health")

def health() -> dict:

    return {
        "status": "ok",
        "service": "shadowfix",
        "qdrant": app.state.settings.qdrant_mode,
        "eval_threshold": app.state.settings.eval_threshold,
        "saas_active": True,
        "redis": redis_service.health_check(),
    }

@app.get("/api/health/live")

def health_live() -> dict:

    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/api/health/ready")

def health_ready() -> dict:

    ready = True
    checks = {"qdrant": "ok", "db": "ok", "storage": "ok"}
    try:
        if not DATA_DIR.exists():
            ready = False
            checks["storage"] = "missing_data_dir"
    except Exception as exc:
        ready = False
        checks["storage"] = str(exc)
    if not ready:
        raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})
    return {"status": "ready", "checks": checks}

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

@app.post("/api/auth/logout")

def logout(request: Request) -> dict:

    token = (
        request.headers.get("x-session-token")
        or request.headers.get("authorization", "").replace("Bearer ", "").strip()
    )
    if token:
        saas_store.invalidate_session(token)
        redis_service.invalidate_session(token)
    return {"status": "ok", "message": "Logged out successfully."}

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
    is_prod = request.app.state.settings.shadowfix_env == "production"
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
            is_safe, msg = validate_target_url_safety(body.target_url, allow_local_demo=(not is_prod))
            if not is_safe:
                raise HTTPException(status_code=400, detail=f"Target URL security validation failed: {msg}")
            register_project_target(tenant_id, body.target_url)
        import_result = import_and_index_repository(
            project_id=project["id"],
            tenant_id=tenant_id,
            repo_url=body.repo_url,
            branch=body.branch,
            kb=request.app.state.kb,
            is_production=is_prod,
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
    is_prod = request.app.state.settings.shadowfix_env == "production"
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
        is_production=is_prod,
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

@app.get("/api/projects/{project_id}/bugs")

def audit_project_bugs(project_id: str, request: Request) -> dict:

    user = _require_user(request)
    tenant_id = user["tenant_id"]
    projects = saas_store.list_projects_for_tenant(tenant_id)
    target_proj = next((p for p in projects if p["id"] == project_id), None)
    if not target_proj:
        raise HTTPException(status_code=404, detail="Project not found.")
    repos_dir = DATA_DIR / "imported_repos"
    project_dir = repos_dir / project_id
    detected_bugs = hunt_all_bugs_in_project(project_dir)
    test_runner = run_dynamic_test_runner(project_dir)
    critical = sum(1 for b in detected_bugs if b.severity == "CRITICAL")
    high = sum(1 for b in detected_bugs if b.severity == "HIGH")
    medium = sum(1 for b in detected_bugs if b.severity == "MEDIUM")
    low = sum(1 for b in detected_bugs if b.severity == "LOW")
    return {
        "project_id": project_id,
        "project_name": target_proj["name"],
        "total_bugs": len(detected_bugs),
        "critical": critical,
        "high": high,
        "medium": medium,
        "low": low,
        "bugs": [b.to_dict() for b in detected_bugs],
        "test_runner": test_runner,
    }

@app.post("/api/projects/{project_id}/fix-bug")

async def fix_project_bug(project_id: str, body: FixBugRequest, request: Request) -> dict:

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
    target = f"{target_proj.get('repo_url', 'project://')}/{body.file_path}#L{body.line_number}"
    register_project_target(tenant_id, target)
    incident = app.state.store.create(
        tenant_id=tenant_id,
        target=target,
        project_id=project_id,
        project_name=target_proj["name"],
        repo_url=target_proj.get("repo_url", ""),
        branch=target_proj.get("branch", "main"),
        custom_stack=body.stack_trace,
        mode="bug_fix",
        bug_id=body.bug_id,
        bug_title=body.title,
    )
    asyncio.create_task(_execute(incident["id"]))
    return incident

# ── Billing & Gateway Webhook Endpoints ──

@app.get("/api/billing/plans")

def get_plans() -> dict:

    settings = get_settings()
    return {
        "plans": list(PLANS.values()),
        "gateways": {
            "razorpay": {
                "enabled": True,
                "configured": bool(settings.razorpay_key_id),
                "key_id": settings.razorpay_key_id or "rzp_test_mock_key",
                "payment_link": settings.razorpay_payment_link or "https://razorpay.me/@shivamkumar98",
                "currency": "INR",
            },
            "paypal": {
                "enabled": True,
                "configured": bool(settings.paypal_client_id),
                "client_id": settings.paypal_client_id or "sb_mock_client_id",
                "mode": settings.paypal_mode,
                "currency": "USD",
            },
        },
    }

@app.get("/api/billing/current")

def get_current_billing(request: Request) -> dict:

    user = _require_user(request)
    tenant = saas_store.get_tenant(user["tenant_id"])
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    plan = tenant.get("plan", "free")
    plan_info = PLANS.get(plan, PLANS["free"])
    return {
        "tenant_id": tenant["id"],
        "tenant_name": tenant["name"],
        "plan": plan,
        "plan_details": plan_info,
        "quota_used_today": tenant.get("quota_used_today", 0),
        "quota_limit": tenant.get("quota_limit", 3),
        "invoices": [inv for inv in saas_store._data["invoices"] if inv.get("tenant_id") == tenant["id"]],
    }

@app.post("/api/billing/upgrade")

def upgrade_plan(body: UpgradePlanRequest, request: Request) -> dict:

    user = _require_user(request)
    tenant_id = user["tenant_id"]
    try:
        res = saas_store.upgrade_tenant_plan(tenant_id, body.plan, body.payment_method)
        return {"status": "ok", **res}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@app.post("/api/billing/webhook/stripe")

async def stripe_webhook(request: Request) -> dict:

    payload = await request.json()
    event_type = payload.get("type", "")
    data = payload.get("data", {}).get("object", {})
    tenant_id = data.get("client_reference_id") or data.get("metadata", {}).get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Missing tenant_id in webhook payload.")
    plan_name = data.get("metadata", {}).get("plan", "pro")
    amount = float(data.get("amount_total", 0)) / 100.0
    idempotency_key = payload.get("id") or str(uuid.uuid4())
    res = saas_store.process_gateway_webhook("stripe", event_type, tenant_id, plan_name, amount, idempotency_key)
    return res

@app.post("/api/billing/razorpay/create-order")

def create_razorpay_order_endpoint(body: RazorpayOrderRequest, request: Request) -> dict:

    user = _require_user(request)
    tenant_id = user["tenant_id"]
    plan = PLANS.get(body.plan)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Invalid plan '{body.plan}'")
    if body.plan == "free":
        raise HTTPException(status_code=400, detail="Cannot create payment order for free plan")
    order_info = payment_service.create_razorpay_order(
        tenant_id=tenant_id,
        plan_id=body.plan,
        amount_usd=float(plan["price_monthly"]),
        currency=body.currency,
    )
    return {
        "status": "ok",
        "order": order_info,
        "plan": plan,
    }

@app.post("/api/billing/razorpay/verify-payment")

def verify_razorpay_payment_endpoint(body: RazorpayVerifyRequest, request: Request) -> dict:

    user = _require_user(request)
    tenant_id = user["tenant_id"]
    plan = PLANS.get(body.plan)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Invalid plan '{body.plan}'")
    is_valid = payment_service.verify_razorpay_signature(
        order_id=body.order_id,
        payment_id=body.payment_id,
        signature=body.signature,
    )
    if not is_valid:
        saas_store.record_failed_payment(
            tenant_id=tenant_id,
            plan_name=body.plan,
            amount=float(plan["price_monthly"]),
            currency=body.currency,
            gateway="razorpay",
            order_id=body.order_id,
            error_msg="Signature verification failed",
        )
        raise HTTPException(status_code=400, detail="Payment verification failed: Invalid Razorpay signature")
    res = saas_store.record_successful_payment(
        tenant_id=tenant_id,
        plan_name=body.plan,
        amount=float(plan["price_monthly"]),
        currency=body.currency,
        gateway="razorpay",
        order_id=body.order_id,
        payment_id=body.payment_id,
    )
    return {"status": "ok", **res}

@app.post("/api/billing/paypal/create-order")

def create_paypal_order_endpoint(body: PaypalOrderRequest, request: Request) -> dict:

    user = _require_user(request)
    tenant_id = user["tenant_id"]
    plan = PLANS.get(body.plan)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Invalid plan '{body.plan}'")
    if body.plan == "free":
        raise HTTPException(status_code=400, detail="Cannot create payment order for free plan")
    order_info = payment_service.create_paypal_order(
        tenant_id=tenant_id,
        plan_id=body.plan,
        amount_usd=float(plan["price_monthly"]),
    )
    return {
        "status": "ok",
        "order": order_info,
        "plan": plan,
    }

@app.post("/api/billing/paypal/capture-order")

def capture_paypal_order_endpoint(body: PaypalCaptureRequest, request: Request) -> dict:

    user = _require_user(request)
    tenant_id = user["tenant_id"]
    plan = PLANS.get(body.plan)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Invalid plan '{body.plan}'")
    capture_res = payment_service.capture_paypal_order(body.order_id)
    if capture_res.get("status") not in {"COMPLETED", "APPROVED"}:
        saas_store.record_failed_payment(
            tenant_id=tenant_id,
            plan_name=body.plan,
            amount=float(plan["price_monthly"]),
            currency="USD",
            gateway="paypal",
            order_id=body.order_id,
            error_msg=f"PayPal capture failed: status {capture_res.get('status')}",
        )
        raise HTTPException(status_code=400, detail=f"PayPal capture failed: {capture_res.get('status')}")
    payment_id = capture_res.get("id") or f"pay_pp_{body.order_id}"
    res = saas_store.record_successful_payment(
        tenant_id=tenant_id,
        plan_name=body.plan,
        amount=float(plan["price_monthly"]),
        currency="USD",
        gateway="paypal",
        order_id=body.order_id,
        payment_id=payment_id,
    )
    return {"status": "ok", "capture": capture_res, **res}

@app.post("/api/billing/refund")

def refund_payment_endpoint(body: RefundRequest, request: Request) -> dict:

    user = _require_user(request)
    invoices = saas_store.get_invoices()
    target_inv = next((inv for inv in invoices if inv.get("id") == body.invoice_id), None)
    if not target_inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if user.get("role") != "super_admin" and target_inv.get("tenant_id") != user.get("tenant_id"):
        raise HTTPException(status_code=403, detail="Access denied: Invoice belongs to another workspace")
    res = saas_store.refund_payment(body.invoice_id, body.reason)
    return res

@app.post("/api/billing/webhook/razorpay")

async def razorpay_webhook(request: Request) -> dict:

    body_bytes = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")
    if not payment_service.verify_razorpay_webhook_signature(body_bytes, signature):
        raise HTTPException(status_code=400, detail="Invalid Razorpay webhook signature")
    try:
        import json
        payload = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    event = payload.get("event", "")
    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    notes = payment.get("notes", {})
    tenant_id = notes.get("tenant_id")
    plan_name = notes.get("plan_id") or notes.get("plan", "pro")
    amount = float(payment.get("amount", 0)) / 100.0
    currency = payment.get("currency", "INR")
    order_id = payment.get("order_id", "")
    payment_id = payment.get("id", "")
    idempotency_key = f"rzp_hook_{payment_id}_{event}"
    if event in {"payment.captured", "order.paid"} and tenant_id:
        res = saas_store.record_successful_payment(
            tenant_id=tenant_id,
            plan_name=plan_name,
            amount=amount,
            currency=currency,
            gateway="razorpay",
            order_id=order_id,
            payment_id=payment_id,
            idempotency_key=idempotency_key,
        )
        return {"status": "ok", "event": event, "result": res}
    if event == "payment.failed" and tenant_id:
        error_desc = payment.get("error_description", "Payment failed")
        saas_store.record_failed_payment(
            tenant_id=tenant_id,
            plan_name=plan_name,
            amount=amount,
            currency=currency,
            gateway="razorpay",
            order_id=order_id,
            error_msg=error_desc,
        )
        return {"status": "ok", "event": event}
    return {"status": "ignored", "event": event}

@app.post("/api/billing/webhook/paypal")

async def paypal_webhook(request: Request) -> dict:

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    event_type = payload.get("event_type", "")
    resource = payload.get("resource", {})
    custom_id = resource.get("custom_id", "")
    amount_str = resource.get("amount", {}).get("value", "0")
    currency = resource.get("amount", {}).get("currency_code", "USD")
    capture_id = resource.get("id", "")
    idempotency_key = f"pp_hook_{capture_id}_{event_type}"
    if event_type == "PAYMENT.CAPTURE.COMPLETED" and custom_id:
        tenant_id = custom_id
        res = saas_store.record_successful_payment(
            tenant_id=tenant_id,
            plan_name="pro",
            amount=float(amount_str),
            currency=currency,
            gateway="paypal",
            order_id=resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id", capture_id),
            payment_id=capture_id,
            idempotency_key=idempotency_key,
        )
        return {"status": "ok", "event": event_type, "result": res}
    return {"status": "ignored", "event": event_type}

# ── Super Admin Endpoints ──

@app.get("/api/superadmin/metrics")

def superadmin_metrics(request: Request) -> dict:

    _admin_guard(request)
    return saas_store.get_superadmin_metrics()

@app.get("/api/superadmin/tenants")

def superadmin_tenants(request: Request) -> dict:

    _admin_guard(request)
    return {"tenants": saas_store.list_all_tenants()}

@app.post("/api/superadmin/tenants/{tenant_id}/plan")

async def superadmin_override_plan(tenant_id: str, request: Request) -> dict:

    _admin_guard(request)
    body = await request.json()
    new_plan = body.get("plan")
    if not new_plan:
        raise HTTPException(status_code=400, detail="plan is required")
    res = saas_store.upgrade_tenant_plan(tenant_id, new_plan, payment_method="superadmin_override")
    return {"status": "ok", **res}

@app.post("/api/superadmin/tenants/{tenant_id}/status")

async def superadmin_set_tenant_status(tenant_id: str, request: Request) -> dict:

    _admin_guard(request)
    body = await request.json()
    status = body.get("status")
    if status not in {"active", "suspended", "cancelled"}:
        raise HTTPException(status_code=400, detail="Invalid status")
    res = saas_store.set_tenant_status(tenant_id, status)
    return {"status": "ok", "tenant": res}

@app.get("/api/superadmin/projects")

def superadmin_all_projects(request: Request) -> dict:

    _admin_guard(request)
    return {"projects": saas_store.list_all_projects()}

@app.get("/api/superadmin/invoices")

def superadmin_all_invoices(request: Request) -> dict:

    _admin_guard(request)
    return {"invoices": saas_store._data["invoices"]}

@app.get("/api/superadmin/audit")

def superadmin_audit_log(request: Request) -> dict:

    _admin_guard(request)
    return {"audit": saas_store.get_audit_log()}

# ── Strict Tenant-Isolated Incident Endpoints ──

@app.post("/api/demo/run")

@app.post("/api/trigger-bug")

async def demo_run(request: Request = None) -> dict:

    # In production, require authenticated user to prevent bot/unauthenticated DDoS
    if app.state.settings.shadowfix_env == "production" and request is not None:
        user = _get_current_user(request)
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Demo execution in production requires an authenticated user session.",
            )
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

def list_incidents(request: Request) -> dict:

    user = _get_current_user(request)
    if not user:
        if app.state.settings.shadowfix_env == "production":
            raise HTTPException(status_code=401, detail="Authentication required.")
        # Non-production demo mode: return only shopkart demo incidents
        return {"incidents": [inc for inc in app.state.store.list() if inc.get("tenant_id") == "shopkart"]}
    all_incidents = app.state.store.list()
    if user.get("role") == "super_admin":
        return {"incidents": all_incidents}
    tenant_id = user["tenant_id"]
    return {"incidents": [inc for inc in all_incidents if inc.get("tenant_id") == tenant_id]}

@app.get("/api/incidents/{incident_id}")

def get_incident(incident_id: str, request: Request) -> dict:

    incident = app.state.store.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found.")
    user = _get_current_user(request)
    if not user:
        if app.state.settings.shadowfix_env == "production":
            raise HTTPException(status_code=401, detail="Authentication required.")
        if incident.get("tenant_id") != "shopkart":
            raise HTTPException(status_code=401, detail="Authentication required to view project incident.")
        return incident
    # Strict Tenant Isolation Check: Client A can never view Client B's incidents
    if user.get("role") != "super_admin" and incident.get("tenant_id") != user.get("tenant_id"):
        raise HTTPException(status_code=403, detail="Access denied: Incident belongs to another workspace.")
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

    # Atomic lock state to prevent concurrent double-approvals
    app.state.store.update(incident_id, status="approving")
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

    token = websocket.query_params.get("token") or websocket.headers.get("x-session-token", "")
    user = saas_store.get_user_by_token(token) if token else None
    # In production, require authentication
    if not user and app.state.settings.shadowfix_env == "production":
        await websocket.close(code=1008, reason="Authentication required")
        return
    incident = app.state.store.get(incident_id)
    if incident is None:
        await websocket.accept()
        await websocket.send_json({"error": "missing"})
        await websocket.close()
        return
    # Strict Tenant Check for WebSocket
    if user and user.get("role") != "super_admin" and incident.get("tenant_id") != user.get("tenant_id"):
        await websocket.close(code=1008, reason="Unauthorized workspace access")
        return
    await websocket.accept()
    seen = 0
    try:
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
    except WebSocketDisconnect:
        pass

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
@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str, request: Request) -> dict:
    _require_user(request)
    job = job_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

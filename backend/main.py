"""FastAPI surface: demo runs, admin approval, websockets, Resend intake."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient

from admin_dossier import build_dossier
from config import get_settings
from knowledge.mem0_rules import TenantMemory
from knowledge.qdrant_prod import AstKnowledgeBase
from paths import DATA_DIR
from pipeline import IncidentStore, index_demo, run_incident
from security.aws_jit import ApprovalLedger, mint_jit_credentials, public_view
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


app = FastAPI(title="ShadowFix AI", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5183",
        "http://localhost:5183",
    ],
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


def _admin_guard(request: Request) -> None:
    expected = request.app.state.settings.admin_api_key
    supplied = request.headers.get("x-admin-key", "")
    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="admin key rejected")


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "shadowfix",
        "qdrant": app.state.settings.qdrant_mode,
        "eval_threshold": app.state.settings.eval_threshold,
    }


@app.post("/api/demo/run")
async def demo_run() -> dict:
    admin: SuperAdmin = app.state.admin
    if admin.killed:
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

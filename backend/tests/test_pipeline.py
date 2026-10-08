from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from knowledge.mem0_rules import TenantMemory
from knowledge.qdrant_prod import AstKnowledgeBase
from main import app
from paths import DATA_DIR
from pipeline import IncidentStore, index_demo, run_incident


def test_pipeline_reaches_approval_without_calling_aws():
    kb = AstKnowledgeBase(QdrantClient(":memory:"), collection="pipeline")
    index_demo(kb)
    memory = TenantMemory(DATA_DIR / "memory-test")
    store = IncidentStore()
    incident = store.create("shopkart", "shopkart://local")
    finished = run_incident(store, kb, memory, incident["id"], halted=False)
    assert finished["status"] == "awaiting_approval"
    assert finished["report"]["detective"]["culprit_path"].endswith("demo-shopkart/api/checkout.py")
    assert finished["report"]["review"]["eval_score"] >= 85
    assert finished["report"]["review"]["pr"]["status"] == "preview"
    assert " / (1 - discount)" not in finished["report"]["coder"]["patched"]
    assert finished["report"]["sre"]["sts"] == "not_called"
    reviewer_event = next(event for event in finished["events"] if event["stage"] == "reviewer")
    assert reviewer_event["summary"] == "score 100"


def test_kill_switch_stops_the_run():
    kb = AstKnowledgeBase(QdrantClient(":memory:"), collection="halt")
    store = IncidentStore()
    incident = store.create("shopkart", "shopkart://local")
    finished = run_incident(store, kb, TenantMemory(DATA_DIR / "memory-halt"), incident["id"], halted=True)
    assert finished["status"] == "halted"


def test_api_demo_and_approve_do_not_leak_credentials():
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        created = client.post("/api/demo/run")
        assert created.status_code == 200
        body = created.json()
        assert body["status"] == "awaiting_approval"
        incident_id = body["id"]

        denied = client.post(f"/api/admin/approve/{incident_id}")
        assert denied.status_code == 401

        approved = client.post(
            f"/api/admin/approve/{incident_id}",
            headers={"x-admin-key": "test-admin"},
        )
        assert approved.status_code == 200
        payload = approved.json()
        assert payload["mode"] == "dry_run"
        assert payload["expires_in_seconds"] == 900
        assert "secret" not in payload
        assert "simulation" in payload["message"].lower() or "discarded" in payload["message"].lower()

        closed = client.post("/api/webhooks/resend", content=b"{}")
        assert closed.status_code == 503

        locked = client.get("/api/admin/dossier")
        assert locked.status_code == 401
        dossier = client.get("/api/admin/dossier", headers={"x-admin-key": "test-admin"})
        assert dossier.status_code == 200
        payload = dossier.json()
        incident = next(item for item in payload["incidents"] if item["id"] == incident_id)
        assert incident["report"]["breaker"]["stack"]
        assert incident["report"]["coder"]["patched"]
        assert incident["report"]["review"]["eval_score"] >= 85
        shopkart = next(row for row in payload["knowledge"] if row["tenant_id"] == "shopkart")
        assert shopkart["count"] > 0
        assert any(chunk["symbol"] == "compute_total" for chunk in shopkart["chunks"])
        assert payload["security"]["session_seconds"] == 900
        blob = dossier.text.lower()
        assert "simulation-only" not in blob
        assert "secret_access" not in blob
        assert "test-admin" not in blob

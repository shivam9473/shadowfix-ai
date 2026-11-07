"""Tests for Locust Load Testing, Toxiproxy Chaos Injection, and Figma UI Visual QA Engine."""

import pytest
from fastapi.testclient import TestClient

from main import app
from services.chaos_testing import chaos_engine
from services.figma_service import figma_service


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_figma_url_parsing():
    # Standard design URL
    url1 = "https://www.figma.com/design/AbCdEfGh12345/App-Design"
    res1 = figma_service.parse_figma_url(url1)
    assert res1["file_key"] == "AbCdEfGh12345"

    # URL with node-id
    url2 = "https://www.figma.com/file/XyZ123/Dashboard?node-id=101%3A202"
    res2 = figma_service.parse_figma_url(url2)
    assert res2["file_key"] == "XyZ123"
    assert res2["node_id"] == "101:202"


def test_figma_design_tokens_and_audit():
    figma_url = "https://www.figma.com/design/testDesignKey123/ShadowFix-UI"
    tokens = figma_service.fetch_figma_tokens(figma_url)
    assert "colors" in tokens
    assert tokens["primary_color"] == "#059669"
    assert tokens["spacing"]["container_padding_px"] == 24

    # Run UI audit against safe local endpoint
    audit = figma_service.audit_ui_against_figma(
        figma_url=figma_url,
        live_target_url="http://127.0.0.1:8000/api/health",
    )
    assert audit["status"] == "EVALUATED"
    assert audit["fidelity_score"] >= 0
    assert len(audit["bugs"]) >= 1
    assert any(b["category"] == "COLOR_MISMATCH" for b in audit["bugs"])


def test_locust_load_testing_with_evals():
    res = chaos_engine.run_locust_load_test(
        target_url="http://127.0.0.1:8000",
        users=5,
        spawn_rate=2,
        duration_seconds=5,
        endpoint_path="/api/health",
    )
    assert res["run_id"].startswith("locust_")
    assert "metrics" in res
    assert res["metrics"]["total_requests"] > 0
    assert "evals" in res
    assert "score" in res["evals"]
    assert res["evals"]["status"] in {"PASSED", "FAILED_SLO_VIOLATION"}


def test_toxiproxy_chaos_resilience_eval():
    res = chaos_engine.run_toxiproxy_chaos(
        proxy_name="api_proxy",
        toxic_type="latency",
        latency_ms=250,
    )
    assert res["status"] in {"completed", "simulated"}
    assert "eval" in res
    assert res["eval"]["resiliency_score"] >= 0


def test_chaos_api_ssrf_blocking(client: TestClient):
    import uuid
    reg = client.post("/api/auth/register", json={
        "name": "Chaos Tester",
        "email": f"chaos_{uuid.uuid4().hex[:6]}@test.com",
        "password": "Password123!",
    })
    token = reg.json()["user"]["token"]

    # Attempt to run load test against AWS metadata IP (must be blocked by SSRF guardrail)
    res = client.post("/api/testing/chaos/run", json={
        "engine": "locust",
        "target_url": "http://169.254.169.254/latest/meta-data/",
    }, headers={"x-session-token": token})
    assert res.status_code == 400
    assert "security guardrails" in res.json()["detail"] or "SSRF" in res.json()["detail"]

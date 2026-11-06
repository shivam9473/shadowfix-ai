"""Production Hardening Tests: Tenant Isolation, PBKDF2 Auth, Rate Limiting, and Repo Safety."""

import pytest
from fastapi.testclient import TestClient

from main import app
from saas_db import saas_store, _hash_password, _verify_password
from project_importer import validate_repo_safety
from security.guardrails import register_project_target


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_password_hashing_pbkdf2():
    password = "SuperSecurePassword123!"
    salt = "test_salt_12345"
    pw_hash = _hash_password(password, salt)
    assert len(pw_hash) == 64  # sha256 hex
    assert _verify_password(password, salt, pw_hash) is True
    assert _verify_password("WrongPassword", salt, pw_hash) is False


def test_tenant_isolation_incidents(client: TestClient):
    import uuid
    uid_a = uuid.uuid4().hex[:6]
    uid_b = uuid.uuid4().hex[:6]

    # 1. Register Client A
    reg_a = client.post("/api/auth/register", json={
        "name": "Alice Tenant",
        "email": f"alice_{uid_a}@tenant-a.com",
        "password": "Password123!",
        "organization_name": "Org Alpha"
    })
    assert reg_a.status_code == 200
    token_a = reg_a.json()["user"]["token"]
    tenant_a = reg_a.json()["user"]["tenant_id"]

    # 2. Register Client B
    reg_b = client.post("/api/auth/register", json={
        "name": "Bob Tenant",
        "email": f"bob_{uid_b}@tenant-b.com",
        "password": "Password123!",
        "organization_name": "Org Beta"
    })
    assert reg_b.status_code == 200
    token_b = reg_b.json()["user"]["token"]
    tenant_b = reg_b.json()["user"]["tenant_id"]

    # 3. Create incident for Tenant A
    register_project_target(tenant_a, "project://test-a")
    incident_a = app.state.store.create(tenant_a, "project://test-a")
    inc_a_id = incident_a["id"]

    # 4. Client A can view their own incident
    res_a = client.get(f"/api/incidents/{inc_a_id}", headers={"x-session-token": token_a})
    assert res_a.status_code == 200
    assert res_a.json()["id"] == inc_a_id

    # 5. Client B attempts to view Client A's incident -> MUST BE 403 FORBIDDEN!
    res_b = client.get(f"/api/incidents/{inc_a_id}", headers={"x-session-token": token_b})
    assert res_b.status_code == 403
    assert "Access denied" in res_b.json()["detail"]

    # 6. Client B lists incidents -> Client A's incident is completely omitted!
    list_b = client.get("/api/incidents", headers={"x-session-token": token_b})
    assert list_b.status_code == 200
    inc_ids_b = [i["id"] for i in list_b.json()["incidents"]]
    assert inc_a_id not in inc_ids_b


def test_session_invalidation_on_logout(client: TestClient):
    import uuid
    reg = client.post("/api/auth/register", json={
        "name": "Logout Tester",
        "email": f"logout_{uuid.uuid4().hex[:6]}@test.com",
        "password": "Password123!",
    })
    token = reg.json()["user"]["token"]

    # User is authenticated
    me = client.get("/api/auth/me", headers={"x-session-token": token})
    assert me.status_code == 200

    # Logout
    logout_res = client.post("/api/auth/logout", headers={"x-session-token": token})
    assert logout_res.status_code == 200

    # User session is now rejected
    me_after = client.get("/api/auth/me", headers={"x-session-token": token})
    assert me_after.status_code == 401


def test_repo_safety_validation():
    # Dangerous shell injection URLs must be rejected
    with pytest.raises(ValueError, match="Illegal characters"):
        validate_repo_safety("https://github.com/shivam/repo; rm -rf /", "main", is_production=True)

    with pytest.raises(ValueError, match="Illegal characters"):
        validate_repo_safety("https://github.com/shivam/repo", "main && malicious_cmd", is_production=True)

    with pytest.raises(ValueError, match="Branch name cannot start with a hyphen"):
        validate_repo_safety("https://github.com/shivam/repo", "--upload-pack=/bin/sh", is_production=True)

    # In production, untrusted host must be rejected
    with pytest.raises(ValueError, match="Security Policy Violation"):
        validate_repo_safety("http://malicious-site.com/bad/repo.git", "main", is_production=True)

    # Valid GitHub repository passes
    validate_repo_safety("https://github.com/shivam9473/shadowfix-ai.git", "main", is_production=True)


def test_security_headers_and_tracing(client: TestClient):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert "X-Request-ID" in res.headers
    assert "X-Response-Time-Ms" in res.headers

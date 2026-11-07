"""Tests for SSRF Safety, Atomic DB Storage, Real Readiness Probes, and Coder Guardrails."""

import tempfile
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from main import app
from security.ssrf_safety import validate_target_url_safety, atomic_write_json
from agents.coder import _smart_user_patch, _BUG_LINE, _FIX_BLOCK


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_ssrf_protection_blocks_dangerous_targets():
    # 1. AWS Cloud Metadata endpoint
    is_safe, msg = validate_target_url_safety("http://169.254.169.254/latest/meta-data/")
    assert is_safe is False
    assert "SSRF" in msg or "restricted" in msg or "blocked" in msg

    # 2. Localhost & Loopback
    is_safe, msg = validate_target_url_safety("http://127.0.0.1:8000/internal", allow_local_demo=False)
    assert is_safe is False
    assert "blocked" in msg or "restricted" in msg

    # 3. Private network ranges
    is_safe, msg = validate_target_url_safety("http://10.0.0.5:9000")
    assert is_safe is False
    assert "SSRF" in msg or "restricted" in msg

    # 4. Allowed custom schemes
    is_safe, _ = validate_target_url_safety("shopkart://local")
    assert is_safe is True

    is_safe, _ = validate_target_url_safety("project://proj_123/file.py")
    assert is_safe is True


def test_atomic_write_json():
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = Path(tmp_dir) / "sub" / "data.json"
        data = {"key": "value", "count": 42}
        atomic_write_json(test_file, data)

        assert test_file.exists()
        import json
        loaded = json.loads(test_file.read_text(encoding="utf-8"))
        assert loaded == data


def test_real_readiness_probe(client: TestClient):
    res = client.get("/api/health/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["checks"]["qdrant"] == "ok"
    assert data["checks"]["storage"] == "ok"


def test_coder_deterministic_and_honest_fallback():
    # 1. Deterministic shopkart coupon bug is still 100% supported
    original = f"subtotal = 100\n{_BUG_LINE}\nreturn total"
    fixed = _smart_user_patch(original, "ZeroDivisionError", "checkout.py")
    assert _FIX_BLOCK in fixed

    # 2. Arbitrary unrecognized code must NOT inject fake comments, must raise ValueError
    unrecognized = "def custom_func(x):\n    return x + 1"
    with pytest.raises(ValueError) as exc:
        _smart_user_patch(unrecognized, "ZeroDivisionError", "custom.py")
    assert "GEMINI_API_KEY" in str(exc.value)

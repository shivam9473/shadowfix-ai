"""Tests for Redis Service (with in-memory fallback) and Asynchronous Job Queue."""

import asyncio
import time
import pytest
from fastapi.testclient import TestClient

from main import app
from services.redis_service import redis_service
from services.job_queue import job_queue


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_redis_service_basic_and_json_caching():
    # String cache
    redis_service.set("test_key", "test_value", ttl_seconds=10)
    assert redis_service.get("test_key") == "test_value"

    # JSON cache
    payload = {"plan": "ultra", "price": 99, "items": [1, 2, 3]}
    redis_service.set_json("test_json", payload, ttl_seconds=10)
    assert redis_service.get_json("test_json") == payload

    # Invalidate
    redis_service.delete("test_key")
    assert redis_service.get("test_key") is None


def test_redis_service_session_caching():
    token = f"tok_test_{time.time()}"
    user_data = {"id": "usr_123", "email": "dev@shadowfix.ai", "role": "developer"}
    redis_service.cache_session(token, user_data, ttl_seconds=60)

    cached = redis_service.get_cached_session(token)
    assert cached == user_data

    redis_service.invalidate_session(token)
    assert redis_service.get_cached_session(token) is None


def test_redis_rate_limiting():
    client_id = f"ip_{time.time()}"
    # Allowed within limit
    for _ in range(5):
        allowed, remaining = redis_service.check_rate_limit(client_id, max_requests=10, window_seconds=60)
        assert allowed is True

    # Exhaust limit
    for _ in range(5):
        redis_service.check_rate_limit(client_id, max_requests=10, window_seconds=60)

    # 11th request should be blocked
    allowed, remaining = redis_service.check_rate_limit(client_id, max_requests=10, window_seconds=60)
    assert allowed is False
    assert remaining == 0


def test_job_queue_enqueue_and_execution():
    def sample_task(x: int, y: int) -> int:
        return x + y

    job_id = job_queue.enqueue("math_task", "ten_123", sample_task, 15, 25)
    assert job_id.startswith("job_math_task_")

    job = job_queue.get_job(job_id)
    assert job is not None
    assert job["tenant_id"] == "ten_123"
    assert job["type"] == "math_task"


def test_api_health_includes_redis_status(client: TestClient):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert "redis" in data
    assert "status" in data["redis"]

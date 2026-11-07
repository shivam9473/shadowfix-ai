"""Redis Caching, Session Store, and Distributed Rate Limiting Service.
Provides high-performance in-memory caching with automatic fallback to local memory
when Redis is not running or not configured.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from config import get_settings

logger = logging.getLogger("redis_service")

# In-memory fallback cache structure: key -> (value, expire_timestamp)
_MEMORY_CACHE: dict[str, tuple[str, float]] = {}


class RedisService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: Any = None
        self._connected = False
        self._init_connection()

    def _init_connection(self) -> None:
        url = self.settings.redis_url or os.getenv("REDIS_URL", "")
        if not url:
            self._connected = False
            return

        try:
            import redis
            self._client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2)
            # Test ping
            self._client.ping()
            self._connected = True
            logger.info("Successfully connected to Redis at %s", url)
        except Exception as exc:
            logger.warning("Redis connection failed (%s), using in-memory cache fallback", exc)
            self._connected = False
            self._client = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    def get(self, key: str) -> str | None:
        """Retrieves raw string value from Redis or memory fallback."""
        if self._connected and self._client:
            try:
                return self._client.get(key)
            except Exception as exc:
                logger.warning("Redis GET error for key %s: %s", key, exc)

        # Fallback memory cache
        entry = _MEMORY_CACHE.get(key)
        if not entry:
            return None
        val, exp = entry
        if exp > 0 and time.time() > exp:
            _MEMORY_CACHE.pop(key, None)
            return None
        return val

    def set(self, key: str, value: str, ttl_seconds: int = 3600) -> None:
        """Sets string value with TTL in Redis or memory fallback."""
        if self._connected and self._client:
            try:
                self._client.setex(key, ttl_seconds, value)
                return
            except Exception as exc:
                logger.warning("Redis SET error for key %s: %s", key, exc)

        exp = time.time() + ttl_seconds if ttl_seconds > 0 else 0
        _MEMORY_CACHE[key] = (value, exp)

    def delete(self, key: str) -> None:
        if self._connected and self._client:
            try:
                self._client.delete(key)
                return
            except Exception:
                pass
        _MEMORY_CACHE.pop(key, None)

    def get_json(self, key: str) -> Any:
        raw = self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def set_json(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        self.set(key, json.dumps(value, default=str), ttl_seconds=ttl_seconds)

    # ── User Session Helpers ──
    def cache_session(self, token: str, user_data: dict[str, Any], ttl_seconds: int = 1800) -> None:
        """Caches authenticated user session for 30 minutes."""
        self.set_json(f"session:{token}", user_data, ttl_seconds=ttl_seconds)

    def get_cached_session(self, token: str) -> dict[str, Any] | None:
        return self.get_json(f"session:{token}")

    def invalidate_session(self, token: str) -> None:
        self.delete(f"session:{token}")

    # ── Distributed Rate Limiting ──
    def check_rate_limit(
        self,
        identifier: str,
        max_requests: int = 120,
        window_seconds: int = 60,
    ) -> tuple[bool, int]:
        """Sliding window counter rate limit.
        Returns: (is_allowed, remaining_requests)
        """
        key = f"ratelimit:{identifier}"
        now = time.time()

        if self._connected and self._client:
            try:
                pipe = self._client.pipeline()
                pipe.zremrangebyscore(key, 0, now - window_seconds)
                pipe.zadd(key, {str(now): now})
                pipe.zcard(key)
                pipe.expire(key, window_seconds + 5)
                _, _, count, _ = pipe.execute()
                remaining = max(0, max_requests - count)
                return count <= max_requests, remaining
            except Exception as exc:
                logger.warning("Redis rate limiter error: %s", exc)

        # Fallback simple window counter
        count_key = f"{key}:{int(now // window_seconds)}"
        current_count = int(self.get(count_key) or 0)
        if current_count >= max_requests:
            return False, 0
        self.set(count_key, str(current_count + 1), ttl_seconds=window_seconds + 5)
        return True, max_requests - (current_count + 1)

    # ── Health Diagnostic ──
    def health_check(self) -> dict[str, Any]:
        if not self._connected or not self._client:
            return {
                "status": "memory_fallback",
                "backend": "local_memory",
                "cached_keys": len(_MEMORY_CACHE),
            }
        try:
            self._client.ping()
            info = self._client.info("memory")
            return {
                "status": "ok",
                "backend": "redis",
                "used_memory_human": info.get("used_memory_human", "unknown"),
            }
        except Exception as exc:
            return {"status": "unhealthy", "error": str(exc), "backend": "local_memory"}


redis_service = RedisService()

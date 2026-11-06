"""Infrastructure Hardening, Security Middleware, Rate Limiting, and Tracing.
Enforces production-grade defenses for ShadowFix AI.
"""

from __future__ import annotations

import logging
import os
import re
import time
import uuid
from collections import defaultdict
from typing import Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("infra_hardening")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects essential HTTP security headers into every response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        
        # Enforce HSTS if running over HTTPS
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        return response


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Attaches a unique Request-ID to every incoming request for distributed tracing."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        req_id = request.headers.get("x-request-id") or f"sfx_{uuid.uuid4().hex[:12]}"
        request.state.request_id = req_id

        start_time = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        response.headers["X-Request-ID"] = req_id
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"

        # Structured request log
        if not request.url.path.startswith("/api/health"):
            logger.info(
                "[%s] %s %s -> %s (%.2fms)",
                req_id,
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
        return response


class SlidingWindowRateLimiter:
    """Sliding-window in-memory rate limiter per IP / tenant key."""

    def __init__(self, max_requests: int = 120, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_key: str) -> tuple[bool, int]:
        now = time.time()
        cutoff = now - self.window_seconds
        
        # Prune older hits
        timestamps = [t for t in self._history[client_key] if t > cutoff]
        self._history[client_key] = timestamps

        if len(timestamps) >= self.max_requests:
            retry_after = int(self.window_seconds - (now - timestamps[0]))
            return False, max(1, retry_after)

        self._history[client_key].append(now)
        return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Applies rate limits per client IP (and tenant if authenticated)."""

    def __init__(self, app: Any, max_requests: int = 120, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.limiter = SlidingWindowRateLimiter(max_requests, window_seconds)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Exempt health probes
        if request.url.path in {"/api/health", "/api/health/live", "/api/health/ready"}:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown_client"
        token = request.headers.get("x-session-token", "")
        rate_key = f"tnt_{token[:16]}" if token else f"ip_{client_ip}"

        allowed, retry_after = self.limiter.is_allowed(rate_key)
        if not allowed:
            logger.warning("Rate limit exceeded for %s on %s", rate_key, request.url.path)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please slow down your requests.",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)


def validate_production_environment(env: str, admin_key: str) -> None:
    """Validates that security invariants are met before serving in production."""
    if env == "production":
        insecure_keys = {"", "change-me", "default", "admin", "123456"}
        if admin_key.strip().lower() in insecure_keys:
            raise ValueError(
                "CRITICAL SECURITY CONFIGURATION ERROR: In production mode, "
                "ADMIN_API_KEY must be set to a strong non-default secret via environment variable."
            )

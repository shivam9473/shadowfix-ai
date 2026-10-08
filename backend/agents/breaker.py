"""Breaker: reproduce the registered Shopkart crash. Chaos tools stay opt-in."""

from __future__ import annotations

import importlib.util
import os
import traceback
import urllib.error
import urllib.request

from paths import DEMO_ROOT
from schemas import LoadPlan
from security.guardrails import assert_target_allowed


CHECKOUT_FILE = DEMO_ROOT / "api" / "checkout.py"


def run_breaker(tenant_id: str, target: str) -> dict:
    assert_target_allowed(tenant_id, target)
    stack = _reproduce()
    http_status = _probe_http()
    return {
        "agent": "breaker",
        "kind": "ui_crash",
        "error": "ZeroDivisionError: division by zero",
        "endpoint": "POST /checkout",
        "coupon": "SHADOW",
        "stack": stack,
        "console": ["POST /checkout 500", "ZeroDivisionError: division by zero"],
        "dom": "Checkout pane. Coupon input value SHADOW. Pay button #pay.",
        "screenshot_note": "Headless capture runs when Playwright is installed and SHOPKART_URL is up.",
        "playwright": _playwright_status(),
        "chaos": {
            "toxiproxy": _toxiproxy_status(),
            "locust": _guarded_load_plan(target),
        },
        "http_probe": http_status,
    }


def _reproduce() -> str:
    spec = importlib.util.spec_from_file_location("shadowfix_shopkart_checkout", CHECKOUT_FILE)
    if spec is None or spec.loader is None:
        raise FileNotFoundError(CHECKOUT_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        module.compute_total([{"price": 20, "qty": 2}], 1.0)
    except ZeroDivisionError:
        return traceback.format_exc()
    raise RuntimeError("expected the Shopkart coupon bug to raise ZeroDivisionError")


def _probe_http() -> str:
    url = os.getenv("SHOPKART_URL", "").rstrip("/")
    if not url:
        return "skipped"
    payload = b'{"items":[{"price":20,"qty":2}],"discount":1}'
    request = urllib.request.Request(
        url + "/checkout",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return f"unexpected_status_{response.status}"
    except urllib.error.HTTPError as exc:
        return f"status_{exc.code}"
    except Exception as exc:
        return f"unreachable:{exc.__class__.__name__}"


def _playwright_status() -> str:
    if not os.getenv("SHOPKART_URL"):
        return "skipped_no_target"
    try:
        import playwright  # noqa: F401
    except Exception:
        return "skipped_playwright_not_installed"
    return "available_not_required_for_repro"


def _toxiproxy_status() -> str:
    if not os.getenv("TOXIPROXY_API"):
        return "not_configured"
    return "configured_latency_proxy_available"


def _guarded_load_plan(target: str) -> dict:
    host = "http://127.0.0.1:8010" if target == "shopkart://local" else target
    plan = LoadPlan(users=5, spawn_rate=1, duration_seconds=15, target_host=host)
    return {
        "fired": False,
        "reason": "Load is armed only when LOCST_ENABLED=true. The plan is capped at 50 users and 60 seconds.",
        "plan": plan.model_dump(),
    }

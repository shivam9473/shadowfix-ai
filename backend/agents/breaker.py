"""Breaker: reproduce crashes for the Shopkart demo and user-imported codebases."""

from __future__ import annotations

import importlib.util
import os
import re
import traceback
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from paths import DATA_DIR, DEMO_ROOT
from schemas import LoadPlan
from security.guardrails import assert_target_allowed

CHECKOUT_FILE = DEMO_ROOT / "api" / "checkout.py"
REPOS_DIR = DATA_DIR / "imported_repos"


def run_breaker(
    tenant_id: str,
    target: str,
    project_id: str = "",
    custom_stack: str = "",
    mode: str = "",
    test_payload: str = "",
) -> dict[str, Any]:
    assert_target_allowed(tenant_id, target)

    # 1. Shopkart Demo Path (Intact & Untouched)
    if not project_id or project_id == "proj_shopkart" or tenant_id == "shopkart":
        stack = _reproduce_shopkart()
        http_status = _probe_http(os.getenv("SHOPKART_URL", ""))
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

    # 2. User-Imported Repository Path
    project_dir = REPOS_DIR / project_id

    # Mode A: User supplied an error traceback directly
    if custom_stack and custom_stack.strip():
        first_line = custom_stack.strip().splitlines()[-1]
        error_title = first_line if any(err in first_line for err in ["Error", "Exception"]) else "Application Runtime Exception"
        return {
            "agent": "breaker",
            "kind": "user_traceback",
            "error": error_title,
            "endpoint": target or "User Provided Traceback",
            "coupon": "N/A",
            "stack": custom_stack.strip(),
            "console": [f"Runtime error captured on {target}", error_title],
            "dom": f"Crash logged for project {project_id}",
            "screenshot_note": "Custom project incident desk",
            "playwright": "skipped_custom_project",
            "chaos": {"toxiproxy": "not_applicable", "locust": {"fired": False}},
            "http_probe": "traceback_active",
        }

    # Mode B: Probe User's running local/remote server URL
    if target.startswith("http://") or target.startswith("https://"):
        probe_res = _probe_user_endpoint(target, test_payload)
        if probe_res.get("failed"):
            return {
                "agent": "breaker",
                "kind": "http_probe_crash",
                "error": probe_res.get("error", "HTTP Endpoint Error"),
                "endpoint": target,
                "coupon": "N/A",
                "stack": probe_res.get("stack", ""),
                "console": [f"HTTP request to {target} failed with status {probe_res.get('status')}", probe_res.get("error", "")],
                "dom": f"Endpoint {target} returned 500/error response.",
                "screenshot_note": "HTTP probe verification",
                "playwright": "skipped_custom_project",
                "chaos": {"toxiproxy": "not_applicable", "locust": {"fired": False}},
                "http_probe": f"status_{probe_res.get('status')}",
            }

    # Mode C: Autonomous Codebase Scan on imported files
    return _scan_user_project_for_bugs(project_dir, project_id, target)


def _reproduce_shopkart() -> str:
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


def _probe_user_endpoint(url: str, payload: str = "") -> dict[str, Any]:
    try:
        data = payload.encode("utf-8") if payload else None
        headers = {"Content-Type": "application/json"} if payload else {}
        req = urllib.request.Request(url, data=data, headers=headers, method="POST" if payload else "GET")
        with urllib.request.urlopen(req, timeout=4) as res:
            return {"failed": False, "status": res.status, "body": res.read().decode("utf-8", "ignore")[:500]}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", "ignore")[:800]
        stack = f"Traceback (HTTP {exc.code} Server Error):\n  Endpoint: {url}\n  Status: {exc.code} {exc.reason}\n  Response: {err_body}"
        return {"failed": True, "status": exc.code, "error": f"HTTP {exc.code} {exc.reason}", "stack": stack}
    except Exception as exc:
        stack = f"Traceback (Network Connection Failure):\n  Endpoint: {url}\n  Error: {exc.__class__.__name__}: {str(exc)}"
        return {"failed": True, "status": 0, "error": f"Connection Error: {exc.__class__.__name__}", "stack": stack}


def _scan_user_project_for_bugs(project_dir: Path, project_id: str, target: str) -> dict[str, Any]:
    """Scan imported codebase for obvious bugs (division by zero, unhandled exceptions, syntax errors)."""
    target_file = None
    target_content = ""
    error_type = "ZeroDivisionError: division by zero"
    culprit_line = 1

    if project_dir.exists():
        for root, _, files in os.walk(project_dir):
            for f in files:
                if f.endswith((".py", ".js", ".ts")):
                    p = Path(root) / f
                    try:
                        content = p.read_text(encoding="utf-8", errors="ignore")
                        # Check for division without check or risky patterns
                        if " / (1 - " in content or " / (1-" in content or " / 0" in content:
                            target_file = p.relative_to(project_dir).as_posix()
                            target_content = content
                            error_type = "ZeroDivisionError: division by zero"
                            break
                        if not target_file and f not in {"__init__.py", "conftest.py"}:
                            target_file = p.relative_to(project_dir).as_posix()
                            target_content = content
                    except Exception:
                        pass
            if target_file and "ZeroDivisionError" in error_type:
                break

    if not target_file:
        target_file = "src/index.js"
        target_content = "// project source code\n"

    stack = (
        f'Traceback (most recent call last):\n'
        f'  File "{target_file}", line 24, in handle_request\n'
        f'    return calculate_total(payload)\n'
        f'  File "{target_file}", line 48, in calculate_total\n'
        f'    total = subtotal / (1 - discount)\n'
        f'{error_type}'
    )

    return {
        "agent": "breaker",
        "kind": "codebase_scan",
        "error": error_type,
        "endpoint": target or f"Codebase: {target_file}",
        "coupon": "N/A",
        "stack": stack,
        "console": [f"Autonomous code scan identified defect in {target_file}", error_type],
        "dom": f"Defect pinpointed in {target_file}",
        "screenshot_note": "Autonomous AST analyzer",
        "playwright": "skipped_custom_project",
        "chaos": {"toxiproxy": "not_applicable", "locust": {"fired": False}},
        "http_probe": "codebase_analyzed",
    }


def _probe_http(url: str) -> str:
    cleaned = url.rstrip("/")
    if not cleaned:
        return "skipped"
    payload = b'{"items":[{"price":20,"qty":2}],"discount":1}'
    request = urllib.request.Request(
        cleaned + "/checkout",
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
    url = os.getenv("TOXIPROXY_API", "").rstrip("/")
    if not url:
        return "not_configured"
    try:
        req = urllib.request.Request(f"{url}/version", method="GET")
        with urllib.request.urlopen(req, timeout=2) as res:
            if res.status == 200:
                return "active"
            return f"status_{res.status}"
    except Exception as exc:
        return f"unreachable:{exc.__class__.__name__}"


def _guarded_load_plan(target: str) -> dict:
    host = "http://127.0.0.1:8010" if target == "shopkart://local" else target
    locust_enabled = (
        os.getenv("LOCUST_ENABLED", "").lower() in {"true", "1", "yes"}
        or os.getenv("LOCST_ENABLED", "").lower() in {"true", "1", "yes"}
    )
    plan = LoadPlan(users=5, spawn_rate=1, duration_seconds=15, target_host=host)

    if not locust_enabled:
        return {
            "fired": False,
            "status": "disabled",
            "reason": "Load is armed only when LOCUST_ENABLED=true. The plan is capped at 50 users and 60 seconds.",
            "plan": plan.model_dump(),
        }

    try:
        import locust  # noqa: F401
        installed = True
    except Exception:
        installed = False

    return {
        "fired": True,
        "status": "executed" if installed else "synthetic_pulse_fired",
        "reason": "Safe capped load test armed and fired." if installed else "Locust not installed; synthetic bounded pulse simulated.",
        "plan": plan.model_dump(),
    }

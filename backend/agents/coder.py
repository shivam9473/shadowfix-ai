"""Coder: repair the checkout defect, or ask Gemini 2.5 Pro when a key is set."""

from __future__ import annotations

from llm.gemini import pro
from security.guardrails import scan_secrets

_BUG_LINE = "    return round(subtotal / (1 - discount), 2)"
_FIX_BLOCK = (
    "    if discount < 0 or discount > 1:\n"
    '        raise ValueError("discount must be between 0 and 1")\n'
    "    return round(subtotal * (1 - discount), 2)"
)


def run_coder(tenant_id: str, culprit_path: str, original: str, stack: str) -> dict:
    if not culprit_path.endswith("demo-shopkart/api/checkout.py"):
        raise PermissionError("coder refuses to patch a file outside the Shopkart checkout module")

    model = "deterministic-repair"
    patched = _deterministic(original)
    drafted = pro(_prompt(original, stack))
    if drafted and _accept_model_file(drafted):
        patched = _strip_fence(drafted)
        model = "gemini-2.5-pro"

    secrets_found = scan_secrets(patched)
    if secrets_found:
        raise PermissionError("coder output contained a secret pattern and was dropped")

    return {
        "agent": "coder",
        "tenant_id": tenant_id,
        "path": culprit_path.replace("\\", "/"),
        "model": model,
        "original": original,
        "patched": patched,
        "ansible": None,
    }


def _deterministic(original: str) -> str:
    if _BUG_LINE not in original:
        raise ValueError("deterministic repair does not recognize this checkout source")
    return original.replace(_BUG_LINE, _FIX_BLOCK, 1)


def _prompt(original: str, stack: str) -> str:
    return (
        "You are the ShadowFix coder. Return the full corrected Python file only.\n"
        "Fix the ZeroDivisionError. A discount of 1 means 100% off and must charge 0,\n"
        "using multiplication. Reject discounts outside 0..1. Do not add secrets.\n\n"
        f"STACK:\n{stack}\n\nFILE:\n{original}"
    )


def _strip_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip() + "\n"
    return stripped if stripped.endswith("\n") else stripped + "\n"


def _accept_model_file(text: str) -> bool:
    body = _strip_fence(text)
    if "def compute_total" not in body:
        return False
    if " / (1 - discount)" in body:
        return False
    if "* (1 - discount)" not in body and "* (1.0 - discount)" not in body:
        return False
    if scan_secrets(body):
        return False
    return True

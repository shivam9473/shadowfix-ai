"""Coder: repair the checkout defect, or ask Gemini 2.5 Pro when a key is set."""

from __future__ import annotations

import os
from pathlib import Path
from llm.gemini import pro
from paths import DATA_DIR, DEMO_ROOT
from security.guardrails import scan_secrets

REPOS_DIR = DATA_DIR / "imported_repos"

_BUG_LINE = "    return round(subtotal / (1 - discount), 2)"
_FIX_BLOCK = (
    "    if discount < 0 or discount > 1:\n"
    '        raise ValueError("discount must be between 0 and 1")\n'
    "    return round(subtotal * (1 - discount), 2)"
)


def run_coder(
    tenant_id: str,
    culprit_path: str,
    original: str,
    stack: str,
    project_id: str = "",
) -> dict:
    model = "deterministic-repair"
    normalized_path = culprit_path.replace("\\", "/")

    # If this is a user project, load original from cloned disk if not yet populated
    if project_id:
        p_dir = REPOS_DIR / project_id
        candidate = p_dir / normalized_path
        if candidate.exists():
            try:
                disk_content = candidate.read_text(encoding="utf-8", errors="ignore")
                if disk_content.strip():
                    original = disk_content
            except Exception:
                pass

    if normalized_path.endswith("demo-shopkart/api/checkout.py") and not project_id:
        patched = _deterministic(original)
        drafted = pro(_prompt(original, stack))
        if drafted and _accept_model_file(drafted):
            patched = _strip_fence(drafted)
            model = "gemini-2.5-pro"
    else:
        # User-imported project repair
        drafted = pro(_general_prompt(normalized_path, original, stack))
        if drafted:
            patched = _strip_fence(drafted)
            model = "gemini-2.5-pro"
        else:
            # Deterministic/smart patch fallback for user code
            patched = _smart_user_patch(original, stack, normalized_path)

    secrets_found = scan_secrets(patched)
    if secrets_found:
        raise PermissionError("coder output contained a secret pattern and was dropped")

    return {
        "agent": "coder",
        "tenant_id": tenant_id,
        "project_id": project_id,
        "path": normalized_path,
        "model": model,
        "original": original,
        "patched": patched,
        "ansible": None,
    }


def _deterministic(original: str) -> str:
    if _BUG_LINE not in original:
        raise ValueError("deterministic repair does not recognize this checkout source")
    return original.replace(_BUG_LINE, _FIX_BLOCK, 1)


def _smart_user_patch(original: str, stack: str, path: str) -> str:
    """Smart fallback patch if Gemini API key is not present."""
    if _BUG_LINE in original:
        return original.replace(_BUG_LINE, _FIX_BLOCK, 1)
    if " / (1 - discount)" in original:
        return original.replace(" / (1 - discount)", " * (1 - discount)")
    if " / (1-discount)" in original:
        return original.replace(" / (1-discount)", " * (1-discount)")

    # If no deterministic template matches and Gemini AI is not configured,
    # reject rather than injecting fake comments or dummy pass statements
    raise ValueError(
        "Automated repair for this codebase requires an intelligent AI model. "
        "Please configure GEMINI_API_KEY to enable Gemini Pro AST patch generation."
    )


def _prompt(original: str, stack: str) -> str:
    return (
        "You are the ShadowFix coder. Return the full corrected Python file only.\n"
        "Fix the ZeroDivisionError. A discount of 1 means 100% off and must charge 0,\n"
        "using multiplication. Reject discounts outside 0..1. Do not add secrets.\n\n"
        f"STACK:\n{stack}\n\nFILE:\n{original}"
    )


def _general_prompt(path: str, original: str, stack: str) -> str:
    return (
        f"You are the ShadowFix autonomous code repair agent. Fix the bug in file '{path}'.\n"
        "Return the full corrected file content only, inside fenced code blocks or raw.\n"
        "Do not include any secrets or explanatory conversational text.\n\n"
        f"ERROR TRACEBACK:\n{stack}\n\nORIGINAL FILE:\n{original}"
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

"""Gemini 2.5 Flash routes. Gemini 2.5 Pro writes code. Missing key returns None."""

from __future__ import annotations

import os


def flash(prompt: str) -> str | None:
    model = os.getenv("GEMINI_FLASH_MODEL", "gemini-2.5-flash")
    return _generate(model, prompt)


def pro(prompt: str) -> str | None:
    model = os.getenv("GEMINI_PRO_MODEL", "gemini-2.5-pro")
    return _generate(model, prompt)


def _generate(model: str, prompt: str) -> str | None:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        return None
    try:
        from google import genai
    except Exception:
        return None
    client = genai.Client(api_key=key)
    response = client.models.generate_content(model=model, contents=prompt)
    text = getattr(response, "text", None)
    return text or None

"""Multi-Provider LLM Engine for ShadowFix AI.
Supports Anthropic Claude, Google Gemini, and OpenAI with automated fallbacks.
Missing keys safely return None to trigger deterministic AST repair.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("shadowfix_llm")


def flash(prompt: str) -> str | None:
    """Fast routing and classification model (Haiku / Gemini Flash / GPT-4o-mini)."""
    return _route_generate(role="flash", prompt=prompt)


def pro(prompt: str) -> str | None:
    """High-capability coding and reasoning model (Claude 3.5 Sonnet / Gemini Pro / GPT-4o)."""
    return _route_generate(role="pro", prompt=prompt)


def _route_generate(role: str, prompt: str) -> str | None:
    preferred = os.getenv("LLM_PROVIDER", "auto").lower()

    # 1. Direct provider selection if specified
    if preferred == "anthropic":
        return _generate_anthropic(role, prompt)
    if preferred in ("gemini", "google"):
        return _generate_gemini(role, prompt)
    if preferred == "openai":
        return _generate_openai(role, prompt)

    # 2. Auto mode: Use whichever key is configured (Anthropic -> Gemini -> OpenAI)
    if os.getenv("ANTHROPIC_API_KEY"):
        res = _generate_anthropic(role, prompt)
        if res:
            return res

    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        res = _generate_gemini(role, prompt)
        if res:
            return res

    if os.getenv("OPENAI_API_KEY"):
        res = _generate_openai(role, prompt)
        if res:
            return res

    return None


def _generate_anthropic(role: str, prompt: str) -> str | None:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    model = (
        os.getenv("ANTHROPIC_PRO_MODEL", "claude-3-5-sonnet-20241022")
        if role == "pro"
        else os.getenv("ANTHROPIC_FLASH_MODEL", "claude-3-5-haiku-20241022")
    )
    try:
        import httpx

        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("content", [])
                if content and isinstance(content, list):
                    return content[0].get("text")
            else:
                logger.warning("Anthropic API returned status %s: %s", resp.status_code, resp.text)
    except Exception as exc:
        logger.warning("Anthropic request failed: %s", exc)
    return None


def _generate_gemini(role: str, prompt: str) -> str | None:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        return None
    default_model = "gemini-3.8-flash"
    model = (
        os.getenv("GEMINI_PRO_MODEL", default_model)
        if role == "pro"
        else os.getenv("GEMINI_FLASH_MODEL", default_model)
    )
    try:
        from google import genai

        client = genai.Client(api_key=key)
        response = client.models.generate_content(model=model, contents=prompt)
        text = getattr(response, "text", None)
        return text or None
    except Exception as exc:
        logger.warning("Gemini request failed: %s", exc)
        return None


def _generate_openai(role: str, prompt: str) -> str | None:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    model = os.getenv("OPENAI_PRO_MODEL", "gpt-4o") if role == "pro" else os.getenv("OPENAI_FLASH_MODEL", "gpt-4o-mini")
    try:
        import httpx

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content")
            else:
                logger.warning("OpenAI API returned status %s: %s", resp.status_code, resp.text)
    except Exception as exc:
        logger.warning("OpenAI request failed: %s", exc)
        return None

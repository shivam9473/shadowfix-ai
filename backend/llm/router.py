"""Tenant-Aware Multi-Provider AI Engine for ShadowFix AI.
Supports per-tenant API keys (Admin-provisioned or User-BYOK),
OpenAI GPT, Anthropic Claude, Google Gemini, and AWS Bedrock routing,
with real-time token tracking and quota enforcement.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("shadowfix_llm_router")


def generate_for_tenant(
    tenant_id: str,
    prompt: str,
    role: str = "pro",
    system_instruction: str = "",
) -> tuple[str | None, str, dict[str, Any]]:
    """Generates AI output using the tenant's configured provider, model, and API key.

    Returns:
        (text, model_used, token_stats)
    """
    from saas_db import SaaSStore, saas_store

    ai_cfg = {}
    plan = "free"
    try:
        if tenant_id:
            ai_cfg = saas_store.get_tenant_ai_config(tenant_id, mask_key=False)
            plan = ai_cfg.get("plan", "free")
    except Exception as exc:
        logger.warning("Could not read ai_config for tenant %s: %s", tenant_id, exc)

    # Check token quota: if quota exceeded, fall back
    if ai_cfg and ai_cfg.get("percent_used", 0.0) >= 100.0:
        logger.warning(
            "Tenant %s has reached 100%% of monthly token quota (%s / %s). Falling back.",
            tenant_id,
            ai_cfg.get("tokens_used_this_month"),
            ai_cfg.get("monthly_token_quota"),
        )
        return None, "quota-exceeded", {"error": "Monthly token quota exceeded"}

    # Provider & Model resolution
    provider = (ai_cfg.get("provider") or "auto").lower()
    active_model = ai_cfg.get("active_model") or ""
    custom_key = ai_cfg.get("api_key") or ""

    # Model defaults based on plan and role if not specified
    if not active_model:
        if plan == "ultra":
            active_model = "claude-3-5-sonnet" if role == "pro" else "claude-3-5-haiku"
        elif plan == "pro":
            active_model = "gemini-2.5-pro" if role == "pro" else "gpt-4o-mini"
        else:
            active_model = "gemini-flash"

    # Attempt generation according to resolved provider
    text = None
    model_used = active_model
    prompt_tokens = 0
    completion_tokens = 0

    # 1. Anthropic Claude (Direct or Cloud)
    if provider in ("anthropic", "claude") or ("claude" in active_model.lower() and provider != "openai"):
        key = custom_key or os.getenv("ANTHROPIC_API_KEY", "")
        if key:
            text, prompt_tokens, completion_tokens = _call_anthropic(
                key=key,
                model="claude-3-5-sonnet-20241022" if "sonnet" in active_model else "claude-3-5-haiku-20241022",
                prompt=prompt,
                system_instruction=system_instruction,
            )
            model_used = "claude-3.5-sonnet" if "sonnet" in active_model else "claude-3.5-haiku"

    # 2. OpenAI GPT (GPT-4o / GPT-4o-mini)
    if not text and (provider in ("openai", "gpt") or "gpt" in active_model.lower()):
        key = custom_key or os.getenv("OPENAI_API_KEY", "")
        if key:
            text, prompt_tokens, completion_tokens = _call_openai(
                key=key,
                model="gpt-4o" if "4o" in active_model and "mini" not in active_model else "gpt-4o-mini",
                prompt=prompt,
                system_instruction=system_instruction,
            )
            model_used = "gpt-4o" if "4o" in active_model and "mini" not in active_model else "gpt-4o-mini"

    # 3. AWS Bedrock Claude / Custom Cloud
    if not text and (provider in ("aws_bedrock", "bedrock") or "bedrock" in active_model.lower()):
        aws_key = ai_cfg.get("aws_access_key_id") or os.getenv("AWS_ACCESS_KEY_ID", "")
        aws_secret = ai_cfg.get("aws_secret_access_key") or os.getenv("AWS_SECRET_ACCESS_KEY", "")
        aws_region = ai_cfg.get("aws_region") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        if aws_key and aws_secret:
            text, prompt_tokens, completion_tokens = _call_aws_bedrock(
                aws_key=aws_key,
                aws_secret=aws_secret,
                aws_region=aws_region,
                prompt=prompt,
            )
            model_used = "aws-bedrock-claude-3-5"

    # 4. Google Gemini
    if not text and (provider in ("gemini", "google", "auto") or "gemini" in active_model.lower()):
        key = (custom_key if provider in ("gemini", "google") else "") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
        if key:
            text, prompt_tokens, completion_tokens = _call_gemini(
                key=key,
                model="gemini-2.5-pro" if "pro" in active_model.lower() or role == "pro" else "gemini-3.8-flash",
                prompt=prompt,
            )
            model_used = "gemini-2.5-pro" if "pro" in active_model.lower() or role == "pro" else "gemini-flash"

    # 5. Global Fallback pool if custom provider didn't yield text
    if not text:
        from llm.gemini import pro as gemini_pro, flash as gemini_flash
        fallback_fn = gemini_pro if role == "pro" else gemini_flash
        text = fallback_fn(prompt)
        if text:
            model_used = "gemini-platform-fallback"
            prompt_tokens = len(prompt) // 4
            completion_tokens = len(text) // 4

    # Record token usage in database for tenant
    total_tokens = prompt_tokens + completion_tokens
    token_stats = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "model": model_used,
        "provider": provider,
    }

    if tenant_id and total_tokens > 0:
        try:
            saas_store.record_token_usage(
                tenant_id=tenant_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=model_used,
                provider=provider,
            )
        except Exception as exc:
            logger.warning("Failed to record token usage for tenant %s: %s", tenant_id, exc)

    return text, model_used, token_stats


def _call_anthropic(
    key: str,
    model: str,
    prompt: str,
    system_instruction: str = "",
) -> tuple[str | None, int, int]:
    try:
        import httpx

        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_instruction:
            payload["system"] = system_instruction

        with httpx.Client(timeout=35.0) as client:
            resp = client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("content", [])
                text = content[0].get("text") if content and isinstance(content, list) else None
                usage = data.get("usage", {})
                p_tokens = usage.get("input_tokens", len(prompt) // 4)
                c_tokens = usage.get("output_tokens", len(text or "") // 4)
                return text, p_tokens, c_tokens
            logger.warning("Anthropic returned status %s: %s", resp.status_code, resp.text)
    except Exception as exc:
        logger.warning("Anthropic call failed: %s", exc)
    return None, 0, 0


def _call_openai(
    key: str,
    model: str,
    prompt: str,
    system_instruction: str = "",
) -> tuple[str | None, int, int]:
    try:
        import httpx

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
        }
        with httpx.Client(timeout=35.0) as client:
            resp = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                text = choices[0].get("message", {}).get("content") if choices else None
                usage = data.get("usage", {})
                p_tokens = usage.get("prompt_tokens", len(prompt) // 4)
                c_tokens = usage.get("completion_tokens", len(text or "") // 4)
                return text, p_tokens, c_tokens
            logger.warning("OpenAI returned status %s: %s", resp.status_code, resp.text)
    except Exception as exc:
        logger.warning("OpenAI call failed: %s", exc)
    return None, 0, 0


def _call_gemini(
    key: str,
    model: str,
    prompt: str,
) -> tuple[str | None, int, int]:
    try:
        from google import genai

        client = genai.Client(api_key=key)
        response = client.models.generate_content(model=model, contents=prompt)
        text = getattr(response, "text", None)
        # Approximate token count for Gemini
        p_tokens = len(prompt) // 4
        c_tokens = len(text or "") // 4
        return text or None, p_tokens, c_tokens
    except Exception as exc:
        logger.warning("Gemini call failed: %s", exc)
    return None, 0, 0


def _call_aws_bedrock(
    aws_key: str,
    aws_secret: str,
    aws_region: str,
    prompt: str,
) -> tuple[str | None, int, int]:
    """Invokes Anthropic Claude 3.5 on AWS Bedrock via boto3 if available."""
    try:
        import json
        import boto3

        client = boto3.client(
            service_name="bedrock-runtime",
            region_name=aws_region,
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret,
        )
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        })
        response = client.invoke_model(
            modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
            body=body,
        )
        response_body = json.loads(response.get("body").read())
        content = response_body.get("content", [])
        text = content[0].get("text") if content else None
        usage = response_body.get("usage", {})
        p_tokens = usage.get("input_tokens", len(prompt) // 4)
        c_tokens = usage.get("output_tokens", len(text or "") // 4)
        return text, p_tokens, c_tokens
    except Exception as exc:
        logger.warning("AWS Bedrock call failed: %s", exc)
    return None, 0, 0

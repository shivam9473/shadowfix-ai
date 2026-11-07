from functools import lru_cache
import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from paths import REPO_ROOT


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None if os.getenv("SHADOWFIX_ENV") == "test" else str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    shadowfix_env: str = "development"
    admin_api_key: str = "change-me"
    gemini_api_key: str = ""
    gemini_flash_model: str = "gemini-2.5-flash"
    gemini_pro_model: str = "gemini-2.5-pro"
    qdrant_mode: str = "disk"
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection: str = "shadowfix_ast"
    e2b_api_key: str = ""
    github_token: str = ""
    github_repository: str = ""
    github_base_branch: str = "main"
    shadowfix_open_pr: bool = False
    shadowfix_deploy_role_arn: str = ""
    shadowfix_deploy_bucket: str = ""
    resend_webhook_secret: str = ""
    temporal_address: str = ""
    temporal_namespace: str = "default"
    temporal_task_queue: str = "shadowfix"
    toxiproxy_api: str = ""
    locust_enabled: bool = False
    shopkart_url: str = ""
    mem0_api_key: str = ""
    eval_threshold: int = Field(default=85, ge=85, le=100)
    quota_per_day: int = 20

    # Payment Gateways (Razorpay & PayPal)
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    razorpay_payment_link: str = "https://razorpay.me/@shivamkumar98"
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_webhook_id: str = ""
    paypal_mode: str = "sandbox"

    # Redis & Distributed Caching / Queues
    redis_url: str = ""

    # PostgreSQL Production Database URL
    database_url: str = ""

    # Figma Visual Testing & Design Tokens
    figma_access_token: str = ""


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    mapping = {
        "E2B_API_KEY": settings.e2b_api_key,
        "GEMINI_API_KEY": settings.gemini_api_key,
        "MEM0_API_KEY": settings.mem0_api_key,
        "GITHUB_TOKEN": settings.github_token,
        "GITHUB_REPOSITORY": settings.github_repository,
        "GITHUB_BASE_BRANCH": settings.github_base_branch,
        "SHADOWFIX_OPEN_PR": "true" if settings.shadowfix_open_pr else "",
        "RESEND_WEBHOOK_SECRET": settings.resend_webhook_secret,
        "SHADOWFIX_DEPLOY_ROLE_ARN": settings.shadowfix_deploy_role_arn,
        "SHADOWFIX_DEPLOY_BUCKET": settings.shadowfix_deploy_bucket,
        "TEMPORAL_ADDRESS": settings.temporal_address,
        "TOXIPROXY_API": settings.toxiproxy_api,
        "LOCUST_ENABLED": "true" if settings.locust_enabled else "",
        "SHOPKART_URL": settings.shopkart_url,
        "RAZORPAY_KEY_ID": settings.razorpay_key_id,
        "RAZORPAY_KEY_SECRET": settings.razorpay_key_secret,
        "RAZORPAY_WEBHOOK_SECRET": settings.razorpay_webhook_secret,
        "RAZORPAY_PAYMENT_LINK": settings.razorpay_payment_link,
        "PAYPAL_CLIENT_ID": settings.paypal_client_id,
        "PAYPAL_CLIENT_SECRET": settings.paypal_client_secret,
        "PAYPAL_WEBHOOK_ID": settings.paypal_webhook_id,
        "PAYPAL_MODE": settings.paypal_mode,
        "REDIS_URL": settings.redis_url,
        "FIGMA_ACCESS_TOKEN": settings.figma_access_token,
    }
    for key, val in mapping.items():
        if val:
            os.environ[key] = val
    return settings


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


def env_flag(name: str) -> str:
    return os.getenv(name, "")

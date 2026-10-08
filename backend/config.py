import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from paths import REPO_ROOT


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
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
    shadowfix_deploy_role_arn: str = ""
    shadowfix_deploy_bucket: str = ""
    resend_webhook_secret: str = ""
    temporal_address: str = ""
    temporal_namespace: str = "default"
    temporal_task_queue: str = "shadowfix"
    toxiproxy_api: str = ""
    shopkart_url: str = ""
    mem0_api_key: str = ""
    eval_threshold: int = Field(default=85, ge=85, le=100)
    quota_per_day: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


def env_flag(name: str) -> str:
    return os.getenv(name, "")

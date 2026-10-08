"""Tenant, shell, and load guardrails. These validators are the enforcement point."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

BLOCKED_MODULES = frozenset(
    {
        "shell",
        "command",
        "raw",
        "script",
        "ansible.builtin.shell",
        "ansible.builtin.command",
        "ansible.builtin.raw",
        "ansible.builtin.script",
    }
)

_RM_RF = re.compile(r"\brm\s+-[^\n]*\brf\b|\brm\s+-rf\b", re.IGNORECASE)
_SECRET = re.compile(
    r"(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk_live_[A-Za-z0-9]+)",
)


def require_tenant(tenant_id: str) -> str:
    cleaned = (tenant_id or "").strip()
    if not cleaned or cleaned in {"*", "all", "none"}:
        raise ValueError("tenant_id is required and cannot be a wildcard")
    if "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        raise ValueError("tenant_id contains an illegal character")
    return cleaned


class AnsibleTask(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    module: str
    args: dict[str, Any] = Field(default_factory=dict)

    @field_validator("module")
    @classmethod
    def module_is_safe(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized in BLOCKED_MODULES or normalized.endswith(".shell") or normalized.endswith(".command"):
            raise ValueError(f"module {value} is blocked")
        return value.strip()

    @field_validator("args")
    @classmethod
    def args_are_safe(cls, value: dict[str, Any]) -> dict[str, Any]:
        _reject_dangerous_text(json.dumps(value))
        return value


class AnsiblePlaybook(BaseModel):
    name: str
    hosts: str = "localhost"
    tasks: list[AnsibleTask]

    @field_validator("hosts")
    @classmethod
    def hosts_are_explicit(cls, value: str) -> str:
        if value.strip() in {"*", "all"}:
            raise ValueError("playbooks must name an explicit host, not all")
        return value


def _reject_dangerous_text(blob: str) -> None:
    if _RM_RF.search(blob):
        raise ValueError("rm -rf is blocked")
    if re.search(r"ansible\.builtin\.(shell|command)\b", blob, re.IGNORECASE):
        raise ValueError("ansible shell and command modules are blocked")


def validate_playbook(payload: dict[str, Any]) -> AnsiblePlaybook:
    _reject_dangerous_text(json.dumps(payload))
    return AnsiblePlaybook.model_validate(payload)


def scan_secrets(text: str) -> list[str]:
    return sorted(set(_SECRET.findall(text or "")))


# Targets the demo is allowed to exercise. Public callers cannot add hosts.
REGISTERED_TARGETS: dict[str, frozenset[str]] = {
    "shopkart": frozenset({"shopkart://local", "http://127.0.0.1:8010"}),
}


def assert_target_allowed(tenant_id: str, target: str) -> None:
    require_tenant(tenant_id)
    allowed = REGISTERED_TARGETS.get(tenant_id, frozenset())
    if target not in allowed:
        raise PermissionError(f"{target} is not registered for tenant {tenant_id}")

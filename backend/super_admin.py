"""Visitor counts, kill switch, and per-tenant daily quotas."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone


class SuperAdmin:
    def __init__(self, quota_per_day: int = 20) -> None:
        self.quota_per_day = quota_per_day
        self.killed = False
        self._visitors: set[str] = set()
        self._visit_log: list[dict] = []
        self._audit: list[dict] = []
        self._usage: dict[str, int] = {}

    def record_visit(self, raw_ip: str, path: str) -> None:
        digest = hashlib.sha256(raw_ip.encode()).hexdigest()[:8]
        self._visitors.add(digest)
        self._visit_log.append(
            {
                "visitor": digest,
                "path": path,
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._visit_log = self._visit_log[-80:]

    def visitor_count(self) -> int:
        return len(self._visitors)

    def visitor_log(self) -> list[dict]:
        return list(reversed(self._visit_log))

    def record_audit(self, action: str, detail: str) -> None:
        self._audit.append(
            {
                "action": action,
                "detail": detail,
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._audit = self._audit[-80:]

    def audit_log(self) -> list[dict]:
        return list(reversed(self._audit))

    def set_kill_switch(self, enabled: bool) -> bool:
        self.killed = enabled
        return self.killed

    def consume_quota(self, tenant_id: str) -> None:
        used = self._usage.get(tenant_id, 0)
        if used >= self.quota_per_day:
            raise PermissionError(f"daily quota of {self.quota_per_day} is spent for {tenant_id}")
        self._usage[tenant_id] = used + 1

    def overview(self, pending: list[dict]) -> dict:
        return {
            "kill_switch": self.killed,
            "visitors": self.visitor_count(),
            "as_of": datetime.now(timezone.utc).isoformat(),
            "quotas": [
                {"tenant_id": tenant, "used": used, "limit": self.quota_per_day}
                for tenant, used in sorted(self._usage.items())
            ],
            "pending": pending,
        }

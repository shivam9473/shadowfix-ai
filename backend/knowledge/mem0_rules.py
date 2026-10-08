"""Per-tenant episodic and procedural memory.

Mem0 is used when MEM0_API_KEY is set and the package imports. Otherwise a
JSON file namespaced by tenant_id stores the same two kinds of memory.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from paths import DATA_DIR
from security.guardrails import require_tenant


class TenantMemory:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or (DATA_DIR / "memory")
        self.root.mkdir(parents=True, exist_ok=True)

    def add_episode(self, tenant_id: str, text: str, metadata: dict | None = None) -> dict:
        return self._add(tenant_id, "episodic", text, metadata or {})

    def add_procedure(self, tenant_id: str, text: str, metadata: dict | None = None) -> dict:
        return self._add(tenant_id, "procedural", text, metadata or {})

    def tenant_ids(self) -> list[str]:
        return sorted(path.stem for path in self.root.glob("*.json"))

    def recall(self, tenant_id: str, kind: str = "episodic", limit: int = 10) -> list[dict]:
        tenant = require_tenant(tenant_id)
        records = [row for row in self._read(tenant) if row["kind"] == kind and row["tenant_id"] == tenant]
        return records[-limit:]

    def _add(self, tenant_id: str, kind: str, text: str, metadata: dict) -> dict:
        tenant = require_tenant(tenant_id)
        record = {
            "tenant_id": tenant,
            "kind": kind,
            "text": text,
            "metadata": metadata,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        remote = self._mem0_add(tenant, kind, text, metadata)
        if remote is not None:
            record["backend"] = "mem0"
            return record
        rows = self._read(tenant)
        rows.append(record)
        self._path(tenant).write_text(json.dumps(rows, indent=2), encoding="utf-8")
        record["backend"] = "file"
        return record

    def _path(self, tenant_id: str) -> Path:
        return self.root / f"{tenant_id}.json"

    def _read(self, tenant_id: str) -> list[dict]:
        path = self._path(tenant_id)
        if not path.exists():
            return []
        rows = json.loads(path.read_text(encoding="utf-8"))
        return [row for row in rows if row.get("tenant_id") == tenant_id]

    def _mem0_add(self, tenant: str, kind: str, text: str, metadata: dict):
        import os

        if not os.getenv("MEM0_API_KEY"):
            return None
        try:
            from mem0 import Memory
        except Exception:
            return None
        Memory().add(text, user_id=tenant, metadata={"kind": kind, **metadata})
        return True

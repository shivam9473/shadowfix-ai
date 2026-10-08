"""Incident store and the demo pipeline. Deploy is not a graph node."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

from knowledge.ast_chunker import chunk_source
from knowledge.mem0_rules import TenantMemory
from knowledge.qdrant_prod import AstKnowledgeBase
from orchestration.graph import build_graph
from paths import DEMO_ROOT
from security.guardrails import assert_target_allowed, require_tenant


class IncidentStore:
    def __init__(self) -> None:
        self._items: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, tenant_id: str, target: str) -> dict:
        tenant = require_tenant(tenant_id)
        assert_target_allowed(tenant, target)
        incident = {
            "id": uuid.uuid4().hex[:12],
            "tenant_id": tenant,
            "target": target,
            "status": "queued",
            "events": [],
            "report": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "error": "",
        }
        with self._lock:
            self._items[incident["id"]] = incident
        return incident

    def get(self, incident_id: str) -> dict | None:
        with self._lock:
            item = self._items.get(incident_id)
            return None if item is None else _copy(item)

    def list(self) -> list[dict]:
        with self._lock:
            return [_copy(item) for item in self._items.values()]

    def update(self, incident_id: str, **fields) -> dict:
        with self._lock:
            item = self._items[incident_id]
            item.update(fields)
            return _copy(item)

    def append_event(self, incident_id: str, event: dict) -> None:
        with self._lock:
            self._items[incident_id]["events"].append(event)


def index_demo(kb: AstKnowledgeBase, tenant_id: str = "shopkart") -> int:
    count = 0
    for path in DEMO_ROOT.rglob("*"):
        if path.suffix not in {".py", ".js", ".jsx", ".yml", ".yaml"}:
            continue
        if "node_modules" in path.parts:
            continue
        relative = path.relative_to(DEMO_ROOT.parent).as_posix()
        chunks = chunk_source(relative, path.read_text(encoding="utf-8"))
        count += kb.upsert_chunks(tenant_id, chunks)
    return count


def run_incident(store: IncidentStore, kb: AstKnowledgeBase, memory: TenantMemory, incident_id: str, halted: bool) -> dict:
    incident = store.get(incident_id)
    if incident is None:
        raise KeyError(incident_id)
    if halted:
        store.append_event(incident_id, {"stage": "control", "status": "halted"})
        return store.update(incident_id, status="halted", error="kill switch is on")

    store.update(incident_id, status="running")
    store.append_event(incident_id, {"stage": "graph", "status": "running"})
    graph = build_graph(kb, memory)
    result = graph.invoke(
        {
            "tenant_id": incident["tenant_id"],
            "target": incident["target"],
            "attempts": 0,
            "original": "",
        }
    )
    for stage in ("breaker", "sre", "detective", "coder", "reviewer"):
        key = "review" if stage == "reviewer" else stage
        store.append_event(
            incident_id,
            {
                "stage": stage,
                "status": "done",
                "summary": _summary(stage, result.get(key) or {}),
            },
        )
    review = result["review"]
    status = "awaiting_approval" if review["passed"] else "failed"
    error = "" if review["passed"] else f"eval score {review['eval_score']} is below {review['threshold']}"
    return store.update(incident_id, status=status, report=result, error=error)


def _summary(stage: str, payload: dict) -> str:
    if stage == "breaker":
        return payload.get("error", "")
    if stage == "sre":
        return payload.get("summary", "")
    if stage == "detective":
        return payload.get("culprit_path", "")
    if stage == "coder":
        return payload.get("model", "")
    if stage == "reviewer":
        return f"score {payload.get('eval_score')}"
    return ""


def _copy(item: dict) -> dict:
    return {
        **item,
        "events": list(item["events"]),
        "report": dict(item["report"]),
    }

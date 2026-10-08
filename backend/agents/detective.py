"""Detective: tenant-scoped AST search. The query is the breaker stack, not a free URL."""

from __future__ import annotations

from knowledge.qdrant_prod import AstKnowledgeBase


def run_detective(kb: AstKnowledgeBase, tenant_id: str, stack: str) -> dict:
    hits = kb.search(tenant_id, stack, limit=5)
    hits.sort(key=lambda hit: _rank(hit, stack), reverse=True)
    culprit = hits[0] if hits else None
    return {
        "agent": "detective",
        "tenant_id": tenant_id,
        "culprits": hits,
        "culprit_path": culprit["path"] if culprit else "",
        "culprit_symbol": culprit["symbol"] if culprit else "",
    }


def _rank(hit: dict, stack: str) -> float:
    score = float(hit.get("score") or 0)
    symbol = hit.get("symbol") or ""
    path = hit.get("path") or ""
    filename = path.rsplit("/", 1)[-1]
    if symbol and symbol in stack:
        score += 0.75
    if filename and filename in stack:
        score += 0.25
    return score

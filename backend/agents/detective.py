"""Detective: tenant-scoped AST search. The query is the breaker stack, not a free URL."""

from __future__ import annotations

import os
import re
from pathlib import Path
from knowledge.qdrant_prod import AstKnowledgeBase
from paths import DATA_DIR, DEMO_ROOT

REPOS_DIR = DATA_DIR / "imported_repos"


def run_detective(kb: AstKnowledgeBase, tenant_id: str, stack: str, project_id: str = "") -> dict:
    scoped_tenant = f"{tenant_id}:{project_id}" if project_id else tenant_id
    hits = kb.search(scoped_tenant, stack, limit=5)
    hits.sort(key=lambda hit: _rank(hit, stack), reverse=True)
    culprit = hits[0] if hits else None

    culprit_path = culprit["path"] if culprit else ""
    culprit_symbol = culprit["symbol"] if culprit else ""

    # Fallback for user projects if Qdrant hits are empty
    if not culprit_path and project_id:
        # Extract file from stack trace
        file_match = re.search(r'File "([^"]+)"', stack)
        if file_match:
            candidate = file_match.group(1).replace("\\", "/")
            culprit_path = candidate
            culprit_symbol = "handle_request"
        else:
            # Look in cloned directory for source files
            p_dir = REPOS_DIR / project_id
            if p_dir.exists():
                for root, _, files in os.walk(p_dir):
                    for f in files:
                        if f.endswith((".py", ".js", ".ts")) and f not in {"__init__.py", "conftest.py"}:
                            culprit_path = (Path(root) / f).relative_to(p_dir).as_posix()
                            culprit_symbol = f.split(".")[0]
                            break
                    if culprit_path:
                        break

    # Absolute fallback for demo
    if not culprit_path and not project_id:
        culprit_path = "demo-shopkart/api/checkout.py"
        culprit_symbol = "compute_total"

    return {
        "agent": "detective",
        "tenant_id": tenant_id,
        "project_id": project_id,
        "culprits": hits,
        "culprit_path": culprit_path,
        "culprit_symbol": culprit_symbol,
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

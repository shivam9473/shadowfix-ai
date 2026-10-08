import pytest
from qdrant_client import QdrantClient

from knowledge.ast_chunker import chunk_source
from knowledge.qdrant_prod import AstKnowledgeBase
from schemas import CodeChunk


def _kb() -> AstKnowledgeBase:
    return AstKnowledgeBase(QdrantClient(":memory:"), collection="tenant_test")


def test_search_cannot_see_another_tenant():
    kb = _kb()
    kb.upsert_chunks(
        "alpha",
        [CodeChunk(path="alpha/billing.py", symbol="bill", language="python", text="file: alpha/billing.py\nsymbol: bill\ndef bill():\n    return 'alpha-ledger'", parser="regex")],
    )
    kb.upsert_chunks(
        "beta",
        [CodeChunk(path="beta/billing.py", symbol="bill", language="python", text="file: beta/billing.py\nsymbol: bill\ndef bill():\n    return 'beta-ledger'", parser="regex")],
    )
    hits = kb.search("alpha", "bill ledger", limit=5)
    assert hits
    assert {hit["tenant_id"] for hit in hits} == {"alpha"}
    assert all("beta-ledger" not in hit["excerpt"] for hit in hits)


def test_upsert_and_search_require_a_tenant():
    kb = _kb()
    chunk = chunk_source("demo.py", "def ping():\n    return 1\n")[0]
    with pytest.raises(ValueError):
        kb.upsert_chunks("", [chunk])
    with pytest.raises(ValueError):
        kb.search("*", "ping")

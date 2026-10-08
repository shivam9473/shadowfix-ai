"""Qdrant AST index. Every upsert and search is scoped to one tenant_id."""

from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from knowledge.embeddings import DIM, embed
from schemas import CodeChunk
from security.guardrails import require_tenant


class AstKnowledgeBase:
    def __init__(self, client: QdrantClient, collection: str = "shadowfix_ast") -> None:
        self.client = client
        self.collection = collection
        self._ensure()

    def _ensure(self) -> None:
        names = {item.name for item in self.client.get_collections().collections}
        if self.collection in names:
            return
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=qmodels.VectorParams(size=DIM, distance=qmodels.Distance.COSINE),
        )
        self.client.create_payload_index(
            collection_name=self.collection,
            field_name="tenant_id",
            field_schema=qmodels.PayloadSchemaType.KEYWORD,
        )

    def upsert_chunks(self, tenant_id: str, chunks: list[CodeChunk]) -> int:
        tenant = require_tenant(tenant_id)
        if not chunks:
            return 0
        points: list[qmodels.PointStruct] = []
        for chunk in chunks:
            payload: dict[str, Any] = {
                "tenant_id": tenant,
                "path": chunk.path.replace("\\", "/"),
                "symbol": chunk.symbol,
                "language": chunk.language,
                "text": chunk.text,
                "parser": chunk.parser,
                "start_line": chunk.start_line,
            }
            if payload["tenant_id"] != tenant:
                raise PermissionError("refusing to write a chunk for another tenant")
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{tenant}:{payload['path']}:{chunk.symbol}:{chunk.start_line}"))
            points.append(
                qmodels.PointStruct(
                    id=point_id,
                    vector=embed(chunk.text),
                    payload=payload,
                )
            )
        self.client.upsert(collection_name=self.collection, points=points)
        return len(points)

    def search(self, tenant_id: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search is impossible to call without a tenant filter. There is no unscoped method."""

        tenant = require_tenant(tenant_id)
        tenant_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="tenant_id",
                    match=qmodels.MatchValue(value=tenant),
                )
            ]
        )
        hits = self._query(embed(query), tenant_filter, limit)
        results = []
        for hit in hits:
            payload = hit.payload or {}
            if payload.get("tenant_id") != tenant:
                raise PermissionError("cross-tenant hit leaked from Qdrant")
            results.append(
                {
                    "path": payload.get("path"),
                    "symbol": payload.get("symbol"),
                    "score": float(hit.score or 0),
                    "start_line": payload.get("start_line"),
                    "parser": payload.get("parser"),
                    "tenant_id": tenant,
                    "excerpt": (payload.get("text") or "")[:400],
                }
            )
        return results

    def catalog(self, tenant_id: str, limit: int = 200) -> list[dict[str, Any]]:
        """List indexed symbols for one tenant. The scroll filter is mandatory."""

        tenant = require_tenant(tenant_id)
        tenant_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="tenant_id",
                    match=qmodels.MatchValue(value=tenant),
                )
            ]
        )
        scrolled = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=tenant_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        records = scrolled[0] if isinstance(scrolled, tuple) else scrolled.points
        rows = []
        for point in records:
            payload = point.payload or {}
            if payload.get("tenant_id") != tenant:
                raise PermissionError("cross-tenant catalog row leaked from Qdrant")
            rows.append(
                {
                    "path": payload.get("path"),
                    "symbol": payload.get("symbol"),
                    "language": payload.get("language"),
                    "parser": payload.get("parser"),
                    "start_line": payload.get("start_line"),
                    "tenant_id": tenant,
                }
            )
        rows.sort(key=lambda row: (row["path"] or "", row["start_line"] or 0))
        return rows

    def _query(self, vector: list[float], query_filter: qmodels.Filter, limit: int):
        if hasattr(self.client, "query_points"):
            response = self.client.query_points(
                collection_name=self.collection,
                query=vector,
                query_filter=query_filter,
                limit=limit,
            )
            return response.points
        return self.client.search(
            collection_name=self.collection,
            query_vector=vector,
            query_filter=query_filter,
            limit=limit,
        )

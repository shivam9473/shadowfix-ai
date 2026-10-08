"""Catalog used as a second AST document so retrieval has more than one file."""

from __future__ import annotations

PRODUCTS = [
    {"sku": "lamp", "name": "Desk lamp", "price": 1200},
    {"sku": "mug", "name": "Clay mug", "price": 450},
    {"sku": "notebook", "name": "Grid notebook", "price": 220},
]


def list_products() -> list[dict]:
    return list(PRODUCTS)

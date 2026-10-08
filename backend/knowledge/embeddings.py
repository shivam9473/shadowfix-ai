"""Deterministic local embeddings so AST search works without an API key."""

from __future__ import annotations

import hashlib
import math
import re

DIM = 384
_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,}")


def embed(text: str, dim: int = DIM) -> list[float]:
    vector = [0.0] * dim
    tokens = _TOKEN.findall((text or "").lower()) or ["empty"]
    for token in tokens:
        digest = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]

"""Embedder seam for the RAG index (SPEC.md §6.5, §15.5).

Phase 0 provides the `Embedder` protocol and `FakeEmbedder`. The fastembed-backed
embedder and the index build/load logic are Phase 5 (Session C). `FakeEmbedder`
is selected under LLM_FAKE=1 so CI never downloads a model.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from .. import config

FAKE_DIM = 256
_TOKEN = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FakeEmbedder:
    """Hashed bag-of-words into a fixed-size L2-normalised vector. Deterministic, offline."""

    dim = FAKE_DIM

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in _TOKEN.findall(text.lower()):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm else vec


class FastEmbedEmbedder:
    """Real embedder. Implemented in Phase 5; raises until then."""

    dim = 384

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("FastEmbedEmbedder lands in Phase 5 (rag/index.py)")


_instance: Embedder | None = None


def get_embedder() -> Embedder:
    global _instance
    if _instance is None:
        _instance = FakeEmbedder() if config.LLM_FAKE else FastEmbedEmbedder()
    return _instance


def index_chunk_count() -> int:
    """Number of chunks in the loaded index. 0 until Phase 5 builds one."""
    return 0

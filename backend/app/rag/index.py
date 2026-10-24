"""Embedders and the vector index (SPEC.md §6.5, §15.5).

`get_embedder()` returns `FakeEmbedder` under LLM_FAKE=1 (offline, deterministic,
used by CI) and `FastEmbedEmbedder` otherwise. `get_index()` loads
backend/rag/index.npz + index_meta.json when they match the current corpus and
embedder, and otherwise builds the index in memory (and saves it when the
embedder is the real one).
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Protocol

import numpy as np

from .. import config
from .ingest import Chunk, corpus_hash, load_corpus
from .text import content_terms

log = logging.getLogger(__name__)

FAKE_DIM = 256
FASTEMBED_MODEL = "BAAI/bge-small-en-v1.5"  # fastembed's default; 384-dim

INDEX_FILE = "index.npz"
META_FILE = "index_meta.json"


class Embedder(Protocol):
    name: str
    dim: int
    min_score: float  # cosine threshold below which a hit is not a source

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed passages (corpus chunks)."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed one search query."""
        ...


class FakeEmbedder:
    """Hashed bag of stemmed content words into a fixed-size L2-normalised vector.

    Deterministic and offline. Stopwords are dropped so question filler like
    "what does ... mean" doesn't dominate the similarity.
    """

    name = "fake-bow-256"
    dim = FAKE_DIM
    min_score = 0.2

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._one(text)

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in content_terms(text):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm else vec


class FastEmbedEmbedder:
    """fastembed ONNX embedder (CPU). The model downloads on first use (~70 MB)."""

    name = f"fastembed:{FASTEMBED_MODEL}"
    dim = 384
    # SPEC §6.5 starting point; bge-small relevant hits are typically 0.6+.
    min_score = 0.45

    def __init__(self, model_name: str = FASTEMBED_MODEL) -> None:
        from fastembed import TextEmbedding  # lazy: CI never imports the model

        self._model = TextEmbedding(model_name=model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.passage_embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return next(iter(self._model.query_embed(text))).tolist()


_embedder: Embedder | None = None
_embedder_lock = threading.Lock()


def get_embedder() -> Embedder:
    global _embedder
    with _embedder_lock:
        if _embedder is None:
            if config.LLM_FAKE:
                _embedder = FakeEmbedder()
            else:
                try:
                    _embedder = FastEmbedEmbedder()
                except Exception:
                    # No cached model and no network: degrade to lexical retrieval
                    # rather than break /rag/ask on stage.
                    log.exception("rag: fastembed unavailable; falling back to FakeEmbedder")
                    _embedder = FakeEmbedder()
        return _embedder


def _normalise(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


class Index:
    def __init__(self, chunks: list[Chunk], vectors: np.ndarray, embedder: Embedder, corpus: str) -> None:
        self.chunks = chunks
        self.vectors = _normalise(np.asarray(vectors, dtype=np.float32).reshape(len(chunks), -1))
        self.embedder = embedder
        self.corpus_hash = corpus
        self.by_id = {c.id: c for c in chunks}

    def __len__(self) -> int:
        return len(self.chunks)

    def scores(self, query: str) -> np.ndarray:
        if not self.chunks:
            return np.zeros(0, dtype=np.float32)
        q = np.asarray(self.embedder.embed_query(query), dtype=np.float32)
        n = np.linalg.norm(q)
        if n == 0:
            return np.zeros(len(self.chunks), dtype=np.float32)
        return self.vectors @ (q / n)

    # -- persistence ---------------------------------------------------------

    def save(self, rag_dir: Path) -> None:
        rag_dir.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(rag_dir / INDEX_FILE, vectors=self.vectors)
        meta = {
            "embedder": self.embedder.name,
            "corpus_hash": self.corpus_hash,
            "chunks": [asdict(c) for c in self.chunks],
        }
        (rag_dir / META_FILE).write_text(json.dumps(meta, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, rag_dir: Path, embedder: Embedder, expect_hash: str) -> "Index | None":
        meta_path, vec_path = rag_dir / META_FILE, rag_dir / INDEX_FILE
        if not (meta_path.is_file() and vec_path.is_file()):
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("embedder") != embedder.name or meta.get("corpus_hash") != expect_hash:
                return None
            chunks = [Chunk(**c) for c in meta["chunks"]]
            vectors = np.load(vec_path)["vectors"]
            return cls(chunks, vectors, embedder, expect_hash)
        except Exception:  # corrupt or old-format file: rebuild
            log.exception("rag: could not load saved index; rebuilding")
            return None


def build_index(embedder: Embedder | None = None, corpus_dir: Path | None = None) -> Index:
    embedder = embedder or get_embedder()
    chunks = load_corpus(corpus_dir)
    vectors = embedder.embed([c.embed_text() for c in chunks]) if chunks else []
    return Index(chunks, np.asarray(vectors, dtype=np.float32), embedder, corpus_hash(corpus_dir))


_index: Index | None = None
_index_lock = threading.Lock()


def get_index() -> Index:
    """Load the saved index if it matches the corpus + embedder, else build it."""
    global _index
    with _index_lock:
        if _index is None:
            embedder = get_embedder()
            expect = corpus_hash()
            idx = Index.load(config.RAG_DIR, embedder, expect)
            if idx is None:
                log.info("rag: building index with %s", embedder.name)
                idx = build_index(embedder)
                if not isinstance(embedder, FakeEmbedder):
                    try:
                        idx.save(config.RAG_DIR)
                    except OSError:
                        log.warning("rag: could not save index to %s", config.RAG_DIR)
            _index = idx
        return _index


def warm_in_background() -> None:
    """Start loading the index (and model) off the request path."""
    threading.Thread(target=_safe_warm, name="rag-warm", daemon=True).start()


def _safe_warm() -> None:
    try:
        get_index()
    except Exception:
        log.exception("rag: index warm-up failed")


def reset() -> None:
    """Tests only: drop cached embedder and index."""
    global _index, _embedder
    with _index_lock, _embedder_lock:
        _index = None
        _embedder = None


def index_chunk_count() -> int:
    """Chunks in the loaded index; 0 while it is still loading (/api/health)."""
    if _index is not None:
        return len(_index)
    if config.LLM_FAKE:  # cheap to build; keeps health accurate in tests
        return len(get_index())
    return 0

"""Top-k retrieval, the "is this actually sourced" check, and Citation objects.

Public API (other sessions use these; keep the signatures):
  retrieve(query, k=6, module=None, tags=None, min_score=None) -> list[Hit]
  citation_for(chunk_id) -> Citation | None
  get_chunk(chunk_id) -> Chunk | None
  to_citation(chunk) -> Citation
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from ..models import Citation
from .index import Index, get_index
from .ingest import Chunk
from .text import content_terms

DEFAULT_K = 6
EXCERPT_CHARS = 240

# Which corpus tags each decision module may draw on. A module that isn't listed
# searches the whole corpus.
MODULE_TAGS: dict[str, set[str]] = {
    "auto_insurance": {"auto_insurance", "general"},
    "rent": {"rent", "general"},
}


@dataclass
class Hit:
    chunk: Chunk
    score: float


def retrieve(
    query: str,
    k: int = DEFAULT_K,
    module: str | None = None,
    tags: set[str] | list[str] | None = None,
    min_score: float | None = None,
) -> list[Hit]:
    """Cosine top-k above the embedder's threshold, filtered by module/tags."""
    index = get_index()
    if not len(index) or not query.strip():
        return []
    allowed = set(tags) if tags else MODULE_TAGS.get(module or "", None)
    threshold = index.embedder.min_score if min_score is None else min_score
    scores = index.scores(query)
    hits: list[Hit] = []
    for i in scores.argsort()[::-1]:
        s = float(scores[i])
        if s < threshold:
            break
        chunk = index.chunks[i]
        if allowed and not allowed.intersection(chunk.tags):
            continue
        hits.append(Hit(chunk, s))
        if len(hits) >= k:
            break
    return hits


def get_chunk(chunk_id: str) -> Chunk | None:
    return get_index().by_id.get(chunk_id)


def _excerpt(text: str) -> str:
    if len(text) <= EXCERPT_CHARS:
        return text
    cut = text[: EXCERPT_CHARS - 1].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def to_citation(chunk: Chunk) -> Citation:
    return Citation(
        chunk_id=chunk.id,
        title=chunk.title,
        url=chunk.url,
        publisher=chunk.publisher,
        year=chunk.year,
        excerpt=_excerpt(chunk.text),
    )


def citation_for(chunk_id: str) -> Citation | None:
    chunk = get_chunk(chunk_id)
    return to_citation(chunk) if chunk else None


# -- term statistics (for the grounding check and extractive answers) ---------

_idf_cache: dict[int, tuple[dict[str, float], float]] = {}


def idf_table(index: Index | None = None) -> tuple[dict[str, float], float]:
    """(idf per stemmed term, idf for a term the corpus has never seen)."""
    index = index or get_index()
    key = id(index)
    if key not in _idf_cache:
        df: Counter[str] = Counter()
        for c in index.chunks:
            df.update(set(content_terms(c.embed_text())))
        n = max(len(index.chunks), 1)
        idf = {t: math.log((n + 1) / (d + 0.5)) for t, d in df.items()}
        _idf_cache.clear()
        # An unseen term weighs as much as the rarest seen one: enough that a
        # missing topic word ("bicycle") sinks coverage, not so much that one
        # odd word in an otherwise answerable question does.
        _idf_cache[key] = (idf, max(idf.values(), default=1.0))
    return _idf_cache[key]


def term_weights(query: str) -> dict[str, float]:
    idf, unseen = idf_table()
    return {t: idf.get(t, unseen) for t in set(content_terms(query))}


def coverage(query: str, hits: list[Hit]) -> float:
    """Share of the question's topic (idf-weighted content terms) found in the hits.

    Similarity alone can't tell "insurance on a bicycle" from "insurance on a car";
    a key term the sources never mention ("bicycle") drags coverage down.
    """
    weights = term_weights(query)
    total = sum(weights.values())
    if not total or not hits:
        return 0.0
    present: set[str] = set()
    for h in hits:
        present.update(content_terms(h.chunk.embed_text()))
    return sum(w for t, w in weights.items() if t in present) / total

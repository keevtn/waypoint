"""Small text helpers shared by ingest, the fake embedder, and retrieval.

Deliberately dumb and dependency-free: lowercase word tokens, a stopword list,
and a light suffix-stripping stemmer. Good enough to make FakeEmbedder retrieval
sensible and to check whether a question's key terms appear in a source.
"""
from __future__ import annotations

import re

_WORD = re.compile(r"[a-z0-9]+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(])")

# Function words plus question/filler verbs that carry no topic.
STOPWORDS = frozenset(
    """
    a about above after again against all also am an and any are as at be because been
    before being below between both but by can could did do does doing done down during
    each either else ever few for from further get gets getting give go goes going got
    had has have having he her here hers him his how i if in into is it its itself just
    know let like make makes many may me might mine more most much must my myself need
    needs no nor not now of off often on once one only or other our ours out over own
    please really said same say says see shall she should so some such tell than that the
    their theirs them then there these they thing things this those through to too under
    until up us use used very want wants was way we well were what whats when where whether
    which while who whom whose why will with would yes yet you your yours yourself
    explain explains mean means meaning define definition happen happens happened work works
    pick picks choose choosing decide deciding big bigger small smaller large good bad best
    better right okay ok enough actually exactly basically generally typically usually
    """.split()
)

# Everyday words mapped onto the vocabulary the sources use.
SYNONYMS = {
    "crash": "accident", "crashes": "accident", "wreck": "accident", "collide": "accident",
    "auto": "car", "automobile": "car", "vehicle": "car", "vehicles": "car",
    "cheap": "premium", "cheaper": "premium", "price": "premium", "prices": "premium",
}


def words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def stem(word: str) -> str:
    """Crude stemmer: strip a common suffix, then cap length so variants collide."""
    for suf in ("ing", "ed", "s", "ly"):
        if word.endswith(suf) and len(word) - len(suf) >= 4:
            word = word[: -len(suf)]
            break
    if word.endswith("e") and len(word) > 4:
        word = word[:-1]
    return word[:6]


def content_terms(text: str) -> list[str]:
    """Stemmed non-stopword tokens, in order, duplicates kept."""
    return [stem(SYNONYMS.get(w, w)) for w in words(text) if w not in STOPWORDS]


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text.strip()) if s.strip()]

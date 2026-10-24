"""corpus/<module>/<slug>.md -> chunks (SPEC.md §6.5).

Each file has YAML-style frontmatter (title, url, publisher, year, tags, ...).
Chunking is heading-first: every `##` section becomes one chunk, and only a
section longer than MAX_WORDS is split further on paragraphs with overlap.
That keeps chunk ids stable (`<slug>#<n>`, n counted from 0 in file order) so
decision-module constraints can cite them; see rag/facts.py.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from .. import config

# ~350 tokens / ~60 token overlap at roughly 1.3 tokens per word.
MAX_WORDS = 270
OVERLAP_WORDS = 45

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass
class Chunk:
    id: str
    slug: str
    module: str  # corpus subdirectory
    title: str
    url: str
    publisher: str
    year: int | None
    tags: list[str]
    section: str
    text: str  # chunk body, without the heading
    meta: dict = field(default_factory=dict)

    def embed_text(self) -> str:
        """What gets embedded: title and section give the body its context."""
        return f"{self.title}. {self.section}. {self.text}"


def parse_frontmatter(raw: str) -> tuple[dict, str]:
    """Minimal frontmatter parser: `key: value` and `key: [a, b]`. No nesting."""
    if not raw.startswith("---"):
        return {}, raw
    end = raw.find("\n---", 3)
    if end == -1:
        return {}, raw
    head, body = raw[3:end], raw[end + 4 :]
    meta: dict = {}
    for line in head.strip().splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            meta[key.strip()] = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
        else:
            meta[key.strip()] = val.strip("'\"")
    return meta, body.lstrip("\n")


def _sections(body: str) -> list[tuple[str, str]]:
    """Split markdown into (heading, text) pairs. Text before any heading gets ''."""
    out: list[tuple[str, list[str]]] = [("", [])]
    for line in body.splitlines():
        m = _HEADING.match(line)
        if m:
            out.append((m.group(2).strip(), []))
        else:
            out[-1][1].append(line)
    return [(h, "\n".join(lines).strip()) for h, lines in out]


def _split_long(text: str) -> list[str]:
    """Pack paragraphs into <= MAX_WORDS pieces, carrying OVERLAP_WORDS of overlap."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    pieces: list[str] = []
    cur: list[str] = []
    for para in paras:
        pw = para.split()
        if cur and len(cur) + len(pw) > MAX_WORDS:
            pieces.append(" ".join(cur))
            cur = cur[-OVERLAP_WORDS:]
        cur.extend(pw)
        while len(cur) > MAX_WORDS:  # a single huge paragraph
            pieces.append(" ".join(cur[:MAX_WORDS]))
            cur = cur[MAX_WORDS - OVERLAP_WORDS :]
    if cur:
        pieces.append(" ".join(cur))
    return pieces


def chunk_file(path: Path, corpus_dir: Path) -> list[Chunk]:
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    slug = path.stem
    module = path.parent.relative_to(corpus_dir).parts[0] if path.parent != corpus_dir else ""
    title = meta.get("title", slug)
    year_raw = str(meta.get("year", "")).strip()
    year = int(year_raw) if year_raw.isdigit() else None
    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]

    chunks: list[Chunk] = []
    for heading, text in _sections(body):
        if not text:
            continue  # e.g. the H1 title line
        section = heading or title
        pieces = [text] if len(text.split()) <= MAX_WORDS else _split_long(text)
        for piece in pieces:
            chunks.append(
                Chunk(
                    id=f"{slug}#{len(chunks)}",
                    slug=slug,
                    module=module,
                    title=title,
                    url=meta.get("url", ""),
                    publisher=meta.get("publisher", ""),
                    year=year,
                    tags=list(tags),
                    section=section,
                    text=" ".join(piece.split()),
                    meta=meta,
                )
            )
    return chunks


def corpus_files(corpus_dir: Path | None = None) -> list[Path]:
    corpus_dir = corpus_dir or config.CORPUS_DIR
    return sorted(p for p in corpus_dir.rglob("*.md") if p.is_file())


def load_corpus(corpus_dir: Path | None = None) -> list[Chunk]:
    corpus_dir = corpus_dir or config.CORPUS_DIR
    chunks: list[Chunk] = []
    for path in corpus_files(corpus_dir):
        chunks.extend(chunk_file(path, corpus_dir))
    return chunks


def corpus_hash(corpus_dir: Path | None = None) -> str:
    """Content hash of the corpus, so a stale index is detected and rebuilt."""
    corpus_dir = corpus_dir or config.CORPUS_DIR
    h = hashlib.sha256()
    for path in corpus_files(corpus_dir):
        h.update(str(path.relative_to(corpus_dir)).replace("\\", "/").encode())
        h.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:16]

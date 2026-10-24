"""Build backend/rag/index.npz + index_meta.json from backend/corpus/ (SPEC.md §6.5).

    python scripts/build_index.py          # real fastembed model (downloads ~70 MB once)
    python scripts/build_index.py --fake   # offline FakeEmbedder; prints chunks, writes nothing

The app also builds the index at startup if the saved one is missing or stale
(corpus hash or embedder changed), so running this is an optimisation for deploys.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fake", action="store_true", help="use FakeEmbedder and don't write files")
    ap.add_argument("-v", "--verbose", action="store_true", help="list every chunk id")
    args = ap.parse_args()

    from app import config
    from app.rag.index import FakeEmbedder, FastEmbedEmbedder, build_index

    t0 = time.time()
    embedder = FakeEmbedder() if args.fake else FastEmbedEmbedder()
    idx = build_index(embedder)
    files = len({c.slug for c in idx.chunks})
    print(f"{len(idx)} chunks from {files} files, embedder={embedder.name}, "
          f"corpus={idx.corpus_hash}, {time.time() - t0:.1f}s")
    if args.verbose or args.fake:
        for c in idx.chunks:
            print(f"  {c.id:36} {len(c.text.split()):4}w  {c.section}")
    if not args.fake:
        idx.save(config.RAG_DIR)
        print(f"wrote {config.RAG_DIR / 'index.npz'} and index_meta.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

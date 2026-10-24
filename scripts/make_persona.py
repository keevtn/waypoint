"""Regenerate backend/data/persona_student.json and backend/data/plaid_custom_user.json
from the SPEC.md §8 definition in backend/app/bank/persona.py (dates relative to today).

Usage: python scripts/make_persona.py [--as-of YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.bank import persona  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", type=date.fromisoformat, default=None)
    args = ap.parse_args()

    out = ROOT / "backend" / "data"
    out.mkdir(parents=True, exist_ok=True)
    doc = persona.generate(args.as_of)
    (out / "persona_student.json").write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    plaid = persona.to_plaid_custom_user(doc)
    (out / "plaid_custom_user.json").write_text(json.dumps(plaid, indent=1) + "\n", encoding="utf-8")
    print(f"as_of={doc['as_of']} transactions={len(doc['transactions'])} -> {out}")


if __name__ == "__main__":
    main()

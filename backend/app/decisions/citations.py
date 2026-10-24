"""Corpus chunk ids referenced by decision-module constraints (SPEC.md §3.3, §6.4).

One place to rewire when Session C's index assigns final chunk ids (SPEC §10
row 5: "Constraints in Phase 3 wired to real chunk ids"). Ids follow the
`<doc-slug>#<chunk>` convention used by the fixtures. Every constraint must
carry at least one; the smoke test enforces it.
"""
from __future__ import annotations

LENDER_REQUIRES_COMP_COLL = ["cfpb-auto-loans#2"]
PA_MINIMUM_COVERAGE = ["pa-auto-insurance-guide#1"]
PA_LIMITED_TORT = ["pa-auto-insurance-guide#3"]
DEDUCTIBLE_TRADEOFF = ["naic-deductibles#1"]
LOW_VALUE_COLLISION = ["naic-deductibles#1", "pa-auto-insurance-guide#2"]

"""Corpus chunk ids referenced by decision-module constraints (SPEC.md §3.3, §6.4).

Imported from `app.rag.facts` (Session C), whose ids are test-checked against
the corpus so an edit can't silently break a citation. Every constraint must
carry at least one; the smoke test enforces it.
"""
from __future__ import annotations

from ..rag import facts

LENDER_REQUIRES_COMP_COLL = [facts.LENDER_REQUIRES_PHYSICAL_DAMAGE, facts.LENDER_REQUIREMENT_ALT]
PA_MINIMUM_COVERAGE = [facts.PA_MIN_COVERAGE, facts.PA_LAPSE_SUSPENSION]
PA_LIMITED_TORT = [facts.PA_TORT]
DEDUCTIBLE_TRADEOFF = [facts.DEDUCTIBLE_AFFORDABLE, facts.DEDUCTIBLE_TRADEOFF]
LOW_VALUE_COLLISION = [facts.DEDUCTIBLE_TRADEOFF, facts.LENDER_REQUIREMENT_ALT]

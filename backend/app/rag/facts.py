"""Chunk ids for the facts decision modules cite (SPEC.md §6.4, §8).

Decision modules should cite these constants instead of hard-coding ids.
tests/test_rag.py checks that each id exists and still contains its fact, so
editing the corpus can't silently break a constraint's citation.
"""
from __future__ import annotations

# PA required coverages and minimum limits: $5,000 medical (first party) benefits,
# $15,000/$30,000 bodily injury liability, $5,000 property damage liability.
PA_MIN_COVERAGE = "pa-auto-insurance-guide#0"
PA_MIN_COVERAGE_ALT = "penndot-insurance-law#0"  # PennDOT's statement of the same minimums

# Limited vs full tort: limited is cheaper but gives up pain-and-suffering claims
# unless an exception applies; full tort is the default if you don't elect limited.
PA_TORT = "pa-auto-insurance-guide#1"

# Lender requirement: auto finance contracts generally require comprehensive and
# collision on a financed car; state minimum liability alone doesn't satisfy it.
LENDER_REQUIRES_PHYSICAL_DAMAGE = "cfpb-auto-loan-insurance#0"
LENDER_REQUIREMENT_ALT = "naic-consumer-auto-guide#1"  # not required by law, lenders may require

# Force-placed insurance if coverage lapses on a financed car.
FORCE_PLACED = "cfpb-auto-loan-insurance#2"

# Deductibles: higher deductible means lower premium; pick one you can afford.
DEDUCTIBLE_TRADEOFF = "naic-deductibles#1"
DEDUCTIBLE_AFFORDABLE = "naic-deductibles#2"

# Shopping: at least three quotes, identical coverage; independent vs captive agents.
GET_THREE_QUOTES = "naic-shopping-agents#0"
INDEPENDENT_AGENT = "naic-shopping-agents#2"

# Registration consequences of an insurance lapse (registration deadline context).
PA_LAPSE_SUSPENSION = "penndot-insurance-law#2"

# GAP insurance is generally optional.
GAP_OPTIONAL = "cfpb-gap-insurance#1"

# General / rent module.
EMERGENCY_FUND = "cfpb-emergency-fund#1"
RENT_30_PERCENT = "hud-housing-affordability#0"

# id -> phrase the chunk must contain (verified by tests).
EXPECTED_TEXT = {
    PA_MIN_COVERAGE: "$15,000/$30,000",
    PA_MIN_COVERAGE_ALT: "$5,000 for damage to property",
    PA_TORT: "Limited tort",
    LENDER_REQUIRES_PHYSICAL_DAMAGE: "require you to maintain comprehensive and collision",
    LENDER_REQUIREMENT_ALT: "lenders may require them",
    FORCE_PLACED: "force-placed",
    DEDUCTIBLE_TRADEOFF: "Higher policy deductibles mean lower policy premiums",
    DEDUCTIBLE_AFFORDABLE: "be sure you can afford the deductible",
    GET_THREE_QUOTES: "at least three",
    INDEPENDENT_AGENT: "independent agent",
    PA_LAPSE_SUSPENSION: "three-month suspension",
    GAP_OPTIONAL: "cannot be required",
    EMERGENCY_FUND: "$500",
    RENT_30_PERCENT: "30 percent",
}

"""Deliberate exclusions from playable PES historical league databases.

Raw original FIFA/FC archives stay immutable for auditing. Excluded original
league affiliations are not imported as playable clubs, season participants,
external promotion feeders, competitions, or manager career options.
"""
from __future__ import annotations

EXCLUDED_LEAGUE_SOURCE_LABELS=frozenset({"ISL", "Indian Super League"})
EXCLUDED_LEAGUE_COUNTRIES=frozenset({"India"})
EXCLUDED_DOMESTIC_CODES=frozenset({"in.1", "2027:in.1"})

def excluded_source_league(label):
    return str(label or "").strip().casefold() in {
        val.casefold() for val in EXCLUDED_LEAGUE_SOURCE_LABELS
    }

def excluded_competition(*, label="", country="", code=""):
    """Do not exclude similarly named clubs from unrelated real leagues."""
    code=str(code or "").strip().casefold()
    if excluded_source_league(label):
        return True
    if code in {c.casefold() for c in EXCLUDED_DOMESTIC_CODES}:
        return True
    return False

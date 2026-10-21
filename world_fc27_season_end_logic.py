"""Pure season-end rule resolver for FC27 game, with no fictional club promotion.

This is a validated prototype, not an active career mutation. Inputs are
already ranked club IDs from real/eligible registered squads with known
season results; every selected playoff winner is an explicit supplied result.
No guessed winners, new player data, empty rosters, or random league movements.
Only game-open pyramids can call the promotion resolver. MLS instead has a
separate 15/15 conference playoff qualification routine.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence

@dataclass(frozen=True)
class BoundaryRules:
    lower_code:str
    upper_code:str
    automatic_promotions:int
    lower_playoff_promotions:int
    upper_automatic_relegations:int
    interdivision_playoff_places:int=0
    name:str=""

@dataclass(frozen=True)
class BoundaryOutcome:
    promoted:tuple[str,...]
    relegated:tuple[str,...]
    played_conditional_exchange:bool
    lower_after:tuple[str,...]
    upper_after:tuple[str,...]

def _validate_ranks(ranks:Sequence[str], expected_size:int|None, label:str):
    if not ranks or any(not isinstance(s,str) or not s.strip() for s in ranks):
        raise ValueError(f"{label}: missing real club IDs or empty standings")
    if len(set(ranks))!=len(ranks):
        raise ValueError(f"{label}: duplicate club IDs")
    if expected_size is not None and len(ranks)!=expected_size:
        raise ValueError(f"{label}: incomplete original league standings")

def resolve_boundary(
    rule:BoundaryRules,
    *, upper_ranked:Sequence[str],lower_ranked:Sequence[str],
    eligible_lower_clubs:frozenset[str],
    eligible_upper_clubs:frozenset[str],
    playoff_promoted:Sequence[str]=(),
    interdivision_winner:str|None=None,
    certified_game_rosters:bool=False,
    actual_season_standings:bool=False,
    upper_expected_club_count:int|None=None,
    lower_expected_club_count:int|None=None,
)->BoundaryOutcome:
    """Return movement *candidates* only; never mutate career records.

    Lower/upper are in standings order highest -> lowest. All promotion
    clubs must be explicitly registered eligible senior clubs with
    certified playing squads. An interdivision winner is selected by
    recorded sporting result, not projected ranking or randomness.
    """
    if not certified_game_rosters or not actual_season_standings:
        raise ValueError("Promotion blocked: registered squads or actual season standings not certified")
    if rule.lower_code==rule.upper_code or not (rule.lower_code.startswith("2027:") and
        rule.upper_code.startswith("2027:")):
        raise ValueError("Only adjacent, distinct FC27 national league boundaries supported")
    counts=(rule.automatic_promotions,rule.lower_playoff_promotions,
            rule.upper_automatic_relegations,rule.interdivision_playoff_places)
    if any(type(x) is not int or x<0 for x in counts) or counts[-1]>1:
        raise ValueError("Unsupported or invalid rule counts")
    if (counts[0]+counts[1]!=counts[2] or
        (counts[0]+counts[1]==0 and counts[3]==0)):
        raise ValueError("Regular promotion and relegation places are unbalanced")
    upper=list(upper_ranked);lower=list(lower_ranked)
    _validate_ranks(upper,upper_expected_club_count,"top division")
    _validate_ranks(lower,lower_expected_club_count,"lower division")
    if set(upper)&set(lower):
        raise ValueError("One game club registered in two different divisions")
    if not set(upper).issubset(eligible_upper_clubs):
        raise ValueError("Top-division real registered senior club eligibility missing")
    direct=list(lower[:counts[0]])
    playoffs=list(playoff_promoted)
    if len(playoffs)!=counts[1] or len(set(playoffs))!=len(playoffs):
        raise ValueError("Explicit result needed for every lower-division play-off promotion")
    if any(p not in lower or p in direct for p in playoffs):
        raise ValueError("Play-off promotion winner not an eligible non-automatic lower club")
    if not set(direct+playoffs).issubset(eligible_lower_clubs):
        raise ValueError("Promotion blocked for ineligible/reserve/unregistered clubs")
    drops=list(upper[-counts[2]:]) if counts[2] else []
    if rule.interdivision_playoff_places:
        if interdivision_winner is None:
            raise ValueError("Recorded interdivision play-off winner required")
        additional_lower=[x for x in lower if x not in direct+playoffs
                          and x in eligible_lower_clubs]
        if not additional_lower:
            raise ValueError("No eligible lower-division tie challenger has a playable squad")
        challenging_lower=additional_lower[0]
        challenging_upper=upper[-counts[2]-1]
        if interdivision_winner not in (challenging_lower,challenging_upper):
            raise ValueError("Interdivision winner must be one of the two actual challengers")
        if interdivision_winner==challenging_lower:
            direct.append(challenging_lower)
            drops.append(challenging_upper)
    elif interdivision_winner is not None:
        raise ValueError("Result provided for a non-existent interdivision playoff")
    promoted=tuple(direct+playoffs)
    relegated=tuple(drops)
    if len(promoted)!=len(relegated):
        raise ValueError("Unbalanced club exchange")
    new_upper=tuple([x for x in upper if x not in relegated]+list(promoted))
    new_lower=tuple([x for x in lower if x not in promoted]+list(relegated))
    if len(new_upper)!=len(upper) or len(new_lower)!=len(lower):
        raise ValueError("Cannot change division size without explicit regulation")
    return BoundaryOutcome(promoted,relegated,
        bool(rule.interdivision_playoff_places and
             interdivision_winner in promoted),new_lower,new_upper)

@dataclass(frozen=True)
class MLSQualifiers:
    eastern_direct:tuple[str,...]
    western_direct:tuple[str,...]
    eastern_wild_card:tuple[str,str]
    western_wild_card:tuple[str,str]

def mls_postseason_qualifiers(
    eastern_ranked:Sequence[str],western_ranked:Sequence[str],
    *,season_match_results_certified:bool=False,
)->MLSQualifiers:
    """2026 MLS seeds 1-7 directly, seeds 8-9 to each conference wildcard.

    The 2026 34-game regular season and MLS Cup winner require real game
    results. This function does not invent wildcard or knockout winners.
    """
    if not season_match_results_certified:
        raise ValueError("MLS playoff seeds blocked until season standings are certified")
    _validate_ranks(eastern_ranked,15,"MLS Eastern Conference")
    _validate_ranks(western_ranked,15,"MLS Western Conference")
    if set(eastern_ranked)&set(western_ranked):
        raise ValueError("MLS team cannot play in both conferences")
    return MLSQualifiers(tuple(eastern_ranked[:7]),tuple(western_ranked[:7]),
                         tuple(eastern_ranked[7:9]),tuple(western_ranked[7:9]))

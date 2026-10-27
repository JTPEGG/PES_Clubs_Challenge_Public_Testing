"""Dry-run multi-region feeder -> one upper league season-end decisions (FC27).

Inputs must be season-actual ranked ID arrays for all sourced groups and
explicit qualifying playoff winners. No application to live careers here.
No original FC27 source clubs or fictitious new squads are created.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Mapping,Sequence

COUNTRY_FORMATS={
 "Spain":{
  "upper":"2027:es.2","lower":"2027:es.3",
  "groups":{"1":20,"2":20},
  "automatic":("1","2"),
  "playoff_pool":("1","2"),
  "playoff_places":2,
 },
 "Germany":{
  "upper":"2027:de.3","lower":"2027:de.4",
  "groups":{"Nord":18,"Nordost":18,"West":18,"Südwest":18,"Bayern":19},
  "automatic":("West","Südwest","Nordost"),
  "playoff_pool":("Nord","Bayern"),
  "playoff_places":1,
 }
}
@dataclass(frozen=True)
class RegionalMovementCandidates:
 country:str
 lower_code:str
 upper_code:str
 promoted:tuple[str,...]
 relegated:tuple[str,...]
 upper_after:tuple[str,...]
 regional_destination_allocations_certified:bool=False

def resolve_regional_movement(
    country:str, *,
    region_ranked:Mapping[str,Sequence[str]],
    upper_ranked:Sequence[str],
    verified_eligible_game_club_ids:frozenset[str],
    certified_game_roster_club_ids:frozenset[str],
    recorded_playoff_winners:Sequence[str],
    actual_final_tables_certified:bool=False,
    expected_upper_team_count:int|None=None,
)->RegionalMovementCandidates:
    if not actual_final_tables_certified:
        raise ValueError("Official in-game final standings not yet certified")
    rule=COUNTRY_FORMATS.get(country)
    if not rule:
        raise ValueError("Only sourced regional Spain or Germany one-level feeder supported")
    if set(region_ranked)!=set(rule["groups"]):
        raise ValueError("All real regional subleague standings required")
    clubs={}
    for group,expected in rule["groups"].items():
        ranked=tuple(region_ranked[group])
        if len(ranked)!=expected or len(set(ranked))!=expected or any(
              not isinstance(x,str) or not x.strip() for x in ranked):
            raise ValueError("Missing or duplicate original regional standing club identities")
        clubs[group]=ranked
    everything=[c for group in clubs.values() for c in group]
    upper=tuple(upper_ranked)
    if (not upper or (expected_upper_team_count is not None and
         len(upper)!=expected_upper_team_count) or
        len(set(upper))!=len(upper) or len(set(everything))!=len(everything) or
        set(upper)&set(everything)):
        raise ValueError("Duplicate clubs, invalid upper table, or mixed regional club identity")
    if any(not isinstance(x,str) or not x.strip() for x in upper):
        raise ValueError("No anonymous clubs accepted")
    if not set(upper).issubset(certified_game_roster_club_ids):
        raise ValueError("Upper division real squads unverified")
    qualifying=verified_eligible_game_club_ids&certified_game_roster_club_ids
    def champion(group):
        eligible=[c for c in clubs[group] if c in qualifying]
        if not eligible:
            raise ValueError("No real eligible registered game squad for region champion")
        return eligible[0]
    automatic=[champion(g) for g in rule["automatic"]]
    winners=tuple(recorded_playoff_winners)
    if len(winners)!=rule["playoff_places"] or len(set(winners))!=len(winners):
        raise ValueError("Recorded two Spanish or one German regional playoff winners required")
    if country=="Germany":
        contenders={champion(g) for g in rule["playoff_pool"]}
        if not set(winners).issubset(contenders):
            raise ValueError("German fourth promotion must win the actual North/Bavaria champions' playoff")
    else:
        eligible_second_to_fifth=set()
        for group,ranked in clubs.items():
            # The game bracket comprises 2nd–5th place per regional group,
            # but skip the champion and exempt second teams from eligibility.
            bracket=[x for x in ranked if x in qualifying and x!=champion(group)][:4]
            if len(bracket)!=4:
                raise ValueError("Insufficient eligible Spanish 2nd–5th game playoff field")
            eligible_second_to_fifth.update(bracket)
        if not set(winners).issubset(eligible_second_to_fifth):
            raise ValueError("Spanish playoff winner not in the eligible recorded regional bracket")
    promoted=tuple(automatic)+winners
    if len(set(promoted))!=4 or not set(promoted).issubset(qualifying):
        raise ValueError("Four distinct game-registered senior promotion clubs required")
    relegated=upper[-4:]
    # Exact regional destination of relegated teams must be based on real
    # club geography / registered sporting affiliation; not guessed here.
    upper_after=tuple(x for x in upper if x not in relegated)+promoted
    if len(upper_after)!=len(upper):
        raise ValueError("Upper division size changed")
    return RegionalMovementCandidates(
        country,rule["lower"],rule["upper"],promoted,relegated,upper_after,False
    )

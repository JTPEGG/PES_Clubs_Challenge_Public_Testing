"""FC27 autonomous club priorities from copied, provenance-labelled game models.

The approved 659-club warehouse is immutable. Career decisions read a separate
snapshot. Missing profiles on older careers fall back to squad-only reasoning;
no anonymous simulated coach is misrepresented as a real manager.
"""
from __future__ import annotations

from world_squad_planner import MIN_COVER, STARTERS, effective_cover

VERSION="fc27-recruitment-priority-v1"

def read_fc27_profiles(conn, *, dataset):
    """Read independently copied FC27 game model profiles, never live source."""
    exists=conn.execute("""SELECT 1 FROM sqlite_master
        WHERE type='table' AND name='world_fc27_club_ai_context'""").fetchone()
    if not exists:
        return {}
    rows=conn.execute("""SELECT club_id,sporting_appeal,ambition_level,
        pressure_to_improve,operating_approach,financial_pressure_band,
        financial_pressure_index,simulated_manager_risk,
        simulated_manager_financial_discipline,source_note
        FROM world_fc27_club_ai_context WHERE dataset_id=?""",
        (dataset,)).fetchall()
    names=("club_id","sporting_appeal","ambition_level",
      "pressure_to_improve","operating_approach","financial_pressure_band",
      "financial_pressure_index","simulated_manager_risk",
      "simulated_manager_financial_discipline","source_note")
    return {row[0]:dict(zip(names,row)) for row in rows}

def modelled_seller_finances(profile):
    """Translate labelled *game* pressure, not unverified real cash balances."""
    if not profile:
        return "stable"
    band=profile["financial_pressure_band"]
    if band=="distress":
        return "distressed"
    if band=="over_committed":
        return "cash_needed"
    return "stable"

def modelled_financial_objective(profile):
    if not profile:
        return "balanced"
    band=profile["financial_pressure_band"]
    if band=="distress":
        return "cash_generation"
    if band in ("over_committed","tight"):
        return "cost_control"
    if profile["operating_approach"]=="high_ambition":
        return "growth"
    return "balanced"

def buyer_recruitment_priority(squads, *, club, departed_lanes=(),
                               profile=None, previous_signings=0,
                               stable_variation=0):
    """Relative chance of a club entering negotiations, never a transfer cap.

    Needs are positional and source-rated. A simulated manager's inclination,
    board ambition and model financial pressure alter *willingness to scout*;
    the independent seller/player/agent/budget rules still decide the deal.
    """
    if previous_signings<0 or not 0<=stable_variation<=25:
        raise ValueError("Invalid market priority inputs")
    roster=squads.get(club,{})
    rated=sorted((ovr for group in roster.values()
                  for _,ovr,_ in group),reverse=True)
    if not rated:
        return -100
    team_floor=rated[min(10,len(rated)-1)]
    shortage=0
    quality_gap=0
    urgent=0
    for lane in set(roster)|set(departed_lanes):
        covered=effective_cover(squads,club,lane)
        if not covered and lane not in departed_lanes:
            continue  # no verified formation requirement for a never-used role
        minimum=max(STARTERS[lane],MIN_COVER[lane])
        shortage+=min(2,max(0,minimum-len(covered)))
        if covered:
            starter=covered[min(STARTERS[lane]-1,len(covered)-1)][1]
            quality_gap+=min(7,max(0,team_floor-starter-3))
        if lane in departed_lanes:
            urgent+=max(0,minimum-len(covered))
    need_score=min(45,shortage*5+quality_gap*1.5+urgent*9)
    if profile:
        ambition=(profile["ambition_level"]-50)*.28
        pressure=(profile["pressure_to_improve"]-50)*.24
        coaching=(profile["simulated_manager_risk"]-50)*.12
        financial=profile["financial_pressure_index"]*.18
    else:
        ambition=pressure=coaching=financial=0
    # Marginal benefit diminishes with arrivals, but no purchase is forbidden.
    return round(need_score+ambition+pressure+coaching-financial
                 -previous_signings*5+stable_variation,2)

def domestic_market_preference(*,same_source_country,profile=None):
    """Soft scouting familiarity, not a restriction on international sales."""
    if same_source_country:
        return 9
    # Financial discipline moderates distant scouting, without a nationality
    # rule, a ban, a regional guess, or any claim about the real manager.
    discipline=profile["simulated_manager_financial_discipline"] if profile else 50
    return -round((discipline-50)/15,2)

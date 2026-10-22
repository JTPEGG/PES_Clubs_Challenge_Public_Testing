"""FC27 autonomous club priorities from copied, provenance-labelled game models.

The approved 659-club warehouse is immutable. Career decisions read a separate
snapshot. Missing profiles on older careers fall back to squad-only reasoning;
no anonymous simulated coach is misrepresented as a real manager.
"""
from __future__ import annotations

from world_squad_planner import MIN_COVER, STARTERS, FAMILY, effective_cover

VERSION="fc27-recruitment-priority-v4-tactical-market"

def read_fc27_profiles(conn, *, dataset, club_id=None):
    """Read independently copied FC27 game model profiles, never live source."""
    exists=conn.execute("""SELECT 1 FROM sqlite_master
        WHERE type='table' AND name='world_fc27_club_ai_context'""").fetchone()
    if not exists:
        return {}
    rows=conn.execute("""SELECT club_id,sporting_appeal,ambition_level,
        pressure_to_improve,operating_approach,financial_pressure_band,
        financial_pressure_index,simulated_manager_risk,
        simulated_manager_financial_discipline,source_note
        FROM world_fc27_club_ai_context WHERE dataset_id=?"""
        + (" AND club_id=?" if club_id is not None else ""),
        (dataset,club_id) if club_id is not None else (dataset,)).fetchall()
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
                               stable_variation=0,starting_roles=None):
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
    for lane in set(roster)|set(departed_lanes)|set(starting_roles or {}):
        required=(STARTERS[lane] if starting_roles is None
                  else starting_roles.get(lane,0))
        if not required:
            continue
        covered=effective_cover(squads,club,lane)
        if not covered and lane not in departed_lanes and starting_roles is None:
            continue  # no implied formation on older worlds
        minimum=(max(STARTERS[lane],MIN_COVER[lane])
                 if starting_roles is None else required+1)
        shortage+=min(2,max(0,minimum-len(covered)))
        if covered:
            starter=covered[min(required-1,len(covered)-1)][1]
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
    # Source-rated established clubs have a continuing incentive to refresh
    # their XI even when every specialist role is currently occupied. This
    # is their own ambition/competitive standard, not a club-name exception.
    # Lower-tier clubs still receive urgency from genuine missing cover.
    ambition_pressure=(profile["ambition_level"]+
                      profile["pressure_to_improve"])/2 if profile else 50
    competitive_refresh=(max(0,team_floor-72)*1.65
                         *max(0.4,min(1.2,ambition_pressure/82)))
    # Marginal benefit diminishes with arrivals, but no purchase is forbidden.
    return round(need_score+ambition+pressure+coaching-financial
                 +competitive_refresh
                 -previous_signings*5+stable_variation,2)

def scouting_desk_activation(*,priority,draw):
    """Per-moment decision to enter the market, never a club/deal quota.

    659 clubs cannot all conduct full-squad scouting every few seconds in
    one server tick. Each club's measured need and ambition determine how
    frequently its desk becomes active; deterministic drawing avoids
    reshuffling interest every time a page is reloaded. Every club remains
    eligible to scout at any moment.
    """
    if type(priority) not in (int,float) or type(draw) is not int or not 0<=draw<1000:
        raise ValueError("Invalid autonomous scouting interest")
    chance=max(12,min(90,round(24+max(-20,priority)*0.62)))
    return draw<chance


def expected_scouting_activity(priority):
    """Auditable share of market ticks for each independent buying desk."""
    if type(priority) not in (int,float):
        raise ValueError("Invalid club recruitment priority")
    return round(max(12,min(90,round(24+max(-20,priority)*0.62)))/1000,3)


def positional_family_priorities(squads, *, club, departed_lanes=(),
                                 starting_roles=None):
    """Sporting recruitment need by specialist lane, NOT arbitrary GK/ST ratios.

    Consider only actual rated squad roles and positions with an agreed
    departure. We do not infer a manager's formation from a FIFA primary
    position list, nor reward buying a third goalkeeper unnecessarily.
    Returns four continuous priorities, so any family can be considered.
    """
    roster=squads.get(club,{})
    rated=sorted((overall for members in roster.values()
                  for _pid,overall,_pos in members),reverse=True)
    if not rated:
        return {group:0.0 for group in ("GK","DEF","MID","FWD")}
    team_floor=rated[min(10,len(rated)-1)]
    by_family={group:[] for group in ("GK","DEF","MID","FWD")}
    for lane in set(roster)|set(departed_lanes)|set(starting_roles or {}):
        if lane not in FAMILY:
            continue
        required=(STARTERS[lane] if starting_roles is None
                  else starting_roles.get(lane,0))
        if not required:
            continue
        peers=effective_cover(squads,club,lane)
        if not peers and lane not in departed_lanes and starting_roles is None:
            continue
        group=FAMILY[lane]
        minimum=(max(STARTERS[lane],MIN_COVER[lane])
                 if starting_roles is None else required+1)
        depth_gap=max(0,minimum-len(peers))
        starter_floor=(peers[min(required-1,len(peers)-1)][1]
                       if peers else team_floor-12)
        quality_gap=max(0,team_floor-3-starter_floor)
        # A recently sold starter is a *reason to scout*, not proof
        # another club will sell or an obligation to complete a deal.
        urgency=11 if lane in departed_lanes else 0
        need=(min(3,depth_gap)*11 + min(12,quality_gap)*2.0 + urgency)
        by_family[group].append(need)
    # Strongest specialist shortage matters most, with weaker aggregate
    # contribution for additional issues within the same family.
    return {group:round(max(values,default=0)+
                        .25*sum(sorted(values,reverse=True)[1:]),2)
            for group,values in by_family.items()}


def candidate_sporting_priority(squads, *, club, position, overall,
                                fit, departed_lanes=(),starting_roles=None):
    """Score marginal sporting gain without a global positional trade ratio.

    A starting goalkeeper is a single-specialist job: buying another one
    when already sufficiently covered requires a materially better target
    to take priority over credible upgrades elsewhere. Goalkeeper moves
    remain possible at every sporting score; none is vetoed by this ranking.
    """
    from world_squad_planner import lane_of
    lane=lane_of(position)
    if lane is None or fit.get("eligible") is not True:
        return -100
    peers=effective_cover(squads,club,lane)
    starter_count=(STARTERS[lane] if starting_roles is None
                   else starting_roles.get(lane,0))
    if not starter_count:
        return -40  # role unused by this manager; not a present XI upgrade
    starter=(peers[min(starter_count-1,len(peers)-1)][1]
             if peers else None)
    shortage=len(peers)<(max(STARTERS[lane],MIN_COVER[lane])
                         if starting_roles is None else starter_count+1)
    gain=max(0,overall-starter) if starter is not None else 0
    agreed_exit=lane in departed_lanes
    # Priority for better starting XI and resolved vacancy. A lower-rated
    # long-term prospect cannot masquerade as a senior first-team upgrade.
    if fit.get("category")=="prospect":
        return -7
    gain_score=min(55,5.0*gain)
    depth_score=20 if shortage else 0
    departure_score=16 if agreed_exit else 0
    if lane=="GK" and not shortage and not agreed_exit:
        # Existing keeper quality/cover, not league-wide keeper transfers,
        # determines the relative urgency of another goalkeeper.
        gain_score-=max(0,20-min(20,gain*2.0))
    return round(gain_score+depth_score+departure_score,2)


def prospect_budget_penalty(*,fee,available_budget,opening_budget):
    """Soft opportunity-cost signal only; never a prospective purchase veto."""
    if any(type(v) is not int or v<0 for v in
           (fee,available_budget,opening_budget)):
        raise ValueError("Prospect budget inputs must be nonnegative integers")
    if available_budget==0 or opening_budget==0:
        return 0.0  # normal transfer affordability determines viability
    # Rising budget opportunity cost lowers priority but doesn't ban a deal.
    return round(min(30,12*fee/available_budget+
                     8*fee/opening_budget),2)



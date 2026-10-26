"""Three-season FC27 strategic decision context -- source evidence, no invented PA.

Read-only decision support for the autonomous 659-club game edition:
  1. immediate sporting cost
  2. present transaction / contract financial opportunity
  3. 1-3 season succession and asset-retention considerations

The current prospect_fit() scouting gate and explicit development category
remain authoritative. A future scenario is NOT an actual PES ability update,
a guaranteed player development, or a replacement already signed.
"""
from datetime import date

VERSION="fc27-three-season-club-strategy-v1"
DATASET="fc27-warehouse-659-mens-2026-27"


def source_ages(conn,*,dataset,player_ids):
    """Batch true date-of-birth evidence for an approved source season."""
    if dataset!=DATASET:
        raise ValueError("The long-term policy is FC27 only")
    ids=sorted(set(int(pid) for pid in player_ids))
    if not ids:
        return {}
    row=conn.execute("SELECT source_date FROM world_datasets WHERE dataset_id=?",
                     (dataset,)).fetchone()
    if not row or not row[0]:
        raise ValueError("FC27 source snapshot date missing")
    asof=date.fromisoformat(row[0])
    ages={}
    for offset in range(0,len(ids),450):
        chunk=ids[offset:offset+450]
        sql=("SELECT player_id,birth_date FROM world_players WHERE player_id IN ("
             +",".join("?" for _ in chunk)+")")
        for pid,birth in conn.execute(sql,chunk):
            if birth:
                birthday=date.fromisoformat(birth)
                age=(asof.year-birthday.year-
                     ((asof.month,asof.day)<(birthday.month,birthday.day)))
                if 16<=age<=45:
                    ages[pid]=age
    return ages


def three_season_outlook(*,age,overall,position):
    """Wide scenario ranges, not invented exact future performance/potential.

    Age influences *decline exposure*, not an enforced overall-rating change.
    Source POT or growth data can be integrated later if appropriately sourced.
    """
    if (type(age) is not int or not 16<=age<=45 or
            type(overall) is not int or not 1<=overall<=99 or
            not isinstance(position,str) or not position):
        raise ValueError("Source age, position and ability required")
    keeper=position.upper() in ("GK","GOALKEEPER")
    season=[]
    for year in (1,2,3):
        expected_decline=max(0,age+year-(35 if keeper else 32))
        risk=min(16,round(expected_decline*(.52 if keeper else .78)))
        # Youth development is explicitly unknown unless a separate
        # verified calibrated potential signal is available. It can stall.
        upper=min(99,overall+(4 if age<=22 else 2 if age<=25 else 0))
        lower=max(1,overall-risk-(3 if age<=24 else 1))
        season.append({"season":year,"age":age+year,
                       "rating_scenario_low":lower,
                       "rating_scenario_high":upper,
                       "decline_exposure":risk})
    return {"source_overall":overall,"source_age":age,
            "position":position,"scenarios":season,
            "projection_kind":"uncertain_age_exposure_not_sourced_potential"}


def club_horizon(*,profile,roster,ages,starting_roles):
    """Generate a club direction from CURRENT live squad and copied finances."""
    if not profile or not isinstance(starting_roles,dict):
        raise ValueError("Modelled club profile and preferred starting XI needed")
    from world_squad_planner import lane_of
    # Avoid reliance on arbitrary club names. A source-rated ageing starter
    # drives succession, and youthful same-lane competition moderates it.
    lanes={}
    for group,players in roster.items():
        lane=lane_of(group)
        if not lane:
            continue
        lanes.setdefault(lane,[])
        lanes[lane].extend((pid,rating,ages.get(pid))
                          for pid,rating,_ in players)
    succession={}
    for lane,required in starting_roles.items():
        if required<=0:
            continue
        peers=sorted(lanes.get(lane,[]),key=lambda x:-x[1])
        starters=peers[:required]
        old=sum(1 for _,_,age in starters if age is not None and
                age>=(34 if lane=="GK" else 31))
        young=sum(1 for _,_,age in peers[required:] if age is not None
                  and age<=23)
        # Strategic pressure persists with multiple old starters and
        # decreases with actual young successors in the current squad.
        # Prospects are not silently counted as proven starting replacements.
        pressure=max(0,old*16-min(12,young*4))
        if pressure:
            succession[lane]=pressure
    from world_fc27_ai_recruitment import FAMILY as POSITION_FAMILY
    family_succession={family:0 for family in ("GK","DEF","MID","FWD")}
    for lane,pressure in succession.items():
        family=POSITION_FAMILY.get(lane)
        if family:
            family_succession[family]=max(family_succession[family],pressure)
    ambition=profile["ambition_level"]
    financial=profile["financial_pressure_index"]
    win_now=min(100,max(0,ambition*.63+
        profile["pressure_to_improve"]*.37-financial*.10))
    development=min(100,max(0,35+sum(succession.values())*.60+
        max(0,financial-50)*.18))
    return {"version":VERSION,"planning_seasons":3,
            "current_competitive_pressure":round(win_now,2),
            "succession_pressure":succession,
            "family_succession_pressure":family_succession,
            "youth_pipeline_priority":round(development,2),
            "financial_pressure_index":financial,
            "replacement_signings_assumed":0,
            "forecast_is_not_guaranteed":True}


def recruitment_horizon_score(*,category,lane,player_age,player_overall,
                              plan,existing_youth_in_lane=0,
                              immediate_starter_upgrade=False):
    """Relative bonus, preserves existing senior/prospect admission checks.

    A prospect adds an *option* for future seasons, NOT an instant XI upgrade.
    A win-now starter can still outweigh a young, longer-term successor.
    """
    if (category not in ("prospect","senior") or
            type(existing_youth_in_lane) is not int or
            existing_youth_in_lane<0 or
            type(immediate_starter_upgrade) is not bool or
            type(player_overall) is not int or not 1<=player_overall<=99 or
            player_age is not None and
            (type(player_age) is not int or not 16<=player_age<=45)):
        raise ValueError("FC27 recruiting plan must use real rated context")
    need=plan["succession_pressure"].get(lane,0)
    if category=="prospect":
        # Even established clubs can buy prospects with no ageing starter.
        # Bonuses don't imply potential ability or mandatory acquisitions.
        bonus=min(18,need*.55+plan["youth_pipeline_priority"]*.055)
        bonus-=min(11,existing_youth_in_lane*4)
        return {"kind":"prospect_succession_option",
                "score":round(bonus,2),
                "promised_immediate_xi_improvement":False,
                "future_ability_verified":False}
    future_risk=(max(0,player_age-30)*1.3 if player_age is not None else 0)
    now_bonus=(min(9,plan["current_competitive_pressure"]*.09)
               if immediate_starter_upgrade else 0)
    # No age-only bans: elite veterans remain attractive for short-term
    # competitive needs and may be acquired as plausible squad depth.
    return {"kind":"short_term_quality_and_succession",
            "score":round(now_bonus+min(11,need*.24)-
                          min(10,future_risk),2),
            "promised_immediate_xi_improvement":immediate_starter_upgrade,
            "future_ability_verified":False}


def senior_succession_fit(*,roster,lane,overall,candidate_age,
                          incumbent_ages,starting_roles,club_plan):
    """Credible 23-30yo first-team succession WITHOUT appropriating prospects.

    A young professional who is close to an ageing specialist's real source
    ability can be valuable before becoming a current-XI improvement.
    prospect_fit() stays authoritative for 16-22yos, with its own evidence.
    Soft search eligibility -- seller/player/board can still decline.
    """
    if (not isinstance(lane,str) or type(overall) is not int or
            type(candidate_age) is not int or not 23<=candidate_age<=30 or
            not isinstance(roster,dict) or not isinstance(starting_roles,dict)
            or not isinstance(incumbent_ages,dict) or not isinstance(club_plan,dict)):
        return {"eligible":False,"reason":"No supported senior succession case"}
    needed=starting_roles.get(lane,0)
    if needed<=0 or club_plan["succession_pressure"].get(lane,0)<=0:
        return {"eligible":False,"reason":"No ageing tactical specialist to succeed"}
    peers=sorted(roster.get(lane,()),key=lambda x:-x[1])
    starters=peers[:needed]
    if not starters:
        return {"eligible":False,"reason":"No actual incumbent specialist"}
    older=[(pid,ability,incumbent_ages.get(pid))
           for pid,ability,_ in starters
           if incumbent_ages.get(pid,0)>=(34 if lane=="GK" else 31)]
    if not older:
        return {"eligible":False,"reason":"No sourced ageing starter"}
    baseline=min(v[1] for v in older)
    age_advantage=max(v[2]-candidate_age for v in older)
    gap=baseline-overall
    # Similar quality now, room for growth is *unknown*, not promised.
    # Older top-class stars can also be replaced by credible senior players
    # slightly below them, but not unrelated 10-OVR weaker squad fillers.
    if gap>4 or age_advantage<4:
        return {"eligible":False,"reason":"Insufficient verified succession case"}
    score=max(46,min(86,58+max(0,age_advantage)*1.2-
                      max(0,gap)*2+
                      club_plan["succession_pressure"][lane]*.33))
    return {"eligible":True,"category":"senior","score":round(score,2),
            "upgrade":-gap,"lane":lane,
            "depth_shortage":False,"senior_replacement":False,
            "succession":True,"eligible_age_range":"23-30",
            "evidence":"Sourced ages and comparable current positional ability",
            "reason":"Senior succession option for a sourced ageing starter; future ability unverified"}


def seller_horizon_review(*,age,overall,position,market_value,
                          offered_fee,weekly_wage,contract_years,
                          squad_sale,profile):
    """Soft seller asking-price shift plus fully inspectable reasons.

    Age is already in *market_value*: don't count a fabricated second
    depreciation as additional cash. Instead assess the real offer premium
    versus retaining a possibly declining starter, lost immediate quality,
    and real source-game wage exposure across the known simulated contract.
    """
    if (type(age) is not int or not 16<=age<=45 or
            type(overall) is not int or not 1<=overall<=99 or
            type(market_value) is not int or market_value<=0 or
            type(offered_fee) is not int or offered_fee<0 or
            weekly_wage is not None and
            (type(weekly_wage) is not int or weekly_wage<0) or
            type(contract_years) is not int or not 0<=contract_years<=6 or
            not squad_sale.get("valid") or not profile):
        raise ValueError("Known FC27 game transaction and tactical facts required")
    projection=three_season_outlook(age=age,overall=overall,
                                    position=position)
    financial=profile["financial_pressure_index"]
    ambition=profile["ambition_level"]
    fee_premium=offered_fee/market_value-1
    ageing=projection["scenarios"][2]["decline_exposure"]
    # Distinguish high wages and an expiring deal from guaranteed saved cash:
    # the contract may be replaced; it's merely exposure to an extension.
    exposure=(weekly_wage or 0)*52*min(3,contract_years)
    future_pressure=min(.065,ageing*.007+
                        (0.027 if contract_years<=1 else 0))
    fee_opportunity=min(.055,max(0,fee_premium)*.09)
    financial_impetus=max(0,financial-55)*.001
    cost_of_loss=min(.11,max(0,squad_sale.get("formation_quality_loss",0))*.0035+
                     max(0,squad_sale.get("starter_rating_drop",0))*.003)
    title_pressure=max(0,ambition-78)*.0011
    # A negative shift favours a cash-in sale, positive protects now.
    shift=max(-.105,min(.105,
        cost_of_loss+title_pressure-
        future_pressure-fee_opportunity-financial_impetus))
    return {"version":VERSION,"years_examined":3,
            "age_at_source_date":age,"position":position,
            "source_market_reference_gbp":market_value,
            "offer_premium_over_reference_pct":round(100*fee_premium,2),
            "weekly_source_game_wage_gbp":weekly_wage,
            "contract_wage_exposure_gbp":exposure,
            "current_tactical_xi_quality_loss":
                squad_sale.get("formation_quality_loss",0),
            "three_season_decline_exposure":
                projection["scenarios"][2]["decline_exposure"],
            "future_ability_is_scenario_only":True,
            "future_replacement_assumed":False,
            "asking_price_shift_pct":round(100*shift,3),
            "decision_tension":(
                "retain_for_current_competition" if shift>.025 else
                "reconsider_ageing_asset_reinvestment"
                if shift<-.025 else "balanced_current_and_future_value")}

"""FC27 fictional agent terms grounded in the EA source-game weekly wage.

This is a dedicated FC27 market-only wage policy. No wages are invented from
OVR where the source salary is present; unknown source salaries remain unknown.
The source-game wage is not represented as a verified real-life salary.
"""
from math import ceil

VERSION="fc27-source-game-wage-contract-policy-v1"


def fc27_agent_wage_floor(*,source_weekly_wage,buyer_appeal,
                          seller_appeal,offered_role,
                          seller_first_choice=False,
                          transfer_listed=False):
    """Minimum game-simulation weekly salary a player might consider.

    Career opportunity and playing time alter the source salary benchmark.
    A genuine first-team player joining a weaker sporting project expects a
    stronger wage; a transfer-listed reserve seeking starts may negotiate
    marginally below current pay. Always a negotiation, never auto-consent.
    """
    if (type(source_weekly_wage) is not int or
        not 0<=source_weekly_wage<=1_000_000 or
        any(type(v) is not int or not 0<=v<=100
            for v in (buyer_appeal,seller_appeal)) or
        offered_role not in ("rotation","regular_starter","key_player",
                             "fringe","unspecified") or
        type(seller_first_choice) is not bool or
        type(transfer_listed) is not bool):
        raise ValueError("Source game wage and modelled sporting circumstances required")
    difference=buyer_appeal-seller_appeal
    # Players on a stronger current team want convincing football/salary
    # reasons for a step down. A prestige step up may compensate modestly.
    incentive=1.045+(max(0,-difference)*.008+
        (0.10 if seller_first_choice and difference<0 else 0))
    incentive-=min(.055,max(0,difference)*.002)
    if offered_role=="key_player":
        incentive+=.05
    elif offered_role=="rotation" and seller_first_choice:
        incentive+=.08
    if transfer_listed and not seller_first_choice:
        incentive-=.07
    # Very small game wages have a practical minimum; unknown never maps
    # to this floor. £500 rounding is consistent with existing contracts.
    return max(500,int(ceil(max(500,source_weekly_wage)*max(.93,incentive)/500)*500))


def fc27_sporting_recruitment_case(*,category,starter_gain,
                                  role_required,team_standard,overall,
                                  ambition,has_recent_departure=False):
    """Relative, soft benefit of a senior signing to an ambitious club.

    Genuine rotation and succession can be valid without an immediate
    starting-XI improvement, but they should NOT be described or selected
    as guaranteed first-team upgrades. No hard minimum rating/club gate.
    """
    if (type(starter_gain) not in (int,float) or
        any(type(v) is not int or not 0<=v<=100
            for v in (team_standard,ambition)) or
        type(overall) is not int or not 1<=overall<=99 or
        type(role_required) is not bool or
        type(has_recent_departure) is not bool):
        raise ValueError("Source-rated recruitment facts required")
    if category=="prospect":
        return {"kind":"development","score":0,"first_team_upgraded":False}
    improvement=max(0,starter_gain)
    suited=improvement>=3
    if suited:
        return {"kind":"first_team_upgrade",
                "score":round(min(30,improvement*5),2),
                "first_team_upgraded":True}
    if role_required or has_recent_departure:
        return {"kind":"needed_rotation_or_replacement",
                "score":round(9+min(9,improvement*2),2),
                "first_team_upgraded":False}
    gap=max(0,team_standard-overall)
    marginal=max(0,ambition-72)
    # Big-club backup churn is a weak purchase rationale unless it is
    # a verified role need. The candidate is still eligible to be pursued.
    return {"kind":"discretionary_depth",
            "score":round(-min(27,gap*.7+marginal*.48),2),
            "first_team_upgraded":False}

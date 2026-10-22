"""FC27-only autonomous market choices: one club, one intent, real chance of no deal.

Scheduling 112 market moments is a CPU budget, not a signing target. No hard
club/position/player transfer counts. All randomness is stable across reloads.
"""
from world_ai_bidding import position_family

POLICY_VERSION="fc27-sporting-economics-v2"
FAMILIES=("GK","DEF","MID","FWD")

def _pick(items,weights,draw):
    if type(draw) is not int or not 0<=draw<1000000:
        raise ValueError("Need a stable draw in 0..999999")
    if len(items)!=len(weights) or not items or any(w<=0 for w in weights):
        raise ValueError("Select from positive weighted options")
    total=sum(weights)
    chosen=draw*total//1000000
    for item,weight in zip(items,weights):
        if chosen<weight:return item
        chosen-=weight
    return items[-1]

def select_recruiting_club(priorities,*,draw):
    """Every active club has a nonzero prospect of leading this market pulse.

    A pulse represents ONE independent recruiting desk, not exhaustive
    retries from every global club until someone can be made to sign.
    """
    if not priorities:
        return None
    clubs=sorted(priorities)
    weights=[max(1,min(180,35+round(priorities[c]))) for c in clubs]
    return _pick(clubs,weights,draw)

def select_tactical_family(*,family_needs,starting_roles,draw):
    """Position need + number of tactical XI roles; no GK or striker quotas."""
    if set(family_needs)!=set(FAMILIES):
        raise ValueError("Need each specialist position family")
    slots={group:0 for group in FAMILIES}
    for role,count in starting_roles.items():
        family=position_family(role)
        if family not in slots:raise ValueError("Unknown tactical specialist")
        slots[family]+=count
    # The manager's actual tactical weakness must matter more than the
    # number of players in each broad family. Every family retains positive
    # probability and goalkeeper transfers remain possible organically.
    return _pick(FAMILIES,[2+slots[f]*2+
        2*max(0,min(90,round(family_needs[f]))) for f in FAMILIES],draw)

def choose_development_focus(*,profile,draw,senior_upgrade_pressure=0):
    """Development is an independent ambition-based strategy, not a quota."""
    if type(draw) is not int or not 0<=draw<1000:
        raise ValueError("Need stable prospect draw")
    if (type(senior_upgrade_pressure) not in (int,float) or
            not 0<=senior_upgrade_pressure<=100):
        raise ValueError("Invalid evidence-based senior recruitment pressure")
    ambition=profile.get("ambition_level",50) if profile else 50
    risk=profile.get("simulated_manager_risk",50) if profile else 50
    financial=profile.get("financial_pressure_index",50) if profile else 50
    likelihood=max(30,min(285,round(145+(ambition-50)*1.3+
                        (risk-50)*.45-(financial-50)*.65-
                        senior_upgrade_pressure*1.05)))
    return draw<likelihood

def pursue_transfer(*,priority,profile,draw):
    """An interested club can decide to keep its money or scouting options.

    Only one sporting opportunity per market pulse is considered.
    Being rich, ambitious or short of players increases willingness;
    it never guarantees a bid or a successful transfer.
    """
    if type(draw) is not int or not 0<=draw<1000:
        raise ValueError("Need stable commitment draw")
    discipline=profile.get("simulated_manager_financial_discipline",50) if profile else 50
    likelihood=max(120,min(840,round(330+priority*4.2-
                                      max(0,discipline-50)*1.2)))
    return draw<likelihood

def player_market_opportunity(*,buyer_appeal,seller_appeal,
                              overall,sporting_upgrade,prospect,
                              buyer_ambition):
    """Sporting merit of a potential move, independent of nationality.

    Modelled sporting appeal is the same game-context used to assess
    player interests. A first-team player moving to a less attractive
    club needs a clearer route into its XI; youth can rationally trade
    prestige for development. No country, border, league or quota inputs.
    """
    if any(type(x) is not int or not 0<=x<=100 for x in
           (buyer_appeal,seller_appeal,buyer_ambition)):
        raise ValueError("Source-labelled 0-100 club appeal is required")
    if type(overall) is not int or not 1<=overall<=99:
        raise ValueError("Source-rated ability is required")
    if type(sporting_upgrade) not in (int,float) or type(prospect) is not bool:
        raise ValueError("Valid player fit and intent required")
    gap=buyer_appeal-seller_appeal
    # Prestige alone should not compel a club to spend. Buying an actual
    # stronger starter is meaningful even from a weaker seller.
    quality=min(18,max(-8,sporting_upgrade)*2.2)
    ambition=max(0,buyer_ambition-70)*.22 if not prospect else 0
    if prospect:
        career=max(-17,min(11,gap*.24))
    else:
        career=max(-29,min(15,gap*.55))
        if gap<0 and sporting_upgrade>=5:
            career+=min(9,sporting_upgrade*1.3)
    return round(quality+career+ambition,2)


def disruption_sale_premium(sale,*,seller_pressure=0,player_wants_exit=False):
    """Additional *asking-price* share for destroying tactical XI/cover.

    A crucial player remains sellable at a sufficiently exceptional fee.
    Pressure or an exit request lowers resistance, never a blanket veto.
    """
    if not sale.get("valid"):
        raise ValueError("Genuine projected sale report required")
    loss=max(0,sale.get("formation_lineup_loss",0))
    final_specialist=(sale.get("after_depth",0)==0 and
                      sale.get("before_depth",0)>0 and
                      sale.get("tactically_required",False))
    starter_drop=max(0,sale.get("starter_rating_drop",0))
    coverage_gap=(loss>=1 or final_specialist)
    percent=(.34 if coverage_gap else .0)+min(.22,starter_drop*.025)
    if sale.get("protected_rotation"):
        percent+=.07
    # Losing the last credible bench option is meaningful even when the
    # manager can still field eleven starters. Not an absolute veto.
    if sale.get("below_target_cover") and not coverage_gap:
        percent+=.16
    percent+=min(.17,max(0,sale.get("backup_quality_drop",0))*.0035)
    percent+=min(.10,max(0,sale.get("rotation_quality_drop",0))*.008)
    # Financial distress and player pressure change the risk the club
    # can tolerate without hard-coding a permanent sale refusal.
    percent*=max(.4,1-min(.45,max(0,seller_pressure)/180))
    if player_wants_exit:percent*=.72
    return round(min(.78,percent),3)

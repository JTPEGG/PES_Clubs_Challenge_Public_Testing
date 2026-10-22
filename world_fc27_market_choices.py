"""FC27-only autonomous market choices: one club, one intent, real chance of no deal.

Scheduling 112 market moments is a CPU budget, not a signing target. No hard
club/position/player transfer counts. All randomness is stable across reloads.
"""
from world_ai_bidding import position_family

POLICY_VERSION="fc27-voluntary-deal-intent-v1"
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
    return _pick(FAMILIES,[2+slots[f]*3+
        max(0,min(60,round(family_needs[f]))) for f in FAMILIES],draw)

def choose_development_focus(*,profile,draw):
    """Development is an independent ambition-based strategy, not a quota."""
    if type(draw) is not int or not 0<=draw<1000:
        raise ValueError("Need stable prospect draw")
    ambition=profile.get("ambition_level",50) if profile else 50
    risk=profile.get("simulated_manager_risk",50) if profile else 50
    financial=profile.get("financial_pressure_index",50) if profile else 50
    likelihood=max(45,min(285,round(145+(ambition-50)*1.3+
                                     (risk-50)*.45-(financial-50)*.65)))
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
    if sale.get("below_target_cover") and not coverage_gap:
        percent+=.045
    # Financial distress and player pressure change the risk the club
    # can tolerate without hard-coding a permanent sale refusal.
    percent*=max(.4,1-min(.45,max(0,seller_pressure)/180))
    if player_wants_exit:percent*=.72
    return round(min(.72,percent),3)

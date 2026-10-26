"""Source-valued, soft financial shortlist for the FC27-only AI world.

A buyer chooses credible targets using its *actual* unreserved cash, source
FC27 value and wage context, plus a seller's current projected squad impact.
This ranks chances of completing a deal; it does NOT assume an asking price,
invent contract terms, ban expensive players or make a seller accept.
"""
from datetime import date

def _source_age_on(birth_date,when):
    """Same ISO-date logic as the offer reference, without Flask imports."""
    if not birth_date or not when:
        return None
    try:
        birthday=date.fromisoformat(birth_date)
        reference=date.fromisoformat(when)
        return (reference.year-birthday.year-
                ((reference.month,reference.day)<(birthday.month,birthday.day)))
    except ValueError:
        return None
from world_valuation import model_value,fc27_game_reference_value

VERSION="fc27-context-financial-shortlist-v1"

def shortlist_reference_values(conn,*,dataset,player_ids):
    """Batch the same FC27 reference calculation used by _player_reference.

    One indexed query per 500 source players replaces hundreds of redundant
    scalar SQLite lookups for every one of hundreds of independent clubs.
    Returns player_id -> (game-reference GBP, source weekly wage or None).
    """
    if dataset!="fc27-warehouse-659-mens-2026-27":
        raise ValueError("Only FC27 autonomous market uses source wage shortlist")
    result={}
    ids=sorted(set(int(v) for v in player_ids))
    for start in range(0,len(ids),450):
        chunk=ids[start:start+450]
        if not chunk:
            continue
        query="""SELECT r.player_id,x.overall,p.birth_date,
                       p.primary_position,d.source_date,c.weekly_wage_gbp
          FROM world_dataset_rosters r
          JOIN world_players p ON p.player_id=r.player_id
          JOIN world_datasets d ON d.dataset_id=r.dataset_id
          LEFT JOIN world_dataset_ratings x ON x.dataset_id=r.dataset_id
                  AND x.player_id=r.player_id
          LEFT JOIN world_dataset_contract_snapshots c
             ON c.dataset_id=r.dataset_id AND c.player_id=r.player_id
          WHERE r.dataset_id=? AND r.player_id IN ("""+",".join("?" for _ in chunk)+")"
        for pid,ovr,birth,position,when,wage in conn.execute(
                query,(dataset,*chunk)).fetchall():
            baseline=model_value(ovr,_source_age_on(birth,when),position)
            if baseline is not None:
                result[pid]=(fc27_game_reference_value(
                    baseline=baseline,overall=ovr,weekly_wage=wage),wage)
    return result


def prospective_purchase_fit(*,valuation,transfer_headroom,weekly_wage,
                             wage_headroom,sale):
    """Soft buyer economics, NEVER a hard veto or imposed bid/ask.

    Existing seller/agent/board decisions remain authoritative. The seller
    risk is only an unsigned forecast; no fictitious replacement is assumed.
    """
    if (type(valuation) is not int or valuation<=0 or
            type(transfer_headroom) is not int or transfer_headroom<0 or
            type(wage_headroom) is not int or wage_headroom<0 or
            weekly_wage is not None and
            (type(weekly_wage) is not int or weekly_wage<0) or
            not isinstance(sale,dict) or not sale.get("valid")):
        raise ValueError("Actual buyer budget, source value and projected seller risk required")
    # A starting-player sale or heavy tactical disruption is likely to
    # require more than reference market value. This is deliberately
    # conservative: the final board and seller can still accept less/more.
    reserve_premium=(.08+(.14 if sale.get("first_choice") else 0)+
        min(.30,max(0,sale.get("sporting_risk",0))*.0018)+
        (.07 if sale.get("protected_rotation") else 0))
    plausible_fee=round(valuation*(1+reserve_premium))
    coverage=transfer_headroom/max(1,plausible_fee)
    # The projected wage is a *source game wage*, not a verified contract
    # demand. Higher demands may still be accepted by the agent.
    wage_cover=(wage_headroom/max(1,weekly_wage)
                if weekly_wage is not None and weekly_wage>0 else None)
    fee_penalty=(min(125,max(0,1-coverage)*115) if coverage<1 else 0)
    wage_penalty=(min(60,max(0,1-wage_cover)*70)
                  if wage_cover is not None and wage_cover<1 else 0)
    flexibility=min(7,max(0,coverage-1)*7)
    if wage_cover is not None:
        flexibility+=min(3,max(0,wage_cover-1)*2)
    return {"score":round(flexibility-fee_penalty-wage_penalty,2),
            "plausible_fee_gbp":plausible_fee,
            "fee_headroom_ratio":round(coverage,3),
            "source_wage_headroom_ratio":(
                 round(wage_cover,3) if wage_cover is not None else None),
            # An audit estimate, not a veto: an unexpectedly cheap sale
            # or unusual low-wage contract may still succeed.
            "budget_plausible":coverage>=1 and
                 (wage_cover is None or wage_cover>=1)}

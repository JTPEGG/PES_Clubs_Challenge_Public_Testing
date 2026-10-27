"""Forward-looking, non-binding replacement feasibility for AI selling clubs.

No mandatory sign-before-sell condition, magic quotas, or invented future
transfer agreements. This creates a soft NEGOTIATING appraisal from a real
projected squad and actual eligible source-rated market candidates. A club
can still sell without a replacement if finances, player wishes or the bid
justify the risk; recruitment needs escalate after an agreed departure.
"""
from __future__ import annotations
from statistics import median

VERSION="ai-forward-replacement-market-v1"

def assess_future_replacement(*,sale,departing_overall,market_options):
    """Market options: source-rated same-specialist-lane OTHER clubs' players.

    Availability here means plausible scouting targets, not that any other
    club/player has agreed to sell, or that wages will be affordable.
    """
    if not sale.get("valid"):
        raise ValueError("A genuine projected seller squad sale profile is required")
    if type(departing_overall) is not int or not 1<=departing_overall<=99:
        raise ValueError("Departing player's real source overall rating required")
    if not isinstance(market_options,(tuple,list)) or any(
            type(v) is not int or not 1<=v<=99 for v in market_options):
        raise ValueError("Source-rated market prospects required, not invented arrivals")
    plausible=[r for r in market_options if r>=departing_overall-6]
    comparable=[r for r in plausible if r>=departing_overall-2]
    top=max(market_options) if market_options else None
    # No future deal is assumed. A real wide market makes a replacement more
    # credible; scarce same-quality players make selling more strategically costly.
    # Numeric weight is a continuously varying scouting PRIORITY, not a veto.
    scarce=12 if not plausible else 8 if len(plausible)==1 else 4 if len(plausible)==2 else 0
    quality_gap=max(0,departing_overall-(top or 0))
    risk=int(sale.get("sporting_risk",0))
    if risk<0:raise ValueError("Negative sporting risk in projected squad")
    weighted_risk=round(
        risk*.55+scarce+min(15,quality_gap*1.5)+
        (5 if sale.get("protected_rotation") else 0)
    )
    if not sale.get("requires_recruitment"):
        urgency="no_short_term_replacement_required"
    else:
        urgency= sale.get("replacement_priority","improve_rotation")
    return {
      "version":VERSION,
      "source_market_candidates":len(market_options),
      "plausible_future_targets_not_agreed":len(plausible),
      "comparable_rating_targets_not_agreed":len(comparable),
      "highest_scouted_source_rating":top,
      "forecast_replacement_outlook":(
          "available" if len(plausible)>=3 else "difficult"),
      "strategic_sale_risk_weight":weighted_risk,
      "post_sale_recruitment_priority":urgency,
      "sale_can_proceed_before_replacement":True,
      "replacements_assumed_signed":0,
      "note":"Scouting alternatives are uncertain; separate buyer, seller, agent and board approval still required"
    }

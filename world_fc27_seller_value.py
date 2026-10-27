"""FC27-only board valuation of a financially attractive but disruptive sale.

An exceptional price can justify selling before finding a replacement.
However, the board must price the *same sporting loss* as the manager:
a source transfer reference price does not express the cost of losing an
irreplaceable starter in the middle of a 30-minute window. No hard veto,
league quota or mandatory replacement signing is introduced.
"""

VERSION="fc27-board-acknowledges-sporting-loss-v1"


def exceptional_seller_board_floor(*,reference_value,base_board_floor,
                                   projected_squad_sale,risk_uplift,
                                   club_ambition=50):
    """Board's minimum *exceptional* price, distinct from routine asking.

    All currency inputs are FC27 game-simulation GBP; player valuation is
    not a real-world quotation. The premium reflects the manager's actual
    formation, current bench and lost starting quality.
    """
    if (type(reference_value) is not int or reference_value<=0 or
            type(base_board_floor) is not int or base_board_floor<0 or
            type(risk_uplift) not in (int,float) or risk_uplift<0 or
            type(club_ambition) is not int or not 0<=club_ambition<=100 or
            not isinstance(projected_squad_sale,dict) or
            not projected_squad_sale.get("valid")):
        raise ValueError("Live FC27 seller squad and legitimate board valuation required")
    sale=projected_squad_sale
    # An ordinary backup or surplus player does not change board policy.
    sporting_loss=(sale.get("first_choice",False) or
                   sale.get("formation_quality_loss",0)>=3 or
                   sale.get("formation_lineup_loss",0)>0 or
                   sale.get("starter_rating_drop",0)>=4)
    if not sporting_loss:
        return base_board_floor
    ambition_scale=.75+max(0,club_ambition-70)*.013
    sporting_cost=reference_value*risk_uplift*ambition_scale
    # Specialist losses can be substantial even when the club can still
    # fill eleven positions with much weaker reserves.
    quality_loss=max(0,sale.get("formation_quality_loss",0))
    specialist_drop=max(0,sale.get("starter_rating_drop",0))
    sporting_cost+=reference_value*min(
        .42,quality_loss*.014+max(0,specialist_drop-4)*.012)
    # Requiring more than the old threshold is not a mandate to retain.
    # An extraordinary offer still causes board intervention.
    floor=max(base_board_floor,base_board_floor+round(sporting_cost))
    return int((floor+49999)//50000)*50000


def honour_accepted_seller_quote(*,saved_decision,current_review,fee,
                                counter_accepted):
    """Recognise a seller's already accepted offer if squad facts did NOT move.

    The initial quote is a legitimate club decision, not a fresh 'maybe' to
    be repriced after the player/agent agreed terms. The actual accepted
    offer must cover the immutable quoted demand. For a counter, there
    must also be a real 'counter_accepted' event. Changed live formations
    or squad quality still force the normal renewed seller examination.
    """
    import json
    if (not isinstance(saved_decision,dict) or
            not isinstance(current_review,dict) or
            type(fee) is not int or fee<0 or
            type(counter_accepted) is not bool):
        return False
    former=saved_decision.get("effective_decision")
    if former not in ("negotiate","accept"):
        return False
    if former=="negotiate" and not counter_accepted:
        return False
    quoted=saved_decision.get("asking_price")
    if type(quoted) is not int or fee<quoted:
        return False
    try:
        previous=json.loads(saved_decision["input_snapshot"])
    except (KeyError,TypeError,ValueError):
        return False
    old=previous.get("tactical_squad_review")
    new=current_review.get("tactical_squad_review")
    if not isinstance(old,dict) or not isinstance(new,dict):
        return False
    # The current price model may vary by bid value. These are stable live
    # footballing facts and must match to honour the EXISTING agreement.
    relevant=("formation","lineup_loss","first_choice",
              "starter_quality_drop","formation_quality_loss",
              "rotation_quality_drop","after_specialist_depth")
    return all(key in old and key in new and old[key]==new[key]
               for key in relevant)

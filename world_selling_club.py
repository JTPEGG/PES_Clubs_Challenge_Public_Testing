"""Read-only selling-club transfer policy for hypothetical sandbox scenarios.

No real-world contracts, values, club finances or player intentions are inferred.
Historical prestige and sporting appeal are deliberately NOT inputs: this module
evaluates the seller's incentives, not the player's willingness to move.
"""
from math import ceil

SELLER_POLICY_VERSION = "selling-club-v1"
SQUAD_ROLES = ("key_player", "regular_starter", "rotation", "fringe")
ROLE_LABELS = {
    "key_player": "Key Player", "regular_starter": "Regular Starter",
    "rotation": "Rotation Player", "fringe": "Fringe Player",
}
FINANCIAL_STATES = ("unknown", "stable", "cash_needed", "distressed")
REPLACEMENT_STATES = ("unknown", "available", "difficult")
SELLER_STANCES = ("unknown", "retain", "neutral", "sell")
ROLE_MULTIPLIER = {"key_player": 1.45, "regular_starter": 1.24,
                   "rotation": 1.05, "fringe": 0.90}


def evaluate_selling_club(*,market_value=None,offer_fee=None,
                          contract_years=None, squad_role="unknown",
                          transfer_listed=None, financial_state="unknown",
                          replacement="unknown", seller_stance="unknown",
                          player_wants_exit=None, age=None):
    """Return an auditable, non-binding decision with optional fee benchmark.

    All prices are scenario inputs in pounds, never generated from OVR.
    Values 'review', 'reject', 'negotiate', 'accept' distinguish missing data,
    unsellable circumstances, a counteroffer, and an acceptable proposed bid.
    """
    if squad_role not in (*SQUAD_ROLES, "unknown"):
        raise ValueError("Unrecognised squad role")
    if financial_state not in FINANCIAL_STATES:
        raise ValueError("Unrecognised financial condition")
    if replacement not in REPLACEMENT_STATES:
        raise ValueError("Unrecognised replacement availability")
    if seller_stance not in SELLER_STANCES:
        raise ValueError("Unrecognised seller stance")
    if any(v is not None and type(v) is not bool for v in
           (transfer_listed, player_wants_exit)):
        raise ValueError("Transfer listing and player exit wishes require yes/no/unknown")
    for label, value in (("market_value",market_value),("offer_fee",offer_fee)):
        if value is not None and (type(value) is not int or not 0<=value<=1_000_000_000):
            raise ValueError(label+" must be a non-negative integer")
    if contract_years is not None and (
            type(contract_years) is not int or not 0<=contract_years<=6):
        raise ValueError("Contract years must be 0–6 or unknown")
    if age is not None and (type(age) is not int or not 16<=age<=45):
        raise ValueError("Age must be 16–45 or unknown")
    shared = dict(policy_version=SELLER_POLICY_VERSION,
                  market_value=market_value, offer_fee=offer_fee,
                  contract_years=contract_years, squad_role=squad_role,
                  transfer_listed=transfer_listed,
                  financial_state=financial_state,replacement=replacement,
                  seller_stance=seller_stance,player_wants_exit=player_wants_exit,
                  age=age)
    def outcome(status, reason, asking_price=None):
        return {**shared, "decision":status, "reason":reason,
                "asking_price":asking_price,
                "fee_shortfall":(max(0, asking_price-offer_fee)
                                 if asking_price is not None and offer_fee is not None
                                 else None)}
    missing=[]
    for field,value in (("market valuation",market_value),
                        ("remaining contract term",contract_years),
                        ("current squad role",squad_role if squad_role!="unknown" else None),
                        ("transfer-listed status",transfer_listed),
                        ("financial position",financial_state if financial_state!="unknown" else None),
                        ("replacement prospects",replacement if replacement!="unknown" else None),
                        ("club selling stance",seller_stance if seller_stance!="unknown" else None),
                        ("player's desire to leave",player_wants_exit)):
        if value is None:
            missing.append(field)
    if missing:
        return outcome("review", "Unverified scenario inputs: "+", ".join(missing)+
                       ". No willingness to sell or fee is inferred.")
    if seller_stance=="retain" and not transfer_listed and not player_wants_exit:
        return outcome("reject","Club intends to retain this player and has no recorded exit pressure. An arbitrary premium does not force a sale.")
    if (squad_role=="key_player" and contract_years>=3
            and not transfer_listed and not player_wants_exit
            and financial_state=="stable" and replacement=="difficult"):
        return outcome("reject","Essential player, lengthy contract, no exit request, stable finances and no practical replacement: not for sale.")
    # Market value is only the *user's* hypothetical input, not inferred from
    # rating, wages, historical prestige, or modern club transfer rumours.
    premium = ROLE_MULTIPLIER[squad_role]
    premium += 0.08 * max(0,contract_years-2)
    if replacement=="difficult":
        premium+=0.22
    if seller_stance=="retain":
        premium+=0.18
    if player_wants_exit:
        premium-=0.15
    if transfer_listed:
        premium-=0.20
    if contract_years<=1:
        premium-=0.17
    if financial_state=="cash_needed":
        premium-=0.12
    elif financial_state=="distressed":
        premium-=0.25
    premium=max(0.50,premium)
    asking_price=int(ceil((market_value*premium)/50_000)*50_000)
    if offer_fee is None:
        return outcome("negotiate", "Selling circumstances permit an enquiry. No bid submitted; displayed fee is a scenario asking price, not a known club valuation.",asking_price)
    if offer_fee >= asking_price:
        return outcome("accept","Bid meets the seller's simulated asking price. This is only provisional club approval; player and agent consent remain separate.",asking_price)
    return outcome("negotiate",
                   "Bid is below the seller's scenario asking price. Club would request improved terms; no player consent is assumed.",asking_price)

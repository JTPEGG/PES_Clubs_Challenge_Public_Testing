"""Reproducible club-specific AI bid valuation for fictional PES career saves.

No claims about real-world transfer bids, club finances, contracts or interest.
Inputs are the career's ratings and budget ledger plus explicitly saved seller
assumptions. Each decision includes an auditable set of pricing inputs.
"""
from hashlib import sha256

AI_BID_VERSION="club-demand-bidding-v2"
MAX_ROUNDS=3
ACTIVE_STATES=frozenset(("proposed","countered","accepted_pending_contract","agreed_future"))

def position_family(raw):
    if raw is None:return None
    code=str(raw).upper().strip().replace(" ","").replace("-","")
    if code in ("GK","GOALKEEPER"):return "GK"
    if code in ("CB","LB","RB","LWB","RWB","DEF","DF","SW","CENTREBACK","FULLBACK"):return "DEF"
    if code in ("DMF","DM","CDM","CMF","CM","AMF","AM","CAM","LMF","RMF","LM","RM","MID","MF"):return "MID"
    if code in ("CF","ST","SS","LWF","RWF","LW","RW","FW","FWD","STRIKER"):return "FWD"
    return None

def round_up_fee(value):
    if type(value) not in (int,float) or value<0:
        raise ValueError("A modelled bid must be a nonnegative amount")
    step=5000 if value<1_000_000 else 25000 if value<5_000_000 else 50000 if value<15_000_000 else 100000
    return int((int(value+0.999999)+step-1)//step*step)

def club_need(*,overall,ratings,position_group=None):
    """Rated-squad need: a better positional upgrade commands a stronger bid."""
    if type(overall) is not int or not 1<=overall<=99:
        raise ValueError("Rated overall is required")
    if not ratings:return {"score":50,"reason":"Insufficient positional samples; neutral buyer need"}
    values=sorted((n for n in ratings if type(n) is int and 1<=n<=99),reverse=True)
    if not values:return {"score":50,"reason":"No eligible ratings; neutral buyer need"}
    # The third-best player in this role measures room for a regular starter,
    # not automatically the team's top player.
    baseline=values[min(2,len(values)-1)]
    delta=overall-baseline
    scarcity=8 if len(values)<3 else 0
    score=max(15,min(95,50+delta*5+scarcity))
    reason=("Position needs improvement" if score>=65 else
            "Credible depth option" if score>=40 else
            "Low priority relative to existing positional strength")
    return {"score":score,"relative_overall":delta,"position_family":position_group,
            "rated_position_players":len(values),"reason":reason}

def seller_price_context(assumptions):
    """Only known player circumstances may affect AI valuation."""
    if not assumptions:return {"adjustment":0.0,"reasons":[]}
    modifier=0.0
    labels=[]
    if assumptions.get("transfer_listed")==1:
        modifier-=0.07
        labels.append("Recorded transfer listing")
    if assumptions.get("player_wants_exit")==1:
        modifier-=0.05
        labels.append("Recorded player exit interest")
    years=assumptions.get("contract_years")
    if years is not None:
        if years<=1:
            modifier-=0.05
            labels.append("Short remaining contract")
        elif years>=4:
            modifier+=0.045
            labels.append("Longer remaining contract")
    if assumptions.get("squad_role")=="key_player":
        modifier+=0.025
        labels.append("Key player importance")
    return {"adjustment":modifier,"reasons":labels}

def _strategy(career_id,player_id,club_id):
    # Stable, club-specific negotiation preference. No runtime randomness and
    # no reliance on salted Python hash: reproducible after save/reload.
    digest=sha256(f"{career_id}|{player_id}|{club_id}|{AI_BID_VERSION}".encode("utf8")).digest()
    return (int.from_bytes(digest[:4],"big")%21-10)/200.0

def determine_offer(*,career_id,player_id,club_id,valuation,available_budget,
                    need_score,eligible_clubs,active_rival_clubs=0,
                    seller_assumptions=None,prior_fee=None,round_number=1):
    if any(type(v) is not int for v in
           (player_id,club_id,valuation,available_budget,need_score,
            eligible_clubs,active_rival_clubs,round_number)):
        raise ValueError("AI bid inputs must be integers")
    if not 0<valuation<=1_000_000_000 or available_budget<0:
        raise ValueError("Unavailable player valuation or buyer transfer budget")
    if not 0<=need_score<=100 or eligible_clubs<0 or active_rival_clubs<0:
        raise ValueError("Invalid rated need or real eligible-club count")
    if not 1<=round_number<=MAX_ROUNDS:
        raise ValueError("AI bidder has exhausted its permitted negotiation rounds")
    if round_number==1 and prior_fee is not None:
        raise ValueError("First bid cannot have a prior fee")
    if round_number>1 and (type(prior_fee) is not int or prior_fee<=0):
        raise ValueError("Follow-up bids must refer to an actual previous fee")

    seller=seller_price_context(seller_assumptions)
    demand_premium=min(0.14,max(0,eligible_clubs-1)*0.035)
    # Active rival proposals add at most 3%, beyond the unique interested
    # clubs premium. Re-running a simulation does not manufacture demand.
    rivalry_premium=min(0.03,active_rival_clubs*0.01)
    funds_ratio=available_budget/valuation
    financial_capacity=max(0.0,min(0.045,(funds_ratio-1)*0.015))
    strategy=_strategy(career_id,player_id,club_id)
    need_uplift=(need_score-50)*0.0035
    base_ratio=(0.96+need_uplift+financial_capacity+strategy+
                demand_premium+rivalry_premium+seller["adjustment"])
    base_ratio=max(0.72,min(1.43,base_ratio))
    baseline_bid=round_up_fee(valuation*base_ratio)
    ceiling=round_up_fee(valuation*(1.55+min(0.07,demand_premium/2)))
    if round_number==1:
        amount=baseline_bid
    else:
        # Buyers can try twice more after a recorded rejection. Each
        # response must improve by at least ~7%, but never leap beyond a
        # capped premium merely because the simulation button was repeated.
        required=round_up_fee(prior_fee*1.07)
        ambition=round_up_fee(baseline_bid*(1+0.08*(round_number-1)))
        amount=max(required,ambition)
        if amount>ceiling:
            return {"fee":None,"reason":
                "The previous rejected offer is already at the AI buyer's plausible valuation ceiling.",
                "max_fee":ceiling,"round":round_number}
    if amount>available_budget:
        return {"fee":None,"reason":
            "The buyer cannot afford the modelled bid after existing committed and reserved fees.",
            "max_fee":min(ceiling,available_budget),"round":round_number}
    return {"fee":amount,"model_version":AI_BID_VERSION,
            "round":round_number,
            "reference_value":valuation,
            "buyer_club_id":club_id,
            "buyer_need_score":need_score,
            "buyer_valuation_ratio":round(amount/valuation,4),
            "eligible_competing_clubs":eligible_clubs,
            "active_rival_clubs":active_rival_clubs,
            "demand_premium_pct":round(100*demand_premium,2),
            "active_rival_premium_pct":round(100*rivalry_premium,2),
            "club_negotiation_style_pct":round(100*strategy,2),
            "relative_squad_need_pct":round(100*need_uplift,2),
            "financial_capacity_pct":round(100*financial_capacity,2),
            "recorded_seller_adjustment_pct":round(100*seller["adjustment"],2),
            "recorded_seller_facts":seller["reasons"],
            "last_offer":prior_fee,
            "maximum_sensible_fee":ceiling,
            "reason":(
                f"Rated squad need {need_score}/100; {eligible_clubs} eligible AI buyers; "
                f"competition premium {round(100*demand_premium,1)}%; "
                f"buyer-specific valuation, budget and documented seller facts. "
                +(f"Improved after rejection of £{prior_fee:,}." if prior_fee else
                  "Initial offer, not a real-world club quotation.")
            )}

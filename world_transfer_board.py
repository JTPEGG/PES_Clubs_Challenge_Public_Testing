"""Versioned, read-only board transfer oversight for fictional club scenarios.

Board policy parameters are explicit, user-controlled assumptions, not
inferred club policy. Historical prestige and sporting appeal stay separate.
The selling board can direct a sale despite the manager wanting to retain,
but cannot produce player consent. The buying board may veto an affordable bid.
"""

BOARD_VERSION = "board-transfer-oversight-v2-context"

FINANCIAL_OBJECTIVES = ("unknown","growth","balanced","cost_control","cash_generation")
AMBITION_LEVELS = ("unknown","survival","consolidation","promotion","continental")
OWNERSHIP_PRIORITIES = ("unknown","sporting","balanced","return_on_investment")
MANAGER_TRUST_LEVELS = ("unknown","low","medium","high")


def _context_shift(context, side):
    """Return context-dependent policy adjustment in percentage points.

    Explicit, illustrative governance assumptions. No club name or league
    position is used to infer a policy. Selling threshold lower -> easier sale;
    buying fee/wage ceilings lower -> stricter acquisition oversight.
    """
    if context is None:
        return 0, None
    if type(context) is not dict:
        raise ValueError("Board context must be an explicit mapping")
    fields = {
        "financial_objective": FINANCIAL_OBJECTIVES,
        "ambition": AMBITION_LEVELS,
        "ownership_priority": OWNERSHIP_PRIORITIES,
        "manager_trust": MANAGER_TRUST_LEVELS,
    }
    if set(context) != set(fields):
        raise ValueError("Board context requires all four governance fields")
    for name, values in fields.items():
        if context[name] not in values:
            raise ValueError("Invalid board context: " + name)
    if "unknown" in context.values():
        return None, "Board financial objective, ambition, ownership priority and manager trust must all be specified"
    financial = context["financial_objective"]
    ambition = context["ambition"]
    ownership = context["ownership_priority"]
    trust = context["manager_trust"]
    if side == "seller":
        shift = {
            "growth":15, "balanced":0, "cost_control":-20,
            "cash_generation":-35,
        }[financial]
        shift += {"survival":-10,"consolidation":0,"promotion":15,"continental":25}[ambition]
        shift += {"sporting":20,"balanced":0,"return_on_investment":-25}[ownership]
        shift += {"low":-15,"medium":0,"high":20}[trust]
    else:
        shift = {"growth":15,"balanced":0,"cost_control":-20,"cash_generation":-30}[financial]
        shift += {"survival":-10,"consolidation":0,"promotion":5,"continental":15}[ambition]
        shift += {"sporting":15,"balanced":0,"return_on_investment":-20}[ownership]
        shift += {"low":-15,"medium":0,"high":15}[trust]
    return shift, None


def _money(name, value):
    if value is not None and (type(value) is not int or not 0 <= value <= 1_000_000_000):
        raise ValueError(name + " must be a nonnegative whole-pound amount or unknown")

def _percent(name, value):
    if value is not None and (type(value) is not int or not 0 <= value <= 1000):
        raise ValueError(name + " must be a whole percentage between 0 and 1000 or unknown")

def evaluate_seller_board(*, offer_fee=None, market_value=None,
                          approval_multiple_pct=None, intervene=False,
                          context=None):
    """A proposed exceptional-offer trigger, not automatic player acceptance.

    intervene=False means oversight is disabled, not that unknown financial
    terms are known. A board intervention supersedes the seller manager's
    sporting veto, but retains all other approval stages.
    """
    _money("offer_fee", offer_fee)
    _money("market_value", market_value)
    _percent("approval_multiple_pct", approval_multiple_pct)
    if type(intervene) is not bool:
        raise ValueError("intervene must be yes or no")
    shift, context_error = _context_shift(context,"seller")
    shared=dict(policy_version=BOARD_VERSION, enabled=intervene,
                offer_fee=offer_fee, market_value=market_value,
                approval_multiple_pct=approval_multiple_pct,
                context=context,threshold_adjustment_pct=shift)
    if not intervene:
        return {**shared,"decision":"not_enabled",
                "reason":"Board exceptional-sale intervention disabled.",
                "required_offer":None,"shortfall":None}
    if context_error is not None:
        return {**shared,"decision":"review","reason":context_error,
                "required_offer":None,"shortfall":None}
    if offer_fee is None or market_value is None or approval_multiple_pct is None:
        return {**shared,"decision":"review",
                "reason":"The board cannot force a sale without an offer, an explicit valuation and an explicit exceptional-offer threshold.",
                "required_offer":None,"shortfall":None}
    if market_value==0:
        return {**shared,"decision":"review",
                "reason":"A zero valuation cannot support an exceptional-offer multiple.",
                "required_offer":None,"shortfall":None}
    # Ceiling division avoids floating-point money errors.
    effective_pct=max(100,approval_multiple_pct+shift)
    required=(market_value*effective_pct+99)//100
    if offer_fee>=required:
        return {**shared,"decision":"direct_sale",
                "reason":"The proposed bid meets the assumed board exceptional-offer threshold. The manager's wish to retain is overridden; player consent is not.",
                "required_offer":required,"shortfall":0}
    return {**shared,"decision":"no_intervention",
            "reason":"The offer is below the board's exceptional-sale threshold; normal selling-club rules still apply.",
            "required_offer":required,"shortfall":required-offer_fee}


def evaluate_buyer_board(*, offer_fee=None, market_value=None,
                         offered_weekly_wage=None, wage_headroom=None,
                         max_fee_pct=None, max_headroom_use_pct=None,
                         intervene=False, context=None):
    """Buyer board value-for-money policy, distinct from affordability."""
    for k,v in (("offer_fee",offer_fee),("market_value",market_value),
                ("offered_weekly_wage",offered_weekly_wage),
                ("wage_headroom",wage_headroom)):
        _money(k,v)
    for k,v in (("max_fee_pct",max_fee_pct),
                ("max_headroom_use_pct",max_headroom_use_pct)):
        _percent(k,v)
    if type(intervene) is not bool:
        raise ValueError("intervene must be yes or no")
    shift, context_error = _context_shift(context,"buyer")
    shared=dict(policy_version=BOARD_VERSION,enabled=intervene,
                context=context,threshold_adjustment_pct=shift,
                max_fee_pct=max_fee_pct,max_headroom_use_pct=max_headroom_use_pct)
    if not intervene:
        return {**shared,"decision":"not_enabled",
                "reason":"Board value-for-money veto disabled.",
                "maximum_fee":None,"maximum_weekly_wage":None}
    if context_error is not None:
        return {**shared,"decision":"review", "reason":context_error,
                "maximum_fee":None,"maximum_weekly_wage":None}
    if any(x is None for x in (
        offer_fee,market_value,offered_weekly_wage,wage_headroom,
        max_fee_pct,max_headroom_use_pct
    )):
        return {**shared,"decision":"review",
                "reason":"Board review needs a bid, valuation, offered salary, wage headroom and both explicit board limits.",
                "maximum_fee":None,"maximum_weekly_wage":None}
    max_fee=(market_value*max(0,max_fee_pct+shift))//100
    max_wage=(wage_headroom*max(0,max_headroom_use_pct+shift))//100
    problems=[]
    if offer_fee>max_fee:
        problems.append("transfer fee exceeds board value ceiling")
    if offered_weekly_wage>max_wage:
        problems.append("offered wages consume too much available weekly headroom")
    if problems:
        return {**shared,"decision":"veto",
                "reason":"Board refuses the proposal: "+" and ".join(problems)+". This veto applies even if technically affordable.",
                "maximum_fee":max_fee,"maximum_weekly_wage":max_wage}
    return {**shared,"decision":"approved",
            "reason":"Proposal meets the assumed board fee and wage-prudence limits.",
            "maximum_fee":max_fee,"maximum_weekly_wage":max_wage}

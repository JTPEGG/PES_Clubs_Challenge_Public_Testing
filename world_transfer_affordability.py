"""Read-only transfer affordability policy.

Never infer a club's budget, wage bill, fees, financial health or accounting
treatment. This deliberately models two distinct constraints: immediate
transfer funds and incremental weekly payroll headroom. Total contract salary
is displayed as a commitment, not deducted from the transfer fee budget.
"""
BUDGET_POLICY_VERSION = "transfer-affordability-v1"


def assess_transfer_affordability(*, transfer_budget=None, wage_headroom=None,
                                   transfer_fee=None, offered_weekly_wage=None,
                                   signing_on_fee=None, agent_fee=None,
                                   other_upfront_fees=None, contract_years=None):
    """Return review, unaffordable, or affordable for explicit scenario inputs.

    Extra fees default to UNKNOWN, not zero. A user must explicitly type zero.
    A budget and wage headroom represent the *remaining* amounts available
    for this deal, after all previous commitments. No club figures are fetched.
    """
    values = dict(transfer_budget=transfer_budget, wage_headroom=wage_headroom,
                  transfer_fee=transfer_fee, offered_weekly_wage=offered_weekly_wage,
                  signing_on_fee=signing_on_fee, agent_fee=agent_fee,
                  other_upfront_fees=other_upfront_fees)
    for name, value in values.items():
        if value is not None and (type(value) is not int or not 0 <= value <= 1_000_000_000):
            raise ValueError(name+" must be an integer amount in pounds or unknown")
    if contract_years is not None and (
        type(contract_years) is not int or contract_years not in (1,2,3,4,5)
    ):
        raise ValueError("Contract years must be 1–5 or unknown")

    upfront = None
    fee_fields = (transfer_fee, signing_on_fee, agent_fee, other_upfront_fees)
    if all(v is not None for v in fee_fields):
        upfront = sum(fee_fields)
    remaining_budget = (
        transfer_budget-upfront if transfer_budget is not None and upfront is not None
        else None
    )
    remaining_wages = (
        wage_headroom-offered_weekly_wage
        if wage_headroom is not None and offered_weekly_wage is not None
        else None
    )
    annual_wage = (offered_weekly_wage*52 if offered_weekly_wage is not None else None)
    contract_wages = (
        annual_wage*contract_years
        if annual_wage is not None and contract_years is not None else None
    )
    shortfall_fees = (
        max(0,-remaining_budget) if remaining_budget is not None else None
    )
    shortfall_wage = (
        max(0,-remaining_wages) if remaining_wages is not None else None
    )
    missing = [name.replace("_"," ") for name,value in
               {**values,"contract_years":contract_years}.items() if value is None]

    # A proven shortfall must not be disguised as merely an unknown outcome.
    if shortfall_fees or shortfall_wage:
        status = "unaffordable"
        reason = "The supplied remaining transfer budget or weekly wage headroom is insufficient."
    elif missing:
        status = "review"
        reason = "Cannot confirm affordability while these inputs are unknown: "+", ".join(missing)+"."
    else:
        status = "affordable"
        reason = "Specified fee commitments and weekly pay fit the supplied remaining budgets."

    return {
        "policy_version":BUDGET_POLICY_VERSION, "decision":status, "reason":reason,
        **values, "contract_years":contract_years,
        "total_upfront_commitment":upfront, "annual_wage_commitment":annual_wage,
        "total_contract_wages":contract_wages,
        "remaining_transfer_budget":remaining_budget,
        "remaining_weekly_wage_headroom":remaining_wages,
        "transfer_shortfall":shortfall_fees, "weekly_wage_shortfall":shortfall_wage,
        "unknown_fields":missing,
    }

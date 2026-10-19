"""Deterministic read-only three-party transfer negotiation coordinator.

Separates seller permission, player willingness, and agent personal terms.
Everything is an explicitly entered scenario assumption unless club scores are
read from the existing frozen world dataset. No offer, contract, wage, squad,
budget, or career save is written by this module.
"""
from math import ceil

from world_player_decisions import (
    evaluate_player_choice_v2, agent_minimum_wage_v2,
    contract_length_consideration, ROLE_LABELS,
)
from world_selling_club import evaluate_selling_club
from world_transfer_affordability import assess_transfer_affordability
from world_transfer_board import evaluate_seller_board, evaluate_buyer_board

NEGOTIATION_VERSION = "transfer-negotiation-v3-board"


def evaluate_transfer_negotiation(*, player, seller, proposed_contract_years=None,
                                  buyer_finances=None, seller_board=None, buyer_board=None):
    """Evaluate a hypothetical approach with independent party and board decisions.

    player and seller are explicit input mappings passed to their respective
    versioned engines.  No values are filled from player rating or club name.
    Outcome:
      blocked          one party has independently refused;
      needs_information facts or proposed contract years are missing;
      counteroffer     at least one party requires better terms;
      provisional_agreement all parties' *simulation* thresholds met.
    """
    if proposed_contract_years is not None and (
        type(proposed_contract_years) is not int
        or proposed_contract_years not in (1,2,3,4,5)
    ):
        raise ValueError("Proposed contract duration must be 1–5 years or unknown")
    player_result = evaluate_player_choice_v2(**player)
    finance_data = dict(buyer_finances or {})
    finance_data["transfer_fee"] = seller.get("offer_fee")
    finance_data["offered_weekly_wage"] = player.get("offered_wage")
    finance_data["contract_years"] = proposed_contract_years
    finance_result = assess_transfer_affordability(**finance_data)
    seller_result = evaluate_selling_club(**seller)
    seller_board_result = evaluate_seller_board(
        offer_fee=seller.get("offer_fee"),
        market_value=seller.get("market_value"),
        **(seller_board or {}),
    )
    buyer_board_result = evaluate_buyer_board(
        offer_fee=seller.get("offer_fee"),
        market_value=seller.get("market_value"),
        offered_weekly_wage=player.get("offered_wage"),
        wage_headroom=finance_data.get("wage_headroom"),
        **(buyer_board or {}),
    )
    # Board direction overrides only the manager/seller's ordinary refusal or
    # demand for a higher fee. It does not bypass the player's decision, agent
    # terms, buying-club affordability, or board scrutiny of the buyer.
    effective_seller = dict(seller_result)
    if seller_board_result["decision"] == "direct_sale":
        effective_seller.update(
            decision="accept",
            reason="Board-directed sale: "+seller_board_result["reason"],
            overridden_seller_decision=seller_result["decision"],
        )
    agent_demand = agent_minimum_wage_v2(choice=player_result)
    offered_wage = player.get("offered_wage")
    contract_warning = None
    if proposed_contract_years is not None and player_result.get("player_phase"):
        contract_warning = contract_length_consideration(
            phase=player_result["player_phase"], years=proposed_contract_years)
        if contract_warning and agent_demand is not None:
            agent_demand = int(ceil((agent_demand * 1.10) / 500) * 500)

    if player_result["decision"] in ("review", "uninterested"):
        agent_status = "not_assessed"
        agent_reason = "Player willingness is not established; no contract negotiation."
    elif offered_wage is None or proposed_contract_years is None:
        agent_status = "needs_information"
        agent_reason = "Offered wage and proposed contract duration are both required."
    elif player_result.get("role_satisfied") is False:
        agent_status = "counteroffer"
        requested = player_result["required_role"]
        agent_reason = "Player requires a "+ROLE_LABELS.get(requested, requested)+" role guarantee."
    elif agent_demand is not None and offered_wage < agent_demand:
        agent_status = "counteroffer"
        agent_reason = (
            f"Offered £{offered_wage:,}/week is below the "
            f"£{agent_demand:,}/week simulated agent minimum."
        )
    else:
        agent_status = "acceptable"
        agent_reason = "Proposed wage, role and contract length meet the simulated minimum."

    if (player_result["decision"] == "uninterested"
            or effective_seller["decision"] == "reject"
            or buyer_board_result["decision"] == "veto"):
        outcome = "blocked"
        next_step = "A party refuses the move; changing only the fee or wage must not bypass that refusal."
    elif finance_result["decision"] == "unaffordable":
        outcome = "blocked"
        next_step = "Buying club cannot afford the proposed fee commitments or weekly wages. Revise the financial offer or available budget."
    elif (player_result["decision"] == "review"
          or seller_result["decision"] == "review"
          or agent_status == "needs_information"
          or finance_result["decision"] == "review"
          or seller_board_result["decision"] == "review"
          or buyer_board_result["decision"] == "review"):
        outcome = "needs_information"
        next_step = "Specify missing sporting, contractual and affordability information before making a credible transfer decision."
    elif (effective_seller["decision"] == "negotiate"
          or player_result["decision"] == "needs_assurances"
          or agent_status == "counteroffer"):
        outcome = "counteroffer"
        next_step = "Improve the outstanding fee, wage or squad-role terms; no deal is agreed."
    elif (effective_seller["decision"] == "accept"
          and player_result["decision"] == "open_to_talks"
          and agent_status == "acceptable"):
        outcome = "provisional_agreement"
        next_step = "Simulated thresholds met only. No transfer is completed or registered."
    else:
        outcome = "needs_information"
        next_step = "Unexpected or incomplete scenario state; manual review required."

    return {
        "policy_version": NEGOTIATION_VERSION,
        "outcome": outcome,
        "next_step": next_step,
        "player": player_result,
        "selling_club": seller_result,
        "effective_selling_club": effective_seller,
        "selling_board": seller_board_result,
        "buying_board": buyer_board_result,
        "buyer_affordability": finance_result,
        "agent": {
            "status": agent_status,
            "reason": agent_reason,
            "minimum_weekly_wage": agent_demand,
            "proposed_weekly_wage": offered_wage,
            "wage_shortfall": (
                max(0,agent_demand-offered_wage)
                if agent_demand is not None and offered_wage is not None else None
            ),
            "proposed_contract_years": proposed_contract_years,
            "contract_warning": contract_warning,
        },
        "read_only": True,
    }

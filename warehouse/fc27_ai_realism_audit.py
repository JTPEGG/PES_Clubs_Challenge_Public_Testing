"""FC27 warehouse-to-AI *read-only* realism audit.

This module does not assert anything about the intentions of living players,
coaches, or actual club boards. Every test offer is hypothetical and ALL
prestige, European participation, squad status, fee and negotiation inputs
are explicitly labelled scenario assumptions, never derived from a name.

It tests existing transfer/board/agent functions and exposes recruitment
quality / GK hoarding checks as PROPOSED GAME POLICY, not deployed rules.
"""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from statistics import median

from world_transfer_negotiations import evaluate_transfer_negotiation
from world_transfer_affordability import assess_transfer_affordability
from world_selling_club import evaluate_selling_club
from world_transfer_board import evaluate_buyer_board

VERSION="fc27-warehouse-realism-scenarios-v1"
ASSUMPTIONS=(
    "hypothetical_prestige_not_observed",
    "hypothetical_offer_fees_not_market_values",
    "hypothetical_current_role_and_european_qualification",
    "fictional_personality_priors_not_actual_people",
    "signed_game_model_wage_headroom_not_audited_cash",
)
PLAYER={
    "buyer_tier":1,"seller_tier":1,"buyer_score":82,"seller_score":80,
    "buyer_prestige":80,"seller_prestige":80,"overall":82,"age":27,
    "current_wage":70000,"current_role":"regular_starter",
    "transfer_listed":True,"renewal_status":"not_offered",
    "buyer_europe":"none","seller_europe":"none",
    "offered_wage":110000,"role_promise":"key_player",
}
SELLER={
    "market_value":15000000,"offer_fee":30000000,"contract_years":2,
    "squad_role":"regular_starter","transfer_listed":True,
    "player_wants_exit":True,"financial_state":"stable",
    "replacement":"available","seller_stance":"sell","age":27,
}
BUDGET={
    "transfer_budget":100000000,"wage_headroom":1000000,
    "signing_on_fee":0,"agent_fee":0,"other_upfront_fees":0,
}

def scenario(*,player=None,seller=None,finances=None,seller_board=None,
             buyer_board=None,contract_years=3):
    return evaluate_transfer_negotiation(
        player={**PLAYER,**(player or {})},
        seller={**SELLER,**(seller or {})},
        buyer_finances={**BUDGET,**(finances or {})},
        seller_board=seller_board,buyer_board=buyer_board,
        proposed_contract_years=contract_years,
    )

def recruitment_fit(*,target_overall,position,existing_position_overalls,
                    explicit_replacement_needed=False):
    """Suggest club scouting priority WITHOUT creating an offer.

    Conservatively reject GK overstock and non-strengthening signings.
    Tactical role, age/potential, contracts, injuries, loan status and
    *projected* arrivals/departures still need the full AI engine.
    """
    if type(target_overall) is not int or not 1<=target_overall<=99:
        return {"decision":"needs_information","reason":"Target source OVR absent"}
    if not position or not isinstance(existing_position_overalls,(tuple,list)) or any(
            type(x) is not int or not 1<=x<=99 for x in existing_position_overalls):
        return {"decision":"needs_information","reason":"No certified position comparison"}
    if type(explicit_replacement_needed) is not bool:
        raise ValueError("Replacement necessity must be explicitly asserted")
    current=sorted(existing_position_overalls,reverse=True)
    is_gk=position.upper() in ("GK","G")
    if not current:
        return {"decision":"priority_vacancy",
                "reason":"No current position options in verified squad"}
    if explicit_replacement_needed:
        return {"decision":"priority_replacement",
                "reason":"Projected outgoing/departed squad member explicitly provided"}
    if is_gk and len(current)>=3 and target_overall<=current[1]:
        return {"decision":"reject_excess_goalkeepers",
                "reason":"Three existing GK options, target not an upgrade on top two"}
    if target_overall>=current[0]+2:
        return {"decision":"clear_first_team_upgrade",
                "reason":"Source rating exceeds current strongest position player by 2+"}
    if target_overall>=median(current[:min(len(current),3)])+2:
        return {"decision":"credible_position_upgrade",
                "reason":"Source rating exceeds recent top-three positional benchmark"}
    if len(current)>=3 and target_overall<median(current[:3])-3:
        return {"decision":"reject_no_credible_upgrade",
                "reason":"Below established position depth; no replacement required"}
    return {"decision":"depth_requires_manual_ai_need",
            "reason":"No proven starting-XI upgrade; tactical/potential/contract evidence required"}

def run_synthetic_scenarios():
    """Immutable realistic constraints with explicitly hypothetical input."""
    checks={}
    outputs={}
    def record(key,actual,expected,what):
        ok=actual==expected
        checks[key]={"pass":ok,"observed":actual,"expected":expected,
                     "question":what}
        if not ok:raise AssertionError(f"{key}: got {actual}, expected {expected}")

    elite=scenario(player={
        "overall":90,"current_wage":180000,"current_role":"key_player",
        "buyer_score":55,"seller_score":88,
        "buyer_prestige":45,"seller_prestige":90,
        "transfer_listed":False,"renewal_status":"renewal_offered",
        "seller_europe":"champions_league","buyer_europe":"none",
        "offered_wage":500000,"role_promise":"key_player",
    },seller={
        "contract_years":4,"squad_role":"key_player","replacement":"difficult",
        "transfer_listed":False,"player_wants_exit":False,
        "seller_stance":"retain","offer_fee":200000000,
        "market_value":70000000
    },seller_board={"intervene":True,"approval_multiple_pct":175,
                   "context":{"financial_objective":"balanced",
                    "ambition":"continental","ownership_priority":"balanced",
                    "manager_trust":"medium"}},
      finances={"transfer_budget":500000000})
    record("elite_downgrade_player_refusal",elite["player"]["decision"],
        "uninterested","Top club elite key player with Europe refuses major downgrade")
    record("board_cannot_override_player",elite["outcome"],
        "blocked","Exceptional seller board offer cannot manufacture consent")
    record("seller_board_can_direct_sale",elite["selling_board"]["decision"],
        "direct_sale","Board may override selling manager at exceptional fee")
    outputs["elite_downgrade"]=elite["outcome"]

    backup=scenario(
      player={"overall":67,"age":34,"current_role":"fringe",
         "current_wage":14000,"buyer_tier":3,"seller_tier":1,
         "buyer_score":46,"seller_score":72,
         "buyer_prestige":35,"seller_prestige":70,
         "offered_wage":30000,"role_promise":"regular_starter",
         "transfer_listed":True,"renewal_status":"not_offered"},
      seller={"market_value":1000000,"offer_fee":1500000,
        "squad_role":"fringe","contract_years":1,
        "transfer_listed":True,"player_wants_exit":True,
        "financial_state":"stable","replacement":"available","seller_stance":"sell",
        "age":34},
      finances={"transfer_budget":3000000,"wage_headroom":50000})
    record("older_backup_lower_league_willing",backup["player"]["decision"],
      "open_to_talks","An older out-of-favour backup can consider guaranteed starts")
    record("backup_lower_league_deal_provisional",backup["outcome"],
      "provisional_agreement","Eligible offer meets simulated salary and role terms")
    outputs["older_backup"]=backup["outcome"]

    stressed=assess_transfer_affordability(
      transfer_budget=0,wage_headroom=-15000,transfer_fee=0,
      offered_weekly_wage=1000,signing_on_fee=0,agent_fee=0,
      other_upfront_fees=0,contract_years=2)
    record("negative_wage_headroom_blocks_purchase",stressed["decision"],
      "unaffordable","Oversubscribed club cannot increase salary commitments")
    outputs["negative_headroom"]=stressed["remaining_weekly_wage_headroom"]

    unknown=scenario(player={"buyer_prestige":None,"seller_prestige":None})
    record("unknown_institutional_prestige_not_fabricated",unknown["outcome"],
      "needs_information","Complete negotiations require separate, real or declared simulation prestige")
    outputs["unknown_prestige"]=unknown["outcome"]

    seller_protect=scenario(seller={
      "squad_role":"key_player","contract_years":4,"transfer_listed":False,
      "player_wants_exit":False,"financial_state":"stable",
      "replacement":"difficult","seller_stance":"retain","offer_fee":40000000})
    record("stable_club_protects_irreplaceable_key_player",
      seller_protect["selling_club"]["decision"],"reject",
      "Selling club refuses a protected key player without replacement")
    record("irreplaceable_player_does_not_transfer",
      seller_protect["outcome"],"blocked",
      "Seller refusal stops transfer regardless of provisional player terms")

    common={"market_value":10000000,"offer_fee":5000000,
      "squad_role":"regular_starter","transfer_listed":False,
      "player_wants_exit":False,"financial_state":"stable",
      "replacement":"available","seller_stance":"neutral","age":29}
    near=evaluate_selling_club(**common,contract_years=1)
    far=evaluate_selling_club(**common,contract_years=4)
    record("expiring_contract_low_asking_price",
      near["asking_price"]<far["asking_price"],True,
      "Short contract results in lower club-side asking fee")
    outputs["contract_price_pair"]=(near["asking_price"],far["asking_price"])

    veto=evaluate_buyer_board(offer_fee=18000000,market_value=10000000,
       offered_weekly_wage=40000,wage_headroom=500000,
       max_fee_pct=120,max_headroom_use_pct=50,
       intervene=True,context={
        "financial_objective":"cost_control","ambition":"consolidation",
        "ownership_priority":"return_on_investment","manager_trust":"medium"})
    record("buyer_board_vetoes_overpriced_bid",veto["decision"],"veto",
       "Financially affordable price may still be poor value")
    outputs["board_veto"]=veto["decision"]

    for key,kwargs,expect in [
        ("gk_overstock",{"target_overall":74,"position":"GK",
                        "existing_position_overalls":[86,80,75]},"reject_excess_goalkeepers"),
        ("gk_upgrade",{"target_overall":90,"position":"GK",
                       "existing_position_overalls":[86,80,75]},"clear_first_team_upgrade"),
        ("elite_low_quality_recruitment",
         {"target_overall":72,"position":"CF",
          "existing_position_overalls":[89,86,83,81]},"reject_no_credible_upgrade"),
        ("replacement_needed",
         {"target_overall":72,"position":"CF",
          "existing_position_overalls":[89,86,83,81],
          "explicit_replacement_needed":True},"priority_replacement")
    ]:
        result=recruitment_fit(**kwargs)
        record(key,result["decision"],expect,
          "Proposed recruitment planning guard against goalkeeper hoarding/weak upgrades")
    return {"policy":VERSION,"scenario_count":len(checks),"results":checks,
        "all_scenario_assertions_passed":all(x["pass"] for x in checks.values()),
        "selected_outcomes":outputs,"scenario_inputs":list(ASSUMPTIONS),
        "all_player_choices_are_hypothetical":True,
        "no_career_or_PES_mutation":True,
        "recruitment_fit_is_proposed_qa_rule_not_current_live_ai":True}

def audit_real_frozen_snapshot(warehouse_file):
    from warehouse.fc27_reference_reader import FC27WarehouseReader
    with FC27WarehouseReader(warehouse_file) as wh:
        rows=wh.conn.execute("""
          SELECT p.club_key,c.competition_code,c.career_scope,p.sporting_appeal,
                 p.institutional_prestige,p.sampled_overall_players,p.confidence,
                 p.ambition_level,f.signed_wage_headroom_weekly_gbp,
                 f.model_transfer_allowance_gbp,f.pressure_band,
                 m.display_role
          FROM wh_fc27_club_decision_profile p
          JOIN wh_fc27_clubs c ON c.edition=p.edition AND c.club_key=p.club_key
          JOIN wh_fc27_club_financial_circumstances f
            ON f.edition=p.edition AND f.club_key=p.club_key
          JOIN wh_fc27_simulated_manager_agents m
            ON m.edition=p.edition AND m.starting_club_key=p.club_key
          WHERE p.edition=2027
        """).fetchall()
        if len(rows)!=659:
            raise ValueError("FC27 659-club starting scope not preserved")
        confidence=Counter(x[6] for x in rows)
        pressure=Counter(x[10] for x in rows)
        sporting=[x[3] for x in rows]
        ambition=[x[7] for x in rows]
        if any(x[4] is not None for x in rows):
            raise ValueError("Observed institutional prestige suddenly invented")
        if any(x[9]<0 for x in rows):
            raise ValueError("Game transfer allowance became negative")
        over=[x for x in rows if x[8]<0]
        if any(x[8]<0 and x[10] not in ("distress","over_committed") for x in rows):
            raise ValueError("Negative wage headroom masquerades as financially normal")
        return {
          "clubs_audited":len(rows),
          "sporting_appeal_range":[min(sporting),max(sporting)],
          "ambition_game_model_range":[min(ambition),max(ambition)],
          "club_squad_evidence":dict(confidence),
          "financial_pressure_distribution":dict(pressure),
          "signed_negative_wage_headroom_clubs":len(over),
          "unknown_real_institutional_prestige":sum(x[4] is None for x in rows),
          "anonymous_fictional_manager_agents":sum(x[-1]=="Anonymous simulated coaching agent" for x in rows),
          "player_game_priors":wh.decision_dimension_coverage()["personalities"],
          "flag_realism_gaps":[
             "Institutional prestige is unknown, so current full player negotiator needs explicit scenario assumptions or independently sourced prestige.",
             "MLS league tier and 53-competition context must not be compared as a single universal European attractiveness scale.",
             "Game-generated personality priors are not yet applied in the transfer coordinator and should not be treated as individual facts.",
             "Recruitment positional upgrades and projected replacement decisions are a proposed gate, not wired to the live club recruitment engine.",
             "Manager agents are fictional placeholders pending evidence-backed current-day manager identities and career histories."
          ],
          "status":"read_only_development_audit"
        }

def build_report(warehouse_file,output):
    result=run_synthetic_scenarios()
    result["real_warehouse_audit"]=audit_real_frozen_snapshot(warehouse_file)
    path=Path(output)
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise FileExistsError("Never overwrite existing realism audit")
    path.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    return result

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--warehouse",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    print(json.dumps(build_report(args.warehouse,args.output),indent=2))

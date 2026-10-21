"""Game-only elite club net squad-balance rule for autonomous AI recruitment.

No owner intent is inferred from the name, league or account balance. This
pure function uses the current rated projected roster, already AGREED
incoming/outgoing transfers, and explicitly saved seller circumstances.

Standalone calibration before integration with world_ai_world: no career
database writes, no live bids, and no fake guaranteed replacements.
"""
from __future__ import annotations
from world_squad_planner import squad_standard

POLICY="elite-projected-net-squad-balance-v1"
ELITE_RATED_TOP11=82
NORMAL_ELITE_NET_DEPARTURES=1
EXCEPTION_ELITE_NET_DEPARTURES=2

def assess_elite_net_departure(*, projected_seller_roster,
                                agreed_incoming, agreed_outgoing,
                                explicitly_transfer_listed=False,
                                explicitly_wants_exit=False,
                                financial_state="unknown",
                                exceptional_board_approval=False,
                                would_weaken_specialist=True):
    if any(type(v) is not int or v<0 for v in (agreed_incoming,agreed_outgoing)):
        raise ValueError("Deal counts must be independently recorded nonnegative integers")
    if any(type(v) is not bool for v in (
            explicitly_transfer_listed,explicitly_wants_exit,
            exceptional_board_approval,would_weaken_specialist)):
        raise ValueError("Seller circumstances need explicit boolean values")
    if financial_state not in ("unknown","stable","cash_needed","distressed"):
        raise ValueError("Unverified financial state")
    standard=squad_standard(projected_seller_roster)
    base={"policy_version":POLICY,
          "existing_agreed_incoming":agreed_incoming,
          "existing_agreed_outgoing":agreed_outgoing,
          "projected_top11_mean":round(standard,2),
          "current_net_departures":agreed_outgoing-agreed_incoming,
          "would_weaken_specialist":would_weaken_specialist}
    if standard<ELITE_RATED_TOP11:
        return {**base,"allowed":True,"basis":"not_elite_squad",
                "note":"Ordinary specialist, finance and player/seller checks still apply"}
    genuinely_exceptional=(explicitly_wants_exit or
        financial_state in ("cash_needed","distressed") or
        exceptional_board_approval)
    cap=(EXCEPTION_ELITE_NET_DEPARTURES if genuinely_exceptional
         else NORMAL_ELITE_NET_DEPARTURES)
    # Cap projected net *after* a candidate sale. Transfer-listed by itself
    # is not a forced exit; signed arrivals restore genuine club capacity.
    new_net=agreed_outgoing+1-agreed_incoming
    if new_net>cap and (would_weaken_specialist or
                        agreed_outgoing>agreed_incoming):
        return {**base,"allowed":False,"basis":"elite_net_departure_limit",
                "allowable_net_departures":cap,
                "note":"Strong club has already sold too much relative to signed arrivals; future potential replacements are not assumed"}
    return {**base,"allowed":True,"basis":(
        "documented_pressure_exception" if genuinely_exceptional
        else "within_normal_net_balance"),
        "allowable_net_departures":cap,
        "note":"This is not seller or player acceptance; independent transfer stages still decide"}


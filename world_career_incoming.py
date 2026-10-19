"""User-triggered simulated AI personal terms for board-approved incoming bids.

A selling board directs ONLY fee acceptance. The player's existing fictional
career-interest engine is independently consulted, including wage/role,
contract and European participation assumptions. Agent demands and the AI
buyer's proposed wages are fictional economy modelling, never real contracts.
Player refusals close the offer; agent counters persist, and accepted terms
require a further explicit step before a future-dated agreement. No PES
registration is changed or cash paid here.
"""
import sqlite3

POLICY_VERSION = "career-ai-personal-terms-v1"

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_career_incoming_approaches (
 offer_id INTEGER PRIMARY KEY REFERENCES world_career_offers(offer_id),
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 status TEXT NOT NULL CHECK(status IN
 ('needs_information','player_refused','role_refused','wage_limit',
  'agent_counter','terms_accepted','future_agreed')),
 attempts INTEGER NOT NULL DEFAULT 0,
 offered_wage_weekly INTEGER,
 agent_requested_weekly INTEGER,
 role_promise TEXT,
 decision_reason TEXT NOT NULL,
 policy_version TEXT NOT NULL,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

def initialize_incoming_approaches(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def incoming_approach(conn,offer_id):
    cursor=conn.execute("""SELECT * FROM world_career_incoming_approaches
         WHERE offer_id=?""",(offer_id,))
    row=cursor.fetchone()
    return dict(zip((c[0] for c in cursor.description),row)) if row else None


def _save(conn,*,career_id,offer_id,status,reason,attempts=0,
          wage=None,agent_wage=None,role=None):
    conn.execute("""INSERT INTO world_career_incoming_approaches
        (offer_id,career_id,status,attempts,offered_wage_weekly,
         agent_requested_weekly,role_promise,decision_reason,policy_version)
        VALUES(?,?,?,?,?,?,?,?,?)
        ON CONFLICT(offer_id) DO UPDATE SET status=excluded.status,
          attempts=excluded.attempts,
          offered_wage_weekly=excluded.offered_wage_weekly,
          agent_requested_weekly=excluded.agent_requested_weekly,
          role_promise=excluded.role_promise,
          decision_reason=excluded.decision_reason,
          policy_version=excluded.policy_version,
          updated_at=CURRENT_TIMESTAMP""",
        (offer_id,career_id,status,attempts,wage,agent_wage,
         role,reason,POLICY_VERSION))
    conn.commit()
    return incoming_approach(conn,offer_id)


def _role_for_ai(conn,*,career_id,player_id,buyer_club_id,required_role):
    """AI cannot offer a role incompatible with its *rated* squad.

    Key player must be among the top three buyer squad players; regular
    starter among the top ~11. Missing rating samples block assurances.
    """
    from world_careers import _player_reference
    career=conn.execute("SELECT dataset_id FROM world_career_saves WHERE career_id=?",
                        (career_id,)).fetchone()
    if not career:
        raise ValueError("Unknown career")
    ds=career[0]
    _,overall=_player_reference(conn,ds,player_id)
    if overall is None:
        return None
    from world_ai_bidding import position_family
    target=conn.execute("""SELECT primary_position FROM world_players
        WHERE player_id=?""",(player_id,)).fetchone()
    family=position_family(target[0]) if target else None
    rated=conn.execute("""SELECT x.overall,p.primary_position
         FROM world_career_registrations r
         JOIN world_dataset_ratings x ON x.player_id=r.player_id
             AND x.dataset_id=?
         JOIN world_players p ON p.player_id=r.player_id
         WHERE r.career_id=? AND r.club_id=? AND x.overall IS NOT NULL
         ORDER BY x.overall DESC""",(ds,career_id,buyer_club_id)).fetchall()
    rankings=[r[0] for r in rated]
    if len(rankings)<8:
        return None
    rank=1+sum(rating>overall for rating in rankings)
    if family=="GK":
        # A 65-rated goalkeeper can genuinely be a club's best goalkeeper
        # despite ranking below most outfielders by overall rating.
        keepers=[rating for rating,pos in rated
                 if position_family(pos)=="GK"]
        if not keepers:
            return None
        keeper_rank=1+sum(rating>overall for rating in keepers)
        if required_role=="key_player":
            return "key_player" if keeper_rank==1 and rank<=3 else None
        if required_role in ("regular_starter","important"):
            return "regular_starter" if keeper_rank==1 else None
        if keeper_rank==1:
            return "regular_starter"
        return "rotation" if keeper_rank==2 else None
    if required_role=="key_player":
        return "key_player" if rank<=3 else None
    if required_role in ("regular_starter","important"):
        return "regular_starter" if rank<=11 else None
    if rank<=3:
        return "key_player"
    if rank<=11:
        return "regular_starter"
    # Even a Rotation Player must have a credible route into the senior
    # squad; unlimited bench promises made purchases too easy.
    return "rotation" if rank<=18 else None


def advance_incoming_approach(conn,*,career_id,offer_id):
    """Advance one user-triggered stage of a simulated inbound AI approach."""
    from world_preseason_window import assert_window_allows_negotiation
    assert_window_allows_negotiation(conn,career_id=career_id)

    from world_careers import (
        career_player_policy,player_move_interest,agent_terms,negotiate_agent,
        confirm_future_agreement,wage_budget_breakdown,withdraw_offer,
    )
    from world_player_decisions import DECISION_V2_VERSION
    from world_career_selling import selling_enabled
    row=conn.execute("""SELECT o.player_id,o.buying_club_id,o.selling_club_id,
        o.status,o.agreement_date,c.manager_club_id
        FROM world_career_offers o JOIN world_career_saves c
          ON c.career_id=o.career_id
        WHERE o.career_id=? AND o.offer_id=? AND c.state='sandbox'""",
        (career_id,offer_id)).fetchone()
    if not row:
        raise ValueError("Offer not in this career")
    player_id,buyer,seller,status,agreement_date,manager=row
    if seller!=manager or buyer==manager:
        raise ValueError("Only incoming offers for your own club can run an AI approach")
    if not selling_enabled(conn,career_id):
        raise ValueError("Activate the enhanced selling simulation first")
    if status not in ("accepted_pending_contract","agreed_future","withdrawn"):
        raise ValueError("AI personal terms require a selling-club fee agreement")
    existing=incoming_approach(conn,offer_id)
    if status=="withdrawn" and existing and existing["status"] in ("player_refused","role_refused"):
        return existing
    if status=="agreed_future" and existing and existing["status"]=="future_agreed":
        return existing
    if status!="accepted_pending_contract":
        raise ValueError("This transfer is no longer available for personal terms")
    if career_player_policy(conn,career_id)["version"]!=DECISION_V2_VERSION:
        return _save(conn,career_id=career_id,offer_id=offer_id,status="needs_information",
            reason="Incoming AI personal terms require a player-decisions-v2 sandbox career.")

    if existing and existing["status"]=="terms_accepted":
        # All five-stage transfers require the manager's separate final
        # confirmation. Advancing AI negotiations must NEVER sign a deal.
        return existing

    signal=player_move_interest(conn,career_id=career_id,offer_id=offer_id)
    if signal["decision"]=="review":
        return _save(conn,career_id=career_id,offer_id=offer_id,
            status="needs_information",reason=signal["reason"])
    if not signal["can_negotiate"]:
        # Distinct player refusal vetoes an already-board-approved fee.
        withdraw_offer(conn,career_id=career_id,offer_id=offer_id)
        conn.execute("""INSERT INTO world_career_offer_events
            (offer_id,event_type,detail) VALUES (?,'player_refused',?)""",
            (offer_id,signal["reason"]))
        conn.commit()
        return _save(conn,career_id=career_id,offer_id=offer_id,
            status="player_refused",reason=signal["reason"])
    role=_role_for_ai(conn,career_id=career_id,player_id=player_id,
                      buyer_club_id=buyer,required_role=signal.get("required_role","none"))
    if role is None:
        return _save(conn,career_id=career_id,offer_id=offer_id,
            status="role_refused",reason=
            "The buying club cannot offer a credible squad role based on its rated squad. "
            "No player agreement was reached.")

    # Only source-rated agent expectations are generated. No real-world wage
    # or contract length is invented. The AI's 90% initial and 100% follow-up
    # wage offers are explicit policy parameters in the fictional game economy.
    try:
        terms=agent_terms(conn,career_id=career_id,offer_id=offer_id)
    except ValueError as exc:
        return _save(conn,career_id=career_id,offer_id=offer_id,
            status="needs_information",reason=str(exc))
    actual=conn.execute("""SELECT demanded_wage_weekly,rounds,status
        FROM world_career_agent_terms WHERE career_id=? AND offer_id=?""",
        (career_id,offer_id)).fetchone()
    demand,rounds,term_status=actual
    if term_status=="accepted":
        return _save(conn,career_id=career_id,offer_id=offer_id,
            status="terms_accepted",attempts=rounds,
            agent_wage=demand,role=role,
            reason="Simulated agent accepted the proposed terms. A further action is required for future agreement.")
    headroom=wage_budget_breakdown(conn,career_id,buyer)["remaining"]
    wage_ceiling=max(0,int(headroom*0.40))
    if wage_ceiling<demand:
        return _save(conn,career_id=career_id,offer_id=offer_id,
            status="wage_limit",attempts=rounds,agent_wage=demand,role=role,
            reason="AI buyer's modelled prudent wage ceiling is below the agent's demand. "
                   "The fee remains agreed but personal terms have stalled.")
    proposed=demand if rounds>=1 else max(1000,((demand*90//100+499)//500)*500)
    proposed=min(proposed,wage_ceiling)
    # A role promise and concrete wage must be evaluated through the same
    # realistic interest engine as the user's outgoing negotiations.
    final_signal=player_move_interest(conn,career_id=career_id,offer_id=offer_id,
                                      role_promise=role,offered_wage=proposed)
    if not final_signal["can_negotiate"]:
        return _save(conn,career_id=career_id,offer_id=offer_id,
            status="needs_information",attempts=rounds,wage=proposed,
            agent_wage=demand,role=role,reason=final_signal["reason"])
    if final_signal["decision"]=="needs_assurances" and final_signal.get("issue") in ("wage","wage_and_role"):
        # Do not incorrectly interpret "willing to discuss" as acceptance.
        if final_signal.get("minimum_wage") is not None:
            needed=final_signal["minimum_wage"]
            if needed>wage_ceiling:
                return _save(conn,career_id=career_id,offer_id=offer_id,
                    status="wage_limit",attempts=rounds,wage=proposed,
                    agent_wage=demand,role=role,
                    reason="Player requires a higher wage than the buyer's credible modelled ceiling.")
            proposed=max(proposed,needed)
    result=negotiate_agent(conn,career_id=career_id,offer_id=offer_id,
                           weekly_wage=proposed,contract_years=3,
                           agreement_date=agreement_date,role_promise=role)
    confirmed=conn.execute("""SELECT status,rounds,demanded_wage_weekly
       FROM world_career_agent_terms WHERE offer_id=?""",(offer_id,)).fetchone()
    state="terms_accepted" if result=="accepted" else "agent_counter"
    return _save(conn,career_id=career_id,offer_id=offer_id,status=state,
        attempts=confirmed[1],wage=proposed,agent_wage=confirmed[2],role=role,
        reason=("Simulated player/agent accepted personal terms; a separate next step confirms a future agreement."
            if result=="accepted" else
            "Agent has countered the AI club's fictional wage offer; run the next negotiation round."))

def competing_player_choice(conn, *, career_id, offer_id):
    """Reassess an UNSIGNED incoming deal after rival clubs enter the race.

    A fee agreement is not a player's signature. Another live, fee-accepted
    approach gives the player an opportunity to compare offers. Persisting
    ties as delays is safer than silently choosing a buyer; a fully signed
    competing agreement is binding and prevents a second signing.
    """
    from world_careers import player_move_interest
    offer=conn.execute("""SELECT player_id,buying_club_id,offered_fee,status
        FROM world_career_offers WHERE career_id=? AND offer_id=?""",
        (career_id,offer_id)).fetchone()
    if not offer:
        raise ValueError("Offer not found")
    player,buyer,fee,status=offer
    signed=conn.execute("""SELECT o.offer_id,c.name FROM world_career_offers o
        JOIN world_clubs c ON c.club_id=o.buying_club_id
        WHERE o.career_id=? AND o.player_id=? AND o.offer_id<>?
          AND o.status IN ('agreed_future','completed') LIMIT 1""",
        (career_id,player,offer_id)).fetchone()
    if signed:
        return {"decision":"refused","reason":
                f"Player has already signed with {signed[1]}. This transfer cannot proceed."}
    rivals=conn.execute("""SELECT o.offer_id,o.buying_club_id,c.name,
        o.status,t.status AS agent_status,t.proposed_wage_weekly
        FROM world_career_offers o JOIN world_clubs c ON c.club_id=o.buying_club_id
        LEFT JOIN world_career_agent_terms t ON t.offer_id=o.offer_id
        WHERE o.career_id=? AND o.player_id=? AND o.offer_id<>?
          AND o.status IN ('accepted_pending_contract','agreed_future')
        ORDER BY o.offer_id""",(career_id,player,offer_id)).fetchall()
    agent=conn.execute("""SELECT role_promise,proposed_wage_weekly,status
        FROM world_career_agent_terms WHERE offer_id=?""",(offer_id,)).fetchone()
    if not agent or agent[2]!="accepted":
        return {"decision":"delayed","reason":"Player and agent terms have not been agreed."}
    # Re-run the existing v2 footballer-interest policy using actual
    # currently recorded rivals and this buyer's agreed wage/role.
    signal=player_move_interest(conn,career_id=career_id,offer_id=offer_id,
                                role_promise=agent[0],offered_wage=agent[1])
    if not signal["can_negotiate"] or signal["decision"] in ("uninterested","review"):
        return {"decision":"refused","reason":"Player is no longer willing to complete the move: "+signal["reason"]}
    if signal["decision"]!="open_to_talks":
        return {"decision":"delayed","reason":"Player requires further assurances: "+signal["reason"]}
    if rivals:
        from world_careers import current_career_prestige
        if any(r[4]!="accepted" or r[5] is None for r in rivals):
            names=", ".join(r[2] for r in rivals[:3])
            return {"decision":"delayed","reason":
                    f"Player is weighing an agreed-fee approach from {names}. "
                    "Competing personal terms are not yet settled."}
        offers=[(offer_id,buyer,"Current buying club",agent[1])]
        offers.extend((r[0],r[1],r[2],r[5]) for r in rivals)
        def attractiveness(entry):
            prestige=current_career_prestige(conn,career_id,entry[1])
            if not prestige or prestige.get("score") is None:
                return None
            return float(prestige["score"])+min(12.0,max(0,entry[3])/10000.0)
        scored=[(attractiveness(item),item) for item in offers]
        if any(score is None for score,item in scored):
            return {"decision":"delayed","reason":
                    "Player requires club-appeal information before choosing."}
        best=max(score for score,item in scored)
        winners=[item for score,item in scored if abs(score-best)<1.0]
        if len(winners)>1:
            return {"decision":"delayed","reason":
                    "Player is undecided between comparable contract offers."}
        if winners[0][0]!=offer_id:
            return {"decision":"refused","reason":
                    "Player prefers the competing club's sporting opportunity and contract."}
        return {"decision":"ready","reason":
                "Player prefers these agreed terms despite competing offers."}
    return {"decision":"ready","reason":"Player and agent are ready to sign."}


def finalise_incoming_approach(conn,*,career_id,offer_id,now=None):
    """Explicit SELLING MANAGER final confirmation after AI player consent.

    Buying club's exceptional financial board review and selling board
    reconsideration both run at finalisation within the signing transaction.
    This call never moves a PES player; it schedules a future registration.
    """
    from world_preseason_window import assert_window_allows_negotiation
    assert_window_allows_negotiation(conn,career_id=career_id,now=now)

    from world_careers import confirm_future_agreement
    from world_career_transfer_protocol import transfer_protocol_enabled
    row=conn.execute("""SELECT o.agreement_date,o.selling_club_id,o.buying_club_id,
         o.status,c.manager_club_id FROM world_career_offers o
         JOIN world_career_saves c ON c.career_id=o.career_id
         WHERE o.career_id=? AND o.offer_id=? AND c.state='sandbox'""",
         (career_id,offer_id)).fetchone()
    if not row or row[1]!=row[4] or row[2]==row[4]:
        raise ValueError("Only the human selling manager can finalise an incoming transfer")
    if not transfer_protocol_enabled(conn,career_id):
        raise ValueError("Enable five-stage transfer confirmation for this career")
    recorded=incoming_approach(conn,offer_id)
    if row[3]=="agreed_future" and recorded and recorded["status"]=="future_agreed":
        return recorded
    if row[3]!="accepted_pending_contract" or not recorded or recorded["status"]!="terms_accepted":
        raise ValueError("The player and agent must accept before manager finalisation")
    from world_offer_deadlines import require_live_confirmation
    require_live_confirmation(conn,career_id=career_id,offer_id=offer_id,now=now)
    accepted=conn.execute("""SELECT status,proposed_wage_weekly FROM world_career_agent_terms
        WHERE career_id=? AND offer_id=?""",(career_id,offer_id)).fetchone()
    if not accepted or accepted[0]!="accepted" or accepted[1] is None:
        raise ValueError("Agent agreement has not been verified")
    choice=competing_player_choice(conn,career_id=career_id,offer_id=offer_id)
    if choice["decision"]!="ready":
        conn.execute("""INSERT INTO world_career_offer_events
            (offer_id,event_type,detail) VALUES(?,?,?)""",
            (offer_id,"player_competing_offer_"+choice["decision"],choice["reason"]))
        conn.commit()
        raise ValueError(choice["reason"])
    confirm_future_agreement(conn,career_id=career_id,offer_id=offer_id,
                             agreement_date=row[0])
    return _save(conn,career_id=career_id,offer_id=offer_id,
        status="future_agreed",attempts=recorded["attempts"],
        wage=accepted[1],agent_wage=recorded["agent_requested_weekly"],
        role=recorded["role_promise"],
        reason="Human selling manager confirmed the signed future agreement; board veto checks passed. PES registration unchanged.")

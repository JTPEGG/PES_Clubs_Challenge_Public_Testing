"""Opt-in five-stage transfer protocol for PES challenge careers.

1 Offer, 2 Seller accepted/rejected/countered, 3 Player and agent talks,
4 Player accepted/refused, 5 Human manager explicitly confirms OR backs out.
Board financial exception reviews run at the LAST gate for opt-in careers.
Older career rules stay intact unless a sandbox chooses this protocol.
No PES registration occurs when a future-dated agreement is signed.
"""
import sqlite3

VERSION="transfer-five-stages-v1"
SCHEMA="""
CREATE TABLE IF NOT EXISTS world_career_transfer_protocols (
 career_id TEXT PRIMARY KEY REFERENCES world_career_saves(career_id) ON DELETE CASCADE,
 version TEXT NOT NULL,
 activation_note TEXT NOT NULL,
 enabled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS world_career_offer_protocols (
 offer_id INTEGER PRIMARY KEY REFERENCES world_career_offers(offer_id),
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 version TEXT NOT NULL,
 captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS world_career_transfer_final_reviews (
 offer_id INTEGER PRIMARY KEY REFERENCES world_career_offers(offer_id),
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 confirmed_by_club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 board_decision TEXT NOT NULL,
 buyer_board_reason TEXT NOT NULL,
 seller_board_reason TEXT NOT NULL,
 reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

def initialize_transfer_protocol(conn):
    conn.executescript(SCHEMA)
    conn.commit()

def transfer_protocol_enabled(conn,career_id):
    # Existing career engines, test fixtures and legacy archives pre-date
    # this optional schema. Its absence MUST mean legacy mode, never a crash.
    present=conn.execute("""SELECT 1 FROM sqlite_master
        WHERE type='table' AND name='world_career_transfer_protocols'""").fetchone()
    if not present:
        return False
    return conn.execute("""SELECT 1 FROM world_career_transfer_protocols
        WHERE career_id=? AND version=?""",(career_id,VERSION)).fetchone() is not None

def offer_uses_five_stages(conn,offer_id):
    """Only offers explicitly created under this protocol may change stages.

    Opting a career in does NOT rewrite outstanding bids or already signed
    agreements that were created under the previous rules.
    """
    exists=conn.execute("""SELECT 1 FROM sqlite_master
        WHERE type='table' AND name='world_career_offer_protocols'""").fetchone()
    if not exists:
        return False
    return conn.execute("""SELECT 1 FROM world_career_offer_protocols
        WHERE offer_id=? AND version=?""",(offer_id,VERSION)).fetchone() is not None


def snapshot_offer_protocol(conn,*,career_id,offer_id):
    """Write as part of the same offer transaction; no implicit commits."""
    if transfer_protocol_enabled(conn,career_id):
        conn.execute("""INSERT INTO world_career_offer_protocols
            (offer_id,career_id,version) VALUES(?,?,?)""",
            (offer_id,career_id,VERSION))


def enable_transfer_protocol(conn,*,career_id,activation_note):
    if not isinstance(activation_note,str) or not activation_note.strip():
        raise ValueError("Confirm explicitly that this is a fictional five-stage career")
    if conn.in_transaction:
        raise ValueError("Complete current transaction before enabling transfer protocol")
    conn.execute("BEGIN IMMEDIATE")
    try:
        career=conn.execute("""SELECT manager_club_id FROM world_career_saves
            WHERE career_id=? AND state='sandbox'""",(career_id,)).fetchone()
        if not career or career[0] is None:
            raise ValueError("Only the currently managed sandbox career can enable the protocol")
        existing=conn.execute("""SELECT activation_note FROM world_career_transfer_protocols
            WHERE career_id=?""",(career_id,)).fetchone()
        if existing:
            if existing[0]!=activation_note:
                raise ValueError("Protocol already enabled; cannot rewrite activation note")
            conn.commit()
            return False
        conn.execute("""INSERT INTO world_career_transfer_protocols
            (career_id,version,activation_note) VALUES(?,?,?)""",
            (career_id,VERSION,activation_note))
        conn.commit()
        return True
    except BaseException:
        conn.rollback()
        raise


def stage_description(*,offer_status,agent_status=None,incoming_status=None):
    if offer_status=="withdrawn":
        return "Withdrawn — manager or player declined"
    if offer_status=="rejected":
        return "Stage 2 — club rejected offer"
    if offer_status=="countered":
        return "Stage 2 — selling club counteroffer"
    if offer_status=="proposed":
        return "Stage 1 — offer awaiting decision"
    if offer_status=="agreed_future":
        return "Stage 5 — manager confirmed; future registration pending"
    if offer_status=="completed":
        return "Transfer completed"
    if incoming_status in ("player_refused","role_refused","wage_limit"):
        return "Stage 4 — player refused or personal terms failed"
    if agent_status=="accepted" or incoming_status=="terms_accepted":
        return "Stage 4 — player and agent accepted; manager must finalise"
    if offer_status=="accepted_pending_contract":
        return "Stage 3 — player consideration and contract negotiation"
    return "Unknown transfer stage"


def final_board_exception(conn,*,career_id,offer_id,weekly_wage):
    """Evaluate independently of initial fee decisions, using the current board.

    A board can veto an overvalued/unsustainable *purchase*. An incoming sale
    originally forced by the seller's board needs continued board direction
    if the manager still refuses and trust/circumstances have changed.
    Both decisions are justified by saved policies, not random events.
    """
    from world_career_board_policy import career_board_decision,require_board_approval
    from world_career_selling import (selling_enabled,offer_decision,
                                      evaluate_career_seller_bid)
    from world_careers import _player_reference,wage_budget_breakdown
    offer=conn.execute("""SELECT o.player_id,o.buying_club_id,o.selling_club_id,
        o.offered_fee,c.dataset_id,c.manager_club_id
        FROM world_career_offers o JOIN world_career_saves c
          ON c.career_id=o.career_id
        WHERE o.career_id=? AND o.offer_id=? AND c.state='sandbox'""",
        (career_id,offer_id)).fetchone()
    if not offer:
        raise ValueError("Offer not found in this sandbox")
    player_id,buyer,seller,fee,dataset,manager=offer
    if manager not in (buyer,seller):
        raise ValueError("A human manager must be a party to the final agreement")
    price,_=_player_reference(conn,dataset,player_id)
    headroom=wage_budget_breakdown(conn,career_id,buyer)["remaining"]
    buyer_decision=career_board_decision(conn,career_id=career_id,club_id=buyer,
        offer_fee=fee,market_value=price,
        offered_wage=weekly_wage,wage_headroom=headroom,stage="terms")
    # Existing buyer policy is an exceptional financial veto if deal is too
    # expensive relative to value/wages; nonexistent AI buyer policy does not
    # create fictitious AI board preferences.
    require_board_approval(buyer_decision)
    seller_reason="No final seller-board reversal recorded."
    if seller==manager and selling_enabled(conn,career_id):
        from world_career_selling import get_seller_assumptions
        saved=offer_decision(conn,offer_id)
        if saved and saved["career_id"]==career_id:
            fresh=evaluate_career_seller_bid(conn,career_id=career_id,
                player_id=player_id,seller_club_id=seller,offer_fee=fee,
                buying_club_id=buyer)
            if fresh["decision"]=="review":
                raise ValueError("Seller board requires a final review: "+fresh["reason"])
            # Board cannot compel a transfer if it no longer directs sale
            # and the manager's documented seller stance remains to retain.
            if saved["board_decision"]=="direct_sale" and (
                    fresh["board_decision"]!="direct_sale" and
                    fresh["seller"]["decision"]=="reject"):
                raise ValueError("Exceptional seller-board veto: it no longer directs a sale "
                                 "against the manager's documented wish to retain the player")
            assumption=get_seller_assumptions(conn,career_id,player_id)
            # Explicit sporting-first ownership can veto *even a manager-
            # approved sale* if a contracted key player is irreplaceable
            # and there is no exit pressure. The saved extraordinary-sale
            # threshold is the board's sporting exception benchmark.
            if (assumption and assumption["board_enabled"]
                and assumption["ownership_priority"]=="sporting"
                and assumption["ambition"] in ("promotion","continental")
                and assumption["financial_state"]=="stable"
                and assumption["replacement"]=="difficult"
                and assumption["squad_role"]=="key_player"
                and assumption["contract_years"]>=2
                and not assumption["transfer_listed"]
                and not assumption["player_wants_exit"]
                and fresh["board_decision"]!="direct_sale"):
                raise ValueError(
                    "Exceptional seller-board veto: sporting-first ownership will "
                    "not release an irreplaceable contracted key player below "
                    "its explicitly configured exceptional-sale threshold.")
            seller_reason=fresh["reason"]
    return {"decision":"approved","buyer_reason":buyer_decision["reason"],
            "seller_reason":seller_reason}


def record_final_review(conn,*,career_id,offer_id,manager_club_id,decision):
    """Must be called inside the same commit transaction as the future deal."""
    if not offer_uses_five_stages(conn,offer_id):
        return
    conn.execute("""INSERT INTO world_career_transfer_final_reviews
        (offer_id,career_id,confirmed_by_club_id,board_decision,
        buyer_board_reason,seller_board_reason)
        VALUES(?,?,?,?,?,?)""",
        (offer_id,career_id,manager_club_id,decision["decision"],
         decision["buyer_reason"],decision["seller_reason"]))

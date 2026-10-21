"""Career-scoped selling club negotiations and exceptional-sale board directions.

Opt-in for existing sandbox careers; enabling it never rewrites old offers.
Each new offer has a frozen selling-club/board decision audit record.
No player wishes, contracts, finances or board personalities are inferred
from club names, ratings or the real world.
"""
import json

from world_selling_club import (
    evaluate_selling_club, SQUAD_ROLES, FINANCIAL_STATES,
    REPLACEMENT_STATES, SELLER_STANCES,
)
from world_transfer_board import (
    evaluate_seller_board, FINANCIAL_OBJECTIVES, AMBITION_LEVELS,
    OWNERSHIP_PRIORITIES, MANAGER_TRUST_LEVELS,
)

POLICY_VERSION = "career-selling-policy-v1"
DEFAULT_ACTIVATION_NOTE = (
    "Enhanced selling-club decisions enabled by default at career creation; "
    "individual player and selling-board circumstances remain unknown until recorded."
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_career_selling_modes (
 career_id TEXT PRIMARY KEY REFERENCES world_career_saves(career_id),
 activated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 source_note TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS world_career_seller_assumptions (
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 seller_club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 market_value INTEGER CHECK(market_value IS NULL OR market_value BETWEEN 0 AND 1000000000),
 contract_years INTEGER CHECK(contract_years IS NULL OR contract_years BETWEEN 0 AND 6),
 squad_role TEXT NOT NULL CHECK(squad_role IN
 ('unknown','key_player','regular_starter','rotation','fringe')),
 transfer_listed INTEGER CHECK(transfer_listed IN (0,1) OR transfer_listed IS NULL),
 player_wants_exit INTEGER CHECK(player_wants_exit IN (0,1) OR player_wants_exit IS NULL),
 financial_state TEXT NOT NULL CHECK(financial_state IN
 ('unknown','stable','cash_needed','distressed')),
 replacement TEXT NOT NULL CHECK(replacement IN ('unknown','available','difficult')),
 seller_stance TEXT NOT NULL CHECK(seller_stance IN ('unknown','retain','neutral','sell')),
 board_enabled INTEGER NOT NULL CHECK(board_enabled IN (0,1)),
 exceptional_offer_pct INTEGER CHECK(exceptional_offer_pct IS NULL OR
     exceptional_offer_pct BETWEEN 0 AND 1000),
 financial_objective TEXT NOT NULL CHECK(financial_objective IN
 ('unknown','growth','balanced','cost_control','cash_generation')),
 ambition TEXT NOT NULL CHECK(ambition IN
 ('unknown','survival','consolidation','promotion','continental')),
 ownership_priority TEXT NOT NULL CHECK(ownership_priority IN
 ('unknown','sporting','balanced','return_on_investment')),
 assumed_manager_trust TEXT NOT NULL CHECK(assumed_manager_trust IN
 ('unknown','low','medium','high')),
 source_note TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(career_id,player_id)
);
CREATE TABLE IF NOT EXISTS world_career_seller_offer_decisions (
 offer_id INTEGER PRIMARY KEY REFERENCES world_career_offers(offer_id),
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 effective_decision TEXT NOT NULL CHECK(effective_decision IN
 ('accept','negotiate','reject')),
 asking_price INTEGER,
 board_decision TEXT NOT NULL,
 seller_reason TEXT NOT NULL,
 board_reason TEXT NOT NULL,
 input_snapshot TEXT NOT NULL,
 policy_version TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

def initialize_career_selling(conn):
    """Add tables only; do not update career records or legacy transfer offers."""
    conn.executescript(SCHEMA)
    conn.commit()

def _check_manager(conn,career_id):
    row=conn.execute("""SELECT manager_club_id FROM world_career_saves
        WHERE career_id=? AND state='sandbox'""",(career_id,)).fetchone()
    if not row or row[0] is None:
        raise ValueError("Not a playable sandbox career")
    return row[0]

def selling_enabled(conn,career_id):
    return conn.execute(
        "SELECT 1 FROM world_career_selling_modes WHERE career_id=?",
        (career_id,)).fetchone() is not None

def enable_career_selling(conn,*,career_id,source_note):
    """Explicit one-time opt-in, retaining all historical offer states."""
    if not isinstance(source_note,str) or not source_note.strip():
        raise ValueError("An activation note is required")
    if conn.in_transaction:
        raise ValueError("Complete current transaction before enabling selling policy")
    conn.execute("BEGIN IMMEDIATE")
    try:
        _check_manager(conn,career_id)
        old=conn.execute("SELECT source_note FROM world_career_selling_modes WHERE career_id=?",
                         (career_id,)).fetchone()
        if old:
            if old[0]!=source_note:
                raise ValueError("Selling policy already enabled; cannot revise activation")
            conn.commit()
            return False
        conn.execute("INSERT INTO world_career_selling_modes(career_id,source_note) VALUES(?,?)",
                     (career_id,source_note))
        conn.commit()
        return True
    except BaseException:
        conn.rollback()
        raise

def get_seller_assumptions(conn,career_id,player_id):
    cursor=conn.execute("""SELECT * FROM world_career_seller_assumptions
        WHERE career_id=? AND player_id=?""",(career_id,player_id))
    row=cursor.fetchone()
    return dict(zip([c[0] for c in cursor.description],row)) if row else None

def record_seller_assumptions(conn,*,career_id,player_id,market_value=None,
    contract_years=None,squad_role="unknown",transfer_listed=None,
    player_wants_exit=None,financial_state="unknown",replacement="unknown",
    seller_stance="unknown",board_enabled=False,exceptional_offer_pct=None,
    financial_objective="unknown",ambition="unknown",
    ownership_priority="unknown",assumed_manager_trust="unknown",source_note=""):
    """Record explicit scenario circumstances for a player in ONE saved career.

    Immutable assumptions avoid retroactively changing open offers. A later
    version can add revision snapshots and audit history if needed.
    """
    for name,value in (("market_value",market_value),
                       ("exceptional_offer_pct",exceptional_offer_pct)):
        upper=1000 if name=="exceptional_offer_pct" else 1_000_000_000
        if value is not None and (type(value) is not int or not 0<=value<=upper):
            raise ValueError("Invalid "+name)
    if contract_years is not None and (
        type(contract_years) is not int or not 0<=contract_years<=6):
        raise ValueError("Invalid contract duration")
    if squad_role not in (*SQUAD_ROLES,"unknown") or financial_state not in FINANCIAL_STATES:
        raise ValueError("Invalid squad role or finances")
    if replacement not in REPLACEMENT_STATES or seller_stance not in SELLER_STANCES:
        raise ValueError("Invalid replacement or club stance")
    if any(x is not None and type(x) is not bool
           for x in (transfer_listed,player_wants_exit)):
        raise ValueError("Transfer listing and player wishes require explicit yes/no/unknown")
    if type(board_enabled) is not bool:
        raise ValueError("Board enabled must be a boolean")
    if (financial_objective not in FINANCIAL_OBJECTIVES or
        ambition not in AMBITION_LEVELS or
        ownership_priority not in OWNERSHIP_PRIORITIES or
        assumed_manager_trust not in MANAGER_TRUST_LEVELS):
        raise ValueError("Unknown seller board context")
    if not isinstance(source_note,str) or not source_note.strip():
        raise ValueError("Record where the fictional selling circumstances came from")
    details=(market_value,contract_years,squad_role,
             None if transfer_listed is None else int(transfer_listed),
             None if player_wants_exit is None else int(player_wants_exit),
             financial_state,replacement,seller_stance,int(board_enabled),
             exceptional_offer_pct,financial_objective,ambition,
             ownership_priority,assumed_manager_trust,source_note)
    if conn.in_transaction:
        raise ValueError("Complete current transaction before recording selling circumstances")
    conn.execute("BEGIN IMMEDIATE")
    try:
        _check_manager(conn,career_id)
        row=conn.execute("SELECT club_id FROM world_career_registrations WHERE career_id=? AND player_id=?",
                         (career_id,player_id)).fetchone()
        if not row:
            raise ValueError("Player is not registered in this saved career")
        seller_id=row[0]
        old=conn.execute("""SELECT market_value,contract_years,squad_role,transfer_listed,
            player_wants_exit,financial_state,replacement,seller_stance,board_enabled,
            exceptional_offer_pct,financial_objective,ambition,ownership_priority,
            assumed_manager_trust,source_note FROM world_career_seller_assumptions
            WHERE career_id=? AND player_id=?""",(career_id,player_id)).fetchone()
        if old:
            if tuple(old)!=details:
                raise ValueError("Player selling circumstances already frozen; revisions need an auditable workflow")
            conn.commit()
            return False
        conn.execute("""INSERT INTO world_career_seller_assumptions(
            career_id,player_id,seller_club_id,market_value,contract_years,
            squad_role,transfer_listed,player_wants_exit,financial_state,
            replacement,seller_stance,board_enabled,exceptional_offer_pct,
            financial_objective,ambition,ownership_priority,assumed_manager_trust,
            source_note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (career_id,player_id,seller_id,*details))
        conn.commit()
        return True
    except BaseException:
        conn.rollback()
        raise

def _trust_from_confidence(confidence):
    if confidence is None:return None
    return "low" if confidence<35 else "medium" if confidence<70 else "high"

def evaluate_career_seller_bid(conn,*,career_id,player_id,seller_club_id,
                               offer_fee,buying_club_id=None):
    """Return a snapshot-ready selling/board decision for a *new* offer.

    Enabled mode with missing seller circumstances returns review and blocks
    new offers; no silent fallback to old fixed-markup seller policy.
    """
    if not selling_enabled(conn,career_id):
        return {"decision":"legacy","board_decision":"not_enabled",
                "reason":"Legacy seller response is preserved until the career opts in.",
                "snapshot":None}
    info=get_seller_assumptions(conn,career_id,player_id)
    if info is None:
        return {"decision":"review","board_decision":"review",
                "reason":"Record seller circumstances for this player before making a bid.",
                "snapshot":None}
    if info["seller_club_id"]!=seller_club_id:
        return {"decision":"review","board_decision":"review",
                "reason":"Recorded seller does not match the player's current registration.",
                "snapshot":None}
    seller=evaluate_selling_club(
        market_value=info["market_value"],offer_fee=offer_fee,
        contract_years=info["contract_years"],squad_role=info["squad_role"],
        transfer_listed=(None if info["transfer_listed"] is None else bool(info["transfer_listed"])),
        player_wants_exit=(None if info["player_wants_exit"] is None else bool(info["player_wants_exit"])),
        financial_state=info["financial_state"],replacement=info["replacement"],
        seller_stance=info["seller_stance"],
        autonomous_market_reassessment=bool(
            str(info.get("source_note") or "").startswith("fictional-autonomous-seller-")
            and seller_club_id!=_check_manager(conn,career_id)))
    board_kwargs={"intervene":bool(info["board_enabled"]),
        "approval_multiple_pct":info["exceptional_offer_pct"]}
    if info["board_enabled"]:
        manager_club_id=_check_manager(conn,career_id)
        if seller_club_id==manager_club_id:
            b=conn.execute("""SELECT manager_confidence FROM world_career_management_board
                WHERE career_id=? AND club_id=?""",(career_id,seller_club_id)).fetchone()
            trust=_trust_from_confidence(b[0] if b else None)
        else:
            trust=(None if info["assumed_manager_trust"]=="unknown"
                   else info["assumed_manager_trust"])
        board_kwargs["context"]=dict(
            financial_objective=info["financial_objective"],
            ambition=info["ambition"],
            ownership_priority=info["ownership_priority"],
            manager_trust=trust if trust is not None else "unknown")
    board=evaluate_seller_board(offer_fee=offer_fee,
        market_value=info["market_value"],**board_kwargs)
    if seller["decision"]=="review":
        return {"decision":"review","board_decision":board["decision"],
                "reason":"Seller facts are incomplete: "+seller["reason"],
                "seller":seller,"board":board,"snapshot":None}
    if board["decision"]=="review":
        return {"decision":"review","board_decision":"review",
                "reason":"Selling board information incomplete: "+board["reason"],
                "seller":seller,"board":board,"snapshot":None}
    # Count actual LIVE rival offers, not every club that theoretically has
    # money or a squad vacancy. Duplicate bid rounds from one club count once.
    # Rejections, withdrawals and signed-deal histories do not inflate demand.
    rival_count=conn.execute("""SELECT COUNT(DISTINCT buying_club_id)
        FROM world_career_offers WHERE career_id=? AND player_id=?
          AND status IN ('proposed','countered','accepted_pending_contract')
          AND (? IS NULL OR buying_club_id<>?)""",
        (career_id,player_id,buying_club_id,buying_club_id)).fetchone()[0]
    premium_pct=min(12,rival_count*4)
    competition={
        "recorded_active_rival_clubs":rival_count,
        "selling_club_counter_premium_pct":premium_pct,
        "basis":"Active distinct offers in this saved career only; no speculative interest is counted.",
    }
    if board["decision"]=="direct_sale":
        effective="accept"
        reason="Selling board directs a sale despite the manager's preference: "+board["reason"]
        asking=board["required_offer"]
    else:
        effective=seller["decision"]
        reason=seller["reason"]
        asking=seller["asking_price"]
        if premium_pct and info["market_value"] is not None:
            # A clear 'not for sale' remains a rejection. Competition cannot
            # conjure player availability, but can raise a negotiable price.
            if effective=="negotiate" and asking is not None:
                adjusted=(asking*(100+premium_pct)+99)//100
                if adjusted>asking:
                    asking=adjusted
                    reason+=(" Recorded competing bids increase the seller's "
                             f"counteroffer by {premium_pct}%.")
            elif effective=="accept":
                floor=(info["market_value"]*(100+premium_pct)+99)//100
                if offer_fee<floor:
                    effective="negotiate"
                    asking=floor
                    reason=("Seller has other active offers and seeks "
                            f"at least £{floor:,} (demand premium {premium_pct}%).")
        if premium_pct and (effective!=seller["decision"] or
                            asking!=seller["asking_price"]):
            # Reflect the effective seller demand in both the live decision
            # and the immutable seller audit, retaining pre-demand facts.
            seller={**seller,"pre_competition_decision":seller["decision"],
                    "pre_competition_asking_price":seller["asking_price"],
                    "pre_competition_reason":seller["reason"],
                    "decision":effective,"asking_price":asking,"reason":reason}
    return {
        "decision":effective,
        "board_decision":board["decision"],
        "reason":reason,"asking_price":asking,"seller":seller,"board":board,
        "market_competition":competition,
        "snapshot":json.dumps({"seller":seller,"board":board,
            "market_competition":competition,
            "effective_reason":reason,"effective_asking_price":asking,
            "recorded_context":{k:v for k,v in info.items() if k not in (
                "created_at","source_note")}},sort_keys=True),
        "policy_version":POLICY_VERSION,
    }

def offer_decision(conn,offer_id):
    cursor=conn.execute("""SELECT * FROM world_career_seller_offer_decisions
        WHERE offer_id=?""",(offer_id,))
    row=cursor.fetchone()
    return dict(zip([c[0] for c in cursor.description],row)) if row else None

def save_offer_decision(conn,*,career_id,offer_id,player_id,result):
    """Only within the same SQLite offer transaction; never autocommits."""
    if result["decision"] not in ("accept","negotiate","reject"):
        raise ValueError("Selling club response must be final for this offer")
    conn.execute("""INSERT INTO world_career_seller_offer_decisions
        (offer_id,career_id,player_id,effective_decision,asking_price,
         board_decision,seller_reason,board_reason,input_snapshot,policy_version)
         VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (offer_id,career_id,player_id,result["decision"],result.get("asking_price"),
         result["board_decision"],result["seller"]["reason"],
         result["board"]["reason"],result["snapshot"],POLICY_VERSION))

"""Career-specific buying board transfer policy.

Integrates saved board confidence and the existing board engine with persistent
career offers, without deriving real-world ownership preferences or budgets.
No configured policy means the existing sandbox retains its previous behaviour;
enabled policies fail closed on missing financial/valuation/trust information.
"""
from world_transfer_board import evaluate_buyer_board

VERSION = "career-buying-board-v1"
POLICY_SCHEMA = """
CREATE TABLE IF NOT EXISTS world_career_buying_board_policies(
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id) ON DELETE CASCADE,
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 max_fee_pct INTEGER NOT NULL CHECK(max_fee_pct BETWEEN 0 AND 1000),
 max_headroom_use_pct INTEGER NOT NULL CHECK(max_headroom_use_pct BETWEEN 0 AND 1000),
 financial_objective TEXT NOT NULL CHECK(financial_objective IN ('growth','balanced','cost_control','cash_generation')),
 ambition TEXT NOT NULL CHECK(ambition IN ('survival','consolidation','promotion','continental')),
 ownership_priority TEXT NOT NULL CHECK(ownership_priority IN ('sporting','balanced','return_on_investment')),
 source_note TEXT NOT NULL,
 version TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(career_id,club_id)
);
"""

def initialize_career_board_policy(conn):
    conn.executescript(POLICY_SCHEMA)
    conn.commit()

def get_policy(conn,career_id,club_id):
    r=conn.execute("""SELECT max_fee_pct,max_headroom_use_pct,
        financial_objective,ambition,ownership_priority,source_note,version
        FROM world_career_buying_board_policies WHERE career_id=? AND club_id=?""",
        (career_id,club_id)).fetchone()
    if r is None:return None
    keys=("max_fee_pct","max_headroom_use_pct","financial_objective",
          "ambition","ownership_priority","source_note","version")
    return dict(zip(keys,r))

def configure_policy(conn,*,career_id,club_id,max_fee_pct,max_headroom_use_pct,
                     financial_objective,ambition,ownership_priority,source_note):
    """One-time opt-in configuration; existing saves are not silently changed."""
    from world_transfer_board import (FINANCIAL_OBJECTIVES,AMBITION_LEVELS,
                                      OWNERSHIP_PRIORITIES)
    for n,v in (("max_fee_pct",max_fee_pct),("max_headroom_use_pct",max_headroom_use_pct)):
        if type(v) is not int or not 0<=v<=1000:
            raise ValueError(n+" must be a whole percentage between 0 and 1000")
    if (financial_objective not in FINANCIAL_OBJECTIVES[1:] or
        ambition not in AMBITION_LEVELS[1:] or
        ownership_priority not in OWNERSHIP_PRIORITIES[1:]):
        raise ValueError("Unknown board objective, ambition or ownership preference")
    if not isinstance(source_note,str) or not source_note.strip():
        raise ValueError("Identify board settings as explicit sandbox assumptions")
    if conn.in_transaction:
        raise ValueError("Complete active transaction before policy setup")
    conn.execute("BEGIN IMMEDIATE")
    try:
        valid=conn.execute("""SELECT 1 FROM world_career_saves c
            JOIN world_career_club_ledger l ON l.career_id=c.career_id
            WHERE c.career_id=? AND c.manager_club_id=? AND l.club_id=?
              AND c.state='sandbox'""",(career_id,club_id,club_id)).fetchone()
        if not valid:raise ValueError("Policy can only be set for your current managed club")
        old=get_policy(conn,career_id,club_id)
        spec=dict(max_fee_pct=max_fee_pct,max_headroom_use_pct=max_headroom_use_pct,
                  financial_objective=financial_objective,ambition=ambition,
                  ownership_priority=ownership_priority,source_note=source_note,
                  version=VERSION)
        if old is not None:
            if old!=spec:raise ValueError("Board policy already locked; changes require a logged revision")
            conn.commit()
            return False
        conn.execute("""INSERT INTO world_career_buying_board_policies
            (career_id,club_id,max_fee_pct,max_headroom_use_pct,
            financial_objective,ambition,ownership_priority,source_note,version)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (career_id,club_id,max_fee_pct,max_headroom_use_pct,
             financial_objective,ambition,ownership_priority,source_note,VERSION))
        conn.commit()
        return True
    except BaseException:
        conn.rollback()
        raise

def career_board_decision(conn,*,career_id,club_id,offer_fee,market_value,
                          offered_wage=None,wage_headroom=None,stage="fee"):
    """Advisory/authorization using current persisted manager confidence.

    stage='fee' checks only fee value; stage='terms' checks BOTH fee and wage.
    Unknown inputs cause review and block the relevant write.
    """
    if stage not in ("fee","terms"):
        raise ValueError("Unknown board approval stage")
    policy=get_policy(conn,career_id,club_id)
    if policy is None:
        return {"decision":"not_configured",
                "reason":"No saved board policy: legacy career transfer behaviour is preserved.",
                "policy_version":VERSION}
    b=conn.execute("""SELECT manager_confidence FROM world_career_management_board
        WHERE career_id=? AND club_id=?""",(career_id,club_id)).fetchone()
    confidence=b[0] if b else None
    if confidence is None:
        return {"decision":"review",
                "reason":"Set an explicit starting board-confidence score before board-controlled transfers.",
                "policy_version":VERSION}
    trust="low" if confidence<35 else "medium" if confidence<70 else "high"
    ctx=dict(financial_objective=policy["financial_objective"],
             ambition=policy["ambition"],
             ownership_priority=policy["ownership_priority"],
             manager_trust=trust)
    if market_value is None or offer_fee is None:
        return {"decision":"review",
                "reason":"A valuation and offered fee are required for board approval.",
                "policy_version":VERSION}
    if stage=="fee":
        # Wage checks happen only once an agent offer and its salary exist.
        # A zero placeholder MUST NOT be interpreted as an approved wage.
        from world_transfer_board import _context_shift
        shift,err=_context_shift(ctx,"buyer")
        if err:
            return {"decision":"review","reason":err,"policy_version":VERSION}
        cap=market_value*max(0,policy["max_fee_pct"]+shift)//100
        return {"decision":"veto" if offer_fee>cap else "approved",
                "reason":("The board refuses the proposed fee on value grounds."
                          if offer_fee>cap else "Fee within saved board policy; wages still unassessed."),
                "maximum_fee":cap,"confidence":confidence,
                "trust":trust,"policy_version":VERSION}
    result=evaluate_buyer_board(intervene=True,offer_fee=offer_fee,
        market_value=market_value,offered_weekly_wage=offered_wage,
        wage_headroom=wage_headroom,max_fee_pct=policy["max_fee_pct"],
        max_headroom_use_pct=policy["max_headroom_use_pct"],context=ctx)
    return {**result,"confidence":confidence,"trust":trust,
            "policy_version":VERSION}

def require_board_approval(result):
    if result["decision"] in ("not_configured","approved"):
        return
    raise ValueError("Buying board "+result["decision"]+": "+result["reason"])

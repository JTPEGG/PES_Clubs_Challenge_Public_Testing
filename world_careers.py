"""Career-isolated transfer negotiations, economy versions and reserved budgets.

Developer engine only: public web routes remain read-only until authenticated
career ownership exists. No mutation of shared dataset squads or PES League Mode.
All mutations use one SQLite IMMEDIATE transaction and idempotency keys.
"""
import sqlite3
import json
from datetime import date
from world_market import allowed_effective_date, offer_result
from world_prestige_calibration import score_club
from world_valuation import model_value
from world_explorer import age_on

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_career_saves (
 career_id TEXT PRIMARY KEY,
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 title TEXT NOT NULL,
 economy_version TEXT NOT NULL,
 manager_club_id INTEGER REFERENCES world_clubs(club_id),
 pes_lock_date TEXT NOT NULL,
 next_summer_date TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'sandbox' CHECK(state IN ('sandbox','active','archived')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK(next_summer_date > pes_lock_date)
);
CREATE TABLE IF NOT EXISTS world_career_club_ledger (
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 transfer_budget INTEGER NOT NULL CHECK(transfer_budget>=0),
 weekly_wage_budget INTEGER NOT NULL CHECK(weekly_wage_budget>=0),
 committed_fees INTEGER NOT NULL DEFAULT 0 CHECK(committed_fees>=0),
 committed_wages INTEGER NOT NULL DEFAULT 0 CHECK(committed_wages>=0),
 PRIMARY KEY(career_id,club_id)
);
CREATE TABLE IF NOT EXISTS world_career_offers (
 offer_id INTEGER PRIMARY KEY,
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 request_key TEXT NOT NULL,
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 buying_club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 selling_club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 offered_fee INTEGER NOT NULL CHECK(offered_fee>=0),
 demanded_fee INTEGER, offered_wage_weekly INTEGER,
 status TEXT NOT NULL CHECK(status IN
  ('proposed','countered','rejected','accepted_pending_contract','agreed_future','withdrawn','completed')),
 agreement_date TEXT NOT NULL,
 effective_date TEXT,
 source_rating INTEGER, economy_version TEXT NOT NULL,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(career_id,request_key),
 CHECK(buying_club_id<>selling_club_id)
);
CREATE TABLE IF NOT EXISTS world_career_offer_events (
 event_id INTEGER PRIMARY KEY,
 offer_id INTEGER NOT NULL REFERENCES world_career_offers(offer_id),
 event_type TEXT NOT NULL, detail TEXT,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS world_career_registrations (
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 PRIMARY KEY(career_id,player_id)
);
CREATE TABLE IF NOT EXISTS world_career_agent_terms(
 offer_id INTEGER PRIMARY KEY REFERENCES world_career_offers(offer_id),
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 demanded_wage_weekly INTEGER NOT NULL CHECK(demanded_wage_weekly>=0),
 proposed_wage_weekly INTEGER,
 status TEXT NOT NULL CHECK(status IN ('awaiting_offer','countered','accepted')),
 rounds INTEGER NOT NULL DEFAULT 0 CHECK(rounds BETWEEN 0 AND 5),
 contract_years INTEGER NOT NULL DEFAULT 3 CHECK(contract_years BETWEEN 1 AND 5),
 role_promise TEXT NOT NULL DEFAULT 'unspecified',
 updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS world_career_player_policies(
 career_id TEXT PRIMARY KEY REFERENCES world_career_saves(career_id),
 decision_version TEXT NOT NULL,
 prestige_source_version TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS world_career_prestige_snapshots(
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 prestige_score INTEGER NOT NULL CHECK(prestige_score BETWEEN 0 AND 100),
 source_version TEXT NOT NULL,
 source_status TEXT NOT NULL,
 PRIMARY KEY(career_id,club_id)
);
CREATE TABLE IF NOT EXISTS world_career_player_circumstances(
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 current_wage_weekly INTEGER NOT NULL CHECK(current_wage_weekly BETWEEN 0 AND 1000000),
 current_role TEXT NOT NULL CHECK(current_role IN
  ('key_player','regular_starter','important','rotation','fringe')),
 transfer_listed INTEGER NOT NULL CHECK(transfer_listed IN (0,1)),
 renewal_status TEXT NOT NULL CHECK(renewal_status IN ('unknown','renewal_offered','not_offered')),
 source_kind TEXT NOT NULL DEFAULT 'user_sandbox_assumption',
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(career_id,player_id)
);
CREATE TABLE IF NOT EXISTS world_career_offer_europe (
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 offer_id INTEGER NOT NULL REFERENCES world_career_offers(offer_id),
 buyer_europe TEXT NOT NULL CHECK(buyer_europe IN
    ('unknown','none','conference_league','europa_league','champions_league')),
 seller_europe TEXT NOT NULL CHECK(seller_europe IN
    ('unknown','none','conference_league','europa_league','champions_league')),
 source_kind TEXT NOT NULL DEFAULT 'user_sandbox_assumption',
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(career_id,offer_id)
);
CREATE INDEX IF NOT EXISTS world_offers_career_status ON world_career_offers(career_id,status);
"""

ECONOMIES = {
    "prototype-v1": {1:(45_000_000,2_300_000),2:(8_000_000,440_000),3:(1_300_000,110_000),4:(450_000,52_000)},
}


def initialize_career_engine(conn):
    conn.executescript(SCHEMA)
    # Migrate older sandbox careers without replacing saved wage decisions.
    cols={r[1] for r in conn.execute("PRAGMA table_info(world_career_agent_terms)")}
    if "role_promise" not in cols:
        conn.execute("""ALTER TABLE world_career_agent_terms
            ADD COLUMN role_promise TEXT NOT NULL DEFAULT 'unspecified'""")
    # A previous development schema allowed 'important' but not the new
    # 'regular_starter' value. Rebuild only this independent circumstances
    # table, preserving its primary key, timestamps and existing records.
    # Do not rewrite previously agreed agent contract promises.
    schema=conn.execute("""SELECT sql FROM sqlite_master
        WHERE type='table' AND name='world_career_player_circumstances'""").fetchone()
    if schema and "'regular_starter'" not in schema[0]:
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        try:
            latest=conn.execute("""SELECT sql FROM sqlite_master WHERE type='table'
                AND name='world_career_player_circumstances'""").fetchone()[0]
            if "'regular_starter'" not in latest:
                conn.execute("""CREATE TABLE world_career_player_circumstances_role_v3(
                    career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
                    player_id INTEGER NOT NULL REFERENCES world_players(player_id),
                    current_wage_weekly INTEGER NOT NULL
                      CHECK(current_wage_weekly BETWEEN 0 AND 1000000),
                    current_role TEXT NOT NULL CHECK(current_role IN
                      ('key_player','regular_starter','important','rotation','fringe')),
                    transfer_listed INTEGER NOT NULL CHECK(transfer_listed IN (0,1)),
                    renewal_status TEXT NOT NULL CHECK(renewal_status IN
                      ('unknown','renewal_offered','not_offered')),
                    source_kind TEXT NOT NULL DEFAULT 'user_sandbox_assumption',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(career_id,player_id))""")
                conn.execute("""INSERT INTO world_career_player_circumstances_role_v3
                    (career_id,player_id,current_wage_weekly,current_role,
                     transfer_listed,renewal_status,source_kind,updated_at)
                    SELECT career_id,player_id,current_wage_weekly,
                      CASE current_role WHEN 'important' THEN 'regular_starter'
                           ELSE current_role END,
                      transfer_listed,renewal_status,source_kind,updated_at
                    FROM world_career_player_circumstances""")
                conn.execute("DROP TABLE world_career_player_circumstances")
                conn.execute("""ALTER TABLE world_career_player_circumstances_role_v3
                    RENAME TO world_career_player_circumstances""")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    # Additive schema only. Existing career modes and offers are not changed.
    # New careers can now record their selling-mode default atomically at creation.
    from world_career_selling import initialize_career_selling
    initialize_career_selling(conn)
    # Additive-only schema: no existing career starts a timed window here.
    from world_preseason_window import initialise_preseason_windows
    initialise_preseason_windows(conn)
    from world_career_lifecycle import initialize_career_lifecycle
    initialize_career_lifecycle(conn)
    conn.commit()


def _one(conn,sql,args=()):
    return conn.execute(sql,args).fetchone()


def _transaction(conn, fn):
    conn.execute("BEGIN IMMEDIATE")
    try:
        result=fn()
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise


def start_sandbox(conn, *, career_id, dataset_id, title, manager_club_id, pes_lock_date,
                  next_summer_date, economy_version="prototype-v1", scale=1.0,
                  player_decision_version="legacy-sporting-v2"):
    """Create a new sandbox; never change source snapshot budgets or rosters."""
    from world_player_decisions import LEGACY_VERSION,DECISION_VERSION,DECISION_V2_VERSION
    if player_decision_version not in (LEGACY_VERSION,DECISION_VERSION,DECISION_V2_VERSION):
        raise ValueError("Unsupported player decision policy")
    if player_decision_version in (DECISION_VERSION,DECISION_V2_VERSION):
        from world_prestige_full import DATASET_ID,ALL_92
        if dataset_id!=DATASET_ID:
            raise ValueError("New player decision policy needs the 2026/27 92-club prestige dataset")
    if economy_version not in ECONOMIES or not 0.25<=scale<=3:
        raise ValueError("Unsupported economy version or scale")
    lock=date.fromisoformat(pes_lock_date)
    summer=date.fromisoformat(next_summer_date)
    if summer<=lock:raise ValueError("Summer date must follow PES league lock")
    if not career_id or not career_id.replace("-","").replace("_","").isalnum():
        raise ValueError("Career ID must contain letters, numbers, underscores or hyphens")
    def action():
        dataset=_one(conn,"SELECT 1 FROM world_datasets WHERE dataset_id=?",(dataset_id,))
        if dataset is None:raise ValueError("Unknown source dataset")
        teams=conn.execute("""SELECT e.club_id,c.tier FROM world_dataset_entries e
            JOIN world_competitions c ON c.competition_id=e.competition_id
            WHERE e.dataset_id=?""",(dataset_id,)).fetchall()
        if manager_club_id not in {x[0] for x in teams}:raise ValueError("Manager club not in dataset")
        conn.execute("""INSERT INTO world_career_saves
            (career_id,dataset_id,title,economy_version,manager_club_id,pes_lock_date,next_summer_date)
            VALUES(?,?,?,?,?,?,?)""",(career_id,dataset_id,title,economy_version,manager_club_id,
                                       pes_lock_date,next_summer_date))
        has_finances=conn.execute("""SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='world_dataset_club_finances'""").fetchone()
        for club,tier in teams:
            # Historical budget evidence overrides the fictional tier baseline
            # ONLY for the matching source dataset and club.
            verified=(conn.execute("""SELECT transfer_budget_gbp,weekly_wage_budget_gbp
                FROM world_dataset_club_finances
                WHERE dataset_id=? AND club_id=?""",(dataset_id,club)).fetchone()
                if has_finances else None)
            b,w=verified if verified is not None else ECONOMIES[economy_version][tier]
            conn.execute("""INSERT INTO world_career_club_ledger
                (career_id,club_id,transfer_budget,weekly_wage_budget)
                VALUES(?,?,?,?)""",(career_id,club,round(b*scale),round(w*scale)))
        conn.execute("""INSERT INTO world_career_registrations(career_id,player_id,club_id)
            SELECT ?,player_id,club_id FROM world_dataset_rosters WHERE dataset_id=?""",
            (career_id,dataset_id))
        from world_career_lifecycle import seed_career_contracts
        seed_career_contracts(conn,career_id=career_id,dataset_id=dataset_id)
        # Each opt-in new career receives its own frozen prestige inputs.
        # Subsequent global rebalancing cannot retroactively alter offers.
        if player_decision_version in (DECISION_VERSION,DECISION_V2_VERSION):
            from world_prestige_full import ALL_92,FULL_VERSION
            ids=dict(conn.execute("""SELECT c.name,c.club_id FROM world_clubs c
                JOIN world_dataset_entries e ON e.club_id=c.club_id
                WHERE e.dataset_id=?""",(dataset_id,)).fetchall())
            if len(ids)!=92 or any(c["name"] not in ids for c in ALL_92):
                raise ValueError("Incomplete club identity match for prestige snapshot")
            conn.execute("""INSERT INTO world_career_player_policies
                (career_id,decision_version,prestige_source_version)
                VALUES(?,?,?)""",(career_id,player_decision_version,FULL_VERSION))
            conn.executemany("""INSERT INTO world_career_prestige_snapshots
                (career_id,club_id,dataset_id,prestige_score,source_version,source_status)
                VALUES(?,?,?,?,?,?)""",
                ((career_id,ids[c["name"]],dataset_id,
                   score_club(c)["score"],FULL_VERSION,c["source_status"])
                 for c in ALL_92))
        # Enhanced selling-club rules are the default for NEW sandbox careers.
        # This insert runs in the same transaction as the career and roster:
        # no partial save or retroactive change to older career negotiations.
        from world_career_selling import DEFAULT_ACTIVATION_NOTE
        conn.execute("""INSERT INTO world_career_selling_modes(career_id,source_note)
            VALUES(?,?)""",(career_id,DEFAULT_ACTIVATION_NOTE))
        return len(teams)
    return _transaction(conn,action)


def career_player_policy(conn,career_id):
    """No policy row means an older career preserves the legacy decisions."""
    from world_player_decisions import LEGACY_VERSION
    row=_one(conn,"""SELECT decision_version,prestige_source_version
        FROM world_career_player_policies WHERE career_id=?""",(career_id,))
    return {"version":row[0],"prestige_version":row[1]} if row else {
        "version":LEGACY_VERSION,"prestige_version":None}


def prestige_snapshot(conn,career_id,club_id):
    """Unknown is never silently substituted with the latest global draft."""
    row=_one(conn,"""SELECT prestige_score,source_version,source_status
        FROM world_career_prestige_snapshots
        WHERE career_id=? AND club_id=?""",(career_id,club_id))
    if row is None:
        return None
    return {"score":row[0],"version":row[1],"review_status":row[2]}


def current_career_prestige(conn,career_id,club_id):
    """Frozen baseline plus attested gradual prestige evolution per career.

    A global recalibration does not rewrite a career. Once an explicitly
    finalised season exists, use its persisted prestige rather than the
    original baseline. A None season score falls back to the frozen draft.
    """
    base=prestige_snapshot(conn,career_id,club_id)
    if base is None:
        return None
    newer=_one(conn,"""SELECT prestige_at_snapshot,season_index
        FROM world_career_reputation_seasons
        WHERE career_id=? AND club_id=? AND season_index>0
        ORDER BY season_index DESC LIMIT 1""",(career_id,club_id))
    if newer is None or newer[0] is None:
        return base
    return {"score":newer[0],"version":base["version"],
            "review_status":base["review_status"],
            "season_index":newer[1],"season_source":"attested career results"}


def player_circumstances(conn,career_id,player_id):
    """Explicit same-career inputs; absent means UNKNOWN, never a guessed wage."""
    cursor=conn.execute("""SELECT current_wage_weekly,current_role,transfer_listed,
        renewal_status,source_kind,updated_at
        FROM world_career_player_circumstances
        WHERE career_id=? AND player_id=?""",(career_id,player_id))
    row=cursor.fetchone()
    if row is None:
        return None
    result=dict(zip((x[0] for x in cursor.description),row))
    from world_player_decisions import canonical_role
    result["current_role"]=canonical_role(result["current_role"])
    result["transfer_listed"]=bool(result["transfer_listed"])
    return result


def offer_europe_context(conn,career_id,offer_id):
    """Per-offer, user-attested European participation; absent is UNKNOWN."""
    row=_one(conn,"""SELECT buyer_europe,seller_europe,source_kind,updated_at
        FROM world_career_offer_europe
        WHERE career_id=? AND offer_id=?""",(career_id,offer_id))
    return ({"buyer_europe":row[0],"seller_europe":row[1],
             "source_kind":row[2],"updated_at":row[3]}
            if row else None)


def set_player_circumstances(conn, *, career_id, offer_id, current_wage_weekly,
                             current_role, transfer_listed, renewal_status,
                             buyer_europe="unknown",seller_europe="unknown",
                             allow_selling_manager=False):
    """Explicit authenticated manager-supplied scenario, not verified contracts.

    Outgoing approaches can be entered by the human buying manager; a dedicated
    incoming-offer route may explicitly authorise the human selling manager.
    Prevent
    changing inputs after agent discussions have begun, so accepted demands
    cannot become detached from the assumptions that produced them.
    """
    from world_preseason_window import assert_window_allows_negotiation
    assert_window_allows_negotiation(conn,career_id=career_id)

    from world_player_decisions import (
        DECISION_V2_VERSION,PLAYER_CURRENT_ROLES,RENEWAL_STATES,
        EUROPE_LEVELS,canonical_role)
    if buyer_europe not in EUROPE_LEVELS or seller_europe not in EUROPE_LEVELS:
        raise ValueError("Continental competition must be explicitly selected or unknown")
    if career_player_policy(conn,career_id)["version"]!=DECISION_V2_VERSION:
        raise ValueError("Player circumstances require a v2 development career")
    if type(current_wage_weekly) is not int or not 0<=current_wage_weekly<=1_000_000:
        raise ValueError("Explicit current weekly wage must be between £0 and £1m")
    if current_role not in PLAYER_CURRENT_ROLES or current_role=="unknown":
        raise ValueError("Select the current squad role")
    current_role=canonical_role(current_role)
    if type(transfer_listed) is not bool:
        raise ValueError("Transfer listed must be explicitly yes or no")
    if renewal_status not in RENEWAL_STATES:
        raise ValueError("Select the contract renewal situation")
    info=_one(conn,"""SELECT o.player_id,o.buying_club_id,o.selling_club_id,
            o.status,c.manager_club_id
        FROM world_career_offers o JOIN world_career_saves c
        ON c.career_id=o.career_id
        WHERE o.offer_id=? AND o.career_id=? AND c.state='sandbox'""",
        (offer_id,career_id))
    if not info or info[3]!="accepted_pending_contract":
        raise ValueError("Only a pending career offer can record player circumstances")
    is_buyer=info[1]==info[4]
    is_seller=(info[2]==info[4] and info[1]!=info[4])
    if not (is_buyer or (allow_selling_manager and is_seller)):
        raise ValueError("Player circumstances can only be supplied by the manager of a party to this offer")
    if allow_selling_manager and not is_seller:
        raise ValueError("This action is restricted to incoming offers for your squad")
    if allow_selling_manager:
        from world_career_selling import selling_enabled
        if not selling_enabled(conn,career_id):
            raise ValueError("Enable the selling-club simulation before recording incoming player circumstances")
    if _one(conn,"""SELECT 1 FROM world_career_agent_terms t
        JOIN world_career_offers o ON o.offer_id=t.offer_id
        WHERE o.career_id=? AND o.player_id=? LIMIT 1""",
        (career_id,info[0])):
        raise ValueError("Player assumptions are locked once agent negotiations begin")
    def action():
        conn.execute("""INSERT INTO world_career_player_circumstances
            (career_id,player_id,current_wage_weekly,current_role,transfer_listed,
             renewal_status,source_kind)
            VALUES(?,?,?,?,?,?,'user_sandbox_assumption')
            ON CONFLICT(career_id,player_id) DO UPDATE SET
            current_wage_weekly=excluded.current_wage_weekly,
            current_role=excluded.current_role,
            transfer_listed=excluded.transfer_listed,
            renewal_status=excluded.renewal_status,
            updated_at=CURRENT_TIMESTAMP""",
            (career_id,info[0],current_wage_weekly,current_role,
             int(transfer_listed),renewal_status))
        conn.execute("""INSERT INTO world_career_offer_europe(
            career_id,offer_id,buyer_europe,seller_europe,source_kind)
            VALUES(?,?,?,?,'user_sandbox_assumption')
            ON CONFLICT(career_id,offer_id) DO UPDATE SET
            buyer_europe=excluded.buyer_europe,
            seller_europe=excluded.seller_europe,
            source_kind=excluded.source_kind,
            updated_at=CURRENT_TIMESTAMP""",
            (career_id,offer_id,buyer_europe,seller_europe))
        conn.execute("""INSERT INTO world_career_offer_events
            (offer_id,event_type,detail) VALUES(?,'player_circumstances',?)""",
            (offer_id,"Explicit user-entered sandbox assumptions: "
             f"current wage £{current_wage_weekly:,}; role {current_role}; "
             f"listed {transfer_listed}; renewal {renewal_status}; "
             f"buying club Europe {buyer_europe}; current club Europe {seller_europe}"))
    return _transaction(conn,action)


def budget_remaining(conn,career_id,club_id):
    row=_one(conn,"""SELECT transfer_budget,committed_fees FROM world_career_club_ledger
        WHERE career_id=? AND club_id=?""",(career_id,club_id))
    if row is None:raise ValueError("Club not in career")
    reserved=_one(conn,"""SELECT COALESCE(SUM(COALESCE(demanded_fee,offered_fee)),0)
        FROM world_career_offers WHERE career_id=? AND buying_club_id=?
        AND status IN ('proposed','countered','accepted_pending_contract','agreed_future')""",
        (career_id,club_id))[0]
    return row[0]-row[1]-reserved



def wage_budget_breakdown(conn, career_id, club_id):
    """Weekly salary capacity in the *simulation*, not verified existing payroll.

    accepted future deals reserve proposed salary while they await registration;
    contract talks without accepted terms do not yet reserve wages.
    """
    row=_one(conn,"""SELECT weekly_wage_budget,committed_wages
        FROM world_career_club_ledger WHERE career_id=? AND club_id=?""",
        (career_id,club_id))
    if row is None:
        raise ValueError("Club not in career")
    future=_one(conn,"""SELECT COALESCE(SUM(offered_wage_weekly),0)
        FROM world_career_offers
        WHERE career_id=? AND buying_club_id=? AND status='agreed_future'""",
        (career_id,club_id))[0]
    total, committed = row
    return {
        "total": total,
        "committed": committed,
        "reserved_future": future,
        "remaining": total-committed-future,
    }


def _player_reference(conn,ds,pid):
    row=_one(conn,"""SELECT x.overall,p.birth_date,p.primary_position,s.source_date
        FROM world_dataset_rosters r JOIN world_players p ON p.player_id=r.player_id
        JOIN world_datasets s ON s.dataset_id=r.dataset_id
        LEFT JOIN world_dataset_ratings x ON x.dataset_id=r.dataset_id AND x.player_id=r.player_id
        WHERE r.dataset_id=? AND r.player_id=?""",(ds,pid))
    if not row:return None,None
    overall,birth,position,when=row
    return model_value(overall,age_on(birth,when),position),overall


def propose_offer(conn, *, career_id, request_key, player_id, buying_club_id,
                  offered_fee, agreement_date, seller_stance="neutral",
                  ai_bid_snapshot=None, autonomous_inbox=False):
    """Idempotent proposal. Seller response is a new event; no signings yet.

    In an explicitly running live transfer window, autonomous buyer bids
    addressed to the HUMAN seller stay proposed until the manager responds.
    Existing legacy transfer paths remain unchanged.
    """
    from world_preseason_window import assert_window_allows_negotiation
    assert_window_allows_negotiation(conn,career_id=career_id)
    if not isinstance(offered_fee,int) or isinstance(offered_fee,bool) or offered_fee<0:
        raise ValueError("Fee must be a nonnegative GBP integer")
    if not request_key:raise ValueError("Idempotency key is required")
    if ai_bid_snapshot is not None and (
        not isinstance(ai_bid_snapshot,dict)
        or ai_bid_snapshot.get("fee")!=offered_fee
        or ai_bid_snapshot.get("buyer_club_id")!=buying_club_id):
        raise ValueError("AI pricing snapshot does not match the proposed offer")
    date.fromisoformat(agreement_date)
    if autonomous_inbox:
        from world_preseason_window import window_snapshot
        if window_snapshot(conn,career_id=career_id)["state"]!="open" or ai_bid_snapshot is None:
            raise ValueError("Automatic inbox offers require a running market and an auditable AI price")
    def action():
        prev=_one(conn,"SELECT offer_id FROM world_career_offers WHERE career_id=? AND request_key=?",
                  (career_id,request_key))
        if prev:return prev[0]
        career=_one(conn,"SELECT dataset_id,economy_version FROM world_career_saves WHERE career_id=?",(career_id,))
        if not career:raise ValueError("Unknown career")
        if _one(conn,"SELECT 1 FROM world_career_club_ledger WHERE career_id=? AND club_id=?",
                (career_id,buying_club_id)) is None:
            raise ValueError("Buyer is not in career")
        reg=_one(conn,"SELECT club_id FROM world_career_registrations WHERE career_id=? AND player_id=?",
                 (career_id,player_id))
        if not reg:raise ValueError("Player not registered in this career")
        seller=reg[0]
        if seller==buying_club_id:raise ValueError("Player is already at buying club")
        active=_one(conn,"""SELECT offer_id FROM world_career_offers WHERE career_id=?
            AND player_id=? AND status IN ('proposed','countered','accepted_pending_contract','agreed_future')
            AND buying_club_id=?""",(career_id,player_id,buying_club_id))
        if active:raise ValueError("Buying club already has an open negotiation for this player")
        available=budget_remaining(conn,career_id,buying_club_id)
        if available<0 or offered_fee>available:
            raise ValueError("Offered fee exceeds buyer's unreserved transfer budget")
        ref,overall=_player_reference(conn,career[0],player_id)
        from world_career_transfer_protocol import (
            transfer_protocol_enabled,snapshot_offer_protocol)
        modern_offer=transfer_protocol_enabled(conn,career_id)
        if not modern_offer:
            from world_career_board_policy import career_board_decision,require_board_approval
            require_board_approval(career_board_decision(conn,career_id=career_id,
                club_id=buying_club_id,offer_fee=offered_fee,market_value=ref,
                stage="fee"))
        from world_career_selling import evaluate_career_seller_bid,save_offer_decision
        manager_id=_one(conn,"SELECT manager_club_id FROM world_career_saves WHERE career_id=?",
                        (career_id,))[0]
        if autonomous_inbox and (seller!=manager_id or buying_club_id==manager_id):
            raise ValueError("Automatic manager inbox bids must target a player at the human club")
        seller_review=(
            {"decision":"await_manager","reason":"Unsolicited AI bid awaiting human selling manager's decision."}
            if autonomous_inbox else
            evaluate_career_seller_bid(conn,career_id=career_id,
                player_id=player_id,seller_club_id=seller,offer_fee=offered_fee,
                buying_club_id=buying_club_id))
        if seller_review["decision"]=="await_manager":
            decision={"reason":seller_review["reason"]}
            status="proposed"
            counter=None
        elif seller_review["decision"]=="legacy":
            decision=offer_result(offered_fee,ref,available,seller_stance)
            if decision["status"]=="blocked":raise ValueError(decision["reason"])
            if decision["status"]=="acceptable_for_discussion":
                status="accepted_pending_contract"
            elif decision["status"]=="counteroffer":
                status="countered"
            elif decision["status"]=="rejected":
                status="rejected"
            else:
                status="proposed"
            counter=decision.get("asking") if status=="countered" else None
        else:
            if seller_review["decision"]=="review":
                # Record the real submitted offer, but NEVER assume a seller
                # accepted before contract, listing and finances are known.
                # The manager can complete the seller facts and explicitly
                # advance this offer from the Career Desk later.
                decision={"reason":"Awaiting selling-club review: "+seller_review["reason"]}
                status="proposed"
                counter=None
            else:
                decision={"reason":seller_review["reason"]}
                status={"accept":"accepted_pending_contract",
                        "negotiate":"countered","reject":"rejected"}[seller_review["decision"]]
                counter=seller_review.get("asking_price") if status=="countered" else None
                if counter is None and status=="countered":
                    raise ValueError("Seller has no established asking price")
        if counter is not None and counter>available:
            status="rejected"
            counter=None
        oid=conn.execute("""INSERT INTO world_career_offers
            (career_id,request_key,player_id,buying_club_id,selling_club_id,offered_fee,
             demanded_fee,status,agreement_date,source_rating,economy_version)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (career_id,request_key,player_id,buying_club_id,seller,offered_fee,
             counter,status,agreement_date,overall,career[1])).lastrowid
        if seller_review["decision"] not in ("legacy","review","await_manager"):
            save_offer_decision(conn,career_id=career_id,offer_id=oid,
                player_id=player_id,result=seller_review)
        if modern_offer:
            snapshot_offer_protocol(conn,career_id=career_id,offer_id=oid)
        conn.execute("INSERT INTO world_career_offer_events(offer_id,event_type,detail) VALUES(?,?,?)",
                     (oid,status,decision["reason"]))
        if ai_bid_snapshot is not None:
            # Keep the exact club-specific price rationale in the SAME
            # transaction as the offer; historical deals remain untouched.
            conn.execute("""INSERT INTO world_career_offer_events
                (offer_id,event_type,detail) VALUES(?,?,?)""",
                (oid,"ai_bid_pricing",json.dumps(ai_bid_snapshot,
                    sort_keys=True,separators=(",",":"))))
        # Normal legacy offers remain untouched. Timed-mode offers are
        # enrolled only when they are CREATED during an open window.
        # Never auto-import historical deals or let a duplicate request
        # create another window membership.
        from world_preseason_window import attach_offer_to_window
        attach_offer_to_window(conn,career_id=career_id,offer_id=oid)
        return oid
    return _transaction(conn,action)


def review_pending_seller_offer(conn, *, career_id, offer_id):
    """Reassess a submitted offer only after sufficient seller facts exist.

    The initial proposed offer is retained even if critical selling-club facts
    are unknown. Player consent/agent talks remain separate later stages.
    Uses the same documented seller and board evaluator as initial bids.
    """
    # Timed-mode careers disallow every negotiation mutation at the deadline.
    # Untouched legacy careers preserve the original workflow.
    from world_preseason_window import assert_window_allows_negotiation
    assert_window_allows_negotiation(conn,career_id=career_id)

    from world_career_selling import (
        evaluate_career_seller_bid,save_offer_decision,offer_decision)
    def action():
        row=_one(conn,"""SELECT o.player_id,o.selling_club_id,o.buying_club_id,
            o.offered_fee,o.status,c.manager_club_id
            FROM world_career_offers o JOIN world_career_saves c
                ON c.career_id=o.career_id
            WHERE o.career_id=? AND o.offer_id=? AND c.state='sandbox'""",
            (career_id,offer_id))
        if not row:raise ValueError("Offer not found in this saved career")
        player,seller,buyer,fee,status,manager=row
        if manager not in (buyer,seller):
            raise ValueError("Only the manager's current club can request a selling-club review")
        if status!="proposed":
            raise ValueError("Only an offer awaiting the seller's decision can be reviewed")
        if offer_decision(conn,offer_id):
            raise ValueError("A selling-club decision has already been recorded")
        reg=_one(conn,"""SELECT club_id FROM world_career_registrations
            WHERE career_id=? AND player_id=?""",(career_id,player))
        if reg is None or reg[0]!=seller:
            raise ValueError("The player's registration changed while this offer was pending")
        # The submitted fee already reserves budget in pending state.
        available=budget_remaining(conn,career_id,buyer)+fee
        if fee>available:
            raise ValueError("Buying club no longer has enough unreserved funds for its offer")
        result=evaluate_career_seller_bid(conn,career_id=career_id,
            player_id=player,seller_club_id=seller,offer_fee=fee,
            buying_club_id=buyer)
        if result["decision"]=="legacy":
            raise ValueError("This offer belongs to enhanced selling-club review")
        if result["decision"]=="review":
            raise ValueError("Seller information still needed: "+result["reason"])
        new_status={"accept":"accepted_pending_contract",
                    "negotiate":"countered","reject":"rejected"}[result["decision"]]
        demand=result.get("asking_price") if new_status=="countered" else None
        if new_status=="countered" and demand is None:
            raise ValueError("Selling club cannot counter without an asking price")
        if demand is not None and demand>available:
            new_status="rejected"
            demand=None
        conn.execute("""UPDATE world_career_offers SET status=?,demanded_fee=?
            WHERE offer_id=?""",(new_status,demand,offer_id))
        save_offer_decision(conn,career_id=career_id,offer_id=offer_id,
            player_id=player,result=result)
        conn.execute("""INSERT INTO world_career_offer_events
            (offer_id,event_type,detail) VALUES(?,?,?)""",
            (offer_id,new_status,result["reason"]))
        return new_status
    return _transaction(conn,action)


def accept_counter(conn, *, career_id, offer_id):
    """Buyer accepts counter subject to *existing* reservations, then contract talks."""
    # Timed-mode careers disallow every negotiation mutation at the deadline.
    # Untouched legacy careers preserve the original workflow.
    from world_preseason_window import assert_window_allows_negotiation
    assert_window_allows_negotiation(conn,career_id=career_id)

    def action():
        o=_one(conn,"""SELECT buying_club_id,offered_fee,demanded_fee,status
            FROM world_career_offers WHERE career_id=? AND offer_id=?""",(career_id,offer_id))
        if not o or o[3]!="countered":raise ValueError("No open counteroffer")
        # Counter amount is already reserved. Check global consistency.
        if budget_remaining(conn,career_id,o[0])<0:raise ValueError("Insufficient unreserved funds")
        from world_career_transfer_protocol import offer_uses_five_stages
        if not offer_uses_five_stages(conn,offer_id):
            from world_career_board_policy import career_board_decision,require_board_approval
            refrow=_one(conn,"""SELECT c.dataset_id,of.player_id FROM world_career_saves c
            JOIN world_career_offers of ON of.career_id=c.career_id
            WHERE of.career_id=? AND of.offer_id=?""",(career_id,offer_id))
            value,_=_player_reference(conn,refrow[0],refrow[1])
            require_board_approval(career_board_decision(conn,career_id=career_id,
                club_id=o[0],offer_fee=o[2],market_value=value,stage="fee"))
        from world_career_selling import offer_decision
        seller_snapshot=offer_decision(conn,offer_id)
        if seller_snapshot is not None:
            if seller_snapshot["career_id"]!=career_id:
                raise ValueError("Seller decision belongs to another career")
            if seller_snapshot["effective_decision"]!="negotiate":
                raise ValueError("No valid selling-club counteroffer to accept")
            last_revised=conn.execute("""SELECT detail FROM world_career_offer_events
                WHERE offer_id=? AND event_type='seller_revised_asking'
                ORDER BY event_id DESC LIMIT 1""",(offer_id,)).fetchone()
            revised_price=(int(last_revised[0]) if last_revised and
                str(last_revised[0]).isdigit() else None)
            if revised_price is not None and revised_price==o[2]:
                pass  # Seller explicitly lowered its asking price this round.
            elif seller_snapshot["asking_price"] is None or o[2] < seller_snapshot["asking_price"]:
                raise ValueError("Counteroffer is below the selling club's stated asking price")
        conn.execute("""UPDATE world_career_offers SET status='accepted_pending_contract',
            offered_fee=demanded_fee,demanded_fee=NULL WHERE offer_id=?""",(offer_id,))
        conn.execute("INSERT INTO world_career_offer_events(offer_id,event_type) VALUES(?,?)",
                     (offer_id,"counter_accepted"))
    return _transaction(conn,action)


def settle_future_deal(conn, *, career_id, offer_id, weekly_wage, agreement_date):
    """Reserve wages and fee; NEVER move the player in the active PES season.

    'agreed_future' is not completed and registration remains unchanged.
    """
    # Timed-mode careers disallow every negotiation mutation at the deadline.
    # Untouched legacy careers preserve the original workflow.
    from world_preseason_window import assert_window_allows_negotiation
    assert_window_allows_negotiation(conn,career_id=career_id)

    if not isinstance(weekly_wage,int) or weekly_wage<0:
        raise ValueError("Wage must be a nonnegative GBP integer")
    date.fromisoformat(agreement_date)
    def action():
        o=_one(conn,"""SELECT player_id,buying_club_id,selling_club_id,offered_fee,status
            FROM world_career_offers WHERE career_id=? AND offer_id=?""",(career_id,offer_id))
        if not o or o[4]!="accepted_pending_contract":raise ValueError("No pending contract deal")
        # Domain-level guarantee, regardless of which route finalises.
        # BEGIN IMMEDIATE serialises competing sign-off attempts. A player
        # cannot enter two binding future agreements in the same career.
        conflicting=_one(conn,"""SELECT offer_id FROM world_career_offers
            WHERE career_id=? AND player_id=? AND offer_id<>?
            AND status IN ('agreed_future','completed') LIMIT 1""",
            (career_id,o[0],offer_id))
        if conflicting:
            raise ValueError("Player has already signed for another club")
        from world_player_morale import is_unavailable
        from world_preseason_window import window_snapshot
        snap=window_snapshot(conn,career_id=career_id)
        if snap["state"]!="not_started" and is_unavailable(
                conn,career_id=career_id,window_id=snap["window_id"],
                player_id=o[0]):
            raise ValueError("Player has refused to play and is unavailable for this PES season")
        agent=_one(conn,"""SELECT status,proposed_wage_weekly
            FROM world_career_agent_terms WHERE career_id=? AND offer_id=?""",
            (career_id,offer_id))
        if not agent or agent[0]!="accepted" or agent[1]!=weekly_wage:
            raise ValueError("Player/agent terms must be accepted before the agreement can be finalised")
        career=_one(conn,"SELECT pes_lock_date,next_summer_date FROM world_career_saves WHERE career_id=?",(career_id,))
        if career is None:raise ValueError("Unknown career")
        wages=wage_budget_breakdown(conn,career_id,o[1])
        if weekly_wage>wages["remaining"]:
            raise ValueError("Wage offer exceeds available weekly wage budget")
        if budget_remaining(conn,career_id,o[1])<0:
            raise ValueError("Fee reservations exceed available budget")
        from world_career_transfer_protocol import (
            offer_uses_five_stages,final_board_exception,record_final_review)
        modern=offer_uses_five_stages(conn,offer_id)
        if modern:
            final_review=final_board_exception(conn,career_id=career_id,
                offer_id=offer_id,weekly_wage=weekly_wage)
        else:
            from world_career_board_policy import career_board_decision,require_board_approval
            ds=_one(conn,"SELECT dataset_id FROM world_career_saves WHERE career_id=?",(career_id,))[0]
            valuation,_=_player_reference(conn,ds,o[0])
            require_board_approval(career_board_decision(conn,career_id=career_id,
                club_id=o[1],offer_fee=o[3],market_value=valuation,
                offered_wage=weekly_wage,wage_headroom=wages["remaining"],stage="terms"))
        effective=allowed_effective_date(date.fromisoformat(agreement_date),date.fromisoformat(agreement_date),
            date.fromisoformat(career[0]),date.fromisoformat(career[1]),active_pes=True)
        conn.execute("""UPDATE world_career_offers
            SET status='agreed_future',offered_wage_weekly=?,agreement_date=?,effective_date=?
            WHERE offer_id=?""",(weekly_wage,agreement_date,effective.isoformat(),offer_id))
        if modern:
            manager=_one(conn,"SELECT manager_club_id FROM world_career_saves WHERE career_id=?",
                (career_id,))[0]
            record_final_review(conn,career_id=career_id,offer_id=offer_id,
                manager_club_id=manager,decision=final_review)
        conn.execute("INSERT INTO world_career_offer_events(offer_id,event_type,detail) VALUES(?,?,?)",
                     (offer_id,"future_deal_agreed",
                      "Human manager confirmed personal terms; board exception review passed; PES registration unchanged"
                      if modern else "PES registration not changed"))
        return effective.isoformat()
    return _transaction(conn,action)


def agent_terms(conn, *, career_id, offer_id):
    """Create/read fictional agent expectations. No verified salary inference."""
    from world_preseason_window import assert_window_allows_negotiation
    assert_window_allows_negotiation(conn,career_id=career_id)

    from world_player_decisions import (
        DECISION_VERSION,DECISION_V2_VERSION,agent_minimum_wage,
        agent_minimum_wage_v2)
    policy=career_player_policy(conn,career_id)
    # Initialise sport and reputation reads BEFORE entering SQLite's immediate
    # transaction; source initialisers contain commits and must not run inside it.
    choice=None
    if policy["version"] in (DECISION_VERSION,DECISION_V2_VERSION):
        choice=player_move_interest(conn,career_id=career_id,offer_id=offer_id)
    def current_record():
        cursor=conn.execute("""SELECT * FROM world_career_agent_terms
            WHERE offer_id=? AND career_id=?""",(offer_id,career_id))
        row=cursor.fetchone()
        return (dict(zip((col[0] for col in cursor.description),row))
                if row is not None else None)
    def action():
        o=_one(conn,"""SELECT o.status,o.player_id,c.dataset_id FROM world_career_offers o
            JOIN world_career_saves c ON c.career_id=o.career_id
            WHERE o.career_id=? AND o.offer_id=?""",(career_id,offer_id))
        if not o or o[0] not in ("accepted_pending_contract","agreed_future"):
            raise ValueError("Club fee agreement required before agent talks")
        row=current_record()
        if row:return row
        _ref,overall=_player_reference(conn,o[2],o[1])
        # Game economy only: source overall is not a claim about real wages.
        if overall is None:
            raise ValueError("Cannot generate fictional agent terms without a sourced rating")
        demand=int(round((1000*2**((overall-55)/8))/500)*500)
        demand=max(1000,min(demand,250_000))
        if policy["version"] in (DECISION_VERSION,DECISION_V2_VERSION):
            if not choice["can_negotiate"]:
                raise ValueError("Player will not open agent talks: "+choice["reason"])
            adjusted=(agent_minimum_wage_v2(choice=choice)
                      if policy["version"]==DECISION_V2_VERSION else
                      agent_minimum_wage(
                          base_wage=demand,choice=choice,
                          competing_bid=choice.get("competing_pressure",0)>=13))
            if adjusted is None:
                raise ValueError("Unassessed personal-term demand")
            demand=max(1000,adjusted)
        conn.execute("""INSERT INTO world_career_agent_terms
            (offer_id,career_id,demanded_wage_weekly,status)
            VALUES (?,?,?,'awaiting_offer')""",(offer_id,career_id,demand))
        source_label=(
            "player-decisions-v2; explicit current wages, squad role and renewal assumptions"
            if policy["version"]==DECISION_V2_VERSION else
            "player-decisions-v1; provisional historical prestige and role"
            if policy["version"]==DECISION_VERSION else
            "Legacy fictional wage scale")
        conn.execute("""INSERT INTO world_career_offer_events(offer_id,event_type,detail)
            VALUES (?,'agent_opened',?)""",
            (offer_id,f"{source_label}: agent requests £{demand}/week"))
        return current_record()
    return _transaction(conn,action)


def negotiate_agent(conn, *, career_id, offer_id, weekly_wage, contract_years,
                    agreement_date, role_promise="unspecified"):
    """Agent rejects low wages, counters intermediate offers and accepts suitable ones.

    Accepted terms create an agreement for next summer, but never move player.
    No claim that a real-world player consented.
    """
    # Timed-mode careers disallow every negotiation mutation at the deadline.
    # Untouched legacy careers preserve the original workflow.
    from world_preseason_window import assert_window_allows_negotiation
    assert_window_allows_negotiation(conn,career_id=career_id)

    if not isinstance(weekly_wage,int) or isinstance(weekly_wage,bool) or weekly_wage<0:
        raise ValueError("Wage must be a nonnegative integer")
    if not isinstance(contract_years,int) or contract_years not in (1,2,3,4,5):
        raise ValueError("Contract duration must be 1–5 years")
    from world_player_decisions import (
        DECISION_VERSION,DECISION_V2_VERSION,contract_length_consideration,
        ROLES,role_satisfies,canonical_role)
    if role_promise not in ROLES:
        raise ValueError("Unsupported playing-time promise")
    # Map the legacy 'important' promise to the second tier in new offers.
    role_promise=canonical_role(role_promise)
    date.fromisoformat(agreement_date)
    policy=career_player_policy(conn,career_id)
    interest=player_move_interest(conn,career_id=career_id,offer_id=offer_id)
    if not interest["can_negotiate"]:
        raise ValueError("Player is not currently willing to negotiate: "+interest["reason"])
    required=interest.get("required_role","none")
    if required=="key_player" and not role_satisfies(role_promise,required):
        raise ValueError("This player requires a Key Player guarantee before agent talks")
    if required in ("regular_starter","important") and not role_satisfies(role_promise,required):
        raise ValueError("This move requires a Regular Starter or Key Player first-team guarantee before agent talks")
    if policy["version"]==DECISION_VERSION:
        with_role=player_move_interest(
            conn,career_id=career_id,offer_id=offer_id,role_promise=role_promise)
        if not with_role["can_negotiate"] or with_role["decision"]!="open_to_talks":
            raise ValueError("Player's career requirements have not been met: "+with_role["reason"])
    elif policy["version"]==DECISION_V2_VERSION:
        with_offer=player_move_interest(
            conn,career_id=career_id,offer_id=offer_id,
            role_promise=role_promise,offered_wage=weekly_wage)
        if not with_offer["can_negotiate"]:
            raise ValueError("Player refuses this offer: "+with_offer["reason"])
        if with_offer["decision"]=="needs_assurances" and not role_satisfies(
                role_promise,with_offer["required_role"]):
            raise ValueError("Required squad role has not been promised")
        # Wages below the player's threshold create a counter rather than
        # an automatic acceptance; missing salary is never treated as consent.
    if _one(conn,"SELECT 1 FROM world_career_agent_terms WHERE offer_id=? AND career_id=?",(offer_id,career_id)) is None:
        agent_terms(conn,career_id=career_id,offer_id=offer_id)
    def action():
        row=_one(conn,"""SELECT t.demanded_wage_weekly,t.rounds,t.status,o.status,o.buying_club_id
            FROM world_career_agent_terms t JOIN world_career_offers o ON o.offer_id=t.offer_id
            WHERE t.career_id=? AND t.offer_id=?""",(career_id,offer_id))
        if not row or row[3]!="accepted_pending_contract":
            raise ValueError("This negotiation is no longer awaiting player terms")
        demand,rounds=row[0],row[1]
        if rounds>=5:raise ValueError("Maximum agent rounds reached; withdraw and renegotiate later")
        if interest["decision"]=="needs_assurances" and policy["version"] not in (DECISION_VERSION,DECISION_V2_VERSION):
            player=_one(conn,"SELECT player_id FROM world_career_offers WHERE offer_id=? AND career_id=?",
                (offer_id,career_id))
            dataset=_one(conn,"SELECT dataset_id FROM world_career_saves WHERE career_id=?",(career_id,))[0]
            _,overall=_player_reference(conn,dataset,player[0])
            if overall is not None:
                base=max(1000,min(int(round((1000*2**((overall-55)/8))/500)*500),250_000))
                demand=max(demand,int(round(base*1.25/500)*500))
                conn.execute("""UPDATE world_career_agent_terms SET demanded_wage_weekly=?
                    WHERE offer_id=?""",(demand,offer_id))
        if policy["version"] in (DECISION_VERSION,DECISION_V2_VERSION):
            issue=contract_length_consideration(
                phase=interest["player_phase"],years=contract_years)
            if issue:
                demand=max(demand,round((demand*1.10)/500)*500)
                conn.execute("""UPDATE world_career_agent_terms
                    SET demanded_wage_weekly=? WHERE offer_id=? AND career_id=?""",
                    (demand,offer_id,career_id))
        wages=wage_budget_breakdown(conn,career_id,row[4])
        if weekly_wage>wages["remaining"]:
            raise ValueError("Wage offer exceeds available wage budget")
        if weekly_wage>=demand:
            conn.execute("""UPDATE world_career_agent_terms
                SET proposed_wage_weekly=?,contract_years=?,role_promise=?,
                    rounds=rounds+1,status='accepted',
                updated_at=CURRENT_TIMESTAMP WHERE offer_id=?""",
                (weekly_wage,contract_years,role_promise,offer_id))
            conn.execute("""INSERT INTO world_career_offer_events(offer_id,event_type,detail)
                VALUES (?,'agent_accepted',?)""",(offer_id,f"Fictional agent accepted £{weekly_wage}/week for {contract_years} years"))
            return "accepted"
        if weekly_wage<demand*0.6:
            status="rejected"
        else:
            status="countered"
        conn.execute("""UPDATE world_career_agent_terms SET proposed_wage_weekly=?,
            contract_years=?,role_promise=?,rounds=rounds+1,status='countered',
            updated_at=CURRENT_TIMESTAMP WHERE offer_id=?""",(weekly_wage,contract_years,role_promise,offer_id))
        conn.execute("""INSERT INTO world_career_offer_events(offer_id,event_type,detail)
            VALUES (?,?,?)""",(offer_id,"agent_"+status,
            f"Game agent requests £{demand}/week; previous offer £{weekly_wage}/week"))
        return status
    # An agent accepting terms is NOT manager confirmation. The manager must
    # explicitly confirm the future agreement through a separate POST action.
    return _transaction(conn,action)



def confirm_future_agreement(conn, *, career_id, offer_id, agreement_date):
    """Explicit manager approval after simulated player/agent acceptance.

    Does not process payment or alter active PES registration.
    """
    # Timed-mode careers disallow every negotiation mutation at the deadline.
    # Untouched legacy careers preserve the original workflow.
    from world_preseason_window import assert_window_allows_negotiation
    assert_window_allows_negotiation(conn,career_id=career_id)

    terms=_one(conn,"""SELECT t.status,t.proposed_wage_weekly FROM world_career_agent_terms t
        JOIN world_career_offers o ON o.offer_id=t.offer_id
        WHERE o.career_id=? AND o.offer_id=? AND o.status='accepted_pending_contract'""",
        (career_id,offer_id))
    if not terms or terms[0]!="accepted" or terms[1] is None:
        raise ValueError("Agent terms must be accepted before manager confirms the deal")
    return settle_future_deal(conn,career_id=career_id,offer_id=offer_id,
        weekly_wage=terms[1],agreement_date=agreement_date)


def _competition_pressure(conn, *, career_id, offer_id, player_id,
                           buyer_club_id, buyer_sporting, buyer_prestige):
    """Only *recorded* same-career rival offers count, never advisory interest."""
    from world_player_decisions import competitor_advantage
    from world_reputation_progression import current_career_appeal
    rivals=conn.execute("""SELECT DISTINCT buying_club_id FROM world_career_offers
        WHERE career_id=? AND player_id=? AND offer_id<>? AND buying_club_id<>?
        AND status IN ('proposed','countered','accepted_pending_contract','agreed_future')""",
        (career_id,player_id,offer_id,buyer_club_id)).fetchall()
    best=0
    for (rival_id,) in rivals:
        p=current_career_prestige(conn,career_id,rival_id)
        sporting=current_career_appeal(conn,career_id,rival_id)
        if not p or not sporting or sporting["score"] is None:
            continue
        best=max(best,competitor_advantage(
            rival_sporting=sporting["score"],rival_prestige=p["score"],
            buyer_sporting=buyer_sporting,buyer_prestige=buyer_prestige))
    return best


def player_move_interest(conn, *, career_id, offer_id, role_promise="unspecified",
                         offered_wage=None):
    """Player-interest signal using career-selected, versioned decision rules.

    Older careers stay on the pre-existing sporting-only algorithm. New opt-in
    career saves use fixed provisional prestige snapshots, source player age and
    rating, playable-role assurances and actual recorded sandbox rival offers.
    No rule treats a fictional preference as a real player's expressed consent.
    """
    row=_one(conn,"""SELECT o.player_id,o.buying_club_id,o.selling_club_id,
            c.dataset_id,o.agreement_date
        FROM world_career_offers o JOIN world_career_saves c ON c.career_id=o.career_id
        WHERE o.career_id=? AND o.offer_id=?""",(career_id,offer_id))
    if not row:
        raise ValueError("Offer not found")
    from world_reputation_v2 import initialize_pyramid,assess_player_interest
    from world_reputation_progression import initialize_progression,current_career_appeal
    from world_player_decisions import (
        DECISION_VERSION,DECISION_V2_VERSION,evaluate_player_choice,
        evaluate_player_choice_v2)
    initialize_pyramid(conn)
    initialize_progression(conn)
    buyer_profile=current_career_appeal(conn,career_id,row[1])
    seller_profile=current_career_appeal(conn,career_id,row[2])
    tiers=dict(conn.execute("SELECT competition_id,tier FROM world_competitions").fetchall())
    buyer=tiers.get(buyer_profile["competition_id"]) if buyer_profile else None
    seller=tiers.get(seller_profile["competition_id"]) if seller_profile else None
    _reference,overall=_player_reference(conn,row[3],row[0])
    policy=career_player_policy(conn,career_id)
    if policy["version"] in (DECISION_VERSION,DECISION_V2_VERSION):
        buyer_prestige=current_career_prestige(conn,career_id,row[1])
        seller_prestige=current_career_prestige(conn,career_id,row[2])
        player=_one(conn,"SELECT birth_date FROM world_players WHERE player_id=?",(row[0],))
        age=age_on(player[0],row[4]) if player else None
        rival_pressure=0
        if (buyer_profile and buyer_prestige and
            buyer_profile["score"] is not None):
            rival_pressure=_competition_pressure(
                conn,career_id=career_id,offer_id=offer_id,player_id=row[0],
                buyer_club_id=row[1],buyer_sporting=buyer_profile["score"],
                buyer_prestige=buyer_prestige["score"])
        common=dict(
            buyer_tier=buyer,seller_tier=seller,
            buyer_score=buyer_profile["score"] if buyer_profile else None,
            seller_score=seller_profile["score"] if seller_profile else None,
            buyer_prestige=buyer_prestige["score"] if buyer_prestige else None,
            seller_prestige=seller_prestige["score"] if seller_prestige else None,
            overall=overall,age=age,role_promise=role_promise,
            competitor_pressure=rival_pressure)
        if policy["version"]==DECISION_V2_VERSION:
            facts=player_circumstances(conn,career_id,row[0])
            european=offer_europe_context(conn,career_id,offer_id)
            result=evaluate_player_choice_v2(
                **common,
                buyer_europe=european["buyer_europe"] if european else "unknown",
                seller_europe=european["seller_europe"] if european else "unknown",
                current_wage=facts["current_wage_weekly"] if facts else None,
                current_role=facts["current_role"] if facts else "unknown",
                transfer_listed=facts["transfer_listed"] if facts else None,
                renewal_status=facts["renewal_status"] if facts else "unknown",
                offered_wage=offered_wage)
        else:
            result=evaluate_player_choice(**common)
        descriptions={
            "uninterested":"Not interested in this move",
            "needs_assurances":"Requires playing-time assurances",
            "open_to_talks":"Open to personal terms (simulation)",
            "review":"Player circumstances require evidence or explicit assumptions",
        }
        signal=descriptions.get(result["decision"],"Unassessed")
        if policy["version"]==DECISION_V2_VERSION and result["decision"]=="needs_assurances":
            signal={
                "wage":"Higher wages required",
                "role":"Squad-role guarantee required",
                "wage_and_role":"Higher wages and role guarantee required",
            }.get(result.get("issue"),signal)
        return {**result,"signal":signal,
                "prestige_source_version":policy["prestige_version"],
                "prestige_review_status":(
                    buyer_prestige["review_status"] if buyer_prestige else "unknown")}
    outcome=assess_player_interest(
        buyer_tier=buyer,seller_tier=seller,
        buyer_score=buyer_profile["score"] if buyer_profile else None,
        seller_score=seller_profile["score"] if seller_profile else None,
        player_overall=overall)
    descriptions={
        "uninterested":"Not interested in this move",
        "needs_assurances":"Requires career assurances",
        "open_to_talks":"Open to talks (provisional)",
        "review":"Interest cannot be assessed",
    }
    return {"signal":descriptions.get(outcome["decision"],"Unassessed"),
            "reason":outcome["reason"],"decision":outcome["decision"],
            "can_negotiate":outcome["can_negotiate"],
            "policy_version":policy["version"],"required_role":
            "important" if outcome["decision"]=="needs_assurances" else "none"}


def withdraw_offer(conn, *, career_id, offer_id):
    """Releases reserved transfer/wage capacity; does not modify registrations."""
    # Timed-mode careers disallow every negotiation mutation at the deadline.
    # Untouched legacy careers preserve the original workflow.
    from world_preseason_window import assert_window_allows_negotiation
    assert_window_allows_negotiation(conn,career_id=career_id)

    def action():
        row=_one(conn,"SELECT status FROM world_career_offers WHERE career_id=? AND offer_id=?",
                 (career_id,offer_id))
        if not row or row[0] not in ("proposed","countered","accepted_pending_contract","agreed_future"):
            raise ValueError("Offer cannot be withdrawn")
        from world_career_transfer_protocol import offer_uses_five_stages
        if row[0]=="agreed_future" and offer_uses_five_stages(conn,offer_id):
            raise ValueError("A manager-confirmed future agreement is binding; it cannot be silently cancelled")
        conn.execute("UPDATE world_career_offers SET status='withdrawn' WHERE offer_id=?",(offer_id,))
        conn.execute("INSERT INTO world_career_offer_events(offer_id,event_type) VALUES(?,?)",
                     (offer_id,"withdrawn"))
    return _transaction(conn,action)


def reject_incoming_offer(conn, *, career_id, offer_id):
    """Human selling manager rejects a live AI offer, without moving a player.

    This is a genuine fee/transfer rejection, unlike a buyer's withdrawal.
    The AI may consider one higher proposal on a *later simulation* if its
    budget and explicit seller circumstances justify another approach.
    """
    # Timed-mode careers disallow every negotiation mutation at the deadline.
    # Untouched legacy careers preserve the original workflow.
    from world_preseason_window import assert_window_allows_negotiation
    assert_window_allows_negotiation(conn,career_id=career_id)

    def action():
        row=_one(conn,"""SELECT o.status,o.selling_club_id,o.buying_club_id,
            c.manager_club_id FROM world_career_offers o
            JOIN world_career_saves c ON c.career_id=o.career_id
            WHERE o.career_id=? AND o.offer_id=? AND c.state='sandbox'""",
            (career_id,offer_id))
        if not row or row[1]!=row[3] or row[2]==row[3]:
            raise ValueError("Only the human selling manager can reject an incoming AI offer")
        if row[0] not in ("proposed","countered","accepted_pending_contract"):
            raise ValueError("Only an unsigned incoming bid may be rejected")
        conn.execute("""UPDATE world_career_offers
            SET status='rejected' WHERE offer_id=?""",(offer_id,))
        conn.execute("""INSERT INTO world_career_offer_events
            (offer_id,event_type,detail) VALUES(?,?,?)""",
            (offer_id,"manager_rejected",
             "Human selling manager declined the AI offer; future re-bids are optional and capped."))
        return "rejected"
    return _transaction(conn,action)


def ai_interest(conn, *, career_id, player_id, top=4):
    """Interested fictional buyers must afford a credible squad upgrade.

    Club need is evaluated against *rated* positional depth rather than money
    alone. Missing source positions get a neutral score, not fabricated needs.
    The listed clubs are possible competitors, not offers or completed deals.
    """
    from collections import defaultdict
    from world_ai_bidding import position_family,club_need
    if type(top) is not int or not 1<=top<=25:
        raise ValueError("Choose 1–25 candidate clubs")
    career=_one(conn,"SELECT dataset_id FROM world_career_saves WHERE career_id=?",(career_id,))
    if not career:raise ValueError("Unknown career")
    reg=_one(conn,"SELECT club_id FROM world_career_registrations WHERE career_id=? AND player_id=?",
             (career_id,player_id))
    if not reg:raise ValueError("Unknown player")
    ref,overall=_player_reference(conn,career[0],player_id)
    if ref is None or overall is None or ref<=0:return []
    group_row=_one(conn,"SELECT primary_position FROM world_players WHERE player_id=?",
                   (player_id,))
    target_family=position_family(group_row[0]) if group_row else None
    all_scores=defaultdict(list)
    positions=defaultdict(lambda:defaultdict(list))
    for cid,ovr,position in conn.execute("""SELECT r.club_id,x.overall,p.primary_position
        FROM world_career_registrations r
        JOIN world_dataset_ratings x ON x.player_id=r.player_id
          AND x.dataset_id=?
        JOIN world_players p ON p.player_id=r.player_id
        WHERE r.career_id=? AND x.overall IS NOT NULL""",
        (career[0],career_id)):
        if type(ovr) is int and 1<=ovr<=99:
            all_scores[cid].append(ovr)
            known=position_family(position)
            if known is not None:
                positions[cid][known].append(ovr)
    clubs=conn.execute("""SELECT c.club_id,c.name FROM world_career_club_ledger l
         JOIN world_clubs c ON c.club_id=l.club_id WHERE l.career_id=? AND c.club_id<>?
         ORDER BY c.name""",(career_id,reg[0])).fetchall()
    matches=[]
    for cid,name in clubs:
        ratings=sorted(all_scores.get(cid,()),reverse=True)
        if len(ratings)<8:continue
        threshold=ratings[min(15,len(ratings)-1)]
        if overall+2<threshold:continue
        spare=budget_remaining(conn,career_id,cid)
        if spare<round(ref*0.85):continue
        group_ratings=(positions[cid].get(target_family,[])
                       if target_family is not None else ratings[:12])
        need=club_need(overall=overall,ratings=group_ratings,
                       position_group=target_family)
        matches.append({"club_id":cid,"club_name":name,
            "available_budget":spare,"squad_fit_floor":threshold,
            "need_score":need["score"],"need_reason":need["reason"],
            "position_family":target_family,
            "rated_position_players":need.get("rated_position_players")})
    return sorted(matches,key=lambda x:
        (-x["need_score"],-min(5,x["available_budget"]/ref),x["club_name"]))[:top]


def simulate_ai_bids(conn, *, career_id, player_id, max_bids=2, report=False):
    """User-triggered AI offers with credible demand and limited escalation.

    One round per club per simulation. Only a *recorded seller rejection*
    allows a later higher offer, up to two revised bids. A counter, pending
    seller information, accepted terms or binding deal never auto-resets.
    Old ai-v1 records and all original registrations remain intact.
    """
    from world_ai_bidding import determine_offer,MAX_ROUNDS,ACTIVE_STATES
    from world_career_selling import get_seller_assumptions
    if type(max_bids) is not int or not 1<=max_bids<=3:
        raise ValueError("max_bids must be 1 to 3")
    career=_one(conn,"SELECT dataset_id,manager_club_id FROM world_career_saves WHERE career_id=?",
                (career_id,))
    if career is None:raise ValueError("Unknown career")
    reg=_one(conn,"SELECT club_id FROM world_career_registrations WHERE career_id=? AND player_id=?",
             (career_id,player_id))
    if reg is None:raise ValueError("Player is not registered in this saved career")
    model_value,overall=_player_reference(conn,career[0],player_id)
    if model_value is None or overall is None or model_value<=0:
        answer={"offer_ids":[],"new":0,"increased":0,"existing":0,"eligible":0,
            "demand_premium_pct":0,"reason":
            "This player lacks sufficient source ratings or valuation to simulate credible AI bids.",
            "failures":[]}
        return answer if report else []

    recorded=get_seller_assumptions(conn,career_id,player_id)
    valuation=(recorded["market_value"] if recorded and
               recorded["market_value"] and recorded["market_value"]>0 else model_value)
    # Limit the pool to a credible number of genuinely suited buyers, rather
    # than treating all 91 other clubs as desperate for the same individual.
    clubs=[c for c in ai_interest(conn,career_id=career_id,player_id=player_id,top=8)
           if c["club_id"]!=career[1]]
    eligible=len(clubs)
    ids=[]
    new_count=0
    raised_count=0
    old_count=0
    reasons=[]
    no_interest_reason=("No eligible AI buyers: no other club met both the "
        "player's rated squad-fit threshold and the modelled transfer budget "
        "for this bid. No transfer was invented.")
    for club in clubs:
        if new_count>=max_bids:break
        cid=club["club_id"]
        base_key=f"ai-v1-{player_id}-{cid}"
        history=conn.execute("""SELECT offer_id,request_key,offered_fee,status
            FROM world_career_offers WHERE career_id=? AND player_id=?
            AND buying_club_id=?
            AND (request_key=? OR request_key LIKE ?)
            ORDER BY offer_id""",(career_id,player_id,cid,base_key,
                 f"ai-v2-{player_id}-{cid}-r%")).fetchall()
        if history:
            latest=history[-1]
            if latest[3]!="rejected":
                old_count+=1
                ids.append(latest[0])
                continue
            if len(history)>=MAX_ROUNDS:
                reasons.append(club["club_name"]+
                    ": maximum of three rejected bidding rounds reached.")
                continue
            # A manager explicitly determined to keep a player, without exit
            # pressure, will not field infinite bids just because it is cheap.
            if (recorded and recorded["seller_stance"]=="retain"
                    and not recorded["transfer_listed"]
                    and not recorded["player_wants_exit"]
                    and not recorded["board_enabled"]):
                reasons.append(club["club_name"]+
                    ": selling club has a firm recorded not-for-sale stance.")
                continue
            # Only a seller rejection can trigger higher terms. The next
            # transaction creates its own immutable event and unique key.
            round_number=len(history)+1
            prior_fee=latest[2]
            prior_offer_id=latest[0]
            key=f"ai-v2-{player_id}-{cid}-r{round_number}"
        else:
            round_number=1
            prior_fee=None
            prior_offer_id=None
            key=base_key
        active_rivals=_one(conn,"""SELECT COUNT(DISTINCT buying_club_id)
            FROM world_career_offers WHERE career_id=? AND player_id=?
            AND buying_club_id<>? AND status IN
            ('proposed','countered','accepted_pending_contract','agreed_future')""",
            (career_id,player_id,cid))[0]
        available=budget_remaining(conn,career_id,cid)
        price=determine_offer(career_id=career_id,player_id=player_id,
            club_id=cid,valuation=valuation,available_budget=available,
            need_score=int(club.get("need_score",50)),
            eligible_clubs=eligible,active_rival_clubs=active_rivals,
            seller_assumptions=recorded,prior_fee=prior_fee,
            round_number=round_number)
        if price["fee"] is None:
            reasons.append(club["club_name"]+": "+price["reason"])
            continue
        audit={**price,"prior_offer_id":prior_offer_id,
            "buyer_name":club["club_name"],
            "position_family":club.get("position_family"),
            "squad_fit_floor":club.get("squad_fit_floor"),
            "need_reason":club.get("need_reason"),
            "note":"Fictional deterministic club policy, not a verified real bid."}
        try:
            offer_id=propose_offer(conn,career_id=career_id,request_key=key,
                player_id=player_id,buying_club_id=cid,
                offered_fee=price["fee"],agreement_date=date.today().isoformat(),
                seller_stance="neutral",ai_bid_snapshot=audit)
            ids.append(offer_id)
            new_count+=1
            if prior_offer_id is not None:raised_count+=1
        except ValueError as exc:
            reasons.append(club["club_name"]+": "+str(exc))
    if new_count:
        parts=[f"{new_count} new AI offer"+("s" if new_count!=1 else "")+
               " recorded with club-specific valuations."]
        if raised_count:
            parts.append(f"{raised_count} improved after a previous rejection.")
        if eligible>1:
            parts.append(f"{eligible} credible interested clubs create competitive "
                         f"pressure (up to {min(14,(eligible-1)*3.5):g}% demand premium).")
        parts.append("See individual offers and pricing reasons under Negotiations.")
        reason=" ".join(parts)
    elif old_count and not reasons:
        reason=("No fresh bids: these clubs already have open or accepted offers. "
                "Reject a bid before that club can consider an improved offer.")
    elif eligible==0:
        # A buyer can cease to meet the funds filter *because its existing
        # pending offer has already reserved that money*. Don't tell the
        # manager there is no interest when actual offers remain on record.
        waiting=_one(conn,"""SELECT COUNT(DISTINCT buying_club_id)
            FROM world_career_offers WHERE career_id=? AND player_id=?
              AND request_key LIKE 'ai-v%'
              AND status IN ('proposed','countered','accepted_pending_contract',
                             'agreed_future')""",(career_id,player_id))[0]
        reason=(f"No fresh AI bids: {waiting} buyer club(s) already have "
                "open or accepted offers whose funds are reserved. "
                "These offers cannot rise unless they are rejected."
                if waiting else no_interest_reason)
    elif reasons:
        reason="No new bid: "+reasons[0]
        if old_count:reason+=f" {old_count} club(s) already have recorded offers."
    else:
        reason=("No new bids: interested clubs have already responded. "
                "Open offers must be resolved before fresh bids.")
    summary={"offer_ids":ids,"new":new_count,"increased":raised_count,
             "existing":old_count,"eligible":eligible,
             "demand_premium_pct":round(min(14,max(0,eligible-1)*3.5),2),
             "reason":reason,"failures":reasons}
    return summary if report else ids

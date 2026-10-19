"""Server-authoritative 30-minute *pre-season* window; additive career-only core.

The 30-minute wall clock is real, not a simulated PES match clock.
This module does NOT autonomously place AI bids or operate any public HTTP
route yet. It provides transaction-safe start/expiry/registration primitives
for the subsequent autonomous market + manager inbox integration.

IMPORTANT: A completed in-app registration never edits the Xbox PES file.
"""
import sqlite3
from datetime import datetime, timezone, timedelta

WINDOW_SECONDS = 30 * 60
WINDOW_VERSION = "preseason-live-30min-v1"

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_career_preseason_windows(
 window_id INTEGER PRIMARY KEY,
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 season_index INTEGER NOT NULL CHECK(season_index >= 1),
 started_at TEXT NOT NULL,
 deadline_at TEXT NOT NULL,
 closed_at TEXT,
 status TEXT NOT NULL CHECK(status IN ('open','closed')),
 duration_seconds INTEGER NOT NULL CHECK(duration_seconds=1800),
 policy_version TEXT NOT NULL,
 UNIQUE(career_id, season_index)
);
CREATE TABLE IF NOT EXISTS world_career_preseason_window_offers(
 window_id INTEGER NOT NULL REFERENCES world_career_preseason_windows(window_id),
 offer_id INTEGER NOT NULL UNIQUE REFERENCES world_career_offers(offer_id),
 tagged_at TEXT NOT NULL,
 PRIMARY KEY(window_id,offer_id)
);
CREATE TABLE IF NOT EXISTS world_career_preseason_registration_events(
 window_id INTEGER NOT NULL REFERENCES world_career_preseason_windows(window_id),
 offer_id INTEGER NOT NULL REFERENCES world_career_offers(offer_id),
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 from_club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 to_club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 fee_gbp INTEGER NOT NULL CHECK(fee_gbp>=0),
 weekly_wage_gbp INTEGER NOT NULL CHECK(weekly_wage_gbp>=0),
 pes_effective_date TEXT NOT NULL,
 recorded_at TEXT NOT NULL,
 PRIMARY KEY(window_id,offer_id),
 UNIQUE(window_id,player_id)
);
CREATE INDEX IF NOT EXISTS world_career_preseason_window_career
 ON world_career_preseason_windows(career_id,season_index);
"""

def initialise_preseason_windows(conn):
    """Additive schema; safe for existing saves and repeat initialisation."""
    conn.executescript(SCHEMA)
    conn.commit()


def _utc(now=None):
    if now is None:
        return datetime.now(timezone.utc)
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("A timezone-aware UTC clock is required")
    return now.astimezone(timezone.utc)


def _iso(ts):
    return ts.isoformat(timespec="seconds")


def _parse(value):
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def _row(conn,sql,params=()):
    c=conn.execute(sql,params)
    record=c.fetchone()
    return dict(zip((field[0] for field in c.description),record)) if record else None


def window_snapshot(conn, *, career_id, season_index=1, now=None):
    """Read-only inspection. A GET or page reload NEVER advances the market."""
    t=_utc(now)
    # Older isolated career tests and save adapters may not have run the
    # additive window migration yet. Such careers are still LEGACY and must
    # not fail negotiation requests just because the optional table is absent.
    # Real application connections call initialise_preseason_windows at boot.
    if not conn.execute("""SELECT 1 FROM sqlite_master
        WHERE type='table' AND name='world_career_preseason_windows'""").fetchone():
        window=None
    else:
        window=_row(conn,"""SELECT * FROM world_career_preseason_windows
            WHERE career_id=? AND season_index=?""",(career_id,season_index))
    if window is None:
        return {"career_id":career_id,"season_index":season_index,
                "state":"not_started","remaining_seconds":None,
                "started_at":None,"deadline_at":None,"closed_at":None,
                "duration_seconds":WINDOW_SECONDS}
    deadline=_parse(window["deadline_at"])
    remaining=max(0,int((deadline-t).total_seconds()+0.999999))
    state=("closed" if window["status"]=="closed" else
           "deadline_reached" if t>=deadline else "open")
    return {**window,"state":state,"remaining_seconds":remaining}


def start_preseason_window(conn, *, career_id, season_index=1, now=None):
    """Start exactly once with an immutable deadline; NEVER reset on retry.

    Season 2+ must be enabled later only after a verified completed season.
    For now this is limited to the first pre-season of a development sandbox.
    It is NOT called on GET, sign-in, deployment, or career creation.
    """
    t=_utc(now)
    if type(season_index) is not int or season_index!=1:
        raise ValueError("Subsequent windows require verified season-transition support")
    conn.execute("BEGIN IMMEDIATE")
    try:
        career=conn.execute("""SELECT state FROM world_career_saves
            WHERE career_id=?""",(career_id,)).fetchone()
        if not career or career[0]!="sandbox":
            raise ValueError("Pre-season window requires a valid development career")
        existing=_row(conn,"""SELECT window_id FROM world_career_preseason_windows
            WHERE career_id=? AND season_index=?""",(career_id,season_index))
        if existing is None:
            conn.execute("""INSERT INTO world_career_preseason_windows(
                career_id,season_index,started_at,deadline_at,status,
                duration_seconds,policy_version)
                VALUES(?,?,?,?,'open',?,?)""",
                (career_id,season_index,_iso(t),
                 _iso(t+timedelta(seconds=WINDOW_SECONDS)),
                 WINDOW_SECONDS,WINDOW_VERSION))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return window_snapshot(conn,career_id=career_id,
                           season_index=season_index,now=t)


def assert_window_allows_negotiation(conn, *, career_id, now=None):
    """Optional mode guard: returns None for untouched legacy careers.

    Calls that belong to the live-mode save MUST use this guard, including
    POSTs that finalise player/agent terms, not merely the inbox route.
    """
    snap=window_snapshot(conn,career_id=career_id,now=now)
    if snap["state"]=="not_started":
        return None
    if snap["state"]!="open":
        raise ValueError("Transfer deadline passed: the pre-season window is closed")
    return snap


def attach_offer_to_window(conn, *, career_id, offer_id, now=None):
    """Attach a genuinely new offer to the OPEN window in caller's transaction.

    Merely observing historical offers must not import them into a new window.
    Call only once at first creation, not when idempotently returning an old
    request_key or when reviewing old negotiations.
    """
    row=conn.execute("""SELECT 1 FROM world_career_offers
        WHERE offer_id=? AND career_id=?""",(offer_id,career_id)).fetchone()
    if row is None:
        raise ValueError("Cannot attach a foreign career's offer")
    snap=assert_window_allows_negotiation(conn,career_id=career_id,now=now)
    if snap is None:
        return False
    existing=conn.execute("""SELECT window_id
        FROM world_career_preseason_window_offers WHERE offer_id=?""",
        (offer_id,)).fetchone()
    if existing is not None:
        if existing[0]!=snap["window_id"]:
            raise ValueError("Offer already belongs to another transfer window")
        return False
    conn.execute("""INSERT INTO world_career_preseason_window_offers
        (window_id,offer_id,tagged_at) VALUES(?,?,?)""",
        (snap["window_id"],offer_id,_iso(_utc(now))))
    return True


def finalise_preseason_window(conn, *, career_id, season_index=1, now=None):
    """At deadline register ONLY tagged, fully signed deals, exactly once.

    Reconciles safely after process outage or when the app resumes: the
    authoritative UTC deadline is unchanged. The row is locked in one IMMEDIATE
    SQLite transaction; all fee/wage deductions and registrations commit
    together. Incomplete negotiations lapse without being registered.
    """
    t=_utc(now)
    conn.execute("BEGIN IMMEDIATE")
    try:
        snap=window_snapshot(conn,career_id=career_id,
                             season_index=season_index,now=t)
        if snap["state"]=="not_started":
            raise ValueError("The pre-season window has not started")
        if snap["state"]=="open":
            raise ValueError("Cannot register pre-season transfers before deadline")
        if snap["state"]=="closed":
            conn.commit()
            return {"status":"closed","already_closed":True,
                    "registered":0,"expired":0,
                    "window_id":snap["window_id"]}
        c=conn.execute("""SELECT pes_lock_date FROM world_career_saves
            WHERE career_id=? AND state='sandbox'""",(career_id,)).fetchone()
        if c is None:
            raise ValueError("Cannot settle an unknown or non-sandbox career")
        # Only offer IDs explicitly tagged when this window was open belong
        # to the batch; prior-season, test or legacy offers stay untouched.
        offers=conn.execute("""SELECT o.offer_id,o.player_id,
                o.selling_club_id,o.buying_club_id,o.offered_fee,
                o.offered_wage_weekly,o.status,t.status AS agent_status,
                t.proposed_wage_weekly
            FROM world_career_preseason_window_offers wt
            JOIN world_career_offers o ON o.offer_id=wt.offer_id
            LEFT JOIN world_career_agent_terms t ON t.offer_id=o.offer_id
            WHERE wt.window_id=? AND o.career_id=?
            ORDER BY o.offer_id""",(snap["window_id"],career_id)).fetchall()
        registered=0
        expired=0
        moved=set()
        for offer in offers:
            oid,player_id,seller,buyer,fee,wage,status,agent_status,agent_wage=offer
            if status=="agreed_future":
                from world_player_morale import is_unavailable
                if is_unavailable(conn,career_id=career_id,
                                  window_id=snap["window_id"],player_id=player_id):
                    raise ValueError("A player who refuses to play cannot be registered")
                # 'Agreed' means player and agent consented, and the human
                # manager or permitted autonomous counterpart confirmed.
                # Never guess consent from a submitted fee or board directive.
                if agent_status!="accepted" or wage is None or agent_wage!=wage:
                    raise ValueError("Signed offer has inconsistent player/agent consent")
                current=conn.execute("""SELECT club_id FROM world_career_registrations
                    WHERE career_id=? AND player_id=?""",
                    (career_id,player_id)).fetchone()
                if current is None or current[0]!=seller:
                    raise ValueError("Signed player registration no longer matches the selling club")
                if player_id in moved:
                    # Two signings for one player would be illegal. Abort the
                    # entire batch, never arbitrarily award a player to the
                    # first buyer merely because the offer ID is smaller.
                    raise ValueError("Player has multiple signed pre-season deals")
                ledger=conn.execute("""SELECT transfer_budget,weekly_wage_budget,
                    committed_fees,committed_wages FROM world_career_club_ledger
                    WHERE career_id=? AND club_id=?""",(career_id,buyer)).fetchone()
                if (ledger is None or
                    ledger[2]+fee>ledger[0] or
                    ledger[3]+wage>ledger[1]):
                    raise ValueError("Signed transfer exceeds the club's remaining finances")
                conn.execute("""UPDATE world_career_club_ledger
                    SET committed_fees=committed_fees+?,
                        committed_wages=committed_wages+?
                    WHERE career_id=? AND club_id=?""",
                    (fee,wage,career_id,buyer))
                conn.execute("""UPDATE world_career_registrations SET club_id=?
                    WHERE career_id=? AND player_id=? AND club_id=?""",
                    (buyer,career_id,player_id,seller))
                conn.execute("""UPDATE world_career_offers
                    SET status='completed',effective_date=?
                    WHERE offer_id=? AND career_id=?""",(c[0],oid,career_id))
                conn.execute("""INSERT INTO world_career_preseason_registration_events(
                    window_id,offer_id,career_id,player_id,from_club_id,to_club_id,
                    fee_gbp,weekly_wage_gbp,pes_effective_date,recorded_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (snap["window_id"],oid,career_id,player_id,seller,buyer,
                     fee,wage,c[0],_iso(t)))
                conn.execute("""INSERT INTO world_career_offer_events
                    (offer_id,event_type,detail) VALUES(?,?,?)""",
                    (oid,"preseason_registered",
                     "Fully signed pre-season deal registered in career roster at deadline; "
                     "PES console squad remains an external manual setup."))
                moved.add(player_id)
                registered+=1
            elif status in ("proposed","countered","accepted_pending_contract"):
                conn.execute("""UPDATE world_career_offers
                    SET status='withdrawn' WHERE offer_id=? AND career_id=?""",
                    (oid,career_id))
                conn.execute("""INSERT INTO world_career_offer_events
                    (offer_id,event_type,detail) VALUES(?,?,?)""",
                    (oid,"preseason_deadline_expired",
                     "Transfer not fully signed before the real-time 30-minute deadline."))
                expired+=1
            # 'rejected','withdrawn','completed': historical decisions left intact.
        # Pending, independently consented loans register at the same immutable
        # deadline; none may collide with a signed permanent transfer.
        from world_career_lifecycle import activate_agreed_loans
        activate_agreed_loans(conn,career_id=career_id,effective_date=c[0])
        conn.execute("""UPDATE world_career_preseason_windows
            SET status='closed',closed_at=? WHERE window_id=? AND status='open'""",
            (_iso(t),snap["window_id"]))
        conn.commit()
        return {"status":"closed","already_closed":False,
                "registered":registered,"expired":expired,
                "window_id":snap["window_id"]}
    except Exception:
        conn.rollback()
        raise

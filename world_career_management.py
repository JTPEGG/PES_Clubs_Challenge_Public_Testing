"""Persistent development-only career governance and contract state.

Extension of existing world_career_saves/ledger/registrations rather than a
second source of truth. No real transfer is executed. Values are explicit
scenario assumptions or recorded career events, never fabricated from OVR.
All writes are idempotent and restricted to a single saved career.
"""
import json
import sqlite3
from datetime import date

STATE_VERSION = "career-management-v1"
ROLES = ("key_player","regular_starter","rotation","fringe")
SOURCES = ("user_sandbox_assumption","source_backed")
EVENTS = ("objective_exceeded","objective_met","objective_missed",
          "promotion","relegation","successful_cup_run",
          "board_disagreement","board_support")
CONFIDENCE_CHANGE = {
    "objective_exceeded":12,"objective_met":5,"objective_missed":-12,
    "promotion":20,"relegation":-22,"successful_cup_run":7,
    "board_disagreement":-6,"board_support":4,
}
SCHEMA = """
CREATE TABLE IF NOT EXISTS world_career_management_contracts(
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id) ON DELETE CASCADE,
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 wage_weekly INTEGER CHECK(wage_weekly IS NULL OR wage_weekly BETWEEN 0 AND 1000000),
 end_date TEXT,
 squad_role TEXT CHECK(squad_role IS NULL OR squad_role IN
 ('key_player','regular_starter','rotation','fringe')),
 source_kind TEXT NOT NULL CHECK(source_kind IN ('user_sandbox_assumption','source_backed')),
 source_note TEXT NOT NULL DEFAULT '',
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(career_id,player_id)
);
CREATE TABLE IF NOT EXISTS world_career_management_board(
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id) ON DELETE CASCADE,
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 manager_confidence INTEGER CHECK(manager_confidence BETWEEN 0 AND 100),
 confidence_source TEXT NOT NULL CHECK(confidence_source IN ('unset','user_sandbox_assumption','recorded_career_events')),
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(career_id,club_id)
);
CREATE TABLE IF NOT EXISTS world_career_management_events(
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id) ON DELETE CASCADE,
 event_key TEXT NOT NULL,
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 event_type TEXT NOT NULL CHECK(event_type IN
 ('objective_exceeded','objective_met','objective_missed','promotion','relegation',
 'successful_cup_run','board_disagreement','board_support')),
 event_date TEXT NOT NULL,
 confidence_before INTEGER CHECK(confidence_before BETWEEN 0 AND 100),
 confidence_after INTEGER NOT NULL CHECK(confidence_after BETWEEN 0 AND 100),
 source_note TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(career_id,event_key)
);
CREATE INDEX IF NOT EXISTS world_career_management_events_by_club
 ON world_career_management_events(career_id,club_id,event_date);
"""


def initialize_career_management(conn):
    """Idempotent additive schema migration; never edits legacy save tables."""
    conn.executescript(SCHEMA)
    conn.commit()


def _career_club(conn,career_id,club_id):
    row=conn.execute("""SELECT c.career_id FROM world_career_saves c
        JOIN world_career_club_ledger l ON l.career_id=c.career_id
        WHERE c.career_id=? AND l.club_id=?""",(career_id,club_id)).fetchone()
    if row is None:
        raise ValueError("Club is not part of this saved career")


def _immediate(conn, callback):
    if conn.in_transaction:
        raise ValueError("Finish the existing transaction before a career management write")
    conn.execute("BEGIN IMMEDIATE")
    try:
        result=callback()
        conn.commit()
        return result
    except BaseException:
        conn.rollback()
        raise


def _money_or_none(value):
    if value is not None and (type(value) is not int or not 0<=value<=1_000_000):
        raise ValueError("Weekly wage must be a nonnegative whole number or unknown")


def record_contract(conn,*,career_id,player_id,club_id,wage_weekly=None,
                    end_date=None,squad_role=None,
                    source_kind="user_sandbox_assumption",source_note=""):
    """Explicit contract fact for currently registered player in this career.

    Existing records are not overwritten: revisions must use a separate
    deliberate workflow in a later version with history and authorization.
    """
    _money_or_none(wage_weekly)
    if squad_role is not None and squad_role not in ROLES:
        raise ValueError("Unknown role")
    if source_kind not in SOURCES or not isinstance(source_note,str):
        raise ValueError("Invalid contract source")
    if source_kind=="source_backed" and not source_note.strip():
        raise ValueError("Source-backed contracts need a source note")
    if end_date is not None:
        date.fromisoformat(end_date)
    def write():
        _career_club(conn,career_id,club_id)
        reg=conn.execute("""SELECT club_id FROM world_career_registrations
            WHERE career_id=? AND player_id=?""",(career_id,player_id)).fetchone()
        if not reg or reg[0]!=club_id:
            raise ValueError("Player must already be registered to this club in this career")
        existing=conn.execute("""SELECT club_id,wage_weekly,end_date,squad_role,source_kind,source_note
            FROM world_career_management_contracts
            WHERE career_id=? AND player_id=?""",(career_id,player_id)).fetchone()
        proposed=(club_id,wage_weekly,end_date,squad_role,source_kind,source_note)
        if existing:
            if tuple(existing)!=proposed:
                raise ValueError("Contract already recorded; cannot silently overwrite")
            return False
        conn.execute("""INSERT INTO world_career_management_contracts
            (career_id,player_id,club_id,wage_weekly,end_date,squad_role,source_kind,source_note)
            VALUES(?,?,?,?,?,?,?,?)""",(career_id,player_id,*proposed))
        return True
    return _immediate(conn,write)


def set_initial_confidence(conn,*,career_id,club_id,value,
                           source_kind="user_sandbox_assumption"):
    """No fabricated initial trust (the default is unknown)."""
    if type(value) is not int or not 0<=value<=100:
        raise ValueError("Board confidence must be 0–100")
    if source_kind!="user_sandbox_assumption":
        raise ValueError("Initial confidence must be identified as an assumption")
    def write():
        _career_club(conn,career_id,club_id)
        row=conn.execute("""SELECT manager_confidence FROM world_career_management_board
            WHERE career_id=? AND club_id=?""",(career_id,club_id)).fetchone()
        if row:
            if row[0]!=value:
                raise ValueError("Confidence already established; apply recorded events")
            return False
        conn.execute("""INSERT INTO world_career_management_board
            (career_id,club_id,manager_confidence,confidence_source)
            VALUES(?,?,?,?)""",(career_id,club_id,value,source_kind))
        return True
    return _immediate(conn,write)


def record_board_event(conn,*,career_id,club_id,event_key,event_type,
                       event_date,source_note):
    """User-confirmed real game event. Idempotency key never reapplied.

    We do not infer events from standings or matches; an authorised career
    workflow must explicitly supply and confirm the event.
    """
    if event_type not in CONFIDENCE_CHANGE or not isinstance(event_key,str) or not event_key.strip():
        raise ValueError("Invalid event type or key")
    if not isinstance(source_note,str) or not source_note.strip():
        raise ValueError("Every career event requires a source/confirmation note")
    date.fromisoformat(event_date)
    def write():
        _career_club(conn,career_id,club_id)
        if event_type in ("objective_exceeded","objective_met","objective_missed",
                          "promotion","relegation","successful_cup_run"):
            table=conn.execute("""SELECT 1 FROM sqlite_master WHERE type='table'
                AND name='world_career_season_objectives'""").fetchone()
            if table and conn.execute("""SELECT 1 FROM world_career_season_objectives
                    WHERE career_id=? AND club_id=? LIMIT 1""",
                    (career_id,club_id)).fetchone():
                raise ValueError("Objective-based season scoring is active; record the completed season review instead of a duplicate achievement event")
        existing=conn.execute("""SELECT club_id,event_type,event_date,source_note,confidence_after
            FROM world_career_management_events
            WHERE career_id=? AND event_key=?""",(career_id,event_key)).fetchone()
        if existing:
            if tuple(existing[:4])!=(club_id,event_type,event_date,source_note):
                raise ValueError("Event key already used for different details")
            return existing[4]
        row=conn.execute("""SELECT manager_confidence FROM world_career_management_board
            WHERE career_id=? AND club_id=?""",(career_id,club_id)).fetchone()
        if not row or row[0] is None:
            raise ValueError("Initial board confidence must be explicitly established")
        before=row[0]
        after=max(0,min(100,before+CONFIDENCE_CHANGE[event_type]))
        conn.execute("""INSERT INTO world_career_management_events
            (career_id,event_key,club_id,event_type,event_date,
            confidence_before,confidence_after,source_note)
            VALUES(?,?,?,?,?,?,?,?)""",
            (career_id,event_key,club_id,event_type,event_date,before,after,source_note))
        conn.execute("""UPDATE world_career_management_board
            SET manager_confidence=?,confidence_source='recorded_career_events',
                updated_at=CURRENT_TIMESTAMP WHERE career_id=? AND club_id=?""",
            (after,career_id,club_id))
        return after
    return _immediate(conn,write)


def career_management_snapshot(conn,*,career_id,club_id):
    """Read saved finance and contract information, without inferring unknown pay.

    Reuses existing legacy reservation accounting; subtract future agreements
    only once through world_careers helpers.
    """
    _career_club(conn,career_id,club_id)
    from world_careers import budget_remaining,wage_budget_breakdown
    ledger=conn.execute("""SELECT transfer_budget,weekly_wage_budget,committed_fees,committed_wages
        FROM world_career_club_ledger WHERE career_id=? AND club_id=?""",
        (career_id,club_id)).fetchone()
    b=conn.execute("""SELECT manager_confidence,confidence_source
        FROM world_career_management_board WHERE career_id=? AND club_id=?""",
        (career_id,club_id)).fetchone()
    contracts=conn.execute("""SELECT player_id,club_id,wage_weekly,end_date,squad_role,source_kind,source_note
        FROM world_career_management_contracts WHERE career_id=? AND club_id=?
        ORDER BY player_id""",(career_id,club_id)).fetchall()
    return {
        "career_id":career_id,"club_id":club_id,"policy_version":STATE_VERSION,
        "finances":{
            "scenario_transfer_budget":ledger[0],
            "scenario_weekly_wage_budget":ledger[1],
            "committed_fees":ledger[2],"committed_wages":ledger[3],
            "available_transfer_budget":budget_remaining(conn,career_id,club_id),
            "weekly_wages":wage_budget_breakdown(conn,career_id,club_id),
            "source_kind":"career_sandbox_economy",
        },
        "board":{
            "manager_confidence":b[0] if b else None,
            "confidence_source":b[1] if b else "unset",
        },
        "contracts":[{
            "player_id":r[0],"club_id":r[1],"wage_weekly":r[2],
            "end_date":r[3],"squad_role":r[4],
            "source_kind":r[5],"source_note":r[6],
        } for r in contracts],
    }

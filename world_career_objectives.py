"""Career-isolated board objectives with locked seasons and idempotent reviews.

Only explicit human-confirmed outcomes alter manager confidence. The strength
proxy may be suggested from existing rated squads, but never treated as a
verified league finish. Reviews are applied once in a single SQLite transaction.
"""
from datetime import date
import json
from world_board_objectives import evaluate_objective,objective_band,OBJECTIVES_VERSION

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_career_season_objectives (
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id) ON DELETE CASCADE,
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 season_key TEXT NOT NULL,
 expected_rank INTEGER NOT NULL,
 league_size INTEGER NOT NULL,
 expected_relegation INTEGER CHECK(expected_relegation IN (0,1) OR expected_relegation IS NULL),
 strength_source TEXT NOT NULL,
 source_note TEXT NOT NULL,
 model_version TEXT NOT NULL,
 locked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(career_id,club_id,season_key),
 CHECK(league_size BETWEEN 10 AND 30),
 CHECK(expected_rank BETWEEN 1 AND league_size)
);
CREATE TABLE IF NOT EXISTS world_career_objective_strength_snapshots (
 career_id TEXT NOT NULL,
 club_id INTEGER NOT NULL,
 season_key TEXT NOT NULL,
 strength_version TEXT NOT NULL,
 source_date TEXT,
 frozen_rankings_json TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(career_id,club_id,season_key),
 FOREIGN KEY(career_id,club_id,season_key) REFERENCES
 world_career_season_objectives(career_id,club_id,season_key)
);
CREATE TABLE IF NOT EXISTS world_career_season_reviews (
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id) ON DELETE CASCADE,
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 season_key TEXT NOT NULL,
 actual_rank INTEGER NOT NULL,
 promoted INTEGER NOT NULL CHECK(promoted IN (0,1)),
 relegated INTEGER NOT NULL CHECK(relegated IN (0,1)),
 cup_result TEXT NOT NULL,
 result_note TEXT NOT NULL,
 confidence_before INTEGER NOT NULL,
 confidence_after INTEGER NOT NULL,
 confidence_delta INTEGER NOT NULL,
 grade TEXT NOT NULL,
 model_version TEXT NOT NULL,
 reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(career_id,club_id,season_key),
 FOREIGN KEY(career_id,club_id,season_key) REFERENCES
 world_career_season_objectives(career_id,club_id,season_key)
);
"""

def initialize_board_objectives(conn):
    conn.executescript(SCHEMA)
    from world_career_resources import initialize_resource_expectations
    initialize_resource_expectations(conn)
    conn.commit()

def _check_club(conn,career_id,club_id):
    row=conn.execute("""SELECT 1 FROM world_career_saves c
        JOIN world_career_club_ledger l ON c.career_id=l.career_id
        WHERE c.career_id=? AND l.club_id=? AND c.manager_club_id=?
        AND c.state='sandbox'""",(career_id,club_id,club_id)).fetchone()
    if not row:
        raise ValueError("Not the current managed club of a sandbox career")

def _transaction(conn,fn):
    if conn.in_transaction:
        raise ValueError("Complete existing transaction before recording objective")
    conn.execute("BEGIN IMMEDIATE")
    try:
        result=fn()
        conn.commit()
        return result
    except BaseException:
        conn.rollback()
        raise

def _season(key):
    if not isinstance(key,str) or not key or len(key)>32 or not all(
        x.isalnum() or x in "-_" for x in key):
        raise ValueError("Season key must be 1–32 letters, digits, hyphens or underscores")

def lock_objective(conn,*,career_id,club_id,season_key,
                   expected_rank,league_size,expected_relegation=None,
                   strength_source="user_sandbox_assumption",source_note=""):
    """Lock one pre-season expectation; never silently revise later."""
    _season(season_key)
    objective_band(expected_rank=expected_rank,league_size=league_size)
    if expected_relegation is not None and type(expected_relegation) is not bool:
        raise ValueError("Expected relegation must be yes/no/unknown")
    if strength_source!="user_sandbox_assumption":
        raise ValueError("Automatically derived objectives must be locked through the squad-strength snapshot workflow")
    if not isinstance(source_note,str) or not source_note.strip():
        raise ValueError("Explain the chosen expectation and its evidence")
    fields=(expected_rank,league_size,
        None if expected_relegation is None else int(expected_relegation),
        strength_source,source_note,OBJECTIVES_VERSION)
    def write():
        _check_club(conn,career_id,club_id)
        existing=conn.execute("""SELECT expected_rank,league_size,expected_relegation,
            strength_source,source_note,model_version FROM world_career_season_objectives
            WHERE career_id=? AND club_id=? AND season_key=?""",
            (career_id,club_id,season_key)).fetchone()
        if existing:
            if tuple(existing)!=fields:
                raise ValueError("Pre-season objective is locked and cannot be overwritten")
            return False
        # No newly backdated expectations after this club already has a later reviewed season.
        if conn.execute("""SELECT 1 FROM world_career_season_reviews
            WHERE career_id=? AND club_id=? AND season_key>=? LIMIT 1""",
            (career_id,club_id,season_key)).fetchone():
            raise ValueError("Cannot set a fresh objective after a review for this or a later season")
        conn.execute("""INSERT INTO world_career_season_objectives
            (career_id,club_id,season_key,expected_rank,league_size,
             expected_relegation,strength_source,source_note,model_version)
             VALUES(?,?,?,?,?,?,?,?,?)""",
            (career_id,club_id,season_key,*fields))
        return True
    return _transaction(conn,write)

def lock_auto_strength_objective(conn, *, career_id, club_id, season_key,
                                 ambition="consolidation",investment_mandate="none",
                                 investment_pool=0,commitment_note="No improvement mandate specified"):
    """Lock the actual career snapshot's relative squad rank, atomically.

    The manager may still manually enter an assumption through the old route,
    but that cannot masquerade as this documented auto-derived ranking.
    """
    from world_career_strength import strength_baseline
    _season(season_key)
    baseline=strength_baseline(conn,career_id=career_id,club_id=club_id)
    if not baseline["available"]:
        raise ValueError(baseline["reason"])
    # Source note includes methodology; detailed source-ranked snapshot is
    # immutable in its own row, so later data changes cannot rewrite history.
    note=(baseline["method"]+" Dataset "+baseline["dataset_id"]+
          " captured "+str(baseline["source_date"])+
          "; locked automatically, not a verified finishing prediction.")
    from world_career_resources import (
        resource_capacity,expectation_with_resources,VERSION as RESOURCE_VERSION)
    if not isinstance(commitment_note,str) or not commitment_note.strip():
        raise ValueError("Explain the board's ambition and resource mandate")
    capacity=resource_capacity(conn,career_id=career_id,club_id=club_id,baseline=baseline)
    tier=conn.execute("""SELECT c.tier FROM world_dataset_entries e
        JOIN world_competitions c ON c.competition_id=e.competition_id
        WHERE e.dataset_id=? AND e.club_id=?""",
        (baseline["dataset_id"],club_id)).fetchone()[0]
    resources=expectation_with_resources(squad_rank=baseline["rank"],
        league_size=baseline["league_size"],ambition=ambition,
        investment_mandate=investment_mandate,investment_pool=investment_pool,
        opening_unreserved_funds=capacity["unreserved"],
        division_median_transfer_budget=capacity["median_peer_budget"],
        division_tier=tier)
    expected=resources["expected_rank"]
    # Relegation risk follows the *target*, not the unadjusted squad;
    # no assumption for competitions with unknown relegation boundaries.
    relegation=(expected>baseline["league_size"]-3
                if baseline["expected_relegation"] is not None else None)
    resource_mode=investment_mandate!="none" or ambition!="consolidation"
    source="resource_adjusted_proxy" if resource_mode else "squad_strength_proxy"
    note+=" "+resources["explanation"]+" "+commitment_note.strip()
    fields=(expected,baseline["league_size"],
        None if relegation is None else int(relegation),
        source,note,OBJECTIVES_VERSION)
    frozen={**baseline,"resource_expectation":resources,
            "resource_capacity":capacity,"commitment_note":commitment_note}
    serialized=json.dumps(frozen,sort_keys=True,separators=(",",":"))
    def write():
        _check_club(conn,career_id,club_id)
        existing=conn.execute("""SELECT expected_rank,league_size,expected_relegation,
            strength_source,source_note,model_version FROM world_career_season_objectives
            WHERE career_id=? AND club_id=? AND season_key=?""",
            (career_id,club_id,season_key)).fetchone()
        if existing:
            old=conn.execute("""SELECT strength_version,frozen_rankings_json
                FROM world_career_objective_strength_snapshots
                WHERE career_id=? AND club_id=? AND season_key=?""",
                (career_id,club_id,season_key)).fetchone()
            if tuple(existing)==fields and old and old[0]==baseline["model_version"] and old[1]==serialized:
                return False
            raise ValueError("A different pre-season expectation is already locked")
        if conn.execute("""SELECT 1 FROM world_career_season_reviews
            WHERE career_id=? AND club_id=? AND season_key>=? LIMIT 1""",
            (career_id,club_id,season_key)).fetchone():
            raise ValueError("Cannot backdate an objective after completed season reviews")
        conn.execute("""INSERT INTO world_career_season_objectives
            (career_id,club_id,season_key,expected_rank,league_size,
             expected_relegation,strength_source,source_note,model_version)
             VALUES(?,?,?,?,?,?,?,?,?)""",
             (career_id,club_id,season_key,*fields))
        conn.execute("""INSERT INTO world_career_objective_strength_snapshots
            (career_id,club_id,season_key,strength_version,source_date,frozen_rankings_json)
            VALUES(?,?,?,?,?,?)""",
            (career_id,club_id,season_key,baseline["model_version"],
             baseline["source_date"],serialized))
        conn.execute("""INSERT INTO world_career_resource_expectations
            (career_id,club_id,season_key,strength_rank,expected_rank,
             financial_shift,ambition_shift,ambition,investment_mandate,
             investment_pool,opening_transfer_budget,opening_committed_fees,
             opening_unreserved_funds,division_median_transfer_budget,
             commitment_note,model_version)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (career_id,club_id,season_key,baseline["rank"],expected,
             resources["financial_shift"],resources["ambition_shift"],
             ambition,investment_mandate,investment_pool,
             capacity["transfer_budget"],capacity["committed_fees"],
             capacity["unreserved"],capacity["median_peer_budget"],
             commitment_note,RESOURCE_VERSION))
        return True
    return _transaction(conn,write)


def review_season(conn,*,career_id,club_id,season_key,actual_rank,
                  promoted=False,relegated=False,cup_result="not_assessed",
                  result_note=""):
    """An explicitly confirmed final league result, not an inferred event."""
    _season(season_key)
    if not isinstance(result_note,str) or not result_note.strip():
        raise ValueError("A season review needs a verified result note")
    def write():
        _check_club(conn,career_id,club_id)
        objective=conn.execute("""SELECT expected_rank,league_size,expected_relegation
            FROM world_career_season_objectives WHERE career_id=? AND club_id=?
            AND season_key=?""",(career_id,club_id,season_key)).fetchone()
        if not objective:
            raise ValueError("Lock pre-season expectations before reviewing the season")
        evaluation=evaluate_objective(expected_rank=objective[0],
            league_size=objective[1],expected_relegation=(
            None if objective[2] is None else bool(objective[2])),
            actual_rank=actual_rank,promoted=promoted,relegated=relegated,
            cup_result=cup_result)
        old=conn.execute("""SELECT actual_rank,promoted,relegated,cup_result,result_note,
            confidence_after FROM world_career_season_reviews
            WHERE career_id=? AND club_id=? AND season_key=?""",
            (career_id,club_id,season_key)).fetchone()
        wanted=(actual_rank,int(promoted),int(relegated),cup_result,result_note)
        if old:
            if tuple(old[:5])!=wanted:
                raise ValueError("Season review already applied; cannot rewrite result")
            return {"evaluation":evaluation,"confidence_after":old[5],"replayed":True}
        # Avoid applying an older review after a newer one (confidence chronology).
        if conn.execute("""SELECT 1 FROM world_career_season_reviews
            WHERE career_id=? AND club_id=? AND season_key>? LIMIT 1""",
            (career_id,club_id,season_key)).fetchone():
            raise ValueError("Cannot apply a season review out of order")
        board=conn.execute("""SELECT manager_confidence FROM world_career_management_board
            WHERE career_id=? AND club_id=?""",(career_id,club_id)).fetchone()
        if not board or board[0] is None:
            raise ValueError("Explicit initial board confidence required before review")
        from world_career_resources import review_underinvestment
        mandate=conn.execute("""SELECT investment_pool,investment_mandate,
            opening_committed_fees FROM world_career_resource_expectations
            WHERE career_id=? AND club_id=? AND season_key=?""",
            (career_id,club_id,season_key)).fetchone()
        finance_review=None
        if mandate:
            current=conn.execute("""SELECT committed_fees FROM world_career_club_ledger
                WHERE career_id=? AND club_id=?""",(career_id,club_id)).fetchone()
            if not current:
                raise ValueError("Cannot assess resource delivery without a financial ledger")
            recognised=max(0,current[0]-mandate[2])
            finance_review=review_underinvestment(actual_rank=actual_rank,
                expected_rank=objective[0],committed_spend=recognised,
                mandated_funds=mandate[0],mandate=mandate[1])
            evaluation["resource_delta"]=finance_review["delta"]
            evaluation["resource_reason"]=finance_review["reason"]
            evaluation["confidence_delta"]=max(-20,min(20,
                evaluation["confidence_delta"]+finance_review["delta"]))
        before=board[0]
        after=max(0,min(100,before+evaluation["confidence_delta"]))
        conn.execute("""INSERT INTO world_career_season_reviews(
            career_id,club_id,season_key,actual_rank,promoted,relegated,cup_result,
            result_note,confidence_before,confidence_after,confidence_delta,grade,model_version)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (career_id,club_id,season_key,actual_rank,int(promoted),int(relegated),
            cup_result,result_note,before,after,evaluation["confidence_delta"],
            evaluation["grade"],OBJECTIVES_VERSION))
        if finance_review is not None:
            conn.execute("""INSERT INTO world_career_resource_reviews
                (career_id,club_id,season_key,reported_investment,
                 unused_mandated_funds,confidence_delta,reason)
                VALUES(?,?,?,?,?,?,?)""",
                (career_id,club_id,season_key,recognised,
                 finance_review["unused"],finance_review["delta"],
                 finance_review["reason"]))
        conn.execute("""UPDATE world_career_management_board SET
            manager_confidence=?,confidence_source='recorded_career_events',
            updated_at=CURRENT_TIMESTAMP WHERE career_id=? AND club_id=?""",
            (after,career_id,club_id))
        return {"evaluation":evaluation,"confidence_after":after,"replayed":False}
    return _transaction(conn,write)

def objective_history(conn,*,career_id,club_id):
    _check_club(conn,career_id,club_id)
    rows=conn.execute("""SELECT o.season_key,o.expected_rank,o.league_size,
        o.expected_relegation,o.strength_source,o.source_note,o.locked_at,
        r.actual_rank,r.confidence_before,r.confidence_after,r.confidence_delta,
        r.grade,r.result_note,res.strength_rank,res.financial_shift,
        res.ambition_shift,res.ambition,res.investment_mandate,
        res.investment_pool,rr.reported_investment,rr.confidence_delta,
        rr.reason
        FROM world_career_season_objectives o
        LEFT JOIN world_career_resource_expectations res
          ON res.career_id=o.career_id AND res.club_id=o.club_id
          AND res.season_key=o.season_key
        LEFT JOIN world_career_resource_reviews rr
          ON rr.career_id=o.career_id AND rr.club_id=o.club_id
          AND rr.season_key=o.season_key
        LEFT JOIN world_career_season_reviews r ON r.career_id=o.career_id
        AND r.club_id=o.club_id AND r.season_key=o.season_key
        WHERE o.career_id=? AND o.club_id=? ORDER BY o.season_key DESC""",
        (career_id,club_id)).fetchall()
    return [dict(x) if hasattr(x,"keys") else {
        k:v for k,v in zip(("season_key","expected_rank","league_size",
        "expected_relegation","strength_source","source_note","locked_at",
        "actual_rank","confidence_before","confidence_after","confidence_delta",
        "grade","result_note","strength_rank","financial_shift",
        "ambition_shift","ambition","investment_mandate",
        "investment_pool","reported_investment","resource_confidence_delta",
        "resource_reason"),x)} for x in rows]

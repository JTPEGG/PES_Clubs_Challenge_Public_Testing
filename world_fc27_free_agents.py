"""Isolated FC27 source-labelled free-agent pool and no-fee contract signing.

The 659 source club rosters are never rewritten. Free players do not belong to
invented clubs and may be registered only after the real 30-minute deadline.
This game-only supplement is intentionally absent from the original PES save.
"""
from __future__ import annotations
import gzip
import json
import sqlite3
from datetime import date

DATASET="fc27-warehouse-659-mens-2026-27"
POOL_SCHEMA="""
CREATE TABLE IF NOT EXISTS world_fc27_free_agent_pool (
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 source_ea_id TEXT NOT NULL,
 reference_weekly_wage_gbp INTEGER NOT NULL CHECK(reference_weekly_wage_gbp>=0),
 source_overall INTEGER NOT NULL CHECK(source_overall BETWEEN 1 AND 99),
 ratings_provenance TEXT NOT NULL,
 source_url TEXT NOT NULL,
 source_snapshot TEXT NOT NULL,
 PRIMARY KEY(dataset_id,player_id),
 UNIQUE(dataset_id,source_ea_id)
);
CREATE TABLE IF NOT EXISTS world_fc27_free_agent_offers (
 signing_id INTEGER PRIMARY KEY,
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 buying_club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 proposed_weekly_wage_gbp INTEGER NOT NULL CHECK(proposed_weekly_wage_gbp>=0),
 required_weekly_wage_gbp INTEGER NOT NULL CHECK(required_weekly_wage_gbp>=0),
 contract_years INTEGER NOT NULL CHECK(contract_years BETWEEN 1 AND 5),
 squad_role TEXT NOT NULL CHECK(squad_role IN
   ('key_player','regular_starter','rotation','fringe')),
 status TEXT NOT NULL CHECK(status IN
   ('countered','terms_accepted','agreed_future','withdrawn','completed')),
 agent_reason TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(career_id,player_id)
);
CREATE TABLE IF NOT EXISTS world_fc27_free_agent_events (
 event_id INTEGER PRIMARY KEY,
 signing_id INTEGER NOT NULL REFERENCES world_fc27_free_agent_offers(signing_id),
 event TEXT NOT NULL,
 detail TEXT NOT NULL,
 recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS fc27_free_agent_offer_by_career
 ON world_fc27_free_agent_offers(career_id,status);
"""

def initialize_free_agent_schema(conn):
    # Called once per boot, not on every scouting filter request.
    conn.executescript(POOL_SCHEMA)
    conn.commit()

def import_free_agent_supplement(conn,supplement_path):
    """Additive import of audited 29-attribute FC27 game free agents.

    The source is a dated JSON.gz signed by release digest at bootstrap.
    IDs, overall and attribute coverage are checked before any commit.
    """
    with gzip.open(supplement_path,"rt",encoding="utf-8") as fd:
        package=json.load(fd)
    if (package.get("version")!="FC27-free-agents-v1" or
        package.get("excluded_isl_players_not_free_agents")!=256 or
        package.get("official_659_clubs_unchanged") is not True):
        raise ValueError("Unapproved or incomplete FC27 free-agent supplement")
    entries=package.get("players")
    if not isinstance(entries,list) or not 195<=len(entries)<=213:
        raise ValueError("Free-agent source count is incomplete")
    if len({p.get("source_id") for p in entries})!=len(entries):
        raise ValueError("Duplicate EA player IDs in free-agent pool")
    if not any(p["source_id"]=="233049" and p["name"]=="Jadon Sancho"
               for p in entries):
        raise ValueError("Missing separately labelled historic Sancho record")
    before=conn.execute("""SELECT COUNT(*) FROM world_dataset_rosters
         WHERE dataset_id=?""",(DATASET,)).fetchone()[0]
    if before!=17593:
        raise ValueError("The 17,593 source-club registrations must remain pristine")
    initialize_free_agent_schema(conn)
    inserted=0
    for p in entries:
        attrs=p["pes_attributes"]
        if (len(attrs)!=29 or any(type(v) is not int or not 1<=v<=200
                                  for v in attrs.values())):
            raise ValueError("Invalid full PES conversion: "+p["name"])
        sid=str(p["source_id"])
        if conn.execute("""SELECT 1 FROM world_fc27_free_agent_pool
            WHERE dataset_id=? AND source_ea_id=?""",(DATASET,sid)).fetchone():
            raise ValueError("Duplicate free-agent import")
        # An official club player must never be duplicated as an FA.
        collision=conn.execute("""SELECT 1 FROM world_dataset_ratings
            WHERE dataset_id=? AND external_player_id=?""",
            (DATASET,sid)).fetchone()
        if collision:
            raise ValueError("Source player already registered at a club: "+sid)
        pid=conn.execute("""INSERT INTO world_players
            (full_name,birth_date,nationality,primary_position,source_url)
            VALUES(?,?,?,?,?)""",
            (p["name"],p["dob"],p.get("nationality","Unknown"),
             p["position"],p["source_url"])).lastrowid
        conn.execute("""INSERT INTO world_player_source_refs
            (player_id,source_name,external_id,source_url,identity_status)
            VALUES(?,?,?,?,?)""",
            (pid,"FC27-FREE-AGENT-SUPPLEMENT",sid,p["source_url"],
             "dated_source_separately_labelled"))
        conn.execute("""INSERT INTO world_dataset_ratings
            (dataset_id,player_id,source_name,source_edition,source_date,
             external_player_id,overall) VALUES(?,?,?,?,?,?,?)""",
            (DATASET,pid,p["ratings_provenance"],"2027",p["snapshot_date"],
             sid,p["overall"]))
        conn.executemany("""INSERT INTO world_dataset_extended_attributes
            (dataset_id,player_id,attribute,value,source_name)
            VALUES(?,?,?,?,?)""",(
            (DATASET,pid,"PES2020V2:"+k,v,p["ratings_provenance"])
            for k,v in attrs.items()))
        conn.execute("""INSERT INTO world_dataset_pes_v2_player_details
            (dataset_id,player_id,preferred_foot,height_cm,weight_kg,
             alternative_positions_json,position_fit_json)
            VALUES(?,?,?,?,?,?,?)""",
            (DATASET,pid,p.get("preferred_foot"),p.get("height_cm"),
             p.get("weight_kg"),"[]","{}"))
        conn.execute("""INSERT INTO world_fc27_free_agent_pool
            (dataset_id,player_id,source_ea_id,reference_weekly_wage_gbp,
             source_overall,ratings_provenance,source_url,source_snapshot)
            VALUES(?,?,?,?,?,?,?,?)""",
            (DATASET,pid,sid,p["wage_game_gbp"],p["overall"],
             p["ratings_provenance"],p["source_url"],p["snapshot_date"]))
        inserted+=1
    if conn.execute("""SELECT COUNT(*) FROM world_dataset_rosters
        WHERE dataset_id=?""",(DATASET,)).fetchone()[0]!=17593:
        raise ValueError("FA import unexpectedly changed a club roster")
    if conn.execute("""SELECT COUNT(*) FROM world_dataset_entries
        WHERE dataset_id=?""",(DATASET,)).fetchone()[0]!=659:
        raise ValueError("FA import unexpectedly changed source clubs")
    if conn.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("Free-agent import broke dataset references")
    conn.commit()
    return inserted


def _free_offer(conn,career_id,player_id):
    return conn.execute("""SELECT f.*,p.full_name,cl.name AS buyer_name
        FROM world_fc27_free_agent_offers f
        JOIN world_players p ON p.player_id=f.player_id
        JOIN world_clubs cl ON cl.club_id=f.buying_club_id
        WHERE f.career_id=? AND f.player_id=?""",
        (career_id,player_id)).fetchone()

def pool_player(conn,career_id,player_id):
    return conn.execute("""SELECT fa.*,x.overall,p.full_name,
        p.birth_date,p.primary_position,c.manager_club_id
        FROM world_fc27_free_agent_pool fa
        JOIN world_players p ON p.player_id=fa.player_id
        JOIN world_dataset_ratings x ON x.player_id=fa.player_id
            AND x.dataset_id=fa.dataset_id
        JOIN world_career_saves c ON c.dataset_id=fa.dataset_id
        WHERE c.career_id=? AND c.state='sandbox' AND fa.player_id=?
        AND NOT EXISTS(SELECT 1 FROM world_career_registrations r
          WHERE r.career_id=c.career_id AND r.player_id=fa.player_id)""",
        (career_id,player_id)).fetchone()

def offer_free_agent(conn,*,career_id,player_id,weekly_wage,years,role,
                     action="offer"):
    """Player/agent assessment independent of any fictional selling club.

    No transfer fees, no phantom seller, no wage commitments before the
    manager explicitly confirms. Agent can counter an inadequate proposal.
    """
    from world_preseason_window import assert_window_allows_negotiation
    snap=assert_window_allows_negotiation(conn,career_id=career_id)
    if snap is None:raise ValueError("Start the 30-minute window first")
    row=pool_player(conn,career_id,player_id)
    if row is None:raise ValueError("Player is not an available free agent")
    career=row["manager_club_id"]
    original=_free_offer(conn,career_id,player_id)
    if action=="withdraw":
        if not original or original["status"] in ("completed","withdrawn"):
            raise ValueError("No active free-agent negotiation to withdraw")
        conn.execute("""UPDATE world_fc27_free_agent_offers
           SET status='withdrawn',updated_at=CURRENT_TIMESTAMP
           WHERE signing_id=?""",(original["signing_id"],))
        conn.commit()
        return {"status":"withdrawn","message":"Free-agent talks cancelled",
                "player_id":player_id}
    if action=="confirm":
        if not original or original["status"]!="terms_accepted":
            raise ValueError("The player has not agreed terms to sign")
        from world_fc27_player_review import choice_for
        decision=choice_for(conn,career_id=career_id,kind="free_agent",
                            source_id=original["signing_id"])
        if not decision or decision["status"]!="accepted":
            raise ValueError("The player has not yet accepted the move. "+
                "Await the separate decision in your Inbox.")
        # Only the manager may sign; the wage ceiling is checked again at
        # confirmation, including other agreed future contracts.
        budget=conn.execute("""SELECT weekly_wage_budget,committed_wages
            FROM world_career_club_ledger
            WHERE career_id=? AND club_id=?""",(career_id,career)).fetchone()
        reserved=conn.execute("""SELECT
            COALESCE(SUM(offered_wage_weekly),0) FROM world_career_offers
            WHERE career_id=? AND buying_club_id=? AND status='agreed_future'""",
            (career_id,career)).fetchone()[0]
        reserved+=conn.execute("""SELECT COALESCE(SUM(proposed_weekly_wage_gbp),0)
            FROM world_fc27_free_agent_offers WHERE career_id=? AND
            buying_club_id=? AND status='agreed_future'""",
            (career_id,career)).fetchone()[0]
        if budget is None or budget[1]+reserved+original["proposed_weekly_wage_gbp"]>budget[0]:
            raise ValueError("Insufficient available weekly wage budget")
        conn.execute("""UPDATE world_fc27_free_agent_offers
            SET status='agreed_future',updated_at=CURRENT_TIMESTAMP
            WHERE signing_id=?""",(original["signing_id"],))
        conn.execute("""INSERT INTO world_fc27_free_agent_events
             (signing_id,event,detail) VALUES(?,'manager_confirmed',
             'Player agreed contract terms; manager signed before deadline')""",
             (original["signing_id"],))
        conn.commit()
        return {"status":"agreed_future","message":
                "Free-agent signing confirmed — registered at the deadline",
                "player_id":player_id}
    if action!="offer":raise ValueError("Unsupported free-agent action")
    if original and original["status"] in ("agreed_future","completed"):
        raise ValueError("This player has already signed")
    if not isinstance(weekly_wage,int) or not 0<=weekly_wage<=1_000_000:
        raise ValueError("Enter a valid weekly wage in pounds")
    if years not in (1,2,3,4,5):
        raise ValueError("Choose a contract between one and five years")
    if role not in ("key_player","regular_starter","rotation","fringe"):
        raise ValueError("Choose a squad role")
    from world_fc27_ai_recruitment import read_fc27_profiles
    profiles=read_fc27_profiles(conn,dataset=DATASET,club_id=career)
    profile=profiles.get(career)
    if not profile:raise ValueError("Club sporting profile unavailable")
    appeal=int(profile["sporting_appeal"])
    ovr=row["overall"]
    anchor=date.fromisoformat("2026-08-01")
    birth=date.fromisoformat(row["birth_date"])
    age=max(16,anchor.year-birth.year-
            ((anchor.month,anchor.day)<(birth.month,birth.day)))
    # An unattached player has no seller: use his FC27 game wage reference,
    # quality, age and the manager's sporting appeal. Playing-time promises
    # can offset the quality gap; a premium weekly salary can also convince
    # good players to join a smaller club. No arbitrary player name bans.
    expectation=max(40,min(92,round(35+max(0,ovr-61)*2.0)))
    gap=max(0,expectation-appeal)
    role_factor={"key_player":0.87,"regular_starter":1.0,
                 "rotation":1.20,"fringe":1.43}[role]
    premium=1+max(0,gap-8)*0.047
    if age>33:premium*=0.90
    required=max(500,round(row["reference_weekly_wage_gbp"]*
                           role_factor*premium/500)*500)
    from world_fc27_contract_renewals import market_reference_for_transfer
    peer_wage=market_reference_for_transfer(conn,dataset=DATASET,
        player_id=player_id,club_id=career)
    if peer_wage is not None:
        required=max(required,int(round(peer_wage*.86/500)*500))
    # A wage agreement is not player consent. The player's own decision
    # follows as a separate, time-bounded event after comparing proposals.
    status="terms_accepted" if weekly_wage>=required else "countered"
    reason=("Agent has agreed provisional contract terms. The player will "
            "now consider competing offers before replying to your Inbox."
            if status=="terms_accepted" else
            "Agent requests £"+format(required,",")+
            " weekly for this role and club's sporting circumstances")
    if original:
        conn.execute("""UPDATE world_fc27_free_agent_offers SET
           proposed_weekly_wage_gbp=?,required_weekly_wage_gbp=?,
           contract_years=?,squad_role=?,status=?,agent_reason=?,
           updated_at=CURRENT_TIMESTAMP
           WHERE signing_id=?""",
           (weekly_wage,required,years,role,status,reason,
            original["signing_id"]))
        signing_id=original["signing_id"]
    else:
        signing_id=conn.execute("""INSERT INTO world_fc27_free_agent_offers
            (career_id,player_id,buying_club_id,proposed_weekly_wage_gbp,
             required_weekly_wage_gbp,contract_years,squad_role,status,
             agent_reason) VALUES(?,?,?,?,?,?,?,?,?)""",
            (career_id,player_id,career,weekly_wage,required,years,role,
             status,reason)).lastrowid
    conn.execute("""INSERT INTO world_fc27_free_agent_events
        (signing_id,event,detail) VALUES(?,'agent_response',?)""",
        (signing_id,reason))
    conn.commit()
    review=None
    if status=="terms_accepted":
        from world_fc27_player_review import queue_choice
        review=queue_choice(conn,career_id=career_id,kind="free_agent",
            source_id=signing_id,player_id=player_id)
    return {"status":status,"message":reason,"required_weekly_wage_gbp":required,
            "player_review":review["status"] if review else None,
            "player_id":player_id}

def finalise_signed_free_agents(conn,*,career_id,effective_date):
    """Called by pre-season finalisation within its EXISTING transaction."""
    due=conn.execute("""SELECT signing_id,player_id,buying_club_id,
        proposed_weekly_wage_gbp,contract_years,status
        FROM world_fc27_free_agent_offers
        WHERE career_id=? AND status IN
            ('agreed_future','terms_accepted','countered')
        ORDER BY signing_id""",(career_id,)).fetchall()
    completed=0
    for signing,player,buyer,wage,years,status in due:
        if status!="agreed_future":
            conn.execute("""UPDATE world_fc27_free_agent_offers
                SET status='withdrawn' WHERE signing_id=?""",(signing,))
            continue
        if conn.execute("""SELECT 1 FROM world_career_registrations
            WHERE career_id=? AND player_id=?""",
            (career_id,player)).fetchone():
            raise ValueError("Free agent already registered at a club")
        ledger=conn.execute("""SELECT weekly_wage_budget,committed_wages
             FROM world_career_club_ledger WHERE career_id=? AND club_id=?""",
             (career_id,buyer)).fetchone()
        if not ledger or ledger[1]+wage>ledger[0]:
            raise ValueError("Signed free agent exceeds actual wage budget")
        conn.execute("""UPDATE world_career_club_ledger
            SET committed_wages=committed_wages+?
            WHERE career_id=? AND club_id=?""",(wage,career_id,buyer))
        conn.execute("""INSERT INTO world_career_registrations
            (career_id,player_id,club_id) VALUES(?,?,?)""",
            (career_id,player,buyer))
        expires_year=date.fromisoformat(effective_date).year+years
        expires=f"{expires_year}-06-30"
        conn.execute("""INSERT OR REPLACE INTO world_career_contract_snapshots
            (career_id,player_id,parent_club_id,weekly_wage_gbp,
             expires_on,renewal_status,source_kind)
            VALUES(?,?,?,?,?,'agreed','FC27-FA-independent-game-terms')""",
            (career_id,player,buyer,wage,expires))
        conn.execute("""UPDATE world_fc27_free_agent_offers SET
            status='completed' WHERE signing_id=?""",(signing,))
        conn.execute("""INSERT INTO world_fc27_free_agent_events
            (signing_id,event,detail) VALUES(?,'deadline_registered',
             'Wage-only free signing added to manager squad at 30-minute deadline')""",
            (signing,))
        completed+=1
    return completed

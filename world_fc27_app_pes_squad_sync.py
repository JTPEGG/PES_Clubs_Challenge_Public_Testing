"""FC27 app-world player registration -> playable PES squad sync staging.

Inputs:
 - edition 2027 derived *world* SQLite (659 active clubs, 344 intended playable)
 - read-only 22-edition men's-only historical squad SQLite (same edition source keys)
Only the 2027 FC27 registered male source players enter the staging layer.
Players outside the 659 active-club world are kept in the original archive,
not silently reattached to unknown clubs. Their PES abilities are preserved.
Transfers update current assignments in this isolated stage, never source IDs.
No unverified PES team/player numeric IDs or platform-native edit files.
"""
from __future__ import annotations
import csv
import hashlib
import json
import sqlite3
from pathlib import Path

EDITION=2027
EXPECTED_GAME_CLUBS=659
EXPECTED_PLAYABLE_CLUBS=344
EXPECTED_SOURCE_PLAYER_ROWS=17849
EXPECTED_ACTIVE_PLAYER_ROWS=17593
ATTRS=(
 "offensive_awareness","ball_control","dribbling","tight_possession",
 "low_pass","lofted_pass","finishing","heading","place_kicking","curl",
 "speed","acceleration","kicking_power","jump","physical_contact",
 "balance","stamina","defensive_awareness","ball_winning","aggression",
 "gk_awareness","gk_catching","gk_clearing","gk_reflexes","gk_reach",
)
AUX=("weak_foot_usage","weak_foot_accuracy","form","injury_resistance")
SCHEMA="""
CREATE TABLE fc27_app_player_registration (
  edition INTEGER NOT NULL CHECK(edition=2027),
  player_key TEXT NOT NULL,
  source_player_id TEXT NOT NULL,
  player_name TEXT NOT NULL,
  source_club_key TEXT NOT NULL,
  current_club_key TEXT NOT NULL,
  primary_position TEXT NOT NULL,
  secondary_positions_json TEXT NOT NULL,
  pes_abilities_json TEXT NOT NULL,
  pes_additional_json TEXT NOT NULL,
  registration_revision INTEGER NOT NULL DEFAULT 0 CHECK(registration_revision>=0),
  PRIMARY KEY (edition,player_key),
  FOREIGN KEY (edition,source_club_key)
    REFERENCES fc27_career_world_clubs(edition,club_key),
  FOREIGN KEY (edition,current_club_key)
    REFERENCES fc27_career_world_clubs(edition,club_key)
);
CREATE INDEX fc27_app_current_squad
 ON fc27_app_player_registration(edition,current_club_key);
CREATE TABLE fc27_app_transfer_ledger (
  edition INTEGER NOT NULL CHECK(edition=2027),
  ledger_id INTEGER PRIMARY KEY AUTOINCREMENT,
  transaction_key TEXT NOT NULL UNIQUE,
  player_key TEXT NOT NULL,
  source_club_key TEXT NOT NULL,
  destination_club_key TEXT NOT NULL,
  source_revision INTEGER NOT NULL,
  destination_revision INTEGER NOT NULL,
  transfer_reason TEXT NOT NULL CHECK(
    transfer_reason IN ('permanent_transfer','loan_registration','season_promotion_reassignment')),
  FOREIGN KEY (edition,player_key)
    REFERENCES fc27_app_player_registration(edition,player_key),
  FOREIGN KEY (edition,source_club_key)
    REFERENCES fc27_career_world_clubs(edition,club_key),
  FOREIGN KEY (edition,destination_club_key)
    REFERENCES fc27_career_world_clubs(edition,club_key)
);
CREATE TABLE fc27_verified_pes_team_identity (
  edition INTEGER NOT NULL CHECK(edition=2027),
  platform TEXT NOT NULL CHECK(platform IN ('pc','ps4')),
  club_key TEXT NOT NULL,
  pes_team_id INTEGER NOT NULL CHECK(pes_team_id>0),
  actual_game_data_evidence TEXT NOT NULL,
  PRIMARY KEY(edition,platform,club_key),
  UNIQUE(edition,platform,pes_team_id),
  FOREIGN KEY(edition,club_key)
   REFERENCES fc27_career_world_clubs(edition,club_key)
);
CREATE TABLE fc27_verified_pes_player_identity (
  edition INTEGER NOT NULL CHECK(edition=2027),
  platform TEXT NOT NULL CHECK(platform IN ('pc','ps4')),
  player_key TEXT NOT NULL,
  pes_player_id INTEGER NOT NULL CHECK(pes_player_id>0),
  actual_game_data_evidence TEXT NOT NULL,
  PRIMARY KEY(edition,platform,player_key),
  UNIQUE(edition,platform,pes_player_id),
  FOREIGN KEY(edition,player_key)
   REFERENCES fc27_app_player_registration(edition,player_key)
);
CREATE VIEW fc27_playable_current_squad AS
 SELECT p.edition,p.player_key,p.source_player_id,p.player_name,
        p.source_club_key,p.current_club_key,
        c.original_club AS current_club_name,c.competition_code,
        p.primary_position,p.secondary_positions_json,
        p.pes_abilities_json,p.pes_additional_json,
        p.registration_revision
 FROM fc27_app_player_registration p
 JOIN fc27_career_world_clubs c
   ON c.edition=p.edition AND c.club_key=p.current_club_key
 WHERE c.competition_mode IN
   ('open_league_season_candidate','playable_closed_league_candidate');
"""

def _validated_ratings(abilities,extra):
    if not isinstance(abilities,dict) or set(abilities)!=set(ATTRS):
        raise ValueError("Source player profile has missing or unexpected PES rating fields")
    if any(type(x) is not int or not 40<=x<=99 for x in abilities.values()):
        raise ValueError("Source PES estimates must have 25 complete integer 40-99 attributes")
    if not isinstance(extra,dict) or set(extra)!=set(AUX):
        raise ValueError("Source profile has missing or unexpected auxiliary fields")
    if any(type(x) is not int for x in extra.values()):
        raise ValueError("All auxiliary fields require original integer values")

def _checked_world(db):
    source=dict(db.execute("""
      SELECT club_key,original_club FROM fc27_career_world_clubs WHERE edition=2027
    """))
    n=db.execute("""
      SELECT COUNT(*) FROM fc27_effective_manager_selectable_original_clubs
    """).fetchone()[0]
    if len(source)!=EXPECTED_GAME_CLUBS or n!=EXPECTED_PLAYABLE_CLUBS:
        raise ValueError("FC27 current 659-source / 344-selectable club world mismatch")
    if db.execute("""
      SELECT COUNT(*) FROM edition_readiness WHERE edition=2027 AND career_ready!=0
    """).fetchone()[0]:
        raise ValueError("Cannot merge preliminary source squads into a live career")
    return source

def install(db:sqlite3.Connection, men_only_db:Path|str, *, strict=True):
    """Build a *copy* of the active app player world; read historical source only."""
    clubs=_checked_world(db)
    men=Path(men_only_db).resolve()
    if not men.is_file():
        raise FileNotFoundError("Read-only historical player catalogue missing")
    uri=f"file:{men.as_posix()}?mode=ro"
    with sqlite3.connect(uri,uri=True) as historical:
        count=historical.execute("""
           SELECT COUNT(*) FROM players WHERE edition=2027
        """).fetchone()[0]
        if strict and count!=EXPECTED_SOURCE_PLAYER_ROWS:
            raise ValueError("Historical men-only player source edition drift")
        original_keys={key for (key,) in historical.execute("""
          SELECT club_key FROM clubs WHERE edition=2027
        """)}
        if not set(clubs).issubset(original_keys):
            raise ValueError("One or more original FC27 game clubs missing from men-only catalogue")
        rows=[]
        excluded=0
        for (player_key,sid,name,club_key,assignment,position,alternatives,ability,addition) in historical.execute("""
            SELECT player_key,source_player_id,player_name,club_key,assignment,
                   primary_position,alternative_positions,pes_abilities_json,
                   pes_additional_json
            FROM players WHERE edition=2027 ORDER BY source_row_number
        """):
            if club_key not in clubs:
                excluded+=1
                continue
            if assignment!="at_club" or not club_key or not name.strip():
                raise ValueError("An active source-club player has unverified club assignment")
            stats=json.loads(ability);extra=json.loads(addition)
            _validated_ratings(stats,extra)
            if not isinstance(json.loads(alternatives),list):
                raise ValueError("Source position alternatives are not a list")
            rows.append((2027,player_key,sid,name,club_key,club_key,position,
                         alternatives,ability,addition,0))
    if strict and (len(rows)!=EXPECTED_ACTIVE_PLAYER_ROWS or
                   excluded!=EXPECTED_SOURCE_PLAYER_ROWS-EXPECTED_ACTIVE_PLAYER_ROWS):
        raise ValueError("FC27 17,593 active player identities / excluded source population changed")
    if len({r[1] for r in rows})!=len(rows):
        raise ValueError("Source player key collision; cannot merge player IDs")
    db.executescript(SCHEMA)
    db.executemany("""
      INSERT INTO fc27_app_player_registration
      VALUES(?,?,?,?,?,?,?,?,?,?,?)
    """,rows)
    expected_playable=db.execute("""
      SELECT COUNT(*) FROM fc27_playable_current_squad
    """).fetchone()[0]
    if strict and expected_playable!=9269:
        raise ValueError("FC27 initial playable player headcount changed")
    if db.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("Player source registration introduced orphan clubs")
    return {
      "edition":2027,"historical_mens_source_player_rows":count,
      "active_app_player_rows":len(rows),
      "original_player_rows_outside_active_FC27_world":excluded,
      "playable_squad_players_at_start":expected_playable,
      "source_clubs_with_current_registrations":db.execute("""
        SELECT COUNT(DISTINCT current_club_key) FROM fc27_app_player_registration
      """).fetchone()[0],
      "active_source_club_ID_direct_matches":len(clubs),
      "initial_game_team_ID_crosswalks":0,
      "initial_game_player_ID_crosswalks":0,
      "original_source_memberships_mutated":False,
      "game_binary_file_created":False
    }

def move_player(db:sqlite3.Connection, *,player_key:str, from_club_key:str,
                to_club_key:str, transaction_key:str,
                reason:str="permanent_transfer"):
    """Exact source-key move, optimistic revision + replay-safe transaction ID."""
    if reason not in ("permanent_transfer","loan_registration","season_promotion_reassignment"):
        raise ValueError("Unsupported registration reason")
    if not transaction_key or not transaction_key.strip():
        raise ValueError("Transfer needs a deterministic external transaction key")
    if from_club_key==to_club_key:
        raise ValueError("Cannot move player to same club")
    existing=db.execute("""
       SELECT player_key,source_club_key,destination_club_key,transfer_reason
       FROM fc27_app_transfer_ledger WHERE transaction_key=?
    """,(transaction_key,)).fetchone()
    if existing:
        if existing!=(player_key,from_club_key,to_club_key,reason):
            raise ValueError("Duplicate transaction key reused for different transfer")
        return {"status":"already_applied","player_key":player_key}
    reg=db.execute("""
       SELECT current_club_key,registration_revision
       FROM fc27_app_player_registration WHERE edition=2027 AND player_key=?
    """,(player_key,)).fetchone()
    if reg is None:
        raise ValueError("Player does not belong to registered FC27 app world")
    if reg[0]!=from_club_key:
        raise ValueError("Player no longer registered at asserted selling club")
    if not db.execute("""
       SELECT 1 FROM fc27_career_world_clubs WHERE edition=2027 AND club_key=?
    """,(to_club_key,)).fetchone():
        raise ValueError("Receiving club not registered in app world")
    next_revision=reg[1]+1
    with db:
        changed=db.execute("""
           UPDATE fc27_app_player_registration
           SET current_club_key=?,registration_revision=?
           WHERE edition=2027 AND player_key=?
             AND current_club_key=? AND registration_revision=?
        """,(to_club_key,next_revision,player_key,from_club_key,reg[1]))
        if changed.rowcount!=1:
            raise ValueError("Concurrent transfer changed current club registration")
        db.execute("""
          INSERT INTO fc27_app_transfer_ledger
          (edition,transaction_key,player_key,source_club_key,
           destination_club_key,source_revision,destination_revision,transfer_reason)
          VALUES (2027,?,?,?,?,?,?,?)
        """,(transaction_key,player_key,from_club_key,to_club_key,reg[1],
             next_revision,reason))
    return {"status":"applied","player_key":player_key,
            "from_club_key":from_club_key,"to_club_key":to_club_key,
            "revision":next_revision}

def register_verified_pes_slot(db:sqlite3.Connection,*,platform:str,
      kind:str,source_key:str,pes_numeric_id:int,actual_game_data_evidence:str):
    """Explicit game-file verified IDs only; never infer from FIFA source IDs."""
    if platform not in ("pc","ps4") or kind not in ("team","player"):
        raise ValueError("Only PC/PS4 verified PES2020 team/player mappings supported")
    if type(pes_numeric_id) is not int or pes_numeric_id<=0:
        raise ValueError("PES numeric game file ID must be verified positive integer")
    if len(actual_game_data_evidence.strip())<12:
        raise ValueError("PES mapping needs meaningful evidence from an actual game edit file")
    table=("fc27_verified_pes_team_identity" if kind=="team"
           else "fc27_verified_pes_player_identity")
    column="club_key" if kind=="team" else "player_key"
    with db:
        db.execute(f"""INSERT INTO {table}
         (edition,platform,{column},pes_{kind}_id,actual_game_data_evidence)
         VALUES(2027,?,?,?,?)""",
         (platform,source_key,pes_numeric_id,actual_game_data_evidence))

def export_playable_preview(db:sqlite3.Connection,output:Path|str,*,platform="pc"):
    """CSV for manual review and adapter integration; never PES native file."""
    if platform not in ("pc","ps4"):
        raise ValueError("No native external option-file import on Xbox PES2020")
    dest=Path(output);dest.mkdir(parents=True,exist_ok=True)
    clubs=_checked_world(db)
    rows=db.execute("""
       SELECT p.player_key,p.player_name,p.source_player_id,
              p.source_club_key,p.current_club_key,
              p.current_club_name,p.competition_code,
              p.primary_position,p.secondary_positions_json,
              p.pes_abilities_json,p.pes_additional_json,p.registration_revision,
              t.pes_team_id,i.pes_player_id
       FROM fc27_playable_current_squad p
       LEFT JOIN fc27_verified_pes_team_identity t
        ON t.edition=p.edition AND t.club_key=p.current_club_key
         AND t.platform=?
       LEFT JOIN fc27_verified_pes_player_identity i
        ON i.edition=p.edition AND i.player_key=p.player_key
         AND i.platform=?
       ORDER BY p.current_club_name,p.player_name,p.player_key
    """,(platform,platform)).fetchall()
    header=("app_player_key","source_player_id","player_name","source_club_key",
            "current_club_key","current_club_name","competition_code","primary_position",
            "alternative_positions_json","registration_revision","pes_team_id",
            "pes_player_id","pes_mapping_status")+ATTRS+AUX
    output_rows=[]
    no_team=no_player=0
    for key,name,sid,source,club,clubname,league,pos,alts,abilities,add,revision,teamid,pid in rows:
        ability=json.loads(abilities);aux=json.loads(add)
        _validated_ratings(ability,aux)
        if teamid is None:no_team+=1
        if pid is None:no_player+=1
        status=("verified_game_ids" if teamid is not None and pid is not None
                else "missing_both_game_ids" if teamid is None and pid is None
                else "missing_team_game_id" if teamid is None
                else "missing_player_game_id")
        output_rows.append((key,sid,name,source,club,clubname,league,pos,alts,revision,
                            teamid if teamid is not None else "",
                            pid if pid is not None else "",status)+
                           tuple(ability[x] for x in ATTRS)+tuple(aux[x] for x in AUX))
    target=dest/"FC27_PLAYABLE_CURRENT_SQUADS_PES2020_REVIEW_ONLY.csv"
    with target.open("w",newline="",encoding="utf-8-sig") as stream:
        writer=csv.writer(stream);writer.writerow(header);writer.writerows(output_rows)
    missing_clubs=db.execute("""
       SELECT COUNT(*) FROM fc27_effective_manager_selectable_original_clubs c
       LEFT JOIN fc27_verified_pes_team_identity t
         ON t.edition=c.edition AND t.club_key=c.club_key AND t.platform=?
       WHERE t.club_key IS NULL
    """,(platform,)).fetchone()[0]
    payload={
      "edition":2027,"platform":platform,
      "original_selectable_clubs":EXPECTED_PLAYABLE_CLUBS,
      "registered_players_currently_at_playable_clubs":len(rows),
      "missing_pes_team_mappings_for_playable_clubs":missing_clubs,
      "playable_player_rows_missing_pes_team_id":no_team,
      "playable_player_rows_missing_pes_player_id":no_player,
      "native_pes_edit_file_created":False,
      "ready_for_game_import":False,
      "source_player_ids_are_not_pes_player_ids":True,
      "source_and_current_club_membership_are_distinct":True,
      "csv_sha256":hashlib.sha256(target.read_bytes()).hexdigest(),
    }
    (dest/"FC27_PES_SQUAD_SYNC_READINESS.json").write_text(
        json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    return payload

def require_native_export_ready(db:sqlite3.Connection,*,platform="pc"):
    """Reject fake completeness; actual platform-specific writer still separate."""
    if platform not in ("pc","ps4"):
        raise ValueError("Unsupported native PES2020 edit-file target")
    missing_team=db.execute("""
       SELECT COUNT(*) FROM fc27_effective_manager_selectable_original_clubs c
       LEFT JOIN fc27_verified_pes_team_identity t
        ON t.edition=c.edition AND t.club_key=c.club_key AND t.platform=?
       WHERE t.club_key IS NULL
    """,(platform,)).fetchone()[0]
    missing_player=db.execute("""
       SELECT COUNT(*) FROM fc27_playable_current_squad c
       LEFT JOIN fc27_verified_pes_player_identity p
        ON p.edition=c.edition AND p.player_key=c.player_key AND p.platform=?
       WHERE p.player_key IS NULL
    """,(platform,)).fetchone()[0]
    if missing_team or missing_player:
        raise ValueError(f"Native PES2020 edit export blocked: {missing_team} teams and {missing_player} players lack verified game IDs")
    raise NotImplementedError("Native PES2020 game-file writer not built; review-only CSV supported")

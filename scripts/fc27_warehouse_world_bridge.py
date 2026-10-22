"""Import the *approved 659-club* FC27 warehouse into a NEW disposable world.

This is separate from the older 670-club FIFA edition importer. It does not
overwrite historical datasets, existing careers, Render or PES files. Source
club/player keys and snapshot SHA256 are kept for audit and career lineage.
Use only the 2026/27 immutable snapshot with the explicitly reviewed scope.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

EDITION=2027
DATASET="fc27-warehouse-659-mens-2026-27"
SEASON="2026/27"
DATE="2026-08-01"
SOURCE_NAME="FC27-WAREHOUSE-659"
CREATED_NOTE="FC27 immutable 659-club source snapshot; game wages/finance modelled"

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as file:
        while chunk:=file.read(1024*1024):
            h.update(chunk)
    return h.hexdigest()

def build_world(reference_path,target_path):
    from world_historical_career_import import initialize_target
    reference=Path(reference_path).resolve()
    destination=Path(target_path).resolve()
    if not reference.is_file():raise FileNotFoundError(reference)
    if destination.exists():raise FileExistsError("Refuse to replace any existing career/world")
    destination.parent.mkdir(parents=True,exist_ok=True)
    sha=digest(reference)
    try:
        with sqlite3.connect(destination) as db:
            db.execute("PRAGMA foreign_keys=ON")
            initialize_target(db)
            db.execute("ATTACH DATABASE ? AS frozen",(f"file:{reference.as_posix()}?mode=ro",))
            info=db.execute("""SELECT edition,season,state,immutable_source_clubs,
                    source_active_players FROM frozen.wh_fc27_snapshot""").fetchone()
            if info!=(2027,"2026/27","frozen_reference_not_live_career",659,17593):
                raise ValueError("Must import the exact approved 659-club FC27 warehouse")
            leagues=list(db.execute("""SELECT competition_code,country,name,tier,
                starting_original_clubs,intended_playable,game_movement
                FROM frozen.wh_fc27_competitions WHERE edition=2027
                ORDER BY competition_code"""))
            clubs=list(db.execute("""SELECT club_key,name,competition_code,career_scope
                FROM frozen.wh_fc27_clubs WHERE edition=2027 ORDER BY club_key"""))
            registrations=list(db.execute("""SELECT r.player_key,r.club_key,p.name,
                p.date_of_birth,p.nationality,p.primary_position,p.source_player_id,
                p.source_overall,p.alternative_positions_json,p.position_fit_indices_json,
                p.preferred_foot,p.height_cm,p.weight_kg,c.weekly_game_wage_gbp,
                c.contract_expires_on,c.wage_provenance
                FROM frozen.wh_fc27_starting_rosters r
                JOIN frozen.wh_fc27_players p ON p.edition=r.edition
                   AND p.player_key=r.player_key
                JOIN frozen.wh_fc27_starting_contracts c ON c.edition=r.edition
                   AND c.player_key=r.player_key
                WHERE r.edition=2027 ORDER BY r.player_key"""))
            if len(clubs)!=659 or len(registrations)!=17593 or len(leagues)!=53:
                raise ValueError("FC27 club/league/registered-player reconciliation drift")
            db.execute("""CREATE TABLE fc27_warehouse_import_audit(
               dataset_id TEXT PRIMARY KEY,source_sha256 TEXT NOT NULL,
               source_clubs INTEGER NOT NULL,source_players INTEGER NOT NULL,
               original_source_competitions INTEGER NOT NULL,
               provenance TEXT NOT NULL)""")
            db.execute("""INSERT OR IGNORE INTO world_seasons
              (season_id,label,start_date,registration_lock) VALUES(?,?,?,?)""",
              (SEASON,SEASON,DATE,DATE))
            db.execute("""INSERT INTO world_datasets
              (dataset_id,season_id,title,source_label,source_date,status)
              VALUES(?,?,?,?,?,'review')""",(DATASET,SEASON,
              "FC27 659-club source-identity QA world",CREATED_NOTE,DATE))
            codes={}
            for code,country,name,tier,size,playable,movement in leagues:
                identifier="WH27-"+hashlib.sha256(code.encode()).hexdigest()[:15]
                db.execute("""INSERT INTO world_competitions
                 (competition_id,name,country,tier,expected_clubs)
                 VALUES(?,?,?,?,?)""",(identifier,name+" [FC27-659]",country,tier,size))
                codes[code]=identifier
            mapping={}
            for key,name,competition,scope in clubs:
                # Preserve the *original* exact key in a source map, never
                # merge identity merely because two clubs share a display name.
                display=name+" [WH27:"+hashlib.sha256(key.encode()).hexdigest()[:10]+"]"
                cid=db.execute("""INSERT INTO world_clubs
                     (name,nation,finances_source) VALUES(?,?,?)""",
                     (display,next(x[1] for x in leagues if x[0]==competition),
                      "FC27 source club financial game model")).lastrowid
                mapping[key]=cid
                db.execute("""INSERT INTO world_dataset_entries
                  (dataset_id,competition_id,club_id) VALUES(?,?,?)""",
                  (DATASET,codes[competition],cid))
                db.execute("""INSERT INTO world_dataset_pes_v2_club_map
                     (dataset_id,source_key,world_id) VALUES(?,?,?)""",
                     (DATASET,key,cid))
            finances=list(db.execute("""SELECT club_key,game_transfer_budget_gbp,
                game_wage_budget_weekly_gbp FROM frozen.wh_fc27_club_financials
                WHERE edition=2027"""))
            if len(finances)!=659:raise ValueError("Incomplete source finances")
            db.executemany("""INSERT INTO world_dataset_club_finances
                (dataset_id,club_id,transfer_budget_gbp,weekly_wage_budget_gbp,
                 source_name) VALUES(?,?,?,?,?)""",
                ((DATASET,mapping[key],transfer,wage,
                 "GAME_MODEL:FC27_659_source_financial_capacity")
                 for key,transfer,wage in finances))
            player_ids={}
            for (key,club,name,dob,nation,pos,srcid,overall,other,fit,
                 foot,height,weight,wage,expires,wage_origin) in registrations:
                pid=db.execute("""INSERT INTO world_players
                  (full_name,birth_date,nationality,primary_position,source_url)
                  VALUES(?,?,?,?,?)""",(name,dob,nation,pos,
                  "FC27 edition-source, immutable warehouse reference")).lastrowid
                player_ids[key]=pid
                db.execute("""INSERT INTO world_player_source_refs
                 (player_id,source_name,external_id,source_url,identity_status)
                 VALUES(?,?,?,?,?)""",
                 (pid,SOURCE_NAME,key,"FC27 source player key",
                  "edition_scoped_source"))
                db.execute("""INSERT INTO world_dataset_pes_v2_player_map
                 (dataset_id,source_key,world_id) VALUES(?,?,?)""",(DATASET,key,pid))
                db.execute("""INSERT INTO world_dataset_rosters
                 (dataset_id,player_id,club_id,evidence,verification_status)
                 VALUES(?,?,?,?,?)""",(DATASET,pid,mapping[club],
                  "immutable source starting roster","source_snapshot"))
                db.execute("""INSERT INTO world_dataset_pes_v2_player_details
                 (dataset_id,player_id,preferred_foot,height_cm,weight_kg,
                  alternative_positions_json,position_fit_json)
                 VALUES(?,?,?,?,?,?,?)""",(DATASET,pid,foot,height,weight,other,fit))
                if overall is not None:
                    if type(overall) is not int or not 1<=overall<=99:
                        raise ValueError("Source overall outside 1–99")
                    db.execute("""INSERT INTO world_dataset_ratings
                     (dataset_id,player_id,source_name,source_edition,
                      source_date,external_player_id,overall)
                     VALUES(?,?,?,?,?,?,?)""",
                     (DATASET,pid,"FIFA/FC original source","2027",DATE,key,overall))
                if not isinstance(wage,int) or not 0<=wage<=1_000_000:
                    raise ValueError("Missing/bad source game wage")
                db.execute("""INSERT INTO world_dataset_contract_snapshots
                 (dataset_id,player_id,club_id,weekly_wage_gbp,expires_on,
                  renewal_status,source_name)
                 VALUES(?,?,?,?,?,'unknown',?)""",
                 (DATASET,pid,mapping[club],wage,expires,
                 "FC27-659:"+wage_origin))
            # No magic new original personality or skill estimates. Retain
            # all 25 + 4 approved PES2020 V2 attribute scores individually.
            attrs=db.execute("""SELECT player_key,attribute_key,value
              FROM frozen.wh_fc27_player_attributes WHERE edition=2027
              ORDER BY player_key,attribute_key""")
            attr_count=0
            for key,label,value in attrs:
                if key not in player_ids:raise ValueError("Unregistered attribute owner")
                if type(value) is not int or not 1<=value<=200:
                    raise ValueError("PES attribute outside allowed converter range")
                db.execute("""INSERT INTO world_dataset_extended_attributes
                 (dataset_id,player_id,attribute,value,source_name)
                 VALUES(?,?,?,?,?)""",
                 (DATASET,player_ids[key],"PES2020V2:"+label,value,
                  "FIFA/FC-to-PES2020 V2 source-derived game estimate"))
                attr_count+=1
            if attr_count!=17593*29:
                raise ValueError("Incomplete 29-attribute converted player ratings")
            loan_count=db.execute("""SELECT COUNT(*) FROM
              frozen.wh_fc27_starting_loans WHERE edition=2027""").fetchone()[0]
            # Original approved release has zero source loans for FC27.
            # A future positive count requires full parent/borrower audit.
            if loan_count:
                raise ValueError("Source loan terms not validated for this bridge")
            db.execute("""INSERT INTO world_dataset_historical_finance_policy
                (dataset_id,model_version,provenance) VALUES(?,?,?)""",
                (DATASET,"FC27-659-game-finance-v1",
                 "Original source pay plus bounded simulation club wage ceilings"))
            db.execute("""INSERT INTO world_dataset_pes_v2_metadata
               (dataset_id,edition,unknown_source_player_rows,source_sha256,
                model_finance_sha256,circumstances_sha256,source_provenance)
               VALUES(?,?,?,?,?,?,?)""",
               (DATASET,2027,256,sha,sha,sha,
                "Approved 659 active source clubs, exact identity; QA-only hierarchy"))
            db.execute("""INSERT INTO fc27_warehouse_import_audit
                VALUES(?,?,?,?,?,?)""",
                (DATASET,sha,659,17593,53,
                 "All source keys explicit; game model finance never reported actual"))
            if db.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("Broken foreign-key mapping")
            db.commit()
            counts={
                "source_clubs":len(clubs),"source_competitions":len(leagues),
                "source_registered_players":len(registrations),
                "modelled_financial_profiles":len(finances),
                "pes_attribute_values":attr_count,
                "source_loans":loan_count,
                "source_sha256":sha,
                "dataset_id":DATASET,
                "production_deployment":False,
                "source_was_read_only":True,
                "historical_competition_validation_bypassed_for_disposable_QA_only":True
            }
            (destination.parent/(destination.stem+".import_audit.json")).write_text(
                json.dumps(counts,indent=2)+"\n",encoding="utf-8")
            return counts
    except Exception:
        if destination.exists():destination.unlink()
        raise

if __name__=="__main__":
    pa=argparse.ArgumentParser()
    pa.add_argument("--warehouse",required=True)
    pa.add_argument("--target",required=True)
    args=pa.parse_args()
    print(json.dumps(build_world(args.warehouse,args.target),indent=2),flush=True))

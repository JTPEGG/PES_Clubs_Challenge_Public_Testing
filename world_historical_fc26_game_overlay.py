"""Add uniquely reconciled FC26 in-game leagues to historical career staging.

Independent fixture evidence and FIFA15-23 game source take precedence.
Use original FC26 binary game team ID only after same-edition unique name
validation from pinned FC26 data. No game files, squads, saves changed.
"""
from __future__ import annotations
import argparse,csv,json,sqlite3
from pathlib import Path
PIN="7592f1734afff43d7dbc7161565732e9ba3d28bc"
VERSION="original-fc26-game-home-league-overlay-v1"
SCHEMA="""
CREATE TABLE original_fc26_binary_team_leagues(
 edition INTEGER NOT NULL CHECK(edition=2026),club_key TEXT NOT NULL,
 game_team_id TEXT NOT NULL,game_team_name TEXT NOT NULL,
 game_league_id TEXT NOT NULL,game_league_name TEXT NOT NULL,
 game_league_tier INTEGER NOT NULL,source_commit TEXT NOT NULL,
 evidence_method TEXT NOT NULL CHECK(evidence_method='unique_same_edition_game_name_pinned_club_id'),
 FOREIGN KEY(edition,club_key) REFERENCES edition_club_competitions(edition,club_key),
 PRIMARY KEY(edition,club_key));
CREATE VIEW full_historical_club_starting_leagues AS
 SELECT e.edition,e.club_key,e.club,
    COALESCE(e.starting_competition,
        CASE WHEN x.game_league_id IS NOT NULL THEN 'GAME:2026:'||x.game_league_id END)
        AS starting_competition,
    CASE WHEN e.starting_competition IS NOT NULL THEN e.evidence_origin
         WHEN x.game_league_id IS NOT NULL THEN 'original_fc26_binary_game_league'
         ELSE 'unresolved' END AS evidence_origin,
    COALESCE(e.game_league_id,x.game_league_id) AS game_league_id,
    COALESCE(e.game_league_name,x.game_league_name) AS game_league_name,
    COALESCE(e.game_source_tier,x.game_league_tier) AS game_source_tier,
    e.career_status
 FROM expanded_historical_club_starting_leagues e
 LEFT JOIN original_fc26_binary_team_leagues x
 ON e.edition=x.edition AND e.club_key=x.club_key;
"""

def collect(source_sqlite,fc26_csv,output,strict=True):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    target=out/"HISTORICAL_COMPETITION_REGISTER_22_EDITION_FC26_EXTENDED.sqlite"
    if target.exists():raise FileExistsError("No overwriting historical source releases")
    with sqlite3.connect(f"file:{Path(source_sqlite).resolve()}?mode=ro",uri=True) as db,\
         sqlite3.connect(target) as dest:
        db.backup(dest)
    with open(fc26_csv,encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    keys=("Edition","Original_Club_Key","Original_Club","Game_Team_ID","Game_Team",
          "Game_League_ID","Game_League","Tier","Coverage","Evidence_Method")
    if not rows or not set(keys).issubset(rows[0]):
        raise ValueError("Invalid 2026 archived game club team league source")
    evidence=[]
    for row in rows:
        if row["Edition"]!="2026" or row["Coverage"] not in ("already_sourced","new_game_league"):
            raise ValueError("FC26 team identity evidence or year invalid")
        if row["Evidence_Method"]!="unique_same_edition_game_name_pinned_club_id" or row["Tier"] not in ("1","2","3","4"):
            raise ValueError("Non-game original club/league level not permitted")
        if not row["Game_Team_ID"].isdigit() or not row["Game_League_ID"].isdigit():
            raise ValueError("Invalid official numeric game IDs")
        evidence.append((2026,row["Original_Club_Key"],row["Game_Team_ID"],
                         row["Game_Team"],row["Game_League_ID"],row["Game_League"],
                         int(row["Tier"]),PIN,row["Evidence_Method"]))
    with sqlite3.connect(target) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(SCHEMA)
        names={str(k):v for k,v in db.execute(
            "SELECT club_key,club FROM edition_club_competitions WHERE edition=2026")}
        for row,payload in zip(rows,evidence):
            if names.get(row["Original_Club_Key"])!=row["Original_Club"]:
                raise ValueError("FC26 input original club name drift")
        db.executemany("INSERT INTO original_fc26_binary_team_leagues VALUES (?,?,?,?,?,?,?,?,?)",evidence)
        before=db.execute("SELECT COUNT(*) FROM expanded_historical_club_starting_leagues WHERE starting_competition IS NOT NULL").fetchone()[0]
        after=db.execute("SELECT COUNT(*) FROM full_historical_club_starting_leagues WHERE starting_competition IS NOT NULL").fetchone()[0]
        new=after-before
        if strict and (len(rows)!=499 or new!=128 or before!=8544):
            raise ValueError("Not the verified original FC26 and 22-edition source cohorts")
        if new!=sum(row["Coverage"]=="new_game_league" for row in rows):
            raise ValueError("FC26 original game links unexpectedly conflict with existing evidence")
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok" or db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Invalid 22-edition FC26 source overlay SQLite")
        if db.execute("SELECT COUNT(*) FROM edition_readiness WHERE career_ready!=0").fetchone()[0]:
            raise ValueError("Unverified historical careers cannot be activated")
        db.commit()
    report=dict(version=VERSION,original_22_edition_game_clubs=13104,
        previous_club_seasons_with_home_league_evidence=before,
        fc26_source_game_name_links=len(rows),new_fc26_original_game_home_leagues=new,
        combined_club_seasons_with_starting_league_evidence=after,
        original_game_club_seasons_remaining_unresolved=13104-after,
        source_commit=PIN,game_year=2026,
        original_squads_untouched=True,career_ready_editions=0)
    (out/"COMPLETE_22_EDITION_FC26_GAME_LEAGUE_AUDIT.json").write_text(
         json.dumps(report,indent=2),encoding="utf-8")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--registry",required=True)
    p.add_argument("--source",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--no-strict",action="store_true")
    a=p.parse_args()
    print(json.dumps(collect(a.registry,a.source,a.output,not a.no_strict),indent=2))

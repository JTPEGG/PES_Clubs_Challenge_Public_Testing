"""Non-destructive early FIFA (2005-2014) Spanish tier-2 evidence overlay.

Source unique same-edition Spanish Segunda name candidates; independently
sourced from dated CC0 fixtures. Never approve an ambiguous EA identity or
a future-season club move. Career activation remains blocked.
"""
from __future__ import annotations
import argparse
import csv
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

from world_historical_competition_registry import canonical

VERSION="segundo-historico-fifa05-14-staged-v1"
VIEW="edition_career_starting_league_candidates"
SCHEMA="""
CREATE TABLE early_spanish_segunda_season_sources(
 edition INTEGER NOT NULL, league_code TEXT NOT NULL,
 season TEXT NOT NULL, expected_clubs INTEGER NOT NULL CHECK(expected_clubs=22),
 source_url TEXT NOT NULL, source_sha256 TEXT NOT NULL,
 PRIMARY KEY(edition,league_code));
CREATE TABLE early_spanish_segunda_club_memberships(
 edition INTEGER NOT NULL, league_code TEXT NOT NULL,
 fixture_club TEXT NOT NULL, source_sha256 TEXT NOT NULL,
 PRIMARY KEY(edition,league_code,fixture_club),
 FOREIGN KEY(edition,league_code) REFERENCES early_spanish_segunda_season_sources(edition,league_code));
CREATE TABLE early_spanish_segunda_game_club_candidates(
 edition INTEGER NOT NULL, club_key TEXT NOT NULL,
 league_code TEXT NOT NULL,fixture_club TEXT NOT NULL,
 source_sha256 TEXT NOT NULL,
 evidence_method TEXT NOT NULL
   CHECK(evidence_method='unique_same_edition_canonical_name_provisional'),
 PRIMARY KEY(edition,club_key),
 FOREIGN KEY(edition,club_key) REFERENCES edition_club_competitions(edition,club_key));
CREATE VIEW edition_career_starting_league_candidates AS
 SELECT old.edition, old.club_key, old.club,
 COALESCE(old.starting_competition,
     CASE WHEN span.club_key IS NOT NULL THEN
        CAST(span.edition AS TEXT)||':'||span.league_code END) AS starting_competition,
 CASE WHEN old.starting_competition IS NOT NULL THEN old.evidence_origin
      WHEN span.club_key IS NOT NULL THEN 'segundo_spanish_fixture_same_name_provisional'
      ELSE 'unresolved' END AS evidence_origin,
 old.game_league_id,old.game_league_name,old.game_source_tier,
 old.career_status
 FROM full_historical_club_starting_leagues old
 LEFT JOIN early_spanish_segunda_game_club_candidates span
   ON span.edition=old.edition AND span.club_key=old.club_key;
"""


def load(path):
    with open(path,encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))


def build(source_db, leagues_csv, clubs_csv, matches_csv, output, strict=True):
    d=Path(output);d.mkdir(parents=True,exist_ok=True)
    output_db=d/"HISTORICAL_CAREER_DIVISION_CANDIDATES_22_EDITION.sqlite"
    if output_db.exists():
        raise FileExistsError("Never overwrite the historical source evidence release")
    with sqlite3.connect(f"file:{Path(source_db).resolve()}?mode=ro",uri=True) as source,\
         sqlite3.connect(output_db) as dest:
        source.backup(dest)
    leagues=load(leagues_csv);clubs=load(clubs_csv);matches=load(matches_csv)
    if strict and (len(leagues)!=10 or len(clubs)!=220):
        raise ValueError("Dated 2005-2014 Spanish Segunda roster coverage was not verified")
    seasons={}
    for row in leagues:
        y=int(row["Edition"]);code=row["League_Code"]
        if (y not in range(2005,2015) or code!="es.2" or
            int(row["Tier"])!=2 or int(row["Source_Clubs"])!=22 or
            row["Season"]!=f"{y-1}-{y%100:02d}" or
            row["Evidence_Status"]!="pinned_CC0_dated_fixture_memberships"):
            raise ValueError("Invalid historic Segunda season or division mapping")
        if (y,code) in seasons:
            raise ValueError("Duplicate source division")
        seasons[(y,code)]=(row["Season"],22,row["Source_URL"],row["SHA256"])
    members=defaultdict(set)
    for row in clubs:
        y=int(row["Edition"]);code=row["League_Code"];identity=(y,code)
        if (identity not in seasons or
            row["Source_URL"]!=seasons[identity][2] or
            row["SHA256"]!=seasons[identity][3] or
            row["Evidence_Status"]!="dated_fixture_team_not_independently_game_verified"):
            raise ValueError("Member is not in a dated CC0 Spanish Segunda source")
        norm=canonical(row["Club"])
        if norm in members[identity]:
            raise ValueError("Normalized fixture club name collides in year")
        members[identity].add(norm)
    if any(len(members[identity])!=22 for identity in seasons):
        raise ValueError("Historical Segunda source season incomplete")

    with sqlite3.connect(output_db) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(SCHEMA)
        original={(int(y),key):(name,group_type) for y,key,name,group_type in
            db.execute("SELECT edition,club_key,club,group_type FROM edition_club_competitions")}
        candidate_rows=[]
        for x in matches:
            y=int(x["Edition"]);key=x["FIFA_Club_Key"];league=x["League_Code"]
            ident=(y,league);original_info=original.get((y,key))
            if (ident not in seasons or not original_info or
                original_info[0]!=x["FIFA_Club"] or
                original_info[1]=="continental_cup_bucket" or
                canonical(x["Fixture_Club"]) not in members[ident] or
                x["SHA256"]!=seasons[ident][3] or
                x["Source_URL"]!=seasons[ident][2] or
                canonical(x["FIFA_Club"])!=canonical(x["Fixture_Club"]) or
                x["Evidence_Method"]!="unique_same_edition_canonical_name_provisional"):
                raise ValueError("Unsafe original FIFA club-to-dated Segunda match")
            candidate_rows.append((y,key,league,x["Fixture_Club"],x["SHA256"],x["Evidence_Method"]))
        db.executemany("""INSERT INTO early_spanish_segunda_season_sources
                            VALUES(?,?,?,?,?)""",((y,code,*v) for (y,code),v in seasons.items()))
        db.executemany("""INSERT INTO early_spanish_segunda_club_memberships
                            VALUES(?,?,?,?)""",(
          (int(x["Edition"]),x["League_Code"],x["Club"],x["SHA256"]) for x in clubs))
        db.executemany("""INSERT INTO early_spanish_segunda_game_club_candidates
                            VALUES(?,?,?,?,?,?)""",candidate_rows)
        old=db.execute("""SELECT COUNT(*) FROM full_historical_club_starting_leagues
             WHERE starting_competition IS NOT NULL""").fetchone()[0]
        new=db.execute("""SELECT COUNT(*) FROM edition_career_starting_league_candidates
             WHERE starting_competition IS NOT NULL""").fetchone()[0]
        assigned=new-old
        if strict and old!=8672:raise ValueError("Expected certified prior overlay with 8,672 league-evidenced clubs")
        if assigned>len(candidate_rows) or assigned<0:
            raise ValueError("New Spanish Segunda assignments exceed dated source evidence")
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok" or db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Final 22-edition SQLite integrity failure")
        if db.execute("SELECT COUNT(*) FROM edition_readiness WHERE career_ready!=0").fetchone()[0]:
            raise ValueError("Never silently activate unverified historic careers")
        db.commit()

    audit={"version":VERSION,
           "old_starting_league_evidence":old,
           "source_league_seasons":len(leagues),
           "source_fixture_club_memberships":len(clubs),
           "unique_same_edition_game_club_name_candidates":len(candidate_rows),
           "new_early_fifa_club_division_candidates":assigned,
           "combined_game_club_seasons_with_league_evidence":new,
           "game_club_seasons_still_unresolved":13104-new,
           "career_ready_editions":0,
           "no_original_squads_changed":True}
    (d/"EARLY_FIFA_2005_14_SEGUNDA_MERGE_AUDIT.json").write_text(
        json.dumps(audit,indent=2),encoding="utf-8")
    return audit


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--registry",required=True)
    p.add_argument("--leagues",required=True)
    p.add_argument("--clubs",required=True)
    p.add_argument("--matches",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--no-strict",action="store_true")
    a=p.parse_args()
    print(json.dumps(build(a.registry,a.leagues,a.clubs,a.matches,a.output,
                           strict=not a.no_strict),indent=2))

"""Integrate 11-country historical fixture membership matches with game leagues.

A deliberately separate evidence tier, preserving original game league and
sourced historic fixture records without overriding either. Match exact
canonical names ONLY when each game and each league has a unique same-edition
identity, then write a source-linked provisional league record.
"""
from __future__ import annotations
import argparse,csv,json,sqlite3
from collections import Counter,defaultdict
from pathlib import Path
from world_historical_competition_registry import canonical

VERSION="supplemental-european-match-member-overlay-v1"
PIN_SHA="c510a881aae5f8400c74dd62f78bc1a9322d697c98ec180f8beb78d9e21f724a"

SCHEMA="""
CREATE TABLE supplemental_european_match_leagues (
    edition INTEGER NOT NULL,code TEXT NOT NULL,
    source_competition_name TEXT NOT NULL,country TEXT NOT NULL,tier INTEGER NOT NULL,
    source_url TEXT NOT NULL,source_sha256 TEXT NOT NULL,
    PRIMARY KEY(edition,code));
CREATE TABLE supplemental_european_match_clubs(
    edition INTEGER NOT NULL,competition_code TEXT NOT NULL,
    club_name TEXT NOT NULL,source_url TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    PRIMARY KEY(edition,competition_code,club_name),
    FOREIGN KEY(edition,competition_code)
        REFERENCES supplemental_european_match_leagues(edition,code));
CREATE TABLE supplemental_european_fifa_club_evidence(
    edition INTEGER NOT NULL,club_key TEXT NOT NULL,
    competition_code TEXT NOT NULL,fixture_club TEXT NOT NULL,
    source_url TEXT NOT NULL,source_sha256 TEXT NOT NULL,
    evidence_confidence TEXT NOT NULL
       CHECK(evidence_confidence='same_edition_unique_club_name_provisional'),
    PRIMARY KEY(edition,club_key),
    FOREIGN KEY(edition,club_key)
        REFERENCES edition_club_competitions(edition,club_key));
CREATE VIEW expanded_historical_club_starting_leagues AS
 SELECT base.edition,base.club_key,base.club,
    COALESCE(base.starting_competition,supp.competition_code) AS starting_competition,
    CASE WHEN base.starting_competition IS NOT NULL THEN base.evidence_origin
         WHEN supp.competition_code IS NOT NULL THEN
             'independent_archived_match_member_name_provisional'
         ELSE 'unresolved' END AS evidence_origin,
    base.game_league_id,base.game_league_name,base.game_source_tier,
    base.career_status
 FROM historical_club_starting_leagues base
 LEFT JOIN supplemental_european_fifa_club_evidence supp
     ON supp.edition=base.edition AND supp.club_key=base.club_key;
"""
def getrows(path):
    with open(path,encoding="utf-8-sig",newline="") as h:
        return list(csv.DictReader(h))

def build(registry_source,league_csv,club_csv,output,strict=True):
    d=Path(output);d.mkdir(parents=True,exist_ok=True)
    result=d/"HISTORICAL_COMPETITION_REGISTER_WITH_EUROPEAN_SOURCE_LEAGUES.sqlite"
    if result.exists():raise FileExistsError("Never overwrite a previous dated evidence release")
    leagues=getrows(league_csv);clubs=getrows(club_csv)
    if strict and (len(leagues)!=87 or len(clubs)!=1474):
        raise ValueError("Pinned 11-country source club count differs from accepted audit")
    existing={}
    for item in leagues:
        y=int(item["Edition"]);code=item["Edition_Code"]
        if not 2009<=y<=2016 or code!=f"{y}:{item['League_Code']}":
            raise ValueError("Foreign edition in archived club league")
        if int(item["Tier"])!=1 or item["Evidence_Status"]!=(
            "season_match_team_ids_crosschecked_non_game_id"):
            raise ValueError("External match source is not a checked first division")
        if strict and item["Source_SHA256"]!=PIN_SHA:
            raise ValueError("Pinned match archive digest changed")
        if (y,code) in existing:raise ValueError("Duplicate edition competition")
        existing[(y,code)]=item
    sets=defaultdict(list)
    for row in clubs:
        y=int(row["Edition"]);code=f"{y}:{row['League_Code']}"
        if (y,code) not in existing or (
            row["Country"]!=existing[(y,code)]["Country"] or
            row["Source_SHA256"]!=existing[(y,code)]["Source_SHA256"] or
            row["Source_URL"]!=existing[(y,code)]["Source_URL"] or
            row["Evidence_Status"]!="independent_match_team_not_original_fifa_identity"):
            raise ValueError("Source club not pinned to a real dated season")
        sets[(y,canonical(row["Club"]))].append(row)
    import sqlite3
    with sqlite3.connect(f"file:{Path(registry_source).resolve()}?mode=ro",uri=True) as src,\
         sqlite3.connect(result) as dst:
        src.backup(dst)
    candidates=[];conflicts=[];counts=Counter()
    with sqlite3.connect(result) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(SCHEMA)
        for (y,code),rec in existing.items():
            db.execute("""INSERT INTO supplemental_european_match_leagues
                VALUES(?,?,?,?,?,?,?)""",(y,code,rec["Competition"],
                   rec["Country"],1,rec["Source_URL"],rec["Source_SHA256"]))
        db.executemany("INSERT INTO supplemental_european_match_clubs VALUES (?,?,?,?,?)",
           ((int(x["Edition"]),f"{x['Edition']}:{x['League_Code']}",
              x["Club"],x["Source_URL"],x["Source_SHA256"]) for x in clubs))
        originals=db.execute("""SELECT edition,club_key,club,starting_competition,
                         evidence_origin FROM historical_club_starting_leagues""").fetchall()
        game_names=defaultdict(list)
        for y,key,name,_,_ in originals:
            game_names[(int(y),canonical(name))].append((str(key),str(name)))
        for y,key,name,current,origin in originals:
            if current is not None:continue
            game_key=(int(y),canonical(name))
            matched=sets.get(game_key,[])
            if not matched:continue
            if len(game_names[game_key])!=1 or len(
                {(x["League_Code"],canonical(x["Club"])) for x in matched})!=1:
                conflicts.append((y,key,name,"ambiguous_game_or_source_name",
                                  " | ".join(sorted({x["League_Code"] for x in matched}))))
                counts["ambiguous_canonical_names"]+=1
                continue
            x=matched[0]
            candidates.append((y,key,f"{y}:{x['League_Code']}",x["Club"],
                               x["Source_URL"],x["Source_SHA256"],
                               "same_edition_unique_club_name_provisional"))
        db.executemany("""INSERT INTO supplemental_european_fifa_club_evidence
                   VALUES (?,?,?,?,?,?,?)""",candidates)
        expected=db.execute("SELECT COUNT(*) FROM historical_club_starting_leagues").fetchone()[0]
        before=db.execute("""SELECT COUNT(*) FROM historical_club_starting_leagues
                        WHERE starting_competition IS NOT NULL""").fetchone()[0]
        after=db.execute("""SELECT COUNT(*) FROM expanded_historical_club_starting_leagues
                        WHERE starting_competition IS NOT NULL""").fetchone()[0]
        if expected!=13104 and strict:raise ValueError("Not a verified original 22-edition catalogue")
        if before+len(candidates)!=after:raise ValueError("Source overlay lost club assignments")
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok" or db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Supplemental archive violates historic registry integrity")
        if db.execute("SELECT COUNT(*) FROM edition_readiness WHERE career_ready!=0").fetchone()[0]:
            raise ValueError("External source cannot turn on historical careers")
        db.commit()
    with (d/"NEW_EUROPEAN_MATCH_GAME_CLUB_CROSSWALK.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f);w.writerow(("Edition","Original_Game_Club_Key",
          "Independent_League_Code","Fixture_Club","Fixture_Source_URL",
          "Archive_SHA256","Evidence_Method"));w.writerows(candidates)
    with (d/"EUROPEAN_MATCH_NAME_AMBIGUITY_REVIEW.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f);w.writerow(("Edition","Original_Game_Club_Key","Club",
          "Issue","Candidate_Divisions"));w.writerows(conflicts)
    summary={"version":VERSION,"original_game_club_seasons":expected,
       "previous_league_evidence":before,"new_source_linked_club_seasons":len(candidates),
       "combined_club_seasons_with_league_evidence":after,
       "remaining_unresolved":expected-after,
       "external_match_source_league_seasons":len(leagues),
       "external_match_source_memberships":len(clubs),
       "name_collisions_pending_manual_review":len(conflicts),
       "does_not_certify_original_game_team_identity":True,
       "career_ready_editions":0,"original_source_squads_modified":False}
    (d/"EXPANDED_2009_16_LEAGUE_MATCH_AUDIT.json").write_text(
        json.dumps(summary,indent=2),encoding="utf-8")
    return summary

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--registry",required=True);p.add_argument("--leagues",required=True)
    p.add_argument("--clubs",required=True);p.add_argument("--output",required=True)
    p.add_argument("--no-strict",action="store_true")
    a=p.parse_args()
    print(json.dumps(build(a.registry,a.leagues,a.clubs,a.output,strict=not a.no_strict),indent=2))

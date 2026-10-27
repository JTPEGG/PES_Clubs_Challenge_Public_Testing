"""Stage FIFA15 England's full 92 real game club identities for a pilot.

90 game-club records already matched date-specific professional division
fixtures; Shrewsbury has an abbreviated original name; York City exists in
FIFA15 but was omitted by the supplied player/club dataset. Both missing
game-team ID facts are attested by original-edition FIFA Index team pages.

This is a NON-DESTRUCTIVE staging SQLite copy. York's 28 actual FIFA15
players still require source-attribute restoration before any playable
PES import; no guessed player fields or production career writes.
"""
from __future__ import annotations
import argparse,csv,json,sqlite3
from collections import defaultdict
from pathlib import Path
from world_historical_competition_registry import canonical
from world_historical_movement_rules import source_rules
from world_lightweight_feeder import rollover

EDITION=2015
EXPECTED={"2015:en.1":20,"2015:en.2":24,"2015:en.3":24,"2015:en.4":24}
VERSION="fifa15-92-original-game-team-identity-restore-pilot-v1"
SCHEMA="""
CREATE TABLE pilot_fifa15_provenance(
 edition INTEGER NOT NULL CHECK(edition=2015),
 source_url TEXT NOT NULL,source_status TEXT NOT NULL,
 source_football_season TEXT NOT NULL,allow_career INTEGER NOT NULL CHECK(allow_career=0));
CREATE TABLE pilot_fifa15_playable_club_placements(
 edition INTEGER NOT NULL CHECK(edition=2015),
 competition_code TEXT NOT NULL,
 source_fixture_club TEXT NOT NULL,
 game_club_key TEXT NOT NULL,
 game_display_name TEXT NOT NULL,
 verified_game_team_id INTEGER,
 source_url TEXT NOT NULL,
 game_team_page_url TEXT,
 original_import_status TEXT NOT NULL,
 gameplay_player_roster_status TEXT NOT NULL,
 PRIMARY KEY(edition,competition_code,source_fixture_club),
 UNIQUE(edition,game_club_key));
CREATE TABLE pilot_fifa15_conference_external_feeders(
 edition INTEGER NOT NULL CHECK(edition=2015),
 competition_code TEXT NOT NULL CHECK(competition_code='2015:en.5'),
 club_name TEXT NOT NULL,
 source_url TEXT NOT NULL,
 source_status TEXT NOT NULL,
 PRIMARY KEY(edition,competition_code,club_name));
"""

def build(original_db,identity_json,conference_json,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    dest=out/"FIFA15_ENGLAND_92_CLUB_SOURCE_STAGING.sqlite"
    if dest.exists():raise FileExistsError("Never overwrite existing historical source staging")
    identities=json.loads(Path(identity_json).read_text(encoding="utf-8"))
    league_meta=json.loads(Path(conference_json).read_text(encoding="utf-8"))
    if (identities.get("edition")!=EDITION or
        identities.get("league_code")!="2015:en.4" or
        league_meta.get("game_edition")!=EDITION or
        league_meta.get("competition_code")!="2015:en.5"):
        raise ValueError("Wrong-edition team identity or Conference feeder source")
    game_meta={canonical(x["source_english_league_name"]):x
               for x in identities.get("teams",[])}
    if set(game_meta)!={canonical("York City"),canonical("Shrewsbury Town")}:
        raise ValueError("Unapproved or incomplete original FIFA15 game team identity restorations")
    if {int(x["game_team_id"]) for x in game_meta.values()}!={127,1948}:
        raise ValueError("Wrong official game team IDs")
    if any(not x["source_game_team_url"].endswith("/fifa15") for x in game_meta.values()):
        raise ValueError("Wrong source edition for restoring FIFA15 clubs")
    with sqlite3.connect(f"file:{Path(original_db).resolve()}?mode=ro",uri=True) as src,\
         sqlite3.connect(dest) as db:
        src.backup(db)
    with sqlite3.connect(dest) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(SCHEMA)
        original=db.execute("""SELECT club_key,club FROM edition_club_competitions
                               WHERE edition=?""",(EDITION,)).fetchall()
        bygame=defaultdict(list)
        for key,name in original:bygame[canonical(name)].append((key,name))
        source=db.execute("""SELECT competition_code,club_name,source_url
                             FROM sourced_domestic_league_clubs
                             WHERE edition=? AND competition_code IN (?,?,?,?)
                             ORDER BY competition_code,club_name""",(EDITION,*EXPECTED)).fetchall()
        year_counts=defaultdict(int)
        staged=[]
        game_keys=set()
        exceptions=[]
        for code,fixture,url in source:
            year_counts[code]+=1
            game_matches=bygame[canonical(fixture)]
            meta=game_meta.get(canonical(fixture))
            if meta:
                game_matches=bygame[canonical(meta["game_team_name"])]
                if canonical(fixture)==canonical("York City"):
                    if game_matches:raise ValueError("York is unexpectedly in the original game club catalogue")
                    key="external_original_fifa_team:2015:1948"
                    name="York City"
                    import_status="real_FIFA15_game_club_missing_from_initial_import"
                    roster="SOURCE_ROSTER_RESTORATION_REQUIRED_28_PLAYERS"
                else:
                    if len(game_matches)!=1:raise ValueError("Shrewsbury ambiguous in original game catalogue")
                    key,name=game_matches[0]
                    import_status="original_game_club_present_with_abbreviated_name"
                    roster="original_source_imported_game_club_roster"
                source_id=int(meta["game_team_id"])
                if (source_id==127 and int(meta["source_game_roster_count"])!=34
                    or source_id==1948 and int(meta["source_game_roster_count"])!=28):
                    raise ValueError("Missing real original FIFA15 game team squad source")
                exceptions.append((code,fixture,key,name,source_id,meta["source_game_team_url"],roster))
            else:
                if len(game_matches)!=1:
                    raise ValueError(f"Still unresolved FIFA15 English original club identity: {fixture}")
                key,name=game_matches[0]
                source_id=None
                import_status="existing_original_catalogue_club_unique_source_fixture_name"
                roster="original_source_imported_game_club_roster"
            if key in game_keys:
                raise ValueError("One original FIFA15 club incorrectly assigned to multiple leagues")
            game_keys.add(key)
            staged.append((EDITION,code,fixture,key,name,source_id,url,
                            meta["source_game_team_url"] if meta else None,
                            import_status,roster))
        if year_counts!=EXPECTED or len(staged)!=92:
            raise ValueError("FIFA15 historical English 4-tier divisions lack genuine 92 team members")
        confirmed_extra=sum(x[8]=="real_FIFA15_game_club_missing_from_initial_import" for x in staged)
        if confirmed_extra!=1 or len(exceptions)!=2:
            raise ValueError("Original FIFA15 source restoration requires exactly York and Shrewsbury")
        league_names=league_meta.get("clubs",[])
        if len(league_names)!=24 or len({canonical(x) for x in league_names})!=24:
            raise ValueError("Incomplete or colliding real 2014/15 Conference club pool")
        if set(map(canonical,league_names))&set(map(canonical,(x[2] for x in staged))):
            raise ValueError("Historical League Two and Conference clubs overlap")
        if league_meta.get("source_url")!="https://fchd.info/lghist/conf2015.htm":
            raise ValueError("Uncorroborated historical Conference league source")
        db.execute("INSERT INTO pilot_fifa15_provenance VALUES(2015,?,?,?,0)",
           (identities["source_league_url"],identities["source_status"],"2014-15"))
        db.executemany("INSERT INTO pilot_fifa15_playable_club_placements VALUES(?,?,?,?,?,?,?,?,?,?)",staged)
        db.executemany("INSERT INTO pilot_fifa15_conference_external_feeders VALUES(?,?,?,?,?)",
           [(EDITION,"2015:en.5",name,league_meta["source_url"],league_meta["source_status"])
            for name in league_names])
        movement=[row for row in source_rules(2015) if row["lower"].startswith("ENG:")]
        if len(movement)!=4:raise ValueError("FIFA15 England season-end movement rules missing")
        l2=tuple(x[2] for x in staged if x[1]=="2015:en.4")
        simulate=rollover({"2015:en.4":l2,"2015:en.5":league_names},
             playable_floor="league_two",edition=2015,
             starting_season=2014,relegated_from_playable=l2[:2])
        if len(simulate["promoted_into_playable"])!=2 or simulate["simulated_feeders"]!=["2015:en.5"]:
            raise ValueError("One-level historical fixture-membership simulation failed")
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok" or db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("New read-only FIFA15 English source staging database invalid")
        if db.execute("SELECT COUNT(*) FROM edition_readiness WHERE career_ready=1").fetchone()[0]:
            raise ValueError("Cannot accidentally enable an incomplete playable PES career")
        db.commit()
    with (out/"FIFA15_ENGLISH_92_SOURCE_IDENTITIES.csv").open(
        "w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f);w.writerow(("Edition","League_Code","Source_Club",
           "Game_Club_Key","Game_Display_Name","Source_Game_Team_ID","Fixture_URL",
           "Original_FIFA15_Team_Page","Source_Import_Status","Gameplay_Squad_Status"))
        w.writerows(staged)
    summary={
        "version":VERSION,"original_game_edition":EDITION,
        "game_source_season":"2014-15",
        "original_catalogue_game_clubs_unchanged":596,
        "verified_real_game_club_identities_in_english_tiers_1_to_4":92,
        "original_imported_english_club_identities":91,
        "missing_original_game_team_recovered_from_external_game_source":1,
        "additional_original_game_club":"York City",
        "source_game_team_id":1948,
        "external_original_game_roster_players_requiring_source_restore":28,
        "shrewsbury_game_name_crosswalk_team_id":127,
        "source_english_professional_club_counts":dict(year_counts),
        "real_2014_15_nonplayable_conference_club_pool":24,
        "valid_one_level_league_two_conference_promotion_boundary":True,
        "simulated_year_is_not_real_historical_promotion":True,
        "all_92_gameplay_rosters_certified":False,
        "career_ready":False,
        "existing_career_saves_modified":False,
        "original_source_players_modified":False}
    (out/"FIFA15_92_CLUB_HISTORICAL_PILOT_SOURCE_RESTORATION_AUDIT.json").write_text(
        json.dumps(summary,indent=2),encoding="utf-8")
    return summary

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--registry",required=True)
    p.add_argument("--original-game-evidence",required=True)
    p.add_argument("--conference",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    print(json.dumps(build(a.registry,a.original_game_evidence,a.conference,a.output),indent=2))

"""Standalone sourced FIFA15 England career pilot dataset (NOT a career save).

92 original FIFA15 game clubs; real 2014/15 dated English professional
memberships; 24 real 2014/15 Conference one-hop feeder clubs.
Each playable game club gets SOURCE-PRESENT original FIFA player records and
25+4 completed *estimated* PES20 attributes. No synthetic source players,
no native game option file, no changes to production career database.
"""
from __future__ import annotations
import argparse,csv,json,sqlite3
from collections import Counter
from pathlib import Path
from world_fifa_pes_converter_v2 import TARGETS
from scripts.export_fifa_pes_v2 import EXTRAS

VERSION="fifa15-england-92-real-club-2586-player-test-dataset-v1"
YORK="external_original_fifa_team:2015:1948"
SCHEMA="""
PRAGMA foreign_keys=ON;
CREATE TABLE edition_metadata(
 edition INTEGER PRIMARY KEY CHECK(edition=2015),
 source_season TEXT NOT NULL, game TEXT NOT NULL,
 career_ready INTEGER NOT NULL CHECK(career_ready=0),
 source_rosters_fully_verified INTEGER NOT NULL CHECK(source_rosters_fully_verified=0),
 native_option_file_available INTEGER NOT NULL CHECK(native_option_file_available=0));
CREATE TABLE competitions(
 competition_code TEXT PRIMARY KEY,competition_name TEXT NOT NULL,
 tier INTEGER NOT NULL,playable INTEGER NOT NULL,
 original_edition INTEGER NOT NULL CHECK(original_edition=2015));
CREATE TABLE source_real_game_clubs(
 game_club_key TEXT PRIMARY KEY,original_game_team_id INTEGER,
 name TEXT NOT NULL,original_fifa_display_name TEXT NOT NULL,
 competition_code TEXT NOT NULL REFERENCES competitions(competition_code),
 identity_evidence TEXT NOT NULL,
 original_roster_status TEXT NOT NULL);
CREATE TABLE real_game_source_players(
 original_game_player_key TEXT PRIMARY KEY,
 game_club_key TEXT NOT NULL REFERENCES source_real_game_clubs(game_club_key),
 original_player_id TEXT NOT NULL,
 player_name TEXT NOT NULL,
 primary_position TEXT NOT NULL,
 source_edition INTEGER NOT NULL CHECK(source_edition=2015),
 source_provider TEXT NOT NULL,
 source_update TEXT,
 pes_core_25_estimates_json TEXT NOT NULL CHECK(json_valid(pes_core_25_estimates_json)),
 pes_additional_4_estimates_json TEXT NOT NULL CHECK(json_valid(pes_additional_4_estimates_json)),
 provenance TEXT NOT NULL);
CREATE TABLE external_nonplayable_feeder_clubs(
 competition_code TEXT NOT NULL REFERENCES competitions(competition_code),
 club_name TEXT NOT NULL,source_url TEXT NOT NULL,
 PRIMARY KEY(competition_code,club_name));
CREATE VIEW real_club_roster_counts AS
 SELECT club.game_club_key,club.name,club.competition_code,
        COUNT(player.original_game_player_key) AS source_players_with_numeric_PES_estimates
 FROM source_real_game_clubs club
 LEFT JOIN real_game_source_players player ON player.game_club_key=club.game_club_key
 GROUP BY club.game_club_key;
"""


def number(value):
    try:
        i=int(float(value))
        if 1<=i<=200 and float(value)==i:
            return i
    except (TypeError,ValueError):pass
    raise ValueError("Game player ability is not an integer source-backed estimate")


def build(squads_db,staging_db,york_estimates,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    target=out/"FIFA15_ENGLISH_92_ORIGINAL_CLUB_AND_PLAYER_GAMEPLAY_TEST.sqlite"
    if target.exists():raise FileExistsError("Never overwrite a previously verified source game dataset")
    with sqlite3.connect(f"file:{Path(staging_db).resolve()}?mode=ro",uri=True) as db:
        clubs=db.execute("""SELECT game_club_key,verified_game_team_id,
            source_fixture_club,game_display_name,competition_code,
            original_import_status,gameplay_player_roster_status
            FROM pilot_fifa15_playable_club_placements
            ORDER BY competition_code,source_fixture_club""").fetchall()
        feeders=db.execute("""SELECT competition_code,club_name,source_url
           FROM pilot_fifa15_conference_external_feeders ORDER BY club_name""").fetchall()
    if len(clubs)!=92 or len(feeders)!=24:
        raise ValueError("Missing actual source FIFA15 English playable club/Conference memberships")
    names={club[0] for club in clubs}
    if len(names)!=92 or sum(club[0]==YORK for club in clubs)!=1:
        raise ValueError("Original FIFA15 club identity collision or missing York City")
    with sqlite3.connect(f"file:{Path(squads_db).resolve()}?mode=ro",uri=True) as db:
        players=db.execute("""SELECT player_key,club_key,source_player_id,
                player_name,primary_position,source_provider,
                pes_abilities_json,pes_additional_json,edition
             FROM players WHERE edition=2015 AND club_key IS NOT NULL
             ORDER BY player_key""").fetchall()
    with open(york_estimates,encoding="utf-8-sig",newline="") as f:
        york=list(csv.DictReader(f))
    if len(york)!=20:raise ValueError("Only 20 authentic source York City players have been recovered")
    cols=set(york[0])
    expected=set(TARGETS)|set(EXTRAS)|{"source_player_id","player_name",
        "source_edition","source_club","primary_position","source_provider"}
    if not expected.issubset(cols):
        raise ValueError("York source-based FIFA/PES converter did not restore 25+4 ratings")
    game_plays=[]
    for key,club,id,player_name,position,provider,ratings,more,edition in players:
        if club not in names:continue
        abilities=json.loads(ratings);additional=json.loads(more)
        if set(abilities)!=set(TARGETS) or set(additional)!=set(EXTRAS):
            raise ValueError("Original FIFA15 source player lacks 25+4 PES estimates")
        for value in list(abilities.values())+list(additional.values()):
            number(value)
        game_plays.append((key,club,str(id),player_name,position,2015,
            provider,None,json.dumps(abilities,sort_keys=True),
            json.dumps(additional,sort_keys=True),"unaltered_original_FIFA15_PES20_V2_converted_squad"))
    if len(game_plays)!=2566:
        raise ValueError(f"91 original imported FIFA15 club rosters are inconsistent: {len(game_plays)}")
    for row in york:
        if row["source_edition"]!="2015" or row["source_club"]!="York City":
            raise ValueError("York player source changed game edition or club")
        abilities={key:number(row[key]) for key in TARGETS}
        additional={key:number(row[key]) for key in EXTRAS}
        game_plays.append((f"2015:pinned_FIFA15_York_City_EA1948:{row['source_player_id']}",
             YORK,str(row["source_player_id"]),row["player_name"],row["primary_position"],
             2015,row["source_provider"],"2",
             json.dumps(abilities,sort_keys=True),
             json.dumps(additional,sort_keys=True),"restored_actual_York_game_player_PES20_V2_estimate"))
    with sqlite3.connect(target) as db:
        db.executescript(SCHEMA)
        db.execute("INSERT INTO edition_metadata VALUES(2015,'2014-15','FIFA 15',0,0,0)")
        competition=[
           ("2015:en.1","Premier League",1,1,2015),
           ("2015:en.2","Championship",2,1,2015),
           ("2015:en.3","League One",3,1,2015),
           ("2015:en.4","League Two",4,1,2015),
           ("2015:en.5","Conference Premier",5,0,2015)]
        db.executemany("INSERT INTO competitions VALUES(?,?,?,?,?)",competition)
        db.executemany("INSERT INTO source_real_game_clubs VALUES(?,?,?,?,?,?,?)",
          [(key,ea,name,game,code,status,roster)
           for key,ea,name,game,code,status,roster in clubs])
        db.executemany("INSERT INTO external_nonplayable_feeder_clubs VALUES(?,?,?)",feeders)
        db.executemany("INSERT INTO real_game_source_players VALUES(?,?,?,?,?,?,?,?,?,?,?)",game_plays)
        counts=db.execute("""SELECT game_club_key,name,competition_code,source_players_with_numeric_PES_estimates
                             FROM real_club_roster_counts ORDER BY competition_code,name""").fetchall()
        missing=[name for key,name,code,n in counts if n==0]
        if missing:raise ValueError(f"Invalid original FIFA15 club with zero sourced playable players: {missing}")
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok" or db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Stand-alone historical PES career test dataset contains invalid references")
        db.commit()
    with (out/"FIFA15_ENGLISH_PLAYABLE_CLUB_SQUAD_INVENTORY.csv").open(
            "w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f);w.writerow(("Game_Club_Key","Club","League","Sourced_Players"));w.writerows(counts)
    totals=Counter(x[2] for x in counts)
    stats=dict(version=VERSION,
        original_fifa_edition=2015,original_game_season="2014-15",
        real_historical_english_professional_clubs=len(clubs),
        playable_clubs_with_at_least_one_real_source_player=len(counts),
        source_original_professional_players=len(game_plays)-len(york),
        restored_original_fifa15_york_players=len(york),
        all_92_club_source_players=len(game_plays),
        complete_estimated_pes_core_rating_values=len(game_plays)*25,
        complete_estimated_pes_auxiliary_rating_values=len(game_plays)*4,
        nonplayable_real_conference_clubs=len(feeders),
        additional_nonplayable_lower_tiers_used=0,
        per_division_real_game_club_counts=dict(totals),
        york_other_snapshot_missing_source_players_not_invented=8,
        source_snapshots_not_proven_opening_day=True,
        game_export_native_option_file_created=False,
        all_92_club_original_game_rosters_fully_certified=False,
        existing_22_edition_database_unmodified=True,
        production_careers_unmodified=True,
        career_ready=False)
    (out/"FIFA15_92_CLUB_OFFLINE_PES_SOURCE_PILOT_AUDIT.json").write_text(
           json.dumps(stats,indent=2),encoding="utf-8")
    return stats

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--squads",required=True)
    p.add_argument("--club-staging",required=True)
    p.add_argument("--york-estimates",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    print(json.dumps(build(args.squads,args.club_staging,args.york_estimates,args.output),indent=2))

"""Attach real FIFA15 York City source players to 92-club English career pilot.

Non-destructive copy of historical source staging SQLite. FIFA15 York City is
not in the original imported player catalogue. It is present in a pinned SoFIFA
FIFA15 update-2 snapshot with 20 original source players and attributes.
The original FIFA Index team page lists 28 from a different update; do not
invent absent records. Players are NOT transformed to estimated PES abilities.
"""
from __future__ import annotations
import argparse,csv,json,sqlite3,hashlib
from pathlib import Path

VERSION="fifa15-york-actual-player-overlay-92-club-pilot-v1"
YORK_KEY="external_original_fifa_team:2015:1948"
TEAM_ID=1948
SRC_PIN="13389f463935d257e92811eebbd50405df1a982aa45233a63d1ce075daca133e"
SQL="""
CREATE TABLE pilot_fifa15_original_game_roster_counts(
 edition INTEGER NOT NULL CHECK(edition=2015),
 game_club_key TEXT NOT NULL,
 original_player_count INTEGER NOT NULL CHECK(original_player_count>=0),
 PRIMARY KEY(edition,game_club_key));
CREATE TABLE pilot_fifa15_real_york_source_players(
 edition INTEGER NOT NULL CHECK(edition=2015),
 team_id INTEGER NOT NULL CHECK(team_id=1948),
 game_player_id INTEGER NOT NULL,
 player_name TEXT NOT NULL,
 original_position TEXT NOT NULL,
 source_overall INTEGER NOT NULL CHECK(source_overall BETWEEN 20 AND 100),
 original_attribute_json TEXT NOT NULL CHECK(json_valid(original_attribute_json)),
 source_sha256 TEXT NOT NULL,
 source_update TEXT NOT NULL,
 PRIMARY KEY(edition,game_player_id));
CREATE VIEW pilot_fifa15_playable_roster_inventory AS
SELECT s.edition,s.competition_code,s.source_fixture_club,
 s.game_club_key,s.verified_game_team_id,
 COALESCE((SELECT m.original_player_count
        FROM pilot_fifa15_original_game_roster_counts m
        WHERE m.edition=s.edition AND m.game_club_key=s.game_club_key),0)
        AS imported_original_squad_players,
 (SELECT COUNT(*) FROM pilot_fifa15_real_york_source_players y
        WHERE s.game_club_key='external_original_fifa_team:2015:1948'
        AND y.edition=s.edition AND y.team_id=1948) AS restored_york_source_players,
 s.gameplay_player_roster_status
 FROM pilot_fifa15_playable_club_placements s;
"""

def build(source_db,york_csv,source_audit,output,squads_sqlite):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    target=out/"FIFA15_ENGLAND_92_REAL_SOURCE_SQUAD_PILOT.sqlite"
    if target.exists():raise FileExistsError("Don't overwrite a historical staging release")
    source_meta=json.loads(Path(source_audit).read_text(encoding="utf-8"))
    if (source_meta.get("source_pin") not in (None,SRC_PIN)
            or source_meta.get("original_source_sha256")!=SRC_PIN
            or source_meta.get("fifa_version")!=15
            or source_meta.get("original_game_team_id")!=TEAM_ID
            or source_meta.get("club")!="York City"
            or source_meta.get("source_snapshot_not_assumed_opening_day") is not True):
        raise ValueError("York FIFA15 historical source edition/game data not verified")
    with open(york_csv,encoding="utf-8-sig",newline="") as f:
        inp=csv.DictReader(f)
        fields=inp.fieldnames or []
        required={"fifa_version","player_id","club_team_id","club_name","short_name",
           "overall","player_positions","fifa_update"}
        if not required.issubset(fields):
            raise ValueError("Original York player source fields incomplete")
        rows=list(inp)
    if len(rows)!=int(source_meta["original_players_recovered"]):
        raise ValueError("York City source player row count changed")
    if not 18<=len(rows)<=40:raise ValueError("Real source full team player limit")
    original=[]
    for x in rows:
        if (str(x["fifa_version"]).strip()!="15"
              or int(float(x["club_team_id"]))!=TEAM_ID
              or x["club_name"]!="York City"
              or not x["short_name"].strip()):
            raise ValueError("FIFA15 York City real game player origin mismatch")
        pid=int(float(x["player_id"]))
        overall=int(float(x["overall"]))
        original.append((2015,TEAM_ID,pid,x["short_name"].strip(),
            x["player_positions"].strip(),overall,
            json.dumps(x,ensure_ascii=False,sort_keys=True),SRC_PIN,
            str(x.get("fifa_update") or "unknown")))
    if len({x[2] for x in original})!=len(original):
        raise ValueError("Same-edition actual original York player ID collision")
    with sqlite3.connect(f"file:{Path(source_db).resolve()}?mode=ro",uri=True) as source,\
         sqlite3.connect(target) as dst:
        source.backup(dst)
    with sqlite3.connect(f"file:{Path(squads_sqlite).resolve()}?mode=ro",uri=True) as source_squads:
        original_clubs={str(key):str(name) for key,name in source_squads.execute(
            "SELECT club_key,name FROM clubs WHERE edition=2015")}
        source_counts={str(key):int(count) for key,count in source_squads.execute("""
            SELECT club_key,COUNT(*) FROM players WHERE edition=2015
            AND club_key IS NOT NULL AND assignment='at_club' GROUP BY club_key""")}
        if len(original_clubs)!=596:
            raise ValueError("Original immutable FIFA15 imported player/squad catalogue changed")
    with sqlite3.connect(target) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(SQL)
        db.executemany("INSERT INTO pilot_fifa15_original_game_roster_counts VALUES(?,?,?)",
           [(2015,key,source_counts.get(key,0)) for key in sorted(original_clubs)])
        york=db.execute("""SELECT source_fixture_club,verified_game_team_id,game_club_key
              FROM pilot_fifa15_playable_club_placements
              WHERE edition=2015 AND game_club_key=?""",(YORK_KEY,)).fetchall()
        if york!=[("York City",1948,YORK_KEY)]:
            raise ValueError("Source restoration not linked to approved original FIFA15 York team")
        for name,key,game_name in db.execute(
            "SELECT source_fixture_club,game_club_key,game_display_name FROM pilot_fifa15_playable_club_placements"):
            if key!=YORK_KEY and original_clubs.get(key)!=game_name:
                raise ValueError("Original FIFA15 playable roster club identity mismatch")
        db.executemany("""INSERT INTO pilot_fifa15_real_york_source_players
           VALUES(?,?,?,?,?,?,?,?,?)""",original)
        inventory=db.execute("""SELECT source_fixture_club,
               imported_original_squad_players,restored_york_source_players
               FROM pilot_fifa15_playable_roster_inventory
               ORDER BY competition_code,source_fixture_club""").fetchall()
        missing=[(name,im,restored) for name,im,restored in inventory
                 if im+restored==0]
        if len(inventory)!=92:
            raise ValueError("FIFA15 English staged club identity coverage altered")
        if len(original)!=20:
            # Preserve rather than imply update-2 reconstructed all other
            # FIFA15 launch York players: our pinned archival source has 20.
            raise ValueError("Pinned historical source FIFA15 York snapshot differs")
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok" or db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Original squad overlay SQLite corruption")
        if db.execute("SELECT COUNT(*) FROM edition_readiness WHERE career_ready!=0").fetchone()[0]:
            raise ValueError("Original historical career gating accidentally enabled")
        db.commit()
    with (out/"FIFA15_ENGLISH_CLUB_ROSTER_COUNTS.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.writer(f)
        writer.writerow(("Club","Imported_FIFA15_Squad_Players","Restored_York_Source_Players"))
        writer.writerows(inventory)
    result=dict(version=VERSION,game_edition=2015,original_season="2014-15",
       authentic_english_game_club_placements=len(inventory),
       existing_original_club_catalogue_modified=False,
       actual_untouched_original_game_players_for_91_teams=sum(x[1] for x in inventory),
       source_restored_york_city_players=len(original),
       source_roster_update="2",
       original_york_fifaindex_team_list_count_other_snapshot=28,
       incomplete_relative_to_other_snapshot=True,
       playable_clubs_without_any_original_or_restored_players=len(missing),
       names_missing_gameplay_squad=[x[0] for x in missing],
       game_edition_source_pin=SRC_PIN,
       all_92_gameplay_rosters_certified=False,
       estimated_PES_player_attributes_not_yet_generated=True,
       career_ready=False,production_careers_untouched=True)
    (out/"FIFA15_ENGLISH_REAL_SOURCE_SQUAD_PILOT_AUDIT.json").write_text(
         json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--registry",required=True)
    a.add_argument("--york",required=True)
    a.add_argument("--source-audit",required=True)
    a.add_argument("--squads",required=True)
    a.add_argument("--output",required=True)
    x=a.parse_args()
    print(json.dumps(build(x.registry,x.york,x.source_audit,x.output,x.squads),indent=2))

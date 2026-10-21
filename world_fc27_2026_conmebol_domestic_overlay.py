"""Final FC27 edition-only SOURCE alignment for 40 original CONMEBOL clubs.

Use original FC27 imported cup club name + exact reviewed official 2026
CONMEBOL national association + dated real 2026 first-division participation
source. Never mistake Copa Libertadores/Sudamericana for domestic leagues,
and never claim a complete independently verified whole-season club universe,
EA club ID or ready career. All 21 previous editions untouched.
"""
from __future__ import annotations
import argparse,csv,json,sqlite3
from collections import Counter,defaultdict
from pathlib import Path
VERSION="fc27-one-year-all-670-domestic-competition-source-associations-v1"
EDITION=2027
SCHEMA="""
CREATE TABLE fc27_conmebol_2026_domestic_league_sources(
    edition INTEGER NOT NULL CHECK(edition=2027),
    league_code TEXT NOT NULL,
    country TEXT NOT NULL,competition TEXT NOT NULL,
    source_year INTEGER NOT NULL CHECK(source_year=2026),
    official_2026_domestic_source_url TEXT NOT NULL,
    national_competition_tier INTEGER NOT NULL CHECK(national_competition_tier=1),
    original_game_id_verified INTEGER NOT NULL CHECK(original_game_id_verified=0),
    complete_league_fixture_roster_verified INTEGER NOT NULL CHECK(complete_league_fixture_roster_verified=0),
    PRIMARY KEY(edition,league_code));
CREATE TABLE fc27_conmebol_original_club_domestic_candidates(
    edition INTEGER NOT NULL CHECK(edition=2027),
    club_key TEXT NOT NULL,
    original_source_name TEXT NOT NULL,
    continental_source_group TEXT NOT NULL,
    verified_national_association TEXT NOT NULL,
    source_domestic_competition TEXT NOT NULL,
    reviewed_2026_official_cup_name TEXT NOT NULL,
    official_cup_source_url TEXT NOT NULL,
    national_2026_league_source_url TEXT NOT NULL,
    evidence_status TEXT NOT NULL
      CHECK(evidence_status='official_country_plus_2026_domestic_division_candidate_membership_pending'),
    PRIMARY KEY(edition,club_key),
    FOREIGN KEY(edition,club_key)
       REFERENCES edition_club_competitions(edition,club_key),
    FOREIGN KEY(edition,source_domestic_competition)
       REFERENCES fc27_conmebol_2026_domestic_league_sources(edition,league_code));
CREATE VIEW fc27_2026_27_complete_source_competition_alignment AS
 SELECT o.edition,o.club_key,o.club,
        COALESCE(o.starting_competition,c.source_domestic_competition) AS starting_competition,
        CASE WHEN o.starting_competition IS NOT NULL THEN o.evidence_origin
             WHEN c.source_domestic_competition IS NOT NULL THEN
               'reviewed_2026_official_cup_country_and_independent_domestic_first_tier'
             ELSE 'unresolved' END AS evidence_origin,
        CASE WHEN o.starting_competition IS NOT NULL THEN o.registration_scope
             WHEN c.source_domestic_competition IS NOT NULL THEN
               'country_backed_home_division_candidate_no_individual_roster_certificate'
             ELSE 'home_league_missing' END AS verification_scope
 FROM fc27_one_year_club_competition_alignment o
 LEFT JOIN fc27_conmebol_original_club_domestic_candidates c
   ON o.edition=c.edition AND o.club_key=c.club_key;
"""
def export(path,head,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        wr=csv.writer(f);wr.writerow(head);wr.writerows(rows)

def build(registry,country_review_path,domestic_review_path,output,strict=True):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    official=json.loads(Path(country_review_path).read_text(encoding="utf-8"))
    domestic=json.loads(Path(domestic_review_path).read_text(encoding="utf-8"))
    if (official.get("version")!="fc27-conmebol-official-2026-team-country-reviewed-v1"
        or domestic.get("version")!="fc27-2026-conmebol-domestic-participation-review-v1"
        or official.get("edition")!=2027 or domestic.get("edition")!=2027
        or official.get("actual_competition_year")!=2026
        or domestic.get("real_world_season")!="calendar_2026"):
        raise ValueError("Must use original verified 2026 calendar-year national league sources")
    entries=official["entries"]
    reviewed={(e["source_group"],e["source_club"]):e for e in entries}
    if len(entries)!=40 or len(reviewed)!=40:
        raise ValueError("Must independently identify exactly 40 game-source CONMEBOL club countries")
    leagues=domestic["countries"]
    if len(leagues)!=9:
        raise ValueError("Expected exactly nine source domestic league associations for 2026")
    dbfile=out/"FC27_2026_27_ALL_670_SOURCE_CLUB_HOME_COMPETITIONS.sqlite"
    if dbfile.exists():raise FileExistsError("Do not overwrite prior source-country review database")
    with sqlite3.connect(f"file:{Path(registry).resolve()}?mode=ro",uri=True) as source,\
         sqlite3.connect(dbfile) as dest:
        source.backup(dest)
    with sqlite3.connect(dbfile) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(SCHEMA)
        known_codes={code:(country,int(tier)) for code,country,tier in
           db.execute("SELECT code,country,tier FROM competition_seasons WHERE edition=2027")}
        for country,data in leagues.items():
            code="2027:"+data["code"]
            if code in known_codes and known_codes[code]!=(country,1):
                raise ValueError(f"Official domestic affiliation contradicts existing 2027 source {code}")
            if (not data["source"].startswith("https://") or
                not data["competition"] or not data["code"].endswith(".1")):
                raise ValueError("Dated 2026 national first-division source absent")
            db.execute("INSERT INTO fc27_conmebol_2026_domestic_league_sources VALUES (?,?,?,?,?,?,?,?,?)",
              (2027,code,country,data["competition"],2026,data["source"],1,0,0))
        originals=db.execute("""SELECT c.club_key,c.club,c.original_source_league,p.starting_competition
           FROM edition_club_competitions c
           JOIN fc27_one_year_club_competition_alignment p
             ON p.edition=c.edition AND p.club_key=c.club_key
           WHERE c.edition=2027 ORDER BY c.club_key""").fetchall()
        cup_candidates=[(key,name,group) for key,name,group,code in originals if code is None]
        if len(cup_candidates)!=40 or {
            group for key,name,group in cup_candidates
           }!={"CONMEBOL Libertadores","CONMEBOL Sudamericana"}:
            raise ValueError("Only true continental source group members may get another domestic home league")
        if set(reviewed)!={(group,name) for key,name,group in cup_candidates}:
            raise ValueError("2026 official country evidence does not cover every original exact FC27 cup club")
        rows=[]
        for key,name,group in cup_candidates:
            reviewed_club=reviewed[(group,name)]
            country=reviewed_club["country"]
            info=leagues.get(country)
            if info is None:raise ValueError("National 2026 domestic source not verified")
            if not reviewed_club["official_club"] or not official["group_sources"].get(group,"").startswith("https://"):
                raise ValueError("Official 2026 club name or primary source unavailable")
            rows.append((2027,key,name,group,country,"2027:"+info["code"],
                 reviewed_club["official_club"],official["group_sources"][group],
                 info["source"],"official_country_plus_2026_domestic_division_candidate_membership_pending"))
        db.executemany("INSERT INTO fc27_conmebol_original_club_domestic_candidates VALUES (?,?,?,?,?,?,?,?,?,?)",rows)
        before=db.execute("""SELECT COUNT(*) FROM fc27_one_year_club_competition_alignment
                      WHERE starting_competition IS NOT NULL""").fetchone()[0]
        after=db.execute("""SELECT COUNT(*) FROM fc27_2026_27_complete_source_competition_alignment
                      WHERE starting_competition IS NOT NULL""").fetchone()[0]
        total=db.execute("SELECT COUNT(*) FROM fc27_2026_27_complete_source_competition_alignment").fetchone()[0]
        if strict and (before!=630 or after!=670 or total!=670 or len(rows)!=40):
            raise ValueError("Original FC27 home league grouping coverage changed")
        if after!=before+len(rows) or total!=after:
            raise ValueError("Not all original FC27 source records have a domestic competition")
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok" or db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Unsafe game-source/real-club league join")
        if db.execute("SELECT COUNT(*) FROM edition_readiness WHERE career_ready!=0").fetchone()[0]:
            raise ValueError("External 2026 source cannot unlock unverified historical careers")
        total_22=db.execute("SELECT COUNT(*) FROM edition_club_competitions").fetchone()[0]
        if strict and total_22!=13104:raise ValueError("Other original edition records altered")
        db.commit()
    export(out/"FC27_CONMEBOL_REVIEWED_2026_HOME_DOMESTIC_LEAGUES.csv",
      ("Edition","Club_Key","Original_FC27_Club","Original_Continental_Source_Group",
       "Official_Country","2026_Domestic_Competition_Code","Official_Cup_Club_Name",
       "Official_2026_Cup_Source","Independent_2026_Domestic_Club_Source","Evidence_Status"),rows)
    report={"version":VERSION,"edition":2027,
       "fc27_source_club_records":total,"previously_domestic_source_groups":before,
       "new_2026_country_backed_domestic_league_candidates":len(rows),
       "total_staged_domestic_source_competition_associations":after,
       "national_2026_first_division_evidence_sources":len(leagues),
       "source_club_identity_EA_ids_not_verified":True,
       "full_real_world_league_rosters_not_verified":True,
       "season_promotion_relegation_graph_complete":False,
       "career_ready":False,"other_21_editions_unmodified":True,
       "original_player_data_unmodified":True}
    (out/"FC27_ALL_670_CLUB_DOMESTIC_SOURCE_ALIGNMENT_AUDIT.json").write_text(
       json.dumps(report,indent=2),encoding="utf-8")
    return report
if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--registry",required=True)
    a.add_argument("--countries",required=True)
    a.add_argument("--domestic",required=True)
    a.add_argument("--output",required=True)
    x=a.parse_args()
    print(json.dumps(build(x.registry,x.countries,x.domestic,x.output),indent=2))

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
from world_fc27_release_exclusions import sanitize_fc27_active_release
from world_fc27_source_membership_policy import adopt_staged_memberships
from world_fc27_additional_movement_rules import stage as stage_additional_movements
VERSION="fc27-one-year-all-659-playable-domestic-source-associations-v2"
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
    reviewed_2026_domestic_club_name TEXT NOT NULL,
    individual_2026_membership_source_url TEXT NOT NULL,
    national_2026_league_source_url TEXT NOT NULL,
    evidence_status TEXT NOT NULL
      CHECK(evidence_status='reviewed_individual_2026_domestic_membership_EA_identity_pending'),
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
               'official_2026_country_plus_named_2026_domestic_membership_review'
             ELSE 'unresolved' END AS evidence_origin,
        CASE WHEN o.starting_competition IS NOT NULL THEN o.registration_scope
             WHEN c.source_domestic_competition IS NOT NULL THEN
               'individual_2026_club_membership_review_original_EA_ID_pending'
             ELSE 'home_league_missing' END AS verification_scope
 FROM fc27_one_year_club_competition_alignment o
 LEFT JOIN fc27_conmebol_original_club_domestic_candidates c
   ON o.edition=c.edition AND o.club_key=c.club_key;
"""
def validate_individual_memberships(official_entries, domestic):
    """Require a season-dated domestic member witness for every cup-source club.

    National association alone does not prove a domestic division. This review
    does not certify original EA team IDs or an entire league's registration.
    """
    records=domestic.get("individual_club_memberships")
    if not isinstance(records,list) or len(records)!=len(official_entries):
        raise ValueError("Every cup-source club needs a separate 2026 domestic membership witness")
    bykey={(x["continental_source_group"],x["original_source_club"]):x for x in records}
    official={(x["source_group"],x["source_club"]):x for x in official_entries}
    if len(bykey)!=len(records) or set(bykey)!=set(official):
        raise ValueError("Missing, duplicated or unexpected individual 2026 domestic club review")
    for key,record in bykey.items():
        source=official[key]
        country=source["country"]
        league=domestic["countries"].get(country)
        if (league is None or record["national_association"]!=country
            or record["domestic_code"]!=league["code"]
            or record["verified_season"]!=2026
            or record["domestic_membership_source"]!=league["source"]
            or record["status"]!="2026_named_first_division_participation_review_game_identity_not_verified"
            or not str(record["domestic_2026_roster_club"]).strip()
            or not str(record["domestic_membership_source"]).startswith("https://")):
            raise ValueError(f"Unsupported 2026 individual domestic league member: {key}")
    return bykey

def export(path,head,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        wr=csv.writer(f);wr.writerow(head);wr.writerows(rows)

def build(registry,country_review_path,domestic_review_path,output,strict=True,movement_rules_path=None):
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
    individual_members=validate_individual_memberships(entries,domestic)
    if len(leagues)!=9:
        raise ValueError("Expected exactly nine source domestic league associations for 2026")
    dbfile=out/"FC27_2026_27_ALL_659_SOURCE_CLUB_HOME_COMPETITIONS.sqlite"
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
            member=individual_members[(group,name)]
            country=reviewed_club["country"]
            info=leagues.get(country)
            if info is None:raise ValueError("National 2026 domestic source not verified")
            if not reviewed_club["official_club"] or not official["group_sources"].get(group,"").startswith("https://"):
                raise ValueError("Official 2026 club name or primary source unavailable")
            rows.append((2027,key,name,group,country,"2027:"+info["code"],
                 reviewed_club["official_club"],official["group_sources"][group],
                 member["domestic_2026_roster_club"],member["domestic_membership_source"],
                 info["source"],"reviewed_individual_2026_domestic_membership_EA_identity_pending"))
        db.executemany("INSERT INTO fc27_conmebol_original_club_domestic_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",rows)
        before=db.execute("""SELECT COUNT(*) FROM fc27_one_year_club_competition_alignment
                      WHERE starting_competition IS NOT NULL""").fetchone()[0]
        after=db.execute("""SELECT COUNT(*) FROM fc27_2026_27_complete_source_competition_alignment
                      WHERE starting_competition IS NOT NULL""").fetchone()[0]
        total=db.execute("SELECT COUNT(*) FROM fc27_2026_27_complete_source_competition_alignment").fetchone()[0]
        if strict and (before!=619 or after!=659 or total!=659 or len(rows)!=40):
            raise ValueError("Original FC27 home league grouping coverage changed")
        if after!=before+len(rows) or total!=after:
            raise ValueError("Not all original FC27 source records have a domestic competition")
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok" or db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Unsafe game-source/real-club league join")
        if db.execute("SELECT COUNT(*) FROM edition_readiness WHERE career_ready!=0").fetchone()[0]:
            raise ValueError("External 2026 source cannot unlock unverified historical careers")
        total_22=db.execute("SELECT COUNT(*) FROM edition_club_competitions").fetchone()[0]
        if strict and total_22!=13104:raise ValueError("Other original edition records altered")
        # Only the new disposable release copy is cleaned. The upstream
        # 13,104-record historical source archive remains wholly unchanged.
        removed=sanitize_fc27_active_release(db,expected_exclusions=11 if strict else None)
        remaining_2027=db.execute(
            "SELECT COUNT(*) FROM edition_club_competitions WHERE edition=2027"
        ).fetchone()[0]
        if remaining_2027!=total or db.execute(
            "SELECT COUNT(*) FROM fc27_2026_27_complete_source_competition_alignment"
        ).fetchone()[0]!=total:
            raise ValueError("Active FC27 database club rows do not reconcile after removal")
        scope=adopt_staged_memberships(db,strict=strict)
        movements=(stage_additional_movements(db,movement_rules_path,strict=strict)
                   if movement_rules_path is not None else None)
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise ValueError("Final FC27 release copy has invalid SQLite integrity")
        db.commit()
    export(out/"FC27_CONMEBOL_REVIEWED_2026_HOME_DOMESTIC_LEAGUES.csv",
      ("Edition","Club_Key","Original_FC27_Club","Original_Continental_Source_Group",
       "Official_Country","2026_Domestic_Competition_Code","Official_Cup_Club_Name",
       "Official_2026_Cup_Source","Reviewed_2026_Domestic_Club",
       "Individual_2026_Domestic_Source","Country_Division_Source","Evidence_Status"),rows)
    report={"version":VERSION,"edition":2027,
       "fc27_active_club_records":total,
       "excluded_original_source_clubs":removed,
       "excluded_clubs_remaining_in_derived_SQLite":0,
       "derived_SQLite_club_season_rows":total_22-removed,
       "archived_unchanged_FC27_club_records":670,"previously_domestic_source_groups":before,
       "new_2026_country_backed_domestic_league_candidates":len(rows),
       "individually_reviewed_2026_domestic_club_memberships":len(individual_members),
       "total_staged_domestic_source_competition_associations":after,
       "national_2026_first_division_evidence_sources":len(leagues),
       "source_club_identity_EA_ids_not_verified":True,
       "full_real_world_league_rosters_not_verified":True,
       "individual_member_name_matches_not_EA_team_id_proof":True,
       "season_promotion_relegation_graph_complete":False,
       "career_ready":False,"other_21_editions_unmodified":True,
       "user_approved_source_membership_scope":scope,
       "additional_2027_movement_rules_staged":movements,
       "original_player_data_unmodified":True}
    (out/"FC27_ALL_659_CLUB_DOMESTIC_SOURCE_ALIGNMENT_AUDIT.json").write_text(
       json.dumps(report,indent=2),encoding="utf-8")
    return report
if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--registry",required=True)
    a.add_argument("--countries",required=True)
    a.add_argument("--domestic",required=True)
    a.add_argument("--movement-rules")
    a.add_argument("--output",required=True)
    x=a.parse_args()
    print(json.dumps(build(x.registry,x.countries,x.domestic,x.output,movement_rules_path=x.movement_rules),indent=2))

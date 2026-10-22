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
from world_fc27_movement_gameplay_policy import apply_gameplay_decisions
from world_fc27_remaining_movement_game_policy import stage_game_defaults
from world_fc27_broader_closed_league_scope import close_peripheral_leagues
from world_fc27_career_world_playability import stage as stage_career_world
from world_fc27_mls_playable_scope import stage_mls
from world_fc27_nl_pt_feeder_review import stage as stage_nl_pt_feeders
from world_fc27_regional_feeder_rosters import stage as stage_regional_feeders
from world_fc27_effective_season_end_routes import stage as stage_effective_movement_routes
from world_fc27_eight_country_playable_scope import apply_eight_country_scope
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

def build(registry,country_review_path,domestic_review_path,output,strict=True,movement_rules_path=None,gameplay_decisions_path=None,remaining_game_rules_path=None,official_feeder_rosters_path=None,playable_scope_path=None,mls_scope_path=None,nl_pt_feeders_path=None,regional_feeders_path=None):
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
        if gameplay_decisions_path is not None and movements is None:
            raise ValueError("FC27 gameplay simplifications require staged source movement rules")
        gameplay_policy=(apply_gameplay_decisions(db,gameplay_decisions_path,strict=strict)
                         if gameplay_decisions_path is not None else None)
        if remaining_game_rules_path is not None and (movements is None or gameplay_policy is None):
            raise ValueError("Remaining game movement rules require source and approved overrides")
        remaining_game_policy=(stage_game_defaults(db,remaining_game_rules_path,strict=strict)
                               if remaining_game_rules_path is not None else None)
        prior_game_scope=(close_peripheral_leagues(db,strict=strict)
                          if remaining_game_rules_path is not None else None)
        if playable_scope_path is not None and prior_game_scope is None:
            raise ValueError("Six-country playable choice requires prior source/game competition policies")
        final_game_scope=(apply_eight_country_scope(db,playable_scope_path,strict=strict)
                          if playable_scope_path is not None else prior_game_scope)
        if official_feeder_rosters_path is not None and final_game_scope is None:
            raise ValueError("Sourced feeder clubs require completed effective FC27 game competition scope")
        if mls_scope_path is not None and playable_scope_path is None:
            raise ValueError("MLS requires valid eight-country playable scope first")
        mls_playable=(stage_mls(db,mls_scope_path,strict=strict)
                      if mls_scope_path is not None else None)
        if official_feeder_rosters_path is not None and mls_playable is None:
            raise ValueError("Career roles require the complete MLS and European selectable scope")
        career_world=(stage_career_world(db,official_feeder_rosters_path,strict=strict)
                      if official_feeder_rosters_path is not None else None)
        if nl_pt_feeders_path is not None and career_world is None:
            raise ValueError("Dutch Portuguese club lists require earlier three source lists")
        nl_pt_real_feeders=(stage_nl_pt_feeders(db,nl_pt_feeders_path,strict=strict)
                            if nl_pt_feeders_path is not None else None)
        if regional_feeders_path is not None and nl_pt_real_feeders is None:
            raise ValueError("Regional one-hop sources require completed existing feeder pool mapping")
        regional_one_hop=(stage_regional_feeders(db,regional_feeders_path,strict=strict)
                          if regional_feeders_path is not None else None)
        effective_route_index=(stage_effective_movement_routes(db,strict=strict)
                               if regional_one_hop is not None else None)
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise ValueError("Final FC27 release copy has invalid SQLite integrity")
        db.commit()
    if career_world is not None:
        with sqlite3.connect(dbfile) as release_db:
            feeder_csv=release_db.execute("""
               SELECT edition,feeder_code,real_club_name,regional_group,
                      reserve_or_youth,source_url,
                      PES_player_squad_imported,game_promotion_registered
               FROM fc27_sourced_real_one_hop_feeder_clubs
               ORDER BY feeder_code,regional_group,real_club_name
            """).fetchall()
            world_csv=release_db.execute("""
               SELECT edition,club_key,original_club,competition_code,
                      competition_mode,manager_job_market_candidate,
                      playable_in_PES_verified
               FROM fc27_career_world_clubs ORDER BY competition_code,original_club
            """).fetchall()
        export(out/"FC27_2026_27_OFFICIAL_REAL_FEEDER_CLUB_NAMES.csv",
          ("Edition","Feeder_Code","Real_Club_Name","Group","Reserve_Youth",
           "Official_2026_27_Member_Source","PES_Squad_Imported",
           "Game_Promotion_Registered"),feeder_csv)
        export(out/"FC27_2026_27_CAREER_WORLD_CLUB_ROLES.csv",
          ("Edition","Original_Source_Club_Key","Club","Domestic_Competition",
           "Season_World_Mode","Manager_Job_Market_Candidate",
           "PES_Player_Squad_Ready"),world_csv)
    if regional_one_hop is not None:
        with sqlite3.connect(dbfile) as regional_db:
            regional_rows=regional_db.execute("""
               SELECT c.edition,c.code,c.regional_group,c.real_club_name,
                      c.reserve_or_youth,g.source_url,
                      c.same_name_in_original_FC27_source,
                      c.PES_player_squad_imported
               FROM fc27_regional_feeder_2026_27_club c
               JOIN fc27_regional_feeder_2026_27_group g ON
                 g.edition=c.edition AND g.code=c.code AND
                 g.regional_group=c.regional_group
               ORDER BY c.code,c.regional_group,c.real_club_name
            """).fetchall()
        export(out/"FC27_2026_27_SPANISH_GERMAN_REAL_REGIONAL_FEEDERS.csv",
          ("Edition","Lower_Competition","Regional_Group","Sourced_Club_Name",
           "Reserve_Youth","2026_27_Source","Matches_Original_Club_Name",
           "PES_Squad_Imported"),regional_rows)
    if effective_route_index is not None:
        with sqlite3.connect(dbfile) as route_db:
            route_rows=route_db.execute("""
               SELECT edition,upper_code,lower_code,route_type,
                      direct_promotions,lower_playoff_promotions,
                      upper_direct_relegations,upper_conditional_survival_places,
                      rule_notes,executable_career_movement
               FROM fc27_effective_playable_season_end_routes
               ORDER BY upper_code
            """).fetchall()
        export(out/"FC27_2026_27_EFFECTIVE_OPEN_PLAYABLE_SEASON_END_ROUTES.csv",
          ("Edition","Playable_Upper_Competition","Immediate_Lower_Feeder",
           "Rule_Source_Kind","Direct_Promotions",
           "Guaranteed_Lower_Playoff_Promotions","Direct_Relegations",
           "Conditional_Survival_Playoff","Gameplay_Rule_Notes",
           "Career_Movement_Currently_Executable"),route_rows)
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
       "user_approved_2027_gameplay_movement_assumptions":gameplay_policy,
       "remaining_2027_gameplay_movement_scope":remaining_game_policy,
       "final_2027_open_and_closed_gameplay_scope":final_game_scope,
       "prior_2027_game_scope_before_six_country_choice":prior_game_scope,
       "source_club_career_world_and_real_2027_feeders":career_world,
       "MLS_2026_closed_division_intended_playable":mls_playable,
       "Dutch_Portuguese_2026_27_real_feeder_name_registration":nl_pt_real_feeders,
       "Spain_Germany_2026_27_regional_feeder_registration":regional_one_hop,
       "FC27_16_open_league_effective_season_end_routes":effective_route_index,
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
    a.add_argument("--gameplay-decisions")
    a.add_argument("--remaining-game-rules")
    a.add_argument("--official-feeder-rosters")
    a.add_argument("--playable-scope")
    a.add_argument("--mls-scope")
    a.add_argument("--nl-pt-feeders")
    a.add_argument("--regional-feeders")
    a.add_argument("--output",required=True)
    x=a.parse_args()
    print(json.dumps(build(x.registry,x.countries,x.domestic,x.output,
       movement_rules_path=x.movement_rules,
       gameplay_decisions_path=x.gameplay_decisions,
       remaining_game_rules_path=x.remaining_game_rules,
       official_feeder_rosters_path=x.official_feeder_rosters,
       playable_scope_path=x.playable_scope,
       mls_scope_path=x.mls_scope,
       nl_pt_feeders_path=x.nl_pt_feeders,
       regional_feeders_path=x.regional_feeders),indent=2))

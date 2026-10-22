"""Year-one FC27 real-world roster and competition-rule verification.

Read only original FC27 source-group club identities and compare with genuine
2026/27 published team lists. A licence successor is NEVER silently assigned
to a defunct original game club. Records remain unresolved for PLAYABLE roster
certification if season teams disagree, even if source leagues are named.
"""
from __future__ import annotations
import argparse,csv,json,sqlite3
from pathlib import Path
from world_historical_competition_registry import canonical
from world_competition_exclusions import excluded_source_league

VERSION="fc27-2026-27-official-roster-conflict-audit-v1"

def compare(source_db,review,outdir):
    out=Path(outdir);out.mkdir(parents=True,exist_ok=True)
    config=json.loads(Path(review).read_text(encoding="utf-8"))
    if config.get("version")!="fc27-independent-2026-27-domestic-roster-check-v1" or config.get("edition")!=2027:
        raise ValueError("Independent official published season rosters are not for original FC27")
    if any(excluded_source_league(x['original_group']) for x in config['competitions']):
        raise ValueError('An excluded league cannot be audited as an active competition')
    with sqlite3.connect(f"file:{Path(source_db).resolve()}?mode=ro",uri=True) as db:
        old=db.execute("SELECT COUNT(*) FROM edition_club_competitions WHERE edition=2027").fetchone()[0]
        if old!=670:raise ValueError("Historical original FC27 source rows unexpectedly changed")
        game={group:[(club_key,name) for club_key,name in db.execute(
            """SELECT club_key,club FROM edition_club_competitions
               WHERE edition=? AND original_source_league=? ORDER BY club""",
            (2027,group))]
            for group in [x["original_group"] for x in config["competitions"]]}
        staged=db.execute("SELECT COUNT(*) FROM fc27_2026_27_complete_source_competition_alignment WHERE starting_competition IS NOT NULL").fetchone()[0]
        ready=db.execute("SELECT COUNT(*) FROM edition_readiness WHERE career_ready!=0").fetchone()[0]
        original_rows=db.execute("SELECT COUNT(*) FROM edition_club_competitions").fetchone()[0]
    if staged!=659 or ready or original_rows!=13104:
        raise ValueError("Official roster check cannot operate on incomplete or active career source DB")
    all_matches=[];exceptions=[];report=[]
    for item in config["competitions"]:
        group=item["original_group"];source=game[group];official=item["official_clubs"]
        if not item["official_source_url"].startswith("https://") or not source:
            raise ValueError("Unsupported official dated competition or empty original game group")
        # Normalize only the explicitly reviewed display aliases. Never
        # equate a licensed successor with its historic source identity.
        successors=set(item.get("nonidentity_successor_names",[]))
        def norm(name):
            return canonical(item.get("aliases",{}).get(name,name))
        src_keys={}
        for game_key,name in source:
            key=canonical(name) if name in successors else norm(name)
            if key in src_keys:raise ValueError("Original game source club identity duplicated")
            src_keys[key]=(game_key,name)
        off_keys={}
        for name in official:
            key=norm(name)
            if key in off_keys:raise ValueError("Official club source identity duplicated")
            off_keys[key]=name
        common=set(src_keys)&set(off_keys)
        for k in sorted(common):
            key,name=src_keys[k]
            all_matches.append((group,item["competition_code"],key,name,off_keys[k],
                                item["official_source_url"],"source_display_name_matches_published_roster"))
        for k in sorted(set(src_keys)-common):
            key,name=src_keys[k]
            exceptions.append((group,key,name,"",item["official_source_url"],
                "original_game_club_missing_from_2026_27_official_roster"))
        for k in sorted(set(off_keys)-common):
            exceptions.append((group,"","",off_keys[k],item["official_source_url"],
                "official_2026_27_club_absent_from_imported_FC27_game_source"))
        status="published_2026_27_club_roster_matches_original_FC27" if not (
            set(src_keys)^set(off_keys)) else "mismatch_needs_original_game_club_roster_decision"
        report.append((group,item["competition_code"],len(source),len(official),len(common),
                       len(src_keys.keys()-off_keys.keys()),len(off_keys.keys()-src_keys.keys()),
                       status,item["official_source_url"]))
    def dump(path,header,rows):
        with (out/path).open("w",encoding="utf-8-sig",newline="") as stream:
            writer=csv.writer(stream);writer.writerow(header);writer.writerows(rows)
    dump("FC27_INDEPENDENT_DOMESTIC_ROSTER_AUDIT.csv",(
         "Original_Source_Group","Competition_Code","Original_Game_Club_Count",
         "Independent_2026_27_Club_Count","Matched_Club_Count",
         "Original_Only_Clubs","Official_Only_Clubs","Real_Season_Status",
         "Independent_Official_Source_URL"),report)
    dump("FC27_CONFIRMED_FULL_ROSTER_GAME_CLUBS.csv",(
         "Game_Group","Home_League_Code","Original_Game_Key","Original_Game_Name",
         "Independent_Club_Name","Independent_Source_URL","Source_Limit"),all_matches)
    dump("FC27_REAL_WORLD_CLUB_ROSTER_EXCEPTIONS.csv",(
         "Game_Group","Game_Club_Key","Game_Club","Official_Club",
         "Independent_Official_Source_URL","Discrepancy"),exceptions)
    audited_rules=[]
    for r in config["movement_rules"]:
        if (not r["source_url"].startswith("https://") or
            r["competition_code"]!="2027:be.1" or
            r["league_size"]!=18 or r["regular_season_matches_per_club"]!=34
            or r["championship_playoffs"] or r["direct_relegations"]!=2):
            raise ValueError("Belgian 2026/27 official format has unexpected edge")
        audited_rules.append((r["country"],r["competition_code"],r["competition"],
          r["league_size"],r["regular_season_matches_per_club"],
          r["championship_playoffs"],r["direct_relegations"],r["source_url"],
          "specific_2026_27_regime_sourced_feeder_destinations_pending"))
    dump("FC27_OFFICIAL_COMPETITION_MOVEMENT_RULES_REVIEW.csv",(
        "Country","Competition_Code","Competition","Clubs",
        "Regular_Season_Matches_Per_Club","Championship_Playoffs",
        "Direct_Relegations","Official_Regulations_Source_URL",
        "Movement_Evidence_Status"),audited_rules)
    data={"version":VERSION,"edition":2027,
        "original_FC27_game_clubs":old,"eligible_FC27_game_clubs":staged,
        "excluded_original_clubs":old-staged,
        "domestic_source_competitions_named":staged,
        "official_season_leagues_participant_lists_checked":len(report),
        "participant_lists_fully_matching_original_game":sum(x[7].startswith("published") for x in report),
        "independent_same_year_original_club_matches":len(all_matches),
        "original_clubs_missing_from_actual_season_lists":sum(bool(x[1]) for x in exceptions),
        "actual_season_clubs_missing_from_original_game":sum(bool(x[3]) for x in exceptions),
        "original_game_source_roster_mismatches":len(exceptions),
        "new_versioned_official_movement_regime_records":len(audited_rules),
        "fc27_full_game_club_identity_certified":False,
        "fc27_2026_27_all_playable_rosters_certified":False,
        "season_end_promotion_graph_fully_verified":False,
        "career_ready":False,"original_game_squads_untouched":True}
    (out/"FC27_SEASON_ROSTER_AND_MOVEMENT_RULE_AUDIT.json").write_text(
        json.dumps(data,indent=2),encoding="utf-8")
    return data
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--registry",required=True)
    p.add_argument("--review",required=True);p.add_argument("--output",required=True)
    a=p.parse_args()
    print(json.dumps(compare(a.registry,a.review,a.output),indent=2))

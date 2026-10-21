"""Prioritise one historical PES career edition without unlocking unverified leagues.

Reads the already assembled 22-edition club+competition source evidence.
Reports what blocks each edition: clubs, game-only league IDs and one-hop
promotion/relegation. Never changes the career schema or production saves.
"""
from __future__ import annotations
import argparse
import csv
import json
import sqlite3
from collections import Counter,defaultdict
from pathlib import Path

VERSION="22-edition-pilot-readiness-audit-v1"
EXPECTED_EDITIONS=set(range(2005,2028))-{2025}
SOURCE_VIEW="edition_career_starting_league_candidates"


def audit(registry, output, strict=True):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(f"file:{Path(registry).resolve()}?mode=ro",uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise ValueError("Original historical evidence database corrupted")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Historical league foreign-key verification failed")
        tables={name for (name,) in db.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
        needed={SOURCE_VIEW,"edition_club_competitions","edition_readiness",
                "competition_seasons","season_versioned_rules"}
        if not needed.issubset(tables):
            raise ValueError("Missing source-backed original game career evidence tables")

        rows=db.execute(f"""SELECT p.edition,p.club_key,p.club,p.starting_competition,
                                    p.evidence_origin,e.group_type,e.original_source_league,
                                    p.career_status
                             FROM {SOURCE_VIEW} p
                             JOIN edition_club_competitions e
                             ON e.edition=p.edition AND e.club_key=p.club_key
                             ORDER BY p.edition,p.club_key""").fetchall()
        membership={int(y):Counter() for (y,) in
                    db.execute("SELECT DISTINCT edition FROM edition_club_competitions")}
        edition_sources=defaultdict(set)
        for edition,code in db.execute("SELECT edition,code FROM competition_seasons"):
            edition_sources[int(edition)].add(code)
        feeders=Counter()
        for edition,number in db.execute(
           "SELECT edition,COUNT(*) FROM sourced_nonplayable_feeder_clubs GROUP BY edition"):
            feeders[int(edition)]=number
        rules=defaultdict(list)
        for edition,lower,upper,verified in db.execute(
            "SELECT edition,lower,upper,feeder_verified FROM season_versioned_rules"):
            rules[int(edition)].append((lower,upper,bool(verified)))
        ready={int(y):int(v) for y,v in db.execute(
            "SELECT edition,career_ready FROM edition_readiness")}
        game_by_edition=Counter()
        for y, in db.execute("SELECT edition FROM game_source_domestic_competitions"):
            game_by_edition[int(y)]+=1

    missing_rows=[]
    game_only_rows=[]
    for y,key,name,comp,origin,group,original_source,status in rows:
        year=int(y);counter=membership[year]
        counter["total"]+=1
        if status!="blocked":raise ValueError("Cannot certify careers with unknown gate")
        if comp is None:
            if origin!="unresolved":
                raise ValueError("Missing competition must be marked unresolved")
            counter["unresolved"]+=1
            missing_rows.append((year,key,name,group,original_source or "",
                                 "missing_same_edition_domestic_league"))
        else:
            counter["with_evidence"]+=1
            counter["source:"+str(origin)]+=1
            if comp.startswith("GAME:"):
                counter["needs_game_league_to_pyramid_crosswalk"]+=1
                game_only_rows.append((year,key,name,comp,"game_league_without_verified_movement_link"))
            elif comp not in edition_sources[year]:
                # Independently dated additional league still needs entry
                # in the central promotion/relegation competition registry.
                counter["external_league_pending_registry"]+=1
                game_only_rows.append((year,key,name,comp,"additional_dated_league_not_yet_in_pyramid"))
        if group=="continental_cup_bucket":
            counter["continental_source_bucket"]+=1

    if strict and (len(rows)!=13104 or set(membership)!=EXPECTED_EDITIONS):
        raise ValueError("Expected all 22 original FIFA/FC editions and 13,104 clubs")
    if any(ready.values()):
        raise ValueError("No original unverified edition can be career-ready")
    report_rows=[]
    for year in sorted(membership):
        c=membership[year]
        unresolved=c["unresolved"]
        pending=c["needs_game_league_to_pyramid_crosswalk"]+c["external_league_pending_registry"]
        rule_count=len(rules[year])
        unverified=sum(not passed for _,_,passed in rules[year])
        official_feeder=feeders[year]
        # We rank by measured independent/source evidence, NOT implicit
        # readiness. Even the top candidate is strictly a diagnostic pilot.
        coverage=round(100*c["with_evidence"]/c["total"],2) if c["total"] else 0
        blockers=[]
        if unresolved: blockers.append("unresolved_original_game_clubs")
        if pending: blockers.append("game_leagues_not_mapped_to_playable_pyramid")
        if not rule_count:blockers.append("no_season_scoped_promotion_relegation_rules")
        elif unverified:blockers.append("unverified_feeder_boundaries")
        if not official_feeder:blockers.append("missing_one_hop_source_feeder_memberships")
        report_rows.append(dict(
          Edition=year,Original_Clubs=c["total"],
          Evidence_Club_Seasons=c["with_evidence"],
          Unresolved=c["unresolved"],
          Evidence_Coverage_Pct=coverage,
          Original_FIFA_Game_Only_League_IDs=c["needs_game_league_to_pyramid_crosswalk"],
          Additional_League_Not_Centrally_Registered=c["external_league_pending_registry"],
          Continental_Original_Source_Buckets=c["continental_source_bucket"],
          Promotion_Rules=rule_count,Unverified_Feeder_Rules=unverified,
          Source_Feeder_Club_Observations=official_feeder,
          Sourced_Competition_Seasons=len(edition_sources[year]),
          Game_Source_League_Groups=game_by_edition[year],
          Diagnostic_Blocked_By=" | ".join(blockers) or "manual_identity_validation_remaining",
          Can_Create_Career="no"))
    ranked=sorted(report_rows,key=lambda d:(
        -d["Evidence_Coverage_Pct"],d["Unresolved"],
        d["Original_FIFA_Game_Only_League_IDs"],-d["Promotion_Rules"],d["Edition"]))
    for pos,row in enumerate(ranked,1):
        row["Pilot_Evidence_Rank"]=pos
    report_rows.sort(key=lambda x:x["Edition"])
    def dump(name,header,data):
        with (out/name).open("w",newline="",encoding="utf-8-sig") as f:
            writer=csv.writer(f);writer.writerow(header);writer.writerows(data)
    header=["Edition","Original_Clubs","Evidence_Club_Seasons","Unresolved",
            "Evidence_Coverage_Pct","Original_FIFA_Game_Only_League_IDs",
            "Additional_League_Not_Centrally_Registered",
            "Continental_Original_Source_Buckets","Promotion_Rules",
            "Unverified_Feeder_Rules","Source_Feeder_Club_Observations",
            "Sourced_Competition_Seasons","Game_Source_League_Groups",
            "Diagnostic_Blocked_By","Can_Create_Career","Pilot_Evidence_Rank"]
    dump("HISTORICAL_EDITION_CAREER_PILOT_READINESS.csv",header,
         [[r.get(k,"") for k in header] for r in report_rows])
    dump("UNRESOLVED_GAME_CLUBS_PRIORITISED_BY_EDITION.csv",
         ("Edition","FIFA_Club_Key","FIFA_Club_Name","Original_Group_Type",
          "Original_League_Key","Reason"),missing_rows)
    dump("GAME_LEAGUE_PYRAMID_CROSSWALK_BACKLOG.csv",
         ("Edition","FIFA_Club_Key","FIFA_Club_Name","Starting_League_ID",
          "Reason"),game_only_rows)
    first=ranked[0]
    summary={
       "version":VERSION,"original_game_club_seasons":len(rows),
       "editions":len(membership),
       "club_seasons_with_home_league_evidence":sum(x["Evidence_Club_Seasons"] for x in report_rows),
       "unresolved_game_club_seasons":len(missing_rows),
       "league_to_pyramid_links_needing_verification":len(game_only_rows),
       "career_ready_editions":0,
       "first_diagnostic_pilot_year":first["Edition"],
       "pilot_edition_clubs":first["Original_Clubs"],
       "pilot_edition_missing_club_leagues":first["Unresolved"],
       "pilot_edition_coverage_percent":first["Evidence_Coverage_Pct"],
       "pilot_edition_unverified_feeder_rules":first["Unverified_Feeder_Rules"],
       "pilot_readiness":"read_only_evidence_diagnostic_not_career_enabled",
       "pilot_priority_order":[r["Edition"] for r in ranked],
       "source_clubs_unchanged":True,"production_careers_untouched":True}
    (out/"HISTORICAL_EDITIONS_PILOT_READINESS_AUDIT.json").write_text(
       json.dumps(summary,indent=2),encoding="utf-8")
    return summary


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--registry",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--no-strict",action="store_true")
    a=ap.parse_args()
    print(json.dumps(audit(a.registry,a.output,strict=not a.no_strict),indent=2))

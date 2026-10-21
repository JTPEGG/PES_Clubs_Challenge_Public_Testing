"""Edition-specific FC27 domestic competition and one-hop feeder release audit.

Audit *derived* active FC27 SQLite, not original archival source or career saves.
No source league label is treated as proof of an independently registered club.
No movement rule is silently assumed for competitions outside dated rule data.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from world_competition_exclusions import excluded_source_league
from world_historical_competition_topology import SCOPED_NAMES, topology


def audit(connection, *, strict=True):
    rows=connection.execute("""
        SELECT a.club_key, a.club, a.starting_competition,
               a.evidence_origin, a.verification_scope,
               e.original_source_league
        FROM fc27_2026_27_complete_source_competition_alignment a
        JOIN edition_club_competitions e
          ON e.edition=a.edition AND e.club_key=a.club_key
        WHERE a.edition=2027
    """).fetchall()
    if strict and len(rows)!=659:
        raise ValueError("FC27 active source club release count is not 659")
    if len({r[0] for r in rows})!=len(rows):
        raise ValueError("Source club appeared twice in FC27 active release")
    if any(not r[2] or excluded_source_league(r[5]) for r in rows):
        raise ValueError("Unknown or expressly excluded FC27 domestic club identity")
    if connection.execute(
        "SELECT COUNT(*) FROM edition_readiness WHERE edition=2027 AND career_ready!=0"
    ).fetchone()[0]:
        raise ValueError("Uncertified FC27 career has been enabled")

    meta={}
    for code,country,tier,name in connection.execute(
        "SELECT code,country,tier,name FROM competition_seasons WHERE edition=2027"
    ):
        meta[code]=(country,tier,name,"independent_fixture_competition_label")
    for code,country,tier,name,scope in connection.execute("""
        SELECT canonical_code,country,tier,competition,registration_scope
        FROM fc27_reviewed_domestic_competitions WHERE edition=2027
    """):
        old=meta.get(code)
        if old and (old[0],old[1])!=(country,tier):
            raise ValueError(f"Club source disagrees on {code} association and tier")
        meta[code]=(country,tier,name,scope)
    for code,country,name,tier in connection.execute("""
        SELECT league_code,country,competition,national_competition_tier
        FROM fc27_conmebol_2026_domestic_league_sources WHERE edition=2027
    """):
        old=meta.get(code)
        if old and (old[0],old[1])!=(country,tier):
            raise ValueError(f"2026 CONMEBOL first-division association conflict {code}")
        meta[code]=(country,tier,name,"individual_2026_name_review_not_complete_league")

    season=topology(2027)
    by_rule_id={(country,tier):rule_id
        for rule_id,(country,tier,name) in SCOPED_NAMES.items()}
    touched_nodes={edge["from"] for edge in season["promotion_edges"]}|{
        edge["to"] for edge in season["promotion_edges"]}
    closed={code for (code,) in connection.execute("""
        SELECT competition_code FROM season_non_pyramid_formats WHERE edition=2027
        AND direct_promotions=0 AND playoff_promotions=0 AND direct_relegations=0
    """)}
    fixture_count=Counter(dict(connection.execute("""
        SELECT competition_code,COUNT(*) FROM sourced_domestic_league_clubs
        WHERE edition=2027 GROUP BY competition_code
    """).fetchall()))
    feeder_by_country_tier=Counter()
    for code,tier,count in connection.execute("""
        SELECT competition_code,tier,COUNT(*) FROM sourced_nonplayable_feeder_clubs
        WHERE edition=2027 GROUP BY competition_code,tier
    """):
        if code in meta:
            country=meta[code][0]
            feeder_by_country_tier[(country,tier)]+=count
    clubs_by_code=defaultdict(list)
    scopes_by_code=defaultdict(set)
    for key,club,code,origin,scope,label in rows:
        clubs_by_code[code].append((key,club,origin,scope))
        scopes_by_code[code].add(scope)
    conmebol_original_clubs=connection.execute(
        "SELECT COUNT(*) FROM fc27_conmebol_original_club_domestic_candidates "
        "WHERE edition=2027"
    ).fetchone()[0]
    partial_licensed_original_clubs=connection.execute(
        "SELECT COALESCE(SUM(source_clubs),0) FROM fc27_reviewed_domestic_competitions "
        "WHERE edition=2027 AND registration_scope LIKE 'partial_licensed_subset%'"
    ).fetchone()[0]

    source_accepted={code:count for code,count in connection.execute("""
        SELECT competition_code,retained_source_club_count
        FROM fc27_source_as_provided_membership_policy WHERE edition=2027
    """)}
    if len(source_accepted)!=33 or sum(source_accepted.values())!=280:
        raise ValueError("FC27 user-accepted source groups missing from release")
    diagnostics=[]
    for code,members in sorted(clubs_by_code.items()):
        country,tier,name,meta_scope=meta.get(code,("unregistered",None,"not registered",
                                            "no_canonical_competition_metadata"))
        scope="|".join(sorted(scopes_by_code[code]))
        rule_id=by_rule_id.get((country,tier))
        if code in closed:
            rule="verified_closed_or_no_promotion_format"
        elif rule_id in touched_nodes:
            rule="partial_dated_pyramid_rules_external_feeder_unverified"
        else:
            rule="season_end_movement_rules_not_linked_or_unverified"
        # Accepted source clubs stay in the world, without fabricated extra clubs.
        accepted=code in source_accepted
        if accepted and source_accepted[code]!=len(members):
            raise ValueError("FC27 source acceptance does not match the club group")
        membership_status=("accepted_current_FC27_membership_as_provided"
                           if accepted else "independent_dated_membership_evidence_present")
        # One immediate lower tier only: never discover lower-of-lower clubs.
        direct_feeder=feeder_by_country_tier.get((country,tier+1),0) if tier else 0
        reasons=[]
        if country=="unregistered":reasons.append("canonical_competition_absent")
        if "partial_licensed_subset" in meta_scope or "partial_licensed_subset" in scope:
            reasons.append("licensed_subset_not_complete_domestic_division")
        if "individual_2026_club_membership" in scope:
            reasons.append("individual_clubs_reviewed_but_full_domestic_roster_not_verified")
        if not fixture_count[code] and not accepted:
            reasons.append("no_independent_dated_fixture_member_pool_for_this_competition")

        if rule.startswith("season_end_movement_rules"):
            reasons.append("2026_27_movement_destinations_missing")
        if rule=="partial_dated_pyramid_rules_external_feeder_unverified":
            reasons.append("movement_rules_partial_or_feeder_not_certified")
        reasons.append("source_club_original_EA_identity_not_certified")
        diagnostics.append({
            "competition_code":code,"country":country,"tier":tier,
            "competition":name,"source_club_count":len(members),
            "dated_fixture_member_count":fixture_count[code],
            "independent_immediate_feeder_observations":direct_feeder,
            "registration_scope":scope,"movement_rule_status":rule,
            "membership_status":membership_status,
            "additional_roster_membership_research_required":False,
            "playability_decision":"unchanged_pending_topology_review" if accepted else "unchanged",
            "certified_for_career":False,
            "remaining_blockers":";".join(reasons)
        })
    return {
        "version":"fc27-one-edition-domestic-league-completion-gate-v1",
        "edition":2027,"active_source_clubs":len(rows),
        "distinct_active_domestic_competitions":len(diagnostics),
        "unknown_home_league_clubs":0,
        "source_as_provided_competitions_user_accepted":len(source_accepted),
        "source_as_provided_original_clubs_preserved":sum(source_accepted.values()),
        "additional_membership_roster_research_required_for_current_scope":0,
        "greece_original_source_clubs_preserved":source_accepted["2027:gr.1"],
        "germany_second_division_source_clubs_preserved":source_accepted["2027:de.2"],
        "competition_playability_not_changed_by_this_decision":True,
        "clubs_in_partial_licensed_source_competitions":partial_licensed_original_clubs,
        "clubs_in_continental_source_domestic_review":conmebol_original_clubs,
        "competitions_without_independent_dated_membership_pool":sum(
            x["dated_fixture_member_count"]==0 for x in diagnostics),
        "competitions_with_no_linked_season_end_movement_rule":sum(
            x["movement_rule_status"]=="season_end_movement_rules_not_linked_or_unverified"
            for x in diagnostics),
        "competitions_with_partial_movement_rules":sum(
            x["movement_rule_status"]=="partial_dated_pyramid_rules_external_feeder_unverified"
            for x in diagnostics),
        "competitions_with_explicit_closed_format":sum(
            x["movement_rule_status"]=="verified_closed_or_no_promotion_format"
            for x in diagnostics),
        "known_dated_2027_pyramid_edges":len(season["promotion_edges"]),
        "complete_2027_canonical_movement_destinations":False,
        "one_hop_feeder_policy":"only tier+1 observed; never recursively generated",
        "next_task":"2026_27_promotion_relegation_and_one_hop_feeder_rules",
        "membership_scope_accepted_is_not_independent_fixture_verification":True,
        "all_original_EA_IDs_certified":False,
        "competition_rosters_and_feeders_certified":False,
        "career_ready":False,"FC26_allowed_to_start":False,
        "competitions":diagnostics
    }


def export(registry,outdir):
    out=Path(outdir);out.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(f"file:{Path(registry).resolve()}?mode=ro",uri=True) as db:
        report=audit(db)
    rows=report.pop("competitions")
    with (out/"FC27_ACTIVE_COMPETITION_STRUCTURE_GAPS.csv").open(
         "w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
    (out/"FC27_COMPETITION_STRUCTURE_READINESS.json").write_text(
        json.dumps(report,indent=2),encoding="utf-8"
    )
    return report


if __name__=="__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("--registry",required=True)
    cli.add_argument("--output",required=True)
    x=cli.parse_args()
    print(json.dumps(export(x.registry,x.output),indent=2))

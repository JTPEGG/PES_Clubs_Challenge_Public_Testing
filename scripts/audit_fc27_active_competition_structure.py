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
    staged_additional = {
        upper: (lower,source,status)
        for lower,upper,source,status in connection.execute("""
            SELECT lower_code,upper_code,regulation_source_url,rule_status
            FROM fc27_additional_movement_boundaries WHERE edition=2027
        """)
    }
    if len(staged_additional)!=9:
        raise ValueError("Expected all nine additional country movement routes")
    pragmatic_game_rules={
        code:(lower,up,playoff,down,delta,mode)
        for code,lower,up,playoff,down,delta,mode in connection.execute("""
          SELECT upper_code,immediate_lower_code,direct_promotions,
            playoff_promotions,direct_relegations,top_division_size_delta,movement_mode
          FROM fc27_remaining_34_gameplay_movement WHERE edition=2027
        """)
    }
    if len(pragmatic_game_rules)!=34:
        raise ValueError("Exactly 34 additional 2027 source league gameplay regimes required")
    game_feeders=connection.execute("""
       SELECT COUNT(*) FROM fc27_game_only_named_immediate_feeders
       WHERE edition=2027 AND original_game_club_pool_verified=0
    """).fetchone()[0]
    if game_feeders!=4:
        raise ValueError("Game policy must retain four open one-hop game feeder names")

    gameplay_decisions={
        (lower,upper):(up,playoff,down,tie,policy)
        for lower,upper,up,playoff,down,tie,policy in connection.execute("""
          SELECT lower_code,upper_code,direct_promotions,playoff_promotions,
                 direct_relegations,interdivision_playoff_places,status
          FROM fc27_user_approved_movement_game_rules WHERE edition=2027
        """)
    }
    if len(gameplay_decisions)!=2:
        raise ValueError("FC27 user-approved Italian and Austrian game decisions missing")
    if gameplay_decisions[("2027:it.2","2027:it.1")][:4]!=(2,1,3,0):
        raise ValueError("Italian game play-off numbers changed")
    if gameplay_decisions[("2027:at.2","2027:at.1")][:4]!=(1,0,1,0):
        raise ValueError("Austria direct-exchange game simplification changed")
    named_nonplayable_feeders=connection.execute("""
        SELECT COUNT(*) FROM fc27_extra_movement_feeder_nodes
        WHERE edition=2027 AND club_roster_verified=0
    """).fetchone()[0]
    effective_scope={
       code:(policy,basis,disclosure)
       for code,policy,basis,disclosure in connection.execute("""
          SELECT competition_code,movement_policy,policy_basis,
                 simplification_disclosure
          FROM fc27_effective_world_league_movement_scope WHERE edition=2027
       """)
    }
    if len(effective_scope)!=53:
        raise ValueError("Every active FC27 division requires an effective movement scope")
    closed_count=sum(v[0]=="closed" for v in effective_scope.values())
    if closed_count!=37 or sum(v[0]=="open_pyramid" for v in effective_scope.values())!=16:
        raise ValueError("Expected corrected user-selected 37-closed 16-open FC27 world")
    remaining_effective_feeders=connection.execute("""
      SELECT COUNT(*) FROM fc27_effective_named_immediate_game_feeders
    """).fetchone()[0]
    if remaining_effective_feeders!=4:
        raise ValueError("France Ligue 3, Italy Serie C, Netherlands Eerste Divisie and Portugal Liga 2 are named feeders")
    feeder_quality={
      code:(realnames,eligible)
      for code,realnames,eligible in connection.execute("""
        SELECT feeder_code,published_real_club_names,eligible_player_squads_for_PES
        FROM fc27_feeder_pool_readiness WHERE edition=2027
      """)
    }
    if len(feeder_quality)!=4 or sorted(n for n,e in feeder_quality.values() if n>0)!=[18,18,20,60]:
        raise ValueError("Four real 2026/27 feeder identity lists required, player squads still unavailable")
    if any(e for n,e in feeder_quality.values()):
        raise ValueError("No promotion from incomplete PES feeder squads is allowed")
    career_clubs=dict(connection.execute("""
        SELECT competition_mode,COUNT(*)
        FROM fc27_career_world_clubs WHERE edition=2027 GROUP BY competition_mode
    """))
    if career_clubs!={"open_league_season_candidate":314,
                     "playable_closed_league_candidate":30,
                     "closed_background_world":315}:
        raise ValueError("Expected 314 European and 30 MLS career clubs plus 315 background clubs")
    selectable=connection.execute("""
        SELECT COUNT(*) FROM fc27_manager_selectable_career_clubs
    """).fetchone()[0]
    if selectable!=344:
        raise ValueError("Expected 314 European plus 30 MLS selectable club candidates")
    mls_playable=connection.execute("""
      SELECT COUNT(*) FROM fc27_mls_playable_closed_league_approval
      WHERE edition=2027 AND no_promotion_or_relegation=1
        AND intended_manager_selectable=1
    """).fetchone()[0]
    if mls_playable!=1 or connection.execute("""
      SELECT COUNT(*) FROM fc27_mls_official_conference_membership
      WHERE edition=2027
    """).fetchone()[0]!=30:
        raise ValueError("MLS two-conference 30-club playable format missing")
    core_enabled=connection.execute("""
        SELECT COUNT(*) FROM fc27_effective_core_pyramid_game_boundaries
        WHERE edition=2027 AND game_enabled=1
    """).fetchone()[0]
    if core_enabled!=7:
        raise ValueError("Seven historical England/Germany/Spain movement edges must be open in gameplay")


    regional_groups=connection.execute("""
       SELECT country,regional_group,expected_members FROM
          fc27_regional_feeder_2026_27_group WHERE edition=2027
       ORDER BY country,regional_group
    """).fetchall()
    regional_clubs=connection.execute("""
       SELECT code,COUNT(*) FROM fc27_regional_feeder_2026_27_club
       WHERE edition=2027 GROUP BY code
    """).fetchall()
    if (len(regional_groups)!=7 or
        dict(regional_clubs)!={"2027:es.3":40,"2027:de.4":91} or
        sorted(n for c,g,n in regional_groups)!=[18,18,18,18,19,20,20]):
        raise ValueError("Spain two / Germany five sourced regional club pools must contain 40+91 teams")
    regional_policies=connection.execute("""
       SELECT lower_code,upper_code,expected_promoted,upper_relegated,
              promotion_simulation_enabled
       FROM fc27_regional_feeder_game_policy
       WHERE edition=2027 ORDER BY lower_code
    """).fetchall()
    if regional_policies!=[
      ("2027:de.4","2027:de.3",4,4,0),
      ("2027:es.3","2027:es.2",4,4,0)
    ]:
        raise ValueError("German Spanish two one-hop 4-up/4-down game policies changed")
    if connection.execute("""
       SELECT COUNT(*) FROM fc27_regional_feeder_2026_27_club
       WHERE PES_player_squad_imported!=0 OR promotion_eligible_game_registration!=0
    """).fetchone()[0]:
        raise ValueError("Regional players or promotion eligibility falsely certified")

    routes=connection.execute("""
      SELECT upper_code,lower_code,route_type,executable_career_movement
      FROM fc27_effective_playable_season_end_routes WHERE edition=2027
    """).fetchall()
    if (len(routes)!=16 or
        len({x[0] for x in routes})!=16 or
        any(r[3] for r in routes) or
        any(r[0]=="2027:us.mls" for r in routes)):
        raise ValueError("All 16 sourced game movement routes must be indexed, with MLS excluded")
    route_modes=dict(Counter(r[2] for r in routes))
    if route_modes!={"dated_core_pyramid":7,
                     "sourced_country_game_override":6,
                     "simplified_delegated_game":1,
                     "regional_4_up_4_down":2}:
        raise ValueError("Unexpected source provenance in FC27 game movement routes")

    diagnostics=[]
    for code,members in sorted(clubs_by_code.items()):
        country,tier,name,meta_scope=meta.get(code,("unregistered",None,"not registered",
                                            "no_canonical_competition_metadata"))
        scope="|".join(sorted(scopes_by_code[code]))
        rule_id=by_rule_id.get((country,tier))
        if effective_scope.get(code,(None,))[0]=="closed":
            rule="user_approved_closed_game_league_no_promotion_relegation"
        elif code in closed:
            rule="verified_closed_or_no_promotion_format"
        elif code in staged_additional:
            rule="season_dated_source_rules_mapped_feeder_not_certified"
        elif code in pragmatic_game_rules:
            rule=("game_policy_no_promotion_relegation"
                  if pragmatic_game_rules[code][-1]=="no_promotion_or_relegation"
                  else "game_policy_simplified_one_hop_unpopulated_feeder")
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
        if rule=="season_dated_source_rules_mapped_feeder_not_certified":
            reasons.append("published_movement_regime_mapped_but_lower_club_eligibility_pending")
        if rule=="game_policy_simplified_one_hop_unpopulated_feeder":
            reasons.append("game_assumption_identifies_only_lower_division_not_promotion_eligible_clubs")
        if rule in ("game_policy_no_promotion_relegation",
                    "user_approved_closed_game_league_no_promotion_relegation"):
            reasons.append("gameplay_closed_no_feeder_required_source_clubs_remain")
        reasons.append("source_club_original_EA_identity_not_certified")
        diagnostics.append({
            "competition_code":code,"country":country,"tier":tier,
            "competition":name,"source_club_count":len(members),
            "dated_fixture_member_count":fixture_count[code],
            "independent_immediate_feeder_observations":direct_feeder,
            "registration_scope":scope,"movement_rule_status":rule,
            "effective_game_movement_scope":effective_scope[code][0],
            "effective_game_scope_origin":effective_scope[code][1],
            "effective_gameplay_simplification":effective_scope[code][2],
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
        "additional_source_country_movement_edges":len(staged_additional),
        "new_pragmatic_gameplay_competition_decisions":len(pragmatic_game_rules),
        "gameplay_closed_leagues_across_entire_fc27":closed_count,
        "gameplay_open_leagues_across_entire_fc27":53-closed_count,
        "manager_intended_playable_countries":9,
        "manager_intended_playable_competition_codes_including_MLS":17,
        "manager_MLS_original_clubs":career_clubs["playable_closed_league_candidate"],
        "manager_MLS_no_promotion_relegation":True,
        "manager_intended_playable_competition_codes":16,
        "manager_intended_playable_club_candidates":selectable,
        "effective_historical_core_pyramid_edges_enabled":core_enabled,
        "former_german_core_edges_effectively_disabled":0,
        "gameplay_remaining_effective_feeders_without_club_rosters":remaining_effective_feeders,
        "dated_real_spanish_regional_feeder_names":dict(regional_clubs)["2027:es.3"],
        "dated_real_german_regional_feeder_names":dict(regional_clubs)["2027:de.4"],
        "named_regional_source_groups":len(regional_groups),
        "regional_game_4up_4down_policies_staged":len(regional_policies),
        "fc27_effective_open_playable_season_end_routes":len(routes),
        "fc27_career_movement_routes_actually_executable":0,
        "fc27_effective_rule_route_provenance_counts":route_modes,
        "fc27_MLS_separate_playable_without_relegation_route":True,
        "regional_playable_PES_squads_verified":0,
        "feeder_divisions_with_official_real_2026_27_memberships":sum(
            n>0 for n,e in feeder_quality.values()),
        "genuine_feeder_club_names_registered":connection.execute("""
          SELECT COUNT(*) FROM fc27_sourced_real_one_hop_feeder_clubs
          WHERE edition=2027
        """).fetchone()[0],
        "official_real_feeder_clubs_in_current_open_league_scope":sum(
            n for n,e in feeder_quality.values()),
        "retained_real_belgian_feeder_names_but_no_active_belgian_movement":15,
        "feeder_divisions_still_without_any_2026_27_real_club_pool":sum(
            n==0 for n,e in feeder_quality.values()),
        "original_clubs_eligible_for_open_league_schedule_after_game_import":
            career_clubs["open_league_season_candidate"],
        "original_clubs_retained_in_closed_background_job_and_transfer_market":
            career_clubs["closed_background_world"],
        "original_clubs_eligible_for_any_intended_playable_competition":selectable,
        "feeder_players_ready_for_real_PES_matches":0,
        "no_feeder_required_for_closed_leagues":True,
        "gameplay_competitions_with_closed_division_format":sum(
            x[-1]=="no_promotion_or_relegation" for x in pragmatic_game_rules.values()),
        "gameplay_named_one_hop_feeders_without_club_squads":game_feeders,
        "gameplay_original_extra_named_feeder_nodes_before_closure_filter":named_nonplayable_feeders,
        "gameplay_country_rule_codes_mapped_in_existing_active_competitions":len(pragmatic_game_rules),
        "no_remaining_completely_unmapped_active_movement_policy":True,
        "user_approved_explicit_gameplay_movement_simplifications":len(gameplay_decisions),
        "italian_serie_b_gameplay_uses_promotion_playoff":True,
        "austrian_prior_direct_exchange_retained_in_history_but_game_closed":True,
        "austrian_gameplay_uses_direct_one_up_one_down":False,
        "game_assumptions_separated_from_historical_regulations":True,
        "total_staged_2027_movement_edges":len(season["promotion_edges"])+len(staged_additional),
        "additional_one_hop_feeder_names_without_game_rosters":named_nonplayable_feeders,
        "competitions_with_additional_season_dated_movement_rules":sum(
            x["movement_rule_status"]=="season_dated_source_rules_mapped_feeder_not_certified"
            for x in diagnostics),
        "complete_2027_canonical_movement_destinations":False,
        "one_hop_feeder_policy":"only tier+1 observed; never recursively generated",
        "next_task":"verify_promotion_eligible_one_hop_club_pools_and_apply_playable_gameplay_rules",
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

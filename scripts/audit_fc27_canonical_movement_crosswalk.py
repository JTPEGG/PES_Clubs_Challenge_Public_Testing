"""FC27 2026/27-only canonical promotion/relegation *crosswalk*, not gameplay.

Never turn published rule templates into automatic transfers of clubs without
verified season entrants, player identities, destination league or qualification.
Link existing 2027 dated English, German and Spanish pyramid nodes to their
source competition identities, including original FC27 2. Bundesliga clubs.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path

from world_historical_competition_topology import SCOPED_NAMES, topology

EDITION = 2027
NODE_TO_CANONICAL = {
    "ENG:PL": "2027:en.1", "ENG:CH": "2027:en.2",
    "ENG:L1": "2027:en.3", "ENG:L2": "2027:en.4",
    "ENG:NL": "2027:en.5",  # ONE immediate non-playable feeder below League Two
    "GER:BL1": "2027:de.1", "GER:BL2": "2027:de.2",
    "GER:D3": "2027:de.3",
    "ESP:LL1": "2027:es.1", "ESP:LL2": "2027:es.2",
}


def audit(db):
    source = topology(EDITION)
    registered = {
        code: (country, int(tier), int(count))
        for code,country,tier,count in db.execute("""
          SELECT competition_code,country,tier,active_source_clubs
          FROM fc27_2026_27_active_domestic_competitions
        """)
    }
    # The National League has a dated 24-club fixture pool, but no imported
    # original FC27 playable squads. It is the *only* non-playable node mapped
    # here, as the immediate promotion/relegation source for League Two.
    fixture_competitions = {
        code: (country,int(tier))
        for code,country,tier in db.execute("""
          SELECT code,country,tier FROM competition_seasons WHERE edition=2027
        """)
    }
    game_source_clubs = {}
    for code,count in db.execute("""
        SELECT starting_competition,COUNT(*)
        FROM fc27_2026_27_complete_source_competition_alignment
        GROUP BY starting_competition
    """):
        game_source_clubs[code]=count
    legacy_rules = {
        (lower,upper): (promotions,playoffs,relegations,entrants,status)
        for lower,upper,promotions,playoffs,entrants,relegations,status in db.execute("""
          SELECT lower,upper,direct_promotions,playoff_promotions,
                 eligible_ranks,direct_relegations,source_status
          FROM season_versioned_rules WHERE edition=2027
        """)
    }
    edges=[]
    for item in source["promotion_edges"]:
        lower,upper=item["from"],item["to"]
        if lower not in NODE_TO_CANONICAL or upper not in NODE_TO_CANONICAL:
            raise ValueError("2027 movement template includes unscoped competition")
        lower_code,upper_code=NODE_TO_CANONICAL[lower],NODE_TO_CANONICAL[upper]
        meta_lower=registered.get(lower_code)
        meta_upper=registered.get(upper_code)
        feeder=False
        if lower=="ENG:NL":
            feeder=True
            if lower_code not in fixture_competitions:
                raise ValueError("National League immediate feeder missing")
            country,tier=fixture_competitions[lower_code]
            meta_lower=(country,tier,0)
            if db.execute("""
                SELECT COUNT(*) FROM sourced_nonplayable_feeder_clubs
                WHERE edition=2027 AND competition_code=?
            """,(lower_code,)).fetchone()[0]!=24:
                raise ValueError("The dated 2026/27 National League feeder is not 24 clubs")
        if meta_lower is None or meta_upper is None:
            raise ValueError(f"Missing actual 2027 competition code {lower_code} -> {upper_code}")
        for node,meta in ((lower,meta_lower),(upper,meta_upper)):
            ctry,tier,name=SCOPED_NAMES[node]
            if meta[:2]!=(ctry,tier):
                raise ValueError(f"Original FC27 competition country/tier changed: {node}")
        expected_automatic=int(item["auto_promotions"])
        expected_playoff=int(item["playoff_promotions"])
        expected_relegations=item["automatic_relegations"]
        if expected_relegations is None:
            raise ValueError("Unknown automatic relegation destination")
        prior=legacy_rules.get((lower,upper))
        if prior is not None and prior[:3]!=(
            expected_automatic,expected_playoff,expected_relegations
        ):
            raise ValueError("Two independent dated movement models contradict each other")
        if not item["source_url"].startswith("https://"):
            raise ValueError("Published season competition rule reference missing")
        edges.append(dict(
            season=EDITION,lower_code=lower_code,upper_code=upper_code,
            lower_clubs_from_original_FC27=int(meta_lower[2]),
            upper_clubs_from_original_FC27=int(meta_upper[2]),
            lower_is_immediate_one_hop_feeder=feeder,
            direct_promotions=expected_automatic,
            playoff_promotion_places=expected_playoff,
            direct_relegations=expected_relegations,
            playoff_format=item["playoff_note"],
            published_rule_source=item["source_url"],
            rule_data_crosschecked_in_season_versioned_rules=prior is not None,
            canonical_destination_validated=True,
            complete_season_end_simulation_certified=False,
        ))
    if len(edges)!=7:
        raise ValueError("Expected exactly seven previously sourced 2026/27 pyramid edges")
    if game_source_clubs.get("2027:de.2")!=18:
        raise ValueError("German second-tier original squad group must remain intact")
    if db.execute("""
      SELECT COUNT(*) FROM edition_readiness WHERE edition=2027 AND career_ready!=0
    """).fetchone()[0]:
        raise ValueError("Unverified FC27 careers must remain disabled")
    return {
        "edition":EDITION,
        "source_2027_competition_edges_canonically_linked":len(edges),
        "linked_legacy_2027_season_rule_crosschecks":sum(
            x["rule_data_crosschecked_in_season_versioned_rules"] for x in edges),
        "national_league_one_hop_feeder_present":any(
            x["lower_is_immediate_one_hop_feeder"] for x in edges),
        "german_second_tier_original_clubs_preserved":game_source_clubs["2027:de.2"],
        "canonical_nodes_in_existing_2027_pyramid":len(NODE_TO_CANONICAL),
        "all_53_competitions_career_ready":False,
        "future_career_saves_not_modified":True,
        "note":"Seven already evidenced starting-season 2027 movement edges have canonical destinations; complete feeder eligibility, wider-country movement, and playable division decisions remain separate.",
        "edges":edges,
    }


def export(dbfile,outdir):
    path=Path(outdir);path.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(f"file:{Path(dbfile).resolve()}?mode=ro",uri=True) as db:
        data=audit(db)
    edges=data.pop("edges")
    with (path/"FC27_SEVEN_CANONICAL_MOVEMENT_BOUNDARIES.csv").open(
      "w",encoding="utf-8-sig",newline=""
    ) as handle:
        writer=csv.DictWriter(handle,fieldnames=list(edges[0]))
        writer.writeheader();writer.writerows(edges)
    (path/"FC27_MOVEMENT_BOUNDARY_NEXT_STAGE.json").write_text(
        json.dumps(data,indent=2),encoding="utf-8"
    )
    return data


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--registry",required=True)
    ap.add_argument("--output",required=True)
    a=ap.parse_args()
    print(json.dumps(export(a.registry,a.output),indent=2))

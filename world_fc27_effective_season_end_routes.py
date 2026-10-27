"""FC27 one-hop season-end movement routing index for all 16 game-open leagues.

Structural bridge only. Routes are sourced from effective game policy, not
original regulation when an explicit simplified policy supersedes it.
MLS is playable separately but not in sporting movement routes.
This table deliberately cannot be used as a live career-write ledger.
"""
from __future__ import annotations
import sqlite3
from world_historical_competition_topology import topology
from scripts.audit_fc27_canonical_movement_crosswalk import NODE_TO_CANONICAL

EDITION=2027
EXPECTED={
 "2027:en.1":"2027:en.2",
 "2027:en.2":"2027:en.3",
 "2027:en.3":"2027:en.4",
 "2027:en.4":"2027:en.5",
 "2027:de.1":"2027:de.2",
 "2027:de.2":"2027:de.3",
 "2027:de.3":"2027:de.4",
 "2027:es.1":"2027:es.2",
 "2027:es.2":"2027:es.3",
 "2027:fr.1":"2027:fr.2",
 "2027:fr.2":"2027:fr.3",
 "2027:it.1":"2027:it.2",
 "2027:it.2":"2027:it.3",
 "2027:sco.1":"2027:sco.2",
 "2027:nl.1":"2027:nl.2",
 "2027:pt.1":"2027:pt.2",
}
SCHEMA="""
CREATE TABLE fc27_effective_playable_season_end_routes(
 edition INTEGER NOT NULL CHECK(edition=2027),
 upper_code TEXT NOT NULL,
 lower_code TEXT NOT NULL,
 route_type TEXT NOT NULL CHECK(route_type IN
   ('dated_core_pyramid','sourced_country_game_override',
    'simplified_delegated_game','regional_4_up_4_down')),
 direct_promotions INTEGER,
 lower_playoff_promotions INTEGER,
 upper_direct_relegations INTEGER,
 upper_conditional_survival_places INTEGER,
 rule_notes TEXT NOT NULL,
 route_verification_status TEXT NOT NULL CHECK(
  route_verification_status='source_and_game_rules_defined_squads_missing'),
 executable_career_movement INTEGER NOT NULL CHECK(executable_career_movement=0),
 PRIMARY KEY(edition,upper_code)
);
CREATE VIEW fc27_season_end_gameplay_readiness AS
 SELECT r.edition,r.upper_code,r.lower_code,r.route_type,
        r.rule_notes,r.executable_career_movement,
        CASE WHEN r.lower_code IN ('2027:es.3','2027:de.4')
          THEN 'multiple_real_regional_groups_no_PES_squads'
          WHEN r.lower_code='2027:en.5'
          THEN 'dated_national_league_no_PES_squads'
          ELSE 'named_lower_club_source_or_in_game_division_roster_not_certified_for_PES'
        END AS feeder_readiness
 FROM fc27_effective_playable_season_end_routes r;
"""

def stage(db:sqlite3.Connection, *,strict=True):
    core={
       upper:(lower,int(enabled)) for lower,upper,enabled in db.execute("""
         SELECT lower_code,upper_code,game_enabled
         FROM fc27_effective_core_pyramid_game_boundaries WHERE edition=2027
       """)
    }
    if len(core)!=7 or any(e!=1 for l,e in core.values()):
        raise ValueError("All seven official England Germany Spain routes must be game enabled")
    template={}
    for r in topology(2027)["promotion_edges"]:
        low=NODE_TO_CANONICAL[r["from"]]
        up=NODE_TO_CANONICAL[r["to"]]
        template[up]=r
    sourced={
      upper:(lower,auto,po,down,extra,note)
      for lower,upper,auto,po,down,extra,note in db.execute("""
        SELECT lower_code,upper_code,direct_promotions,playoff_promotions,
          direct_relegations,interdivision_playoff_places,effective_format
        FROM fc27_effective_additional_movement_after_world_closure
        WHERE edition=2027
      """)
      if upper in EXPECTED
    }
    delegated={
      upper:(lower,auto,po,down,mode,notes)
      for upper,lower,auto,po,down,mode,notes in db.execute("""
        SELECT upper_code,immediate_lower_code,direct_promotions,
           playoff_promotions,direct_relegations,movement_mode,
           explicit_assumption_disclosure
        FROM fc27_remaining_34_gameplay_movement WHERE edition=2027
      """)
      if upper in EXPECTED
    }
    regional={
      upper:(lower,auto,promoted,down)
      for lower,upper,auto,promoted,down in db.execute("""
        SELECT lower_code,upper_code,automatic_group_champions,
            expected_promoted,upper_relegated
        FROM fc27_regional_feeder_game_policy WHERE edition=2027
      """)
    }
    expected_cohorts=(7,6,1,2)
    if (len(core),len(sourced),len(delegated),len(regional))!=expected_cohorts:
        raise ValueError("All 16 game routes need exactly 7 core,6 source,1 delegated,2 regional")
    coverage={}
    def add(upper,lower,kind,auto,po,down,conditional,note):
        if upper in coverage:
            raise ValueError(f"Duplicate effective national game route {upper}")
        if EXPECTED.get(upper)!=lower:
            raise ValueError(f"Off-scope or wrong one-hop feeder for {upper}")
        if not note:
            raise ValueError("No source description for game route")
        coverage[upper]=(2027,upper,lower,kind,auto,po,down,conditional,note,
                         "source_and_game_rules_defined_squads_missing",0)
    for upper,(lower,enabled) in core.items():
        edge=template[upper]
        auto=edge["auto_promotions"]
        playoff=edge["playoff_promotions"]
        down=edge["automatic_relegations"]
        # Bundesliga and 2.Bundesliga are conditional upper-vs-lower
        # survival ties, not additional guaranteed promotion slots.
        conditional=playoff if upper.startswith("2027:de.") else 0
        po=0 if conditional else playoff
        if (auto+po!=down) or (conditional and po):
            raise ValueError("Original Germany conditional boundary cannot become 3 guaranteed promotions")
        add(upper,lower,"dated_core_pyramid",auto,po,down,conditional,
            str(edge["playoff_note"]))
    for upper,(lower,auto,po,down,extra,note) in sourced.items():
        if not isinstance(auto,int) or not isinstance(down,int):
            raise ValueError("Missing confirmed source-country base exchange count")
        if po is None:
            po=0
        if extra is None:
            extra=0
        # A lower-league playoff promotion must balance automatic relegation,
        # conditional upper-vs-lower games do not count toward direct movement.
        if auto+po!=down:
            raise ValueError(f"Source/game country lower feeder places do not balance: {upper}")
        add(upper,lower,"sourced_country_game_override",auto,po,down,extra,str(note))
    for upper,(lower,auto,po,down,mode,notes) in delegated.items():
        if mode!="gameplay_simplified_one_hop_exchange" or auto+po!=down:
            raise ValueError("Explicit source-game closure leaked into 16 playable routes")
        add(upper,lower,"simplified_delegated_game",auto,po,down,0,notes)
    for upper,(lower,groups,up,down) in regional.items():
        if up!=4 or down!=4 or not groups:
            raise ValueError("Four up/down regional group model changed")
        add(upper,lower,"regional_4_up_4_down",
            2 if upper=="2027:es.2" else 3,
            2 if upper=="2027:es.2" else 1,
            down,0,"Real 2026/27 separate regional tables + explicit recorded playoff winners; relegated-club regional allocation requires source evidence")
    if set(coverage)!=set(EXPECTED):
        raise ValueError("Some playable upper division has no eligible immediate promotion route")
    if db.execute("""
       SELECT COUNT(*) FROM fc27_eight_country_playable_approval
    """).fetchone()[0]!=16:
        raise ValueError("Expected 16 European game-playable division candidates")
    if db.execute("""
      SELECT COUNT(*) FROM fc27_mls_playable_closed_league_approval
      WHERE no_promotion_or_relegation=1 AND intended_manager_selectable=1
    """).fetchone()[0]!=1:
        raise ValueError("MLS must be playable but have no sporting lower feeder")
    db.executescript(SCHEMA)
    db.executemany("""
       INSERT INTO fc27_effective_playable_season_end_routes
       VALUES(?,?,?,?,?,?,?,?,?,?,?)
    """,[coverage[x] for x in sorted(coverage)])
    if db.execute("""
      SELECT COUNT(*) FROM fc27_effective_playable_season_end_routes
      WHERE upper_code='2027:us.mls' OR executable_career_movement!=0
    """).fetchone()[0]:
        raise ValueError("No MLS promotion route or premature real career mutation")
    if db.execute("""
      SELECT COUNT(*) FROM edition_readiness WHERE edition=2027 AND career_ready!=0
    """).fetchone()[0] or db.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("No active career while game/PES fixture and feeder squad data unresolved")
    return {
       "edition":2027,"open_playable_routes_with_derived_effective_rule":16,
       "source_core_routes":len(core),"sourced_country_game_rules":len(sourced),
       "delegated_one_hop_rules":len(delegated),"dated_regional_rules":len(regional),
       "MLS_closed_pyramid_is_independently_playable":True,
       "MLS_erroneous_relegation_routes":0,
       "actual_career_league_movements_enabled":0,
       "missing_real_PES_roster_activation_blocked":True
    }

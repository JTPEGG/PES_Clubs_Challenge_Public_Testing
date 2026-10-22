"""FC27 edition-specific final gameplay promotion/relegation SCOPE, not career play.

Close peripheral divisions while keeping original teams, squads, transfers
and job markets intact. Retain historical published rules separately. Only
open pyramids can demand feeder club pools; named unpopulated divisions never
become fabricated clubs. Explicit user-approved Italy and Austria exceptions
are protected.
"""
from __future__ import annotations

import sqlite3

EDITION=2027
CLOSED_SOURCE_BOUNDARIES=frozenset({"2027:ch.1"})
EXPECTED_CLOSED_FROM_34=30
EXPECTED_OPEN_2027=21
EXPECTED_CLOSED_2027=32
PRESERVE_SOURCE_GAME_OVERRIDES=frozenset({"2027:it.1","2027:at.1"})
SCHEMA="""
CREATE TABLE fc27_effective_world_league_movement_scope(
  edition INTEGER NOT NULL CHECK(edition=2027),
  competition_code TEXT NOT NULL,
  country TEXT NOT NULL,
  tier INTEGER NOT NULL,
  original_game_source_clubs INTEGER NOT NULL CHECK(original_game_source_clubs>0),
  movement_policy TEXT NOT NULL CHECK(movement_policy IN ('open_pyramid','closed')),
  policy_basis TEXT NOT NULL,
  simplification_disclosure TEXT NOT NULL,
  ready_for_simulation INTEGER NOT NULL CHECK(ready_for_simulation=0),
  PRIMARY KEY(edition,competition_code)
);
CREATE TABLE fc27_additional_historical_source_league_closure(
  edition INTEGER NOT NULL CHECK(edition=2027),
  upper_code TEXT NOT NULL,
  reason TEXT NOT NULL,
  override_kind TEXT NOT NULL CHECK(override_kind='user_delegated_no_promotion_or_relegation'),
  PRIMARY KEY(edition,upper_code),
  FOREIGN KEY(edition,upper_code) REFERENCES
    fc27_effective_world_league_movement_scope(edition,competition_code)
);
CREATE VIEW fc27_effective_additional_movement_after_world_closure AS
 SELECT a.edition,a.lower_code,a.upper_code,a.country,a.lower_name,a.upper_name,
  CASE WHEN c.upper_code IS NOT NULL THEN 0 ELSE a.effective_direct_promotions END
    AS direct_promotions,
  CASE WHEN c.upper_code IS NOT NULL THEN 0 ELSE a.effective_playoff_promotions END
    AS playoff_promotions,
  CASE WHEN c.upper_code IS NOT NULL THEN 0 ELSE a.effective_direct_relegations END
    AS direct_relegations,
  CASE WHEN c.upper_code IS NOT NULL THEN 0 ELSE a.effective_interdivision_playoff_places END
    AS interdivision_playoff_places,
  CASE WHEN c.upper_code IS NOT NULL THEN 'no_promotion_or_relegation'
       ELSE a.effective_playoff_description END AS effective_format,
  CASE WHEN c.upper_code IS NOT NULL THEN 'user_delegated_closed_game_league'
       ELSE a.effective_rule_provenance END AS game_rule_origin,
  a.historical_source_url,
  a.promotion_simulation_ready
 FROM fc27_effective_additional_game_movement_rules a
 LEFT JOIN fc27_additional_historical_source_league_closure c
   ON c.edition=a.edition AND c.upper_code=a.upper_code;
CREATE VIEW fc27_effective_named_immediate_game_feeders AS
 SELECT f.edition,f.competition_code,f.country,f.tier,f.name,
    'delegated_game_open_pyramid_unpopulated' AS basis
 FROM fc27_game_only_named_immediate_feeders f
 JOIN fc27_remaining_34_gameplay_movement r
   ON r.edition=f.edition AND r.immediate_lower_code=f.competition_code
 JOIN fc27_effective_world_league_movement_scope s
   ON s.edition=r.edition AND s.competition_code=r.upper_code
 WHERE s.movement_policy='open_pyramid'
 UNION ALL
 SELECT f.edition,f.competition_code,f.country,f.tier,f.name,
    'published_lower_division_unpopulated' AS basis
 FROM fc27_extra_movement_feeder_nodes f
 JOIN fc27_additional_movement_boundaries r
   ON r.edition=f.edition AND r.lower_code=f.competition_code
 JOIN fc27_effective_world_league_movement_scope s
   ON s.edition=r.edition AND s.competition_code=r.upper_code
 WHERE s.movement_policy='open_pyramid';
"""

def close_peripheral_leagues(db:sqlite3.Connection, *, strict=True):
    registered={
        code:(country,int(tier),int(count))
        for code,country,tier,count in db.execute("""
          SELECT competition_code,country,tier,active_source_clubs
          FROM fc27_2026_27_active_domestic_competitions
        """)
    }
    if strict and (len(registered)!=53 or sum(x[2] for x in registered.values())!=659):
        raise ValueError("Cannot determine source divisions before applying closed-world policy")
    delegated={
       code:(mode,reason)
       for code,mode,reason in db.execute("""
         SELECT upper_code,movement_mode,explicit_assumption_disclosure
         FROM fc27_remaining_34_gameplay_movement WHERE edition=2027
       """)
    }
    other={
       upper:lower
       for upper,lower in db.execute("""
          SELECT upper_code,lower_code FROM fc27_additional_movement_boundaries
          WHERE edition=2027
       """)
    }
    official_closed={
       code for (code,) in db.execute("""
         SELECT competition_code FROM season_non_pyramid_formats
         WHERE edition=2027 AND direct_promotions=0
           AND playoff_promotions=0 AND direct_relegations=0
       """)
    }
    if len(delegated)!=34 or len(other)!=9 or official_closed!={"2027:us.mls"}:
        raise ValueError("Existing FC27 competition policy cohorts have drifted")
    if set(delegated)&set(other) or (set(delegated)|set(other))&official_closed:
        raise ValueError("Source regime cohorts overlap")
    if len(CLOSED_SOURCE_BOUNDARIES & set(other))!=1:
        raise ValueError("Source-backed Swiss competition closure not found")
    if PRESERVE_SOURCE_GAME_OVERRIDES & (set(CLOSED_SOURCE_BOUNDARIES)|
         {code for code,(mode,reason) in delegated.items() if mode=="no_promotion_or_relegation"}):
        raise ValueError("Earlier user-approved Italy or Austria movement regime wrongly closed")
    game_overrides={code:(up,playoff,down,tie) for code,up,playoff,down,tie in db.execute("""
       SELECT upper_code,direct_promotions,playoff_promotions,
              direct_relegations,interdivision_playoff_places
       FROM fc27_user_approved_movement_game_rules WHERE edition=2027
    """)}
    if (set(game_overrides)!=PRESERVE_SOURCE_GAME_OVERRIDES or
        game_overrides["2027:it.1"]!=(2,1,3,0) or
        game_overrides["2027:at.1"]!=(1,0,1,0)):
        raise ValueError("Italian always-playoff or Austrian direct-swap rule was changed")
    before=dict(registered)
    completed=[]
    for code,(country,tier,count) in sorted(registered.items()):
        if code in delegated:
            mode,reason=delegated[code]
            closed=mode=="no_promotion_or_relegation"
            policy="user_delegated_closed_game_league" if closed else "user_delegated_open_game_league"
            description=reason
        elif code in other:
            closed=code in CLOSED_SOURCE_BOUNDARIES
            policy="user_delegated_closed_over_historical_rule" if closed else "dated_regime_open"
            description=("Closed Swiss Super League for game simulation; historical 11th-place barrage, 12th-place drop and all source evidence retained but not executed."
                        if closed else "Retain dated source movement regime with existing disclosed gameplay overrides.")
        elif code in official_closed:
            closed=True
            policy="original_verified_closed_format"
            description="Official 2026 MLS closed-league regime has no sporting promotion/relegation."
        else:
            closed=False
            policy="previously_mapped_core_game_pyramid"
            description="Preserve England Germany Spain dated source pyramid and one-hop national feeders."
        completed.append((2027,code,country,tier,count,"closed" if closed else "open_pyramid",
                          policy,description,0))
    if not ({x[1] for x in completed}==set(registered)):
        raise ValueError("FC27 final game classification omitted an original league")
    closes=[x for x in completed if x[5]=="closed"]
    if len(closes)!=EXPECTED_CLOSED_2027 or len(completed)-len(closes)!=EXPECTED_OPEN_2027:
        raise ValueError("FC27 closed/open scope changed without approval and audit")
    if sum(code in delegated and mode=="no_promotion_or_relegation"
           for code,(mode,reason) in delegated.items())!=EXPECTED_CLOSED_FROM_34:
        raise ValueError("Expected 30 of 34 peripheral gameplay leagues closed")
    if db.execute("""
        SELECT COUNT(*) FROM edition_readiness WHERE edition=2027 AND career_ready!=0
    """).fetchone()[0]:
        raise ValueError("Scope simplification cannot authorise an unverified career")
    db.executescript(SCHEMA)
    db.executemany("INSERT INTO fc27_effective_world_league_movement_scope VALUES(?,?,?,?,?,?,?,?,?)",completed)
    db.execute("""
      INSERT INTO fc27_additional_historical_source_league_closure
      VALUES(2027,'2027:ch.1',?,
        'user_delegated_no_promotion_or_relegation')
    """,("Treat Swiss Super League as closed in game; skip relegation to Challenge League and its qualification barrage.",))
    name_feeders=db.execute("""
      SELECT COUNT(*) FROM fc27_effective_named_immediate_game_feeders
    """).fetchone()[0]
    if name_feeders!=9:
        raise ValueError("Nine remaining named feeder nodes expected after broad closures")
    swiss=db.execute("""
       SELECT direct_promotions,playoff_promotions,direct_relegations,
              interdivision_playoff_places
       FROM fc27_effective_additional_movement_after_world_closure
       WHERE upper_code='2027:ch.1'
    """).fetchone()
    if swiss!=(0,0,0,0):
        raise ValueError("Swiss closed movement override failed")
    if dict((code,(country,int(tier),int(count))) for code,country,tier,count in db.execute("""
        SELECT competition_code,country,tier,active_source_clubs
        FROM fc27_2026_27_active_domestic_competitions
    """))!=before:
        raise ValueError("Original FC27 club membership modified by gameplay scope")
    if db.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("Broad close policy broke SQLite references")
    return {
      "edition":2027,"active_original_club_count":sum(x[2] for x in registered.values()),
      "closed_game_domestic_competitions":len(closes),
      "open_game_domestic_competitions":len(completed)-len(closes),
      "remaining_game_one_hop_named_feeders_without_rosters":name_feeders,
      "greece_kept_as_closed_with_source_clubs":registered["2027:gr.1"][2],
      "k_league_preserves_12_source_clubs_without_2027_growth":
          registered["2027:kr.1"][2]==12,
      "italy_and_austria_explicit_user_decisions_preserved":True,
      "swiss_barrage_only_removed_from_effective_game_rules_not_historical_sources":True,
      "original_club_and_player_records_untouched":True,
      "world_ready_to_simulate":False
    }

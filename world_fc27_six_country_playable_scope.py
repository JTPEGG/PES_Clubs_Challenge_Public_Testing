"""FC27 only: lock intended playable careers to England/Spain/France/Italy/Scotland/Portugal.

Apply after the historical source rules and the previous 32-closed game scope,
before importing feeder club names. This is an explicitly user-directed
gameplay override, not a claim about actual season regulations or proof that
PES-editable squads already exist. Never alter archival edition clubs.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

VERSION="fc27-six-country-open-playable-career-scope-v1"
COUNTRY_CODES={
    "England": ("2027:en.1","2027:en.2","2027:en.3","2027:en.4"),
    "Spain": ("2027:es.1","2027:es.2"),
    "France": ("2027:fr.1","2027:fr.2"),
    "Italy": ("2027:it.1","2027:it.2"),
    "Scotland": ("2027:sco.1",),
    "Portugal": ("2027:pt.1",),
}
PLAYABLE_CODES=frozenset(code for values in COUNTRY_CODES.values() for code in values)
NEWLY_CLOSED_CODES=frozenset({
    "2027:de.1","2027:de.2","2027:de.3",
    "2027:nl.1","2027:be.1","2027:at.1",
    "2027:tr.1","2027:pl.1","2027:ar.1"
})
SOURCE_RULES_TO_DISABLE=frozenset({"2027:nl.1","2027:be.1","2027:at.1"})
# From 7 existing dated UK/Germany/Spain edges, 2 German destinations close.
CORE_BOUNDS=(
    ("2027:en.2","2027:en.1"),
    ("2027:en.3","2027:en.2"),
    ("2027:en.4","2027:en.3"),
    ("2027:en.5","2027:en.4"),  # sourced National League immediate feeder
    ("2027:de.2","2027:de.1"),
    ("2027:de.3","2027:de.2"),
    ("2027:es.2","2027:es.1"),
)
SCHEMA="""
CREATE TABLE fc27_six_country_playable_approval(
  edition INTEGER NOT NULL CHECK(edition=2027),
  competition_code TEXT NOT NULL,
  country TEXT NOT NULL,
  original_source_club_count INTEGER NOT NULL CHECK(original_source_club_count>0),
  intended_manager_selectable INTEGER NOT NULL CHECK(intended_manager_selectable=1),
  PES_match_roster_verified INTEGER NOT NULL CHECK(PES_match_roster_verified=0),
  career_gameplay_activated INTEGER NOT NULL CHECK(career_gameplay_activated=0),
  PRIMARY KEY(edition,competition_code),
  FOREIGN KEY(edition,competition_code)
    REFERENCES fc27_effective_world_league_movement_scope(edition,competition_code)
);
CREATE TABLE fc27_newly_closed_country_scope_decisions(
  edition INTEGER NOT NULL CHECK(edition=2027),
  competition_code TEXT NOT NULL,
  previous_policy TEXT NOT NULL CHECK(previous_policy='open_pyramid'),
  effective_policy TEXT NOT NULL CHECK(effective_policy='closed'),
  reason TEXT NOT NULL,
  decision_date TEXT NOT NULL CHECK(decision_date='2026-10-21'),
  original_clubs_retained INTEGER NOT NULL CHECK(original_clubs_retained=1),
  PRIMARY KEY(edition,competition_code),
  FOREIGN KEY(edition,competition_code)
    REFERENCES fc27_effective_world_league_movement_scope(edition,competition_code)
);
CREATE TABLE fc27_effective_core_pyramid_game_boundaries(
  edition INTEGER NOT NULL CHECK(edition=2027),
  lower_code TEXT NOT NULL,
  upper_code TEXT NOT NULL,
  game_enabled INTEGER NOT NULL CHECK(game_enabled IN (0,1)),
  reason TEXT NOT NULL,
  PRIMARY KEY(edition,lower_code,upper_code)
);
CREATE VIEW fc27_intended_playable_club_candidates AS
 SELECT c.edition,c.club_key,c.club,c.starting_competition
 FROM fc27_2026_27_complete_source_competition_alignment c
 JOIN fc27_six_country_playable_approval p
  ON p.edition=c.edition AND p.competition_code=c.starting_competition;
"""

def apply_six_country_scope(db:sqlite3.Connection, path, *, strict=True):
    cfg=json.loads(Path(path).read_text(encoding="utf-8"))
    if (cfg.get("version")!=VERSION or cfg.get("edition")!=2027
        or cfg.get("career_playable_intent_not_runtime_verification") is not True
        or cfg.get("all_other_fc27_active_domestic_competitions")!=
           "closed_to_sporting_promotion_relegation_and_not_manager_selectable"):
        raise ValueError("FC27 six-country gameplay approval not confirmed")
    groups=cfg.get("open_and_intended_playable_countries")
    if not isinstance(groups,list) or len(groups)!=6:
        raise ValueError("Exactly six playable countries must be specified")
    if {x["country"]:tuple(x["competition_codes"]) for x in groups}!=COUNTRY_CODES:
        raise ValueError("Playable competition list differs from six-country user decision")
    if (set(cfg.get("recorded_new_closure_countries",[]))!=
        {"Poland","Turkey","Austria","Belgium","Argentina","Germany","Netherlands"}):
        raise ValueError("Newly closed countries not transparently recorded")
    rows={
        code:(country,int(tier),int(clubs),movement)
        for code,country,tier,clubs,movement in db.execute("""
          SELECT competition_code,country,tier,original_game_source_clubs,movement_policy
          FROM fc27_effective_world_league_movement_scope WHERE edition=2027
        """)
    }
    if len(rows)!=53 or (strict and sum(x[2] for x in rows.values())!=659):
        raise ValueError("Expected original 53/659 FC27 competition source snapshot")
    if {code for code,v in rows.items() if v[3]=="open_pyramid"} != PLAYABLE_CODES|NEWLY_CLOSED_CODES:
        raise ValueError("Unexpected previously open competition: cannot close silently")
    if {code for code,v in rows.items() if v[3]=="closed"}&PLAYABLE_CODES:
        raise ValueError("Approved playable competition previously closed")
    for country,codes in COUNTRY_CODES.items():
        for code in codes:
            if code not in rows or rows[code][0]!=country:
                raise ValueError(f"Playable code/country mismatch: {code}")
    if sum(rows[code][2] for code in PLAYABLE_CODES)!=240:
        raise ValueError("Expected 240 original FC27 clubs across six playable countries")
    original_source=db.execute("""
      SELECT COUNT(*) FROM edition_club_competitions WHERE edition=2027
    """).fetchone()[0]
    before_source=dict(db.execute("""
       SELECT club_key,starting_competition
       FROM fc27_2026_27_complete_source_competition_alignment WHERE edition=2027
    """))
    db.executescript(SCHEMA)
    db.executemany("""
        UPDATE fc27_effective_world_league_movement_scope
        SET movement_policy='closed',
            policy_basis='six_country_user_approved_gameplay_scope',
            simplification_disclosure=?
        WHERE edition=2027 AND competition_code=? AND movement_policy='open_pyramid'
    """,[
        (f"Game scope decision 21 Oct 2026: close {rows[code][0]} to sporting promotion/relegation; "
         "retain all existing FC27 clubs, players, historical rules, transfer-market "
         "availability and unaltered original domestic membership.",code)
        for code in sorted(NEWLY_CLOSED_CODES)
    ])
    if db.execute("SELECT changes()").fetchone()[0]!=1:
        # SQLite changes() tracks the last UPDATE (one row); full count checked below.
        raise ValueError("FC27 targeted closure update did not affect expected final row")
    db.executemany("""
      INSERT INTO fc27_newly_closed_country_scope_decisions VALUES(
        2027,?,'open_pyramid','closed',?,'2026-10-21',1)
    """,[(code,
         f"User's final playable-country list excludes {rows[code][0]}; "
         "no sporting movement or feeder investment in this country.")
          for code in sorted(NEWLY_CLOSED_CODES)])
    db.executemany("""
      INSERT INTO fc27_six_country_playable_approval VALUES(2027,?,?,?,1,0,0)
    """,[(code,rows[code][0],rows[code][2]) for code in sorted(PLAYABLE_CODES)])
    db.executemany("""
      INSERT INTO fc27_additional_historical_source_league_closure
      VALUES(2027,?,?,'user_delegated_no_promotion_or_relegation')
    """,[(code,
          f"Final 21 October six-country game scope supersedes earlier "
          f"{rows[code][0]} source-backed movement; historical rules retained.")
         for code in sorted(SOURCE_RULES_TO_DISABLE)])
    enabled=[]
    for lower,upper in CORE_BOUNDS:
        allowed=int(upper in PLAYABLE_CODES)
        enabled.append((2027,lower,upper,allowed,
          "six_country_open_career_pyramid" if allowed
          else "German source movement retained historically but game closed"))
    db.executemany("""
      INSERT INTO fc27_effective_core_pyramid_game_boundaries VALUES(?,?,?,?,?)
    """,enabled)
    actual=dict(db.execute("""
        SELECT movement_policy,COUNT(*)
        FROM fc27_effective_world_league_movement_scope
        WHERE edition=2027 GROUP BY movement_policy
    """))
    if actual!={"closed":41,"open_pyramid":12}:
        raise ValueError("Final game scope must be 12 open and 41 closed")
    if db.execute("""
      SELECT COUNT(*) FROM fc27_intended_playable_club_candidates
    """).fetchone()[0]!=240:
        raise ValueError("Playable manager club candidates not 240")
    if db.execute("""
      SELECT COUNT(*) FROM fc27_effective_named_immediate_game_feeders
    """).fetchone()[0]!=3:
        raise ValueError("Only Italy Serie C, France Ligue 3 and Portugal 2 may need named feeders")
    if db.execute("""
      SELECT COUNT(*) FROM fc27_effective_core_pyramid_game_boundaries
      WHERE game_enabled=1
    """).fetchone()[0]!=5:
        raise ValueError("Expected 4 English + 1 Spanish enabled core pyramid boundaries")
    for code in ("2027:at.1","2027:be.1","2027:nl.1","2027:ch.1"):
        effective=db.execute("""
          SELECT direct_promotions,playoff_promotions,direct_relegations,
                 interdivision_playoff_places
          FROM fc27_effective_additional_movement_after_world_closure
          WHERE edition=2027 AND upper_code=?
        """,(code,)).fetchone()
        if effective!=(0,0,0,0):
            raise ValueError(f"Historical country movement still active in game: {code}")
    if db.execute("""
      SELECT direct_promotions,playoff_promotions,direct_relegations
      FROM fc27_effective_additional_movement_after_world_closure
      WHERE upper_code='2027:it.1'
    """).fetchone()!=(2,1,3):
        raise ValueError("User-approved mandatory Serie B playoffs lost")
    if (db.execute("""
      SELECT COUNT(*) FROM edition_club_competitions WHERE edition=2027
    """).fetchone()[0]!=original_source or
        dict(db.execute("""
          SELECT club_key,starting_competition
          FROM fc27_2026_27_complete_source_competition_alignment WHERE edition=2027
        """))!=before_source or
        db.execute("PRAGMA foreign_key_check").fetchall()):
        raise ValueError("Game scope change altered original club associations or foreign keys")
    if db.execute("""
      SELECT COUNT(*) FROM edition_readiness WHERE edition=2027 AND career_ready!=0
    """).fetchone()[0]:
        raise ValueError("Intended selectable country does not certify playable PES files")
    return {
       "edition":2027,"intended_playable_countries":list(COUNTRY_CODES),
       "open_intended_playable_competitions":12,
       "closed_background_competitions":41,
       "original_clubs_in_intended_playable_competitions":240,
       "original_clubs_in_closed_background_competitions":419,
       "newly_closed_competition_codes":sorted(NEWLY_CLOSED_CODES),
       "newly_disabled_existing_source_rule_boundaries":sorted(SOURCE_RULES_TO_DISABLE),
       "enabled_existing_core_pyramid_boundaries":5,
       "effective_named_one_hop_feeders":3,
       "published_source_regulations_preserved":True,
       "manager_playability_is_intent_not_verified_PES_import":True,
       "original_club_and_player_records_untouched":True,
       "career_activated":False
    }

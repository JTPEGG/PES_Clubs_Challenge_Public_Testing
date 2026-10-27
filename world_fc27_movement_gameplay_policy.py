"""Explicit FC27 *gameplay* movement rules, separate from historical sources.

This module records deliberate user-approved simplifications. Real-world
regulations stay in fc27_additional_movement_boundaries, untouched. A game
rule must not be silently described as an official league rule, and it must
never activate a career or fabricate feeder clubs.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

VERSION="fc27-gameplay-movement-decisions-v1"
APPROVED={
  ("2027:it.2","2027:it.1"): (2,1,3,0),
  ("2027:at.2","2027:at.1"): (1,0,1,0),
}
SCHEMA="""
CREATE TABLE fc27_user_approved_movement_game_rules(
 edition INTEGER NOT NULL CHECK(edition=2027),
 lower_code TEXT NOT NULL,
 upper_code TEXT NOT NULL,
 country TEXT NOT NULL,
 direct_promotions INTEGER NOT NULL CHECK(direct_promotions>=0),
 playoff_promotions INTEGER NOT NULL CHECK(playoff_promotions>=0),
 direct_relegations INTEGER NOT NULL CHECK(direct_relegations>=0),
 interdivision_playoff_places INTEGER NOT NULL CHECK(interdivision_playoff_places=0),
 playoff_or_exchange_description TEXT NOT NULL,
 historical_exception_ignored TEXT NOT NULL,
 decision_source TEXT NOT NULL CHECK(decision_source='user_approved_simplification'),
 decision_date TEXT NOT NULL,
 reason TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status='gameplay_assumption_not_historical_fact'),
 career_activated INTEGER NOT NULL CHECK(career_activated=0),
 PRIMARY KEY(edition,lower_code,upper_code),
 FOREIGN KEY(edition,lower_code,upper_code)
  REFERENCES fc27_additional_movement_boundaries(edition,lower_code,upper_code)
);
CREATE VIEW fc27_effective_additional_game_movement_rules AS
 SELECT original.edition,original.lower_code,original.upper_code,
        original.country,original.lower_name,original.upper_name,
        COALESCE(game.direct_promotions,original.direct_promotions)
             AS effective_direct_promotions,
        game.playoff_promotions AS effective_playoff_promotions,
        COALESCE(game.direct_relegations,original.direct_relegations)
             AS effective_direct_relegations,
        COALESCE(game.interdivision_playoff_places,
                 original.conditional_exchange_places)
             AS effective_interdivision_playoff_places,
        COALESCE(game.playoff_or_exchange_description,
                 original.conditional_format) AS effective_playoff_description,
        CASE WHEN game.edition IS NOT NULL
             THEN 'explicit_user_approved_gameplay_assumption'
             ELSE 'staged_published_real_world_regime_not_game_approved'
             END AS effective_rule_provenance,
        original.regulation_source_url AS historical_source_url,
        game.historical_exception_ignored AS intentionally_ignored_real_world_exception,
        original.promotion_simulation_ready AS promotion_simulation_ready
 FROM fc27_additional_movement_boundaries original
 LEFT JOIN fc27_user_approved_movement_game_rules game
 ON original.edition=game.edition
    AND original.lower_code=game.lower_code
    AND original.upper_code=game.upper_code;
"""

def apply_gameplay_decisions(db:sqlite3.Connection, config_path, *, strict=True):
    config=json.loads(Path(config_path).read_text(encoding="utf-8"))
    if (config.get("version")!=VERSION or config.get("edition")!=2027
         or config.get("policy")!="game_rules_override_only_never_change_archived_real_world_regulations"):
        raise ValueError("Expected approved season-specific game policy, not real rules")
    decisions=config.get("decisions")
    if not isinstance(decisions,list) or len(decisions)!=len(APPROVED):
        raise ValueError("Missing deliberate Italian or Austrian game decision")
    actual={}
    for x in decisions:
        key=(x["lower_code"],x["upper_code"])
        if key in actual:
            raise ValueError("Duplicate game override")
        actual[key]=x
    if set(actual)!=set(APPROVED):
        raise ValueError("Only agreed Italian and Austrian overrides are authorised")
    original_rows={
      (a,b):(country,up,down,tie,fmt,source)
      for a,b,country,up,down,tie,fmt,source in db.execute("""
        SELECT lower_code,upper_code,country,direct_promotions,
               direct_relegations,conditional_exchange_places,
               conditional_format,regulation_source_url
        FROM fc27_additional_movement_boundaries WHERE edition=2027
      """)
    }
    if strict and len(original_rows)!=9:
        raise ValueError("Other FC27 staged country movement rules are absent")
    # Check the historical baseline; a new historical source must not be
    # overwritten with a stale simplifying assumption without a re-review.
    for key,(country,baseline) in {
      ("2027:it.2","2027:it.1"):("Italy",(2,3,1)),
      ("2027:at.2","2027:at.1"):("Austria",(1,1,1)),
    }.items():
        old=original_rows.get(key)
        if old is None or old[0]!=country or old[1:4]!=baseline:
            raise ValueError(f"Published source changed for {country}; re-review game override")
    before=dict(original_rows)
    records=[]
    for key,x in sorted(actual.items()):
        up=x["gameplay_direct_promotions"]
        playoffs=x["gameplay_playoff_promotions"]
        down=x["gameplay_direct_relegations"]
        tie=x["gameplay_interdivision_playoff_places"]
        if any(type(n) is not int or n<0 for n in (up,playoffs,down,tie)):
            raise ValueError("Game rule slots must be nonnegative integers")
        if (up,playoffs,down,tie)!=APPROVED[key]:
            raise ValueError("Gameplay exchange cannot silently depart from user-approved numbers")
        if up+playoffs!=down+tie:
            raise ValueError("Season-end game club exchange is not balanced")
        if (x["country"]!=original_rows[key][0] or
            x["decision_source"]!="user_approved_simplification" or
            x["decision_date"]!="2026-10-21" or
            not all(x.get(k) for k in ("game_playoff_rule","exception_ignored","rationale"))):
            raise ValueError("Unattributed or incomplete game assumption")
        if key[0]=="2027:it.2" and "3rd to 8th" not in x["game_playoff_rule"]:
            raise ValueError("Serie B game decision must always use 3rd-8th playoffs")
        if key[0]=="2027:at.2" and "No promotion/relegation match" not in x["game_playoff_rule"]:
            raise ValueError("Austria game decision must be a direct exchange")
        records.append((2027,*key,x["country"],up,playoffs,down,tie,
                        x["game_playoff_rule"],x["exception_ignored"],
                        x["decision_source"],x["decision_date"],x["rationale"],
                        "gameplay_assumption_not_historical_fact",0))
    db.executescript(SCHEMA)
    db.executemany(
      "INSERT INTO fc27_user_approved_movement_game_rules VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
      records)
    current={
      (a,b):(country,up,down,tie,fmt,source)
      for a,b,country,up,down,tie,fmt,source in db.execute("""
        SELECT lower_code,upper_code,country,direct_promotions,
               direct_relegations,conditional_exchange_places,
               conditional_format,regulation_source_url
        FROM fc27_additional_movement_boundaries WHERE edition=2027
      """)
    }
    if current!=before:
        raise ValueError("Gameplay policy unexpectedly modified historical movement sources")
    if db.execute(
        "SELECT COUNT(*) FROM edition_readiness WHERE edition=2027 AND career_ready!=0"
    ).fetchone()[0]:
        raise ValueError("Game assumption cannot enable historical career until world is ready")
    if db.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("Game overrides contain invalid original source foreign keys")
    return {
       "edition":2027,
       "explicitly_logged_gameplay_assumptions":len(records),
       "italy_serie_b_playoff_always_used":True,
       "austria_direct_exchange_one_up_one_down":True,
       "source_regulations_preserved":True,
       "balanced_exchange_rules":True,
       "no_new_feeder_clubs_created":True,
       "career_activated":False
    }

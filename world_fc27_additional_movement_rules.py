"""FC27 2026/27: staged other-country movement edges, source-first and fail-closed.

All nine regulations are 2026/27-specific. Their existing FC27 source club
registrations must not be altered. A second-tier *name* is not an invented
club pool; if its game clubs are not present it remains an unpopulated,
non-playable, immediate feeder, and no career promotion is authorised.
"""
from __future__ import annotations

import json
import sqlite3
from urllib.parse import urlparse
from pathlib import Path

EDITION=2027
VERSION="fc27-additional-season-movement-regimes-v1"
SOURCE_HOSTS=frozenset({
    "www.lfp.fr","www.fff.fr","www.proleague.be","spfl.co.uk",
    "www.knvb.nl","www.ligaportugal.pt","sfl.ch","sport.sky.it",
    "www.bundesliga.at",
})
EXPECTED={
    ("2027:fr.2","2027:fr.1"),
    ("2027:fr.3","2027:fr.2"),
    ("2027:be.2","2027:be.1"),
    ("2027:sco.2","2027:sco.1"),
    ("2027:nl.2","2027:nl.1"),
    ("2027:pt.2","2027:pt.1"),
    ("2027:ch.2","2027:ch.1"),
    ("2027:it.2","2027:it.1"),
    ("2027:at.2","2027:at.1"),
}
SCHEMA="""
CREATE TABLE fc27_extra_movement_feeder_nodes(
  edition INTEGER NOT NULL CHECK(edition=2027),
  competition_code TEXT NOT NULL,
  country TEXT NOT NULL,
  tier INTEGER NOT NULL CHECK(tier>1),
  name TEXT NOT NULL,
  source_status TEXT NOT NULL
     CHECK(source_status='published_immediate_feeder_name_without_original_squads'),
  club_roster_verified INTEGER NOT NULL CHECK(club_roster_verified=0),
  PRIMARY KEY(edition,competition_code)
);
CREATE TABLE fc27_additional_movement_boundaries(
  edition INTEGER NOT NULL CHECK(edition=2027),
  lower_code TEXT NOT NULL,
  upper_code TEXT NOT NULL,
  country TEXT NOT NULL,
  lower_name TEXT NOT NULL,
  upper_name TEXT NOT NULL,
  direct_promotions INTEGER NOT NULL CHECK(direct_promotions>=0),
  direct_relegations INTEGER NOT NULL CHECK(direct_relegations>=0),
  conditional_exchange_places INTEGER NOT NULL
     CHECK(conditional_exchange_places BETWEEN 0 AND 1),
  conditional_format TEXT NOT NULL,
  regulation_source_url TEXT NOT NULL,
  rule_status TEXT NOT NULL,
  league_specific_exceptions TEXT NOT NULL,
  lower_membership_status TEXT NOT NULL,
  playable_2027 INTEGER NOT NULL CHECK(playable_2027=0),
  promotion_simulation_ready INTEGER NOT NULL CHECK(promotion_simulation_ready=0),
  PRIMARY KEY(edition,lower_code,upper_code)
);
CREATE VIEW fc27_mapped_additional_promotion_routes AS
 SELECT * FROM fc27_additional_movement_boundaries WHERE edition=2027;
"""

def stage(db:sqlite3.Connection, config_path, *, strict=True):
    cfg=json.loads(Path(config_path).read_text(encoding="utf-8"))
    if cfg.get("edition")!=EDITION or cfg.get("version")!=VERSION:
        raise ValueError("Expected genuine original FC27 season 2026/27 regulation")
    rules=cfg.get("rules")
    if not isinstance(rules,list) or len(rules)!=len(EXPECTED):
        raise ValueError("Expected exactly nine individually documented country boundaries")
    if {(x["lower_code"],x["upper_code"]) for x in rules}!=EXPECTED:
        raise ValueError("Unexpected, duplicate, or missing FC27 domestic boundary")
    registered={}
    for code,country,tier,name,number in db.execute("""
        SELECT competition_code,country,tier,name,active_source_clubs
        FROM fc27_2026_27_active_domestic_competitions
    """):
        registered[code]=(country,int(tier),name,int(number))
    if strict and (len(registered)!=53 or sum(v[3] for v in registered.values())!=659):
        raise ValueError("Edition source club roster has drifted")
    fixture={
        code:(country,int(tier),name)
        for code,country,tier,name in db.execute("""
        SELECT code,country,tier,name FROM competition_seasons WHERE edition=2027
    """)}
    db.executescript(SCHEMA)
    seen_feeders={}
    saved=[]
    for r in rules:
        lower,upper=r["lower_code"],r["upper_code"]
        country=r["country"]
        if upper not in registered:
            raise ValueError(f"Unknown domestic destination {upper}")
        if lower in registered:
            low=registered[lower]
            low_status="original_2027_FC27_clubs_in_competition"
        elif lower in fixture:
            low=(*fixture[lower],0)
            low_status="independently_dated_one_hop_nonplayable_feeder"
        else:
            low=(country,registered[upper][1]+1,r["lower_name"],0)
            low_status="published_immediate_feeder_name_no_club_pool"
            if lower in seen_feeders and seen_feeders[lower]!=low:
                raise ValueError("Feeder source competition contradiction")
            seen_feeders[lower]=low
        high=registered[upper]
        if (low[0]!=country or high[0]!=country or
            high[1]+1!=low[1] or
            not lower.startswith("2027:") or not upper.startswith("2027:")):
            raise ValueError("Country/tier/edition boundary mismatch")
        if low[3] and low[2]!=r["lower_name"]:
            # Different official naming may exist, but never silently relabel.
            raise ValueError("FC27 game lower division name conflicts with official tier")
        if not all(type(r[x])==int and r[x]>=0 for x in
               ("direct_promotions","direct_relegations","conditional_exchange_places")):
            raise ValueError("Movement slots must be explicitly sourced integers")
        if r["conditional_exchange_places"]>1:
            raise ValueError("Unsupported unproven multi-team conditional tie")
        if not (r["conditional_format"] and r["league_specific_exceptions"]):
            raise ValueError("Cannot erase important conditional promotion cases")
        parsed=urlparse(r["source_url"])
        if parsed.scheme!="https" or parsed.hostname not in SOURCE_HOSTS:
            raise ValueError("Rule reference must come from a checked source")
        if r["rule_status"] not in (
            "season_specific_published_rule",
            "2026_27_secondary_source_confirmed_official_exceptions_pending"):
            raise ValueError("No unsourced or invented movement regime")
        if r["complete_feeder_club_identity_verified"] or r["career_activated"]:
            raise ValueError("Cannot certify feeder clubs or start a career from rule template")
        saved.append((
            EDITION,lower,upper,country,r["lower_name"],r["upper_name"],
            r["direct_promotions"],r["direct_relegations"],
            r["conditional_exchange_places"],r["conditional_format"],
            r["source_url"],r["rule_status"],r["league_specific_exceptions"],
            low_status,0,0
        ))
    db.executemany("INSERT INTO fc27_additional_movement_boundaries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",saved)
    db.executemany("INSERT INTO fc27_extra_movement_feeder_nodes VALUES(?,?,?,?,?,?,0)",[
       (EDITION,code,v[0],v[1],v[2],
        "published_immediate_feeder_name_without_original_squads")
       for code,v in sorted(seen_feeders.items())
    ])
    if db.execute("""
        SELECT COUNT(*) FROM edition_readiness WHERE edition=2027 AND career_ready!=0
    """).fetchone()[0]:
        raise ValueError("Source regime cannot enable an unverified career")
    if db.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("New dated FC27 rules broke foreign-key integrity")
    return {
        "edition":EDITION,"additional_2026_27_movements":len(saved),
        "first_time_named_one_hop_feeder_competitions":len(seen_feeders),
        "existing_2027_club_divisions_reused":sum(
            r[-3]=="original_2027_FC27_clubs_in_competition" for r in saved),
        "external_dated_feeder_divisions_reused":sum(
            r[-3]=="independently_dated_one_hop_nonplayable_feeder" for r in saved),
        "rule_based_conditional_exchanges":sum(r[8]>0 for r in saved),
        "complete_feeder_roster_verification":False,
        "original_club_records_modified":False,
        "career_activated":False,
    }

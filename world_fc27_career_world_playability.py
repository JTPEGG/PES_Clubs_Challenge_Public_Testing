"""FC27 career-world planning: preserve 659 game clubs; register genuine feeders.

Staging ONLY: original source club squads are not yet PES-editable match squads,
and feeder clubs from official lists have no imported player roster. Closed
leagues remain available for transfer and job-market consideration while
their sporting promotion/relegation is disabled by a separate policy.
"""
from __future__ import annotations

import json
import sqlite3
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

EDITION=2027
VERSION="fc27-one-hop-official-2026-27-feeder-memberships-v1"
OFFICIAL_SOURCES={
  "2027:fr.3":"https://www.fff.fr/article/17022-le-calendrier-2026-2027-est-servi.html",
  "2027:be.2":"https://www.proleague.be/nieuws/kalender-2026-2027-nieuwkomers-treffen-elkaar-meteen-in-challenger-pro-league",
  "2027:it.3":"https://www.seriec.com/clubs",
}
EXPECTED={"2027:fr.3":18,"2027:be.2":15,"2027:it.3":60}
EXPECTED_RESERVES={"2027:fr.3":0,"2027:be.2":4,"2027:it.3":3}
SCHEMA="""
CREATE TABLE fc27_career_world_clubs (
  edition INTEGER NOT NULL CHECK(edition=2027),
  club_key TEXT NOT NULL,
  original_club TEXT NOT NULL,
  competition_code TEXT NOT NULL,
  competition_mode TEXT NOT NULL CHECK(
    competition_mode IN ('open_league_season_candidate','closed_background_world')),
  transfer_market_candidate INTEGER NOT NULL CHECK(transfer_market_candidate=1),
  manager_job_market_candidate INTEGER NOT NULL CHECK(manager_job_market_candidate=1),
  playable_in_PES_verified INTEGER NOT NULL CHECK(playable_in_PES_verified=0),
  domestic_season_schedule_activated INTEGER NOT NULL CHECK(domestic_season_schedule_activated=0),
  PRIMARY KEY(edition,club_key),
  FOREIGN KEY(edition,club_key) REFERENCES edition_club_competitions(edition,club_key)
);
CREATE TABLE fc27_sourced_real_one_hop_feeder_clubs (
  edition INTEGER NOT NULL CHECK(edition=2027),
  feeder_code TEXT NOT NULL,
  real_club_name TEXT NOT NULL,
  regional_group TEXT NOT NULL,
  reserve_or_youth INTEGER NOT NULL CHECK(reserve_or_youth IN (0,1)),
  source_url TEXT NOT NULL,
  source_evidence TEXT NOT NULL CHECK(
    source_evidence='league_or_federation_published_2026_27_competition_membership'),
  original_FC27_game_club_record INTEGER NOT NULL CHECK(original_FC27_game_club_record=0),
  PES_player_squad_imported INTEGER NOT NULL CHECK(PES_player_squad_imported=0),
  game_promotion_registered INTEGER NOT NULL CHECK(game_promotion_registered=0),
  PRIMARY KEY(edition,feeder_code,real_club_name)
);
CREATE TABLE fc27_feeder_pool_readiness (
  edition INTEGER NOT NULL CHECK(edition=2027),
  feeder_code TEXT NOT NULL,
  feeder_country TEXT NOT NULL,
  feeder_tier INTEGER NOT NULL,
  feeder_name TEXT NOT NULL,
  published_real_club_names INTEGER NOT NULL CHECK(published_real_club_names>=0),
  named_pool_source_status TEXT NOT NULL,
  eligible_player_squads_for_PES INTEGER NOT NULL CHECK(eligible_player_squads_for_PES=0),
  season_end_promotion_enabled INTEGER NOT NULL CHECK(season_end_promotion_enabled=0),
  PRIMARY KEY(edition,feeder_code)
);
CREATE VIEW fc27_career_world_gameplay_scope AS
 SELECT s.edition,s.competition_code,s.country,s.name,s.original_game_source_clubs,
        s.movement_policy,
        CASE WHEN s.movement_policy='open_pyramid' THEN 'simulated_league_candidate'
             ELSE 'passive_background_no_sporting_movement'
        END AS season_role
 FROM fc27_effective_world_league_movement_scope s;
"""

def namekey(name):
    return "".join(ch for ch in unicodedata.normalize("NFKD",name.casefold())
                   if ch.isalnum() and not unicodedata.combining(ch))

def stage(db:sqlite3.Connection, config_path, *, strict=True):
    config=json.loads(Path(config_path).read_text(encoding="utf-8"))
    if (config.get("version")!=VERSION or config.get("edition")!=EDITION or
        config.get("scope")!="actual_named_clubs_only_not_playable_squads"):
        raise ValueError("Wrong feeder source edition or unsupported roster provenance")
    groups=config.get("groups")
    if not isinstance(groups,list) or len(groups)!=3 or {x["feeder_competition_code"] for x in groups}!=set(EXPECTED):
        raise ValueError("Only three reviewed official 2026/27 one-hop feeder lists may be staged")
    original=db.execute("""
       SELECT a.club_key,a.club,a.starting_competition,s.movement_policy
       FROM fc27_2026_27_complete_source_competition_alignment a
       JOIN fc27_effective_world_league_movement_scope s
         ON s.edition=a.edition AND s.competition_code=a.starting_competition
       WHERE a.edition=2027
    """).fetchall()
    if len(original)!=659 or len({r[0] for r in original})!=659:
        raise ValueError("FC27 659-source-club identity changed")
    league_scope=db.execute("""
       SELECT movement_policy,count(*),sum(original_game_source_clubs)
       FROM fc27_effective_world_league_movement_scope
       WHERE edition=2027 GROUP BY movement_policy
    """).fetchall()
    if dict((m,(n,clubs)) for m,n,clubs in league_scope)!={
        "closed":(32,249),"open_pyramid":(21,410)}:
        raise ValueError("FC27 21-open 32-closed career-world scope changed")
    named={
      code:(country,int(tier),name)
      for _,code,country,tier,name,_ in db.execute("""
        SELECT * FROM fc27_effective_named_immediate_game_feeders WHERE edition=2027
      """)
    }
    if len(named)!=9:
        raise ValueError("Effective feeder name scope changed")
    original_names={namekey(name) for key,name,code,mode in original}
    if db.execute("""
       SELECT COUNT(*) FROM edition_readiness WHERE edition=2027 AND career_ready!=0
    """).fetchone()[0]:
        raise ValueError("Incomplete source feeder squads must not unlock careers")
    verified=[]
    per_group={}
    for cohort in groups:
        code=cohort["feeder_competition_code"]
        clubs=cohort["clubs"]
        if (code not in named or cohort["country"]!=named[code][0] or
            cohort["competition"]!=named[code][2] or
            cohort["edition"]!=2027 or cohort["season"]!="2026-27" or
            cohort["source_official_url"]!=OFFICIAL_SOURCES[code] or
            urlparse(cohort["source_official_url"]).scheme!="https" or
            cohort["original_game_player_squad_imported"] is not False or
            len(clubs)!=EXPECTED[code] or cohort["roster_count"]!=len(clubs)):
            raise ValueError("Official published feeder metadata inconsistent")
        keys=[namekey(x["club_name"]) for x in clubs]
        if len(set(keys))!=len(keys) or any(not x for x in keys):
            raise ValueError("Official feeder name duplicated or blank")
        if set(keys)&original_names:
            raise ValueError("A feeder team already exists in a different original game division; review its identity")
        reserve=sum(x["reserve_or_youth"] is True for x in clubs)
        if reserve!=EXPECTED_RESERVES[code]:
            raise ValueError("Reserve/team eligibility classification was changed")
        groupsizes=Counter(x["regional_group"] for x in clubs)
        if code=="2027:it.3":
            if groupsizes!={"A":20,"B":20,"C":20}:
                raise ValueError("Serie C must preserve three distinct real group memberships")
        elif groupsizes!={"national":len(clubs)}:
            raise ValueError("Cannot invent regional groups for national league")
        for item in clubs:
            if type(item["reserve_or_youth"]) is not bool:
                raise ValueError("Reserve classification must be explicit")
            verified.append((2027,code,item["club_name"],item["regional_group"],
                int(item["reserve_or_youth"]),cohort["source_official_url"],
                "league_or_federation_published_2026_27_competition_membership",
                0,0,0))
        per_group[code]=len(clubs)
    if len(verified)!=93:
        raise ValueError("Officially named feeder club count changed")
    db.executescript(SCHEMA)
    db.executemany("""
      INSERT INTO fc27_career_world_clubs VALUES(?,?,?,?,?,1,1,0,0)
    """,[(2027,key,name,competition,
          "open_league_season_candidate" if mode=="open_pyramid"
          else "closed_background_world") for key,name,competition,mode in original])
    db.executemany("""
      INSERT INTO fc27_sourced_real_one_hop_feeder_clubs
      VALUES(?,?,?,?,?,?,?,?,?,?)
    """,verified)
    db.executemany("""
      INSERT INTO fc27_feeder_pool_readiness VALUES(?,?,?,?,?,?,?,0,0)
    """,[(2027,code,country,tier,name,per_group.get(code,0),
         "official_published_2026_27_club_pool" if code in per_group
         else "name_only_not_eligible_for_promotion")
         for code,(country,tier,name) in sorted(named.items())])
    original_count=db.execute(
        "SELECT COUNT(*) FROM edition_club_competitions WHERE edition=2027"
    ).fetchone()[0]
    if original_count!=659 or db.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("Feeder sourcing damaged immutable original FC27 clubs")
    return {
      "edition":2027,"all_original_clubs_with_explicit_career_world_role":len(original),
      "open_pyramid_season_candidate_clubs":410,
      "closed_background_world_clubs":249,
      "manager_job_market_source_clubs_retained":659,
      "official_real_feeder_clubs_now_named":len(verified),
      "complete_real_feeder_membership_pools":len(per_group),
      "other_named_feeders_lacking_real_club_pools":len(named)-len(per_group),
      "reserve_or_youth_clubs_explicitly_tagged":sum(r[4] for r in verified),
      "game_fixtures_or_PES_player_squads_unlocked":False,
      "active_game_promotion_eligible_feeder_squads":0,
      "original_players_and_clubs_untouched":True,
      "other_editions_untouched":True,
    }

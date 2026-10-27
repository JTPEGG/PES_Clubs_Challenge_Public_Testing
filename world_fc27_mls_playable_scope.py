"""Keep MLS selectable with its actual closed-pyramid, two-conference structure.

A playable competition need not have promotion/relegation. This module runs
after the eight European country choices; it *does not* relabel MLS an open
pyramid or invent players/FC27 EA club IDs. Exact official 2026 conference
names remain separately sourced until original FC27 names are reconciled.
"""
from __future__ import annotations
import json
import sqlite3
from collections import Counter
from pathlib import Path

MLS="2027:us.mls"
VERSION="fc27-mls-playable-closed-pyramid-v2"
SCHEMA="""
CREATE TABLE fc27_mls_playable_closed_league_approval (
  edition INTEGER NOT NULL CHECK(edition=2027),
  competition_code TEXT NOT NULL CHECK(competition_code='2027:us.mls'),
  original_source_clubs INTEGER NOT NULL CHECK(original_source_clubs=30),
  intended_manager_selectable INTEGER NOT NULL CHECK(intended_manager_selectable=1),
  no_promotion_or_relegation INTEGER NOT NULL CHECK(no_promotion_or_relegation=1),
  PES_match_roster_verified INTEGER NOT NULL CHECK(PES_match_roster_verified=0),
  season_schedule_activated INTEGER NOT NULL CHECK(season_schedule_activated=0),
  PRIMARY KEY(edition,competition_code),
  FOREIGN KEY(edition,competition_code)
   REFERENCES fc27_effective_world_league_movement_scope(edition,competition_code)
);
CREATE TABLE fc27_mls_official_conference_membership (
  edition INTEGER NOT NULL CHECK(edition=2027),
  source_calendar_year INTEGER NOT NULL CHECK(source_calendar_year=2026),
  official_club_name TEXT NOT NULL,
  conference TEXT NOT NULL CHECK(conference IN ('Eastern','Western')),
  source_url TEXT NOT NULL,
  mapped_original_game_club_key TEXT NOT NULL,
  PRIMARY KEY(edition,official_club_name),
  UNIQUE(edition,mapped_original_game_club_key),
  FOREIGN KEY(edition,mapped_original_game_club_key)
    REFERENCES edition_club_competitions(edition,club_key)
);
CREATE TABLE fc27_mls_calendar_and_playoff_policy (
  edition INTEGER NOT NULL CHECK(edition=2027),
  competition_code TEXT NOT NULL CHECK(competition_code='2027:us.mls'),
  conference_team_count INTEGER NOT NULL CHECK(conference_team_count=15),
  team_count INTEGER NOT NULL CHECK(team_count=30),
  regular_season_games_per_team INTEGER NOT NULL CHECK(regular_season_games_per_team=34),
  home_games INTEGER NOT NULL CHECK(home_games=17),
  away_games INTEGER NOT NULL CHECK(away_games=17),
  conference_matches INTEGER NOT NULL CHECK(conference_matches=28),
  cross_conference_matches INTEGER NOT NULL CHECK(cross_conference_matches=6),
  conference_playoff_qualifiers INTEGER NOT NULL CHECK(conference_playoff_qualifiers=9),
  round_one_best_of INTEGER NOT NULL CHECK(round_one_best_of=3),
  cup_winner_via_knockout INTEGER NOT NULL CHECK(cup_winner_via_knockout=1),
  league_standings_and_playoffs_simulator_activated INTEGER NOT NULL
       CHECK(league_standings_and_playoffs_simulator_activated=0),
  PRIMARY KEY(edition,competition_code)
);
CREATE VIEW fc27_effective_manager_selectable_competitions AS
 SELECT edition,competition_code,country,
        'open_pyramid' AS playing_format
 FROM fc27_eight_country_playable_approval
 UNION ALL
 SELECT p.edition,p.competition_code,s.country,
        'closed_mls_conference_and_cup_playoffs' AS playing_format
 FROM fc27_mls_playable_closed_league_approval p
 JOIN fc27_effective_world_league_movement_scope s
   ON s.edition=p.edition AND s.competition_code=p.competition_code;
CREATE VIEW fc27_effective_manager_selectable_original_clubs AS
 SELECT a.edition,a.club_key,a.club,a.starting_competition,e.playing_format
 FROM fc27_2026_27_complete_source_competition_alignment a
 JOIN fc27_effective_manager_selectable_competitions e
   ON e.edition=a.edition AND e.competition_code=a.starting_competition;
"""
def stage_mls(db:sqlite3.Connection, path, *, strict=True):
    cfg=json.loads(Path(path).read_text(encoding="utf-8"))
    if (cfg.get("version")!=VERSION or cfg.get("edition")!=2027 or
        cfg.get("calendar_season")!=2026 or cfg.get("game_competition_code")!=MLS or
        cfg.get("manager_selectable") is not True or
        cfg.get("sporting_promotion_or_relegation") is not False or
        cfg.get("league_fixture_engine_activated") is not False or
        cfg.get("PES_gameplay_player_squads_validated") is not False):
        raise ValueError("MLS selectable closed-league source policy not confirmed")
    r=db.execute("""
      SELECT s.country,s.original_game_source_clubs,s.movement_policy,
             COUNT(a.club_key)
      FROM fc27_effective_world_league_movement_scope s
      JOIN fc27_2026_27_complete_source_competition_alignment a
        ON a.edition=s.edition AND a.starting_competition=s.competition_code
      WHERE s.edition=2027 AND s.competition_code=?
      GROUP BY s.country,s.original_game_source_clubs,s.movement_policy
    """,(MLS,)).fetchone()
    if r is None or r[1:]!=(30,"closed",30):
        raise ValueError("Original FC27 MLS source club group must remain 30 and closed for movement")
    if db.execute("""
        SELECT COUNT(*) FROM season_non_pyramid_formats
        WHERE edition=2027 AND competition_code=? AND direct_promotions=0
          AND playoff_promotions=0 AND direct_relegations=0
    """,(MLS,)).fetchone()[0]!=1:
        raise ValueError("MLS historical closed pyramid/source evidence missing")
    fmt=cfg["competition_format"]
    expected={
        "conference_team_count":15,"team_count":30,"regular_season_games_per_team":34,
        "home_games":17,"away_games":17,"conference_matches":28,
        "cross_conference_matches":6,"conference_playoff_qualifiers":9,
        "round_one_best_of":3,
    }
    if any(fmt.get(k)!=v or type(fmt.get(k)) is not int for k,v in expected.items()):
        raise ValueError("Official 2026 MLS conference/regular-season rules changed")
    if (fmt.get("direct_first_round_seeds")!="1-7" or
        fmt.get("wild_card_seeds")!="8-9" or
        not all(fmt.get(k) is True for k in
            ("wild_card_single_leg","conference_semifinal_one_leg",
             "conference_final_one_leg","mls_cup_final_one_leg"))):
        raise ValueError("Official 2026 MLS postseason rules or bracket differ")
    entries=cfg.get("official_clubs",[])
    if (len(entries)!=30 or len({x["name"].casefold() for x in entries})!=30 or
       Counter(x["conference"] for x in entries)!={"Eastern":15,"Western":15} or
       any(not x["name"].strip() for x in entries) or
       cfg["source"]!="https://bracket.mlssoccer.com/league-reports/competition-guidelines/"):
        raise ValueError("Expected 30 named official MLS clubs across 15/15 conferences")
    source_clubs=dict(db.execute("""
       SELECT club,club_key FROM fc27_2026_27_complete_source_competition_alignment
       WHERE edition=2027 AND starting_competition=?
    """,(MLS,)))
    if len(source_clubs)!=30:
        raise ValueError("MLS source club names must be one-to-one")
    matching=[]
    for x in entries:
        original_name=x.get("original_FC27_club_name")
        if original_name not in source_clubs:
            raise ValueError(f"MLs original FC27 club name missing: {original_name}")
        matching.append((x["name"],x["conference"],cfg["source"],source_clubs[original_name]))
    if len({m[-1] for m in matching})!=30:
        raise ValueError("FC27 MLS official to original game identity mapping is not one-to-one")
    db.executescript(SCHEMA)
    db.execute("""
      INSERT INTO fc27_mls_playable_closed_league_approval VALUES(2027,?,30,1,1,0,0)
    """,(MLS,))
    db.executemany("""
      INSERT INTO fc27_mls_official_conference_membership VALUES(2027,2026,?,?,?,?)
    """,matching)
    db.execute("""
      INSERT INTO fc27_mls_calendar_and_playoff_policy
      VALUES(2027,?,15,30,34,17,17,28,6,9,3,1,0)
    """,(MLS,))
    if db.execute("""
       SELECT COUNT(DISTINCT mapped_original_game_club_key)
       FROM fc27_mls_official_conference_membership
    """).fetchone()[0]!=30:
        raise ValueError("All source FC27 MLS club IDs must be uniquely crosswalked")
    if db.execute("""
       SELECT COUNT(*) FROM fc27_effective_manager_selectable_competitions
    """).fetchone()[0]!=17:
        raise ValueError("Exactly 16 European divisions plus playable closed MLS expected")
    if db.execute("""
       SELECT COUNT(*) FROM fc27_effective_manager_selectable_original_clubs
    """).fetchone()[0]!=344:
        raise ValueError("Expected 314 European FC27 clubs plus 30 MLS clubs")
    if db.execute("""
       SELECT movement_policy FROM fc27_effective_world_league_movement_scope
       WHERE edition=2027 AND competition_code=?
    """,(MLS,)).fetchone()!=("closed",):
        raise ValueError("MLS must never be recategorised as promotion/relegation league")
    if db.execute("""
       SELECT COUNT(*) FROM edition_readiness WHERE edition=2027 AND career_ready!=0
    """).fetchone()[0] or db.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("Playable intent cannot activate unverified world or break identity records")
    return {
       "edition":2027,"intended_playable_nations_including_mls":9,
       "intended_playable_competition_codes":17,
       "open_promotion_relegation_divisions":16,
       "closed_mls_playable_divisions":1,
       "intended_selectable_original_game_clubs":344,
       "other_original_world_clubs":315,
       "mls_2026_source_members":30,
       "mls_eastern_clubs":15,"mls_western_clubs":15,
       "mls_regular_season_matches_per_club":34,
       "real_world_source_club_name_crosswalk_certified":True,
       "mls_matches_and_player_rosters_ready":False,
       "promotion_relegation_changes_for_mls":0
    }

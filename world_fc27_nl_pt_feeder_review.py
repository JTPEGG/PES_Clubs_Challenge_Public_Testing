"""Register Dutch/Portuguese 2026/27 real club feeder identities, no PES squads.

Runs after 93 earlier French, Belgian and Italian named feeder records have
been persisted. These are source club *identities*, not playable new squads.
Dutch list: VI 2026/27 participants crosschecked against official KNVB fixtures.
Portugal list: Liga Portugal 2026/27 official second-tier standings.
"""
from __future__ import annotations
import json
import sqlite3
import unicodedata
from pathlib import Path
from collections import Counter

VERSION="fc27-nl-pt-reviewed-2026-27-named-feeders-v1"
EXPECTED={
 "2027:nl.2":(20,4,"Netherlands","Eerste Divisie",
    "https://www.vi.nl/competities/eerste-divisie/over",
    "dated_season_full_member_list_secondary_source_crosschecked_against_knvb"),
 "2027:pt.2":(18,3,"Portugal","Liga Portugal 2",
    "https://www.ligaportugal.pt/competition/912/liga-portugal-meu-super/round/20262027?stat=players&tab=stats&type=50",
    "official_2026_27_professional_league_standings_18_members")
}

def norm(s):
    return "".join(c for c in unicodedata.normalize("NFKD",s.casefold())
                   if c.isalnum() and not unicodedata.combining(c))

def stage(db:sqlite3.Connection,path,*,strict=True):
    cfg=json.loads(Path(path).read_text(encoding="utf-8"))
    if (cfg.get("version")!=VERSION or cfg.get("edition")!=2027 or
        cfg.get("source_evidence_not_PES_player_squads") is not True):
        raise ValueError("Wrong dated feeder identity review")
    groups={g["feeder_competition_code"]:g for g in cfg.get("groups",[])}
    if len(cfg.get("groups",[]))!=2 or set(groups)!=set(EXPECTED):
        raise ValueError("Expected Dutch and Portuguese feeder source groups only")
    existing=db.execute("""
      SELECT COUNT(*) FROM fc27_sourced_real_one_hop_feeder_clubs WHERE edition=2027
    """).fetchone()[0]
    if existing!=93:
        raise ValueError("Original French Belgian and Italian feeder evidence changed")
    original_clubs={norm(name) for (name,) in db.execute("""
      SELECT club FROM fc27_2026_27_complete_source_competition_alignment WHERE edition=2027
    """)}
    stored={norm(name) for (name,) in db.execute("""
       SELECT real_club_name FROM fc27_sourced_real_one_hop_feeder_clubs WHERE edition=2027
    """)}
    rows=[]
    for code,(total,reserves,country,league,url,status) in EXPECTED.items():
        g=groups[code]
        if (g.get("edition")!=2027 or g.get("season")!="2026-27" or
            g.get("country")!=country or g.get("competition")!=league or
            g.get("source_official_url")!=url or
            g.get("source_status")!=status or g.get("roster_count")!=total or
            g.get("original_game_player_squad_imported") is not False or
            len(g.get("clubs",[]))!=total):
            raise ValueError(f"Changed {code} season-specific feeder membership source")
        if code=="2027:nl.2" and g.get("secondary_confirmation_url")!=(
           "https://www.knvb.nl/nieuws/betaald-voetbal/competitiezaken/71918/definitief-competitieprogramma-202627-vastgesteld"):
            raise ValueError("2026/27 Dutch fixture crosscheck missing")
        if db.execute("""
          SELECT COUNT(*) FROM fc27_feeder_pool_readiness
          WHERE edition=2027 AND feeder_code=? AND published_real_club_names=0
        """,(code,)).fetchone()[0]!=1:
            raise ValueError("Lower feeder is not active and awaiting real names")
        namekeys=[norm(x["club_name"]) for x in g["clubs"]]
        if (len(set(namekeys))!=total or any(not x for x in namekeys) or
            len(set(namekeys)&stored)>0):
            raise ValueError("Invalid or duplicate feeder club names")
        # Fuzzy homonyms in original season should be independently reviewed
        # rather than treated as a new FC27 club without evidence.
        if set(namekeys)&original_clubs:
            raise ValueError("Feeder identity collides with existing FC27 source club")
        if (sum(x["reserve_or_youth"] is True for x in g["clubs"])!=reserves
            or any(x["regional_group"]!="national" or
                   type(x["reserve_or_youth"]) is not bool for x in g["clubs"])):
            raise ValueError("Reserve eligibility and one-national-division source drift")
        evidence=("season_named_clubs_secondary_source_crosschecked_with_federation"
                  if code=="2027:nl.2" else
                  "league_or_federation_published_2026_27_competition_membership")
        rows.extend((2027,code,x["club_name"],"national",int(x["reserve_or_youth"]),
                     url,evidence,0,0,0) for x in g["clubs"])
        db.execute("""
          UPDATE fc27_feeder_pool_readiness
          SET published_real_club_names=?, named_pool_source_status=?
          WHERE edition=2027 AND feeder_code=?
        """,(total,status,code))
    db.executemany("""
      INSERT INTO fc27_sourced_real_one_hop_feeder_clubs
      VALUES(?,?,?,?,?,?,?,?,?,?)
    """,rows)
    if db.execute("""
       SELECT COUNT(*) FROM fc27_sourced_real_one_hop_feeder_clubs WHERE edition=2027
    """).fetchone()[0]!=131:
        raise ValueError("Expected all 131 historical named feeder club identities")
    if db.execute("""
       SELECT COUNT(*) FROM fc27_feeder_pool_readiness
       WHERE edition=2027 AND published_real_club_names>0
    """).fetchone()[0]!=4:
        raise ValueError("Four named game-open lower feeders should have real clubs")
    if db.execute("""
       SELECT COUNT(*) FROM fc27_feeder_pool_readiness
       WHERE eligible_player_squads_for_PES!=0 OR season_end_promotion_enabled!=0
    """).fetchone()[0] or db.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("Source names must not register playable PES teams")
    return {
      "edition":2027,"newly_sourced_named_feeder_clubs":38,
      "dutch_first_division_2026_27_clubs":20,
      "portuguese_second_division_2026_27_clubs":18,
      "dutch_reserve_side_names":4,"portuguese_reserve_side_names":3,
      "total_source_named_feeder_clubs_retained_including_closed_belgium":131,
      "active_four_game_feeder_club_names":116,
      "open_feeders_without_real_named_club_members":0,
      "player_squads_imported_for_feeders":0,
      "career_activated":False
    }

"""FC27 source-dated third/fourth-tier Spanish/German immediate regional feeder pools.

One level only: two 2026/27 Primera Federación groups, five Regionalliga
groups. Source club identities are NOT PES roster / player identities. Do not
invent reserve-player ratings, promote unregistered clubs, or append another
tier below these regions.
"""
from __future__ import annotations
import json,sqlite3,unicodedata
from pathlib import Path
from collections import Counter

EDITION=2027
VERSION="fc27-2026-27-real-regional-one-hop-feeders-v1"
SPAIN={"1":20,"2":20}
GERMANY={"Nord":18,"Nordost":18,"West":18,"Südwest":18,"Bayern":19}
SOURCES={
 "1":"https://rfef.es/es/noticias/aprobados-los-grupos-de-primera-federacion-para-la-temporada-202627",
 "2":"https://rfef.es/es/noticias/aprobados-los-grupos-de-primera-federacion-para-la-temporada-202627",
 "Nord":"https://datencenter.dfb.de/en/data-center/107/current/fair-play",
 "Nordost":"https://www.nofv-online.de/index.php/nofv-vereine.html",
 "West":"https://wdfv.de/spielbetrieb/herren-regionalliga-west",
 "Südwest":"https://www.regionalliga-suedwest.de/Spielbetrieb/Vereine/",
 "Bayern":"https://datencenter.dfb.de/en/competitions/2257/seasons/current/current_matchweek?datacenter_name=data-center",
}
SCHEMA="""
CREATE TABLE fc27_regional_feeder_2026_27_group(
 edition INTEGER NOT NULL CHECK(edition=2027),
 code TEXT NOT NULL,
 country TEXT NOT NULL,
 tier INTEGER NOT NULL,
 regional_group TEXT NOT NULL,
 expected_members INTEGER NOT NULL,
 source_url TEXT NOT NULL,
 original_game_club_records_added INTEGER NOT NULL CHECK(original_game_club_records_added=0),
 full_player_squad_verified INTEGER NOT NULL CHECK(full_player_squad_verified=0),
 group_season_simulator_enabled INTEGER NOT NULL CHECK(group_season_simulator_enabled=0),
 PRIMARY KEY(edition,code,regional_group)
);
CREATE TABLE fc27_regional_feeder_2026_27_club(
 edition INTEGER NOT NULL CHECK(edition=2027),
 code TEXT NOT NULL,
 regional_group TEXT NOT NULL,
 real_club_name TEXT NOT NULL,
 reserve_or_youth INTEGER NOT NULL CHECK(reserve_or_youth IN (0,1)),
 PES_player_squad_imported INTEGER NOT NULL CHECK(PES_player_squad_imported=0),
 promotion_eligible_game_registration INTEGER NOT NULL
     CHECK(promotion_eligible_game_registration=0),
 same_name_in_original_FC27_source INTEGER NOT NULL CHECK(
     same_name_in_original_FC27_source IN (0,1)),
 PRIMARY KEY(edition,code,regional_group,real_club_name),
 FOREIGN KEY(edition,code,regional_group) REFERENCES
   fc27_regional_feeder_2026_27_group(edition,code,regional_group)
);
CREATE TABLE fc27_regional_feeder_game_policy(
 edition INTEGER NOT NULL CHECK(edition=2027),
 lower_code TEXT NOT NULL,
 upper_code TEXT NOT NULL,
 expected_promoted INTEGER NOT NULL CHECK(expected_promoted=4),
 upper_relegated INTEGER NOT NULL CHECK(upper_relegated=4),
 automatic_group_champions TEXT NOT NULL,
 playoff_final_winners INTEGER NOT NULL,
 playoff_group_candidates TEXT NOT NULL,
 season_rule_status TEXT NOT NULL CHECK(
   season_rule_status='season_specific_game_simplification_no_automatic_results'),
 promotion_simulation_enabled INTEGER NOT NULL CHECK(promotion_simulation_enabled=0),
 PRIMARY KEY(edition,lower_code,upper_code)
);
"""
def _norm(value):
    return "".join(ch for ch in unicodedata.normalize("NFKD",value.casefold())
                   if ch.isalnum() and not unicodedata.combining(ch))

def stage(db:sqlite3.Connection,path,*,strict=True):
    cfg=json.loads(Path(path).read_text(encoding="utf-8"))
    if (cfg.get("version")!=VERSION or cfg.get("edition")!=EDITION or
        cfg.get("game_rule_scope")!="only_one_feeder_level_below_2027_es.2_and_de.3" or
        cfg.get("original_game_clubs_altered") is not False or
        cfg.get("real_club_names_not_new_game_player_squads") is not True or
        cfg.get("no_lower_of_lower_divisions") is not True):
        raise ValueError("Regional feeder provenance and scope not certified")
    groups=cfg.get("groups")
    if not isinstance(groups,list) or len(groups)!=7:
        raise ValueError("Expected exactly seven sourced regional feeder groups")
    identifiers={(x["country"],x["group"]) for x in groups}
    if identifiers!={("Spain",g) for g in SPAIN}|{("Germany",g) for g in GERMANY}:
        raise ValueError("2026/27 seven-group country or identity mismatch")
    codes={"Spain":"2027:es.3","Germany":"2027:de.4"}
    intended={"Spain":"2027:es.2","Germany":"2027:de.3"}
    for country,upper in intended.items():
        if db.execute("""
           SELECT movement_policy,original_game_source_clubs
           FROM fc27_effective_world_league_movement_scope
           WHERE edition=2027 AND competition_code=?
        """,(upper,)).fetchone()[0]!="open_pyramid":
            raise ValueError(f"Regional immediate upper division not game-open: {upper}")
    orig_clubs={_norm(name) for (name,) in db.execute("""
      SELECT club FROM fc27_2026_27_complete_source_competition_alignment
      WHERE edition=2027
    """)}
    all_rows=[]
    group_rows=[]
    globally=set()
    for g in groups:
        ctry=g["country"];region=g["group"]
        expected=(SPAIN if ctry=="Spain" else GERMANY)[region]
        lower=codes[ctry]
        if (g["competition_code"]!=lower or
            g["competition_name"]!=("Primera Federación" if ctry=="Spain" else "Regionalliga")
            or g["expected_member_count"]!=expected or
            len(g.get("clubs",[]))!=expected or
            g["season"]!="2026-27" or g["source_url"]!=SOURCES[region]):
            raise ValueError(f"Original {ctry} 2026/27 region roster drift: {region}")
        identity={(ctry,_norm(x["name"])) for x in g["clubs"]}
        if len(identity)!=expected or any(not x[1] for x in identity):
            raise ValueError("Blank or duplicate source regional club membership")
        if globally & identity:
            raise ValueError("One club listed in multiple regional groups")
        globally|=identity
        if any(x["group"]!=region or type(x["reserve_or_youth"]) is not bool or
               x["game_ready_PES_player_roster"] is not False for x in g["clubs"]):
            raise ValueError("Reserve flag or PES squad evidence missing")
        group_rows.append((EDITION,lower,ctry,3 if ctry=="Spain" else 4,
                           region,expected,g["source_url"],0,0,0))
        for x in g["clubs"]:
            all_rows.append((EDITION,lower,region,x["name"],
                             int(x["reserve_or_youth"]),0,0,
                             int(_norm(x["name"]) in orig_clubs)))
    rules=cfg.get("gameplay_promotions")
    if not isinstance(rules,list) or len(rules)!=2:
        raise ValueError("Two regional feeder game rules required")
    rule_by_code={x["lower_competition"]:x for x in rules}
    if set(rule_by_code)!=set(codes.values()):
        raise ValueError("Missing Germany or Spain immediate regional promotion rules")
    for country,groupset,automatic,playoff,finalists in (
      ("Spain",SPAIN,["1","2"],2,[]),
      ("Germany",GERMANY,["West","Südwest","Nordost"],1,["Nord","Bayern"])):
        rule=rule_by_code[codes[country]]
        if (rule["upper_competition"]!=intended[country] or
            rule["automatic_from_group_winners"]!=automatic or
            rule["regional_playoff_winners"]!=playoff or
            rule.get("playoff_finalists",[])!=finalists or
            rule["up"]!=4 or rule["down"]!=4):
            raise ValueError(f"Rule for 4 balanced {country} regional exchange places changed")
    source_count=db.execute("""
      SELECT COUNT(*) FROM edition_club_competitions WHERE edition=2027
    """).fetchone()[0]
    db.executescript(SCHEMA)
    db.executemany("""
      INSERT INTO fc27_regional_feeder_2026_27_group VALUES(?,?,?,?,?,?,?,?,?,?)
    """,group_rows)
    db.executemany("""
      INSERT INTO fc27_regional_feeder_2026_27_club VALUES(?,?,?,?,?,?,?,?)
    """,all_rows)
    db.executemany("""
      INSERT INTO fc27_regional_feeder_game_policy
      VALUES(2027,?,?,4,4,?,?,?,
        'season_specific_game_simplification_no_automatic_results',0)
    """,[(rule["lower_competition"],rule["upper_competition"],
           ",".join(rule["automatic_from_group_winners"]),
           rule["regional_playoff_winners"],
           ",".join(rule.get("playoff_finalists",[])))
           for rule in rules])
    if len(all_rows)!=131 or len(group_rows)!=7:
        raise ValueError("2026/27 Spanish/German source group count not 40+91")
    if (db.execute("""
      SELECT COUNT(*) FROM edition_club_competitions WHERE edition=2027
    """).fetchone()[0]!=source_count or db.execute("PRAGMA foreign_key_check").fetchall()):
        raise ValueError("Regional review modified original game clubs or foreign key identity")
    if db.execute("""
        SELECT COUNT(*) FROM edition_readiness WHERE edition=2027 AND career_ready!=0
    """).fetchone()[0]:
        raise ValueError("No valid PES regional feeder squads - career must remain off")
    return {
       "edition":2027,
       "verified_regional_spain_club_names":40,
       "reviewed_regional_german_club_names":91,
       "separate_one_hop_regional_groups":7,
       "regionalliga_bavaria_2026_27_real_team_count":19,
       "new_real_feeder_club_names":131,
       "regional_club_name_collisions_with_source_club_labels":sum(r[-1] for r in all_rows),
       "source_game_squad_player_records_modified":False,
       "regional_promoted_clubs_registered":0,
       "regional_game_season_simulation_activated":False
    }

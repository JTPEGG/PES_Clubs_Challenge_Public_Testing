"""FC27: user's delegated, disclosed simplified rules for remaining league codes.

This is STAGING, not a career engine. Country names/league codes come from
the existing derived FC27 database; a source-group missing its whole division
does not gain fake clubs. Every judgement call remains inspectable.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

VERSION="fc27-user-delegated-gameplay-movement-gaps-v2"
EXPECTED=set((
 "ae.1 ar.1 au.1 az.1 bg.1 bo.1 br.1 cl.1 cn.1 co.1 "
 "cy.1 cz.1 dk.1 ec.1 fi.1 gr.1 hr.1 hu.1 ie.1 it.2 "
 "kr.1 mx.1 no.1 pe.1 pl.1 py.1 ro.1 sa.1 se.1 th.1 "
 "tr.1 ua.1 uy.1 ve.1"
).split())
EXPECTED_CODES={"2027:"+code for code in EXPECTED}
# Only major career-route lower divisions stay open in this 34-code tranche.
# Wider sourced European pyramids are handled separately and never overridden here.
OPEN_PYRAMIDS=frozenset({"2027:ar.1","2027:it.2","2027:pl.1","2027:tr.1"})
CLOSED=EXPECTED_CODES-OPEN_PYRAMIDS
if len(CLOSED)!=30:
    raise RuntimeError("FC27 explicitly approved broad closed-league scope drift")
PINNED={"2027:tr.1":18,"2027:pl.1":18,"2027:dk.1":12,
        "2027:se.1":16,"2027:no.1":16,"2027:kr.1":12,
        "2027:gr.1":4,"2027:it.2":20,
        "2027:au.1":12,"2027:mx.1":18}
SCHEMA="""
CREATE TABLE fc27_remaining_34_gameplay_movement(
 edition INTEGER NOT NULL CHECK(edition=2027),
 upper_code TEXT NOT NULL,
 country TEXT NOT NULL,
 upper_tier INTEGER NOT NULL,
 immediate_lower_code TEXT,
 immediate_lower_name TEXT,
 direct_promotions INTEGER NOT NULL CHECK(direct_promotions>=0),
 playoff_promotions INTEGER NOT NULL CHECK(playoff_promotions>=0),
 direct_relegations INTEGER NOT NULL CHECK(direct_relegations>=0),
 top_division_size_delta INTEGER NOT NULL,
 movement_mode TEXT NOT NULL CHECK(movement_mode IN
 ('no_promotion_or_relegation','gameplay_simplified_one_hop_exchange')),
 explicit_assumption_disclosure TEXT NOT NULL,
 source_context_url TEXT,
 source_context_not_complete_official_regulation INTEGER NOT NULL
     CHECK(source_context_not_complete_official_regulation=1),
 rule_provenance TEXT NOT NULL CHECK(rule_provenance IN
 ('game_policy_closed_league','user_delegated_simplification')),
 calendar_scope TEXT NOT NULL,
 club_squad_pool_ready INTEGER NOT NULL CHECK(club_squad_pool_ready=0),
 career_activated INTEGER NOT NULL CHECK(career_activated=0),
 PRIMARY KEY(edition,upper_code)
);
CREATE TABLE fc27_game_only_named_immediate_feeders(
 edition INTEGER NOT NULL CHECK(edition=2027),
 competition_code TEXT NOT NULL,
 country TEXT NOT NULL,
 tier INTEGER NOT NULL CHECK(tier>=2),
 name TEXT NOT NULL,
 provenance TEXT NOT NULL CHECK(provenance='user_approved_gameplay_one_hop_feeder_name'),
 original_game_club_pool_verified INTEGER NOT NULL CHECK(original_game_club_pool_verified=0),
 PRIMARY KEY(edition,competition_code)
);
CREATE VIEW fc27_simplified_game_movement_scope AS
 SELECT * FROM fc27_remaining_34_gameplay_movement WHERE edition=2027;
"""

def stage_game_defaults(db:sqlite3.Connection, path, *, strict=True):
    config=json.loads(Path(path).read_text(encoding="utf-8"))
    if (config.get("version")!=VERSION or config.get("edition")!=2027 or
        config.get("policy")!="pragmatic_broad_closed_league_defaults_preserve_four_select_open_pyramids"):
        raise ValueError("Wrong historical edition or gameplay-policy provenance")
    rows=config.get("rules")
    if not isinstance(rows,list) or len(rows)!=34:
        raise ValueError("FC27 agreed 34-group scope must be fully documented")
    upper_codes=[r["upper_code"] for r in rows]
    if len(set(upper_codes))!=34 or set(upper_codes)!=EXPECTED_CODES:
        raise ValueError("Some source competition is absent or duplicated in game policy")
    available={
      code:(country,int(tier),int(clubs)) for code,country,tier,clubs in db.execute("""
        SELECT competition_code,country,tier,active_source_clubs
        FROM fc27_2026_27_active_domestic_competitions
      """)
    }
    if strict and (len(available)!=53 or sum(x[2] for x in available.values())!=659):
        raise ValueError("FC27 original clubs or domestic divisions have drifted")
    for code,count in PINNED.items():
        if available.get(code,(None,0,0))[2]!=count:
            raise ValueError("Original FC27 club group changed; review before game defaults")
    occupied=set(x for (x,) in db.execute("""
        SELECT upper_code FROM fc27_additional_movement_boundaries WHERE edition=2027
    """))
    if set(upper_codes)&occupied:
        raise ValueError("Existing published movement regime cannot be silently overridden")
    original_count=db.execute("""
        SELECT COUNT(*) FROM edition_club_competitions WHERE edition=2027
    """).fetchone()[0] if strict else None
    before=dict(available)
    validated=[]
    feeders={}
    for r in rows:
        code=r["upper_code"]
        country,tier,number=available[code]
        lower=r["immediate_lower_code"]
        lower_name=r["immediate_lower_name"]
        up=r["game_direct_promotions"]
        playoff=r["game_playoff_promotions"]
        down=r["game_direct_relegations"]
        delta=r["top_division_club_count_delta_after_season"]
        if (r["country"]!=country or not isinstance(delta,int) or type(delta) is not int
             or any(type(x) is not int or x<0 for x in (up,playoff,down))
             or up+playoff-down!=delta):
            raise ValueError(f"Country or promotion/relegation conservation mismatch {code}")
        if not (r["assumption_disclosure"] and
                r["source_context_is_complete_verified_regulation"] is False and
                r["original_game_clubs_modified"] is False and
                r["feeder_original_club_squads_verified"] is False):
            raise ValueError("Game assumption omitted or incorrectly represented as real data")
        if r["source_context_url"]:
            ref=urlparse(r["source_context_url"])
            if ref.scheme!="https" or not ref.hostname or ref.hostname=="example.com":
                raise ValueError("Invalid contextual movement source")
        mode=r["movement_mode"]
        if code in CLOSED:
            if (mode!="no_promotion_or_relegation" or
                any((up,playoff,down,delta)) or lower is not None or lower_name is not None
                or r["rule_provenance"] not in
                ("game_policy_closed_league","user_delegated_closed_league")):
                raise ValueError("2026/27 closed league must not exchange fictional teams")
        else:
            expected_lower="2027:"+code.split(":")[1].split(".")[0]+"."+str(tier+1)
            if (mode!="gameplay_simplified_one_hop_exchange" or lower!=expected_lower
                 or not lower_name or r["rule_provenance"]!="user_delegated_simplification"):
                raise ValueError("Only immediately adjacent real named feeder division is allowed")
            if lower in available or lower in occupied:
                raise ValueError("Duplicated or conflicting original 2027 domestic game group")
            if lower in feeders and feeders[lower]!=(country,tier+1,lower_name):
                raise ValueError("Duplicate lower division name or country conflict")
            feeders[lower]=(country,tier+1,lower_name)
        if delta!=0:
            raise ValueError("FC27 league-size change is suppressed for closed leagues, including Korea")
        if code in ("2027:kr.1","2027:ro.1","2027:se.1","2027:no.1") and mode!="no_promotion_or_relegation":
            raise ValueError("Explicit user's four named minor leagues must remain closed")
        if code=="2027:pl.1" and (up,playoff,down)!=(2,1,3):
            raise ValueError("Polish three-team relegation / second-tier playoff changed")
        if code=="2027:it.2" and (up,playoff,down)!=(4,0,4):
            raise ValueError("Serie B -> Serie C game assumption changed")
        validated.append((2027,code,country,tier,lower,lower_name,up,playoff,
             down,delta,mode,r["assumption_disclosure"],r["source_context_url"],
             1,r["rule_provenance"],r["calendar_scope"],0,0))
    if db.execute("""
        SELECT COUNT(*) FROM edition_readiness WHERE edition=2027 AND career_ready!=0
    """).fetchone()[0]:
        raise ValueError("Do not activate careers from unpopulated feeder names")
    db.executescript(SCHEMA)
    db.executemany("""
        INSERT INTO fc27_remaining_34_gameplay_movement
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """,validated)
    db.executemany("""
        INSERT INTO fc27_game_only_named_immediate_feeders
        VALUES (?,?,?,?,?,?,0)
    """,[(2027,code,ctry,tier,name,"user_approved_gameplay_one_hop_feeder_name")
          for code,(ctry,tier,name) in sorted(feeders.items())])
    if dict((code,(ctry,int(tier),int(num))) for code,ctry,tier,num in db.execute("""
        SELECT competition_code,country,tier,active_source_clubs
        FROM fc27_2026_27_active_domestic_competitions
    """))!=before:
        raise ValueError("Game policy modified original 2027 league assignment")
    if strict and db.execute(
        "SELECT COUNT(*) FROM edition_club_competitions WHERE edition=2027"
    ).fetchone()[0]!=original_count:
        raise ValueError("Game policy modified original FC27 club archive")
    if db.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("Game defaults introduced broken foreign keys")
    return {
      "edition":2027, "source_competitions_with_new_game_rules":len(validated),
      "closed_2026_27_game_competitions":len(CLOSED),
      "new_named_nonplayable_single_step_feeders_without_squads":len(feeders),
      "game_scope_does_not_require_feeders_for_closed_leagues":True,
      "source_competitions_with_nonzero_game_exchange":len(validated)-len(CLOSED),
      "south_korea_2027_k_league_expansion_applied_in_game":False,
      "source_starting_2027_k_league_club_count_retained":available["2027:kr.1"][2],
      "explicitly_2027_closed_country_examples":["South Korea","Romania","Sweden","Norway"],
      "original_game_clubs_retained_in_all_closed_leagues":True,
      "closed_game_competitions_can_still_have_clubs_transfers_and_manager_jobs":True,
      "simulation_roster_certification":False,
      "original_club_records_modified":False,"career_activated":False
    }

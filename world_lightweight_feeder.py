"""One-hop simulated nonplayable feeder for the PES historical career world.

England configuration:
  * L2 playable -> National League is the only simulated external division
  * National League optionally playable -> National North/South are terminal
There is NO Step 3/4 pyramid, no invented players or historical future outcomes.
The simulation selects entrants deterministically from the real source club pool.
This module is a staging/QA adapter: it does not alter existing career saves.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from world_historical_competition_registry import canonical

VERSION="one-hop-real-club-feeders-v1"
SUPPORTED_EDITION=2027
ENGLISH_NATIONAL="2027:en.5"
ENGLISH_NORTH="2027:en.6n"
ENGLISH_SOUTH="2027:en.6s"
ENGLISH_LEAGUE_TWO="2027:en.4"
TERMINAL_FEEDERS=(ENGLISH_NORTH,ENGLISH_SOUTH)
# This is an intentional gameplay simplification, not a claim of official
# step-1/step-2 regional promotion or geographical reallocation rules.
FLOOR_MODE={
    "league_two": dict(playable=ENGLISH_LEAGUE_TWO,
                       feeders=(ENGLISH_NATIONAL,),
                       incoming={ENGLISH_NATIONAL:2},
                       out=2),
    "national_league":dict(playable=ENGLISH_NATIONAL,
                           feeders=TERMINAL_FEEDERS,
                           incoming={ENGLISH_NORTH:2,ENGLISH_SOUTH:2},
                           out=4),
}


def _identity(value):
    if not isinstance(value,str) or not value.strip():
        raise ValueError("Club must have a real, non-empty name")
    return canonical(value)


def _unique(names,description):
    if len(names)!=len({_identity(name) for name in names}):
        raise ValueError(f"Duplicate/ambiguous {description}")
    return tuple(names)


def load_english_feeder_pools(conn, *, edition=SUPPORTED_EDITION):
    """Read already cross-checked FA allocations and dated lower-EFL clubs.

    A game-league/source name is NOT proof of an EA player roster. Nonplayable
    clubs need only a name and a competition ID for simulated movement.
    """
    if edition!=SUPPORTED_EDITION:
        raise ValueError("Only FC27 official NLS source pools are currently verified")
    required=(ENGLISH_LEAGUE_TWO,ENGLISH_NATIONAL,ENGLISH_NORTH,ENGLISH_SOUTH)
    rows=conn.execute("""SELECT code,country,tier FROM competition_seasons
                       WHERE code IN (?,?,?,?)""",required).fetchall()
    divisions={code:(country,tier) for code,country,tier in rows}
    expected={ENGLISH_LEAGUE_TWO:("England",4),
              ENGLISH_NATIONAL:("England",5),
              ENGLISH_NORTH:("England",6),
              ENGLISH_SOUTH:("England",6)}
    if divisions!=expected:
        raise ValueError("Missing or wrongly labelled real domestic division")
    pool={}
    # The L2 list comes from the season-specific independent fixture source.
    l2=[r[0] for r in conn.execute("""
        SELECT club_name FROM sourced_domestic_league_clubs
        WHERE edition=? AND competition_code=? ORDER BY club_name""",
        (edition,ENGLISH_LEAGUE_TWO))]
    pool[ENGLISH_LEAGUE_TWO]=_unique(l2,"League Two source clubs")
    if len(pool[ENGLISH_LEAGUE_TWO])!=24:
        raise ValueError("League Two dated source has no complete 24-club pool")
    # FA-allocated names (not third-party abbreviations) are the definitive
    # NLS club labels, with the existing collector having cross-checked 72/72.
    for code in (ENGLISH_NATIONAL,ENGLISH_NORTH,ENGLISH_SOUTH):
        observed=conn.execute("""SELECT club_name,status FROM
            official_fa_nls_allocations WHERE edition=? AND competition_code=?
            ORDER BY club_name""",(edition,code)).fetchall()
        if len(observed)!=24 or any(r[1]!="fa_official_allocation_crosschecked"
                                    for r in observed):
            raise ValueError(f"Incomplete official FA feeder pool: {code}")
        pool[code]=_unique([r[0] for r in observed],f"{code} FA club names")
    all_names=[name for clubs in pool.values() for name in clubs]
    _unique(all_names,"clubs across all active and feeder divisions")
    return pool


def _draw(source_clubs, count, *, starting_season, key):
    if len(source_clubs)<count+2 or count<1:
        raise ValueError("Not enough eligible real clubs in feeder")
    # Deliberately a lightweight nonplayable simulation: ranking is fictional
    # within the career, but club identities and source divisions are real.
    # Salt by season and division to prevent repeatedly fixed promotions.
    def rank(club):
        payload=f"{VERSION}|{starting_season}|{key}|{_identity(club)}"
        return (hashlib.sha256(payload.encode("utf-8")).hexdigest(),_identity(club))
    return tuple(sorted(source_clubs,key=rank)[:count])


def rollover(pools, *, playable_floor, starting_season,
             relegated_from_playable, destination_regions=None):
    """Return one simulated boundary, no writes and no deeper feeder chains.

    For the optional National League playable mode exactly two NL relegated
    clubs must have known North/South destinations each. This keeps the 24+24
    feeder pools balanced without inventing unverified geography.
    """
    if playable_floor not in FLOOR_MODE:
        raise ValueError("Unsupported playable floor: cannot invent deeper pyramid")
    if not isinstance(starting_season,int) or starting_season<2026:
        raise ValueError("Invalid season simulation anchor")
    spec=FLOOR_MODE[playable_floor]
    if len(relegated_from_playable)!=spec["out"]:
        raise ValueError("Wrong relegation count from playable division")
    exiting=_unique(relegated_from_playable,"relegated playable clubs")
    current={code:tuple(clubs) for code,clubs in pools.items()}
    required=(spec["playable"],)+tuple(spec["feeders"])
    if any(code not in current for code in required):
        raise ValueError("Missing required real league/feeder source pool")
    for code in required:
        _unique(current[code],f"{code} real clubs")
        if len(current[code])!=24:
            raise ValueError(f"Unexpected number of teams in {code}")
    actual={_identity(x) for x in current[spec["playable"]]}
    if any(_identity(x) not in actual for x in exiting):
        raise ValueError("Relegated club must have been in original playable division")
    lower_names=[x for c in spec["feeders"] for x in current[c]]
    _unique(lower_names,"external feeder pool")
    if set(map(_identity,lower_names))&actual:
        raise ValueError("A club cannot start in playable and feeder leagues")
    selected={}
    for code,count in spec["incoming"].items():
        selected[code]=_draw(current[code],count,
                             starting_season=starting_season,key=code)
    incoming=tuple(x for code in spec["feeders"] for x in selected[code])
    if playable_floor=="league_two":
        assigned={ENGLISH_NATIONAL:exiting}
        if destination_regions:
            raise ValueError("North/South destinations are not used with League Two")
    else:
        if not destination_regions or set(destination_regions)!=set(exiting):
            raise ValueError("Need verified destination for every NL relegated club")
        assigned={code:[] for code in TERMINAL_FEEDERS}
        for name in exiting:
            region=destination_regions[name]
            if region not in assigned:
                raise ValueError("Relegated club assigned outside North/South")
            assigned[region].append(name)
        if any(len(assigned[code])!=2 for code in TERMINAL_FEEDERS):
            raise ValueError("Lightweight model requires two relegations per region")
    result=dict(current)
    leave={_identity(x) for x in exiting}
    result[spec["playable"]]=tuple(x for x in current[spec["playable"]]
                                    if _identity(x) not in leave)+incoming
    for code in spec["feeders"]:
        rising={_identity(x) for x in selected[code]}
        result[code]=tuple(x for x in current[code]
                           if _identity(x) not in rising)+tuple(assigned[code])
    if any(len(result[code])!=24 for code in required):
        raise ValueError("Unexpected loss of real clubs after feeder rollover")
    _unique([x for code in required for x in result[code]],
            "post-rollover division clubs")
    # Fixed terminal depth: the two 6th-tier pools themselves never consume
    # any lower division, irrespective of playable floor.
    return {
        "edition":SUPPORTED_EDITION,
        "starting_season":starting_season,
        "mode":playable_floor,
        "playable_division":spec["playable"],
        "simulated_feeders":list(spec["feeders"]),
        "bottom_external_depth":1,
        "promoted_into_playable":list(incoming),
        "relegated_from_playable":list(exiting),
        "promotion_by_feeder":{k:list(v) for k,v in selected.items()},
        "club_pools_after":{k:list(v) for k,v in result.items()},
        "method":"reproducible_seeded_nonplayable_results_not_historical_standings",
        "no_game_squads_generated":True,
        "no_production_career_changes":True,
        "career_activation_approved":False,
    }


def qa_run(sqlite_file,outdir):
    out=Path(outdir);out.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(f"file:{Path(sqlite_file).resolve()}?mode=ro",uri=True) as db:
        pool=load_english_feeder_pools(db)
    l2_relegated=pool[ENGLISH_LEAGUE_TWO][:2]
    nl_relegated=pool[ENGLISH_NATIONAL][:4]
    nl_region={nl_relegated[0]:ENGLISH_NORTH,
               nl_relegated[1]:ENGLISH_NORTH,
               nl_relegated[2]:ENGLISH_SOUTH,
               nl_relegated[3]:ENGLISH_SOUTH}
    l2_result=rollover(pool,playable_floor="league_two",
                       starting_season=2026,relegated_from_playable=l2_relegated)
    nl_result=rollover(pool,playable_floor="national_league",
                       starting_season=2026,relegated_from_playable=nl_relegated,
                       destination_regions=nl_region)
    report={
        "version":VERSION,"edition":SUPPORTED_EDITION,
        "source_playable_league_two_clubs":len(pool[ENGLISH_LEAGUE_TWO]),
        "official_fa_national_league_clubs":len(pool[ENGLISH_NATIONAL]),
        "official_fa_north_clubs":len(pool[ENGLISH_NORTH]),
        "official_fa_south_clubs":len(pool[ENGLISH_SOUTH]),
        "normal_playable_floor":"League Two; simulate exactly National League",
        "optional_floor":"National League; simulate North and South as terminal feeders",
        "lower_steps_required":False,"invented_nonplayable_squads":0,
        "career_activation_approved":False,"nonplayable_rollovers_validated":2,
        "example_league_two_promotion":l2_result["promoted_into_playable"],
        "example_national_league_promotion":nl_result["promoted_into_playable"],
        "actual_career_results_modified":False,
    }
    (out/"LIGHTWEIGHT_FEEDER_ROLLOVER_QA.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    return report


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--registry",required=True)
    p.add_argument("--output",required=True)
    opts=p.parse_args()
    print(json.dumps(qa_run(opts.registry,opts.output),indent=2,ensure_ascii=False))

"""Run non-destructive 2014/15 English Conference one-hop season-end smoke test.

Real club pools come from original 2014/15 independent League Two fixtures
and archived Conference Premier final table. Illustrative relegated clubs are
chosen only for QA: NOT historical end-of-season results or future game sims.
"""
from __future__ import annotations
import argparse,hashlib,json,sqlite3
from pathlib import Path
from world_lightweight_feeder import rollover,_unique
from world_historical_competition_registry import canonical

VERSION="historical-2015-english-one-hop-feeder-pilot-v1"
EDITION=2015
LOWER="2015:en.4"
FEEDER="2015:en.5"

def audit(dbfile,source_json,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    fp=Path(source_json)
    origin=json.loads(fp.read_text(encoding="utf-8"))
    if any((origin.get(k)!=v) for k,v in (
        ("game_edition",EDITION),("season","2014-15"),
        ("competition_code",FEEDER),("country","England"),
        ("tier",5),("source_status","date_specific_complete_24_club_historical_table"))):
        raise ValueError("Wrong-dated nonplayable English Conference source")
    if not str(origin.get("source_url","")).startswith("https://fchd.info/lghist/conf2015.htm"):
        raise ValueError("Not the reviewed contemporary historical Conference table")
    team_names=_unique(origin.get("clubs",[]),"dated FCHD Conference teams")
    if len(team_names)!=24:raise ValueError("FIFA15 Conference Premier must contain 24 real source clubs")
    with sqlite3.connect(f"file:{Path(dbfile).resolve()}?mode=ro",uri=True) as db:
        league=db.execute("SELECT country,tier FROM competition_seasons WHERE code=?",(LOWER,)).fetchone()
        if league!=("England",4):
            raise ValueError("FIFA15 English League Two competition is missing or wrong tier")
        l2_clubs=tuple(x[0] for x in db.execute("""
           SELECT club_name FROM sourced_domestic_league_clubs
           WHERE edition=? AND competition_code=? ORDER BY club_name""",(EDITION,LOWER)))
        active_career=db.execute(
            "SELECT COUNT(*) FROM edition_readiness WHERE career_ready=1").fetchone()[0]
    if active_career:raise ValueError("Unverified career may not be enabled")
    _unique(l2_clubs,"real 2014/15 League Two source teams")
    if len(l2_clubs)!=24:raise ValueError("Incomplete independently sourced 2014/15 League Two list")
    if set(map(canonical,team_names)) & set(map(canonical,l2_clubs)):
        raise ValueError("2014/15 Conference club overlaps League Two; season identity conflict")
    pools={LOWER:l2_clubs,FEEDER:team_names}
    first=rollover(pools,playable_floor="league_two",
         starting_season=2014,relegated_from_playable=l2_clubs[-2:],edition=EDITION)
    second=rollover(first["club_pools_after"],playable_floor="league_two",
         starting_season=2015,relegated_from_playable=first["club_pools_after"][LOWER][-2:],
         edition=EDITION)
    assert first["club_pools_after"]!=pools
    assert len(first["promoted_into_playable"])==2
    assert all(len(second["club_pools_after"][league])==24 for league in (LOWER,FEEDER))
    assert first["simulated_feeders"]==[FEEDER]
    result={
       "version":VERSION,"fifa_edition":EDITION,"historical_starting_season":"2014-15",
       "real_source_league_two_clubs":len(l2_clubs),
       "real_historical_conference_feeder_clubs":len(team_names),
       "verified_source_url":origin["source_url"],
       "dated_factual_club_ledger_sha256":hashlib.sha256(fp.read_bytes()).hexdigest(),
       "one_hop_feeder_uses_real_clubs":True,"regional_lower_tiers_required":False,
       "reproducible_rollovers_checked":2,
       "illustrative_first_virtual_season_promotions":first["promoted_into_playable"],
       "fixture_clubs_displaced_for_testing_only":first["relegated_from_playable"],
       "simulations_not_real_historical_results":True,
       "does_not_create_players_or_clubs":True,
       "actual_career_mode_enabled":False,"original_saves_modified":False,
       "remaining_separate_blocker":"York City missing from original FIFA15 men's squad catalogue; Shrewsbury source label review"}
    (out/"FIFA15_CONFERENCE_ONE_HOP_QA.json").write_text(
       json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    return result

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--registry",required=True)
    ap.add_argument("--conference",required=True)
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    print(json.dumps(audit(args.registry,args.conference,args.output),
                     indent=2,ensure_ascii=False))

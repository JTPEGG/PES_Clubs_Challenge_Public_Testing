"""Diagnostic single-edition first career pilot: England 2014/15 in FIFA 15.

Check all 92 season-specific English professional division clubs from pinned
fixtures against original FIFA15 game clubs; require deterministic promotion
rules and a real (one-level-only) 2014/15 Conference feeder. This is a read-only
test -- it must never fabricate missing clubs or set career_ready=1.
"""
from __future__ import annotations
import argparse,csv,json,sqlite3
from collections import Counter,defaultdict
from pathlib import Path
from world_historical_competition_registry import canonical
from world_historical_movement_rules import source_rules

EDITION=2015
CODES={"2015:en.1":20,"2015:en.2":24,"2015:en.3":24,"2015:en.4":24}
VERSION="fifa15-english-four-tier-first-career-source-pilot-v2"
# The original FIFA15 source actually calls this real League Two club simply
# 'Shrewsbury'. A unique source-game identity is review evidence, not a newly
# created FIFA club or proof of original EA team ID.
CONTROLLED_GAME_LABELS={(2015,"2015:en.4",canonical("Shrewsbury Town")):canonical("Shrewsbury")}

def audit(dbpath,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(f"file:{Path(dbpath).resolve()}?mode=ro",uri=True) as db:
        clubs=db.execute("""SELECT club_key,club,starting_competition,evidence_origin
               FROM edition_career_starting_league_candidates
               WHERE edition=?""",(EDITION,)).fetchall()
        external=db.execute("""SELECT competition_code,club_name,source_url
                FROM sourced_domestic_league_clubs
                WHERE edition=? AND competition_code IN (?,?,?,?)
                ORDER BY competition_code,club_name""",(EDITION,*CODES)).fetchall()
        fixture_db=db.execute("""SELECT club_key,competition_code,fixture_club
                FROM fixture_club_evidence WHERE edition=?""",(EDITION,)).fetchall()
        feed=db.execute("""SELECT COUNT(*) FROM sourced_nonplayable_feeder_clubs
                         WHERE edition=?""",(EDITION,)).fetchone()[0]
        original_count=db.execute(
             "SELECT total_clubs FROM edition_readiness WHERE edition=?",(EDITION,)).fetchone()
        game_missing=db.execute("""SELECT COUNT(*) FROM edition_career_starting_league_candidates
           WHERE edition=? AND starting_competition IS NULL""",(EDITION,)).fetchone()[0]
        verified_game=db.execute(
           "SELECT career_ready FROM edition_readiness WHERE edition=?",(EDITION,)).fetchone()[0]
    if not original_count or original_count[0]!=len(clubs) or verified_game!=0:
        raise ValueError("Incorrect or accidentally activated original FIFA15 career data")
    byname=defaultdict(list)
    for key,name,comp,origin in clubs:
        byname[canonical(name)].append((key,name,comp,origin))
    bysource=defaultdict(list)
    for key,code,fixture in fixture_db:
        bysource[(code,canonical(fixture))].append(key)
    original={c[0]:c for c in clubs}
    status=Counter()
    verified=[]
    seen=set()
    league_source=Counter(x[0] for x in external)
    for code,name,url in external:
        candidates=byname[canonical(name)]
        alias_used=False
        if len(candidates)!=1:
            exact_keys=bysource[(code,canonical(name))]
            candidates=[original[k] for k in exact_keys if k in original]
        if not candidates:
            alias_key=CONTROLLED_GAME_LABELS.get((EDITION,code,canonical(name)))
            if alias_key:
                candidates=byname[alias_key]
                alias_used=len(candidates)==1
        if len(candidates)!=1:
            reason="game_club_ambiguous" if candidates else "no_same_edition_original_game_club"
            status[reason]+=1
            verified.append((code,name,"","",url,reason))
            continue
        key,display,assigned,origin=candidates[0]
        if key in seen:
            status["same_game_club_claimed_twice"]+=1
            verified.append((code,name,key,display,url,"same_game_club_claimed_twice"))
            continue
        seen.add(key)
        if assigned and assigned!=code and not assigned.startswith("GAME:"):
            status["conflicting_other_league_source"]+=1
            verified.append((code,name,key,display,url,"conflicting_other_league_source"))
            continue
        stage=("curated_original_source_shrewsbury_alias_needs_game_identity_review"
               if alias_used else
               "fixture_registered" if assigned==code else
               "original_game_league_needs_id_crosswalk" if assigned else
               "same_edition_name_only_pending_club_id_review")
        status[stage]+=1
        verified.append((code,name,key,display,url,stage))
    for code,expected in CODES.items():
        if league_source[code]!=expected:
            status["incomplete_real_league_source"]+=1
    rules=[x for x in source_rules(EDITION) if x["lower"].startswith("ENG:")]
    required={"ENG:CH","ENG:L1","ENG:L2","ENG:NL"}
    if {r["lower"] for r in rules}!=required:
        raise ValueError("FIFA15 dated EFL pyramid edges were not supplied")
    real_movement=[(r["lower"],r["upper"],r["direct_promotions"],
                    r["playoff_promotions"],r["direct_relegations"]) for r in rules]
    recognized=(status["fixture_registered"]
              +status["original_game_league_needs_id_crosswalk"]
              +status["same_edition_name_only_pending_club_id_review"]
              +status["curated_original_source_shrewsbury_alias_needs_game_identity_review"])
    external_team_count=len(external)
    cannot_start=bool(recognized!=92 or status.get("conflicting_other_league_source")
              or feed==0 or status["incomplete_real_league_source"])
    with (out/"FIFA15_ENGLAND_92_REAL_CLUB_IDENTITY_AUDIT.csv").open(
            "w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f);w.writerow(("Competition","External_Club","FIFA_Club_Key",
          "Game_Club_Name","External_Fixture_URL","Review_Status"));w.writerows(verified)
    with (out/"FIFA15_ENGLAND_PROMOTION_BORDERS.csv").open(
             "w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f);w.writerow(("Lower_Division","Upper_Division",
         "Direct_Promotions","Playoff_Promotions","Relegations_From_Upper"));w.writerows(real_movement)
    report={
       "version":VERSION,"edition":EDITION,"season":"2014-15",
       "all_original_edition_clubs":len(clubs),
       "original_edition_clubs_still_without_any_league":game_missing,
       "professional_source_divisions":len(CODES),
       "expected_english_professional_clubs":92,
       "dated_english_professional_source_clubs":external_team_count,
       "same_edition_source_to_game_club_matches":recognized,
       "controlled_historical_name_aliases_pending_review":
           status["curated_original_source_shrewsbury_alias_needs_game_identity_review"],
       "source_game_matching_status":dict(status),
       "dating_source_clubs_per_division":dict(league_source),
       "dated_english_promotion_movement_edges":len(real_movement),
       "one_level_below_league_two_source_2014_15_feeder_clubs":feed,
       "has_all_pilot_club_identities":recognized==92 and len(seen)==92,
       "can_start_first_historical_career":not cannot_start and False,
       "status":"read_only_pilot_requirements_audit_not_career_activation",
       "original_source_squads_modified":False,
    }
    (out/"FIFA15_ENGLISH_FIRST_CAREER_PILOT_AUDIT.json").write_text(
         json.dumps(report,indent=2),encoding="utf-8")
    return report

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--registry",required=True)
    a.add_argument("--output",required=True)
    op=a.parse_args()
    print(json.dumps(audit(op.registry,op.output),indent=2))

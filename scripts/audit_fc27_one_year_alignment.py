"""FC27 2026/27: one-edition club, competition and boundary reconciliation audit.

Read the original staged 22-edition SQLite but touch ONLY edition=2027.
The audit separates authentic game-player groupings from genuine domestic
competition membership; same names never imply verified EA club identities.
Never modifies the master DB, career activation, squads or other editions.
"""
from __future__ import annotations
import argparse,csv,json,sqlite3
from collections import Counter,defaultdict
from pathlib import Path
from world_historical_competition_registry import canonical,cup_group
EDITION=2027
VERSION="fc27-year-first-domestic-alignment-audit-v1"
SOURCE_VIEW="edition_career_starting_league_candidates"

def export(path,columns,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as out:
        w=csv.writer(out);w.writerow(columns);w.writerows(rows)

def audit(source,outdir):
    out=Path(outdir);out.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(f"file:{Path(source).resolve()}?mode=ro",uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise ValueError("Bad historical source registry")
        originals=db.execute("""
         SELECT c.club_key,c.club,c.original_source_league,c.group_type,
                c.confidence,p.starting_competition,p.evidence_origin
         FROM edition_club_competitions c
         JOIN edition_career_starting_league_candidates p
           ON c.edition=p.edition AND c.club_key=p.club_key
         WHERE c.edition=? ORDER BY c.club,c.club_key""",(EDITION,)).fetchall()
        leagues=db.execute("SELECT code,country,tier,name FROM competition_seasons WHERE edition=? ORDER BY country,tier,code",(EDITION,)).fetchall()
        fixtures=db.execute("""SELECT c.competition_code,c.club_name,c.verification,
                         c.source_url FROM sourced_domestic_league_clubs c
                         WHERE c.edition=? ORDER BY c.competition_code,c.club_name""",(EDITION,)).fetchall()
        source_groups=db.execute("""SELECT league_key,source_label,club_count,
                  corroborated_competition,exact_clubs,alias_candidates,status
                  FROM source_league_groups WHERE edition=? ORDER BY club_count DESC,source_label""",(EDITION,)).fetchall()
        rules=db.execute("""SELECT lower,upper,direct_promotions,playoff_promotions,
                         direct_relegations,source_status,feeder_verified
                         FROM season_versioned_rules WHERE edition=?
                         ORDER BY lower,upper""",(EDITION,)).fetchall()
        feeder=db.execute("""SELECT competition_code,club_name
                         FROM sourced_nonplayable_feeder_clubs
                         WHERE edition=?""",(EDITION,)).fetchall()
        fa=db.execute("""SELECT competition_code,club_name,status
                         FROM official_fa_nls_allocations WHERE edition=?""",(EDITION,)).fetchall()
        original_total=db.execute("SELECT COUNT(*) FROM edition_club_competitions").fetchone()[0]
        ready=db.execute("SELECT career_ready FROM edition_readiness WHERE edition=?",(EDITION,)).fetchone()
    if not originals or original_total!=13104 or ready is None or int(ready[0])!=0:
        raise ValueError("Wrong 22-edition registry or already activated career")
    codes={code:(country,tier,name) for code,country,tier,name in leagues}
    src_by_code=defaultdict(list)
    src_by_name=defaultdict(list)
    for code,name,status,url in fixtures:
        src_by_code[code].append(name)
        src_by_name[canonical(name)].append((code,name))
    game_by_name=defaultdict(list)
    for key,name,group,typ,confidence,comp,origin in originals:
        game_by_name[canonical(name)].append((key,name))
    linked=Counter();unresolved=[];checks=[];auto=[];reviews=[]
    for key,name,group,typ,confidence,code,origin in originals:
        linked[str(origin)]+=1
        if code:
            if code.startswith("GAME:"):linked["not_yet_in_domestic_graph"]+=1
            elif code not in codes:linked["external_competition_not_registered"]+=1
            elif typ=="continental_cup_bucket":reviews.append((key,name,group,
                     code,"continental_group_must_not_substitute_home_league"))
            continue
        reason=("continental_competition_bucket" if typ=="continental_cup_bucket"
                else "original_source_group_missing" if not group
                else "original_source_group_unresolved")
        matches=src_by_name.get(canonical(name),[])
        unique={(c,canonical(n)) for c,n in matches}
        if len(game_by_name[canonical(name)])!=1:
            reason="game_name_collision"
        elif len(unique)>1:reason="same_name_in_multiple_dated_divisions"
        elif len(unique)==1:
            c,n=matches[0]
            reason="unique_2027_fixture_name_pending_identity_review"
            # Names are candidates only: no country or EA-id assurance.
            auto.append((key,name,group,c,n,"unique_same_edition_canonical_provisional"))
        unresolved.append((key,name,group,typ,confidence,reason,
            "|".join(sorted({m[0] for m in matches}))))
    seen_comp=defaultdict(list)
    for key,name,group,typ,confidence,code,origin in originals:
        if code in codes:seen_comp[code].append((key,name,origin))
    for code,(country,tier,name) in sorted(codes.items()):
        source_names=src_by_code.get(code,[])
        assigned=seen_comp.get(code,[])
        checks.append((code,country,tier,name,len(source_names),len(assigned),
                       len({canonical(x) for x in source_names}),
                       len({canonical(x[1]) for x in assigned}),
                       "|".join(sorted(set(x[2] for x in assigned))),
                       "one_to_one_source_membership_pending_game_id"
                       if source_names else "no_independent_fixture_clubs"))
    groups=[(key,label,total,code or "",exact,alias,status) for key,label,total,code,exact,alias,status in source_groups]
    original_by_group=defaultdict(list)
    for key,name,group,typ,confidence,code,origin in originals:
        original_by_group[group or "<blank>"].append((key,name,code or "",origin))
    group_examples=[(group,len(records)," | ".join(name for _,name,_,_ in records[:12]))
                    for group,records in sorted(original_by_group.items(),
                     key=lambda item:(-len(item[1]),item[0]))]
    export(out/"FC27_ALL_ORIGINAL_GAME_CLUBS.csv",
       ("Club_Key","Original_Club","Original_Source_League","Group_Type","Confidence",
        "Starting_Competition","Evidence_Origin"),originals)
    export(out/"FC27_UNRESOLVED_ORIGINAL_CLUBS.csv",
       ("Club_Key","Original_Club","Original_Source_League","Group_Type","Confidence",
        "Reason","Fixture_League_Candidates"),unresolved)
    export(out/"FC27_PROVISIONAL_UNIQUE_NAME_RECOVERY_QUEUE.csv",
       ("Club_Key","Original_Club","Original_Source_League","Candidate_Competition",
        "Original_Fixture_Club","Evidence_Limit"),auto)
    export(out/"FC27_SOURCE_COMPETITION_COVERAGE.csv",
       ("Competition_Code","Country","Tier","Competition","Sourced_Fixture_Clubs",
        "Original_Game_Clubs_Currently_Assigned","Unique_Source_Names",
        "Unique_Assigned_Game_Club_Names","Assignment_Origins",
        "Validation_Status"),checks)
    export(out/"FC27_SOURCE_GROUP_CLUB_MEMBERS.csv",
       ("Original_Source_Group","Club_Key","Club","Current_Competition","Evidence_Origin"),
       [(group,*x) for group,records in original_by_group.items() for x in records])
    export(out/"FC27_SOURCE_GROUP_EXAMPLES.csv",
       ("Original_Source_Group","Original_Clubs","First_12_Game_Club_Names"),group_examples)
    export(out/"FC27_UNRESOLVED_SOURCE_GROUPS.csv",
       ("Source_Key","Source_Group","Original_Game_Clubs","Corroborated_Competition",
        "Exact_Source_Clubs","Alias_Review_Clubs","Status"),groups)
    export(out/"FC27_VERSIONED_MOVEMENT_RULES.csv",
       ("Lower","Upper","Direct_Promotions","Playoff_Promotions",
        "Direct_Relegations","Rule_Status","Feeder_Validated"),rules)
    export(out/"FC27_REQUIRES_REVIEW.csv",
       ("Club_Key","Club","Original_League","Starting_Competition","Reason"),reviews)
    bygroup=Counter((r[2] or "<missing>") for r in unresolved)
    summary={
      "version":VERSION,"edition":EDITION,"season":"2026/27",
      "original_edition_clubs":len(originals),
      "clubs_with_any_starting_competition":len(originals)-len(unresolved),
      "clubs_without_home_competition":len(unresolved),
      "source_league_seasons":len(leagues),
      "source_league_club_observations":len(fixtures),
      "source_groups":len(source_groups),
      "unresolved_by_original_source_group":dict(bygroup.most_common()),
      "unresolved_source_group_club_examples":{k:records[:12] for k,records in [
          (group,[name for key,name,comp,origin in original_by_group[group]])
          for group in bygroup]},
      "evidence_by_origin":dict(linked),
      "unique_name_candidate_review_queue":len(auto),
      "problematic_linked_continental_groups":len(reviews),
      "season_rule_edges":len(rules),
      "unverified_feeder_rule_edges":sum(not x[-1] for x in rules),
      "nonplayable_feeder_observations":len(feeder),
      "official_FA_allocated_feeders":len(fa),
      "max_source_club_names_per_competition":max(map(len,src_by_code.values()),default=0),
      "edition_career_ready":False,
      "game_club_identity_certified":False,
      "production_database_unchanged":True}
    (out/"FC27_ONE_YEAR_ALIGNMENT_DIAGNOSTIC.json").write_text(
       json.dumps(summary,indent=2),encoding="utf-8")
    return summary

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--registry",required=True)
    a.add_argument("--output",required=True)
    args=a.parse_args()
    print(json.dumps(audit(args.registry,args.output),indent=2))

"""Fast, season-safe club-to-league name reconciliation.

The input competition register already contains independently sourced 447
season-specific divisions. This module resolves controlled club abbreviations
on the SAME original FIFA edition only, with unique source and game names.
All accepted matches are PROVISIONAL name evidence, never proof of EA team ID.
No career is activated. Ambiguous identities remain in a separate review CSV.
"""
from __future__ import annotations
import argparse,csv,json,sqlite3,re,unicodedata
from collections import Counter,defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from world_historical_competition_registry import canonical,cup_group

VERSION="historical-controlled-club-alias-reconcile-v1"
TOKEN_EXPANSIONS={
 "utd":"united","man":"manchester","nottm":"nottingham",
 "st":"saint","ath":"athletic","athl":"athletic",
 "int'l":"international",
}
# Unambiguous club display conventions only. Reconciliation also requires a
# UNIQUE SAME-SEASON external club and UNIQUE original-game club identity.
CONTROLLED_VARIANTS={
 "qpr":"queensparkrangers",
 "spurs":"tottenhamhotspur",
 "psg":"parissaintgermain",
 "bayernmunich":"bayernmunchen",
 "bayernmunchen":"bayernmunchen",
 "bayernmuenchen":"bayernmunchen",
 "intermilan":"internazionale",
 "intermilano":"internazionale",
 "internazionalemilano":"internazionale",
 "redstarbelgrade":"crvenazvezda",
 "redstar":"crvenazvezda",
}
def alias_key(s):
    s=unicodedata.normalize("NFKD",str(s).casefold()).replace("&"," and ")
    s="".join(c for c in s if not unicodedata.combining(c))
    t=re.findall(r"[a-z0-9]+",s)
    t=[TOKEN_EXPANSIONS.get(v,v) for v in t]
    result=canonical(" ".join(t))
    return CONTROLLED_VARIANTS.get(result,result)

def read_rows(database,sql,params=()):
    return database.execute(sql,params).fetchall()

def reconcile(source_sqlite,register_sqlite,output,identity_file=None):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    guards={}
    if identity_file:
        obj=json.loads(Path(identity_file).read_text(encoding="utf-8"))
        if obj["version"]!="historical-club-identity-disambiguation-v1":
            raise ValueError("Unsupported immutable identity evidence ledger")
        for x in obj["entries"]:
            guards[(int(x["edition"]),str(x["game_club_key"]))]=x["country"]
    with sqlite3.connect(f"file:{Path(source_sqlite).resolve()}?mode=ro",uri=True) as src,\
         sqlite3.connect(f"file:{Path(register_sqlite).resolve()}?mode=ro",uri=True) as db:
        games=read_rows(src,"SELECT edition,club_key,name,league_key FROM clubs")
        existing=read_rows(db,"SELECT edition,club_key,confidence,group_type FROM edition_club_competitions")
        seasons={r[0]:(r[1],r[2],r[3]) for r in
                 read_rows(db,"SELECT code,edition,country,tier FROM competition_seasons")}
        sources=read_rows(db,"""SELECT c.edition,c.competition_code,c.club_name,
                                 c.source_url,c.source_sha256,c.verification
                             FROM sourced_domestic_league_clubs c
                             ORDER BY c.edition,c.competition_code,c.club_name""")
        checked=read_rows(db,"SELECT edition,club_key,competition_code,fixture_club FROM fixture_club_evidence")
    orig={(int(y),str(k)):(str(name),str(group or "")) for y,k,name,group in games}
    linked={(int(y),str(k)) for y,k,conf,typ in existing if conf!="unresolved"}
    conflicted={(int(y),str(k)) for y,k,conf,typ in existing if conf=="conflict"}
    cups={(int(y),str(k)) for y,k,conf,typ in existing if typ=="continental_cup_bucket"}
    fixture_taken={(int(y),code,canonical(name)) for y,key,code,name in checked}
    games_by_alias=defaultdict(list)
    for y,k,name,group in games:
        ident=(int(y),str(k))
        if ident in linked or ident in conflicted or ident in cups:
            continue
        games_by_alias[(int(y),alias_key(name))].append((str(k),str(name)))
    source_by_alias=defaultdict(list)
    for y,code,name,url,digest,verification in sources:
        if seasons[code][0]!=int(y):
            raise ValueError("Season-specific source registered under a different edition")
        source_by_alias[(int(y),alias_key(name))].append(
            (code,str(name),url,digest,verification,seasons[code][1]))
    candidate_rows=[]; ambiguous=[]; rejected=Counter()
    for (y,namekey),game_candidates in sorted(games_by_alias.items()):
        if len(game_candidates)!=1:
            rejected["same_edition_game_alias_collision"]+=len(game_candidates)
            for k,g in game_candidates:
                ambiguous.append((y,k,g,"","",0,"duplicate_original_name_after_alias"))
            continue
        club_key,game_name=game_candidates[0]
        source_candidates=source_by_alias.get((y,namekey),[])
        if not source_candidates:
            continue
        distinct={(x[0],canonical(x[1])) for x in source_candidates}
        if len(distinct)!=1:
            rejected["different_source_divisions_or_clubs"]+=1
            ambiguous.append((y,club_key,game_name," | ".join(sorted({x[0] for x in source_candidates})),
                              " | ".join(sorted({x[1] for x in source_candidates})),0,
                              "same_alias_in_multiple_external_clubs"))
            continue
        code,fixture,url,digest,verification,country=source_candidates[0]
        if canonical(game_name)==canonical(fixture):
            # Existing simple normaliser has already considered this match,
            # so don't paper over a previously rejected source conflict.
            rejected["basic_canonical_already_processed"]+=1
            continue
        if guards.get((y,club_key),country)!=country:
            rejected["independently_identified_wrong_country"]+=1
            ambiguous.append((y,club_key,game_name,code,fixture,0,
                              "source_country_conflicts_with_verified_EA_identity"))
            continue
        if fixture_taken and (y,code,canonical(fixture)) in fixture_taken:
            # Check already-used fixture by fixture name, not the game's alias.
            rejected["fixture_already_used"]+=1
            continue
        # Same edition + exact expanded abbreviation + one-to-one source
        # country + pinned source checksum; never standalone fuzzy acceptance.
        candidate_rows.append((y,club_key,game_name,code,fixture,url,digest,
                               country,verification,"controlled_alias_same_edition_unique",
                               "provisional_name_evidence_not_game_id"))
    # Catch collisions of one source team mapped to two game clubs before export
    group=defaultdict(list)
    for x in candidate_rows:group[(x[0],x[3],canonical(x[4]))].append(x)
    safe=[]
    for key,rows in group.items():
        if len(rows)!=1:
            rejected["source_team_selected_by_two_game_clubs"]+=len(rows)
            for x in rows:ambiguous.append((x[0],x[1],x[2],x[3],x[4],0,
                                           "source_team_alias_collision"))
        else:safe.append(rows[0])
    safe.sort(key=lambda x:(x[0],x[3],x[2]))
    with (output/"AUTO_CONTROLLED_CLUB_ALIASES.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f);w.writerow(("Edition","FIFA_Club_Key","FIFA_Club",
            "Competition_Code","Fixture_Club","Source_URL","Source_SHA256",
            "Source_Country","Source_Verification","Match_Reason","Identity_Limit"))
        w.writerows(safe)
    with (output/"AUTO_ALIAS_COLLISIONS_FOR_REVIEW.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f);w.writerow(("Edition","FIFA_Club_Key","FIFA_Club",
            "Candidate_Competitions","Source_Names","Score","Reason"))
        w.writerows(ambiguous)
    audit=dict(version=VERSION,original_club_seasons=len(orig),
       previously_evidenced_game_club_seasons=len(linked),
       previously_unresolved=len(orig)-len(linked),
       controlled_unique_same_edition_name_links=len(safe),
       new_edition_counts=dict(Counter(str(x[0]) for x in safe)),
       ambiguous_name_records=len(ambiguous),rejection_reasons=dict(rejected),
       source_club_seasons=len(sources),source_competitions=len(seasons),
       no_fuzzy_auto_assignments=True,source_team_id_not_inferred=True,
       career_ready=False,player_squads_created=0)
    (output/"AUTO_ALIAS_RECONCILIATION_AUDIT.json").write_text(
        json.dumps(audit,indent=2),encoding="utf-8")
    return audit

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True)
    p.add_argument("--registry",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--identity-review")
    a=p.parse_args()
    print(json.dumps(reconcile(a.source,a.registry,a.output,
        a.identity_review),indent=2))

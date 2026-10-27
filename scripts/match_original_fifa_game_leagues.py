"""Recover source-game domestic league assignments from historical FIFA teams.

A season-specific FIFA team roster is directly relevant even where separate
fixture archives do not cover the country's league. This is a GAME league
crosswalk; it does not pretend an independent real-world competition has been
verified or fabricate promotion/relegation memberships.
"""
from __future__ import annotations
import argparse,csv,json,sqlite3
from collections import Counter,defaultdict
from pathlib import Path
from scripts.audit_historical_ea_team_id_leagues import edition_of,viable_league
from scripts.reconcile_historical_club_aliases import alias_key
from world_historical_competition_registry import canonical,cup_group

VERSION="original-fifa-game-team-league-name-join-v1"
COVERED=set(range(2015,2024))
FIELDNAMES=("Edition","FIFA_Club_Key","Original_FIFA_Club","Original_Group",
            "EA_Team_ID","EA_Team_Name","Game_League_ID","Game_League_Name",
            "Game_League_Level","Game_Club_Country","EA_Observation_Count",
            "Name_Method","Evidence_Status","Reason")

def audit(original_database,source_csv,output,registry_db=None):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(f"file:{Path(original_database).resolve()}?mode=ro",uri=True) as db:
        clubs=[(int(y),str(key),str(name),str(group or "")) for y,key,name,group in
               db.execute("SELECT edition,club_key,name,league_key FROM clubs")]
    linked=set()
    if registry_db:
        with sqlite3.connect(f"file:{Path(registry_db).resolve()}?mode=ro",uri=True) as db:
            linked={(int(y),str(key)) for y,key in db.execute(
                 "SELECT edition,club_key FROM edition_club_competitions WHERE evidence_competition IS NOT NULL")}
    originals=defaultdict(list)
    by_edition=Counter()
    for y,key,name,group in clubs:
        if y not in COVERED:continue
        by_edition[y]+=1
        originals[(y,canonical(name))].append((y,key,name,group))
    source_by_name=defaultdict(list)
    source_by_alias=defaultdict(list)
    original_aliases=defaultdict(list)
    for y,key,name,group in clubs:
        if y in COVERED:original_aliases[(y,alias_key(name))].append(key)
    read_count=Counter()
    with open(source_csv,encoding="utf-8-sig",newline="") as h:
        rd=csv.DictReader(h)
        required={"team_id","fifa_version","team_name","league_id","league_name","league_level"}
        if not required.issubset(rd.fieldnames or ()):
            raise ValueError("Pinned original FIFA men's teams source has missing fields")
        for row in rd:
            y=edition_of(row["fifa_version"])
            if y not in COVERED:continue
            name=str(row["team_name"] or "").strip()
            if not name or cup_group(row["league_name"]):continue
            if not viable_league(row["league_name"],row["league_level"]):continue
            if not str(row["league_id"]).strip().isdigit():continue
            if not str(row["team_id"]).strip().isdigit():continue
            datum=(str(row["team_id"]).strip(),name,
                   str(row["league_id"]).strip(),str(row["league_name"]).strip(),
                   int(float(row["league_level"])),
                   str(row.get("nationality_name") or "").strip(),
                   str(row.get("fifa_update") or "").strip())
            source_by_name[(y,canonical(name))].append(datum)
            source_by_alias[(y,alias_key(name))].append(datum)
            read_count[y]+=1
    passed=[];reviews=[];count=Counter()
    for (edition,canon),records in sorted(originals.items()):
        src=source_by_name.get((edition,canon),[])
        if len(records)!=1:
            for _,key,name,group in records:
                reviews.append((edition,key,name,group,"","","","",0,"",0,
                                "ambiguous","duplicate_original_game_names"))
            count["original_name_collisions"]+=len(records)
            continue
        y,key,name,group=records[0]
        method="unique_same_edition_exact_name"
        if not src:
            new_key=alias_key(name)
            if len(original_aliases[(edition,new_key)])!=1:
                count["controlled_alias_game_name_collision"]+=1
                continue
            src=source_by_alias.get((edition,new_key),[])
            method="unique_same_edition_controlled_alias"
        if not src:continue
        team_ids={x[0] for x in src}
        identities={(x[0],x[2],x[3],x[4],x[5]) for x in src}
        if len(team_ids)!=1 or len(identities)!=1:
            reviews.append((edition,key,name,group,"","",
                            " | ".join(sorted({x[2] for x in src})),
                            " | ".join(sorted({x[3] for x in src})),0,"",len(src),
                            "ambiguous","same_name_multiple_teams_or_leagues"))
            count["conflicting_source_team_identity_or_league"]+=1
            continue
        team_id,game_name,league_id,league_name,level,country,update=src[0]
        status=("previous_fixture_evidence_corroborated" if (edition,key) in linked
                else "game_edition_home_league_identified")
        passed.append((edition,key,name,group,team_id,game_name,league_id,
                       league_name,level,country,len(src),method,
                       status,"historical_game_team_league_evidence_not_full_pyramid"))
        if method=="unique_same_edition_controlled_alias":
            count["source_game_name_controlled_alias"]+=1
        count[status]+=1
    seen={(r[0],r[1]) for r in passed}
    def dump(path,rows):
        with (out/path).open("w",encoding="utf-8-sig",newline="") as f:
            w=csv.writer(f);w.writerow(FIELDNAMES);w.writerows(rows)
    dump("FIFA_GAME_EDITION_EXACT_CLUB_DOMESTIC_LEAGUES.csv",passed)
    dump("FIFA_GAME_EDITION_NAME_CONFLICTS.csv",reviews)
    summary={
      "version":VERSION,"game_source":"jsulz/FIFA23 archived mens SoFIFA teams by FIFA edition",
      "fifa_editions":sorted(COVERED),
      "original_game_clubs_all_editions":len(clubs),
      "original_game_clubs_in_source_period":sum(by_edition.values()),
      "same_edition_source_observations":sum(read_count.values()),
      "unique_same_edition_name_domestic_league_matches":len(passed),
      "new_game_home_leagues_not_previously_in_fixture_register":
         count["game_edition_home_league_identified"],
      "previous_independent_fixture_evidence_corroborated":
         count["previous_fixture_evidence_corroborated"],
      "ambiguous_source_or_game_names":len(reviews),
      "source_game_name_controlled_alias":count["source_game_name_controlled_alias"],
      "per_edition_matching":dict(Counter(str(x[0]) for x in passed)),
      "game_clubs_with_no_exact_game_team_name":sum(by_edition.values())-len(seen)-len(reviews),
      "no_game_team_id_only_joins":True,"no_cross_year_inheritance":True,
      "direct_game_league_name_not_claimed_independent_fixture_verified":True,
      "no_career_activation":True,"modified_squads":False,
    }
    (out/"FIFA_GAME_EDITION_LEAGUE_NAME_MATCH_AUDIT.json").write_text(
         json.dumps(summary,indent=2),encoding="utf-8")
    return summary

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--original",required=True)
    p.add_argument("--teams",required=True)
    p.add_argument("--registry")
    p.add_argument("--output",required=True)
    opts=p.parse_args()
    print(json.dumps(audit(opts.original,opts.teams,opts.output,opts.registry),indent=2))

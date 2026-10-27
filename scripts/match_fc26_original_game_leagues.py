"""Cross-match authentic pinned FC26 team/league links by same-game club name.

The input came from bundled FC26 game template tables teams, leagues and
leagueteamlinks at a pinned public binary archive. Cross-reference current
original FC26 club names only, never blindly trust unrelated numeric IDs.
"""
from __future__ import annotations
import argparse,csv,json,sqlite3
from collections import Counter,defaultdict
from pathlib import Path
from world_historical_competition_registry import canonical,cup_group

PIN="7592f1734afff43d7dbc7161565732e9ba3d28bc"
VERSION="fc26-original-game-team-league-corroboration-v1"
def collect(source_csv,registry_sqlite,output):
    d=Path(output);d.mkdir(parents=True,exist_ok=True)
    with open(source_csv,encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    required={"Edition","Team_ID","Team","League_ID","League",
       "Tier","Gender","Is_Women_League","Is_International_League"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("Not an extracted original FC26 game teams link table")
    members=defaultdict(list);league_data=defaultdict(set);nations=Counter()
    for row in rows:
        if row["Edition"]!="2026" or not row["Team_ID"].isdigit() or not row["League_ID"].isdigit():
            raise ValueError("Non-FC26 or non-original ID in team league source")
        if row["Gender"]!="0" or row["Is_Women_League"]!="0" or row["Is_International_League"]!="0":
            nations["filtered_non_mens_domestic"]+=1
            continue
        if row["Tier"] not in ("1","2","3","4"):
            nations["filtered_non_playable_regime"]+=1
            continue
        league=row["League"]
        if not league or cup_group(league) or "rest of world" in league.casefold():
            nations["filtered_cup_or_other_group"]+=1
            continue
        data=(row["Team_ID"],row["Team"],row["League_ID"],league,int(row["Tier"]))
        members[canonical(row["Team"])].append(data)
        league_data[row["League_ID"]].add((league,int(row["Tier"])))
    with sqlite3.connect(f"file:{Path(registry_sqlite).resolve()}?mode=ro",uri=True) as db:
        games=db.execute("SELECT club_key,club FROM edition_club_competitions WHERE edition=2026").fetchall()
        evidenced={x[0] for x in db.execute("""
          SELECT club_key FROM expanded_historical_club_starting_leagues
          WHERE edition=2026 AND starting_competition IS NOT NULL""")}
    game_names=defaultdict(list)
    for key,name in games:game_names[canonical(name)].append((key,name))
    matches=[];conflicts=[];counts=Counter()
    for k,clubs in sorted(game_names.items()):
        source=members.get(k,[])
        if not source:continue
        if len(clubs)!=1 or len({(x[0],x[2]) for x in source})!=1:
            conflicts.append((clubs[0][0],clubs[0][1],"name_or_source_identity_collision"))
            continue
        club_key,name=clubs[0];team_id,team_name,lid,league,tier=source[0]
        if len(league_data[lid])!=1:
            conflicts.append((club_key,name,"original_game_league_id_conflicting_labels"))
            continue
        matches.append((2026,club_key,name,team_id,team_name,lid,league,tier,
                        "already_sourced" if club_key in evidenced else "new_game_league",
                        "unique_same_edition_game_name_pinned_club_id"))
        counts["already_sourced" if club_key in evidenced else "new_game_league"]+=1
    with (d/"FC26_ORIGINAL_GAME_CLUB_LEAGUES.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f);w.writerow(("Edition","Original_Club_Key","Original_Club",
           "Game_Team_ID","Game_Team","Game_League_ID","Game_League",
           "Tier","Coverage","Evidence_Method"));w.writerows(matches)
    with (d/"FC26_GAME_CLUB_IDENTITY_CONFLICTS.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f);w.writerow(("Original_Club_Key","Club","Issue"));w.writerows(conflicts)
    report={"version":VERSION,"source_commit":PIN,"original_game_year":2026,
       "original_mens_game_clubs_in_edition":len(games),
       "pinned_original_game_team_league_source_rows":len(rows),
       "valid_original_game_team_names":len(members),
       "same_game_unique_club_identity_league_links":len(matches),
       "new_club_seasons_with_original_game_league":counts["new_game_league"],
       "already_sourced_club_seasons_corroborated":counts["already_sourced"],
       "identity_collisions_held_for_review":len(conflicts),
       "source_filters":dict(nations),"no_cross_edition_reuse":True,
       "no_career_activation":True,"squads_modified":False}
    (d/"FC26_ORIGINAL_TEAM_LEAGUE_MATCH_AUDIT.json").write_text(json.dumps(report,indent=2))
    return report
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--source",required=True)
    p.add_argument("--registry",required=True);p.add_argument("--output",required=True)
    a=p.parse_args()
    print(json.dumps(collect(a.source,a.registry,a.output),indent=2))

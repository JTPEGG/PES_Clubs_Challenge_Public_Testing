"""Recover real 2008/09–2015/16 European league members from archived matches.

Source: Kaggle European Soccer Database mirrored at a pinned GitHub commit.
Eleven real first divisions; country, season, team IDs are linked through
Match, League, Country, Team. No matching to future season, no player edits.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,sqlite3
from collections import defaultdict,Counter
from pathlib import Path

VERSION="european-soccer-historical-2008-16-top-division-members-v1"
SOURCE_REPO="judithagara/European-Soccer-Database"
SOURCE_COMMIT="7c83ef15d74c669b92663300de8e1454441939b9"
SOURCE_URL=f"https://raw.githubusercontent.com/{SOURCE_REPO}/{SOURCE_COMMIT}/database.sqlite.zip"
COUNTRIES={
 "Belgium":("be.1","Belgium","Pro League"),
 "England":("en.1","England","Premier League"),
 "France":("fr.1","France","Ligue 1"),
 "Germany":("de.1","Germany","Bundesliga"),
 "Italy":("it.1","Italy","Serie A"),
 "Netherlands":("nl.1","Netherlands","Eredivisie"),
 "Poland":("pl.1","Poland","Ekstraklasa"),
 "Portugal":("pt.1","Portugal","Primeira Liga"),
 "Scotland":("sco.1","Scotland","Premier Division / Premiership"),
 "Spain":("es.1","Spain","La Liga"),
 "Switzerland":("ch.1","Switzerland","Super League"),
}
def extract(source_sqlite,output,source_checksum=""):
    d=Path(output);d.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(f"file:{Path(source_sqlite).resolve()}?mode=ro",uri=True) as db:
        tables={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"Match","League","Team","Country"}.issubset(tables):
            raise ValueError("Archived source does not contain four original lookup tables")
        names={int(k):str(v) for k,v in db.execute("SELECT id,name FROM Country")}
        leagues={int(k):int(v) for k,v in db.execute("SELECT id,country_id FROM League")}
        teams={int(k):str(v).strip() for k,v in db.execute("SELECT team_api_id,team_long_name FROM Team")}
        matches=db.execute("""SELECT season,league_id,home_team_api_id,away_team_api_id
                         FROM Match ORDER BY season,league_id,id""").fetchall()
    seasons=defaultdict(lambda:dict(teams=set(),matches=0))
    skipped=Counter()
    for season,lid,h,a in matches:
        # Original season '2008/2009' starts the FIFA 2009 game edition.
        if not isinstance(season,str) or len(season)!=9 or season[4]!="/" or not(
            season[:4].isdigit() and season[5:].isdigit()):
            skipped["season_format_not_fifa_edition"]+=1;continue
        start=int(season[:4]);edition=start+1
        if not 2009<=edition<=2016 or int(season[5:])!=start+1:
            skipped["unsupported_source_starting_year"]+=1;continue
        country=names.get(leagues.get(lid))
        if country not in COUNTRIES:
            skipped["source_country_not_approved"]+=1;continue
        pair=[teams.get(h),teams.get(a)]
        if any(not t for t in pair) or pair[0]==pair[1]:
            raise ValueError("Historical match team identity missing or duplicated")
        key=(edition,country)
        seasons[key]["teams"].update(pair)
        seasons[key]["matches"]+=1
    season_rows=[];club_rows=[];issues=[]
    for (edition,country),data in sorted(seasons.items()):
        code,country_name,competition=COUNTRIES[country]
        roster=sorted(data["teams"])
        size=len(roster)
        games=data["matches"]
        if not 10<=size<=24 or games<size*5:
            issues.append((edition,country,code,size,games,"insufficient_dated_results"))
            continue
        count=f"{edition}:{code}"
        season_rows.append((edition,f"{edition-1}/{edition%100:02d}",
            code,country_name,1,competition,count,size,games,
            SOURCE_URL,source_checksum,
            "season_match_team_ids_crosschecked_non_game_id"))
        for team in roster:
            club_rows.append((edition,f"{edition-1}/{edition%100:02d}",
                code,country_name,1,team,SOURCE_URL,source_checksum,
                "independent_match_team_not_original_fifa_identity"))
    def write(name,header,rows):
        with (d/name).open("w",newline="",encoding="utf-8-sig") as f:
            w=csv.writer(f);w.writerow(header);w.writerows(rows)
    write("EUROPEAN_MATCH_DOMESTIC_LEAGUE_SEASONS.csv",
       ("Edition","Starting_Season","League_Code","Country","Tier",
        "Competition","Edition_Code","Source_Clubs","Match_Rows",
        "Source_URL","Source_SHA256","Evidence_Status"),season_rows)
    write("EUROPEAN_MATCH_DOMESTIC_LEAGUE_CLUBS.csv",
       ("Edition","Starting_Season","League_Code","Country","Tier",
        "Club","Source_URL","Source_SHA256","Evidence_Status"),club_rows)
    write("EUROPEAN_MATCH_INCOMPLETE.csv",
       ("Edition","Country","League_Code","Source_Clubs","Match_Rows","Reason"),issues)
    summary={
       "version":VERSION,"source_url":SOURCE_URL,"source_sha256":source_checksum,
       "source_11_countries":len(COUNTRIES),
       "complete_season_divisions":len(season_rows),
       "independent_season_club_memberships":len(club_rows),
       "incomplete_seasons":len(issues),"skipped_match_rows":dict(skipped),
       "fifa_editions":sorted({x[0] for x in season_rows}),
       "original_fifa_club_ids_certified":0,"historical_careers_ready":False,
       "player_data_modified":False}
    (d/"EUROPEAN_MATCH_SOURCE_AUDIT.json").write_text(
       json.dumps(summary,indent=2),encoding="utf-8")
    return summary

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--sha256",default="")
    a=p.parse_args()
    print(json.dumps(extract(a.source,a.output,a.sha256),indent=2))

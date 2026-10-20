"""Bulk recover independently dated domestic league member lists for FIFA/FC.

One file per ORIGINAL starting season; club names are provisional game-identity
evidence, not definitive FIFA-ID matches and not manufactured squads.
Uses immutable CC0 OpenFootball and footballcsv source snapshots.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,sqlite3,urllib.request,urllib.error
from collections import Counter
from pathlib import Path
from scripts.collect_historical_national_league_feeders import parse_source
from scripts.collect_legacy_multicountry_leagues import source_teams_csv

WORLD="42df8203e73e922cdfa36104e3acee3aea1f2bc0"
EUROPE="63df627f3c87ce71708f016522ea236cf74332c3"
SOUTH="f51b2dcf5e0fab9f0abd5206ab8c24a413e67277"
SOCCERVERSE="d4a8cc571b37d54371e2623947d39f87325e047c"
REPOS={"world":f"https://raw.githubusercontent.com/openfootball/world/{WORLD}",
       "europe":f"https://raw.githubusercontent.com/openfootball/europe/{EUROPE}",
       "south":f"https://raw.githubusercontent.com/openfootball/south-america/{SOUTH}",
       "soccerverse":f"https://raw.githubusercontent.com/footballcsv/cache.soccerverse/{SOCCERVERSE}"}
EDITIONS=tuple(y for y in range(2005,2028) if y!=2025)
VERSION="historical-season-source-gap-backfill-v1"
# Fixed-pinned repositories, documented source seasons, no cross-edition copying.
TEXT_FAMILIES=(
 ("jp.1","Japan",1,"J1 League","world","asia/japan/{year}_jp1.txt","calendar"),
 ("cn.1","China",1,"Chinese Super League","world","asia/china/{year}_cn1.txt","calendar"),
 ("au.1","Australia",1,"A-League","world","pacific/australia/{season}_au1.txt","season"),
 ("mx.1","Mexico",1,"Liga MX","world","north-america/mexico/{season}_mx1.txt","season"),
 ("br.1","Brazil",1,"Série A","south","brazil/{year}_br1.txt","calendar"),
 ("tr.1","Turkey",1,"Süper Lig","europe","turkey/{season}_tr1.txt","season"),
 ("co.1","Colombia",1,"Primera A","south","colombia/{year}_co1.txt","calendar"),
)
# FIFA 2005-2010 legacy already collected; 2011-2019 independent season
# CSVs may fill gaps where the original JSON export has no league.
CSV_FAMILIES={
 "at.1":("Austria","Bundesliga","at"),
 "nl.1":("Netherlands","Eredivisie","nl"),
 "pt.1":("Portugal","Primeira Liga","pt"),
 "de.1":("Germany","Bundesliga","de"),
 "es.1":("Spain","La Liga","es"),
 "fr.1":("France","Ligue 1","fr"),
 "it.1":("Italy","Serie A","it"),
 "ar.1":("Argentina","Primera División","ar"),
}
def source_targets(edition,already):
    if edition not in EDITIONS:
        raise ValueError("No unsupported edition or FC25 year")
    season=f"{edition-1}-{edition%100:02d}"
    year=edition-1
    out=[]
    for code,country,tier,name,repo,pattern,mapping in TEXT_FAMILIES:
        if (edition,code) not in already and edition>=2011:
            url=REPOS[repo]+"/"+pattern.format(season=season,year=year)
            out.append((edition,str(year) if mapping=="calendar" else season,
                        code,country,tier,name,url,"footballtxt"))
    for code,(country,name,tag) in CSV_FAMILIES.items():
        if 2011<=edition<=2019 and (edition,code) not in already:
            url=REPOS["soccerverse"]+f"/{season}/{tag}.csv"
            out.append((edition,season,code,country,1,name,url,"fixturecsv"))
    return out

def source_read(url):
    request=urllib.request.Request(url,headers={
        "User-Agent":"PES-Clubs-Challenge-V2-Source-Provenance-Collector"})
    with urllib.request.urlopen(request,timeout=30) as handle:
        raw=handle.read()
    return raw.decode("utf-8-sig"),hashlib.sha256(raw).hexdigest()

def parse_fixture_source(content,kind):
    if kind=="footballtxt":
        expected,teams,fixtures=parse_source(content)
        if not (10<=expected<=32 and expected==len(teams) and fixtures>=50):
            raise ValueError(f"declared={expected}, parsed={len(teams)}, fixtures={fixtures}")
        return teams,fixtures
    if kind=="fixturecsv":
        return source_teams_csv(content)
    raise ValueError("Unrecognised immutable source")

def collect(registry_sqlite,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(f"file:{Path(registry_sqlite).resolve()}?mode=ro",uri=True) as db:
        existing={(int(y),str(code).split(":",1)[1])
                  for code,y in db.execute("SELECT code,edition FROM competition_seasons")}
    leagues=[];clubs=[];failures=[];families=Counter()
    for edition in EDITIONS:
        for year,season,code,country,tier,name,url,kind in source_targets(edition,existing):
            try:
                content,digest=source_read(url)
                members,fixture_count=parse_fixture_source(content,kind)
            except urllib.error.HTTPError as err:
                if err.code!=404:raise
                failures.append((year,code,url,"pinned_file_unavailable"))
                families["missing_pinned_file"]+=1
                continue
            except ValueError as err:
                failures.append((year,code,url,"unusable_fixture_source:"+str(err)))
                families["unusable_source"]+=1
                continue
            if (year,code) in existing:
                raise ValueError("Existing game-season competition source overwritten")
            leagues.append((year,season,code,country,tier,name,url,
                 "independent_pinned_source_fixture_team_count_checked",
                 len(members),fixture_count,digest))
            for member in members:
                clubs.append((year,season,code,country,tier,name,member,
                     url,digest,"independent_fixture_membership_pending_game_id"))
            families[code]+=1
    def dump(path,header,rows):
        with (output/path).open("w",encoding="utf-8-sig",newline="") as f:
            writer=csv.writer(f);writer.writerow(header);writer.writerows(rows)
    dump("EXPANDED_DOMESTIC_LEAGUE_SEASONS.csv",
       ("Edition","Start_Season","League_Code","Country","Tier","Competition",
        "Source_URL","Source_Status","Parsed_Teams","Fixture_Count","Source_SHA256"),leagues)
    dump("EXPANDED_DOMESTIC_SOURCE_CLUBS.csv",
       ("Edition","Start_Season","League_Code","Country","Tier","Competition",
        "Fixture_Club","Source_URL","Source_SHA256","Evidence_Status"),clubs)
    dump("EXPANDED_SOURCE_REJECTIONS.csv",
       ("Edition","League_Code","Source_URL","Reason"),failures)
    audit={"version":VERSION,"base_existing_division_seasons":len(existing),
      "new_domestic_league_seasons":len(leagues),
      "new_fixture_club_seasons":len(clubs),
      "missing_or_incomplete_sources":len(failures),
      "by_source_competition":dict(families),
      "source_pins":{"world":WORLD,"europe":EUROPE,"south-america":SOUTH,
                      "soccerverse":SOCCERVERSE},
      "licensed_source_basis":"OpenFootball and footballcsv CC0; source participant evidence only",
      "year_specific":True,"game_id_assignments_are_provisional":True,
      "career_ready":False,"game_squads_generated":0}
    (output/"EXPANDED_HISTORICAL_SOURCE_AUDIT.json").write_text(
        json.dumps(audit,indent=2),encoding="utf-8")
    return audit

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--registry",required=True)
    a.add_argument("--output",required=True)
    args=a.parse_args()
    print(json.dumps(collect(args.registry,args.output),indent=2))

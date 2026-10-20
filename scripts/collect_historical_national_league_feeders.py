"""Recover actual National League feeder clubs from pinned CC0 schedules.

This establishes season-specific NON-FIFA feeder membership evidence only.
It never invents players, promotion results, or a 2026/27 feeder club pool.
"""
import argparse,csv,hashlib,json,re,urllib.error,urllib.request
from pathlib import Path

PIN="9ee7a0c351805c99cc334478a9bf04b7d0432fec"
BASE=f"https://raw.githubusercontent.com/openfootball/england/{PIN}"
FORMAT_OLD=re.compile(r"^\s*(?:(?:\d{1,2}:\d{2})\s+)?(?P<a>.*?)\s{2,}"
 r"\d{1,2}-\d{1,2}(?:\s+\([^)]+\))?\s{2,}(?P<b>.*?)\s*$")
FORMAT_NEW=re.compile(r"^\s*(?:(?:\d{1,2}:\d{2})\s+)?(?P<a>.*?)\s{2,}"
 r"v\s+(?P<b>.*?)\s{2,}\d{1,2}-\d{1,2}(?:\s+\([^)]+\))?\s*$")

def parse_source(txt):
    match=re.search(r"^#\s*Teams\s+(\d+)\s*$",txt,re.M)
    if match is None:raise ValueError("No independently declared team count")
    count=int(match.group(1));teams=set();games=0
    for line in txt.splitlines():
        m=FORMAT_OLD.match(line) or FORMAT_NEW.match(line)
        if m:
            a,b=(m.group("a").strip(),m.group("b").strip())
            if not a or not b:raise ValueError("Invalid fixture")
            teams.update((a,b));games+=1
    return count,sorted(teams),games

def collect(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    leagues=[];clubs=[];missing=[]
    for y in range(2016,2028):
        season=f"{y-1}-{y%100:02d}"
        url=f"{BASE}/{season}/5-nationalleague.txt"
        try:
            req=urllib.request.Request(url,headers={
                "User-Agent":"PES-V2-Historical-Football-Competition-Source"})
            with urllib.request.urlopen(req,timeout=20) as response:
                raw=response.read()
        except urllib.error.HTTPError as ex:
            if ex.code!=404:raise
            missing.append((y,season,url,"no_pinned_source_file"))
            continue
        expected,teams,fixtures=parse_source(raw.decode("utf-8-sig"))
        status="source_team_list_complete" if expected==len(teams) and fixtures>=50 else "partial_or_conflicting_source"
        sha=hashlib.sha256(raw).hexdigest()
        leagues.append((y,season,"ENG:NL",5,"National League",expected,len(teams),
           fixtures,status,url,sha))
        if status=="source_team_list_complete":
            for team in teams:
                clubs.append((y,season,"ENG:NL",5,team,
                     "fixture_member_not_game_squad",url,sha))
        else:missing.append((y,season,url,status))
    def write(name,headers,records):
        with (out/name).open("w",newline="",encoding="utf-8-sig") as f:
            w=csv.writer(f);w.writerow(headers);w.writerows(records)
    write("NATIONAL_LEAGUE_HISTORICAL_FEEDER_CLUBS.csv",
       ("Edition","Starting_Season","Competition_Code","Tier","Club",
       "Evidence_Status","Fixture_URL","Source_SHA256"),clubs)
    write("NATIONAL_LEAGUE_FIXTURE_SOURCE_COVERAGE.csv",
       ("Edition","Starting_Season","Competition_Code","Tier","League",
       "Declared_Teams","Parsed_Teams","Fixture_Records","Status",
       "URL","SHA256"),leagues)
    write("NATIONAL_LEAGUE_UNVERIFIED_SEASONS.csv",
       ("Edition","Starting_Season","URL","Unverified_Reason"),missing)
    report={"source_commit":PIN,"edition_seasons_checked":12,
        "complete_feeder_seasons":len(leagues)-sum(x[8]!="source_team_list_complete" for x in leagues),
        "recorded_season_club_memberships":len(clubs),
        "missing_or_unverified_seasons":len(missing),
        "no_fictitious_clubs_created":True,
        "lower_regional_boundary_remains_open":True,"global_career_ready":False}
    (out/"NATIONAL_LEAGUE_FEEDER_SOURCE_AUDIT.json").write_text(json.dumps(report,indent=2))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",required=True)
    a=p.parse_args();print(json.dumps(collect(a.output),indent=2))

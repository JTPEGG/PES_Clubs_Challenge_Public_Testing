"""Extend historical men's domestic season sources without copying later-year teams.

Pinned CC0 Football.TXT evidence: unfilled English divisions, MLS (calendar
year) and Argentina Primera (calendar year). Original FIFA source and careers
are read-only; successful fixture parse is not FIFA club-identity validation.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,urllib.error,urllib.request
from collections import Counter
from pathlib import Path
from scripts.collect_historical_national_league_feeders import parse_source

ENGLAND_PIN="9ee7a0c351805c99cc334478a9bf04b7d0432fec"
WORLD_PIN="42df8203e73e922cdfa36104e3acee3aea1f2bc0"
SOUTH_AMERICA_PIN="f51b2dcf5e0fab9f0abd5206ab8c24a413e67277"
ENGLAND_BASE=f"https://raw.githubusercontent.com/openfootball/england/{ENGLAND_PIN}"
WORLD_BASE=f"https://raw.githubusercontent.com/openfootball/world/{WORLD_PIN}"
SOUTH_AMERICA_BASE=f"https://raw.githubusercontent.com/openfootball/south-america/{SOUTH_AMERICA_PIN}"
ENGLISH_FILES={
 "en.1":(1,"Premier League","1-premierleague.txt"),
 "en.2":(2,"Championship","2-championship.txt"),
 "en.3":(3,"League One","3-league1.txt"),
 "en.4":(4,"League Two","4-league2.txt"),
}
DE_PIN="c34532ab6950aa0089ef1c736ffdb8c818c3356f"
ES_PIN="80035a93dd4920985af52aa097a54a6fb888563b"
IT_PIN="48954d163c312aa705efacb64f771267031fe6eb"
EU_PIN="63df627f3c87ce71708f016522ea236cf74332c3"
DE_BASE=f"https://raw.githubusercontent.com/openfootball/deutschland/{DE_PIN}"
ES_BASE=f"https://raw.githubusercontent.com/openfootball/espana/{ES_PIN}"
IT_BASE=f"https://raw.githubusercontent.com/openfootball/italy/{IT_PIN}"
EU_BASE=f"https://raw.githubusercontent.com/openfootball/europe/{EU_PIN}"
# Tier-two/three fixtures previously absent from the pinned JSON export,
# but present in the independently pinned source-season text repositories.
MORE_TIERS=(
  ("de.3","Germany",3,"3. Liga",DE_BASE,"3-liga3.txt","germany"),
  ("es.2","Spain",2,"Segunda División",ES_BASE,"2-liga2.txt","spain"),
  ("it.2","Italy",2,"Serie B",IT_BASE,"2-serieb.txt","italy"),
)
VERSION="pinned-domestic-competition-supplement-v2"
EDITIONS=tuple(y for y in range(2005,2028) if y!=2025)

def source_targets(edition,available):
    """Map FIFA edition to REAL season starts; never use 2026 fixtures in FIFA26."""
    if edition not in EDITIONS:
        raise ValueError("No playable FC25 source and no invented future edition")
    season=f"{edition-1}-{edition%100:02d}"
    rows=[]
    if edition>=2011:
        for code,(tier,name,file) in ENGLISH_FILES.items():
            if (edition,code) not in available:
                rows.append((edition,season,code,"England",tier,name,
                             f"{ENGLAND_BASE}/{season}/{file}","england"))
    if edition>=2011:
        for code,country,tier,name,base,filename,family in MORE_TIERS:
            if (edition,code) not in available:
                rows.append((edition,season,code,country,tier,name,
                             f"{base}/{season}/{filename}",family))
        if (edition,"fr.2") not in available:
            rows.append((edition,season,"fr.2","France",2,"Ligue 2",
                 f"{EU_BASE}/france/{season}_fr2.txt","france"))
    source_year=edition-1
    if (edition,"us.mls") not in available:
        rows.append((edition,str(source_year),"us.mls","United States / Canada",1,
           "Major League Soccer",
           f"{WORLD_BASE}/north-america/major-league-soccer/{source_year}_mls.txt","mls"))
    if (edition,"ar.1") not in available:
        rows.append((edition,str(source_year),"ar.1","Argentina",1,
            "Primera División",
            f"{SOUTH_AMERICA_BASE}/argentina/{source_year}_ar1.txt","argentina"))
    return rows

def fetch_source(url):
    req=urllib.request.Request(url,headers={
        "User-Agent":"PES-V2-Men-Historical-Competition-Pinned-Supplement"})
    with urllib.request.urlopen(req,timeout=25) as response:
        payload=response.read()
    return payload.decode("utf-8-sig"),hashlib.sha256(payload).hexdigest()

def collect(recent_catalog,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    with open(recent_catalog,encoding="utf-8-sig",newline="") as f:
        original=list(csv.DictReader(f))
    available={(int(row["Edition"]),row["Source_File"].removesuffix(".json"))
               for row in original if row["Source_Status"]=="source_team_list_available"}
    rows,teams,skipped=[],[],[]
    statuses=Counter()
    for edition in EDITIONS:
        for y,season,code,country,tier,name,url,family in source_targets(edition,available):
            try:
                raw,digest=fetch_source(url)
            except urllib.error.HTTPError as e:
                if e.code!=404:raise
                skipped.append((edition,season,code,url,"no_pinned_source_file"))
                statuses["not_in_pinned_archive"]+=1
                continue
            try:
                declared,members,fixtures=parse_source(raw)
            except ValueError as e:
                skipped.append((edition,season,code,url,
                                "unusable_source:"+str(e)))
                statuses["unverified_source"]+=1
                continue
            if declared!=len(members) or fixtures<50 or declared<10:
                skipped.append((edition,season,code,url,"incomplete_or_wrong_team_count"))
                statuses["unverified_source"]+=1
                continue
            rows.append((y,season,code,country,tier,name,url,
                         "pinned_fixture_membership_checked",declared,
                         len(members),fixtures,digest))
            for member in members:
                teams.append((y,season,code,country,tier,name,member,
                    url,digest,"independent_fixture_club_not_game_identity"))
            statuses[family]+=1
    def export(filename,columns,items):
        with (out/filename).open("w",encoding="utf-8-sig",newline="") as handle:
            w=csv.writer(handle);w.writerow(columns);w.writerows(items)
    export("PINNED_SUPPLEMENT_DOMESTIC_LEAGUE_SEASONS.csv",
        ("Edition","Start_Season","League_Code","Country","Tier","Competition",
         "Source_URL","Source_Status","Declared_Teams","Parsed_Teams",
         "Parsed_Fixtures","Source_SHA256"),rows)
    export("PINNED_SUPPLEMENT_DOMESTIC_SOURCE_CLUBS.csv",
        ("Edition","Start_Season","League_Code","Country","Tier","Competition",
         "Fixture_Club","Source_URL","Source_SHA256","Evidence_Status"),teams)
    export("PINNED_SUPPLEMENT_MISSING_AND_UNVERIFIED.csv",
        ("Edition","Start_Season","League_Code","Source_URL","Reason"),skipped)
    result={
      "version":VERSION,"pinned_england":ENGLAND_PIN,
      "pinned_world":WORLD_PIN,"pinned_south_america":SOUTH_AMERICA_PIN,
      "pinned_de":DE_PIN,"pinned_es":ES_PIN,"pinned_it":IT_PIN,
      "pinned_europe":EU_PIN,
      "licence":"CC0 per pinned OpenFootball repositories",
      "editions_considered":len(EDITIONS),
      "additional_league_seasons":len(rows),
      "additional_independent_club_seasons":len(teams),
      "source_family_counts":dict(statuses),
      "missing_or_unverified_season_files":len(skipped),
      "calendar_mapping":"edition 2026 uses calendar-2025 MLS and Argentina, never 2026",
      "all_links_staging_only":True,"careers_ready":False,
      "historical_player_rosters_created":0,
    }
    (out/"PINNED_SUPPLEMENT_AUDIT.json").write_text(json.dumps(result,indent=2))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--recent",required=True)
    p.add_argument("--output",required=True)
    opt=p.parse_args()
    print(json.dumps(collect(opt.recent,opt.output),indent=2))

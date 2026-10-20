"""Recover 2004/05–2009/10 England tier 1–4 membership from CC0 Football.TXT.

This supplements (never overwrites) historical FIFA 05–10 sources that lack
competition labels. Original full fixture source pinned to an immutable
OpenFootball England commit. Never assign by approximate team-name similarity.
"""
import argparse,csv,hashlib,json,re,sqlite3,urllib.request
from collections import defaultdict
from pathlib import Path
from scripts.collect_openfootball_historical_competitions import namekey,match_club

PIN="9ee7a0c351805c99cc334478a9bf04b7d0432fec"
BASE=f"https://raw.githubusercontent.com/openfootball/england/{PIN}"
SOURCE_FILES={
 1:("1-premierleague.txt","Premier League"),
 2:("2-championship.txt","Championship"),
 3:("3-league1.txt","League One"),
 4:("4-league2.txt","League Two")
}
# A fixture result needs a real numeric score with two or more whitespace
# separators between team and result. Text headings cannot become clubs.
MATCH=re.compile(r"^\s*(?:(?:\d{1,2}:\d{2})\s+)?"
 r"(?P<home>.*?)\s{2,}(?P<score>\d{1,2}-\d{1,2})"
 r"(?:\s+\([^)]+\))?\s{2,}(?P<away>.*?)\s*$")
TOTAL=re.compile(r"^#\s*Teams\s+(\d+)\s*$")

def teams_from_text(text):
    expected=None;teams=set();results=0
    for line in text.splitlines():
        if expected is None:
            m=TOTAL.match(line)
            if m:expected=int(m.group(1))
        hit=MATCH.match(line)
        if hit:
            teams.update((hit.group("home").strip(),hit.group("away").strip()))
            results+=1
    if not 10<=len(teams)<=30 or not results>=50:
        raise ValueError("Football.TXT fixtures have insufficient source teams")
    return teams,expected,results

def get_source(url):
    req=urllib.request.Request(url,headers={
         "User-Agent":"PES-Clubs-Challenge-V2-source-competition-audit"})
    with urllib.request.urlopen(req,timeout=30) as response:
        raw=response.read()
    return raw.decode("utf-8-sig"),hashlib.sha256(raw).hexdigest()

def build(clubs_sqlite,outdir):
    output=Path(outdir);output.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(f"file:{Path(clubs_sqlite).resolve()}?mode=ro",uri=True) as db:
        clubs=defaultdict(lambda:defaultdict(list))
        for edition,key,name in db.execute("""SELECT edition,club_key,name FROM clubs
            WHERE edition BETWEEN 2005 AND 2010"""):
            clubs[edition][namekey(name)].append((key,name))
    files=[];matches=[];review=[];used=set()
    for edition in range(2005,2011):
        folder=f"{edition-1}-{str(edition)[-2:]}"
        for tier,(filename,competition) in SOURCE_FILES.items():
            url=f"{BASE}/{folder}/{filename}"
            txt,sha=get_source(url)
            teams,expected,fixtures=teams_from_text(txt)
            usable=expected==len(teams)
            validated=0
            for name in sorted(teams):
                pair=clubs[edition].get(namekey(name),[])
                if usable and len(pair)==1:
                    key,actual=pair[0]
                    if (edition,key) in used:
                        raise ValueError("Club assigned to two domestic leagues")
                    used.add((edition,key))
                    matches.append((edition,folder,tier,competition,
                       name,actual,key,url,sha,"exact_unique_name_provisional"))
                    validated+=1
                else:
                    review.append((edition,folder,tier,competition,name,
                       "source_teams_count_disagreement" if not usable else
                       "ambiguous_name" if len(pair)>1 else "name_needs_review",url))
            files.append((edition,folder,tier,competition,url,len(teams),
                          expected,fixtures,validated,sha,
                          "parsed_source_verified_team_count" if usable
                          else "source_team_count_disagreement"))
    def dump(name,headers,rows):
        with (output/name).open("w",newline="",encoding="utf-8-sig") as f:
            wr=csv.writer(f);wr.writerow(headers);wr.writerows(rows)
    dump("ENGLAND_2005_2010_FOOTBALLTXT_SOURCE_FILES.csv",
         ("FIFA_Edition","Season","Tier","Competition","Source_URL",
          "Parsed_Teams","Source_Declared_Teams","Fixture_Rows",
          "Exact_Matched_FIFA_Clubs","Source_SHA256","Status"),files)
    dump("ENGLAND_2005_2010_PROVISIONAL_CLUB_COMPETITIONS.csv",
         ("FIFA_Edition","Season","Tier","Competition","Source_Team",
         "FIFA_Club","FIFA_Club_Key","Source_URL","Source_SHA256",
         "Match_Status"),matches)
    dump("ENGLAND_2005_2010_CLUB_NAME_REVIEW.csv",
         ("FIFA_Edition","Season","Tier","Competition","Source_Team",
          "Reason","Source_URL"),review)
    outcome=dict(version="historical-openfootball-legacy-england-v1",
       pinned_source_commit=PIN,source_files=len(files),
       checked_source_teams=sum(x[5] for x in files),
       exact_source_club_matches=len(matches),
       unmatched_or_ambiguous=len(review),
       full_world_ready=False,original_source_unchanged=True,
       no_fuzzy_matches=True)
    (output/"ENGLAND_2005_2010_SOURCE_MEMBERSHIP_AUDIT.json").write_text(
       json.dumps(outcome,indent=2))
    return outcome

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--catalog",required=True);p.add_argument("--output",required=True)
    a=p.parse_args()
    print(json.dumps(build(a.catalog,a.output),indent=2))

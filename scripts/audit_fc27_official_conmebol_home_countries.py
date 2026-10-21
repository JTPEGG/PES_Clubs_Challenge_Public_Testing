"""Check the 40 FC27 CONMEBOL cup-bucket clubs' real national associations.

The 2026 CONMEBOL Libertadores/Sudamericana official team directory states
each team's country. Country alone does NOT prove its 2026 domestic division.
Only a unique SAME-SEASON independently dated domestic fixture participant
may create a provisional home-division candidate. Cup buckets remain separate.
"""
from __future__ import annotations
import argparse,csv,json,sqlite3,urllib.request,hashlib
from collections import Counter,defaultdict
from html.parser import HTMLParser
from pathlib import Path
from world_historical_competition_registry import canonical

VERSION="fc27-conmebol-official-country-first-v1"
SOURCES={
 "CONMEBOL Libertadores":"https://gol.conmebol.com/libertadores/en/teams",
 "CONMEBOL Sudamericana":"https://gol.conmebol.com/sudamericana/en/teams",
}
COUNTRIES={"Argentina","Bolivia","Brazil","Chile","Colombia","Ecuador",
           "Paraguay","Peru","Uruguay","Venezuela"}
COUNTRY_REGISTRY={
 "Argentina":"Argentina","Bolivia":"Bolivia","Brazil":"Brazil",
 "Chile":"Chile","Colombia":"Colombia","Ecuador":"Ecuador",
 "Paraguay":"Paraguay","Peru":"Peru","Uruguay":"Uruguay",
 "Venezuela":"Venezuela"}
NAME_ALIASES={
 # Typographic error in the FC27 source; explicit single-name review only.
 "alianzaatltico":"alianzaatletico",
 "universidadcentral":"ucv",
 "universidadcentralevenezuela":"ucv",
 "independientedelvalle":"independientevalle",
 "lduquito":"lduquito",
}
def namekey(s):
    x=canonical(s)
    return NAME_ALIASES.get(x,x)

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__();self.items=[];self.ignore=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style","noscript"):self.ignore+=1
    def handle_endtag(self,tag):
        if tag in ("script","style","noscript") and self.ignore:self.ignore-=1
    def handle_data(self,data):
        if not self.ignore:
            x=" ".join(data.split()).strip()
            if x:self.items.append(x)

def parse_country_directory(content):
    parser=VisibleText();parser.feed(content)
    terms=parser.items
    mark=next((i for i,t in enumerate(terms) if t.casefold()=="all teams"),None)
    if mark is None:raise ValueError("No official competition teams directory")
    countries=defaultdict(set);pairs=[]
    for pos in range(mark+2,len(terms)):
        if terms[pos] in COUNTRIES and pos>0:
            club=terms[pos-1]
            if club in COUNTRIES or len(club)>110 or not club or club.casefold() in {
                 "loading","teams","image","follow us","see all","all teams"}:
                continue
            countries[namekey(club)].add(terms[pos])
            pairs.append((club,terms[pos]))
    if len(pairs)<25 or len(pairs)>150:
        raise ValueError(f"Official team country pairs corrupt: {len(pairs)}")
    return dict(countries),pairs

def retrieve(url):
    req=urllib.request.Request(url,headers={
      "User-Agent":"PES-Clubs-Challenge-Historical-Audit/1.0",
      "Accept":"text/html,application/xhtml+xml"})
    with urllib.request.urlopen(req,timeout=32) as f:
        data=f.read(6_000_000)
    return data.decode("utf-8","replace"),hashlib.sha256(data).hexdigest()

def audit(registry,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(f"file:{Path(registry).resolve()}?mode=ro",uri=True) as db:
        countries={code:country for code,country in db.execute(
            "SELECT code,country FROM competition_seasons WHERE edition=2027")}
        fixture=defaultdict(list)
        for code,name in db.execute(
            "SELECT competition_code,club_name FROM sourced_domestic_league_clubs WHERE edition=2027"):
            fixture[namekey(name)].append((code,countries[code]))
        source=db.execute("""SELECT e.club_key,e.club,e.original_source_league
              FROM edition_club_competitions e
              JOIN fc27_one_year_club_competition_alignment p
                 ON p.club_key=e.club_key AND p.edition=e.edition
              WHERE e.edition=2027 AND p.starting_competition IS NULL
              ORDER BY e.original_source_league,e.club""").fetchall()
    if len(source)!=40 or Counter(x[2] for x in source)!={
        "CONMEBOL Libertadores":20,"CONMEBOL Sudamericana":20}:
        raise ValueError("40 original CONMEBOL game bucket teams unexpectedly changed")
    official={}
    official_audit={}
    for label,url in SOURCES.items():
        page,digest=retrieve(url)
        clubs,pairs=parse_country_directory(page)
        official[label]=clubs
        official_audit[label]={"url":url,"sha256":digest,"clubs_and_country_observations":len(pairs)}
    candidates=[];unmatched=[];explicit=[];counts=Counter()
    for clubkey,name,group in source:
        countries_for_name=official[group].get(namekey(name),set())
        if len(countries_for_name)!=1:
            unmatched.append((clubkey,name,group,"official_country_missing_or_ambiguous",
                         " | ".join(sorted(countries_for_name))))
            counts["no_unique_official_country"]+=1
            continue
        ctry=next(iter(countries_for_name))
        assert ctry in COUNTRIES
        matching_domestic={(code,country) for code,country in fixture.get(namekey(name),[])
                           if COUNTRY_REGISTRY[ctry].casefold()==country.casefold()}
        if len(matching_domestic)==1:
            domestic=next(iter(matching_domestic))[0]
            evidence="official_continental_country_plus_unique_2026_domestic_fixture_name"
            counts["source_domestic_club_candidate"]+=1
        elif matching_domestic:
            domestic=""
            evidence="multiple_same_country_2026_domestic_fixture_matches_review"
            counts["domestic_division_collision"]+=1
        else:
            domestic=""
            evidence="association_identified_domestic_division_not_independently_verified"
            counts["national_country_only"]+=1
        candidates.append((clubkey,name,group,ctry,domestic,
             SOURCES[group],official_audit[group]["sha256"],evidence))
    def dump(name,header,rows):
        with (out/name).open("w",encoding="utf-8-sig",newline="") as f:
            w=csv.writer(f);w.writerow(header);w.writerows(rows)
    dump("FC27_CONMEBOL_NATIONAL_ASSOCIATIONS_REVIEW.csv",
       ("Original_Club_Key","Imported_Club","Continental_Source_Group",
        "Official_Club_Country","Domestic_Competition_Candidate","Official_Source_URL",
        "Official_2026_Team_Directory_SHA256","Confidence_Status"),candidates)
    dump("FC27_CONMEBOL_CLUBS_UNRECOGNISED_IN_OFFICIAL_2026_SOURCE.csv",
       ("Original_Club_Key","Imported_Club","Continental_Source_Group",
        "Reason","Possible_Countries"),unmatched)
    result={"edition":2027,"version":VERSION,"source_official_competitions":official_audit,
       "original_fc27_cup_group_clubs":len(source),
       "official_countries_uniquely_identified":len(candidates),
       "country_ambiguous_or_not_in_official_source":len(unmatched),
       "source_domestic_league_fixture_matches":counts["source_domestic_club_candidate"],
       "domestic_home_division_unresolved":len(source)-counts["source_domestic_club_candidate"],
       "country_known_but_domestic_membership_unsourced":counts["national_country_only"],
       "same_country_domestic_source_collisions":counts["domestic_division_collision"],
       "continents_are_not_leagues":True,"career_ready":False}
    (out/"FC27_CONMEBOL_ASSOCIATION_REVIEW_AUDIT.json").write_text(
        json.dumps(result,indent=2),encoding="utf-8")
    return result

if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--registry",required=True)
    a.add_argument("--output",required=True);args=a.parse_args()
    print(json.dumps(audit(args.registry,args.output),indent=2))

"""CC0 historical competition membership evidence from pinned OpenFootball JSON.

Original FIFA05–20 clubs mostly lack a league field. Recover *season-specific*
league membership using independent source match schedules. An exact name
match is provisional source corroboration, not proof of game roster identity.
Never assign a player to a new club, invent a division, or silently fuzzy-join.
All years and source SHA pinned. A source fixture club that does not exist in
the FIFA club list remains an unmatched review item.
"""
from __future__ import annotations

import argparse,csv,hashlib,json,sqlite3,urllib.request,unicodedata
from collections import defaultdict,Counter
from pathlib import Path

VERSION="openfootball-historical-domestic-membership-v1"
PIN="e6744429ee395bc86f247348c6184bb08d4eb361"
BASE=f"https://raw.githubusercontent.com/openfootball/football.json/{PIN}"
LEAGUES={
"en.1":("England",1,"Premier League"),
"en.2":("England",2,"Championship"),
"en.3":("England",3,"League One"),
"en.4":("England",4,"League Two"),
"de.1":("Germany",1,"Bundesliga"),
"de.2":("Germany",2,"2. Bundesliga"),
"de.3":("Germany",3,"3. Liga"),
"es.1":("Spain",1,"La Liga"),
"es.2":("Spain",2,"Segunda División"),
"it.1":("Italy",1,"Serie A"),
"it.2":("Italy",2,"Serie B"),
"fr.1":("France",1,"Ligue 1"),
"fr.2":("France",2,"Ligue 2"),
# Additional pinned domestic sources. Availability varies by season; a 404
# is recorded as a missing *source*, never imputed from a later season.
# Cup files (at.cup, uefa.cl, etc.) are deliberately excluded.
"ar.1":("Argentina",1,"Primera División"),
"at.1":("Austria",1,"Bundesliga"),
"at.2":("Austria",2,"2. Liga"),
"au.1":("Australia",1,"A-League Men"),
"be.1":("Belgium",1,"Belgian Pro League"),
"ch.1":("Switzerland",1,"Swiss Super League"),
"ch.2":("Switzerland",2,"Swiss Challenge League"),
"cz.1":("Czech Republic",1,"Czech First League"),
"dz.1":("Algeria",1,"Algerian Ligue 1"),
"eg.1":("Egypt",1,"Egyptian Premier League"),
"gr.1":("Greece",1,"Super League Greece"),
"hu.1":("Hungary",1,"Nemzeti Bajnokság I"),
"ma.1":("Morocco",1,"Botola Pro"),
"mx.1":("Mexico",1,"Liga MX"),
"nl.1":("Netherlands",1,"Eredivisie"),
"pt.1":("Portugal",1,"Primeira Liga"),
"ru.1":("Russia",1,"Russian Premier League"),
"ru.2":("Russia",2,"Russian First League"),
"sco.1":("Scotland",1,"Scottish Premiership"),
"tr.1":("Turkey",1,"Süper Lig"),
"tr.2":("Turkey",2,"TFF First League"),
}
def namekey(name):
    return "".join(x for x in unicodedata.normalize("NFKD",str(name)).casefold()
                   if x.isascii() and x.isalnum())
def match_club(source_name,club_index):
    """No Levenshtein or silently invented external clubs."""
    candidates=club_index.get(namekey(source_name),[])
    return candidates[0] if len(candidates)==1 else None

def source_season(edition):
    if not 2011<=edition<=2027:raise ValueError("Not in pinned JSON coverage")
    return f"{edition-1}-{str(edition)[-2:]}"

def matches_to_teams(data):
    if not isinstance(data,dict) or not isinstance(data.get("matches"),list):
        raise ValueError("Invalid fixture source schema")
    teams=set()
    for game in data["matches"]:
        for col in ("team1","team2"):
            name=game.get(col)
            if isinstance(name,str) and name.strip():
                teams.add(name.strip())
    return sorted(teams)

def fetch_json(url):
    req=urllib.request.Request(url,headers={
        "User-Agent":"PES-Clubs-Challenge-V2-historical-competition-audit",
        "Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=20) as r:
        payload=r.read()
    return json.loads(payload),hashlib.sha256(payload).hexdigest()

def generate(source_sqlite,out_dir,*,edition_min=2011,edition_max=2027):
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(f"file:{Path(source_sqlite).resolve()}?mode=ro",uri=True) as db:
        by_year=defaultdict(lambda:defaultdict(list))
        for year,key,name in db.execute("SELECT edition,club_key,name FROM clubs"):
            if edition_min<=year<=edition_max:
                by_year[year][namekey(name)].append((key,name))
        expected={x[0] for x in db.execute("SELECT edition FROM editions")}
    covered=[];observations=[];unmatched=[];source_teams=[];status=Counter()
    for year in range(edition_min,edition_max+1):
        if year not in expected:continue
        folder=source_season(year)
        for file,(country,tier,league) in LEAGUES.items():
            url=f"{BASE}/{folder}/{file}.json"
            try:
                data,sha=fetch_json(url)
            except urllib.error.HTTPError as e:
                if e.code==404:
                    status["unavailable_source_file"]+=1
                    covered.append((year,folder,file,country,league,tier,url,
                                    "file_missing",0,0,""))
                    continue
                raise
            teams=matches_to_teams(data)
            if len(teams)<8:
                covered.append((year,folder,file,country,league,tier,url,
                                "incomplete_source_teams",len(teams),0,sha))
                status["incomplete_source_teams"]+=1
                continue
            # Preserve every externally sourced league member, including
            # clubs that cannot yet be identified in the FIFA archive.
            # These rows are NOT playable squads and imply no automatic promotion.
            for team in teams:
                source_teams.append((year,folder,file,country,league,tier,
                    team,url,sha,"pinned_fixture_membership_not_game_identity"))
            source_matches=0
            for team in teams:
                index=by_year[year]
                matches=index.get(namekey(team),[])
                if len(matches)==1:
                    key,original=matches[0]
                    observations.append((year,folder,file,country,league,tier,
                      team,original,key,url,sha,"exact_unique_name_provisional"))
                    source_matches+=1
                else:
                    unmatched.append((year,file,country,league,team,
                                      "FIFA_same_name_ambiguous" if len(matches)>1
                                      else "FIFA_club_name_unmatched",url))
            covered.append((year,folder,file,country,league,tier,url,
                             "source_team_list_available",len(teams),source_matches,sha))
            status["processed_source_leagues"]+=1
            status["exact_matches"]+=source_matches
    # A club matched in two different league competitions is not automatically
    # eligible: it may be a cross-border or reserve-side homonym.
    club_matches=defaultdict(list)
    for o in observations:club_matches[(o[0],o[8])].append(o)
    valid=[o for o in observations if len(club_matches[(o[0],o[8])])==1]
    conflicts=[o for o in observations if len(club_matches[(o[0],o[8])])>1]
    def export(name,head,rows):
        with (out/name).open("w",encoding="utf-8-sig",newline="") as f:
            wr=csv.writer(f);wr.writerow(head);wr.writerows(rows)
    export("PINNED_OPENFOOTBALL_LEAGUES_BY_SEASON.csv",
           ("Edition","Starting_Season","Source_File","Country","Competition",
            "Tier","Source_URL","Source_Status","Source_Teams","Matched_FIFA_Clubs",
            "SHA256"),covered)
    export("PINNED_OPENFOOTBALL_ALL_SOURCE_TEAMS.csv",
           ("Edition","Starting_Season","League_Code","Country","Competition",
            "Tier","Fixture_Club","Source_URL","Source_SHA256","Evidence_Status"),
           source_teams)
    export("EXACT_HISTORICAL_CLUB_LEAGUE_MATCHES.csv",
           ("Edition","Starting_Season","League_Code","Country","Competition",
            "Tier","Fixture_Club","FIFA_Club","FIFA_Club_Key",
            "Source_URL","Source_SHA256","Verification_Status"),valid)
    export("CLUB_LEAGUE_NAME_MATCH_REVIEW.csv",
           ("Edition","League_Code","Country","Competition","Fixture_Club",
            "Match_Status","Source_URL"),unmatched)
    export("CROSS_LEAGUE_MATCH_CONFLICTS.csv",
           ("Edition","Starting_Season","League_Code","Country","Competition",
            "Tier","Fixture_Club","FIFA_Club","FIFA_Club_Key",
            "Source_URL","Source_SHA256","Verification_Status"),conflicts)
    report={"version":VERSION,"pinned_commit":PIN,
      "license":"CC0 public domain per openfootball/football.json",
      "source_catalogue_untouched":True,"global_career_ready":False,
      "source_leagues_available":sum(o[7]=="source_team_list_available" for o in covered),
      "independent_fixture_source_memberships":len(source_teams),
      "provisional_exact_club_memberships":len(valid),
      "needs_manual_alias_or_identity_review":len(unmatched),
      "cross_league_conflict_rows":len(conflicts),
      "source_edition_range":[edition_min,edition_max],
      "pending_2004_to_2009":"Older England Football.TXT data exists separately and will need its own parser/pinned source",
      "notes":"Exact name match is a staging candidate. No unknown competition is assigned to an active career."}
    (out/"OPENFOOTBALL_HISTORICAL_MEMBERSHIP_AUDIT.json").write_text(
        json.dumps(report,indent=2),encoding="utf-8")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--catalog",required=True);p.add_argument("--output",required=True)
    p.add_argument("--from-edition",type=int,default=2011)
    p.add_argument("--through-edition",type=int,default=2027)
    a=p.parse_args()
    print(json.dumps(generate(a.catalog,a.output,
      edition_min=a.from_edition,edition_max=a.through_edition),indent=2))

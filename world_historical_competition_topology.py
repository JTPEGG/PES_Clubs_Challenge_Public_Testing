"""Versioned, fail-closed historical men's competition hierarchy audit.

Do NOT confuse a FIFA/FC source squad grouping with the club's official
domestic league. European/CONMEBOL cup groupings are NOT domestic divisions.
A historic career is NOT ready if any registered team is left with an
unverified domestic competition or if a relegation boundary has no receiving
club pool. This module is STAGING ONLY until independently sourced.

A fixed rule template isn't sufficient for 22 editions: 2026/27 England's
Championship play-offs have six contenders; 2025/26 had four. All rule rows
are keyed by source starting edition, and any earlier-year facts need their
own historically verified membership and rule version.
"""
from __future__ import annotations

import argparse,csv,json,sqlite3
from collections import Counter,defaultdict
from pathlib import Path

VERSION="historical-competition-topology-v1-staging"
SEASONS=tuple(y for y in range(2005,2028) if y!=2025)
EFL_REG="https://images.gc.eflservices.co.uk/6a32d710-5b0b-11f0-ad0f-97502a343283.pdf"
EFL_2027="https://www.efl.com/news/2026/march/05/efl-statement--sky-bet-championship-play-off-format/"
DE_REG="https://www.bundesliga.com/en/bundesliga/news/how-does-promotion-and-relegation-work-in-the-bundesliga-10645"
ES_REG="https://www.laliga.com/noticias/equipos-que-bajan-a-segunda"
ES_SECOND="https://www.laliga.com/noticias/descensos-segunda-division-24-25"

# Source-specific unique league identity, NOT raw display name alone.
# This is deliberately a reviewed SHORTLIST, not a fabricated global map.
SCOPED_NAMES={
 "ENG:PL":("England",1,"Premier League"),
 "ENG:CH":("England",2,"EFL Championship"),
 "ENG:L1":("England",3,"EFL League One"),
 "ENG:L2":("England",4,"EFL League Two"),
 "ENG:NL":("England",5,"National League"),
 "GER:BL1":("Germany",1,"Bundesliga"),
 "GER:BL2":("Germany",2,"2. Bundesliga"),
 "GER:D3":("Germany",3,"3. Liga"),
 "GER:REG":("Germany",4,"Regionalliga (five regional divisions)"),
 "ESP:LL1":("Spain",1,"La Liga"),
 "ESP:LL2":("Spain",2,"Segunda División"),
 "ESP:RFEF":("Spain",3,"Primera Federación (two groups)")
}
# Explicit 2026 FIFA club-league IDs disambiguate e.g. English vs Ukrainian
# Premier League, German vs Austrian Bundesliga, etc.
FIFA26_IDS={
 "13.0":"ENG:PL","14.0":"ENG:CH","60.0":"ENG:L1","61.0":"ENG:L2",
 "19.0":"GER:BL1","20.0":"GER:BL2","2076.0":"GER:D3",
 "53.0":"ESP:LL1","54.0":"ESP:LL2"
}
FC27_LABELS={
 "Premier League":"ENG:PL","EFL Championship":"ENG:CH",
 "EFL League One":"ENG:L1","EFL League Two":"ENG:L2",
 "Bundesliga":"GER:BL1","Bundesliga 2":"GER:BL2","3. Liga":"GER:D3",
 "LALIGA EA SPORTS":"ESP:LL1","LALIGA HYPERMOTION":"ESP:LL2"
}
CUP_SOURCE_LABELS={"CONMEBOL Libertadores":"CONMEBOL_LIBERTADORES",
                   "CONMEBOL Sudamericana":"CONMEBOL_SUDAMERICANA"}

# Edges describe both promotion path and reciprocal demotion; absolute
# historical finished tables determine actual teams at season-end, not
# these templates (and future editions should not be used to seed a prior one).
# playoff_kind distinguishes normal bracket from inter-division tie.
COMMON_EDGES=(
 ("ENG:CH","ENG:PL",2,1,"rank_3_to_6","3rd-6th play-off",EFL_REG),
 ("ENG:L1","ENG:CH",2,1,"rank_3_to_6","3rd-6th play-off",EFL_REG),
 ("ENG:L2","ENG:L1",3,1,"rank_4_to_7","4th-7th play-off",EFL_REG),
 ("ENG:NL","ENG:L2",1,1,"national_league_playoff","National League promotion play-off",EFL_REG),
 ("GER:BL2","GER:BL1",2,1,"third_vs_upper_16th","3rd vs Bundesliga 16th two-leg play-off",DE_REG),
 ("GER:D3","GER:BL2",2,1,"third_vs_upper_16th","3rd vs 2. Bundesliga 16th two-leg play-off",DE_REG),
 ("ESP:LL2","ESP:LL1",2,1,"rank_3_to_6","3rd-6th play-off",ES_REG)
)
EDITION2027_CH=("ENG:CH","ENG:PL",2,1,"rank_3_to_8",
                "3rd/4th enter semi-finals; 5th-8th eliminators",EFL_2027)
RELEGATIONS={
 ("ENG:PL","ENG:CH"):3,("ENG:CH","ENG:L1"):3,
 ("ENG:L1","ENG:L2"):4,("ENG:L2","ENG:NL"):2,
 ("GER:BL1","GER:BL2"):2,("GER:BL2","GER:D3"):2,
 ("ESP:LL1","ESP:LL2"):3,("ESP:LL2","ESP:RFEF"):4,
}
# External feeder edges require VERIFIED team pools before careers can roll
# forward. These aren't guessed teams or phantom auto-promotions.
EXTERNAL_BOUNDARIES=(
 {"from":"GER:REG","to":"GER:D3","reason":"Regionalliga regional promotion and eligible club pool need season-validated rules"},
 {"from":"ESP:RFEF","to":"ESP:LL2","reason":"Two Primera Federación groups, playoff winners and actual entrants need source roster"},
 {"from":"ENG:NL","to":"lower regional leagues","reason":"National League North/South geography and next-year club pool require verification"},
)

def topology(edition):
    if edition not in (2026,2027):
        raise ValueError("Competition rules not verified for this edition")
    nodes=[{"id":key,"edition":edition,"country":ctry,"tier":tier,
            "name":name,"type":"domestic_league",
            "player_club_pool_status":"source_mapped" if key in
            set(FIFA26_IDS.values() if edition==2026 else FC27_LABELS.values())
            else "external_club_pool_required"}
           for key,(ctry,tier,name) in SCOPED_NAMES.items()]
    edges=[]
    for from_id,to_id,auto,playoff,kind,note,src in COMMON_EDGES:
        if edition==2027 and from_id=="ENG:CH":
            from_id,to_id,auto,playoff,kind,note,src=EDITION2027_CH
        edges.append({"from":from_id,"to":to_id,"auto_promotions":auto,
            "playoff_promotions":playoff,"playoff_format":kind,
            "playoff_note":note,"automatic_relegations":RELEGATIONS.get((to_id,from_id)),
            "source_url":src,"edition":edition,
            "competition_boundary_complete":RELEGATIONS.get((to_id,from_id)) is not None})
    # Spain's second-to-third tier has 4 relegations; two-group Primera
    # Federación promotions exist but are not represented as a fictitious
    # single-league final table.
    return {"edition":edition,"season":f"{edition-1}/{edition%100:02d}",
        "source":"Official league and federation regulations linked per edge",
        "nodes":nodes,"promotion_edges":edges,
        "relegation_boundaries":RELEGATIONS,
        "external_feeder_requirements":EXTERNAL_BOUNDARIES,
        "competition_qualification_edges_verified":False,
        "full_world_activated":False}

def classify_league(edition,league_label,source_league_id):
    if edition==2026:
        canonical=FIFA26_IDS.get(str(source_league_id or ""))
    elif edition==2027:
        canonical=FC27_LABELS.get(league_label)
    else:canonical=None
    if canonical:return canonical,"curated_source_competition_match"
    if league_label in CUP_SOURCE_LABELS:
        return CUP_SOURCE_LABELS[league_label],"continental_cup_not_domestic_league"
    if not league_label:return None,"missing_source_league"
    return None,"requires_verified_competition_identity"

def audit(source_database,outdir):
    """Full 22-year source coverage; outputs an explicit unmet-proof backlog.

    Never equates all labelled source FIFA groups with verified football
    pyramid leagues. No edition is enabled until EVERY playable club has a
    verified domestic league and all down/up boundaries have eligible clubs.
    """
    output=Path(outdir);output.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(f"file:{Path(source_database).resolve()}?mode=ro",uri=True) as conn:
        rows=conn.execute("""SELECT e.edition,e.season,c.club_key,c.name,
            l.league_name,l.source_league_id,l.source_league_level
            FROM editions e JOIN clubs c ON c.edition=e.edition
            LEFT JOIN leagues l ON l.league_key=c.league_key
            ORDER BY e.edition,c.name,c.club_key""").fetchall()
        source_leagues=conn.execute("""SELECT edition,league_key,league_name,
            source_league_id,source_league_level
            FROM leagues ORDER BY edition,league_name,league_key""").fetchall()
    if len(rows)!=13104:
        raise ValueError("Must use original approved men's-only 13,104-club archive")
    details=[];issues=Counter();years=defaultdict(Counter)
    for y,season,club_key,name,label,lid,level in rows:
        cid,status=classify_league(y,label,lid)
        if status!="curated_source_competition_match":
            issues[status]+=1
        years[y][status]+=1
        details.append([y,season,club_key,name,label or "",lid or "",
            level or "",cid or "",status,"blocked_until_fully_validated"])
    with (output/"HISTORICAL_CLUB_COMPETITION_COVERAGE.csv").open(
            "w",encoding="utf-8-sig",newline="") as f:
        writer=csv.writer(f)
        writer.writerow(["Edition","Starting_Season","Source_Club_Key","Club",
            "Source_Competition_Label","Source_Competition_ID",
            "Unverified_Source_Level","Curated_Competition_ID",
            "Identity_Status","Career_Activation_Status"])
        writer.writerows(details)
    graphs={str(y):topology(y) for y in (2026,2027)}
    # JSON requires stringify conversion of tuple keys to preserve all edges.
    for obj in graphs.values():
        obj["relegation_boundaries"]=[
            {"from":a,"to":b,"automatic_relegations":n}
            for (a,b),n in RELEGATIONS.items()]
    (output/"HISTORICAL_PROMOTION_RELEGATION_GRAPH.json").write_text(
        json.dumps({"version":VERSION,"graphs":graphs},indent=2),encoding="utf-8")
    outcome={"version":VERSION,"editions":len(years),
        "club_records":len(rows),"source_league_records":len(source_leagues),
        "years":{str(y):dict(yrs) for y,yrs in years.items()},
        "source_issues":dict(issues),
        "full_career_editions_ready":[],
        "activation_policy":"FAIL_CLOSED: no historical full-season career unless verified domestic tier, promotion-relegation network, external feeder club pools and nonleague cup treatment are complete",
        "notes":"Prior technical career import is sandbox-only. All 22 years need independent source competition memberships. FC27 continental club groupings require real domestic club registrations."}
    (output/"HISTORICAL_COMPETITION_READINESS.json").write_text(
        json.dumps(outcome,indent=2),encoding="utf-8")
    return outcome

def assert_full_career_ready(audit_result,edition):
    if edition not in SEASONS:
        raise ValueError("Unsupported historical edition")
    if edition not in audit_result["full_career_editions_ready"]:
        raise ValueError("Competition hierarchy incomplete: no unknown or cup-only club assignment permitted in active historical careers")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True);p.add_argument("--output",required=True)
    a=p.parse_args()
    report=audit(a.source,a.output)
    print(json.dumps({"years":report["editions"],"clubs":report["club_records"],
        "competition_identity_issues":report["source_issues"],
        "ready_editions":report["full_career_editions_ready"]},indent=2))

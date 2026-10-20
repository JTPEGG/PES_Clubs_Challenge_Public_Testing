"""One source-audited, men-only competition evidence register across 22 editions.

Fixture membership != a complete football pyramid. This register does NOT
issue career-ready certificates: unresolved domestic divisions, continental
cup buckets and external feeder pools stay blocked.
"""
import argparse,csv,hashlib,json,re,sqlite3,unicodedata
from collections import defaultdict,Counter
from pathlib import Path

VERSION="historical-competition-register-v1"
YEARS=set(range(2005,2028))-{2025}
CUPS=("conmebol libertadores","conmebol sudamericana","uefa champions","uefa europa")
ALIASES={
 "westbromwichalbion":"westbrom","wolverhamptonwanderers":"wolves",
 "nottinghamforest":"nottmforest","queensparkrangers":"qpr",
 "brightonandhovealbion":"brighton","brightonhovealbion":"brighton",
 "miltonkeynesdons":"mkdons"
}

def canonical(s):
    s=unicodedata.normalize("NFKD",str(s).casefold()).replace("&"," and ")
    s="".join(c for c in s if not unicodedata.combining(c))
    words=[x for x in re.findall(r"[a-z0-9]+",s)
           if x not in ("fc","afc","sc","ac","cf")]
    value="".join(words)
    return ALIASES.get(value,value)

def cup_group(name):
    return any(x in str(name or "").casefold() for x in CUPS)

def csvrows(path):
    with open(path,encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1048576),b""):h.update(chunk)
    return h.hexdigest()

SCHEMA="""
CREATE TABLE provenance(model TEXT PRIMARY KEY,source_catalog_sha256 TEXT NOT NULL,
  recent_source_sha256 TEXT NOT NULL,early_source_sha256 TEXT NOT NULL,
  men_only INTEGER NOT NULL,careers_ready INTEGER NOT NULL CHECK(careers_ready=0));
CREATE TABLE competition_seasons(
  code TEXT PRIMARY KEY,edition INTEGER NOT NULL,country TEXT NOT NULL,
  tier INTEGER NOT NULL,name TEXT NOT NULL,kind TEXT NOT NULL
  CHECK(kind='domestic_league'),source_url TEXT NOT NULL,source_sha256 TEXT);
CREATE TABLE fixture_club_evidence(
  edition INTEGER NOT NULL,club_key TEXT NOT NULL,club TEXT NOT NULL,
  competition_code TEXT NOT NULL REFERENCES competition_seasons(code),
  fixture_club TEXT NOT NULL,method TEXT NOT NULL,source_url TEXT NOT NULL,
  status TEXT NOT NULL,PRIMARY KEY(edition,club_key));
CREATE TABLE source_league_groups(
  edition INTEGER NOT NULL,league_key TEXT NOT NULL,source_label TEXT NOT NULL,
  club_count INTEGER NOT NULL,corroborated_competition TEXT,
  exact_clubs INTEGER NOT NULL,alias_candidates INTEGER NOT NULL,
  status TEXT NOT NULL,PRIMARY KEY(edition,league_key));
CREATE TABLE edition_club_competitions(
  edition INTEGER NOT NULL,club_key TEXT NOT NULL,club TEXT NOT NULL,
  original_source_league TEXT,group_type TEXT NOT NULL,
  evidence_competition TEXT REFERENCES competition_seasons(code),
  confidence TEXT NOT NULL,career_status TEXT NOT NULL
  CHECK(career_status='blocked'),
  PRIMARY KEY(edition,club_key));
CREATE TABLE edition_readiness(edition INTEGER PRIMARY KEY,total_clubs INTEGER NOT NULL,
  clubs_with_evidence INTEGER NOT NULL,clubs_unresolved INTEGER NOT NULL,
  conflicts INTEGER NOT NULL,career_ready INTEGER NOT NULL CHECK(career_ready=0));
CREATE TABLE dated_movement_edges(edition INTEGER NOT NULL,lower TEXT NOT NULL,
  upper TEXT NOT NULL,automatic_promotions INTEGER NOT NULL,
  playoff_promotions INTEGER NOT NULL,format TEXT NOT NULL,
  source_url TEXT NOT NULL,feeder_clubs_verified INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(edition,lower,upper));
CREATE TABLE external_feeder_requirements(edition INTEGER NOT NULL,
  source_competition TEXT NOT NULL,destination TEXT NOT NULL,
  requirement TEXT NOT NULL,PRIMARY KEY(edition,source_competition,destination));
CREATE TABLE season_versioned_rules(
  edition INTEGER NOT NULL,lower TEXT NOT NULL,upper TEXT NOT NULL,
  direct_promotions INTEGER NOT NULL,playoff_promotions INTEGER NOT NULL,
  eligible_ranks TEXT NOT NULL,direct_relegations INTEGER NOT NULL,
  evidence_url TEXT NOT NULL,source_status TEXT NOT NULL,
  feeder_verified INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(edition,lower,upper));
CREATE TABLE sourced_nonplayable_feeder_clubs(
  edition INTEGER NOT NULL,competition_code TEXT NOT NULL,
  club_name TEXT NOT NULL,tier INTEGER NOT NULL,
  source_url TEXT NOT NULL,source_sha256 TEXT NOT NULL,
  status TEXT NOT NULL,
  PRIMARY KEY(edition,competition_code,club_name));
"""
def collect(source,recent_dir,early_dir,graph_file,output,feeder_dir=None):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    target=out/"HISTORICAL_COMPETITION_REGISTER.sqlite"
    if target.exists():raise FileExistsError("Do not overwrite a previous release")
    with sqlite3.connect(f"file:{Path(source).resolve()}?mode=ro",uri=True) as db:
        originals=db.execute("""SELECT c.edition,c.club_key,c.name,c.league_key,
            l.league_name FROM clubs c LEFT JOIN leagues l ON l.league_key=c.league_key
            ORDER BY c.edition,c.club_key""").fetchall()
        editions=[v for (v,) in db.execute("SELECT edition FROM editions")]
    if len(originals)!=13104 or set(editions)!=YEARS:
        raise ValueError("Not the approved 22-year men's club source archive")
    aliases=defaultdict(list);byid={}
    for y,key,name,group,label in originals:
        aliases[(y,canonical(name))].append((key,name))
        byid[(y,key)]=(name,group,label)
    comps={};candidates=defaultdict(list)
    recent_dir=Path(recent_dir);early_dir=Path(early_dir)
    for row in csvrows(recent_dir/"PINNED_OPENFOOTBALL_LEAGUES_BY_SEASON.csv"):
        if row["Source_Status"]!="source_team_list_available":continue
        y=int(row["Edition"]);id=row["Source_File"].removesuffix(".json")
        comps[f"{y}:{id}"]=(y,row["Country"],int(row["Tier"]),
                            row["Competition"],row["Source_URL"],row["SHA256"])
    for row in csvrows(early_dir/"ENGLAND_2005_2010_FOOTBALLTXT_SOURCE_FILES.csv"):
        if row["Status"]!="parsed_source_verified_team_count":continue
        y=int(row["FIFA_Edition"])
        comps[f"{y}:en.{row['Tier']}"]=(y,"England",int(row["Tier"]),
                         row["Competition"],row["Source_URL"],row["Source_SHA256"])
    def add(year,club,code,fixture,method,url):
        if code not in comps or (year,club) not in byid:return
        candidates[(year,club)].append((code,fixture,method,url))
    for row in csvrows(recent_dir/"EXACT_HISTORICAL_CLUB_LEAGUE_MATCHES.csv"):
        y=int(row["Edition"])
        add(y,row["FIFA_Club_Key"],f"{y}:{row['League_Code']}",
            row["Fixture_Club"],"exact",row["Source_URL"])
    for row in csvrows(early_dir/"ENGLAND_2005_2010_PROVISIONAL_CLUB_COMPETITIONS.csv"):
        y=int(row["FIFA_Edition"])
        add(y,row["FIFA_Club_Key"],f"{y}:en.{row['Tier']}",
            row["Source_Team"],"exact",row["Source_URL"])
    # Alias candidates never override an exact fixture match and are never
    # presented as verified game club identity.
    for rows,edition_col,code_col,name_col in (
        (csvrows(recent_dir/"CLUB_LEAGUE_NAME_MATCH_REVIEW.csv"),
         "Edition","League_Code","Fixture_Club"),
        (csvrows(early_dir/"ENGLAND_2005_2010_CLUB_NAME_REVIEW.csv"),
         "FIFA_Edition","Tier","Source_Team")):
        for row in rows:
            y=int(row[edition_col]);code=(f"{y}:en.{row[code_col]}"
                if edition_col=="FIFA_Edition" else f"{y}:{row[code_col]}")
            hits=aliases[(y,canonical(row[name_col]))]
            if len(hits)!=1:continue
            add(y,hits[0][0],code,row[name_col],"alias_requires_review",
                row["Source_URL"])
    validated=[];conflicts=[];counts=defaultdict(Counter)
    for (y,key),lst in sorted(candidates.items()):
        names={x[0] for x in lst}
        if len(names)>1:
            conflicts.append((y,key,sorted(names)));continue
        best=next((x for x in lst if x[2]=="exact"),lst[0])
        code,fixture,method,url=best
        validated.append((y,key,byid[(y,key)][0],code,fixture,method,url,
             "fixture_exact" if method=="exact" else "alias_needs_identity_review"))
        source_group=byid[(y,key)][1]
        if source_group:counts[(y,source_group)][(code,method)]+=1
    confirmed={(r[0],r[1]):r for r in validated}
    conflicted={(y,key) for y,key,_ in conflicts}
    source_groups=defaultdict(list)
    for row in originals:
        if row[3]:source_groups[(row[0],row[3])].append(row)
    groups=[];group_alias={}
    for (y,g),members in sorted(source_groups.items()):
        label=members[0][4]
        voted=Counter()
        for (comp,method),n in counts[(y,g)].items():voted[comp]+=n
        winners=voted.most_common(1);total=sum(voted.values())
        matched=(winners[0][0] if winners and winners[0][1]>=6
                 and winners[0][1]/total>=.75 and not cup_group(label) else None)
        group_alias[(y,g)]=matched
        groups.append((y,g,label,len(members),matched,
            sum(n for (c,m),n in counts[(y,g)].items() if m=="exact"),
            sum(n for (c,m),n in counts[(y,g)].items() if m!="exact"),
            "cross_checked_fixture_group" if matched else
            "continental_cup_not_domestic" if cup_group(label)
            else "still_unverified"))
    rows=[];per_year=Counter()
    for y,key,name,source_group,label in originals:
        match=confirmed.get((y,key))
        comp=match[3] if match else group_alias.get((y,source_group))
        kind="continental_cup_bucket" if cup_group(label) else (
             "missing_original_source_league" if not source_group else "domestic_source_group")
        if cup_group(label) or (y,key) in conflicted:comp=None
        conf=("conflict" if (y,key) in conflicted else "fixture_exact" if match and match[5]=="exact"
              else "alias_review" if match else "source_group_corroborated" if comp
              else "unresolved")
        rows.append((y,key,name,label,kind,comp,conf,"blocked"))
        if comp:per_year[y]+=1
    # Date-scoped rules remain separately distinguishable from verified
    # full feeder pools. A National League fixture list is not a game squad.
    from world_historical_movement_rules import EDITION_YEARS,source_rules
    season_rules=[r for yr in EDITION_YEARS for r in source_rules(yr)]
    feeder_clubs=[]
    if feeder_dir is not None:
        for row in csvrows(Path(feeder_dir)/"NATIONAL_LEAGUE_HISTORICAL_FEEDER_CLUBS.csv"):
            yr=int(row["Edition"]);tier=int(row["Tier"])
            if yr not in YEARS or tier!=5 or row["Competition_Code"]!="ENG:NL":
                raise ValueError("Invalid source feeder division")
            feeder_clubs.append((yr,row["Competition_Code"],row["Club"],
                tier,row["Fixture_URL"],row["Source_SHA256"],row["Evidence_Status"]))
    graphs=json.loads(Path(graph_file).read_text())["graphs"]
    edges=[];boundaries=[]
    for stringyear,data in graphs.items():
        y=int(stringyear)
        for r in data["promotion_edges"]:
            edges.append((y,r["from"],r["to"],r["auto_promotions"],
               r["playoff_promotions"],r["playoff_format"],r["source_url"],0))
        for r in data["external_feeder_requirements"]:
            boundaries.append((y,r["from"],r["to"],r["reason"]))
    with sqlite3.connect(target) as db:
        db.executescript("PRAGMA foreign_keys=ON;"+SCHEMA)
        db.execute("INSERT INTO provenance VALUES (?,?,?,?,?,?)",
                   (VERSION,sha(source),sha(recent_dir/"EXACT_HISTORICAL_CLUB_LEAGUE_MATCHES.csv"),
                   sha(early_dir/"ENGLAND_2005_2010_PROVISIONAL_CLUB_COMPETITIONS.csv"),1,0))
        db.executemany("INSERT INTO competition_seasons VALUES (?,?,?,?,?,?,?,?)",
            ((key,*value[:4],"domestic_league",value[4],value[5])
             for key,value in comps.items()))
        db.executemany("INSERT INTO fixture_club_evidence VALUES (?,?,?,?,?,?,?,?)",validated)
        db.executemany("INSERT INTO source_league_groups VALUES (?,?,?,?,?,?,?,?)",groups)
        db.executemany("INSERT INTO edition_club_competitions VALUES (?,?,?,?,?,?,?,?)",rows)
        db.executemany("INSERT INTO edition_readiness VALUES (?,?,?,?,?,?)",(
            (y,sum(row[0]==y for row in originals),per_year[y],
              sum(row[0]==y for row in originals)-per_year[y],
              sum(a==y for a,k,t in conflicts),0) for y in sorted(YEARS)))
        db.executemany("INSERT INTO dated_movement_edges VALUES (?,?,?,?,?,?,?,?)",edges)
        db.executemany("INSERT INTO external_feeder_requirements VALUES (?,?,?,?)",boundaries)
        db.executemany("INSERT INTO season_versioned_rules VALUES (?,?,?,?,?,?,?,?,?,?)",
            ((r["edition"],r["lower"],r["upper"],r["direct_promotions"],
             r["playoff_promotions"],r["playoff_entrants"],r["direct_relegations"],
             r["evidence_url"],r["source_status"],0) for r in season_rules))
        db.executemany("INSERT INTO sourced_nonplayable_feeder_clubs VALUES (?,?,?,?,?,?,?)",
            feeder_clubs)
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise ValueError("SQLite integrity failure")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Competition foreign-key failure")
        db.commit()
    def export(name,head,records):
        with (out/name).open("w",encoding="utf-8-sig",newline="") as f:
            wr=csv.writer(f);wr.writerow(head);wr.writerows(records)
    export("HISTORICAL_CLUB_COMPETITION_STATUS.csv",
           ("Edition","Source_Club_Key","Club","Original_League_Label",
            "Original_Group_Type","Evidence_Domestic_League","Match_Status",
            "Career_Status"),rows)
    export("HISTORICAL_MEMBERSHIP_CROSSWALK.csv",
           ("Edition","Source_Club_Key","Club","Competition_Code",
            "External_Source_Club","Method","Source_URL","Confidence"),validated)
    export("SOURCE_GROUPS_CROSSCHECK.csv",
           ("Edition","League_Source_Key","League_Label","Source_Clubs",
            "Corroborated_Competition","Fixture_Exact_Matches","Alias_Candidates",
            "Status"),groups)
    report={"version":VERSION,"source_clubs":len(rows),"source_years":len(YEARS),
       "historical_domestic_league_seasons":len(comps),
       "independent_fixture_matches":len(validated),
       "exact_matches":sum(x[5]=="exact" for x in validated),
       "normalized_alias_candidates":sum(x[5]!="exact" for x in validated),
       "cross_checked_original_league_groups":sum(x[7]=="cross_checked_fixture_group" for x in groups),
       "club_years_with_sourced_home_league_evidence":sum(per_year.values()),
       "club_years_unresolved":len(rows)-sum(per_year.values()),
       "disputed_club_years":len(conflicts),"dated_movement_edges_staged":len(edges),
       "external_feeders_unverified":len(boundaries),
       "season_versioned_rule_records":len(season_rules),
       "historical_nonplayable_feeder_club_years":len(feeder_clubs),
       "career_ready_editions":[],
       "comment":"Historical fixture data and provider league labels are evidence only. Complete country-wide feeders and all club assignments are NOT yet verified."}
    (out/"COMPETITION_REGISTRY_AUDIT.json").write_text(json.dumps(report,indent=2))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("source","recent-dir","early-dir","graph","output","feeder-dir"):
        p.add_argument("--"+x,required=True)
    a=p.parse_args()
    print(json.dumps(collect(a.source,a.recent_dir,a.early_dir,a.graph,
        a.output,feeder_dir=a.feeder_dir),indent=2))

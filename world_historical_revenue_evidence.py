"""Add source-observed annual club revenues, WITHOUT laundering EUR into GBP cash.

Deloitte values are immutable observations, not authority for takeover
payments, transfer budgets, unrestricted cash, or exact simulation wages.
Only read editions with source publication before the starting-season date.
"""
from __future__ import annotations

import argparse,csv,hashlib,json,sqlite3
from collections import defaultdict
from datetime import date
from pathlib import Path
from world_historical_financial_circumstances import norm,preseason_date

VERSION="historical-revenue-observations-v1"
REVENUE_CLUB_SYNONYMS={
 "fcbarcelona":"barcelona","barcelona":"barcelona",
 "bayernmunich":"fcbayernmunchen","fcbayernmunchen":"fcbayernmunchen",
 "parissaintgermain":"psg","psg":"psg",
 "brightonandhovealbion":"brighton","brightonhovealbion":"brighton","brighton":"brighton",
 "atleticodemadrid":"atleticomadrid","atleticomadrid":"atleticomadrid",
 "vfb stuttgart":"vfb stuttgart"
}
def standard_club_name(club):
    n=norm(club)
    return REVENUE_CLUB_SYNONYMS.get(n,n)

SCHEMA="""
CREATE TABLE IF NOT EXISTS revenue_observation_release(
 version TEXT PRIMARY KEY,source_circumstances_sha256 TEXT NOT NULL,
 immutable_observations_sha256 TEXT NOT NULL,
 source_method TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_club_annual_revenues(
 observation_id TEXT NOT NULL,edition INTEGER NOT NULL,
 matched_club_key TEXT,original_club_name TEXT NOT NULL,
 financial_year_end INTEGER NOT NULL,currency TEXT NOT NULL CHECK(currency='EUR'),
 revenue_eur INTEGER NOT NULL CHECK(revenue_eur>=0),
 publication_date TEXT NOT NULL,source_url TEXT NOT NULL,
 match_status TEXT NOT NULL,
 available_at_edition_preseason INTEGER NOT NULL,
 PRIMARY KEY(observation_id,edition)
);
CREATE TABLE IF NOT EXISTS latest_club_revenue_reference(
 club_key TEXT PRIMARY KEY,edition INTEGER NOT NULL,
 source_observation_id TEXT,source_financial_year_end INTEGER,
 observed_revenue_eur INTEGER,source_published TEXT,
 source_url TEXT,
 as_of_availability_status TEXT NOT NULL,
 CHECK((source_observation_id IS NULL AND observed_revenue_eur IS NULL) OR
       (source_observation_id IS NOT NULL AND observed_revenue_eur IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS sourced_sector_benchmarks(
 id TEXT PRIMARY KEY,year INTEGER NOT NULL,competition TEXT NOT NULL,
 metric TEXT NOT NULL,currency TEXT NOT NULL,amount INTEGER NOT NULL,
 published TEXT NOT NULL,source_url TEXT NOT NULL
);
"""
def build(circumstances_db,evidence_file,outdir):
    evidence=json.loads(Path(evidence_file).read_text(encoding="utf-8"))
    if evidence.get("scope")!="mens_only":raise ValueError("Men-only observations required")
    records=evidence["observations"]
    if len({o["id"] for o in records})!=len(records):
        raise ValueError("Duplicate observations")
    out=Path(outdir);out.mkdir(parents=True,exist_ok=True)
    dest=out/"PES_V2_REVENUE_EVIDENCE.sqlite"
    if dest.exists():raise FileExistsError("Do not overwrite revenue evidence database")
    with sqlite3.connect(f"file:{Path(circumstances_db).resolve()}?mode=ro",uri=True) as old:
        rows=old.execute("""SELECT club_key,edition,club_name
            FROM historical_club_circumstances ORDER BY edition,club_name""").fetchall()
    if len(rows)!=13104:raise ValueError("Club parity failure")
    by_year=defaultdict(list)
    by_name=defaultdict(list)
    for key,edition,name in rows:
        by_year[edition].append((key,name))
        by_name[(edition,standard_club_name(name))].append(key)
    status=defaultdict(int);matches=[]
    for ed in sorted(by_year):
        for o in records:
            publication=date.fromisoformat(o["date_published"])
            if int(o["financial_year_end"])>=ed or publication>preseason_date(ed):
                continue
            candidates=by_name.get((ed,standard_club_name(o["club"])),[])
            mode="unique" if len(candidates)==1 else ("unmatched" if not candidates else "ambiguous")
            if mode!="unique":
                status[mode]+=1
            else:
                status["unique"]+=1
            matches.append((o["id"],ed,candidates[0] if mode=="unique" else None,
               o["club"],o["financial_year_end"],o["currency"],o["value"],
               o["date_published"],o["source_url"],mode,int(mode=="unique")))
    latest={}
    obsbyid={o["id"]:o for o in records}
    for ob_id,ed,key,name,yr,curr,val,pub,url,mode,ready in matches:
        if not ready:continue
        old=latest.get(key)
        if old is None or (yr,pub)>(old[1],old[4]):
            latest[key]=(ob_id,yr,val,url,pub)
    with sqlite3.connect(dest) as db:
        db.executescript(SCHEMA)
        db.execute("""INSERT INTO revenue_observation_release VALUES(?,?,?,?)""",(
          VERSION,hashlib.sha256(Path(circumstances_db).read_bytes()).hexdigest(),
          hashlib.sha256(Path(evidence_file).read_bytes()).hexdigest(),
          "EUR historical revenue from cited Deloitte; NOT verified cash, budget or foreign-exchange-adjusted GBP revenue"))
        db.executemany("""INSERT INTO source_club_annual_revenues
            (observation_id,edition,matched_club_key,original_club_name,
            financial_year_end,currency,revenue_eur,publication_date,
            source_url,match_status,available_at_edition_preseason)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",matches)
        db.executemany("""INSERT INTO latest_club_revenue_reference(
            club_key,edition,source_observation_id,source_financial_year_end,
            observed_revenue_eur,source_published,source_url,
            as_of_availability_status) VALUES(?,?,?,?,?,?,?,?)""",
            ((key,ed,*((latest[key][0],latest[key][1],latest[key][2],
              latest[key][4],latest[key][3]) if key in latest else
              (None,None,None,None,None)),
              "published_observation" if key in latest else "no_observed_club_revenue")
             for key,ed,name in rows))
        db.executemany("""INSERT INTO sourced_sector_benchmarks
          VALUES(?,?,?,?,?,?,?,?)""",[
            (v["id"],v["financial_year_end"],v["competition"],v["metric"],
             v["currency"],v["amount"],v["source_publication_date"],
             v["source_url"]) for v in evidence["sector_benchmarks"]])
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise ValueError("Revenue DB integrity failed")
        db.commit()
    with (out/"REVENUE_EVIDENCE_CSV.csv").open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.writer(f)
        writer.writerow(("FIFA_Edition","Source_Club_Key","Club","Observed_Financial_Year",
           "Observed_Revenue_EUR","Source_Published","Observed_Source_URL","Status"))
        for key,ed,name in rows:
            val=latest.get(key)
            writer.writerow((ed,key,name,
                val[1] if val else "",val[2] if val else "",
                val[4] if val else "",val[3] if val else "",
                "published_observation" if val else "no_observed_club_revenue"))
    result=dict(version=VERSION,observations=len(records),
        source_sector_benchmarks=len(evidence["sector_benchmarks"]),
        sources_unique_matched_across_editions=dict(status),
        source_clubs_with_observed_revenue=len(latest),
        total_club_profiles=len(rows),
        note="Only EUR revenue source observations; no automatic FX conversion, invented transfer budgets or claimed cash balance.")
    (out/"REVENUE_EVIDENCE_AUDIT.json").write_text(json.dumps(result,indent=2))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--circumstances",required=True)
    p.add_argument("--evidence",default="data/warehouse/historical_club_revenue_observations_v1.json")
    p.add_argument("--output",required=True)
    a=p.parse_args()
    print(json.dumps(build(a.circumstances,a.evidence,a.output),indent=2))

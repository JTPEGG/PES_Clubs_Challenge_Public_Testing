"""Men-only V2 starting wages, contracts and source-loan agreements.

Reads original source CSVs and the validated men's-only club/squad SQLite in
read-only mode. Produces a NEW immutable, enriched SQLite file: it never edits
source archives, a saved career, live data or the existing standalone catalogue.

Model v1: robust observed wage reference by year and source, conditional on
player rating and club stature; historical extrapolation for missing years.
Observed wages retain raw value and are *provisional FIFA-game weekly proxies*,
not verified real salaries or verified historical FX conversions.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import sqlite3
from statistics import median
from zipfile import ZipFile

from scripts.export_fifa_pes_v2 import read_ed, source_members
from scripts.audit_fifa_pes_v2_contract_sources import parse_amount
from world_historical_club_squads import YEARS, first, norm

VERSION="historical-wage-and-loan-v2-fc27-anchored"
WAGE_KEYS={
    **{year:"wage" for year in range(2005,2015)},
    **{year:"wage_eur" for year in range(2015,2023)},
    2023:"WageEUR",2024:"wage",2026:"wage_eur",
}
EXPIRY_KEYS={
    **{year:"contract_length" for year in range(2005,2015)},
    **{year:"contract_valid_until" for year in range(2015,2022)},
    2022:"club_contract_valid_until",2023:"ContractUntil",
    2024:"club_contract_valid_until",2026:"club_contract_valid_until_year",
}
# Pinned, explicit SIMULATION FX assumptions; not verified point-in-time rates.
MODEL_EUR_GBP={2015:.73,2016:.78,2017:.86,2018:.88,2019:.88,
               2020:.88,2021:.86,2022:.85,2023:.87,2024:.86,2026:.85}
PLACEHOLDER_MAX=20
FINANCE_SCHEMA="""
CREATE TABLE IF NOT EXISTS starting_finance_model(
 model_version TEXT PRIMARY KEY,
 source_zip_sha256 TEXT NOT NULL,
 original_catalog_sha256 TEXT NOT NULL,
 scope TEXT NOT NULL CHECK(scope='mens_only'),
 created_for TEXT NOT NULL DEFAULT 'sandbox_only'
);
CREATE TABLE IF NOT EXISTS starting_player_finances(
 player_key TEXT PRIMARY KEY REFERENCES players(player_key),
 edition INTEGER NOT NULL,
 raw_wage TEXT,
 raw_wage_currency TEXT NOT NULL,
 source_wage_weekly_gbp INTEGER,
 model_weekly_wage_gbp INTEGER NOT NULL CHECK(model_weekly_wage_gbp BETWEEN 50 AND 1000000),
 wage_provenance TEXT NOT NULL,
 source_expiry_raw TEXT,
 game_contract_expires_on TEXT,
 expiry_provenance TEXT NOT NULL,
 estimated_squad_tier TEXT NOT NULL,
 model_version TEXT NOT NULL,
 wage_quality_warning TEXT NOT NULL DEFAULT '',
 reference_2026_weekly_wage_gbp INTEGER,
 reference_2026_player_key TEXT,
 reference_2026_match_status TEXT
);
CREATE TABLE IF NOT EXISTS starting_source_loans(
 player_key TEXT PRIMARY KEY REFERENCES players(player_key),
 edition INTEGER NOT NULL,
 borrower_club_key TEXT REFERENCES clubs(club_key),
 raw_parent_club TEXT NOT NULL,
 resolved_parent_club_key TEXT REFERENCES clubs(club_key),
 parent_status TEXT NOT NULL CHECK(parent_status IN
  ('resolved','parent_not_found','ambiguous_parent','invalid_same_club','borrower_unknown')),
 game_return_date TEXT,
 return_date_status TEXT NOT NULL,
 simulated_borrower_wage_share_pct INTEGER,
 salary_share_status TEXT NOT NULL,
 model_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS starting_club_finances(
 club_key TEXT PRIMARY KEY REFERENCES clubs(club_key),
 edition INTEGER NOT NULL,
 model_payroll_weekly_gbp INTEGER NOT NULL,
 model_wage_ceiling_weekly_gbp INTEGER NOT NULL,
 proposed_wage_headroom_weekly_gbp INTEGER NOT NULL,
 financial_provenance TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS starting_finance_edition ON starting_player_finances(edition);
CREATE INDEX IF NOT EXISTS starting_loan_edition ON starting_source_loans(edition);
"""


def money_source(year,raw):
    """Return modelled weekly GBP wage and original currency/quality.

    Do not pretend 2012 FIFAIndex wage units, 2024 FC24 raw K notation, or
    per-year EUR FX values are independently verified salaries.
    """
    text=str(raw or "").strip()
    amount=parse_amount(text)
    if amount is None or amount<=PLACEHOLDER_MAX:
        return None,"unknown","absent_or_placeholder"
    if amount>1_000_000:
        return None,"unknown","outlier_over_one_million"
    if year in range(2012,2015):
        # These legacy monetary values show severe scale/sentinel contamination.
        # Preserve raw wage, but NEVER train, translate or seed current pay from
        # an unverified legacy unit (full-run medians exceeded £270k/week).
        return None,"fifaindex_units_unverified","raw_money_units_unverified_model_instead"
    if year==2024:
        return round(amount*MODEL_EUR_GBP[year]),"FC24_unknown_assumed_EUR","assumed_eur_weekly_unverified"
    if year in MODEL_EUR_GBP and year!=2015:
        return round(amount*MODEL_EUR_GBP[year]),"EUR","assumed_weekly_fx_model"
    return None,"unknown","unusable_source_wage"


FC27_NEXT_YEAR_SIMULATION_INCREASE=1.075
# Only source-backed wages may be carried forward. Never match IDs alone.
CLUB_ALIASES={
  "parissg":"parissaintgermain",
  "psg":"parissaintgermain",
  "napoli":"sscnapoli",
  "lilleosc":"losclille",
  "manutd":"manchesterunited",
  "spurs":"tottenhamhotspur",
  "manchestercity":"manchestercity",
  "mancity":"manchestercity",
}

def _same_club(a,b):
    left=CLUB_ALIASES.get(norm(a),norm(a))
    right=CLUB_ALIASES.get(norm(b),norm(b))
    return bool(left) and left==right

def _source_identity(row):
    # A numeric FIFA ID is insufficient across different source editions.
    # Require shared ID, birth date AND nationality before wage continuity.
    sid=str(row.get("source_id") or "").strip()
    dob=str(row.get("dob") or "").strip()
    nationality=norm(row.get("nationality"))
    return (sid,dob,nationality) if sid and len(dob)==10 and nationality else None

def fc27_source_wage_index(rows_2026):
    index=defaultdict(list)
    for row in rows_2026:
        ident=_source_identity(row)
        if ident and row.get("observed") is not None and row["observed"]>=50:
            index[ident].append(row)
    return {key:items[0] for key,items in index.items() if len(items)==1}

def revise_fc27_wage(row,normal_estimate,source_2026_index):
    """Predict only FC27; preserve all other 21 editions' wage policy.

    Unchanged employer: continuity of a credible prior FIFA weekly wage plus
    a FIXED 7.5% game assumption (not an evidenced new contract).
    Different employer: conservative blend with new club's financial model,
    capped at 2.5x the new-club baseline, not a fictional retained contract.
    No matched identity -> preserve the rating-based original prediction.
    """
    identity=_source_identity(row)
    prior=source_2026_index.get(identity) if identity else None
    if not prior or abs(row["rating"]-prior["rating"])>10:
        return normal_estimate,"game_estimate_fc27_unmatched","",None,None
    if not row.get("club_name") or not prior.get("club_name"):
        return normal_estimate,"game_estimate_fc27_missing_club","",None,None
    prev=round(prior["observed"])
    if _same_club(row["club_name"],prior["club_name"]):
        next_wage=round(prev*FC27_NEXT_YEAR_SIMULATION_INCREASE/50)*50
        return (max(100,min(750000,next_wage)),
                "game_estimate_fc27_same_club_2026_wage_carried",
                "verified_id_dob_nationality_and_same_club",prev,prior["key"])
    implied=prev*FC27_NEXT_YEAR_SIMULATION_INCREASE
    blended=0.55*implied+0.45*normal_estimate
    next_wage=round(min(max(blended,normal_estimate*.75),
                        normal_estimate*2.5)/50)*50
    return (max(100,min(750000,next_wage)),
            "game_estimate_fc27_changed_club_2026_wage_blend",
            "verified_id_dob_nationality_club_changed",prev,prior["key"])


def expiry_source(year,value):
    raw=str(value or "").strip()
    try:
        y=int(float(raw))
    except (ValueError,TypeError):
        return None
    # Contract-length columns from FIFAIndex contain ending YEARS (e.g. 2016).
    return y if year-2<=y<=year+12 else None


def age_on(dob,year):
    try:
        return max(15,min(50,year-date.fromisoformat(dob).year))
    except (ValueError,TypeError):
        return 26


def age_factor(age):
    if age<=18:return .67
    if age<=21:return .83
    if age<=24:return .93
    if age>=36:return .82
    if age>=33:return .94
    return 1.


def position_factor(position):
    if position in ("CF","ST","SS","RWF","LWF"):return 1.08
    if position in ("GK",):return .94
    return 1.


def role_level(overall,teammates):
    if not teammates:return "unknown"
    threshold=sorted(teammates,reverse=True)
    rank=sum(1 for x in teammates if x>overall)
    ratio=rank/max(len(teammates),1)
    if ratio<=.14:return "key_player"
    if ratio<=.60:return "regular_starter"
    if ratio<=.85:return "rotation"
    return "fringe"


def coefficient(rating,age,position):
    return math.exp(.105*(max(45,min(95,rating))-70))*age_factor(age)*position_factor(position)


def calibration_wages(annual):
    """One edition, provider-specific robust median anchors; 20% holdout."""
    fits={}; holdout={}
    for y,rows in annual.items():
        for row in rows:
            wage=row["observed"]
            if wage is None:continue
            # Deterministic player-level split, never cross-edition player IDs.
            key=row["key"]
            if int(hashlib.sha256(key.encode()).hexdigest()[:6],16)%5==0:
                holdout.setdefault(y,[]).append(row)
            else:
                fits.setdefault(y,[]).append(row)
    base={}
    club_calibrations={}
    for y,rows in fits.items():
        samples=[max(80,min(500000,r["observed"]))/coefficient(r["rating"],r["age"],r["position"])
                 for r in rows]
        if len(samples)>=30:base[y]=median(samples)
        club=defaultdict(list)
        for r in rows:
            if r["club"]:
                club[r["club"]].append(
                    max(80,min(500000,r["observed"]))/coefficient(r["rating"],r["age"],r["position"]))
        club_calibrations[y]={k:median(v) for k,v in club.items() if len(v)>=5}
    return base,club_calibrations,holdout


def interpolated_baseline(year,base):
    if year in base and year>=2016:return base[year],"direct_year_robust_training"
    # Early FIFAIndex wages do not have confirmed weekly units and cannot
    # anchor the entire 2005-2015 curve. Only FIFA16+ observations are trained.
    nearest=sorted(y for y in base if y>=2016)
    if not nearest:
        raise ValueError("No credible wage calibration observations")
    lower=[y for y in nearest if y<year]
    upper=[y for y in nearest if y>year]
    if lower and upper:
        lo,hi=max(lower),min(upper)
        weight=(year-lo)/(hi-lo)
        return math.exp(math.log(base[lo])*(1-weight)+math.log(base[hi])*weight),"interpolated_neighbour_edition"
    if upper:
        near=min(upper)
        return base[near]*(1.075**(year-near)),"historical_backcast_7_5pct_simulation"
    near=max(lower)
    return base[near]*(1.075**(year-near)),"historical_forwardcast_7_5pct_simulation"


def predicted_wage(row,annual_baseline,club_cal,club_ratings):
    team=row["club"]
    club_roster=club_ratings.get(team,[])
    top=sorted(club_roster,reverse=True)[:11]
    top_mean=sum(top)/len(top) if top else 70
    # Institutional reputation isn't known in many historical sources.
    # Best-XI quality is explicitly a proxy, not proof of true financial clout.
    strength=max(.25,min(5.,math.exp(.062*(top_mean-74))))
    observed=club_cal.get(team)
    if observed is not None and annual_baseline>0:
        # Shrink observed club data toward squad strength so tiny samples
        # don't overwrite the baseline with one superstar's salary.
        ratio=max(.25,min(7.,observed/annual_baseline))
        strength=.65*ratio+.35*strength
    estimate=annual_baseline*coefficient(row["rating"],row["age"],row["position"])*strength
    return int(max(100,min(750000,round(estimate/50)*50)))


def _season_contract_end(year,expiry_raw,player_key,age):
    sourced=expiry_source(year,expiry_raw)
    if sourced is not None and sourced>=year:
        return f"{sourced}-06-30","source_end_year_game_date_june30"
    # Estimated only: reproducible 1–4 season contract, no random input.
    deterministic=int(hashlib.sha256(player_key.encode()).hexdigest()[:8],16)%4
    length=[1,2,3,4][deterministic]
    if age>=34:length=min(length,2)
    return f"{year+length-1}-06-30","estimated_game_contract_duration"


def _gather_source(sqlite_conn,z,year,member):
    src=read_ed(z,{year:member},year)
    people=sqlite_conn.execute("""SELECT p.player_key,p.source_row_number,p.club_key,
           p.source_overall,p.date_of_birth,p.primary_position,p.loaned_from,
           p.source_player_id,p.nationality,c.name
           FROM players p LEFT JOIN clubs c ON c.club_key=p.club_key
           WHERE p.edition=? ORDER BY p.source_row_number""",(year,)).fetchall()
    rows=[]
    for key,n,club,ovr,dob,position,parent,source_id,nationality,club_name in people:
        if not 1<=n<=len(src):raise ValueError("Source row ordinal invalid")
        row=src[n-1]
        wage_key=WAGE_KEYS.get(year)
        contract_key=EXPIRY_KEYS.get(year)
        raw_wage=row.get(wage_key) if wage_key else None
        observed,currency,source_quality=money_source(year,raw_wage)
        rating=ovr if ovr is not None and 35<=ovr<=99 else 65
        rows.append({
           "key":key,"year":year,"club":club,"rating":rating,
           "source_id":source_id,"dob":dob,"nationality":nationality,
           "club_name":club_name,
           "position":position,"age":age_on(dob,year),
           "raw_wage":raw_wage,"currency":currency,
           "wage_warning":source_quality,
           "observed":observed,"source_expiry":row.get(contract_key) if contract_key else None,
           "loan_parent":parent,
        })
    return rows


def resolve_parent(parent,borrower,club_name_to_keys):
    candidates=club_name_to_keys.get(norm(parent),set())
    if borrower is None:
        return None,"borrower_unknown"
    if not candidates:
        return None,"parent_not_found"
    if len(candidates)!=1:
        return None,"ambiguous_parent"
    match=next(iter(candidates))
    if match==borrower:
        return None,"invalid_same_club"
    return match,"resolved"


def build(catalog,source_zip,output):
    source_zip=Path(source_zip)
    catalog=Path(catalog)
    output=Path(output)
    if output.exists():raise FileExistsError("Never overwrite a historical career catalogue")
    output.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(catalog,output)
    with sqlite3.connect(output) as db,ZipFile(source_zip) as archive:
        db.execute("PRAGMA foreign_keys=ON")
        source_files=source_members(archive)
        if set(source_files)!=set(YEARS):raise ValueError("Source file edition mismatch")
        if db.execute("SELECT COUNT(*) FROM players").fetchone()[0]!=317449:
            raise ValueError("Expected exactly the signed-off men's-only player catalogue")
        db.executescript(FINANCE_SCHEMA)
        db.execute("""INSERT INTO starting_finance_model
                (model_version,source_zip_sha256,original_catalog_sha256,scope)
                VALUES (?,?,?,'mens_only')""",(
                 VERSION,hashlib.sha256(source_zip.read_bytes()).hexdigest(),
                 hashlib.sha256(catalog.read_bytes()).hexdigest()))
        annual={}
        for year in YEARS:
            annual[year]=_gather_source(db,archive,year,source_files[year])
        base,club_cal,holdouts=calibration_wages(annual)
        fc27_prev=fc27_source_wage_index(annual[2026])
        club_names=defaultdict(lambda:defaultdict(set))
        club_ratings=defaultdict(lambda:defaultdict(list))
        for year in YEARS:
            for key,name in db.execute("SELECT club_key,name FROM clubs WHERE edition=?",(year,)):
                club_names[year][norm(name)].add(key)
            for row in annual[year]:
                if row["club"]:club_ratings[year][row["club"]].append(row["rating"])
        quality={}
        totals=Counter()
        for year in YEARS:
            baseline,baseline_method=interpolated_baseline(year,base)
            errors=[]
            for row in holdouts.get(year,[]):
                pred=predicted_wage(row,baseline,club_cal.get(year,{}),club_ratings[year])
                errors.append(abs(math.log(max(1,pred)/max(1,row["observed"]))))
            q=Counter()
            wages=[]
            loan_records=[]
            for row in annual[year]:
                source=row["observed"]
                if source is not None and source>=50:
                    value=max(50,min(1000000,round(source)))
                    provenance="source_weekly_assumed"
                else:
                    value=predicted_wage(row,baseline,club_cal.get(year,{}),club_ratings[year])
                    provenance="game_estimate_"+baseline_method
                reference_2026_wage=reference_2026_key=reference_match=None
                if year==2027 and source is None:
                    (value,provenance,reference_match,
                     reference_2026_wage,reference_2026_key)=revise_fc27_wage(
                        row,value,fc27_prev)
                    if reference_2026_wage is not None:
                        q["fc27_reference_carries"]+=1
                        q["fc27_same_club_carries" if "same_club" in provenance
                          else "fc27_changed_club_blends"]+=1
                expiry,expiry_method=_season_contract_end(
                    year,row["source_expiry"],row["key"],row["age"])
                tier=role_level(row["rating"],club_ratings[year].get(row["club"],[]))
                wages.append((row["key"],year,
                    str(row["raw_wage"] or "") or None,row["currency"],
                    round(source) if source is not None else None,value,
                    provenance,str(row["source_expiry"] or "") or None,
                    expiry,expiry_method,tier,VERSION,row["wage_warning"],
                    reference_2026_wage,reference_2026_key,reference_match))
                q[provenance]+=1
                q["game_expiry_estimated" if expiry_method.startswith("estimated") else "source_expiry_year"]+=1
                if row["loan_parent"]:
                    parent_key,status=resolve_parent(
                        row["loan_parent"],row["club"],club_names[year])
                    # 50% wage split is a modelled starting-point convention,
                    # never described as source evidence.
                    loan_records.append((row["key"],year,row["club"],row["loan_parent"],
                        parent_key,status,f"{year}-06-30",
                        "modelled_end_of_starting_season",50,
                        "game_model_assumption_50pct",VERSION))
                    q["loan_"+status]+=1
            db.executemany("""INSERT INTO starting_player_finances
                (player_key,edition,raw_wage,raw_wage_currency,source_wage_weekly_gbp,
                 model_weekly_wage_gbp,wage_provenance,source_expiry_raw,
                 game_contract_expires_on,expiry_provenance,estimated_squad_tier,
                 model_version,wage_quality_warning,reference_2026_weekly_wage_gbp,
                 reference_2026_player_key,reference_2026_match_status)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",wages)
            db.executemany("""INSERT INTO starting_source_loans
                (player_key,edition,borrower_club_key,raw_parent_club,
                resolved_parent_club_key,parent_status,game_return_date,
                return_date_status,simulated_borrower_wage_share_pct,
                salary_share_status,model_version)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",loan_records)
            q["players"]=len(wages)
            q["loans"]=len(loan_records)
            q["source_valid_wages"]=sum(v["observed"] is not None for v in annual[year])
            q["holdout_n"]=len(errors)
            q["holdout_median_multiplicative_error"]=(
                round(math.exp(median(errors)),3) if errors else None)
            q["median_simulated_weekly_wage"]=round(median(w[5] for w in wages))
            q["source_baseline_reference"]=round(baseline,2)
            q["baseline_method"]=baseline_method
            quality[str(year)]=dict(q)
            totals.update({k:v for k,v in q.items() if isinstance(v,int) and
                           (k in ("players","loans","source_valid_wages") or k.startswith("loan_"))})
            print(f"{year}: {len(wages):,} men-only players; sourced wages={q['source_valid_wages']:,}; "
                  f"loan parents={len(loan_records):,}; resolved={q.get('loan_resolved',0):,}; "
                  f"median model wage £{q['median_simulated_weekly_wage']:,}/week; "
                  f"holdout x{q['holdout_median_multiplicative_error']}",flush=True)
        # Existing borrower registration determines the squad. The ownership
        # ledger uses 50/50 parent/borrower for RESOLVED modelled loans only.
        # Unknown parents remain unlinked rather than introducing fake owners.
        payroll=defaultdict(int)
        loans={k:(p,b) for k,p,b in db.execute("""SELECT player_key,
                resolved_parent_club_key,borrower_club_key
                FROM starting_source_loans WHERE parent_status='resolved'""")}
        for key,club,wage in db.execute("""SELECT p.player_key,p.club_key,
            f.model_weekly_wage_gbp FROM players p JOIN starting_player_finances f
            ON f.player_key=p.player_key WHERE p.club_key IS NOT NULL"""):
            linked=loans.get(key)
            if linked:
                parent,borrower=linked
                borrower_share=round(wage*.5)
                payroll[borrower]+=borrower_share
                payroll[parent]+=wage-borrower_share
            else:
                payroll[club]+=wage
        for club,year in db.execute("SELECT club_key,edition FROM clubs"):
            existing=payroll[club]
            ceiling=max(existing+2000,round(existing*1.18))
            db.execute("""INSERT INTO starting_club_finances(
                club_key,edition,model_payroll_weekly_gbp,
                model_wage_ceiling_weekly_gbp,proposed_wage_headroom_weekly_gbp,
                financial_provenance) VALUES (?,?,?,?,?,'game_model_club_payroll_plus_18pct_headroom')""",
                (club,year,existing,ceiling,ceiling-existing))
        assert db.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
        assert db.execute("SELECT COUNT(*) FROM starting_player_finances").fetchone()[0]==317449
        assert db.execute("""SELECT COUNT(*) FROM starting_player_finances
                             WHERE model_weekly_wage_gbp IS NULL OR
                                   game_contract_expires_on IS NULL""").fetchone()[0]==0
        db.commit()
        report={
            "model_version":VERSION,"scope":"MENS_ONLY_CAREER_REFERENCE",
            "career_installed":False,"production_changed":False,
            "source_player_records":317449,"FC25_excluded":True,
            "original_source_archives_unchanged":True,
            "source_loan_end_dates_available":False,
            "loan_return_policy":"modelled June 30 starting season after verified PES season end",
            "loan_share_policy":"50% borrower share ONLY for modelled loan budget; not historical fact",
            "player_source_wages_provisional_game_units_not_verified_real_pay":True,
            "fc27_wage_correction":"Conservative verified ID+DOB+nationality link to FC26 source wages; same club carry +7.5% simulation, new club blend capped at 2.5x baseline",
            "fc27_2026_wage_carries_are_estimates_not_verified_salaries":True,
            "yearly":quality,"totals":dict(totals)
        }
        (output.parent/"STARTING_FINANCES_AND_LOANS_AUDIT.json").write_text(
            json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
        return report


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--catalog",required=True)
    p.add_argument("--source",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    print("COMPLETE "+json.dumps(build(a.catalog,a.source,a.output)["totals"]),flush=True)

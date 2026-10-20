"""Read-only 22-edition audit of contract, wages and incoming historical loans.

Runs on the exact preserved V2 22-year source archive. Never overwrites game
sources, introduces invented values or modifies career data. All percentages
refer to actual source CSV rows, not verified original game rosters.
"""
from __future__ import annotations

from collections import Counter
import argparse
import csv
import io
import json
import re
import statistics
from pathlib import Path
from zipfile import ZipFile
from scripts.export_fifa_pes_v2 import source_members

YEARS=set(range(2005,2028))-{2025}
BLANK={"","nan","na","n/a","null","none","unknown","--","-","not available"}
CATEGORIES={
    "wage":("wage","salary","earnings","pay_per_week"),
    "contract":("contract","expiry","expires","expiration","expire","valid_until","contract_until"),
    "loan":("loan","borrower","parent_club","temporary_transfer"),
    "transfer_value":("value_eur","value_gbp","market_value","transfer_value"),
    "club_joined":("joined","club_joined","team_joined"),
}
LOAN_PARENT=("club_loaned_from","loaned_from","loanedFrom","parent_club","parent_team")
LOAN_END=("loan_end_date","loan_end","club_loan_end","loan_expires","loaned_until",
          "club_loaned_until","loan_expiry")
MONEY=re.compile(r"^\s*([€£$])?\s*([+-]?\d+(?:[,.]\d+)*)(?:\s*([KM]))?\s*([€£$])?\s*$",re.I)


def present(value):
    return str(value or "").strip().casefold() not in BLANK


def column_category(name):
    normalized=str(name).lower().replace(" ","_").replace("-","_")
    return [key for key,keys in CATEGORIES.items() if any(k in normalized for k in keys)]


def parse_amount(value):
    if not present(value):
        return None
    text=str(value).strip().replace("\u00a0","")
    match=MONEY.fullmatch(text)
    if match is None:
        return None
    sign,number,multiplier,ending=match.groups()
    number=number.replace(",","")
    try:
        value=float(number)
    except ValueError:
        return None
    return round(value*({"K":1000,"M":1000000}.get((multiplier or "").upper(),1)),2)


def _columns(archive,member):
    with archive.open(member) as stream:
        reader=csv.DictReader(io.TextIOWrapper(stream,encoding="utf-8-sig",errors="replace",newline=""))
        header=reader.fieldnames or []
        if not header or len(header)!=len(set(header)):
            raise ValueError("Missing or repeated field names in "+member)
        by_name={}
        for name in header:
            types=column_category(name)
            if types:by_name[name]=types
        stats={name:{"present":0,"parseable_amount":0,"numeric_examples":[],
                     "examples":[], "currency_examples":Counter()} for name in by_name}
        count=0
        loan_records=0
        explicitly_unknown_loan=0
        for row in reader:
            if not any(present(x) for x in row.values()):
                continue
            count+=1
            parent=next((str(row[k]).strip() for k in LOAN_PARENT
                         if k in row and present(row.get(k))),None)
            if parent:
                loan_records+=1
            elif any(k in row for k in LOAN_PARENT):
                explicitly_unknown_loan+=1
            for key,meta in stats.items():
                v=row.get(key)
                if not present(v):
                    continue
                meta["present"]+=1
                if len(meta["examples"])<5 and str(v).strip() not in meta["examples"]:
                    meta["examples"].append(str(v).strip()[:60])
                if "wage" in by_name[key]:
                    amount=parse_amount(v)
                    if amount is not None:
                        meta["parseable_amount"]+=1
                        if len(meta["numeric_examples"])<10000:
                            meta["numeric_examples"].append(amount)
                    currencies=[c for c in ("€","£","$") if c in str(v)]
                    for c in currencies:
                        meta["currency_examples"][c]+=1
        for key,meta in stats.items():
            nums=meta.pop("numeric_examples")
            meta["numeric_min_median_max"]=(
                [round(min(nums),2),round(statistics.median(nums),2),round(max(nums),2)]
                if nums else None)
            meta["currency_examples"]=dict(meta["currency_examples"])
            meta["coverage_pct"]=round(100*meta["present"]/count,2) if count else 0
        return {"rows":count,"headers":header,"fields":stats,
                "loan_parent_rows":loan_records,
                "rows_without_known_loan_parent":explicitly_unknown_loan,
                "loan_parent_fields":[x for x in LOAN_PARENT if x in header],
                "loan_end_fields":[x for x in LOAN_END if x in header]}


def audit(source,out):
    with ZipFile(source) as z:
        files=source_members(z)
        if set(files)!=YEARS:
            raise ValueError("Require full 22-edition V2 source set; never patch FC25")
        manifests=[k for k in z.namelist() if k.endswith("/MANIFEST.json")]
        if len(manifests)!=1:
            raise ValueError("Expected one immutable source manifest")
        data=json.loads(z.read(manifests[0]))
        entries={int(e["edition"]):e for e in data["downloads"]}
        results={}
        for year in sorted(YEARS):
            entry=entries[year]
            meta=_columns(z,files[year])
            if meta["rows"]!=entry["player_rows"]:
                raise ValueError(f"{year}: row count differs from source archive manifest")
            meta["source_provider"]=entry.get("catalog_source","unknown")
            results[str(year)]=meta
            print(f"{year}: {meta['rows']:,} rows; contract/wage fields "+
                  ", ".join(meta["fields"])+
                  f"; loan-parent records {meta['loan_parent_rows']:,}",flush=True)
    final={"scope":"READ_ONLY_V2_SOURCE_COVERAGE_AUDIT",
           "preserved_source_zip_not_modified":True,
           "source_row_count_including_gender_unspecified":sum(r["rows"] for r in results.values()),
           "FC25_excluded":True,
           "estimated_wages_generated":False,
           "FX_conversion_applied":False,
           "all_values_raw_source_units":True,
           "note":"Source-year coverage includes unfiltered input (FC27 has 1940 women excluded downstream in the men's career catalogue). Do not treat currency symbols, contract year values or empty cells as verified weekly GBP / precise expiry dates. This is a field-presence audit.",
           "editions":results}
    output=Path(out)
    output.mkdir(parents=True,exist_ok=True)
    (output/"CONTRACT_SOURCE_COVERAGE.json").write_text(
        json.dumps(final,indent=2,ensure_ascii=False),encoding="utf-8")
    with (output/"CONTRACT_SOURCE_COVERAGE.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.writer(f)
        writer.writerow(("edition","source_players","source_provider","field","category",
                         "present","coverage_pct","parseable_money","min_median_max",
                         "raw_example_values","loan_parent_rows","loan_end_fields"))
        for edition,r in results.items():
            for field,details in r["fields"].items():
                writer.writerow((edition,r["rows"],r["source_provider"],field,
                                 "|".join(column_category(field)),details["present"],
                                 details["coverage_pct"],details["parseable_amount"],
                                 details["numeric_min_median_max"],
                                 " | ".join(details["examples"]),r["loan_parent_rows"],
                                 "|".join(r["loan_end_fields"])))
            if not r["fields"]:
                writer.writerow((edition,r["rows"],r["source_provider"],"(none)","",0,0,0,"","",
                                 r["loan_parent_rows"],"|".join(r["loan_end_fields"])))
    return final


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",required=True)
    ap.add_argument("--output",required=True)
    a=ap.parse_args()
    result=audit(a.source,a.output)
    print("AUDIT TOTAL "+str(result["source_row_count_including_gender_unspecified"]),flush=True)

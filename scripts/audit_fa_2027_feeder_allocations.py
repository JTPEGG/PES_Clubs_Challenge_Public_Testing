"""Reconcile FA official 2026/27 step-1/2 allocations with independent fixtures.

Official FA allocation date 14 May 2026; allocations may subsequently change.
No silent replacement of fixture observations and no simulated clubs.
"""
import argparse,csv,json
from collections import defaultdict
from pathlib import Path
from world_historical_competition_registry import canonical

OFFICIAL_VARIANTS={
    "AFC Telford United":"AFC Telford",
    "King's Lynn Town":"King’s Lynn",
    "Scarborough Athletic":"Scarborough",
    "Bedford Town":"Bedford",
    "Billericay Town":"Billericay",
    "Braintree Town":"Braintree",
    "Chelmsford City":"Chelmsford",
    "Chesham United":"Chesham",
    "Dagenham & Redbridge":"Dag & Red",
    "Dorking Wanderers":"Dorking",
    "Dover Athletic":"Dover",
    "Ebbsfleet United":"Ebbsfleet",
    "Farnham Town":"Farnham",
    "Folkestone Invicta":"Folkestone",
    "Hampton & Richmond Borough":"Hampton & Richmond",
    "Harborough Town":"Harborough",
    "Hednesford Town":"Hednesford",
    "Hemel Hempstead Town":"Hemel Hempstead",
    "Maidenhead United":"Maidenhead",
    "Maidstone United":"Maidstone",
    "Slough Town":"Slough",
    "Spennymoor Town":"Spennymoor",
    "Tonbridge Angels":"Tonbridge",
    "Torquay United":"Torquay",
    "Truro City":"Truro",
    "Worksop Town":"Worksop",
}

def key(name):
    return canonical(OFFICIAL_VARIANTS.get(name,name))

def audit(source,fixture_csv,output):
    doc=json.loads(Path(source).read_text(encoding="utf-8"))
    if (doc["edition"]!=2027 or doc["season"]!="2026-27"
        or doc["sport"]!="men"
        or "2026_05_14" not in doc["status"]
        or not doc["source_url"].startswith("https://www.thefa.com/")):
        raise ValueError("FA dated men's source / edition mismatch")
    divisions=doc["divisions"]
    if sorted(d["code"] for d in divisions)!=["en.5","en.6n","en.6s"]:
        raise ValueError("NLS missing league boundary subdivisions")
    official={}
    for div in divisions:
        if len(div["clubs"])!=24 or len({key(x) for x in div["clubs"]})!=24:
            raise ValueError("Official NLS division must have 24 distinct clubs")
        for name in div["clubs"]:
            member=key(name)
            if member in official:
                raise ValueError("Same official club in multiple NLS divisions")
            official[member]=(div["code"],div["name"],name,div["step"])
    with open(fixture_csv,encoding="utf-8-sig",newline="") as f:
        fixture=list(csv.DictReader(f))
    by_div=defaultdict(dict)
    for row in fixture:
        if row["League_Code"] not in ("en.5","en.6n","en.6s"):
            continue
        if row["Edition"]!="2027" or row["Evidence_Status"]!="source_observation_pending_game_identity_review":
            raise ValueError("Fixture snapshot not review-only for FC27")
        k=key(row["Fixture_Club"])
        if k in by_div[row["League_Code"]]:
            raise ValueError("Overlapping fixture identity inside NLS division")
        by_div[row["League_Code"]][k]=row["Fixture_Club"]
    for div in divisions:
        if len(by_div[div["code"]])!=24:
            raise ValueError("Fixture snapshot incomplete for NLS division")
    found=[];missing=[];unlisted=[];matched=0
    for k,(code,comp,name,step) in sorted(official.items()):
        target=by_div[code].get(k)
        other=[i for i in by_div if i!=code and k in by_div[i]]
        status=("fixture_name_corroborates_FA_division" if target and not other
                else "conflicting_snapshot_division" if other
                else "official_FA_club_unmatched_in_snapshot")
        matched+=status=="fixture_name_corroborates_FA_division"
        found.append((2027,f"2027:{code}",step,comp,name,target or "",status,
            doc["source_url"],"2026-05-14"))
        if status!="fixture_name_corroborates_FA_division":
            missing.append((2027,code,comp,name,status,"2026-05-14"))
    for code,fixture_names in sorted(by_div.items()):
        for name,display in sorted(fixture_names.items()):
            if name not in official:
                unlisted.append((2027,code,display,
                    "fixture_club_not_in_FA_may_2026_allocations"))
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    def export(file,header,rows):
        with (out/file).open("w",encoding="utf-8-sig",newline="") as f:
            w=csv.writer(f);w.writerow(header);w.writerows(rows)
    export("FA_NLS_2027_OFFICIAL_ALLOCATION_CROSSCHECK.csv",
        ("Edition","Competition_Code","Step","Competition","Official_Club",
         "Matched_Snapshot_Club","Status","FA_Source_URL","Allocation_As_At"),
        found)
    export("FA_NLS_2027_MISSING_OR_CONFLICTING.csv",
        ("Edition","League_Code","Competition","Official_Club","Status","As_At"),
        missing)
    export("FA_NLS_2027_EXTRA_SNAPSHOT_NAMES.csv",
        ("Edition","League_Code","Snapshot_Club","Review_Reason"),unlisted)
    report={"edition":2027,"original_FA_allocations":72,
            "official_divisions":len(divisions),
            "snapshot_corroborated":matched,
            "review_differences":len(missing),
            "unlisted_snapshot_club_names":len(unlisted),
            "as_at":"2026-05-14","subject_to_appeals":True,
            "fixture_source_not_overwritten":True,
            "nonplayable_feeder_only":True,
            "all_careers_blocked":True}
    (out/"FA_NLS_2027_ALLOCATION_AUDIT.json").write_text(json.dumps(
        report,indent=2))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--official",required=True)
    p.add_argument("--fixtures",required=True)
    p.add_argument("--output",required=True)
    opt=p.parse_args()
    print(json.dumps(audit(opt.official,opt.fixtures,opt.output),indent=2))

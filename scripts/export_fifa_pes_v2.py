"""Build FIFA05–FC27 complete PES2020 rating CSV archive; FC25 remains GAP.

Uses the existing byte-preserved source archive. Does not overwrite source data,
does not load, touch, or merge any live career, and does not produce game binaries.
"""
from __future__ import annotations
import argparse
import csv
import io
import json
import re
from collections import Counter,defaultdict
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED

from world_fifa_pes_converter_v2 import (
    convert_v2, EditionContext, TARGETS, MODEL_VERSION, DISALLOWED_EDITIONS,
    validate_exportable, UnrestoredEdition, POSITION_FAMILY
)

BASIC=("source_edition","source_player_id","player_name","source_overall",
       "identity_dob","model_version","primary_position",
       "alternative_positions","position_fit_indices","export_status",
       "weak_foot_usage","weak_foot_accuracy","form","injury_resistance")
EXTRAS=("weak_foot_usage","weak_foot_accuracy","form","injury_resistance")
COLUMNS=list(BASIC)
for name in TARGETS:
    COLUMNS.extend((name,name+"_method",name+"_confidence",name+"_sources",
                    name+"_source_edition",name+"_calibration_shift"))
for name in EXTRAS:
    COLUMNS.append(name+"_method")


def source_members(archive):
    files={}
    for name in archive.namelist():
        matched=re.search(r"/data/(\d{4})_[^/]+\.csv$",name)
        if matched:
            edition=int(matched.group(1))
            if edition in files:raise ValueError("Duplicate FIFA edition in original archive")
            files[edition]=name
    return files


def read_ed(archive,files,year):
    if year not in files or year in DISALLOWED_EDITIONS:return []
    with archive.open(files[year]) as stream:
        text=io.TextIOWrapper(stream,encoding="utf-8-sig",errors="replace",newline="")
        return list(csv.DictReader(text))


def to_csv_row(p):
    val={x:p[x] for x in BASIC if x not in EXTRAS and x!="alternative_positions"}
    val["alternative_positions"]=json.dumps(p["alternative_positions"])
    val["position_fit_indices"]=json.dumps(p["position_fit_indices"],sort_keys=True)
    for name,field in p["abilities"].items():
        val[name]=field["value"]
        val[name+"_method"]=field["method"]
        val[name+"_confidence"]=field["confidence"]
        val[name+"_sources"]=json.dumps(field["source_columns"],ensure_ascii=False)
        val[name+"_source_edition"]=json.dumps(field["source_edition"])
        val[name+"_calibration_shift"]=field.get("calibration_shift",0)
    for name,v in p["additional"].items():
        val[name]=v["value"]
        val[name+"_method"]=v["method"]
    return val


def export(source_zip,destination,*,years=None,limit_per_edition=None,
           calibration=None,require_all_supported=False):
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    outcome={"model_version":MODEL_VERSION,
             "conversion_reference":"PES2020",
             "only_allowed_calibration_pair":"FIFA2020 -> PES2020",
             "calibration_offsets_applied":bool(calibration and calibration.get("offsets")),
             "calibration_fifa_edition":2020 if calibration else None,
             "calibration_reference":"PES2020" if calibration else None,
             "excluded_source_edition":2025,
             "excluded_reason":"FC25 detailed data unusable; wait for proper replacement",
             "source_archive_untouched":True,
             "game_binary_created":False,
             "per_edition":{}}
    with ZipFile(source_zip) as original,ZipFile(destination,"w",ZIP_DEFLATED,compresslevel=6,allowZip64=True) as out:
        members=source_members(original)
        if require_all_supported:
            required=set(range(2005,2028))-DISALLOWED_EDITIONS
            missing=sorted(required-set(members))
            if missing:
                raise ValueError("Missing mandatory non-FC25 editions: "+str(missing))
        wanted=sorted(x for x in members if years is None or x in years)
        if not wanted:raise ValueError("No matching FIFA year files")
        for year in wanted:
            if year in DISALLOWED_EDITIONS:
                outcome["per_edition"][str(year)]={
                    "status":"SOURCE_GAP_NOT_REPAIRED","source_players_converted":0
                }
                print(f"{year}: SKIPPED — FC25 source gap",flush=True)
                continue
            rows=read_ed(original,members,year)
            # No gap-year information (2025) is permitted to influence another
            # edition. Adjacent records are used only for exact ID + DOB.
            adjacent={}
            for near in (year-1,year+1,year-2,year+2):
                if near in members and near not in DISALLOWED_EDITIONS:
                    adjacent[near]=read_ed(original,members,near)
            context=EditionContext(year,rows,adjacent)
            current=rows if limit_per_edition is None else rows[:limit_per_edition]
            count=Counter()
            family_counts=defaultdict(Counter)
            filename=f"PES2020_v2/{year}_FIFA_to_PES2020_Complete.csv"
            with out.open(filename,"w") as raw:
                text=io.TextIOWrapper(raw,encoding="utf-8",newline="")
                writer=csv.DictWriter(text,fieldnames=COLUMNS)
                writer.writeheader()
                for i,row in enumerate(current):
                    try:
                        p=convert_v2(row,year,context=context,
                                     approved_calibration=calibration)
                        validate_exportable(p)
                    except Exception as e:
                        raise RuntimeError(f"{year} row {i}: {e}") from e
                    writer.writerow(to_csv_row(p))
                    count["players"]+=1
                    count["alternative_positions"]+=len(p["alternative_positions"])
                    family=POSITION_FAMILY.get(p["primary_position"],"OTHER")
                    family_counts[family]["players"]+=1
                    family_counts[family]["alternative_positions"]+=len(p["alternative_positions"])
                    for ability in p["abilities"].values():
                        count[ability["method"]]+=1
                        count["rating_values"]+=1
                        family_counts[family][ability["method"]]+=1
                        family_counts[family]["ratings"]+=1
                        if ability["value"] is None:count["missing"]+=1
                    for x in p["additional"].values():
                        count["auxiliary_values"]+=1
                        if x["value"] is None:count["missing_aux"]+=1
                text.flush()
            if not count["players"]:
                raise RuntimeError(f"{year}: empty player dataset")
            if count["rating_values"]!=25*count["players"]:
                raise RuntimeError(f"{year}: not 25 ratings for each player")
            if count["auxiliary_values"]!=4*count["players"]:
                raise RuntimeError(f"{year}: auxiliary PES attributes incomplete")
            if count["missing"] or count["missing_aux"]:
                raise RuntimeError(f"{year}: invalid missing PES attribute")
            outcome["per_edition"][str(year)]={
                "status":"FULLY_NUMERIC_ESTIMATED_OUTPUT",
                "source_player_rows":len(rows),
                "converted_players":count["players"],
                "numeric_core_completeness_pct":100.0,
                "reconstructed_rating_values":sum(
                    count[method] for method in (
                        "weighted_estimate","aggregate_reconstruction",
                        "related_same_edition","adjacent_edition_same_id_dob",
                        "same_edition_position_peer_median","position_ovr_prior")),
                "per_position_family":{k:dict(v) for k,v in
                    sorted(family_counts.items())},
                "ratings_written":count["rating_values"],
                "auxiliary_fields_written":count["auxiliary_values"],
                "alternative_positions_written":count["alternative_positions"],
                "methods":{k:v for k,v in count.items()
                           if k not in ("players","alternative_positions",
                                        "rating_values","auxiliary_values",
                                        "missing","missing_aux")},
            }
            print(f"{year}: {count['players']} players × 25 completed PES attributes",flush=True)
        out.writestr("PES2020_v2/MANIFEST.json",
            json.dumps(outcome,indent=2,ensure_ascii=False))
        out.writestr("PES2020_v2/README.txt",
            "VERSION 2 — ESTIMATED PES 2020 GAMEPLAY ATTRIBUTES\n"
            "22 playable source editions (FIFA05–FC27 EXCEPT FC25).\n"
            "FC25 intentionally stays a gap; source records are NOT patched.\n"
            "All export records contain 25 numeric abilities plus Weak Foot\n"
            "Usage, Weak Foot Accuracy, Form and Injury Resistance.\n"
            "Source years, original player IDs, method and confidence retained.\n"
            "FIFA20 is the ONLY permitted PES20 calibration source.\n"
            "Conversion is NOT a native Konami formula, nor an importable\n"
            "Xbox / PS4 / PC option file. PES identities, physical fields,\n"
            "playing styles, skills and game-file codec require further work.\n")
    return outcome


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--edition",action="append",type=int)
    p.add_argument("--limit-per-edition",type=int)
    p.add_argument("--calibration",help="Explicitly approved FIFA20/PES20 calibration JSON")
    p.add_argument("--require-all-supported",action="store_true",
                   help="Reject an incomplete 2005–2027 archive (FC25 remains excluded)")
    x=p.parse_args()
    calibration=json.loads(Path(x.calibration).read_text(encoding="utf-8")) if x.calibration else None
    result=export(x.source,x.output,years=set(x.edition) if x.edition else None,
                  limit_per_edition=x.limit_per_edition,calibration=calibration,
                  require_all_supported=x.require_all_supported)
    print(json.dumps({"model":result["model_version"],
                      "editions":{k:v["status"] for k,v in result["per_edition"].items()}},
                     indent=2),flush=True)

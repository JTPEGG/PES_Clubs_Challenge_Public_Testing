"""Convert the hard-copy annual FIFA archive to PES2020-style CSVs.

Outputs one CSV per edition in a ZIP, preserving measured vs estimated vs
unknown values and original source columns. This is not a PES .ted/.bin file.

Example:
 python -m scripts.export_fifa_pes_csvs \
 --source FIFA_05_to_FC_27_CSV_Hard_Copies.zip \
 --output FIFA_to_PES2020_estimated.csv.zip
"""
import argparse
import csv
import io
import json
from pathlib import Path
import re
from zipfile import ZipFile,ZIP_DEFLATED

from world_fifa_pes_converter import convert,TARGETS,MODEL_VERSION

BASE=("source_edition","source_player_id","player_name","source_overall",
      "model_version","primary_position","alternative_positions",
      "position_fit_indices")
FIELDNAMES=list(BASE)
for stat in TARGETS:
    FIELDNAMES.extend((stat,stat+"_method",stat+"_source_fields"))


def convert_file(source,edition,output,limit=None):
    writer=csv.DictWriter(output,fieldnames=FIELDNAMES)
    writer.writeheader()
    counts={"rows":0,"with_primary_position":0,"alternative_position_rows":0,
            "attributes_present":0,"attributes_missing":0,
            "direct_equivalents":0,"weighted_estimates":0,
            "aggregate_reconstructions":0}
    for original in csv.DictReader(source):
        if limit is not None and counts["rows"]>=limit:break
        obj=convert(original,edition)
        flat={k:obj[k] for k in BASE if k not in ("alternative_positions","position_fit_indices")}
        flat["alternative_positions"]=json.dumps(obj["alternative_positions"])
        flat["position_fit_indices"]=json.dumps(obj["position_fit_indices"])
        for key,value in obj["abilities"].items():
            flat[key]=value["value"] if value["value"] is not None else ""
            flat[key+"_method"]=value["method"]
            flat[key+"_source_fields"]=json.dumps(value["source_columns"])
            if value["value"] is None:
                counts["attributes_missing"]+=1
            else:
                counts["attributes_present"]+=1
            if value["method"]=="direct_equivalent":counts["direct_equivalents"]+=1
            if value["method"]=="weighted_estimate":counts["weighted_estimates"]+=1
            if value["method"]=="aggregate_reconstruction":counts["aggregate_reconstructions"]+=1
        writer.writerow(flat)
        counts["rows"]+=1
        counts["with_primary_position"]+=int(obj["primary_position"] is not None)
        counts["alternative_position_rows"]+=len(obj["alternative_positions"])
    return counts


def export_zip(source_zip,output_zip,*,years=None,limit_per_edition=None):
    """Stream original edition source files through the versioned converter."""
    output_zip=Path(output_zip)
    output_zip.parent.mkdir(parents=True,exist_ok=True)
    report={"model_version":MODEL_VERSION,
            "output_kind":"estimated_pes2020_attributes_not_native_Konami",
            "original_source_untouched":True,
            "per_edition":{},
            "calibration":"no_automatic_calibration",
            "note":"Individual source columns and methods are recorded beside every estimate."}
    with ZipFile(source_zip) as zsrc,ZipFile(output_zip,"w",compression=ZIP_DEFLATED) as zout:
        names=[(int(m.group(1)),name)
               for name in zsrc.namelist()
               if (m:=re.search(r"/data/(\d{4})_[^/]+\.csv$",name))]
        if not names:
            raise ValueError("No year-specific CSV files found under data/ in source archive")
        for year,filename in sorted(names):
            if years is not None and year not in years:continue
            target=f"PES2020_converted/{year}_pes2020_estimates.csv"
            with zsrc.open(filename) as raw:
                decoded=io.TextIOWrapper(raw,encoding="utf-8-sig",errors="replace",newline="")
                with zout.open(target,"w") as output:
                    writer=io.TextIOWrapper(output,encoding="utf-8",newline="")
                    counts=convert_file(decoded,year,writer,limit=limit_per_edition)
                    writer.flush()
            report["per_edition"][str(year)]=counts
            print(year,counts["rows"],"players,",counts["attributes_present"],"attributes",flush=True)
        zout.writestr("PES2020_converted/MANIFEST.json",
                      json.dumps(report,indent=2))
        zout.writestr("PES2020_converted/README.txt",
            "Experimental FIFA/FC -> PES 2020 attribute estimates\n"
            "25 abilities per player, each with mapping method/source fields.\n"
            "No native Konami overall rating or PES player skills are invented.\n"
            "Single-year files retain game edition; source CSVs remain unchanged.\n"
            "Modelled positional fit is NOT official PES positional overall.\n"
            "No file in this archive is a game-ready Xbox/PS4/PC option file.\n")
    return report


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--edition",action="append",type=int)
    p.add_argument("--limit-per-edition",type=int)
    args=p.parse_args()
    export_zip(args.source,args.output,
               years=set(args.edition) if args.edition else None,
               limit_per_edition=args.limit_per_edition)

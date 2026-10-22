"""Merge independently validated V2 rating shards into one playable-data starter.

The 22 converted editions have all 25 integer PES stats and 4 integer auxiliaries.
The data is NOT a native PES option file and is not proof of accurate ratings,
full official rosters, appearances, playing styles, or Xbox importability.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import io
import json
from pathlib import Path
from shutil import copyfileobj
from zipfile import ZipFile, ZIP_DEFLATED

from world_fifa_pes_converter_v2 import TARGETS, DISALLOWED_EDITIONS

YEARS=set(range(2005,2028))-DISALLOWED_EDITIONS
AUX=("weak_foot_usage","weak_foot_accuracy","form","injury_resistance")
REQUIRED_SHARDS={"legacy","restored","modern"}


def merge(source_zip,shard_dir,output):
    shard_dir=Path(shard_dir)
    files=sorted(shard_dir.glob("shard-*.zip"))
    labels={f.stem.removeprefix("shard-") for f in files}
    if labels!=REQUIRED_SHARDS:
        raise ValueError("Missing/extra shard ZIPs: "+repr(sorted(labels)))
    source=ZipFile(source_zip)
    parts=[]
    try:
        source_m=[p for p in source.namelist() if p.endswith("/MANIFEST.json")]
        if len(source_m)!=1:raise ValueError("Source manifest is not unique")
        srcmeta=json.loads(source.read(source_m[0]))
        if srcmeta.get("archive_version")!="PES_V2_STARTING_PLAYER_SOURCE_DATABASE_1.0":
            raise ValueError("Unrecognized selected source archive")
        sources={int(v["edition"]):v for v in srcmeta["downloads"]}
        if set(sources)!=YEARS:raise ValueError("Not precisely 22 source years")
        per_edition={}
        summary=Counter()
        identity_warnings={}
        output=Path(output)
        output.parent.mkdir(parents=True,exist_ok=True)
        with ZipFile(output,"w",ZIP_DEFLATED,compresslevel=6,allowZip64=True) as result:
            for file in files:
                archive=ZipFile(file)
                parts.append(archive)
                names=[n for n in archive.namelist() if n=="PES2020_v2/MANIFEST.json"]
                if len(names)!=1:raise ValueError(str(file)+": missing shard manifest")
                meta=json.loads(archive.read(names[0]))
                if meta.get("calibration_offsets_applied"):
                    raise ValueError("Unapproved FIFA20 calibration used!")
                for year_str,stats in meta["per_edition"].items():
                    year=int(year_str)
                    if year not in YEARS or year in per_edition:
                        raise ValueError("Duplicate, forbidden or unexpected player edition")
                    if stats["status"]!="FULLY_NUMERIC_ESTIMATED_OUTPUT":
                        raise ValueError(str(year)+" source not converted fully")
                    name=f"PES2020_v2/{year}_FIFA_to_PES2020_Complete.csv"
                    if name not in archive.namelist():
                        raise ValueError("Missing converted year CSV "+name)
                    if stats["source_player_rows"]!=sources[year]["player_rows"]:
                        raise ValueError("Lost source players in "+str(year))
                    if stats["converted_players"]!=sources[year]["player_rows"]:
                        raise ValueError("Source-to-CSV row parity failed in "+str(year))
                    if stats["source_provider"]!=sources[year]["catalog_source"]:
                        raise ValueError("Provider was changed without authorization")
                    # Source can contain legacy duplicates; count and disclose
                    # collisions rather than deleting any original records.
                    count=0
                    missing_ids=missing_names=missing_dob=0
                    ids=set()
                    duplicate_ids=0
                    family=Counter()
                    with archive.open(name) as raw:
                        text=io.TextIOWrapper(raw,encoding="utf-8",newline="")
                        reader=csv.DictReader(text)
                        mandatory=set(TARGETS)|set(AUX)|{
                            "source_player_id","namespaced_source_player_key",
                            "source_provider","identity_dob","primary_position"
                        }
                        if not mandatory <= set(reader.fieldnames or []):
                            raise ValueError(str(year)+": essential export fields missing")
                        for row in reader:
                            count+=1
                            for stat in TARGETS:
                                try:v=int(row[stat])
                                except (ValueError,TypeError):raise ValueError(f"{year} row {count}: {stat} not numeric")
                                if not 40<=v<=99:
                                    raise ValueError(f"{year} row {count}: {stat} outside PES limits")
                            for name_aux,low,high in (
                                ("weak_foot_usage",1,4),
                                ("weak_foot_accuracy",1,4),
                                ("form",1,8),
                                ("injury_resistance",1,3)
                            ):
                                try:v=int(row[name_aux])
                                except (ValueError,TypeError):raise ValueError(f"{year} row {count}: {name_aux} not numeric")
                                if not low<=v<=high:
                                    raise ValueError(f"{year} row {count}: {name_aux} outside PES limits")
                            key=row["namespaced_source_player_key"]
                            expected=f"{year}:{row['source_provider']}:{row['source_player_id']}"
                            if key!=expected:
                                raise ValueError(f"{year}: source player namespace mismatch")
                            missing_ids+=not str(row["source_player_id"]).strip() or str(row["source_player_id"]).lower()=="none"
                            missing_names+=not str(row.get("player_name") or "").strip()
                            missing_dob+=not str(row.get("identity_dob") or "").strip()
                            duplicate_ids+=key in ids
                            ids.add(key)
                            family[row["primary_position"]]+=1
                    if count!=stats["converted_players"]:
                        raise ValueError(str(year)+": actual CSV row count mismatch")
                    with archive.open(f"PES2020_v2/{year}_FIFA_to_PES2020_Complete.csv") as src, result.open(
                        f"PES2020_v2/{year}_FIFA_to_PES2020_Complete.csv","w") as dst:
                        copyfileobj(src,dst,1024*1024)
                    per_edition[year_str]=stats
                    identity_warnings[year_str]={
                        "missing_source_ids":missing_ids,
                        "duplicated_namespaced_ids":duplicate_ids,
                        "missing_player_names":missing_names,
                        "unresolved_DOB":missing_dob,
                        "sample_role_counts_from_full_csv":dict(family),
                    }
                    summary["player_records"]+=count
                    summary["core_attributes"]+=25*count
                    summary["auxiliary_attributes"]+=4*count
                    print(f"Final {year}: {count:,} player records validated",flush=True)
            if set(map(int,per_edition))!=YEARS:
                raise ValueError("Merged export missing edition(s)")
            if any("/2025_" in n for n in result.namelist()):
                raise ValueError("FC25 data accidentally merged")
            overall={
                "status":"READY_V2_ESTIMATED_PLAYER_DATABASE_STARTING_POINT",
                "conversion_reference":"PES2020",
                "calibration_source":"FIFA20 only; exploratory proposals NOT applied",
                "source_game_file_importable":False,
                "Xbox_option_file_created":False,
                "FC25":"SOURCE_GAP_NOT_RESTORED",
                "source_original_bytes_preserved":True,
                "full_original_in_game_rosters_verified":False,
                "cross_provider_ids_automatically_joined":False,
                "editions":len(YEARS),
                "converted_player_records":summary["player_records"],
                "validated_integer_PES_core_attributes":summary["core_attributes"],
                "validated_integer_auxiliary_fields":summary["auxiliary_attributes"],
                "per_edition":dict(sorted(per_edition.items())),
                "identity_audit":identity_warnings,
                "source_provenance":srcmeta,
            }
            result.writestr("PES2020_v2/MANIFEST.json",json.dumps(
                overall,indent=2,ensure_ascii=False))
            result.writestr("PES2020_v2/README.txt",
                "PES2020 V2 FINISHED NUMERIC PLAYER DATABASE STARTER\n\n"
                "22 annual player CSVs (FIFA05–FC27 excluding FC25) with every\n"
                "source record represented once per year and all 25 PES-style\n"
                "ratings + 4 auxiliary numeric fields. Core ratings are estimates.\n"
                "FIFA15–FIFA20 source years use whole-edition pinned SoFIFA\n"
                "snapshots; all other years retain existing pinned source sets.\n"
                "Source provider and provider-namespaced source ID included.\n"
                "Missing official squad/appearance/playing-style metadata must\n"
                "be resolved in the following PES player-editor stage.\n"
                "No native console / PC PES game import format is created.\n"
                "No guarantee of completeness against Konami/EA game rosters.\n"
                "FC25 intentionally missing; no FIFA19 calibration.\n")
        return overall
    finally:
        for p in parts:p.close()
        source.close()


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True)
    p.add_argument("--shards",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    x=merge(a.source,a.shards,a.output)
    print("FINAL V2 PLAYER DATABASE",json.dumps({
        "editions":x["editions"],
        "converted_player_records":x["converted_player_records"],
        "core_attributes":x["validated_integer_PES_core_attributes"],
        "auxiliary_attributes":x["validated_integer_auxiliary_fields"],
        "missing_source_ids":sum(v["missing_source_ids"] for v in x["identity_audit"].values()),
        "duplicated_namespaced_ids":sum(v["duplicated_namespaced_ids"] for v in x["identity_audit"].values()),
        "FC25_status":x["FC25"]
    }),flush=True)

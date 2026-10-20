"""Assemble a versioned full starting-point FIFA/PES source archive.

Uses exact existing FIFAIndex CSV source bytes for 2005–14; replaces WHOLE
2015–20 source editions with approved-for-baseline (not official) SoFIFA-derived
CSV snapshots; retains existing independent 2021–24, 2026–27 sources.
Never stitches together individual players from mismatched roster snapshots.
FC25 stays absent. Original two input archives are never changed.
"""
from __future__ import annotations
from collections import defaultdict
import argparse
import csv
import hashlib
import io
import json
import re
import unicodedata
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from scripts.export_fifa_pes_v2 import source_members
from scripts.source_coverage_v2 import source_coverage_status

ROOT="fifa_to_pes_v2_selected_full_sources"
RESTORED=set(range(2015,2021))
REQUIRED=set(range(2005,2028))-{2025}
GAP=2025


def norm(value):
    return "".join(c for c in unicodedata.normalize(
        "NFKD",str(value or "")).casefold() if c.isascii() and c.isalnum())


def identity_candidates(raw, *, restored):
    reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig",errors="replace")))
    mapping=defaultdict(set)
    for index,row in enumerate(reader):
        date=str(row.get("dob" if restored else "birthdate") or "").strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}",date):
            continue
        nationality=norm(row.get("nationality"))
        if not nationality:continue
        for name in ("long_name","short_name") if restored else ("name",):
            normalized=norm(row.get(name))
            if normalized:
                mapping[(normalized,date[:10],nationality)].add(index)
    return mapping


def overlap_report(old_raw,new_raw):
    old=identity_candidates(old_raw,restored=False)
    new=identity_candidates(new_raw,restored=True)
    pairs=defaultdict(set)
    reverse=defaultdict(set)
    ambiguous_keys=0
    for key in old.keys() & new.keys():
        if len(old[key])!=1 or len(new[key])!=1:
            ambiguous_keys+=1
            continue
        oi,ni=next(iter(old[key])),next(iter(new[key]))
        pairs[oi].add(ni)
        reverse[ni].add(oi)
    links=[(oi,next(iter(ni))) for oi,ni in pairs.items()
           if len(ni)==1 and len(reverse[next(iter(ni))])==1]
    return {
        "unique_name_dob_nationality_candidate_matches":len(links),
        "ambiguous_identity_keys_rejected":ambiguous_keys,
        "cross_provider_id_linkage_verified":False,
        "player_rows_not_automatically_union_merged":True,
        "interpretation":"Same-name, birthdate and nationality are indicative only. "
                         "Snapshots and provider IDs are not interchangeable; "
                         "the six SoFIFA edition rosters replace entire old years.",
    }


def create_combined(old_zip,restored_zip,output):
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(old_zip) as old,ZipFile(restored_zip) as new:
        old_members=source_members(old)
        restored_members=source_members(new)
        if set(restored_members)!=RESTORED:
            raise ValueError("The restored archive must contain precisely FIFA15–FIFA20")
        if not REQUIRED <= set(old_members):
            raise ValueError("Original archive missing mandatory non-FC25 years")
        old_m=[n for n in old.namelist() if n.endswith("/MANIFEST.json")]
        new_m=[n for n in new.namelist() if n.endswith("/MANIFEST.json")]
        if len(old_m)!=1 or len(new_m)!=1:
            raise ValueError("Exactly one manifest required in each input")
        old_meta=json.loads(old.read(old_m[0]))
        new_meta=json.loads(new.read(new_m[0]))
        old_records={int(x["edition"]):x for x in old_meta["downloads"]}
        new_records={int(k):v for k,v in new_meta["editions"].items()}
        if set(new_records)!=RESTORED:
            raise ValueError("Restored metadata missing one or more editions")
        result={
            "archive_version":"PES_V2_STARTING_PLAYER_SOURCE_DATABASE_1.0",
            "status":"READY_FOR_PES_RATING_CONVERSION_NOT_NATIVE_IMPORT",
            "editions_expected":len(REQUIRED),
            "FC25":"EXCLUDED_NO_RATINGS_OR_SOURCE_ROWS",
            "all_original_files_untouched":True,
            "source_snapshots_not_verified_opening_day":True,
            "player_roster_coverage_not_independently_verified":True,
            "no_cross_provider_id_merges":True,
            "reference_calibration_game":"FIFA 2020 only (against PES 2020)",
            "ratings_calibration_performed":False,
            "downloads":[],
            "provider_crosswalk_quality_review":{},
        }
        with ZipFile(output,"w",ZIP_DEFLATED,compresslevel=6,allowZip64=True) as out:
            for year in sorted(REQUIRED):
                if year in RESTORED:
                    source_bytes=new.read(restored_members[year])
                    rec=new_records[year]
                    expected_sha=rec.get("sha256")
                    expected_rows=rec["player_rows"]
                    provider=new_meta["source_repository"]
                    source_url=rec["source_url"]
                    prior_bytes=old.read(old_members[year])
                    prior_sha=old_records[year].get("sha256")
                    if prior_sha and hashlib.sha256(prior_bytes).hexdigest()!=prior_sha:
                        raise ValueError(f"{year}: original source checksum mismatch")
                    result["provider_crosswalk_quality_review"][str(year)]=(
                        overlap_report(prior_bytes,source_bytes))
                    result["provider_crosswalk_quality_review"][str(year)].update({
                        "original_source_rows":old_records[year]["player_rows"],
                        "selected_source_rows":expected_rows,
                        "extra_source_rows_not_certified_extra_distinct_players":
                            expected_rows-old_records[year]["player_rows"],
                    })
                else:
                    source_bytes=old.read(old_members[year])
                    rec=old_records[year]
                    expected_sha=rec.get("sha256")
                    expected_rows=rec["player_rows"]
                    provider=rec.get("catalog_source","unknown")
                    source_url=rec["source_url"]
                if not expected_sha or hashlib.sha256(source_bytes).hexdigest()!=expected_sha:
                    raise ValueError(f"{year}: source SHA-256 mismatch")
                rows=sum(1 for r in csv.reader(io.StringIO(
                    source_bytes.decode("utf-8-sig",errors="replace")))
                    if r)-1
                if rows!=expected_rows:
                    raise ValueError(f"{year}: source manifest row count incorrect ({rows})")
                filename=f"{ROOT}/data/{year}_selected_source.csv"
                out.writestr(filename,source_bytes)
                result["downloads"].append({
                    "edition":year,"status":"DOWNLOADED",
                    "player_rows":rows,"catalog_source":provider,
                    "source_url":source_url,
                    "sha256":expected_sha,"filename":filename,
                    "origin":"RESTORED_WHOLE_EDITION" if year in RESTORED
                             else "PRESERVED_EXISTING_SOURCE",
                    "source_coverage_status":source_coverage_status(year,rows,provider),
                })
                print(f"{year}: selected {provider} {rows:,} original player rows",flush=True)
            if set(item["edition"] for item in result["downloads"])!=REQUIRED:
                raise RuntimeError("Final source coverage not exactly 22 editions")
            if any(x["edition"]==GAP for x in result["downloads"]):
                raise RuntimeError("FC25 must not be in game-source archive")
            result["source_rows"]=sum(x["player_rows"] for x in result["downloads"])
            result["six_restored_source_rows"]=sum(x["player_rows"] for x in
                result["downloads"] if x["edition"] in RESTORED)
            out.writestr(f"{ROOT}/MANIFEST.json",json.dumps(
                result,indent=2,ensure_ascii=False))
            out.writestr(f"{ROOT}/README.txt",(
                "VERSIONED FIFA 2005–2027 PLAYER SOURCES FOR PES2020 V2\n"
                "22 source years, excluding FC25. Source bytes remain unchanged.\n"
                "FIFA15–20 are full-year replacements from one pinned SoFIFA series.\n"
                "Other years remain the original verified-download source CSVs.\n"
                "PES gameplay ratings estimated separately; not Konami native ratings.\n"
                "NO original game roster coverage or launch snapshot is guaranteed.\n"
                "Cross-provider candidate matches never merge roster players.\n"
                "No PES native option file, game career, or Render production change.\n"))
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--original-source",required=True)
    p.add_argument("--restored-source",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    result=create_combined(a.original_source,a.restored_source,a.output)
    print("READY CONVERSION INPUT",json.dumps({
        "edition_count":result["editions_expected"],
        "player_rows":result["source_rows"],
        "six_restored_source_rows":result["six_restored_source_rows"],
        "FC25_excluded":True,
        "cross_provider_matches":{
            k:v["unique_name_dob_nationality_candidate_matches"]
            for k,v in result["provider_crosswalk_quality_review"].items(),
        }
    }),flush=True)

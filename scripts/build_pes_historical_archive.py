"""Create actual hard-copy PES2020 attribute + cross-edition PlayersDB CSV archive.

Downloads from pinned public research repository and PlayersDB's explicit
/download/csv endpoint. Source CSVs are byte-preserved and stored separately;
cross-era identity data must never be represented as vintage ability ratings.

No archive/player data is committed into the public Git repo. Emits ZIP and
independent manifest. SHA256 checksums and row counts are verified.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
from urllib.request import Request, urlopen
from zipfile import ZipFile, ZIP_DEFLATED

ROOT="PES_Historical_Databases"
SOURCES=(
    {
        "id":"pes_2020_native_attributes",
        "label":"PES 2020 native ability and ratings dataset",
        "url":"https://raw.githubusercontent.com/mlblbc/pes---Data-visualization-project/5882c0023a7f16eda4599adc87c7ba160aa9411e/pes_2020.csv",
        "filename":"PES_2020_Native_Player_Attributes.csv",
        "min_rows":14000,
        "expected_columns":{
            "name","team_name","nationality","age","registered_position",
            "offensive_awareness","ball_control","dribbling","tight_possession",
            "low_pass","lofted_pass","finishing","heading","place_kicking",
            "curl","speed","acceleration","kicking_power","jump",
            "physical_contact","balance","stamina","defensive_awareness",
            "ball_winning","aggression","gk_awareness","gk_catching",
            "gk_clearing","gk_reflexes","gk_reach",
            "rating_as_GK","rating_as_CB","rating_as_LB","rating_as_RB",
            "rating_as_DMF","rating_as_CMF","rating_as_LMF","rating_as_RMF",
            "rating_as_AMF","rating_as_LWF","rating_as_RWF",
            "rating_as_SS","rating_as_CF","playing_style"
        },
        "scope":"PES 2020 edition-specific data with native attributes, position ratings, skills, and playing style. Research copy, not a Konami game-file export.",
    },
    {
        "id":"playersdb_historical_pes_identities",
        "label":"PlayersDB cross-edition PES and eFootball identity database",
        "url":"https://playersdb.app/download/csv",
        "filename":"PES_eFootball_Historical_Player_Identities.csv",
        "min_rows":100000,
        "expected_columns":{
            "konamiID","playerName","fullName","nationalities","birthdate",
            "height","weight","strongFoot","registeredPosition",
            "positions","game_versions","base_konami_id"
        },
        "scope":"Historical Konami player IDs, identity, biographical fields, game-version coverage, and position references; does NOT contain player ability scores or FIFA IDs in the exported CSV.",
    }
)


def download(url,path,max_bytes=100_000_000):
    request=Request(url,headers={
        "User-Agent":"PES-Challenge-Historical-Archive/1.0",
        "Accept":"text/csv,*/*"
    })
    digest=hashlib.sha256()
    total=0
    with urlopen(request,timeout=120) as resp,path.open("wb") as out:
        for _ in range(200):
            chunk=resp.read(1024*512)
            if not chunk:break
            total+=len(chunk)
            if total>max_bytes:
                raise ValueError("Source exceeds max download size")
            out.write(chunk)
            digest.update(chunk)
        else:
            raise ValueError("Archive source unexpectedly exceeds chunk limit")
    if total<100_000:raise ValueError("File implausibly small")
    with path.open("rb") as check:
        head=check.read(1024).lower().lstrip()
        if head.startswith(b"<!doctype") or head.startswith(b"<html"):
            raise ValueError("Server returned HTML, not CSV")
    return digest.hexdigest(),total


def audit_csv(path,expected,min_rows):
    with path.open("r",encoding="utf-8-sig",newline="",errors="replace") as source:
        reader=csv.reader(source)
        columns=next(reader)
        if len(columns)<15 or len(columns)>250:
            raise ValueError(f"Unexpected header width: {len(columns)}")
        absent=sorted(expected-set(columns))
        if absent:
            raise ValueError(f"Missing required source columns: {absent}")
        count=0
        for row in reader:
            if row and any(str(v).strip() for v in row):
                count+=1
        if count<min_rows:
            raise ValueError(f"Unexpectedly few player records: {count}")
    return count,columns


def create_zip(output,manifest_output=None):
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix="pes_historical_source_"))
    rows=[]
    try:
        for item in SOURCES:
            file=temp/item["filename"]
            sha,bytes_count=download(item["url"],file)
            count,columns=audit_csv(file,item["expected_columns"],item["min_rows"])
            rows.append({
                "source_id":item["id"],"label":item["label"],
                "relative_path":f"{ROOT}/data/{item['filename']}",
                "source_url":item["url"],
                "sha256":sha,"bytes":bytes_count,"player_rows":count,
                "column_count":len(columns),"columns":columns,"scope":item["scope"],
                "source_file":str(file)
            })
            print(f"{item['id']}: {count:,} rows, {len(columns)} columns, {bytes_count:,} bytes; SHA256={sha}",flush=True)
        report={
            "archive_format":"PES_historical_hardcopy_v1",
            "sources": [{k:v for k,v in row.items() if k!="source_file"} for row in rows],
            "datasets_collected":len(rows),
            "row_occurrences_not_unique_players":sum(x["player_rows"] for x in rows),
            "coverage_notice":"Only PES 2020 has native ability stats. PlayersDB covers multiple game editions but is an identity/position index, not annual PES attribute CSVs.",
            "missing_pes_editions":"Other annual PES datasets are not included because no equivalent source CSV was independently verified.",
            "career_database_modified":False,
        }
        manifest_head=["Source ID","Description","Filename","Rows","Columns","Bytes","SHA256","Original source URL","Scope"]
        manifest=io.StringIO()
        writer=csv.writer(manifest)
        writer.writerow(manifest_head)
        for x in rows:
            writer.writerow([x["source_id"],x["label"],x["relative_path"],
                             x["player_rows"],x["column_count"],x["bytes"],
                             x["sha256"],x["source_url"],x["scope"]])
        with ZipFile(output,"w",ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
            for x in rows:
                z.write(x["source_file"],x["relative_path"])
            z.writestr(f"{ROOT}/MANIFEST.csv",manifest.getvalue().encode("utf-8-sig"))
            z.writestr(f"{ROOT}/MANIFEST.json",json.dumps(report,indent=2,ensure_ascii=False))
            z.writestr(f"{ROOT}/README.txt",(
                "HISTORICAL PRO EVOLUTION SOCCER DATA ARCHIVE\n"
                "================================================\n"
                "Contains two independently sourced and UNMODIFIED CSV files:\n"
                "1. PES 2020 native player attributes (25 ratings, 13 positional OVRs, skills).\n"
                "2. PlayersDB PES/eFootball player identity and game-version archive.\n"
                "PlayersDB identity CSV spans many editions but contains NO native abilities.\n"
                "No annual PES 2005-2019 full native-attribute CSVs are included.\n"
                "The records are not joined or deduplicated across these sources.\n"
                "Use MANIFEST.json and SHA256 values to verify each original file.\n"
                "These are research source CSVs, not Xbox/PS4 game option files.\n"
            ).encode("utf-8"))
        if manifest_output:
            p=Path(manifest_output)
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text(manifest.getvalue(),encoding="utf-8-sig")
        print("PES ARCHIVE CREATED:",json.dumps({
            "zip":str(output),"zip_bytes":output.stat().st_size,
            "source_csvs":len(rows),
            "rows":{x["source_id"]:x["player_rows"] for x in rows},
            "columns":{x["source_id"]:x["column_count"] for x in rows},
        }),flush=True)
        return report
    finally:
        shutil.rmtree(temp,ignore_errors=True)


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default="dist/PES_Historical_Database_Hard_Copies.zip")
    ap.add_argument("--manifest",default="dist/PES_Historical_Archive_Manifest.csv")
    args=ap.parse_args()
    create_zip(args.output,args.manifest)

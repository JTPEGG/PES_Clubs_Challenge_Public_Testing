"""Archive actual per-edition FIFA/FC CSVs without homogenising schemas.

Input: docs/warehouse/fifa_fc_annual_sources_2000_2027.json
Result: one ZIP with original CSV bytes, checksums, per-year row counts
and a five-year missing-data notice. Never commits source player files.

Files are downloaded only from existing source URLs. Each source's game
edition stays separate; launch/winter snapshot status is not invented.
"""
import argparse
import concurrent.futures
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import urllib.error
from urllib.parse import quote
from urllib.request import Request, urlopen
from zipfile import ZipFile, ZIP_DEFLATED

CATALOG=Path(__file__).resolve().parents[1] / "docs" / "warehouse" / "fifa_fc_annual_sources_2000_2027.json"
GITHUB_REPO_FIFA23="miraehab/FIFA-23-ML-Project"
GITHUB_SHA_FIFA23="0d188076fa37b3d82c5d390048e00ec5a43b04a7"
GITHUB_PATH_FIFA23="players_fifa23.csv"
MAX_FILE_SIZE=100_000_000
MIN_FILE_SIZE=100_000
ARCHIVE_DIR="fifa_fc_2000_2027"


def resolve_source(row):
    y=row["edition"]
    if y<2005:
        return None
    if y==2023:
        return ("https://raw.githubusercontent.com/"
                +GITHUB_REPO_FIFA23+"/"+GITHUB_SHA_FIFA23+"/"
                +quote(GITHUB_PATH_FIFA23))
    url=row["url"]
    if "github.com/" not in url or "/blob/" not in url:
        raise ValueError(f"No downloadable pinned CSV URL for {y}")
    # GitHub blob URL -> stable raw.githubusercontent.com path,
    # preserving encoded spaces for files with non-simple filenames.
    return url.replace("https://github.com/","https://raw.githubusercontent.com/").replace("/blob/","/")


def file_name(row):
    return f"{row['edition']}_{row['label'].lower().replace(' ','_')}.csv"


def fetch_one(row,tempdir):
    y=row["edition"]
    url=resolve_source(row)
    if url is None:
        return {"edition":y,"status":"UNAVAILABLE","source_url":row.get("url",""),
                "reason":row.get("notes","No verified structured downloadable CSV")}
    local=tempdir/file_name(row)
    error=None
    for n in range(3):
        try:
            req=Request(url,headers={
                "User-Agent":"PES-Challenge-Archive/1.0 (reproducible sources)",
                "Accept":"text/csv, application/octet-stream;q=0.9,*/*;q=0.5"
            })
            digest=hashlib.sha256()
            size=0
            with urlopen(req,timeout=75) as response, local.open("wb") as out:
                code=getattr(response,"status",200)
                if code!=200:raise OSError(f"HTTP {code}")
                while True:
                    block=response.read(1024*1024)
                    if not block:break
                    size+=len(block)
                    if size>MAX_FILE_SIZE:raise ValueError("File exceeds 100MB limit")
                    digest.update(block)
                    out.write(block)
            if size<MIN_FILE_SIZE:
                raise ValueError(f"Suspiciously small CSV: {size} bytes")
            with local.open("rb") as fp:
                pre=fp.read(450)
                if pre.startswith(b"version https://git-lfs") or b"<html" in pre.lower():
                    raise ValueError("Download is LFS pointer or HTML, not a CSV")
            with local.open("r",encoding="utf-8-sig",errors="replace",newline="") as fp:
                reader=csv.reader(fp)
                header=next(reader)
                ncols=len(header)
                if not 5<=ncols<=500:
                    raise ValueError(f"Unexpected CSV columns: {ncols}")
                nrows=sum(1 for row in reader if row and any(x.strip() for x in row))
            if nrows<100:
                raise ValueError(f"Suspicious player count: {nrows}")
            result={"edition":y,"label":row["label"],"status":"DOWNLOADED",
                    "filename":f"{ARCHIVE_DIR}/data/{file_name(row)}",
                    "source_url":url,
                    "catalog_source":row.get("source",""),
                    "catalog_snapshot_note":row.get("notes",""),
                    "source_bytes":size,"player_rows":nrows,"columns":ncols,
                    "sha256":digest.hexdigest(),"header_columns":header}
            print(f"[OK] {row['label']}: {nrows:,} player rows, {ncols} fields, {size/1e6:.2f} MB",flush=True)
            return result
        except Exception as exc:
            error=f"{type(exc).__name__}: {exc}"
            local.unlink(missing_ok=True)
            print(f"[retry {n+1}/3] {y}: {error}",flush=True)
            if n<2:time.sleep(2*(n+1))
    return {"edition":y,"status":"DOWNLOAD_FAILED",
            "source_url":url,"reason":error}


def create_archive(output_zip,dir_for_uncompressed=None,workers=5):
    catalog=json.loads(CATALOG.read_text(encoding="utf-8"))
    rows=catalog["records"]
    assert [p["edition"] for p in rows]==list(range(2000,2028))
    folder=Path(tempfile.mkdtemp(prefix="pes_fifa_yearly_"))
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            details=list(pool.map(lambda row:fetch_one(row,folder),rows))
        complete=[v for v in details if v["status"]=="DOWNLOADED"]
        missing=[v for v in details if v["status"]!="DOWNLOADED"]
        json_report={
            "archive_version":"1.0",
            "series":"FIFA 2000 to EA FC 27",
            "editions_expected":len(rows),
            "actual_csv_count":len(complete),
            "total_player_rows_across_editions":sum(x["player_rows"] for x in complete),
            "archive_scope":"edition-specific native source files; original CSV bytes; no schema union",
            "note":"FIFA2005 means football season 2004/05; snapshots are not necessarily launch rosters.",
            "downloads":details,
            "unavailable":missing,
        }
        output_zip=Path(output_zip)
        output_zip.parent.mkdir(parents=True,exist_ok=True)
        with ZipFile(output_zip,"w",compression=ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
            for v in sorted(complete,key=lambda x:x["edition"]):
                z.write(folder/file_name(v),v["filename"])
            # Don't accidentally label any missing edition as collected.
            top=[["Edition","Game","Status","CSV filename","Rows","Columns","Bytes",
                  "SHA256","Original source URL","Notes"]]
            for row,stat in zip(rows,details):
                top.append([
                    row["edition"],row["label"],stat["status"],stat.get("filename",""),
                    stat.get("player_rows",""),stat.get("columns",""),stat.get("source_bytes",""),
                    stat.get("sha256",""),stat.get("source_url",""),stat.get("reason","") or row.get("notes","")
                ])
            buf=io.StringIO()
            writer=csv.writer(buf);writer.writerows(top)
            z.writestr(f"{ARCHIVE_DIR}/MANIFEST.csv",buf.getvalue().encode("utf-8-sig"))
            z.writestr(f"{ARCHIVE_DIR}/MANIFEST.json",json.dumps(
                json_report,ensure_ascii=False,indent=2).encode("utf-8"))
            z.writestr(f"{ARCHIVE_DIR}/README.txt",(
                "FIFA/EA FC ANNUAL PLAYER DATA ARCHIVE\n\n"
                "This is a hard-copy collection of the individual source CSV files,\n"
                "one file per game edition, not a combined or re-rated database.\n"
                "CSV headers vary by edition. Do not treat game wages/values as real-world facts.\n"
                "Game 2005 = football season 2004/05. 2023 is a standalone year-specific CSV.\n"
                "SHA256 checksums, row counts, field headers and source URLs are in MANIFEST.\n"
                "FIFA 2000-2004: No verified downloadable tabular player file is included.\n"
                "FIFA 2004 community XLSX exists only as an UNVERIFIED archive claim.\n"
                "No full proprietary source data is committed to the project's public Git repo.\n"
                "No live careers, game files or Render records were changed.\n"
            ).encode("utf-8"))
            if dir_for_uncompressed:
                p=Path(dir_for_uncompressed)
                p.mkdir(parents=True,exist_ok=True)
                (p/"MANIFEST.json").write_text(
                    json.dumps(json_report,ensure_ascii=False,indent=2),encoding="utf-8")
                (p/"MANIFEST.csv").write_text(buf.getvalue(),encoding="utf-8-sig")
        zip_size=output_zip.stat().st_size
        print("ARCHIVE RESULT",json.dumps({
            "file":str(output_zip),"size_bytes":zip_size,
            "downloaded_editions":len(complete),
            "total_rows":json_report["total_player_rows_across_editions"],
            "missing_editions":[x["edition"] for x in missing],
        }),flush=True)
        # A complete 05->27 collection must contain 23 files. Early files are
        # explicitly documented as missing, never silently generated.
        unexpected=[x for x in missing if x["edition"]>=2005]
        if unexpected:
            print("ATTENTION: Unexpected download failures: "+repr(unexpected),flush=True)
            return 2
        return 0
    finally:
        shutil.rmtree(folder,ignore_errors=True)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="dist/PES_FIFA_FC_2000_to_2027_Archive.zip")
    p.add_argument("--manifest-dir",default="dist/reports")
    p.add_argument("--workers",type=int,default=5)
    args=p.parse_args()
    raise SystemExit(create_archive(args.output,args.manifest_dir,args.workers))

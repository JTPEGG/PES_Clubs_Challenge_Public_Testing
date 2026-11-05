"""Download & validate an immutable approved FC27 test-world release asset.

Render BUILD ONLY: no GitHub API token, Supabase account, or production saves.
The compressed SQLite is published from the previously approved frozen source
using a separate artifact-building workflow. Render's free ephemeral disk
means new careers may reset after instance replacement.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from time import sleep

from scripts.fc27_warehouse_world_bridge import DATASET

BASE="https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/releases/download/fc27-playtest-world-2026-10-27-v1"
ARCHIVE="FC27_659_PRESEASON_PLAYTEST_WORLD.sqlite.gz"
DESTINATION="fc27_playtest_world.sqlite"
# GitHub's immutable release-asset digest, checked from the official Releases
# API on 2026-11-05. Keep this pinned, independently of asset URL availability.
# This removes a fragile second request for the .sha256 release download, which
# began returning 504 on Render even though the approved asset still exists.
EXPECTED_SHA256="03a7b5075eee79ccf5f7ca8b898949ce5d42cc0fc999bdb0a92a17f163bcde7c"

def fetch(url):
    req=Request(url,headers={"User-Agent":"PES-FC27-Manual-Preview/1.0"})
    for attempt in range(4):
        try:
            return urlopen(req,timeout=120)
        except (HTTPError,URLError) as exc:
            if isinstance(exc,HTTPError) and exc.code not in (408,429,500,502,503,504):
                raise
            if attempt==3:
                raise
            sleep(2**attempt)

def run(destination):
    target=Path(destination).resolve()
    if target.exists():
        raise FileExistsError("Refuse to overwrite a possible saved test career: "+str(target))
    expected=EXPECTED_SHA256
    if len(expected)!=64 or any(c not in "0123456789abcdef" for c in expected):
        raise ValueError("Invalid pinned archive SHA256")
    h=hashlib.sha256()
    target.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix="fc27-preview-",suffix=".gz",dir=target.parent)
    os.close(fd)
    archive=Path(tmp)
    try:
        with fetch(BASE+"/"+ARCHIVE) as source,archive.open("wb") as out:
            while chunk:=source.read(2**20):
                h.update(chunk)
                out.write(chunk)
        if h.hexdigest()!=expected:
            raise ValueError("Immutable source ZIP mismatch; refusing to boot")
        staged=target.with_name(target.name+".tmp")
        if staged.exists():
            raise FileExistsError(str(staged))
        try:
            with gzip.open(archive,"rb") as data,staged.open("wb") as out:
                while chunk:=data.read(2**20):
                    out.write(chunk)
            with sqlite3.connect(f"file:{staged.as_posix()}?mode=ro",uri=True) as db:
                counts=(db.execute(
                    "SELECT COUNT(*) FROM world_dataset_entries WHERE dataset_id=?",(DATASET,)).fetchone()[0],
                    db.execute(
                    "SELECT COUNT(*) FROM world_dataset_rosters WHERE dataset_id=?",(DATASET,)).fetchone()[0],
                    db.execute(
                    "SELECT COUNT(DISTINCT competition_id) FROM world_dataset_entries WHERE dataset_id=?",
                    (DATASET,)).fetchone()[0])
                health=db.execute("PRAGMA quick_check").fetchone()[0]
                audit=db.execute(
                    "SELECT source_clubs,source_players,original_source_competitions "
                    "FROM fc27_warehouse_import_audit WHERE dataset_id=?",(DATASET,)).fetchone()
            if counts!=(659,17593,53) or audit!=(659,17593,53) or health!="ok":
                raise ValueError(f"Unapproved or corrupt FC27 DB: {counts}, {audit}, {health}")
            staged.rename(target)
        finally:
            if staged.exists():staged.unlink()
    finally:
        archive.unlink(missing_ok=True)
    print("FC27 MANUAL PREVIEW VERIFIED: 659 clubs / 17,593 players / 53 competitions",flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--destination",default=DESTINATION)
    arguments=parser.parse_args()
    run(arguments.destination)

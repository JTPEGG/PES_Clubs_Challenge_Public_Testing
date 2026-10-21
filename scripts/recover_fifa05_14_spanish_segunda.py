"""Recover season-correct FIFA05–14 Spanish Segunda members from CC0 archives.

Source: Jack-Tilley/es-espana at a pinned Git SHA. Team lists are obtained
from dated match results. The only accepted automatic matches are unique
same-edition original FIFA club names. No game team ID, squads, country
from nationality, or promotion movement is fabricated.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
import urllib.request
from collections import defaultdict, Counter
from pathlib import Path

from world_historical_competition_registry import canonical

PIN = "d91ca620ebd484ceba25dbf7d8673d55a268aba8"
BASE = f"https://raw.githubusercontent.com/Jack-Tilley/es-espana/{PIN}"
EDITION_RANGE = tuple(range(2005, 2015))
VERSION = "fifa05-14-spanish-segunda-archival-memberships-v1"
SCORE = re.compile(r"^\d{1,2}-\d{1,2}$")
SUFFIX = re.compile(r"\s+\(\d+\)\s*$")


def team_name(raw):
    """Remove trailing archive result group counters, but not real club suffixes."""
    name = SUFFIX.sub("", str(raw or "").strip()).strip()
    if not name or len(name) > 130:
        raise ValueError("Unusable archived team label")
    return name


def match_teams(content):
    reader = csv.DictReader(io.StringIO(content))
    if not {"Team 1", "Team 2", "FT"}.issubset(reader.fieldnames or []):
        raise ValueError("Expected original archived Segunda match headers")
    fixtures = 0
    names = set()
    for row in reader:
        if not SCORE.fullmatch(str(row["FT"] or "").strip()):
            continue
        a = team_name(row["Team 1"])
        b = team_name(row["Team 2"])
        if a == b or canonical(a) == canonical(b):
            raise ValueError("Impossible historical Spanish Segunda fixture")
        names.update((a, b))
        fixtures += 1
    if len(names) != 22 or fixtures < 200:
        raise ValueError(f"Incomplete original Spanish Segunda source: clubs={len(names)} matches={fixtures}")
    if len({canonical(x) for x in names}) != len(names):
        raise ValueError("Spanish source club normalization collision")
    return sorted(names), fixtures


def collect(source_sqlite, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"file:{Path(source_sqlite).resolve()}?mode=ro", uri=True) as db:
        games = db.execute("""SELECT edition,club_key,name
                              FROM clubs WHERE edition BETWEEN 2005 AND 2014""").fetchall()
    game_by_name = defaultdict(list)
    for year, club_key, club in games:
        game_by_name[(int(year), canonical(club))].append((club_key, club))

    seasons = []
    source_clubs = []
    matches = []
    pending = []
    for edition in EDITION_RANGE:
        season = f"{edition-1}-{edition%100:02d}"
        url = f"{BASE}/{season}/2-liga2.csv"
        req = urllib.request.Request(url, headers={
            "User-Agent": "PES-Clubs-Challenge-Public-CC0-Season-Audit"})
        with urllib.request.urlopen(req, timeout=35) as f:
            raw = f.read()
        checksum = hashlib.sha256(raw).hexdigest()
        names, count = match_teams(raw.decode("utf-8-sig"))
        seasons.append((edition,season,"es.2","Spain","Segunda División",
                        2,len(names),count,url,checksum,"pinned_CC0_dated_fixture_memberships"))
        for club in names:
            source_clubs.append((edition,season,"es.2",club,url,checksum,
                                 "dated_fixture_team_not_independently_game_verified"))
            hits = game_by_name.get((edition, canonical(club)), [])
            if len(hits) == 1:
                key, game_name = hits[0]
                matches.append((edition,key,game_name,"es.2",club,url,checksum,
                                "unique_same_edition_canonical_name_provisional"))
            else:
                pending.append((edition,club,"duplicate_original_club_name" if hits
                                else "missing_original_game_name",len(hits)))
    if len(seasons) != len(EDITION_RANGE):
        raise ValueError("Historical source did not supply all ten original game seasons")
    # Guard game names which in the same season would occupy multiple sources.
    seen = defaultdict(set)
    for x in matches:
        seen[(x[0],x[1])].add(canonical(x[4]))
    if any(len(v) > 1 for v in seen.values()):
        raise ValueError("Multiple Spanish source clubs assigned to one original game club")
    def dump(filename,heads,rows):
        with (output / filename).open("w", newline="", encoding="utf-8-sig") as f:
            w=csv.writer(f);w.writerow(heads);w.writerows(rows)
    dump("FIFA05_14_PINNED_SPANISH_SEGUNDA_SEASONS.csv",
         ("Edition","Season","League_Code","Country","Competition","Tier",
          "Source_Clubs","Fixture_Count","Source_URL","SHA256","Evidence_Status"),seasons)
    dump("FIFA05_14_PINNED_SPANISH_SEGUNDA_CLUBS.csv",
         ("Edition","Season","League_Code","Club","Source_URL","SHA256","Evidence_Status"),source_clubs)
    dump("FIFA05_14_SPANISH_SEGUNDA_GAME_NAME_MATCHES.csv",
         ("Edition","FIFA_Club_Key","FIFA_Club","League_Code","Fixture_Club",
          "Source_URL","SHA256","Evidence_Method"),matches)
    dump("FIFA05_14_SPANISH_SEGUNDA_NAME_REVIEW.csv",
         ("Edition","Fixture_Club","Reason","Same_Edition_Game_Name_Count"),pending)
    report={"version":VERSION,"source_commit":PIN,"edition_years":list(EDITION_RANGE),
         "independent_domestic_league_seasons":len(seasons),
         "actual_dated_fixture_club_memberships":len(source_clubs),
         "unique_provisional_game_club_name_matches":len(matches),
         "unmatched_or_ambiguous_source_clubs":len(pending),
         "exact_original_game_id_certificates_issued":0,
         "careers_ready":False,"game_squads_modified":False}
    (output / "FIFA05_14_SPANISH_SEGUNDA_SOURCE_AUDIT.json").write_text(
         json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--output", required=True)
    args=ap.parse_args()
    print(json.dumps(collect(args.source,args.output), indent=2))

"""Offline importer for EA FC 27 player ratings into PES 2.0.

Never overwrite PES attribute profiles with EA ratings. This tool uses
conservative club+display-name matching, saves accepted external ratings in
their own table and produces a detailed review list for ambiguous/unmatched
rows. Source data should be obtained under its applicable usage rights.

Usage: python import_fc27_ratings.py path/to/players.csv path/to/world.db
"""
import csv
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict

SOURCE = "EA FC 27"
SNAPSHOT = "2026-09-12"
CLUB_ALIASES = {
    "manchester utd": "Manchester United",
    "man utd": "Manchester United",
    "man city": "Manchester City",
    "nottingham forest": "Nottingham Forest",
    "nott'm forest": "Nottingham Forest",
    "newcastle utd": "Newcastle United",
    "spurs": "Tottenham Hotspur",
    "tottenham": "Tottenham Hotspur",
    "brighton": "Brighton & Hove Albion",
    "bournemouth": "AFC Bournemouth",
    "leeds": "Leeds United",
    "wolves": "Wolverhampton Wanderers",
    "west brom": "West Bromwich Albion",
    "qpr": "Queens Park Rangers",
}


def normalized(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def club_canonical(name, known):
    exact = {normalized(c): c for c in known}
    aliased = CLUB_ALIASES.get((name or "").strip().casefold(), name)
    return exact.get(normalized(aliased))


def ratings_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS world_external_ratings(
        player_id INTEGER NOT NULL REFERENCES world_players(player_id),
        source_name TEXT NOT NULL, edition TEXT NOT NULL, snapshot_date TEXT NOT NULL,
        external_player_id TEXT NOT NULL,
        overall INTEGER NOT NULL CHECK(overall BETWEEN 1 AND 99),
        pace INTEGER, shooting INTEGER, passing INTEGER, dribbling INTEGER,
        defending INTEGER, physicality INTEGER,
        PRIMARY KEY (player_id, source_name, edition),
        UNIQUE(source_name,edition,external_player_id)
    )""")


def player_keys(row):
    common = (row.get("common_name") or "").strip()
    first = (row.get("first_name") or "").strip()
    last = (row.get("last_name") or "").strip()
    names = [common, last, f"{first} {last}", f"{first[:1]}.{last}"]
    return set(filter(None, (normalized(n) for n in names if n)))


def load_fc27(csv_path, db_path, dry_run=True):
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        ratings_schema(conn)
        clubs = dict(conn.execute("SELECT club_id,name FROM world_clubs").fetchall())
        club_names = set(clubs.values())
        player_rows = conn.execute("""SELECT p.player_id,p.full_name,c.name
            FROM world_players p JOIN world_rosters r ON p.player_id=r.player_id
            JOIN world_clubs c ON c.club_id=r.club_id
            WHERE r.season_id='2026/27'""").fetchall()
        lookup = defaultdict(list)
        for player_id, short_name, club in player_rows:
            lookup[(club, normalized(short_name))].append(player_id)
        accepted, review = [], []
        seen_ids = set()
        with open(csv_path, encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("gender") != "Men's Football":
                    continue
                club = club_canonical(row.get("club"), club_names)
                if not club:
                    continue
                candidates = set()
                for key in player_keys(row):
                    candidates.update(lookup.get((club, key), []))
                if len(candidates) != 1:
                    review.append((row.get("player_id"), row.get("club"), row.get("common_name") or row.get("last_name"), "ambiguous" if candidates else "not matched"))
                    continue
                player_id = next(iter(candidates))
                if player_id in seen_ids:
                    review.append((row.get("player_id"), club, row.get("common_name") or row.get("last_name"), "multiple EA players match same FPL player"))
                    continue
                try:
                    overall = int(row["overall_rating"])
                    if not 1 <= overall <= 99:
                        raise ValueError("out of bounds")
                except (ValueError, TypeError, KeyError):
                    review.append((row.get("player_id"), club, row.get("common_name") or row.get("last_name"), "invalid rating"))
                    continue
                facets = []
                for col in ("pace","shooting","passing","dribbling","defending","physicality"):
                    val = (row.get(col) or "").strip()
                    facets.append(int(val) if val.isdigit() and 1 <= int(val) <= 99 else None)
                accepted.append((player_id,SOURCE,"fc27",row.get("snapshot_date") or SNAPSHOT,
                                 str(row["player_id"]),overall,*facets))
                seen_ids.add(player_id)
        if not dry_run:
            conn.executemany("""INSERT INTO world_external_ratings(
                 player_id,source_name,edition,snapshot_date,external_player_id,
                 overall,pace,shooting,passing,dribbling,defending,physicality)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                 ON CONFLICT(player_id,source_name,edition) DO UPDATE SET
                 snapshot_date=excluded.snapshot_date,
                 overall=excluded.overall, pace=excluded.pace,
                 shooting=excluded.shooting, passing=excluded.passing,
                 dribbling=excluded.dribbling, defending=excluded.defending,
                 physicality=excluded.physicality""", accepted)
        return {"matched":len(accepted),"needs_review":len(review),"review":review}


if __name__ == "__main__":
    if len(sys.argv) not in (3,4):
        raise SystemExit("Usage: python import_fc27_ratings.py players.csv world.db [--apply]")
    result = load_fc27(sys.argv[1],sys.argv[2],dry_run=(len(sys.argv)<4 or sys.argv[3]!="--apply"))
    print("Matched:",result["matched"],"Needs review:",result["needs_review"])
    for item in result["review"][:30]:
        print("Review:",item)

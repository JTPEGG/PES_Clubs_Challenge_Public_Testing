"""Pin CC0 2004/05–2009/10 non-English league memberships independently.

Uses historical match team names, never later-season clubs or made-up squads.
A unique FIFA game-name match is provisional evidence, not career activation.
Source: footballcsv/cache.soccerverse (CC0), immutable commit.
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
from collections import defaultdict
from pathlib import Path

from scripts.collect_openfootball_historical_competitions import namekey

PIN = "d4a8cc571b37d54371e2623947d39f87325e047c"
BASE = f"https://raw.githubusercontent.com/footballcsv/cache.soccerverse/{PIN}"
# The already pinned England source covers tiers 1-4; do not double-register it.
LEAGUES = {
    "ar": ("Argentina", "Primera División"),
    "at": ("Austria", "Bundesliga"),
    "de": ("Germany", "Bundesliga"),
    "es": ("Spain", "La Liga"),
    "fr": ("France", "Ligue 1"),
    "it": ("Italy", "Serie A"),
    "nl": ("Netherlands", "Eredivisie"),
    "pt": ("Portugal", "Primeira Liga"),
}
SCORE = re.compile(r"^\d{1,2}-\d{1,2}$")


def source_teams_csv(data: str):
    reader = csv.DictReader(io.StringIO(data))
    if not {"Team 1", "Team 2", "FT"}.issubset(reader.fieldnames or []):
        raise ValueError("Unexpected historical fixtures CSV columns")
    teams = set()
    games = 0
    for row in reader:
        if not SCORE.fullmatch((row["FT"] or "").strip()):
            continue
        a, b = (row["Team 1"] or "").strip(), (row["Team 2"] or "").strip()
        if not a or not b or a == b:
            raise ValueError("Corrupt fixture pairing")
        teams.update((a, b))
        games += 1
    if not 10 <= len(teams) <= 30 or games < 100:
        raise ValueError("Historical fixture source is incomplete")
    return sorted(teams), games


def get_source(url):
    request = urllib.request.Request(url, headers={
        "User-Agent": "PES-Clubs-Challenge-CC0-legacy-competition-audit"})
    with urllib.request.urlopen(request, timeout=30) as stream:
        raw = stream.read()
    return raw.decode("utf-8-sig"), hashlib.sha256(raw).hexdigest()


def build(source_sqlite, output):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"file:{Path(source_sqlite).resolve()}?mode=ro", uri=True) as db:
        names = defaultdict(lambda: defaultdict(list))
        for edition, key, club in db.execute(
                "SELECT edition, club_key, name FROM clubs WHERE edition BETWEEN 2005 AND 2010"):
            names[edition][namekey(club)].append((key, club))
    leagues = []
    source_clubs = []
    provisional = []
    review = []
    for edition in range(2005, 2011):
        season = f"{edition - 1}-{edition % 100:02d}"
        for tag, (country, league) in LEAGUES.items():
            url = f"{BASE}/{season}/{tag}.csv"
            fixture_csv, checksum = get_source(url)
            teams, games = source_teams_csv(fixture_csv)
            matches = 0
            for team in teams:
                source_clubs.append((edition, season, f"{tag}.1", country,
                    league, 1, team, url, checksum,
                    "pinned_fixture_membership_not_game_identity"))
                hits = names[edition].get(namekey(team), [])
                if len(hits) == 1:
                    key, name = hits[0]
                    provisional.append((edition, season, f"{tag}.1", country,
                        league, 1, team, name, key, url, checksum,
                        "exact_unique_name_provisional"))
                    matches += 1
                else:
                    review.append((edition, f"{tag}.1", country, league, team,
                        "ambiguous_game_club_name" if hits else
                        "no_same_name_game_club", url))
            leagues.append((edition, season, f"{tag}.1", country, league, 1,
                url, "source_team_list_available", len(teams), games,
                matches, checksum))
    club_hits = defaultdict(set)
    for row in provisional:
        club_hits[(row[0], row[8])].add(row[2])
    valid = [row for row in provisional if len(club_hits[(row[0], row[8])]) == 1]
    ambiguous = [row for row in provisional if len(club_hits[(row[0], row[8])]) > 1]

    def dump(file, headers, rows):
        with (out / file).open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)

    dump("LEGACY_MULTICOUNTRY_LEAGUE_SEASONS.csv",
        ("Edition", "Starting_Season", "League_Code", "Country", "Competition",
         "Tier", "Source_URL", "Source_Status", "Source_Teams",
         "Fixture_Rows", "Matched_FIFA_Clubs", "SHA256"), leagues)
    dump("LEGACY_MULTICOUNTRY_SOURCE_CLUBS.csv",
        ("Edition", "Starting_Season", "League_Code", "Country", "Competition",
         "Tier", "Fixture_Club", "Source_URL", "Source_SHA256",
         "Evidence_Status"), source_clubs)
    dump("LEGACY_MULTICOUNTRY_EXACT_CLUB_MATCHES.csv",
        ("Edition", "Starting_Season", "League_Code", "Country", "Competition",
         "Tier", "Fixture_Club", "FIFA_Club", "FIFA_Club_Key",
         "Source_URL", "Source_SHA256", "Verification_Status"), valid)
    dump("LEGACY_MULTICOUNTRY_NAME_REVIEW.csv",
        ("Edition", "League_Code", "Country", "Competition", "Fixture_Club",
         "Reason", "Source_URL"), review)
    dump("LEGACY_MULTICOUNTRY_CONFLICTS.csv",
        ("Edition", "Starting_Season", "League_Code", "Country", "Competition",
         "Tier", "Fixture_Club", "FIFA_Club", "FIFA_Club_Key",
         "Source_URL", "Source_SHA256", "Verification_Status"), ambiguous)
    audit = {
        "pin": PIN, "license": "CC0",
        "years": 6, "countries": len(LEAGUES),
        "independently_sourced_league_seasons": len(leagues),
        "source_club_memberships": len(source_clubs),
        "exact_name_matches_provisional": len(valid),
        "unmatched_or_ambiguous_names": len(review),
        "cross_league_identity_conflicts": len(ambiguous),
        "complete_career_editions": [],
        "original_fifa_squads_modified": False,
    }
    (out / "LEGACY_MULTICOUNTRY_AUDIT.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8")
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--output", required=True)
    options = parser.parse_args()
    print(json.dumps(build(options.catalog, options.output), indent=2))

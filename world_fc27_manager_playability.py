"""The approved *manager-selectable* FC27 clubs, NOT the complete AI market.

Approved on 21 Oct 2026: 16 divisions across eight European countries
(314 source clubs) plus closed-league playable MLS (30 source clubs).
All 659 remain registered and active in the transfer market.

The starter-world importer intentionally stores each source competition under
a stable "WH27-" hash. Reconstruct only those 17 approved source codes to join
against existing world_dataset_entries without changing frozen identities.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

FC27_DATASET = "fc27-warehouse-659-mens-2026-27"
SCOPE_PATH = Path(__file__).parent / "data/warehouse/fc27_2026_27_eight_country_playable_scope.json"
MLS_PATH = Path(__file__).parent / "data/warehouse/fc27_2026_mls_playable_competition.json"

EXPECTED_COUNTRIES = frozenset({
    "England", "Germany", "Spain", "France", "Italy",
    "Scotland", "Portugal", "Netherlands",
})
EXPECTED_COUNTS = (344, 17, 9)


def approved_source_competition_codes():
    cfg = json.loads(SCOPE_PATH.read_text(encoding="utf-8"))
    mls = json.loads(MLS_PATH.read_text(encoding="utf-8"))
    groups = cfg["open_and_intended_playable_countries"]
    codes = [code for group in groups for code in group["competition_codes"]]
    if (
        cfg["version"] != "fc27-eight-country-open-playable-career-scope-v1"
        or cfg["all_other_fc27_active_domestic_competitions"]
            != "closed_to_sporting_promotion_relegation_and_not_manager_selectable"
        or {g["country"] for g in groups} != EXPECTED_COUNTRIES
        or len(groups) != 8 or len(codes) != 16 or len(set(codes)) != 16
        or mls["version"] != "fc27-mls-playable-closed-pyramid-v2"
        or mls["game_competition_code"] != "2027:us.mls"
        or mls["manager_selectable"] is not True
        or mls["sporting_promotion_or_relegation"] is not False
    ):
        raise ValueError("Approved FC27 344-manager-club scope is not intact")
    return tuple(codes) + (mls["game_competition_code"],)


def approved_world_competition_ids():
    return tuple(
        "WH27-" + hashlib.sha256(code.encode("utf-8")).hexdigest()[:15]
        for code in approved_source_competition_codes()
    )


def approved_manager_club_ids(conn, *, dataset_id):
    """Fail closed on drift, instead of silently exposing all warehouse clubs."""
    if dataset_id != FC27_DATASET:
        raise ValueError("Playable FC27 check requires the approved source dataset")
    ids = approved_world_competition_ids()
    placeholders = ",".join("?" for _ in ids)
    source = conn.execute(
        "SELECT COUNT(*) FROM world_dataset_entries WHERE dataset_id=?",
        (dataset_id,),
    ).fetchone()[0]
    if source != 659:
        raise ValueError("FC27 world roster drift; refusing manager selection")
    rows = conn.execute(
        f"""SELECT e.club_id,e.competition_id,co.country
            FROM world_dataset_entries e
            JOIN world_competitions co ON co.competition_id=e.competition_id
            WHERE e.dataset_id=? AND e.competition_id IN ({placeholders})""",
        (dataset_id, *ids),
    ).fetchall()
    club_ids = frozenset(int(r[0]) for r in rows)
    competitions = {r[1] for r in rows}
    countries = {r[2] for r in rows}
    if (
        (len(club_ids), len(competitions), len(countries)) != EXPECTED_COUNTS
        or competitions != set(ids)
        or len(rows) != 344
    ):
        raise ValueError(
            "FC27 approved manager scope mismatch: "
            f"{len(rows)} clubs, {len(competitions)} leagues, "
            f"{len(countries)} countries; expected 344/17/9"
        )
    return club_ids

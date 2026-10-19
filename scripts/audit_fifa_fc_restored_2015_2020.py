"""Stratified validation of unapproved FIFA15–20 SoFIFA conversion inputs.

Samples source-labelled GK, DEF, MID, ATT across each full annual source, not
just the first N (which are frequently sorted by overall ability).
No calibration, data promotion, permanent career edits or native game files.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from zipfile import ZipFile

from scripts.export_fifa_pes_v2 import source_members, read_ed
from world_fifa_pes_converter import positions
from world_fifa_pes_converter_v2 import (
    EditionContext, POSITION_FAMILY, convert_v2, prepared_row,
    validate_exportable, TARGETS,
)

YEARS = set(range(2015, 2021))
FAMILIES = ("GK", "DEF", "MID", "ATT")


def select_spread(rows, limit):
    """Stable evenly spaced selections including both ends of the source."""
    if len(rows) < limit:
        raise ValueError("Position family has too few source records")
    if limit == 1:
        return [rows[len(rows) // 2]]
    return [rows[(i * (len(rows) - 1)) // (limit - 1)]
            for i in range(limit)]


def run(source, output, per_family=20):
    if per_family < 1:
        raise ValueError("per_family must be positive")
    report = {
        "status": "STRATIFIED_SAMPLE_PASSED_ONLY_IF_ALL_YEARS_COMPLETE",
        "source_years": sorted(YEARS),
        "FIFA20_only_calibration_policy": True,
        "calibration_applied": False,
        "FC25_excluded": True,
        "all_game_roster_membership_verified": False,
        "player_identity_between_source_providers_verified": False,
        "source_edition_results": {},
    }
    with ZipFile(source) as z:
        members = source_members(z)
        if set(members) != YEARS:
            raise ValueError("Restored candidate archive must contain only 2015–20")
        for year in sorted(YEARS):
            rows = read_ed(z, members, year)
            indexed = defaultdict(list)
            for row in rows:
                source_positions = positions(prepared_row(row))
                if not source_positions:
                    continue
                family = POSITION_FAMILY.get(source_positions[0])
                if family in FAMILIES:
                    indexed[family].append(row)
            context = EditionContext(year, rows)  # no cross-provider neighbours
            per_role = {}
            for family in FAMILIES:
                choices = select_spread(indexed[family], per_family)
                stats = Counter()
                for row in choices:
                    result = convert_v2(row, year, context=context)
                    validate_exportable(result)
                    if POSITION_FAMILY[result["primary_position"]] != family:
                        raise ValueError(f"{year}: {family} changed family")
                    for attr in TARGETS:
                        ability = result["abilities"][attr]
                        stats[ability["method"]] += 1
                        stats["validated_numeric_ratings"] += 1
                    stats["players_validated"] += 1
                per_role[family] = {
                    "source_players": len(indexed[family]),
                    "sampled_players": len(choices),
                    "estimated_ratings_checked": stats["validated_numeric_ratings"],
                    "methods": {k: v for k, v in stats.items()
                                if k not in ("players_validated",
                                             "validated_numeric_ratings")},
                }
            report["source_edition_results"][str(year)] = {
                "source_player_rows": len(rows),
                "role_stratified_results": per_role,
                "per_family": per_family,
                "source_provider": "SoFIFA-derived pinned FIFA15–FIFA20 candidate",
                "cross_provider_adjacent_imputation_enabled": False,
            }
            print(f"{year}: {len(rows):,} source rows; "
                  + ", ".join(f"{f}:{per_role[f]['sampled_players']}"
                              for f in FAMILIES), flush=True)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--per-family", type=int, default=20)
    args = parser.parse_args()
    run(args.source, args.output, args.per_family)

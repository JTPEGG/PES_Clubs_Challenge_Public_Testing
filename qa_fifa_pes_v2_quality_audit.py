"""Independent source-coverage and FIFA20-only calibration-quality audit.

Never uses FIFA19 as a PES20 calibration reference. Does not replace source
files, approve calibration offsets, produce game binaries or modify careers.
The legacy FIFAIndex archive is not assumed to contain every game player.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import unicodedata
from zipfile import ZipFile

from qa_pes_conversion_pilot import (
    SRC, PES_SRC, fetch_csv, pairs_for_calibration
)
from qa_fifa20_pes20_calibration_v2 import position_accuracy_report

# Pinned copy of the complete 18,278-row public FIFA 20 SoFIFA snapshot.
# Different provider/snapshot than FIFAIndex; identity overlap is NOT assumed.
ALTERNATE_FIFA20 = (
    "https://raw.githubusercontent.com/kushal-gopal/EA-Sports-Fifa/"
    "66fc78145ff32ea2dea839459e247833856e0f47/players_20.csv"
)
FIFAINDEX_PROVIDER = "lbenz730/fifa_model"
KNOWN_SCRAPE_PAGE_COUNT = 700
OBSERVED_FIFAINDEX_PAGE_CEILING = 10500


def source_coverage_status(edition, rows, provider):
    """Separate source player coverage from numeric PES attribute completeness."""
    if edition == 2025:
        return "EXCLUDED_FC25_NOT_CONVERTED"
    if (2005 <= edition <= 2020
            and provider == FIFAINDEX_PROVIDER
            and rows == OBSERVED_FIFAINDEX_PAGE_CEILING):
        return "KNOWN_SCRAPER_PAGE_LIMIT_REACHED_COVERAGE_UNVERIFIED"
    return "SOURCE_COVERAGE_NOT_INDEPENDENTLY_VERIFIED"


def audit_source_manifest(manifest):
    records = manifest["downloads"]
    rows = {}
    for rec in records:
        year = int(rec["edition"])
        if year < 2005:
            continue
        count = rec.get("player_rows", 0)
        rows[str(year)] = {
            "provider": rec.get("catalog_source", ""),
            "source_rows": count,
            "download_status": rec["status"],
            "coverage_status": source_coverage_status(
                year, count, rec.get("catalog_source", "")
            ),
            "source_url": rec.get("source_url", ""),
            "warning": (
                "The published upstream scraper requests 700 listing pages "
                "(typically 15 players/page); reaching exactly 10,500 rows "
                "does not establish full in-game player coverage."
                if year != 2025 and source_coverage_status(
                    year, count, rec.get("catalog_source", "")
                ).startswith("KNOWN_") else ""
            ),
        }
    limited = [int(y) for y, item in rows.items()
               if item["coverage_status"].startswith("KNOWN_")]
    return {
        "year_records": rows,
        "confirmed_complete_editions": [],
        "source_coverage_conclusion": (
            "All available rows can be processed, but none of these "
            "source lists has been verified to include every player "
            "in its respective game's original roster."
        ),
        "known_fifaindex_700_page_scrape_years": limited,
        "known_fifaindex_page_limit": KNOWN_SCRAPE_PAGE_COUNT,
        "potential_missing_editions_2000_to_2004": list(range(2000, 2005)),
        "FC25": "Downloaded source deliberately excluded; do not patch or impute.",
    }


def normalized_name(value):
    unaccented = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(x for x in unaccented.casefold()
                   if x.isascii() and x.isalnum())


def key_for(row, name, *, is_pes=False):
    return (
        normalized_name(name),
        normalized_name(row.get("nationality")),
        str(row.get("age") or "").strip(),
        normalized_name(row.get("team_name" if is_pes else "club")),
    )


def alias_candidate_pairs(fifa, pes):
    """Unambiguous four-field candidates using either SoFIFA name variant.

    Every alias must map one-to-one on BOTH sides. Such pairs are provisional;
    a name+age+country+club match is never a verified cross-game player ID.
    """
    pes_groups = defaultdict(list)
    for pi, row in enumerate(pes):
        k = key_for(row, row.get("name"), is_pes=True)
        if all(k):
            pes_groups[k].append(pi)
    fifa_groups = defaultdict(set)
    for fi, row in enumerate(fifa):
        for name in (row.get("short_name"), row.get("long_name")):
            k = key_for(row, name)
            if all(k):
                fifa_groups[k].add(fi)
    links = defaultdict(set)
    reverse = defaultdict(set)
    for key, indices in fifa_groups.items():
        possible_pes = pes_groups.get(key, [])
        if len(indices) != 1 or len(possible_pes) != 1:
            continue
        fi = next(iter(indices))
        pi = possible_pes[0]
        links[fi].add(pi)
        reverse[pi].add(fi)
    return [(fifa[fi], pes[next(iter(indices))])
            for fi, indices in sorted(links.items())
            if len(indices) == 1
            and len(reverse[next(iter(indices))]) == 1]


def accuracy_summary(pairs):
    heldout = position_accuracy_report(pairs, holdout_only=True)
    allpairs = position_accuracy_report(pairs, holdout_only=False)
    def families(report):
        return {
            family: {
                "matched_players": item["candidate_players"],
                "relevant_attribute_mae": item[
                    "position_relevant_attributes"]["mae"],
                "rating_observations": item[
                    "position_relevant_attributes"]["observations"],
                "reliability": ("insufficient_sample" if
                                item["candidate_players"] < 10 else
                                "provisional_unverified_identity"),
            }
            for family, item in report["by_primary_position_family"].items()
        }
    return {
        "provisional_matches": len(pairs),
        "holdout_players": heldout["candidate_players_evaluated"],
        "holdout_position_accuracy": families(heldout),
        "full_candidate_set_position_accuracy": families(allpairs),
        "not_independent": (
            "FIFA and PES identities use unverified name, age, nationality "
            "and club; different source snapshots may disagree. The earlier "
            "offset-selection process re-used its holdout, so proposed "
            "offset improvements are not independent validation."
        ),
    }


def run(source_zip, output):
    with ZipFile(source_zip) as archive:
        manifest_names = [p for p in archive.namelist()
                          if p.endswith("/MANIFEST.json")]
        if len(manifest_names) != 1:
            raise ValueError("Expected precisely one original source manifest")
        manifest = json.loads(archive.read(manifest_names[0]))
    coverage = audit_source_manifest(manifest)
    original = fetch_csv(SRC[2020])
    alternate = fetch_csv(ALTERNATE_FIFA20)
    pes = fetch_csv(PES_SRC)
    if len(original) != coverage["year_records"]["2020"]["source_rows"]:
        raise ValueError("FIFA20 source archive count differs from calibration file")
    if len(alternate) < 15000:
        raise ValueError("Supplementary FIFA20 source unexpectedly small")
    primary_pairs = pairs_for_calibration(original, pes)
    alternate_pairs = alias_candidate_pairs(alternate, pes)
    report = {
        "status": "SOURCE_COVERAGE_REVIEWED_CALIBRATION_NOT_APPROVED",
        "calibration_fifa_edition": 2020,
        "reference_pes_edition": 2020,
        "FIFA19_used_as_calibration": False,
        "source_coverage": coverage,
        "fifa20_comparison": {
            "current_fifaindex_player_rows": len(original),
            "alternate_sofifa_player_rows": len(alternate),
            "row_count_difference_not_proven_missing_players":
                len(alternate) - len(original),
            "native_pes2020_reference_rows": len(pes),
            "source_snapshots_or_providers_may_differ": True,
            "original_fifa20_reference": SRC[2020],
            "alternate_fifa20_reference": ALTERNATE_FIFA20,
            "original_index_exact_candidate_matching":
                accuracy_summary(primary_pairs),
            "alternate_sofifa_two_name_candidate_matching":
                accuracy_summary(alternate_pairs),
            "calibration_offsets_applied": False,
            "cross_provider_identity_verified": False,
        },
        "next_steps": [
            "Verify FIFAIndex historical missing clubs/players before claiming full game rosters.",
            "Validate and potentially restore full 2015-20 source data in a separate versioned stage.",
            "Improve FIFA20/PES2020 entity matching and independent position-aware holdout.",
            "Do not approve goalkeeper calibration from a one-keeper holdout.",
        ],
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                      encoding="utf-8")
    print("SOURCE COVERAGE QUALITY AUDIT", json.dumps({
        "fifaindex_years_at_known_page_limit":
            coverage["known_fifaindex_700_page_scrape_years"],
        "fifa20_fifaindex_rows": len(original),
        "fifa20_sofifa_rows": len(alternate),
        "pes2020_reference_rows": len(pes),
        "old_reference_candidate_pairs": len(primary_pairs),
        "alternate_reference_candidate_pairs": len(alternate_pairs),
        "old_holdout": report["fifa20_comparison"][
            "original_index_exact_candidate_matching"]["holdout_position_accuracy"],
        "alternate_holdout": report["fifa20_comparison"][
            "alternate_sofifa_two_name_candidate_matching"]["holdout_position_accuracy"],
        "calibration_applied": False,
    }, indent=2), flush=True)
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
    p.add_argument("--output",
                   default="qa-v2-quality/fifa20-and-source-coverage.json")
    args = p.parse_args()
    run(args.source, args.output)

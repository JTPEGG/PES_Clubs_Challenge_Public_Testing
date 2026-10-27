"""Create a separate, versioned six-edition SoFIFA restoration candidate.

Never overwrites or edits the existing 23 original source CSVs. Never infers
missing rows, adds FC25, approves calibration, or modifies live careers.
All year-specific input CSV bytes are kept verbatim in this supplementary ZIP.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from time import sleep
from urllib.request import Request, urlopen
from zipfile import ZIP_DEFLATED, ZipFile

from scripts.source_coverage_v2 import source_coverage_status

REPOSITORY = "kushal-gopal/EA-Sports-Fifa"
REVISION = "66fc78145ff32ea2dea839459e247833856e0f47"
YEARS = tuple(range(2015, 2021))
ROOT = "fifa_restored_2015_2020"
MAX_BYTES = 35_000_000
REQUIRED = frozenset(("sofifa_id", "short_name", "long_name", "dob",
                      "nationality", "overall", "player_positions"))
TARGET_INPUTS = frozenset(("skill_ball_control", "skill_dribbling",
                          "attacking_short_passing", "movement_sprint_speed",
                          "goalkeeping_reflexes"))
SOURCE_STATUS = "CANDIDATE_RESTORATION_NOT_FULL_ROSTER_CERTIFICATION"


def original_baselines(path):
    """Use actual archived source counts, never a guessed 10,500 constant."""
    with ZipFile(path) as z:
        names = [p for p in z.namelist() if p.endswith("/MANIFEST.json")]
        if len(names) != 1:
            raise ValueError("Expected precisely one original source manifest")
        manifest = json.loads(z.read(names[0]))
    rows = {}
    for rec in manifest["downloads"]:
        if rec["edition"] in YEARS:
            if rec["status"] != "DOWNLOADED":
                raise ValueError("Missing original edition: " + str(rec["edition"]))
            rows[rec["edition"]] = rec
    if set(rows) != set(YEARS):
        raise ValueError("Missing baseline source year(s)")
    return rows


def source_url(year):
    if year not in YEARS:
        raise ValueError("Not an eligible restoration edition: " + str(year))
    return ("https://raw.githubusercontent.com/" + REPOSITORY + "/" +
            REVISION + "/players_" + str(year)[-2:] + ".csv")


def download(year):
    url = source_url(year)
    error = None
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "PES-V2-Source-Restoration/1.0",
                                            "Accept": "text/csv"})
            with urlopen(request, timeout=70) as r:
                data = r.read(MAX_BYTES + 1)
            if not 100_000 < len(data) <= MAX_BYTES:
                raise ValueError("Source byte count outside sensible limits")
            if b"<html" in data[:400].lower() or data.startswith(b"version https://git-lfs"):
                raise ValueError("Source is HTML or a Git LFS pointer")
            return data
        except Exception as exc:
            error = exc
            if attempt < 2:
                sleep(1 + attempt)
    raise RuntimeError("Cannot fetch year " + str(year)) from error


def inspect_csv(data, year, baseline):
    """Fail closed on truncation, year mismatch or malformed key information."""
    content = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content, newline=""))
    columns = reader.fieldnames or []
    missing = REQUIRED.difference(columns)
    if missing:
        raise ValueError(f"{year}: missing identity/position columns: {sorted(missing)}")
    measured = TARGET_INPUTS.intersection(columns)
    if len(measured) < 4:
        raise ValueError(f"{year}: insufficient source attribute columns: {sorted(measured)}")
    identifiers = set()
    duplicate_ids = 0
    valid_ovr = valid_role = valid_dob = keeper = 0
    count = 0
    for row in reader:
        if not any(str(v or "").strip() for v in row.values()):
            continue
        if None in row:
            raise ValueError(f"{year}: malformed CSV with excess columns")
        count += 1
        sid = (row.get("sofifa_id") or "").strip()
        if not sid.isdigit():
            raise ValueError(f"{year}: missing/non-numeric sofifa_id at row {count}")
        if sid in identifiers:
            duplicate_ids += 1
        identifiers.add(sid)
        try:
            n = int(float(row.get("overall") or "nan"))
            valid_ovr += int(1 <= n <= 99)
        except (ValueError, TypeError):
            pass
        role = (row.get("player_positions") or "").strip().upper()
        if role:
            valid_role += 1
            keeper += int(role.split(",")[0].strip() == "GK")
        dob = (row.get("dob") or "").strip()
        valid_dob += int(len(dob) >= 10 and dob[:4].isdigit()
                         and dob[4] == "-" and dob[7] == "-")
    if count <= baseline:
        raise ValueError(f"{year}: candidate {count} does not improve on {baseline}")
    if duplicate_ids:
        raise ValueError(f"{year}: {duplicate_ids} duplicated source player IDs")
    if min(valid_ovr, valid_role, valid_dob) < count * .95:
        raise ValueError(f"{year}: incomplete overall/position/DOB schema")
    if keeper < 100:
        raise ValueError(f"{year}: unexpectedly few source goalkeepers ({keeper})")
    return {"year": year, "player_rows": count,
            "unique_source_ids": len(identifiers),
            "duplicate_source_ids": duplicate_ids,
            "columns": len(columns),
            "measured_attribute_fields": sorted(measured),
            "valid_overall_rows": valid_ovr,
            "position_label_rows": valid_role,
            "iso_dob_rows": valid_dob, "source_goalkeepers": keeper}


def build(output, original_source):
    baselines = original_baselines(original_source)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "status": SOURCE_STATUS,
        "edition_scope": list(YEARS),
        "original_23_file_archive_preserved": True,
        "FC25_excluded": True,
        "fifa20_only_calibration_preserved": True,
        "calibration_performed": False,
        "converter_source_automatically_replaced": False,
        "native_PES_option_file_created": False,
        "source_repository": REPOSITORY,
        "pinned_commit": REVISION,
        "snapshot_comparability_verified": False,
        "all_original_game_roster_players_verified": False,
        "editions": {},
    }
    with ZipFile(output, "w", ZIP_DEFLATED, compresslevel=6) as z:
        for year in YEARS:
            baseline = baselines[year]
            data = download(year)
            result = inspect_csv(data, year, baseline["player_rows"])
            filename = f"{ROOT}/data/{year}_sofifa.csv"
            result.update({
                "status": SOURCE_STATUS,
                "previous_fifaindex_players": baseline["player_rows"],
                "additional_source_rows_not_verified_new_identities":
                    result["player_rows"] - baseline["player_rows"],
                "coverage_status": source_coverage_status(
                    year, result["player_rows"], REPOSITORY
                ),
                "source_url": source_url(year),
                "sha256": hashlib.sha256(data).hexdigest(),
                "source_bytes": len(data),
                "raw_source_member": filename,
                "source_snapshot": "unknown_not_assumed_launch",
                "original_source_url": baseline.get("source_url"),
                "original_source_sha256": baseline.get("sha256"),
            })
            z.writestr(filename, data)
            report["editions"][str(year)] = result
            print(f"{year}: {result['player_rows']:,} raw SoFIFA rows "
                  f"(vs {baseline['player_rows']:,} FIFAIndex); "
                  f"{result['source_goalkeepers']:,} GK; "
                  f"{result['duplicate_source_ids']} duplicated IDs", flush=True)
        report["source_rows_six_years"] = sum(
            y["player_rows"] for y in report["editions"].values())
        report["original_rows_six_years"] = sum(
            y["previous_fifaindex_players"] for y in report["editions"].values())
        z.writestr(f"{ROOT}/MANIFEST.json",
                   json.dumps(report, indent=2, ensure_ascii=False))
        z.writestr(f"{ROOT}/README.txt",
                   "FIFA15-FIFA20 UNAPPROVED SOURCE RESTORATION CANDIDATES\n"
                   "Pinned source bytes are preserved separately from original FIFAIndex.\n"
                   "More rows do NOT prove these are all game players or that source\n"
                   "snapshots agree. Do not merge year-specific rosters automatically.\n"
                   "FC25 is excluded. FIFA20 remains the only PES20 calibration edition.\n"
                   "No production/career/game import files are changed.\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--original-source", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    result = build(a.output, a.original_source)
    print("RESTORATION REVIEW", json.dumps({
        "years": list(YEARS),
        "old_rows": result["original_rows_six_years"],
        "restoration_rows": result["source_rows_six_years"],
        "status": result["status"],
    }), flush=True)

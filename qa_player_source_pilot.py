"""Automated 100-player source-feasibility pilot. No live warehouse writes.

Baseline: EXISTING FC27 reference seed in this repository (rights not cleared).
External enrichment: ONLY openfootball/players CC0 text snapshot.
Output is an inventory of field availability, not another player database.
"""
import argparse
import csv
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from urllib.request import Request, urlopen

from world_fc27_english import FC27_PLAYERS, SNAPSHOT_DATE
from world_squad_planner import EXPLICIT_ALTERNATIVE_POSITIONS

OPENFOOTBALL_SHA = "125d20f7cc06cac7e758b40df535a7695632680a"
OPENFOOTBALL_ENGLAND = (
    "https://raw.githubusercontent.com/openfootball/players/"
    + OPENFOOTBALL_SHA + "/europe/england/eng.players.txt"
)
OPENFOOTBALL_LICENSE = (
    "https://github.com/openfootball/players/blob/"
    + OPENFOOTBALL_SHA + "/LICENSE.md"
)
DATASET = "england-2026-27-fc27"
CLUB_SAMPLE = (
    ("Manchester City", 17),
    ("Arsenal", 17),
    ("Crystal Palace", 17),
    ("Leeds United", 17),
    ("Bolton Wanderers", 16),
    ("Walsall", 16),
)
SNAPSHOT_DATE_ISO = date.fromisoformat(SNAPSHOT_DATE)
FIELDS = (
    "club","player","existing_ea_id","primary_position","age_at_snapshot",
    "overall_present","six_categories_present",
    "alternative_roles_operator_confirmed","alternative_suitability_present",
    "detailed_attributes_present","potential_present","contract_end_present",
    "weekly_wage_present","transfer_status_present",
    "personality_profile_present",
    "cc0_england_identity_match","cc0_height_present",
    "cc0_source","identity_match_method",
)
DOMAIN_FIELDS = (
    "primary_position","age_at_snapshot","overall_present",
    "six_categories_present","alternative_roles_operator_confirmed",
    "alternative_suitability_present","detailed_attributes_present",
    "potential_present","contract_end_present","weekly_wage_present",
    "transfer_status_present","personality_profile_present",
    "cc0_england_identity_match","cc0_height_present",
)


def normalized_name(value):
    a = unicodedata.normalize("NFKD", value)
    a = "".join(c for c in a if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", a.casefold())


def reference_birthdate(text):
    return datetime.strptime(text,"%d-%m-%Y").date()


def reference_age(text):
    birth = reference_birthdate(text)
    return (SNAPSHOT_DATE_ISO.year-birth.year -
            ((SNAPSHOT_DATE_ISO.month,SNAPSHOT_DATE_ISO.day) <
             (birth.month,birth.day)))


def sample_players(records=FC27_PLAYERS):
    """Top rated 17/16 roster players from six different club levels.

    The sample is intentionally first-team-biased, not a random or season-
    representative player population; source identity must be preserved.
    """
    seen = set()
    chosen = []
    for club, n in CLUB_SAMPLE:
        club_rows = [row for row in records if row[6] == club]
        club_rows.sort(key=lambda r:(-r[8],str(r[0])))
        if len(club_rows)<n:
            raise ValueError(f"Club {club} has {len(club_rows)} of {n} players")
        for player in club_rows[:n]:
            if player[0] in seen:
                raise ValueError("Duplicate external ID in sample")
            seen.add(player[0])
            chosen.append(player)
    if len(chosen)!=100:
        raise AssertionError("Expected exactly 100 player reference rows")
    return chosen


def parse_openfootball_players(content):
    """Return exact (normalised name, DOB) -> details from CC0 England file."""
    matches = {}
    for line in content.splitlines():
        matched = re.match(
            r"^([^,]+),\s*[GDMF],\s*([^,]*),\s*b\.\s*"
            r"(\d{1,2} [A-Za-z]{3} \d{4})(?:\s*@.*)?$",line.strip())
        if not matched:
            continue
        name, height, birth = matched.groups()
        try:
            dob = datetime.strptime(birth,"%d %b %Y").date().isoformat()
        except ValueError:
            continue
        key=(normalized_name(name),dob)
        measurement=re.match(r"^(\d+(?:\.\d+)?)\s*m$",height.strip())
        height_cm = round(float(measurement.group(1))*100) if measurement else None
        matches.setdefault(key,[]).append({
            "name":name,"dob":dob,"height_cm":height_cm
        })
    return matches


def load_cc0_england():
    req=Request(OPENFOOTBALL_ENGLAND,headers={"User-Agent":"PES-Challenge-warehouse-QA/1.0"})
    with urlopen(req,timeout=20) as resp:
        body=resp.read()
    return body.decode("utf-8-sig"), hashlib.sha256(body).hexdigest()


def create_report(cc0_text=None, *, source_error=None, source_sha256=None):
    sample=sample_players()
    external=parse_openfootball_players(cc0_text) if cc0_text is not None else {}
    explicit=EXPLICIT_ALTERNATIVE_POSITIONS.get(DATASET,{})
    rows=[]; countries={}
    for player in sample:
        ea_id,name,_,_,_,position,club,_,overall,pace,shooting,passing,dribbling,defending,physical,dob,nation=player
        lookup=(normalized_name(name),reference_birthdate(dob).isoformat())
        candidates=external.get(lookup,[])
        # Ambiguous names / DOB remain unmatched: never guess identities.
        cc0=candidates[0] if len(candidates)==1 else None
        alternatives=explicit.get(str(ea_id),{})
        countries[nation]=countries.get(nation,0)+1
        rows.append({
            "club":club,"player":name,"existing_ea_id":ea_id,
            "primary_position":position,
            "age_at_snapshot":reference_age(dob),
            "overall_present":int(isinstance(overall,int) and 1<=overall<=99),
            "six_categories_present":int(all(
                isinstance(v,int) and 1<=v<=99
                for v in (pace,shooting,passing,dribbling,defending,physical))),
            "alternative_roles_operator_confirmed":len(alternatives),
            "alternative_suitability_present":0,
            "detailed_attributes_present":0,
            "potential_present":0,
            "contract_end_present":0,
            "weekly_wage_present":0,
            "transfer_status_present":0,
            "personality_profile_present":0,
            "cc0_england_identity_match":int(cc0 is not None),
            "cc0_height_present":int(cc0 is not None and cc0["height_cm"] is not None),
            "cc0_source":OPENFOOTBALL_ENGLAND if cc0 else "",
            "identity_match_method":"exact normalised name + DOB" if cc0 else "none",
        })
    summary={
        "status":"source_feasibility_only_not_imported",
        "dataset":DATASET,"source_date":SNAPSHOT_DATE,
        "sample_size":len(rows),
        "sample_selection":"Top-rated 17/17/17/17/16/16 players, deterministic, first-team-biased",
        "clubs":{club:count for club,count in CLUB_SAMPLE},
        "sample_nationalities":countries,
        "source_availability":{
            "existing_fc27_seed":{
                "status":"already_in_development_repo",
                "distributable_rights":"unverified",
                "provider":"existing FC27 reference seed, not an official API",
                "contains":"primary role, name, DOB, OVR, 6 category ratings",
            },
            "openfootball_england":{
                "status":("fetched" if cc0_text is not None else "unavailable"),
                "license":"CC0-1.0 published repository",
                "license_url":OPENFOOTBALL_LICENSE,
                "snapshot_commit":OPENFOOTBALL_SHA,
                "sha256":source_sha256,
                "error":source_error,
                "scope":"English-born/nationality file only; older snapshot; not current club/contract evidence",
            },
        },
        "matched_cc0_english_ids":sum(r["cc0_england_identity_match"] for r in rows),
        "external_match_method":"Exact unicode-normalised player name AND exact birthdate; rejects ambiguity",
        "completeness":{
            col:{"available":sum(
                bool(r[col]) if col!="primary_position" and col!="age_at_snapshot"
                else r[col] is not None
                for r in rows),"total":len(rows)}
            for col in DOMAIN_FIELDS
        },
        "data_rules":[
            "Zero coverage means missing in selected tested sources, not that no source exists.",
            "Player age is calculated at the FC27 seed source date, not today's date.",
            "The local FC27 reference is not certified for public redistribution.",
            "CC0 England match is identity/height evidence only, not 2026 club membership.",
            "Potential, contract situation, player personality and position suitability remain unknown.",
            "Confirmed alternative positions are operator assertions, not independent scouting source evidence.",
            "No values are committed to a real warehouse and no live career changes occur.",
        ],
    }
    return summary,rows


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output-dir",default="qa-player-source-pilot")
    parser.add_argument("--offline",action="store_true",
        help="Prove baseline field coverage without contacting any provider")
    args=parser.parse_args()
    contents=None; error=None; sha=None
    if not args.offline:
        try:
            contents,sha=load_cc0_england()
        except Exception as exc:
            error=f"{type(exc).__name__}: {str(exc)[:160]}"
    report,rows=create_report(contents,source_error=error,source_sha256=sha)
    target=Path(args.output_dir);target.mkdir(parents=True,exist_ok=True)
    (target/"pilot-summary.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    with (target/"pilot-field-coverage.csv").open("w",encoding="utf-8-sig",newline="") as out:
        writer=csv.DictWriter(out,fieldnames=FIELDS)
        writer.writeheader();writer.writerows(rows)
    print(json.dumps({
        "sample_size":report["sample_size"],
        "cc0_status":report["source_availability"]["openfootball_england"]["status"],
        "cc0_exact_matches":report["matched_cc0_english_ids"],
        "field_counts":{k:v["available"] for k,v in report["completeness"].items()},
        "source_error":error
    },indent=2))
    if not args.offline and error:
        raise SystemExit("CC0 source temporarily unavailable: see JSON; do not treat as zero coverage")


if __name__=="__main__":
    main()

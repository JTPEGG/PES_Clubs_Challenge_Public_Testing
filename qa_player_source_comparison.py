"""Compare sources against the SAME 100 players without warehouse writes.

CC0 OpenFootball: read pinned international archive in memory.
FC26: process publicly hosted CSV in memory; emit ONLY source coverage,
matching diagnostics, and boolean per-player field presence (no ratings).
PES/Football Life and Football Manager: report extractor dependencies until
a working source player database is actually available to the workflow.

This is a source-capability pilot, not clearance to republish game records.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime
import io
import json
from pathlib import Path
import re
import sqlite3
from urllib.request import Request, urlopen
import zipfile

from qa_player_source_pilot import (
    sample_players, normalized_name, reference_birthdate,
    OPENFOOTBALL_SHA, FC26_CSV_URL, DATASET,
    parse_openfootball_players,
)

CC0_ARCHIVE = ("https://codeload.github.com/openfootball/players/zip/"
               + OPENFOOTBALL_SHA)
FIELDS = (
    "club", "player", "ea_id",
    "openfootball_country_match", "openfootball_country_sources",
    "openfootball_height",
    "fc26_verified_identity", "fc26_name_differs",
    "fc26_potential", "fc26_detailed_attributes",
    "fc26_other_positions", "fc26_contract_end_year",
    "fc26_wage_eur", "fc26_value_eur",
    "fc26_work_rate", "fc26_preferred_foot",
    "fc26_position_familiarity_ovr", "fm_personality_available",
    "pes_native_abilities_available",
)


def full_openfootball_index(zipped):
    """Scan national files; use name AND DOB, retaining source countries."""
    result = defaultdict(list)
    country_files = 0
    player_lines = 0
    with zipfile.ZipFile(io.BytesIO(zipped)) as archive:
        for filename in archive.namelist():
            if not filename.endswith(".players.txt") or filename.endswith("/"):
                continue
            country_files += 1
            src = archive.read(filename).decode("utf-8-sig",errors="replace")
            matches = parse_openfootball_players(src)
            for key, entries in matches.items():
                for e in entries:
                    result[key].append({
                        "height_cm": e.get("height_cm"),
                        "source_file": filename.split("/",1)[-1],
                    })
                    player_lines += 1
    return result, {"country_files":country_files,
                    "parsed_player_records":player_lines,
                    "unique_name_birth_pairs":len(result)}


def fc26_players_from_csv(text):
    """Read FC26 player records keyed by EA ID; keep latest dated update.

    Never match FC players by fuzzy name; matching must use original EA ID
    AND the exact DOB. Any absent/conflicting DOB remains a nonmatch.
    """
    reader=csv.DictReader(io.StringIO(text))
    cols=set(reader.fieldnames or [])
    required={"player_id","dob","player_positions"}
    if not required.issubset(cols):
        raise ValueError("Missing required FC26 source fields: "
                         +",".join(sorted(required-cols)))
    best={}
    duplicate_ids=Counter()
    rows_read=0
    for row in reader:
        rows_read+=1
        ident=(row.get("player_id") or "").strip()
        if not ident.isdigit():continue
        if ident in best:duplicate_ids[ident]+=1
        prior=best.get(ident)
        if prior is None or (
            (row.get("fifa_update_date") or "",row.get("fifa_update") or "") >
            (prior.get("fifa_update_date") or "",prior.get("fifa_update") or "")
        ):
            best[ident]=row
    return best, {
        "records_read":rows_read,
        "distinct_ids":len(best),
        "ids_with_multiple_records":len(duplicate_ids),
        "columns":len(cols),
        "selected_attributes": sorted(
            col for col in cols
            if col.startswith(("attacking_","skill_","movement_",
                               "power_","mentality_","defending_",
                               "goalkeeping_"))
        ),
    }


def nonempty(v):
    return v is not None and str(v).strip().lower() not in ("","nan","none","null")


def parse_date(v):
    if not nonempty(v):return None
    raw=str(v).strip()[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def compare_players(players, external_index, fc26, details=None):
    observed=[]
    per_club=defaultdict(Counter)
    problems=Counter()
    attrs=(details or {}).get("selected_attributes",[])
    for p in players:
        ea_id,name,_first,_last,_common,position,club,_league,_overall,*tail=p
        birth=reference_birthdate(p[15])
        key=(normalized_name(name),birth.isoformat())
        cc0=external_index.get(key,[])
        countries={e["source_file"] for e in cc0}
        heights={e["height_cm"] for e in cc0 if e["height_cm"] is not None}
        if len(heights)>1:
            problems["multiple_external_heights"]+=1
        external_match=bool(cc0)
        record=fc26.get(str(ea_id))
        id_present=bool(record)
        exact_date=(parse_date(record.get("dob"))==birth) if record else False
        if id_present and not exact_date:
            problems["fc26_id_dob_mismatch_or_missing"]+=1
        selected=record if exact_date else None
        name_differs=bool(selected and
            normalized_name(selected.get("long_name") or
                            selected.get("short_name") or "")!=normalized_name(name))
        if name_differs:
            problems["fc26_name_differs_despite_id_dob_match"]+=1
        role_string=(selected.get("player_positions") or "") if selected else ""
        roles=[x.strip().upper() for x in role_string.split(",") if x.strip()]
        alternatives=[pos for pos in roles if pos!=position.upper()]
        row={
            "club":club,"player":name,"ea_id":str(ea_id),
            "openfootball_country_match":int(external_match),
            "openfootball_country_sources":len(countries),
            "openfootball_height":int(bool(heights)),
            "fc26_verified_identity":int(selected is not None),
            "fc26_name_differs":int(name_differs),
            "fc26_potential":int(bool(selected and nonempty(selected.get("potential")))),
            "fc26_detailed_attributes":int(bool(selected and attrs and
                sum(nonempty(selected.get(k)) for k in attrs)>=15)),
            "fc26_other_positions":int(bool(alternatives)),
            "fc26_contract_end_year":int(bool(selected and
                nonempty(selected.get("club_contract_valid_until_year")))),
            "fc26_wage_eur":int(bool(selected and
                nonempty(selected.get("wage_eur")))),
            "fc26_value_eur":int(bool(selected and
                nonempty(selected.get("value_eur")))),
            "fc26_work_rate":int(bool(selected and
                nonempty(selected.get("work_rate")))),
            "fc26_preferred_foot":int(bool(selected and
                nonempty(selected.get("preferred_foot")))),
            # PES-position ratings and FM-personality need distinct sources.
            "fc26_position_familiarity_ovr":0,
            "fm_personality_available":0,
            "pes_native_abilities_available":0,
        }
        per_club[club]["sample"]+=1
        per_club[club]["openfootball_matches"]+=int(external_match)
        per_club[club]["fc26_verified"]+=int(selected is not None)
        per_club[club]["fc26_alternative_positions"]+=int(bool(alternatives))
        observed.append(row)
    summary={
        "dataset":DATASET,"sample_size":len(observed),
        "matching_policy":"same EA player ID plus exact birth date for FC26; "
                          "exact normalized name + birth date for OpenFootball",
        "per_club":dict(per_club),
        "coverage":{key:sum(row[key] for row in observed)
                    for key in FIELDS[3:] if key!="openfootball_country_sources"},
        "match_diagnostics":dict(problems),
        "source_edition_difference":
            "FC26 records are a different snapshot from 2026/27 FC27. "
            "A match does not prove a contract, wage or current club in 2026/27.",
        "source_status":{
            "openfootball":"global_country_files_scanned",
            "fc26":"public_csv_evaluated_ephemerally",
            "pes_2020":"no game database file supplied to processor",
            "pes21_football_life":"available parser, no underlying game file",
            "football_manager_26":"available save parser, no underlying save file",
        },
        "extractor_references":{
            "pes21":"https://github.com/gvoze32/pes21-player-rating",
            "fm26":"https://github.com/rhiever/fmsave",
        },
        "privacy_and_scope":"Outputs include data-availability flags, not copied FC26 player attributes. "
                            "No game files, wages, profiles or careers are committed.",
    }
    return summary, observed


def get_bytes(url,limit=100_000_000):
    req=Request(url,headers={"User-Agent":"PES-Challenge-source-pilot/1.0"})
    with urlopen(req,timeout=60) as handle:
        body=handle.read(limit+1)
    if len(body)>limit:raise ValueError("Source exceeds size limit")
    return body



def stage_fc26_in_memory(sample,fc26,attribute_columns):
    """Validate a source snapshot against the real warehouse DDL in memory.

    Never import previous-edition player facts as a current FC27 career.
    Only ephemeral source snapshots are constructed, with NO source records
    written to GitHub or to an existing career.
    """
    db=sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
        CREATE TABLE world_datasets(dataset_id TEXT PRIMARY KEY);
        CREATE TABLE world_players(player_id INTEGER PRIMARY KEY);
        CREATE TABLE world_clubs(club_id INTEGER PRIMARY KEY);
        CREATE TABLE world_competitions(competition_id TEXT PRIMARY KEY);
        INSERT INTO world_datasets VALUES('ea-fc26-pilot-only');
    """)
    db.executescript((Path(__file__).resolve().parent/
                      "warehouse"/"schema_v1.sql").read_text(encoding="utf-8"))
    db.execute("""INSERT INTO wh_sources(source_id,name,rights_basis,source_version)
                  VALUES('fc26-eval','FC26 dated QA source','unresolved','fc26-csv-pinned')""")
    counters=Counter()
    for item in sample:
        pid=int(item[0]);birth=reference_birthdate(item[15])
        record=fc26.get(str(pid))
        if not record or parse_date(record.get("dob"))!=birth:
            continue
        db.execute("INSERT INTO world_players(player_id) VALUES(?)",(pid,))
        counters["matched_player_profiles"]+=1
        positions=list(dict.fromkeys(
            x.strip().upper() for x in
            (record.get("player_positions") or "").split(",")
            if x.strip()
        ))
        for i,pos in enumerate(positions):
            if not re.fullmatch(r"[A-Z]{2,5}",pos):
                counters["unrecognized_position_codes"]+=1
                continue
            # Only a true reported position is inserted. Per-role suitability
            # stays NULL because this source does not give a PES-style OVR.
            db.execute("""INSERT INTO wh_player_positions(
                dataset_id,player_id,position_code,position_kind,
                suitability_ovr,origin,source_id)
                VALUES('ea-fc26-pilot-only',?,?,?,?,?,?)""",
                (pid,pos,"primary" if i==0 else "alternative",
                 None,"source","fc26-eval"))
            counters["position_rows"]+=1
            if i>0:counters["alternative_position_rows"]+=1
        if positions:
            db.execute("""INSERT INTO wh_player_position_reviews(
                dataset_id,player_id,review_status,source_id)
                VALUES('ea-fc26-pilot-only',?,'partial','fc26-eval')""",
                (pid,))
        for key in attribute_columns:
            # skill_moves is a separate 1–5 scale and must not be passed
            # off as an ordinary 1–99 ability attribute.
            if key=="skill_moves":continue
            raw=record.get(key)
            if not nonempty(raw):continue
            try:
                value=float(raw)
            except (ValueError,TypeError):
                continue
            if not value.is_integer() or not 1<=value<=99:continue
            db.execute("""INSERT INTO wh_player_attributes(
                dataset_id,player_id,attribute_key,value,origin,source_id)
                VALUES('ea-fc26-pilot-only',?,?,?,?,?)""",
                (pid,key,int(value),"source","fc26-eval"))
            counters["individual_attribute_rows"]+=1
    counters["position_suitability_values"]=db.execute(
        "SELECT COUNT(*) FROM wh_player_positions WHERE suitability_ovr IS NOT NULL"
    ).fetchone()[0]
    counters["fictional_personality_rows"]=db.execute(
        "SELECT COUNT(*) FROM wh_player_traits"
    ).fetchone()[0]
    counters["reference_contract_rows"]=0 # Existing world_dataset_player_contracts owns this data.
    counters["foreign_key_problems"]=len(db.execute("PRAGMA foreign_key_check").fetchall())
    counters["unique_player_ids"]=db.execute(
        "SELECT COUNT(DISTINCT player_id) FROM wh_player_positions"
    ).fetchone()[0]
    db.close()
    return dict(counters)



def run(output):
    sample=sample_players()
    zip_data=get_bytes(CC0_ARCHIVE)
    global_index,cc0_info=full_openfootball_index(zip_data)
    csv_data=get_bytes(FC26_CSV_URL).decode("utf-8-sig",errors="replace")
    fc26,fc_info=fc26_players_from_csv(csv_data)
    summary,rows=compare_players(sample,global_index,fc26,fc_info)
    summary["in_memory_warehouse_stage"]=stage_fc26_in_memory(
        sample,fc26,fc_info["selected_attributes"])
    summary["cc0_archive_info"]=cc0_info
    summary["fc26_csv_info"]={
        "records_read":fc_info["records_read"],
        "distinct_ids":fc_info["distinct_ids"],
        "ids_with_multiple_records":fc_info["ids_with_multiple_records"],
        "columns":fc_info["columns"],
        "detected_individual_attributes":len(fc_info["selected_attributes"]),
        "attribute_keys":fc_info["selected_attributes"],
    }
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    (output/"global-source-summary.json").write_text(
        json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    with (output/"player-source-coverage.csv").open(
        "w",encoding="utf-8-sig",newline=""
    ) as handle:
        writer=csv.DictWriter(handle,fieldnames=FIELDS)
        writer.writeheader();writer.writerows(rows)
    print(json.dumps({
        "sample":summary["sample_size"],
        "country_files":cc0_info["country_files"],
        "fc26_fields":fc_info["columns"],
        "warehouse_stage":summary["in_memory_warehouse_stage"],
        "individual_attribute_fields":len(fc_info["selected_attributes"]),
        "coverage":summary["coverage"],
        "per_club":summary["per_club"],
        "diagnostics":summary["match_diagnostics"],
    },indent=2),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="qa-player-source-global")
    args=parser.parse_args()
    run(args.output)

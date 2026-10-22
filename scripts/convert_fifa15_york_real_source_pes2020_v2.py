"""Convert recovered genuine FIFA15 York source players using approved PES2020 V2.

Both real input (actual original game player attributes) and *estimated*
numeric output remain individually traceable. This is a game balance
estimate, not Konami-native player data and not a playable option file.
FIFA20 is the only permitted calibration reference, no missing player added.
"""
from __future__ import annotations
import argparse,csv,json
from collections import Counter
from pathlib import Path

from world_fifa_pes_converter_v2 import (
    convert_v2,EditionContext,validate_exportable,TARGETS,MODEL_VERSION)
from scripts.export_fifa_pes_v2 import COLUMNS,to_csv_row

VERSION="fifa15-york-original-players-to-pes2020-v2-estimate-v1"
SOURCE_ID="pinned_jsulz_sofifa_FIFA15_mens_legacy_update2"

def convert(source,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    with open(source,encoding="utf-8-sig",newline="") as f:
        players=list(csv.DictReader(f))
    if len(players)!=20:
        raise ValueError("Only the 20 real sourced 2015 York City players are supported")
    if len({str(r["player_id"]) for r in players})!=len(players):
        raise ValueError("Game player ID collision in pinned FIFA15 York source")
    for row in players:
        if str(row.get("fifa_version"))!="15" or str(row.get("club_team_id"))!="1948" or row.get("club_name")!="York City":
            raise ValueError("Not the real pinned same-game FIFA15 York team player source")
    context=EditionContext(2015,players)
    estim=[];counts=Counter()
    for row in players:
        profile=convert_v2(row,2015,context=context)
        validate_exportable(profile)
        if str(profile["source_player_id"])!=str(row["player_id"]):
            raise ValueError("Converted player identity drift from original game source")
        profile["source_provider"]=SOURCE_ID
        profile["namespaced_source_player_key"]=f"2015:{SOURCE_ID}:{row['player_id']}"
        profile["source_club"]="York City"
        profile["source_nationality"]=str(row.get("nationality_name") or row.get("nationality") or "")
        profile["source_height_cm"]=str(row.get("height_cm") or "")
        profile["source_weight_kg"]=str(row.get("weight_kg") or "")
        profile["source_preferred_foot"]=str(row.get("preferred_foot") or "")
        estim.append(to_csv_row(profile))
        for target,ability in profile["abilities"].items():
            counts[ability["method"]]+=1
            if type(ability["value"]) is not int or not 1<=ability["value"]<=99:
                raise ValueError("Source-imputed PES ability missing or out of range")
    path=out/"FIFA15_YORK_REAL_SOURCE_PES2020_25_PLUS_4_ESTIMATED.csv"
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=COLUMNS);w.writeheader();w.writerows(estim)
    data={
      "version":VERSION,"source_game_edition":2015,"source_game_club":"York City",
      "original_game_team_id":1948,"original_game_players":len(players),
      "distinct_original_game_player_ids":len(estim),
      "PES2020_v2_calibration_reference_fifa_edition":2020,
      "PES_game_estimate_model":MODEL_VERSION,
      "numeric_core_attributes_per_original_player":len(TARGETS),
      "numeric_auxiliary_attributes_per_original_player":4,
      "total_core_estimates":len(TARGETS)*len(estim),
      "total_auxiliary_estimates":4*len(estim),
      "source_estimation_methods":dict(counts),
      "game_squad_player_id_coverage_percent":100,
      "does_not_fill_york_source_missing_eight_players":True,
      "different_published_game_roster_snapshot_shows_28":True,
      "native_game_option_file_created":False,
      "career_ready":False,"original_22_edition_source_catalogue_changed":False}
    (out/"FIFA15_YORK_SOURCE_PES2020_V2_CONVERSION_AUDIT.json").write_text(
      json.dumps(data,indent=2),encoding="utf-8")
    return data

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    print(json.dumps(convert(a.source,a.output),indent=2))

"""Read actual FIFA05 goalkeeper rows and verify reconstructed PES2020 attributes.

This is a source-backed QA audit, not a synthetic-only unit test.
No downloaded original CSV or existing career is modified.
"""
from collections import Counter
import json
from pathlib import Path
from statistics import median

from qa_pes_conversion_pilot import SRC, fetch_csv
from world_fifa_pes_converter_v2 import (
    EditionContext, convert_v2, prepared_row, validate_exportable, TARGETS
)
from world_fifa_pes_converter import positions

ROOT=Path("qa-v2-calibration")


def run(output=ROOT/"fifa05-real-goalkeeper-audit.json", sample_cap=100):
    rows=fetch_csv(SRC[2005])
    if len(rows)<100:
        raise ValueError("Real FIFA 05 CSV missing or unexpectedly small")
    # Selection uses the source position, before PES ratings are constructed.
    keepers=[r for r in rows if positions(prepared_row(r))[:1]==["GK"]]
    if len(keepers)<10:
        raise ValueError("Insufficient source-labelled FIFA05 goalkeepers")
    test_rows=keepers[:sample_cap]
    context=EditionContext(2005,rows)
    methods=Counter()
    source_key_counts=Counter()
    player_methods=Counter()
    values={"gk_awareness":[],"gk_catching":[],"gk_clearing":[],
            "gk_reflexes":[],"gk_reach":[]}
    evidence_examples=[]
    for row in test_rows:
        profile=convert_v2(row,2005,context=context)
        validate_exportable(profile)
        if profile["primary_position"]!="GK":
            raise AssertionError("Source goalkeeper lost GK position")
        if set(profile["abilities"])!=set(TARGETS):
            raise AssertionError("Incomplete PES goalkeeper attributes")
        for a,rating in profile["abilities"].items():
            methods[rating["method"]]+=1
        for a in values:
            rating=profile["abilities"][a]
            values[a].append(rating["value"])
            player_methods[(a,rating["method"])]+=1
            for name in rating["source_columns"]:
                source_key_counts[(a,name)]+=1
        if len(evidence_examples)<8:
            evidence_examples.append({
                "source_player_id":profile["source_player_id"],
                "player_name":profile["player_name"],
                "source_overall":profile["source_overall"],
                "gk_reflexes":profile["abilities"]["gk_reflexes"],
                "gk_reach":profile["abilities"]["gk_reach"],
            })
    if median(values["gk_reach"])<=40 or median(values["gk_reflexes"])<=40:
        raise AssertionError("FIFA05 goalkeeper estimates collapsed to PES floor")
    report={
        "data_source":SRC[2005],
        "game_source":"FIFA 05 (2004/05 season)",
        "player_rows_in_original_source":len(rows),
        "source_goalkeepers":len(keepers),
        "goalkeepers_audited":len(test_rows),
        "core_attributes_per_goalkeeper":25,
        "numeric_completeness_pct":100.0,
        "reconstruction_methods_for_all_25":dict(methods),
        "gk_specific":{
            a:{"count":len(values[a]),"median_estimated_rating":median(values[a]),
               "methods":{method:n for (attr,method),n in player_methods.items()
                          if attr==a},
               "input_columns":{field:n for (attr,field),n in source_key_counts.items()
                                if attr==a}}
            for a in values
        },
        "first_eight_audit_traces":evidence_examples,
        "warning":"Estimated PES attributes, not verified Konami goalkeeper ratings.",
    }
    path=Path(output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print("Real FIFA05 goalkeeper audit:",json.dumps({
        "source_goalkeepers":len(keepers),
        "tested":len(test_rows),
        "core_completeness_pct":100,
        "gk_reach_methods":report["gk_specific"]["gk_reach"]["methods"],
        "gk_reflex_methods":report["gk_specific"]["gk_reflexes"]["methods"]
    },indent=2),flush=True)
    return report


if __name__=="__main__":
    run()

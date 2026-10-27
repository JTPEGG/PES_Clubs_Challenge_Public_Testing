"""Propose a FIFA20-only calibration against the native PES2020 sample.

No FIFA19 data enters the process. Matches require identical normalized name,
age, nationality AND club; these are PROVISIONAL pairs until Konami/EA IDs
are independently matched. Train/holdout MAEs are reported per ability;
goalkeeper parameters excluded until real goalkeeper validation is sufficient.
"""
import json
import hashlib
from collections import Counter,defaultdict
from pathlib import Path
from statistics import mean
from qa_pes_conversion_pilot import (
    fetch_csv, SRC, PES_SRC, pairs_for_calibration, calibration_proposal,
    observed_pes, kf
)
from world_fifa_pes_converter_v2 import (
    CALIBRATION_FIFA_EDITION, TARGET_GAME, convert_v2, POSITION_FAMILY, TARGETS
)

assert CALIBRATION_FIFA_EDITION==2020
OUTFIELD=frozenset((
 "offensive_awareness","ball_control","dribbling","tight_possession",
 "low_pass","lofted_pass","finishing","heading","place_kicking",
 "curl","speed","acceleration","kicking_power","jump",
 "physical_contact","balance","stamina","defensive_awareness",
 "ball_winning","aggression",
))


def choose_calibration(proposals,matched_pairs):
    selected={}
    for attr,stat in proposals.items():
        if attr not in OUTFIELD:continue
        shift=stat.get("suggested_shift")
        before=stat.get("holdout_mae_before")
        after=stat.get("holdout_mae_after")
        if (len(str(attr))>0 and isinstance(shift,int)
            and stat.get("train_pairs",0)>=65
            and stat.get("holdout_pairs",0)>=15
            and before is not None and after is not None
            and before-after>=0.5 and abs(shift)<=12):
            selected[attr]=shift
    return {
        "reference_game":TARGET_GAME,
        "training_fifa_edition":2020,
        "training_pes_edition":2020,
        "status":"unapproved_experimental_candidate",
        "candidate_pairs":matched_pairs,
        "identity_quality":"provisional_exact_name_age_nation_club_not_ID_verified",
        "goalkeeper_calibration":"disabled_until_keeper_only_holdout",
        "offsets":selected,
        "per_attribute_heldout":proposals,
        "note":"Candidate offsets are NOT automatically approved or exported. "
               "No FIFA19 record was used for training. Selected shifts improve "
               "held-out 2020 candidate comparison by at least 0.5 points; "
               "use only as experimental cross-edition calibration.",
    }



RELEVANT_BY_FAMILY={
    "GK":("gk_awareness","gk_catching","gk_clearing","gk_reflexes","gk_reach"),
    "DEF":("defensive_awareness","ball_winning","speed","stamina",
           "physical_contact","jump"),
    "MID":("low_pass","lofted_pass","ball_control","tight_possession",
           "dribbling","stamina","defensive_awareness"),
    "ATT":("offensive_awareness","finishing","dribbling","ball_control",
           "speed","acceleration"),
}


def position_accuracy_report(pairs,*,holdout_only=True):
    """Position-stratified *candidate* accuracy using completed V2 profiles.

    Holdout membership uses the SAME 20% split as the proposed calibration.
    It is exploratory because identity links are not verified and offsets are
    selected on this holdout; it is NOT independent external validation.
    """
    bins=defaultdict(lambda:{
        "players":0,"all_errors":[],"relevant_errors":[],
        "by_attr":defaultdict(list),"methods":Counter(),
    })
    source_pairs=0
    for fifa,pes in pairs:
        key=":".join(kf(fifa))
        holdout=int(hashlib.sha256(key.encode()).hexdigest()[:8],16)%5==0
        if holdout_only and not holdout:
            continue
        source_pairs+=1
        profile=convert_v2(fifa,2020)
        family=POSITION_FAMILY.get(profile["primary_position"],"OTHER")
        record=bins[family]
        record["players"]+=1
        for attr in TARGETS:
            actual=observed_pes(pes,attr)
            if actual is None:
                continue
            estimate=profile["abilities"][attr]
            error=estimate["value"]-actual
            record["all_errors"].append(error)
            if attr in RELEVANT_BY_FAMILY.get(family,()):
                record["relevant_errors"].append(error)
            record["by_attr"][attr].append(error)
            record["methods"][estimate["method"]]+=1
    def metrics(errors):
        if not errors:return {"observations":0,"mae":None,"mean_bias":None,
                              "within_5_pct":None}
        return {
            "observations":len(errors),
            "mae":round(mean(abs(v) for v in errors),3),
            "mean_bias":round(mean(errors),3),
            "within_5_pct":round(100*sum(abs(v)<=5 for v in errors)/len(errors),2),
        }
    family_results={}
    for family in ("GK","DEF","MID","ATT","OTHER"):
        item=bins[family]
        family_results[family]={
            "candidate_players":item["players"],
            "all_pes_attributes":metrics(item["all_errors"]),
            "position_relevant_attributes":metrics(item["relevant_errors"]),
            "per_attribute":{attr:metrics(vals)
                             for attr,vals in sorted(item["by_attr"].items())},
            "v2_reconstruction_methods":dict(item["methods"]),
        }
    return {
        "reference_game":"PES 2020","training_fifa_edition":2020,
        "evaluated_split":"existing_deterministic_20pct_holdout"
                          if holdout_only else "all_provisional_pairs",
        "candidate_players_evaluated":source_pairs,
        "matched_identity_status":"NOT_VERIFIED_no_shared_Konami_EA_player_ID",
        "selection_bias":"Provisional pair matching and same holdout reused for "
                         "candidate offset selection. Not independent validation.",
        "unmatched_pes2020_players":"Not evaluated; original reference has 15035 profiles.",
        "by_primary_position_family":family_results,
    }


def train(output_path):
    fifa=fetch_csv(SRC[2020])
    pes=fetch_csv(PES_SRC)
    pairs=pairs_for_calibration(fifa,pes)
    if len(pairs)<100:
        raise ValueError("Too few FIFA20/PES2020 candidate pairs to calibrate")
    proposals=calibration_proposal(pairs)
    report=choose_calibration(proposals,len(pairs))
    target=Path(output_path)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2),encoding="utf-8")
    position_report=position_accuracy_report(pairs)
    target.with_name("fifa20-pes20-position-accuracy.json").write_text(
        json.dumps(position_report,indent=2),encoding="utf-8")
    print("Position-specific provisional holdout:",
          json.dumps({k:{"players":v["candidate_players"],
                         "relevant_mae":v["position_relevant_attributes"]["mae"]}
                      for k,v in position_report["by_primary_position_family"].items()},
                     indent=2),flush=True)
    print("FIFA20/PES20 calibration:",
          json.dumps({"matched_pairs":len(pairs),
                      "experimental_offsets":report["offsets"],
                      "GK_offsets":0},indent=2),flush=True)
    return report


if __name__=="__main__":
    train("qa-v2-calibration/fifa20-pes20-experimental-calibration.json")

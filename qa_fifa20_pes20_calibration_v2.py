"""Propose a FIFA20-only calibration against the native PES2020 sample.

No FIFA19 data enters the process. Matches require identical normalized name,
age, nationality AND club; these are PROVISIONAL pairs until Konami/EA IDs
are independently matched. Train/holdout MAEs are reported per ability;
goalkeeper parameters excluded until real goalkeeper validation is sufficient.
"""
import json
from pathlib import Path
from qa_pes_conversion_pilot import (
    fetch_csv, SRC, PES_SRC, pairs_for_calibration, calibration_proposal
)
from world_fifa_pes_converter_v2 import CALIBRATION_FIFA_EDITION, TARGET_GAME

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
        "status":"approved_heldout_experimental",
        "candidate_pairs":matched_pairs,
        "identity_quality":"provisional_exact_name_age_nation_club_not_ID_verified",
        "goalkeeper_calibration":"disabled_until_keeper_only_holdout",
        "offsets":selected,
        "per_attribute_heldout":proposals,
        "note":"No FIFA19 record was used for training. Selected shifts improve "
               "held-out 2020 candidate comparison by at least 0.5 points; "
               "use only as experimental cross-edition calibration.",
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
    print("FIFA20/PES20 calibration:",
          json.dumps({"matched_pairs":len(pairs),
                      "experimental_offsets":report["offsets"],
                      "GK_offsets":0},indent=2),flush=True)
    return report


if __name__=="__main__":
    train("qa-v2-calibration/fifa20-pes20-experimental-calibration.json")

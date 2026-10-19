"""No-network FIFA20-only calibration and position MAE regression tests."""
import unittest
from qa_fifa20_pes20_calibration_v2 import (
    choose_calibration, position_accuracy_report
)
from world_fifa_pes_converter_v2 import convert_v2


class PositionAccuracyTests(unittest.TestCase):
    def test_experimental_offsets_are_not_automatically_approved(self):
        proposals={"speed":{"suggested_shift":4,"holdout_mae_before":12,
                            "holdout_mae_after":9,"train_pairs":100,
                            "holdout_pairs":25}}
        report=choose_calibration(proposals,125)
        self.assertEqual(report["training_fifa_edition"],2020)
        self.assertEqual(report["status"],"unapproved_experimental_candidate")
        self.assertEqual(report["offsets"]["speed"],4)

    def test_position_stratification_uses_completed_profiles(self):
        pairs=[]
        for role,name in (("GK","Keeper"),("CB","Defender"),
                          ("CM","Midfielder"),("ST","Forward")):
            fifa={"player_id":str(len(pairs)+1),"name":name,
                  "preferred_positions":role,"rating":"80",
                  "nationality":"England","club":"Example FC",
                  "age":"27","gk_reflexes":"86","gk_diving":"82",
                  "short_pass":"75","sprint_speed":"75"}
            profile=convert_v2(fifa,2020)
            pes={attr:str(a["value"]) for attr,a in profile["abilities"].items()}
            pes["speed"]=str(profile["abilities"]["speed"]["value"]+5)
            pairs.append((fifa,pes))
        report=position_accuracy_report(pairs,holdout_only=False)
        self.assertEqual(report["candidate_players_evaluated"],4)
        families=report["by_primary_position_family"]
        self.assertEqual({f:families[f]["candidate_players"] for f
                          in ("GK","DEF","MID","ATT")},
                         {"GK":1,"DEF":1,"MID":1,"ATT":1})
        self.assertEqual(families["GK"]["position_relevant_attributes"]["mae"],0)
        self.assertGreater(families["DEF"]["all_pes_attributes"]["mae"],0)
        self.assertEqual(families["ATT"]["per_attribute"]["speed"]["mae"],5)


if __name__=="__main__":
    unittest.main()

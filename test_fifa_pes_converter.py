"""FIFA->PES conversion contract: labels, era coverage and no fabricated data."""
import csv
from io import StringIO
import unittest
from world_fifa_pes_converter import (
    TARGETS,convert,convert_csv_stream,positions,MODEL_VERSION,PES_MIN,PES_MAX
)

class FifaToPes20Tests(unittest.TestCase):
    def test_25_stat_contract(self):
        self.assertEqual(len(TARGETS),25)
        self.assertIn("gk_reach",TARGETS)
        self.assertIn("tight_possession",TARGETS)

    def test_fifa05_direct_input_and_na_not_zero(self):
        row={
            "player_id":"1625","name":"Thierry Henry","rating":"97",
            "preferred_positions":"ST/CF",
            "ball_control":"94","dribbling":"92","agility":"86",
            "short_pass":"85","long_pass":"80","finishing":"96",
            "att_position":"NA","reactions":"91","gk_reflexes":"NA",
            "gk_handling":"15","sprint_speed":"95","acceleration":"94",
        }
        x=convert(row,2005)
        self.assertEqual(x["primary_position"],"CF")
        self.assertEqual(x["alternative_positions"],[])
        self.assertEqual(x["abilities"]["ball_control"]["value"],94)
        self.assertEqual(x["abilities"]["ball_control"]["method"],"direct_equivalent")
        self.assertEqual(x["abilities"]["offensive_awareness"]["value"],91)
        self.assertEqual(x["abilities"]["offensive_awareness"]["method"],"weighted_estimate")
        self.assertEqual(x["abilities"]["gk_reflexes"]["method"],"missing")
        self.assertIsNone(x["abilities"]["gk_reflexes"]["value"])

    def test_old_era_reconstructs_only_relevant_known_aggregate(self):
        row={"name":"Test","preferred_positions":"CM/DM",
             "rating":"72","passing":"77","pace":"68","physicality":"71"}
        x=convert(row,2005)
        self.assertEqual(x["primary_position"],"CMF")
        self.assertEqual(x["alternative_positions"],["DMF"])
        self.assertEqual(x["abilities"]["low_pass"]["value"],77)
        self.assertEqual(x["abilities"]["low_pass"]["method"],"aggregate_reconstruction")
        self.assertEqual(x["abilities"]["gk_reflexes"]["method"],"missing")
        self.assertEqual(x["abilities"]["offensive_awareness"]["method"],"missing")
        self.assertTrue(x["position_fit_indices"]["CMF"]["value"] is None
                        or x["position_fit_indices"]["CMF"]["confidence"]=="low")

    def test_fc27_alias_positions_and_ability(self):
        row={"player_id":"999","common_name":"Example",
             "overall_rating":"83","position":"RB",
             "alternate_positions":"CB, LB, CDM",
             "attacking_short_passing":"82","movement_sprint_speed":"88",
             "defending_awareness":"81","defending_standing_tackle":"80",
             "mentality_interceptions":"78","power_strength":"77",
             "power_stamina":"80","goalkeeping_reflexes":"12"}
        x=convert(row,2027)
        self.assertEqual(x["primary_position"],"RB")
        self.assertEqual(x["alternative_positions"],["CB","LB","DMF"])
        self.assertEqual(x["abilities"]["speed"]["value"],88)
        self.assertEqual(x["abilities"]["gk_reflexes"]["value"],40)
        self.assertTrue(x["abilities"]["gk_reflexes"]["floor_applied"])
        self.assertNotIn("GK",x["position_fit_indices"])
        self.assertEqual(x["abilities"]["defensive_awareness"]["method"],"weighted_estimate")
        self.assertEqual(x["model_version"],MODEL_VERSION)

    def test_fc23_camel_columns_and_positions(self):
        row={"ID":"123","Name":"Example","Overall":"88",
             "Positions":"CAM, RW","ShortPassing":"90","Acceleration":"85",
             "BallControl":"91","Dribbling":"90","GKReflexes":"8"}
        x=convert(row,2023)
        self.assertEqual(x["primary_position"],"AMF")
        self.assertEqual(x["alternative_positions"],["RWF"])
        self.assertEqual(x["abilities"]["low_pass"]["value"],90)
        self.assertEqual(x["abilities"]["acceleration"]["value"],85)

    def test_no_unlisted_position_inferred(self):
        row={"position":"RB","defending_awareness":"90","power_strength":"90"}
        x=convert(row,2027)
        self.assertEqual(list(x["position_fit_indices"]),["RB"])

    def test_invalid_calibration_rejected(self):
        with self.assertRaises(ValueError):
            convert({"speed":"88","movement_sprint_speed":"75"},2027,
                    calibration={"speed":35})

    def test_csv_stream_and_null_encoding(self):
        inp=StringIO("player_id,position,goalkeeping_reflexes,passing\n1,GK,81,\\n2,CB,,88\n")
        dst=StringIO()
        result=convert_csv_stream(inp,2027,dst)
        self.assertEqual(result["processed"],2)
        self.assertEqual(len(dst.getvalue().splitlines()),2)
        self.assertGreater(result["missing"],0)
        self.assertIn('"value": null',dst.getvalue())


if __name__=="__main__":
    unittest.main()

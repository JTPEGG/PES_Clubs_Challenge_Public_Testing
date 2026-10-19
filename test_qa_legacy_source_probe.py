"""Test source field and identity audit without downloading player records."""
import unittest
from qa_legacy_source_probe import (
    schema_probe,date_value,PES_ABILITY_COLUMNS,PES_POSITION_COLUMNS,
    fifa20_pes20_crosswalk_candidates,
)


class LegacyDataSourceProbeTests(unittest.TestCase):
    def test_fifa20_same_ea_id_and_birth(self):
        raw=(
            "sofifa_id,dob,long_name,overall,player_positions,wage_eur\n"
            "239085,2000-07-21,Erling Haaland,85,ST,100000\n"
            "158023,1987-06-24,Lionel Messi,95,RW,500000\n"
        )
        result=schema_probe(raw,"test-FIFA20")
        self.assertEqual(result["reference_pilot_verified_id_and_dob_count"],1)
        self.assertEqual(result["reference_pilot_ea_id_candidate_count"],1)

    def test_same_name_wrong_birth_does_not_match(self):
        raw=(
            "sofifa_id,dob,long_name,overall,player_positions\n"
            "239085,1999-07-21,Erling Haaland,85,ST\n"
        )
        result=schema_probe(raw,"test-FIFA20")
        self.assertEqual(result["reference_pilot_verified_id_and_dob_count"],0)
        self.assertEqual(result["reference_pilot_mismatched_or_missing_dob_records"],1)

    def test_pes_detailed_fields_not_a_player_identity(self):
        attributes=["offensive_awareness","speed","finishing","dribbling"]
        cols=["name","age","nationality"]+attributes+["rating_as_CB","rating_as_RB","skill_man_marking"]
        line="Alex Example,21,England,80,90,70,70,77,76,1"
        result=schema_probe(",".join(cols)+"\n"+line+"\n","test-PES20")
        self.assertEqual(result["reference_pilot_verified_id_and_dob_count"],0)
        self.assertEqual(result["native_pes_abilities_available"],4)
        self.assertEqual(result["native_pes_position_rating_columns"],2)
        self.assertEqual(result["records_with_all_detected_pes_abilities"],1)

    def test_historical_crosswalk_is_only_a_candidate(self):
        header_fifa=["sofifa_id,short_name,nationality,age,club,dob",
                     "239085,E. Haaland,Norway,19,RB Salzburg,2000-07-21"]
        header_pes=["name,nationality,age,team_name",
                    "E. Haaland,Norway,19,RB Salzburg"]
        fifa=chr(10).join(header_fifa)+chr(10)
        pes=chr(10).join(header_pes)+chr(10)
        report=fifa20_pes20_crosswalk_candidates(fifa,pes)
        self.assertEqual(report["qualifying_candidate_pairs"],1)
        self.assertEqual(report["modern_pilot_exact_fifa20_ids"],1)
        self.assertEqual(report["modern_pilot_with_pes20_candidate"],1)
        self.assertIn("CANDIDATES_NOT_VERIFIED",report["label"])
        ambiguous=fifa20_pes20_crosswalk_candidates(
            fifa,pes+header_pes[1]+chr(10))
        self.assertEqual(ambiguous["qualifying_candidate_pairs"],0)
        self.assertEqual(ambiguous["ambiguous_shared_keys_rejected"],1)

    def test_full_pes_attribute_catalogue_is_25(self):
        self.assertEqual(len(PES_ABILITY_COLUMNS),25)
        self.assertEqual(len(PES_POSITION_COLUMNS),13)
        self.assertEqual(date_value("2000-07-21"),date_value("21-07-2000"))
        self.assertIsNone(date_value("not-a-date"))


if __name__=="__main__":
    unittest.main()

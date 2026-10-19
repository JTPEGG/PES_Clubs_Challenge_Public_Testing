"""Regression gates for FIFA20-only PES20 calibration and PES export completeness."""
import copy
import unittest
from world_fifa_pes_converter_v2 import (
    ConversionError, UnrestoredEdition, EditionContext, convert_v2,
    validate_exportable, identity_key, _source_evidence, TARGETS, MODEL_VERSION,
)

class CompleteConverterV2Tests(unittest.TestCase):
    def test_fifa20_only_not_fifa19_and_never_fc25(self):
        with self.assertRaises(UnrestoredEdition):
            convert_v2({"player_id":"1","name":"Example","preferred_positions":"ST"},2025)
        with self.assertRaises(ConversionError):
            convert_v2({"player_id":"1","name":"Example","preferred_positions":"ST"},2019,
                       approved_calibration={"source_edition":2020,
                                             "reference_game":"PES 2020",
                                             "status":"approved","offsets":{"speed":2}})
        ok=convert_v2({"player_id":"1","name":"Example","preferred_positions":"ST",
                       "sprint_speed":"80"},2020,
                      approved_calibration={"source_edition":2020,
                                            "reference_game":"PES 2020",
                                            "status":"approved","offsets":{"speed":2}})
        self.assertEqual(ok["abilities"]["speed"]["value"],82)
        self.assertEqual(ok["abilities"]["speed"]["calibration_status"],
                         "approved_FIFA20_PES2020")

    def test_25_core_and_four_aux_are_always_complete(self):
        p=convert_v2({"name":"Fictional GK","player_id":"12",
                       "preferred_positions":"GK","rating":"72",
                       "gk_reflexes":"84","gk_positioning":"80",
                       "gk_handling":"76"},2005)
        self.assertTrue(validate_exportable(p))
        self.assertEqual(len(p["abilities"]),25)
        self.assertEqual(len(p["additional"]),4)
        self.assertTrue(all(isinstance(v["value"],int)
                            for v in p["abilities"].values()))
        self.assertIn(p["abilities"]["gk_reach"]["method"],
            ("related_same_edition","adjacent_edition_same_id_dob",
             "same_edition_position_peer_median","position_ovr_prior"))
        self.assertIn("gk_reflexes",p["abilities"]["gk_reach"]["source_columns"])
        self.assertNotEqual(p["abilities"]["gk_reach"]["value"],40)

    def test_missing_2006_reflexes_from_other_goalkeeper_abilities(self):
        p=convert_v2({"name":"Keeper","player_id":"12",
                       "preferred_positions":"GK","rating":"75",
                       "gk_diving":"86","gk_handling":"81",
                       "gk_positioning":"83","gk_reflexes":"NA"},2006)
        self.assertGreater(p["abilities"]["gk_reflexes"]["value"],70)
        self.assertEqual(p["abilities"]["gk_reflexes"]["method"],
                         "related_same_edition")

    def test_use_adjacent_edition_id_and_dob_only_when_needed(self):
        historic={"player_id":"1234","name":"Player",
                  "birthdate":"1982-01-01","rating":"82",
                  "preferred_positions":"GK","gk_diving":"NA"}
        next_year={"player_id":"1234","name":"Player",
                   "birthdate":"1982-01-01","rating":"83",
                   "preferred_positions":"GK","gk_diving":"87"}
        # Explicitly no same-edition reflex etc -> adjacent relevant.
        c=EditionContext(2005,[historic],{2006:[next_year]})
        x=convert_v2(historic,2005,context=c)
        self.assertEqual(x["abilities"]["gk_reach"]["method"],
                         "adjacent_edition_same_id_dob")
        self.assertEqual(x["abilities"]["gk_reach"]["value"],86)

        other=dict(next_year,birthdate="1983-01-01")
        invalid=EditionContext(2005,[historic],{2006:[other]})
        y=convert_v2(historic,2005,context=invalid)
        self.assertNotEqual(y["abilities"]["gk_reach"]["method"],
                            "adjacent_edition_same_id_dob")

    def test_adjacent_never_consults_fc25(self):
        p={"player_id":"1","birthdate":"2000-01-01","name":"Test",
           "rating":"80","preferred_positions":"GK"}
        excluded=dict(p,gk_diving="99")
        c=EditionContext(2024,[p],{2025:[excluded]})
        x=convert_v2(p,2024,context=c)
        self.assertNotEqual(x["abilities"]["gk_reach"]["method"],
                            "adjacent_edition_same_id_dob")

    def test_peer_statistics_conditioned_on_position_and_quality(self):
        rows=[]
        for n in range(18):
            rows.append({"player_id":str(800+n),"name":"Keeper "+str(n),
                         "preferred_positions":"GK","rating":str(70+n%4),
                         "gk_diving":str(72+n%5)})
        test={"player_id":"1","name":"Unknown","rating":"72",
              "preferred_positions":"GK"}
        c=EditionContext(2005,rows+[test])
        x=convert_v2(test,2005,context=c)
        self.assertEqual(x["abilities"]["gk_reach"]["method"],
                         "same_edition_position_peer_median")
        self.assertGreater(x["abilities"]["gk_reach"]["value"],65)

    def test_no_fifa_overall_only_as_complete_identity(self):
        poor={"name":"Example","preferred_positions":"CB","rating":"66"}
        x=convert_v2(poor,2007)
        self.assertTrue(validate_exportable(x))
        self.assertTrue(all(v["value"]>=40 for v in x["abilities"].values()))
        self.assertTrue(any(v["method"]=="position_ovr_prior"
                            for v in x["abilities"].values()))

    def test_invalid_pos_and_missing_name_fail_closed(self):
        with self.assertRaises(ConversionError):
            convert_v2({"name":"Player","preferred_positions":"?","rating":"80"},2005)
        with self.assertRaises(ConversionError):
            convert_v2({"preferred_positions":"GK","rating":"80"},2005)

    def test_reconstructed_fields_have_origin(self):
        p=convert_v2({"name":"No Detailed Skills","preferred_positions":"RB",
                       "rating":"65"},2005)
        for attr in TARGETS:
            item=p["abilities"][attr]
            self.assertIn("method",item)
            self.assertIn("source_columns",item)
            self.assertIn("confidence",item)
            self.assertIn("model_version",item)
        self.assertEqual(p["model_version"],MODEL_VERSION)

    def test_fifa20_exact_id_dob_required(self):
        a={"player_id":"123","birthdate":"2000-03-04"}
        b={"player_id":"123","dob":"2000-03-04"}
        wrong={"player_id":"123","dob":"2000-03-05"}
        self.assertEqual(identity_key(a,2005),identity_key(b,2020))
        self.assertNotEqual(identity_key(a,2005),identity_key(wrong,2020))


if __name__=="__main__":
    unittest.main()

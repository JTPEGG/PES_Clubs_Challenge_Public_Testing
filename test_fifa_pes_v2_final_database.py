"""Offline integration test of the final archive sharding/merge gate."""
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.merge_fifa_pes_v2_final_database import merge, YEARS
from world_fifa_pes_converter_v2 import TARGETS


class FinalDatabaseMergeTests(unittest.TestCase):
    def test_22_annual_CSVs_have_exact_source_parity_and_all_29_integer_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            shards=p/"shards"
            shards.mkdir()
            source=p/"selected.zip"
            years=sorted(YEARS)
            sources=[{"edition":year,"player_rows":1,"catalog_source":"provider"+str(year)}
                     for year in years]
            with ZipFile(source,"w") as z:
                z.writestr("selected/MANIFEST.json",json.dumps({
                    "archive_version":"PES_V2_STARTING_PLAYER_SOURCE_DATABASE_1.0",
                    "downloads":sources}))
            for name,group in (
                ("legacy",[y for y in years if y<=2014]),
                ("restored",[y for y in years if 2015<=y<=2020]),
                ("modern",[y for y in years if y>=2021])):
                with ZipFile(shards/f"shard-{name}.zip","w") as z:
                    per={}
                    for year in group:
                        prov="provider"+str(year)
                        data={
                            "source_player_id":"12","player_name":"Test",
                            "source_provider":prov,
                            "namespaced_source_player_key":f"{year}:{prov}:12",
                            "identity_dob":"1990-01-01",
                            "primary_position":"GK",
                            "weak_foot_usage":2,"weak_foot_accuracy":3,
                            "form":4,"injury_resistance":2,
                            **{k:65 for k in TARGETS},
                        }
                        out=io.StringIO(newline="")
                        writer=csv.DictWriter(out,fieldnames=list(data))
                        writer.writeheader()
                        writer.writerow(data)
                        z.writestr(f"PES2020_v2/{year}_FIFA_to_PES2020_Complete.csv",
                                   out.getvalue())
                        per[str(year)]={
                            "status":"FULLY_NUMERIC_ESTIMATED_OUTPUT",
                            "source_player_rows":1,
                            "converted_players":1,
                            "source_provider":prov,
                        }
                    z.writestr("PES2020_v2/MANIFEST.json",json.dumps({
                        "calibration_offsets_applied":False,"per_edition":per}))
            merged=p/"final.zip"
            result=merge(source,shards,merged)
            self.assertEqual(result["editions"],22)
            self.assertEqual(result["converted_player_records"],22)
            self.assertEqual(result["validated_integer_PES_core_attributes"],550)
            self.assertEqual(result["validated_integer_auxiliary_fields"],88)
            self.assertEqual(result["identity_audit"]["2020"]["missing_source_ids"],0)
            with ZipFile(merged) as z:
                rows=[x for x in z.namelist() if x.endswith("_Complete.csv")]
                self.assertEqual(len(rows),22)
                self.assertNotIn("PES2020_v2/2025_FIFA_to_PES2020_Complete.csv",rows)
                manifest=json.loads(z.read("PES2020_v2/MANIFEST.json"))
                self.assertTrue(manifest["source_original_bytes_preserved"])
                self.assertFalse(manifest["Xbox_option_file_created"])

    def test_raises_if_missing_shards(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            with ZipFile(p/"selected.zip","w"):pass
            with self.assertRaises(ValueError):
                merge(p/"selected.zip",p,p/"output.zip")


if __name__=="__main__":
    unittest.main()

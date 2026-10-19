"""Edition-aware CSV full completeness tests, FC25 explicit gap and source preservation."""
import csv
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from scripts.export_fifa_pes_v2 import export,COLUMNS
from world_fifa_pes_converter_v2 import TARGETS


class ExportV2Tests(unittest.TestCase):
    def test_2025_is_a_gap_not_a_reconstruction(self):
        with TemporaryDirectory() as d:
            original=Path(d)/"in.zip";output=Path(d)/"out.zip"
            with ZipFile(original,"w") as z:
                for year in (2024,2025,2026):
                    z.writestr(f"fifa/data/{year}_edition.csv",
                        "player_id,name,dob,positions,overall_rating,goalkeeping_reflexes\n"
                        "1,Example,2000-07-12,GK,70,80\n")
            report=export(original,output,limit_per_edition=1)
            self.assertEqual(report["per_edition"]["2025"]["converted_players"] if
                "converted_players" in report["per_edition"]["2025"] else 0,0)
            self.assertEqual(report["per_edition"]["2025"]["status"],
                             "SOURCE_GAP_NOT_REPAIRED")
            with ZipFile(output) as z:
                self.assertFalse(any("2025_FIFA" in n for n in z.namelist()))
                self.assertIn("PES2020_v2/2024_FIFA_to_PES2020_Complete.csv",
                              z.namelist())
                self.assertIn("PES2020_v2/2026_FIFA_to_PES2020_Complete.csv",
                              z.namelist())
                out=next(csv.DictReader(StringIO(
                    z.read("PES2020_v2/2024_FIFA_to_PES2020_Complete.csv").decode())))
                self.assertEqual(out["gk_reach_method"],"related_same_edition")
                for stat in TARGETS:
                    self.assertTrue(out[stat].isdigit(),stat)

    def test_csv_metadata_covers_all_25_and_four_aux(self):
        for x in TARGETS:
            self.assertIn(x,COLUMNS)
            self.assertIn(x+"_method",COLUMNS)
            self.assertIn(x+"_confidence",COLUMNS)
            self.assertIn(x+"_sources",COLUMNS)
        for x in ("weak_foot_usage","weak_foot_accuracy","form","injury_resistance"):
            self.assertIn(x,COLUMNS)
            self.assertIn(x+"_method",COLUMNS)
        self.assertIn("position_fit_indices",COLUMNS)
        for x in TARGETS:
            self.assertIn(x+"_source_edition",COLUMNS)
            self.assertIn(x+"_calibration_shift",COLUMNS)

    def test_synthetic_all_22_supported_editions_stay_complete(self):
        with TemporaryDirectory() as d:
            original=Path(d)/"all_fifa.zip"
            output=Path(d)/"all_pes.zip"
            with ZipFile(original,"w") as z:
                for year in range(2005,2028):
                    z.writestr(f"fifa_fc_2000_2027/data/{year}_season.csv",
                        "player_id,name,dob,preferred_positions,rating,gk_reflexes,sprint_speed\n"
                        "123,Test Keeper,1988-02-07,GK,72,80,30\n"
                        "124,Test Wing Back,1987-06-04,RWB,73,11,82\n")
            result=export(original,output,require_all_supported=True)
            self.assertEqual(len(result["per_edition"]),23)
            self.assertEqual(result["per_edition"]["2025"]["status"],
                             "SOURCE_GAP_NOT_REPAIRED")
            supported={str(y) for y in range(2005,2028) if y!=2025}
            self.assertEqual({k for k,v in result["per_edition"].items()
                              if v["status"]=="FULLY_NUMERIC_ESTIMATED_OUTPUT"},
                             supported)
            with ZipFile(output) as z:
                data=[p for p in z.namelist() if p.endswith("_Complete.csv")]
                self.assertEqual(len(data),22)
                for file in data:
                    parsed=list(csv.DictReader(StringIO(z.read(file).decode())))
                    self.assertEqual(len(parsed),2)
                    for r in parsed:
                        self.assertTrue(all(r[attr].isdigit() for attr in TARGETS))
                        self.assertEqual(len(json.loads(r["position_fit_indices"])),
                                         1)
                manifest=json.loads(z.read("PES2020_v2/MANIFEST.json"))
                self.assertFalse(manifest["source_rosters_independently_verified_complete"])
                self.assertEqual(
                    manifest["known_upstream_700_page_scrape_ceiling_editions"],[])
                for year in supported:
                    entry=manifest["per_edition"][year]
                    self.assertEqual(entry["ratings_written"],50)
                    self.assertEqual(entry["numeric_core_completeness_pct"],100.0)
                    self.assertEqual(entry["source_coverage_status"],
                                     "SOURCE_COVERAGE_NOT_INDEPENDENTLY_VERIFIED")
                    self.assertEqual(entry["source_provider"],"unknown")
                    self.assertEqual(set(entry["per_position_family"]),
                                     {"GK","DEF"})



if __name__=="__main__":
    unittest.main()

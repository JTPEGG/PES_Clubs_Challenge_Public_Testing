"""Edition-aware CSV full completeness tests, FC25 explicit gap and source preservation."""
import csv
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


if __name__=="__main__":
    unittest.main()

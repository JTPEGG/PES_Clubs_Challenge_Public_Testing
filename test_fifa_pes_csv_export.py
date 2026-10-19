"""File-level CSV conversion preserves editions, empty fields and provenance."""
from io import BytesIO,StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import csv
import json
import unittest
from zipfile import ZipFile

from scripts.export_fifa_pes_csvs import convert_file,export_zip,FIELDNAMES

class PESCSVExportTests(unittest.TestCase):
    def test_csv_provenance_direct_vs_estimated(self):
        data=StringIO("player_id,name,preferred_positions,rating,ball_control,short_pass,dribbling\n1,Sample A,ST/CM,77,75,80,78\n")
        out=StringIO()
        result=convert_file(data,2005,out)
        self.assertEqual(result["rows"],1)
        row=next(csv.DictReader(StringIO(out.getvalue())))
        self.assertEqual(row["source_edition"],"2005")
        self.assertEqual(row["primary_position"],"CF")
        self.assertIn("CMF",row["alternative_positions"])
        self.assertEqual(row["ball_control"],"75")
        self.assertEqual(row["ball_control_method"],"direct_equivalent")
        self.assertEqual(row["gk_reflexes"],"")
        self.assertEqual(row["gk_reflexes_method"],"missing")
        self.assertIn("ball_control",json.loads(row["ball_control_source_fields"]))

    def test_zip_preserves_years_and_does_not_make_game_file(self):
        with TemporaryDirectory() as tmp:
            a=Path(tmp)/"original.zip";b=Path(tmp)/"converted.zip"
            with ZipFile(a,"w") as z:
                z.writestr("fifa_fc_2000_2027/data/2005_fifa_05.csv",
                           "player_id,name,rating,preferred_positions,ball_control\n1,A,82,CM,70\n")
                z.writestr("fifa_fc_2000_2027/data/2027_ea_fc_27.csv",
                           "player_id,common_name,overall_rating,position,alternate_positions,skill_ball_control\n2,B,85,CB,LB,80\n")
            report=export_zip(a,b)
            self.assertEqual(set(report["per_edition"]),{"2005","2027"})
            with ZipFile(b) as z:
                names=z.namelist()
                self.assertIn("PES2020_converted/2005_pes2020_estimates.csv",names)
                self.assertIn("PES2020_converted/2027_pes2020_estimates.csv",names)
                self.assertIn("PES2020_converted/MANIFEST.json",names)
                self.assertFalse(any(x.endswith(".ted") or x.endswith(".bin") for x in names))


if __name__=="__main__":
    unittest.main()

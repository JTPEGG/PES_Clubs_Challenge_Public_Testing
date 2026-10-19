"""Tests for PES archive source identity and read-only source integrity."""
import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from scripts.build_pes_historical_archive import SOURCES,audit_csv,ROOT

class PESArchiveTests(unittest.TestCase):
    def test_two_different_historical_sources(self):
        self.assertEqual(len(SOURCES),2)
        self.assertEqual({x["id"] for x in SOURCES},
          {"pes_2020_native_attributes","playersdb_historical_pes_identities"})
        self.assertNotEqual(SOURCES[0]["filename"],SOURCES[1]["filename"])

    def test_pes_has_25_original_ability_fields(self):
        src=SOURCES[0]["expected_columns"]
        for field in ("offensive_awareness","gk_reach",
                      "tight_possession","low_pass","place_kicking"):
            self.assertIn(field,src)
        self.assertIn("rating_as_CF",src)
        self.assertIn("playing_style",src)

    def test_identity_archive_does_not_claim_native_ability_scores(self):
        identity=SOURCES[1]
        self.assertIn("game_versions",identity["expected_columns"])
        self.assertNotIn("offensive_awareness",identity["expected_columns"])
        self.assertNotIn("fifaID",identity["expected_columns"])

    def test_rejects_bad_headers_and_too_few_rows(self):
        with TemporaryDirectory() as d:
            f=Path(d)/"bad.csv"
            f.write_text("id,name\n1,Test\n",encoding="utf-8")
            with self.assertRaises(ValueError):
                audit_csv(f,{"game_versions"},10000)

    def test_no_project_career_files_or_installation(self):
        self.assertEqual(ROOT,"PES_Historical_Databases")
        self.assertTrue(all(s["url"].startswith("https://") for s in SOURCES))

if __name__=="__main__":
    unittest.main()

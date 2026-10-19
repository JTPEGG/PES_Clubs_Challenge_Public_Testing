"""Validate the annual FIFA/FC warehouse-source map and conservative status."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CATALOG=json.loads((ROOT/"docs"/"warehouse"/
                    "fifa_fc_annual_sources_2000_2027.json").read_text(
                        encoding="utf-8"))
REPORT=(ROOT/"docs"/"warehouse"/"FIFA_FC_ANNUAL_2000_2027.md").read_text(
    encoding="utf-8")


class FifaFcSourceCatalogTests(unittest.TestCase):
    def test_complete_range_and_unambiguous_editions(self):
        self.assertEqual(len(CATALOG["records"]),28)
        self.assertEqual([x["edition"] for x in CATALOG["records"]],
                         list(range(2000,2028)))
        self.assertEqual(len({x["label"] for x in CATALOG["records"]}),28)

    def test_2005_through_fc27_have_direct_hosted_files(self):
        for row in CATALOG["records"][5:]:
            with self.subTest(year=row["edition"]):
                self.assertIn(row["status"],
                              ("github_csv_present","hosted_multiyear_csv"))
                self.assertTrue(row["url"].startswith("https://"))
                self.assertTrue(row["file_path"].lower().endswith(".csv"))

    def test_early_game_restrictions_cannot_be_misread_as_verified_files(self):
        for row in CATALOG["records"][:5]:
            self.assertNotIn(row["status"],
                             ("github_csv_present","hosted_multiyear_csv"))
            self.assertIn("unverified" if row["edition"]>=2003 else "unextractable",
                          row["status"])
        self.assertEqual(CATALOG["records"][4]["edition"],2004)
        self.assertIn("XLSX",CATALOG["records"][4]["file_path"])

    def test_fifa05_to_20_are_all_single_year_csvs(self):
        root="lbenz730/fifa_model"
        for year in range(2005,2021):
            x=CATALOG["records"][year-2000]
            self.assertEqual(x["source"],root)
            self.assertEqual(x["file_path"],
                             f"stats/player_stats_{year}.csv")

    def test_fifa23_multiseason_is_explicit(self):
        x=CATALOG["records"][23]
        self.assertEqual(x["status"],"hosted_multiyear_csv")
        self.assertEqual(x["source"],"jsulz/FIFA23")
        self.assertIn("multiyear",x["notes"])

    def test_game_edition_boundaries(self):
        self.assertEqual(CATALOG["records"][4]["label"],"FIFA 2004")
        self.assertEqual(CATALOG["records"][23]["label"],"FIFA 23")
        self.assertEqual(CATALOG["records"][24]["label"],"EA FC 24")
        self.assertEqual(CATALOG["records"][27]["label"],"EA FC 27")
        self.assertIn("2004/05",CATALOG["game_year_vs_calendar"])

    def test_readable_report_includes_each_edition(self):
        for row in CATALOG["records"]:
            self.assertIn("| "+row["label"]+" |",REPORT)


if __name__=="__main__":
    unittest.main()

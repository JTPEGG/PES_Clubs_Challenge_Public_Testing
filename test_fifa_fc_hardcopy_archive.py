"""Verify annual archive builds only exact game-edition CSVs."""
import json
from pathlib import Path
import unittest
from scripts.build_fifa_fc_archive import (
    CATALOG, ARCHIVE_DIR, file_name, resolve_source,
)


class AnnualHardcopyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.years=json.loads(CATALOG.read_text(encoding="utf-8"))["records"]

    def test_complete_2000_to_fc27_years(self):
        self.assertEqual([x["edition"] for x in self.years],list(range(2000,2028)))

    def test_early_2000_to_2004_have_no_fake_download_link(self):
        self.assertTrue(all(resolve_source(x) is None for x in self.years[:5]))

    def test_2005_through_fc27_have_downloadable_pinned_sources(self):
        self.assertEqual(len([x for x in self.years if resolve_source(x)]),23)
        for row in self.years[5:]:
            with self.subTest(year=row["edition"]):
                uri=resolve_source(row)
                self.assertTrue(uri.startswith(
                    ("https://raw.githubusercontent.com/","https://huggingface.co/")))
                self.assertTrue(uri.endswith(".csv"))
                self.assertNotIn("/blob/",uri)

    def test_2023_source_is_single_edition_not_90mb_multiyear(self):
        row=self.years[23]
        link=resolve_source(row)
        self.assertIn("miraehab/FIFA-23-ML-Project/",link)
        self.assertIn("0d188076fa37b3d82c5d390048e00ec5a43b04a7",link)
        self.assertTrue(link.endswith("players_fifa23.csv"))

    def test_every_archive_csv_filename_is_unique(self):
        actual=[file_name(x) for x in self.years[5:]]
        self.assertEqual(len(set(actual)),23)
        self.assertIn("2005_fifa_05.csv",actual)
        self.assertIn("2027_ea_fc_27.csv",actual)


if __name__=="__main__":
    unittest.main()

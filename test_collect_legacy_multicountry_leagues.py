"""Historical pre-2010 CC0 countries must remain separate and season-specific."""
import unittest
from scripts.collect_legacy_multicountry_leagues import (
    PIN, LEAGUES, source_teams_csv,
)


class LegacyCountryCompetitionTests(unittest.TestCase):
    def test_scope_and_pinned_source(self):
        self.assertEqual(len(PIN), 40)
        self.assertEqual(len(LEAGUES), 8)
        self.assertEqual(LEAGUES["ar"][0], "Argentina")
        self.assertEqual(LEAGUES["de"][0], "Germany")
        self.assertNotIn("eng", LEAGUES)

    def test_fixture_name_extraction_requires_valid_matches(self):
        sample = "Date,Team 1,FT,Team 2\n" + (
            "2004-08-08,Team A,1-0,Team B\n" * 100)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            source_teams_csv(sample)
        with self.assertRaisesRegex(ValueError, "columns"):
            source_teams_csv("Name,Result\nA,1-0\n")


if __name__ == "__main__":
    unittest.main()

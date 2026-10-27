"""Omitted leagues cannot re-enter historical game-facing competitions."""
import unittest
from world_competition_exclusions import excluded_competition,excluded_source_league

class ActiveWorldExclusions(unittest.TestCase):
    def test_source_label_and_competition_code_excluded(self):
        self.assertTrue(excluded_source_league("ISL"))
        self.assertTrue(excluded_source_league("Indian Super League"))
        self.assertTrue(excluded_source_league(" isl "))
        self.assertTrue(excluded_competition(code="2027:in.1"))
        self.assertTrue(excluded_competition(code="in.1"))
        self.assertTrue(excluded_competition(label="ISL"))
    def test_no_broad_country_or_homonym_exclusions(self):
        self.assertFalse(excluded_competition(country="India",code="other.league"))
        self.assertFalse(excluded_competition(country="Scotland",label="Scottish Premiership"))
        self.assertFalse(excluded_source_league("Icelandic Premier League"))
        self.assertFalse(excluded_source_league("MLS"))
    def test_no_annual_game_year_inheritance(self):
        self.assertFalse(excluded_competition(code="2027:en.1"))
        self.assertFalse(excluded_competition(code="2026:be.1"))

if __name__=="__main__":unittest.main()

"""Regression for pinned, edition-aware football source supplement."""
import unittest
from scripts.collect_historical_competition_supplement import (
  ENGLAND_PIN,WORLD_PIN,SOUTH_AMERICA_PIN,source_targets,
)
from scripts.collect_historical_national_league_feeders import parse_source

class HistoricalSupplementTests(unittest.TestCase):
 def test_calendar_year_is_previous_calendar_in_edition(self):
  a=source_targets(2026,set())
  mls=next(x for x in a if x[2]=="us.mls")
  ar=next(x for x in a if x[2]=="ar.1")
  self.assertTrue(mls[6].endswith("/2025_mls.txt"))
  self.assertTrue(ar[6].endswith("/2025_ar1.txt"))
  self.assertTrue(any(x[2]=="en.3" and x[1]=="2025-26" for x in a))
  with self.assertRaises(ValueError):source_targets(2025,set())
 def test_existing_json_league_season_not_overwritten(self):
  x=source_targets(2022,{(2022,"en.1"),(2022,"ar.1"),(2022,"us.mls")})
  self.assertFalse(any(t[2] in ("en.1","ar.1","us.mls") for t in x))
 def test_fixture_formats_and_team_count(self):
  old="# Teams      10\n" + "  15:00  Team A            2-1 (0-0)  Team B\n"*55
  new="# Teams      10\n" + "  19:00  Team A             v Team B                2-1 (0-0)\n"*55
  # Parser captures genuine fixture pairings; a declared 10 for 2
  # distinct teams is correctly considered an incomplete source by collector.
  self.assertEqual(parse_source(old)[2],55)
  self.assertEqual(parse_source(new)[2],55)
  self.assertEqual(len(ENGLAND_PIN),40)
  self.assertEqual(len(WORLD_PIN),40)
  self.assertEqual(len(SOUTH_AMERICA_PIN),40)

if __name__=="__main__":unittest.main()

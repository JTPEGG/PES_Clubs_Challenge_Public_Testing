"""2024/25-2004/05 England historic league team parsing guard tests."""
import unittest
from scripts.collect_openfootball_legacy_england import teams_from_text,SOURCE_FILES
class LegacyEnglandCompetitionTests(unittest.TestCase):
 def test_footballtxt_extracts_league_teams_not_dates_headings(self):
  rows="= English Premier League 2004/05\n# Teams 20\n▪ Matchday 1\nSat Aug 14\n"
  rows+="  12:45  Tottenham Hotspur        1-1 (1-1)  Liverpool FC\n"
  rows+="  15:00  Aston Villa              2-0 (2-0)  Southampton FC\n"
  rows+="         Newcastle United         2-1 (1-1)  Everton FC\n"\n  rows+="         Arsenal FC               2-1 (1-1)  West Ham United\n"\n  rows+=("         Blackburn Rovers         1-1 (1-1)  Manchester City\n"*60)
  clubs,num,results=teams_from_text(rows)
  self.assertEqual(num,20)
  self.assertIn("Liverpool FC",clubs)
  self.assertNotIn("Sat Aug 14",clubs)
  self.assertEqual(results,64)
 def test_english_four_tiers_source_pinned(self):
  self.assertEqual(tuple(SOURCE_FILES),(1,2,3,4))
  self.assertEqual(SOURCE_FILES[2][1],"Championship")
if __name__=="__main__":unittest.main()

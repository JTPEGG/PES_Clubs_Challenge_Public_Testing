import unittest,json
from pathlib import Path
from scripts.audit_official_mls_2026 import clubkey

class MLSSeasonRulesTests(unittest.TestCase):
 def test_2026_official_format_is_not_the_2027_calendar_year(self):
  doc=json.loads(Path("data/warehouse/mls_2026_official_competition_format.json").read_text())
  self.assertEqual((doc["edition"],doc["calendar_season"]),(2027,2026))
  self.assertEqual(doc["regular_season"]["matches_per_team"],34)
  self.assertEqual(doc["postseason"]["wildcard_seeds"],[8,9])
  self.assertEqual(sum(len(x) for x in doc["club_conferences"].values()),30)
  self.assertEqual(len({clubkey(x) for a in doc["club_conferences"].values() for x in a}),30)
  self.assertTrue(all(v==0 for v in doc["pyramid_movement"].values()))
  self.assertFalse(doc["game_career_ready"])

if __name__=="__main__":unittest.main()

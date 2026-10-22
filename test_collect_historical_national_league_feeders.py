"""Do not confuse fifth-tier fixture entrants with a complete simulated squad."""
import unittest
from scripts.collect_historical_national_league_feeders import parse_source
class NationalLeagueEvidenceTests(unittest.TestCase):
 def test_two_fixture_source_formats(self):
  first="= National League\n# Teams 2\n▪ Round\n"
  first+="  12:30  Sutton United            2-0 (1-0)  Leyton Orient\n"
  n,t,played=parse_source(first)
  self.assertEqual(n,2);self.assertEqual(t,["Leyton Orient","Sutton United"])
  modern="# Teams 2\n  14:00  Altrincham FC           v Aldershot Town           3-2 (2-0)\n"
  n,t,played=parse_source(modern)
  self.assertEqual(t,["Aldershot Town","Altrincham FC"])
  self.assertEqual(played,1)
 def test_no_declared_membership_league_is_not_accepted(self):
  with self.assertRaisesRegex(ValueError,"declared"):
   parse_source("Man United 1-0 Liverpool")

if __name__=="__main__":unittest.main()

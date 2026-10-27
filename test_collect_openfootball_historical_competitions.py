"""Pin and require non-guessing historical club membership collection."""
import unittest
from scripts.collect_openfootball_historical_competitions import (
 LEAGUES,PIN,matches_to_teams,match_club,namekey,source_season
)

class OpenFootballCompetitionTests(unittest.TestCase):
 def test_pinned_source_and_edition_mapping(self):
  self.assertEqual(len(PIN),40)
  self.assertEqual(source_season(2011),"2010-11")
  self.assertEqual(source_season(2027),"2026-27")
  self.assertEqual(LEAGUES["en.4"][1],4)
  self.assertEqual(LEAGUES["de.3"][1],3)
  with self.assertRaises(ValueError):source_season(2005)
 def test_raw_fixture_team_names_are_preserved_without_automatic_fuzzy_aliases(self):
  payload={"matches":[
    {"team1":"Manchester United","team2":"Chelsea"},
    {"team1":"Chelsea","team2":"Tottenham Hotspur"}
  ]}
  self.assertEqual(matches_to_teams(payload),
    ["Chelsea","Manchester United","Tottenham Hotspur"])
  idx={namekey("Manchester United"):[("club1","Manchester United")],
       namekey("Manchester City"):[("club2","Manchester City")]}
  self.assertEqual(match_club("Manchester United",idx),
                   ("club1","Manchester United"))
  self.assertIsNone(match_club("Man United",idx))
  idx[namekey("Manchester United")].append(("collision","Manchester United"))
  self.assertIsNone(match_club("Manchester United",idx))
 def test_additional_countries_are_not_cup_groups(self):
  # Same immutable source, broader verified country coverage.
  self.assertEqual(len(LEAGUES),34)
  for code,country in (
      ("sco.1","Scotland"),("nl.1","Netherlands"),
      ("pt.1","Portugal"),("tr.1","Turkey"),
      ("mx.1","Mexico"),("au.1","Australia"),
      ("ar.1","Argentina"),("at.2","Austria")):
   self.assertEqual(LEAGUES[code][0],country)
  self.assertEqual(LEAGUES["ru.2"][1],2)
  self.assertEqual(LEAGUES["ch.2"][1],2)
  self.assertFalse(any(".cup" in code or "uefa" in code for code in LEAGUES))
 def test_invalid_source_payload_is_blocked(self):
  with self.assertRaises(ValueError):matches_to_teams({"teams":[]})

if __name__=="__main__":unittest.main()

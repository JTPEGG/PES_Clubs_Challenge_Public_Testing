"""Stop unknown league, ambiguous club aliases, and historic rule drift."""
import unittest
from world_historical_competition_registry import canonical,cup_group,YEARS
from world_historical_movement_rules import source_rules,EDITION_YEARS

class HistoricalFootballWorldTests(unittest.TestCase):
 def test_all_22_editions_are_independent_of_fc25_gap(self):
  self.assertEqual(YEARS,set(EDITION_YEARS))
  self.assertEqual(len(YEARS),22)
  self.assertNotIn(2025,YEARS)
 def test_banal_club_suffix_and_name_aliases_are_candidates_only(self):
  self.assertEqual(canonical("Arsenal FC"),canonical("Arsenal"))
  self.assertEqual(canonical("AFC Bournemouth"),canonical("Bournemouth"))
  self.assertEqual(canonical("West Bromwich Albion"),canonical("West Brom"))
  self.assertNotEqual(canonical("Liverpool"),canonical("Liverpool FC Uruguay"))
  self.assertNotEqual(canonical("Manchester United"),canonical("Manchester City"))
 def test_all_external_source_memberships_have_domestic_foreign_keys(self):
  from world_historical_competition_registry import SCHEMA
  self.assertIn("CREATE TABLE sourced_domestic_league_clubs(",SCHEMA)
  self.assertIn("REFERENCES competition_seasons(code)",SCHEMA)
  self.assertIn("independent_fixture_membership",SCHEMA)
 def test_early_multi_country_aliases_are_only_identity_review_keys(self):
  from world_historical_competition_registry import canonical
  self.assertEqual(canonical("AFC Ajax"),canonical("Ajax"))
  self.assertEqual(canonical("Getafe CF"),canonical("Getafe"))
  self.assertEqual(canonical("Valencia CF"),canonical("Valencia"))
  self.assertEqual(canonical("FC Hansa Rostock"),canonical("Hansa Rostock"))
  self.assertEqual(canonical("AC Siena"),canonical("Siena"))
  self.assertNotEqual(canonical("Ajax Cape Town"),canonical("Ajax"))
 def test_scoped_named_source_group_only_links_with_full_dated_fixture_evidence(self):
  from collections import Counter
  from world_historical_competition_registry import curated_group_match
  comps={
   "2026:us.mls":(2026,"United States / Canada",1,"Major League Soccer","source","sha"),
   "2026:ar.1":(2026,"Argentina",1,"Primera División","source","sha"),
   "2022:en.3":(2022,"England",3,"League One","source","sha"),
  }
  sizes={"2026:us.mls":30,"2026:ar.1":30,"2022:en.3":24}
  self.assertEqual(curated_group_match(2026,"Major League Soccer",30,
       Counter({"2026:us.mls":6}),comps,sizes),"2026:us.mls")
  self.assertEqual(curated_group_match(2026,"Liga Profesional de Fútbol",30,
       Counter({"2026:ar.1":5}),comps,sizes),"2026:ar.1")
  self.assertEqual(curated_group_match(2022,"English League One",24,
       Counter({"2022:en.3":3}),comps,sizes),"2022:en.3")
  self.assertIsNone(curated_group_match(2027,"MLS",30,
       Counter({"2026:us.mls":30}),comps,sizes))
  self.assertIsNone(curated_group_match(2026,"Premier League",30,
       Counter({"2026:us.mls":30}),comps,sizes))
  self.assertIsNone(curated_group_match(2026,"Major League Soccer",29,
       Counter({"2026:us.mls":28}),comps,sizes))
  self.assertIsNone(curated_group_match(2026,"Major League Soccer",30,
       Counter({"2026:us.mls":1}),comps,sizes))
  self.assertIsNone(curated_group_match(2026,"Major League Soccer",30,
       Counter({"2026:us.mls":10,"2026:ar.1":1}),comps,sizes))
  self.assertIsNone(curated_group_match(2026,"CONMEBOL Libertadores",30,
       Counter({"2026:ar.1":30}),comps,sizes))
 def test_official_FA_allocation_stays_separate_from_game_squads(self):
  from world_historical_competition_registry import SCHEMA
  self.assertIn("CREATE TABLE official_fa_nls_allocations(",SCHEMA)
  self.assertIn("fa_official_allocation_crosschecked",SCHEMA)
  self.assertIn("REFERENCES competition_seasons(code)",SCHEMA)
  self.assertIn("pinned_third_party_snapshot_review",SCHEMA)
 def test_continental_cup_never_counts_as_domestic_division(self):
  self.assertTrue(cup_group("CONMEBOL Libertadores"))
  self.assertTrue(cup_group("CONMEBOL Sudamericana"))
  self.assertFalse(cup_group("Argentinian Primera División"))
 def test_historical_championship_playoff_expansion(self):
  old=next(r for r in source_rules(2026) if r["lower"]=="ENG:CH")
  new=next(r for r in source_rules(2027) if r["lower"]=="ENG:CH")
  self.assertIn("3rd-6th",old["playoff_entrants"])
  self.assertIn("3rd-8th",new["playoff_entrants"])
  self.assertEqual(new["direct_relegations"],3)
 def test_national_league_six_club_expansion_in_2017_18(self):
  old=next(r for r in source_rules(2017) if r["lower"]=="ENG:NL")
  new=next(r for r in source_rules(2018) if r["lower"]=="ENG:NL")
  self.assertIn("2nd-5th",old["playoff_entrants"])
  self.assertIn("2nd-7th",new["playoff_entrants"])
 def test_germany_3liga_did_not_exist_in_2007_08(self):
  self.assertFalse(any(r["lower"]=="GER:D3" for r in source_rules(2008)))
  self.assertTrue(any(r["lower"]=="GER:D3" for r in source_rules(2009)))
  old=next(r for r in source_rules(2008) if r["lower"]=="GER:BL2")
  new=next(r for r in source_rules(2009) if r["lower"]=="GER:BL2")
  self.assertEqual((old["direct_promotions"],old["playoff_promotions"]),(3,0))
  self.assertEqual((new["direct_promotions"],new["playoff_promotions"]),(2,1))
 def test_no_invention_of_missing_seasons(self):
  with self.assertRaises(ValueError):source_rules(2025)

if __name__=="__main__":
 unittest.main()

"""Test future FC27 season-end candidate resolver without touching careers."""
import unittest
from world_fc27_season_end_logic import (
    BoundaryRules, resolve_boundary, mls_postseason_qualifiers
)

def rows(prefix,n):return tuple(f"{prefix}{i:02d}" for i in range(1,n+1))
TOP=rows("upper",20);LOW=rows("lower",24)

class FC27SeasonEndPrototypeTests(unittest.TestCase):
    def simulate(self,rule,**kw):
        return resolve_boundary(
          rule,upper_ranked=TOP,lower_ranked=LOW,
          eligible_lower_clubs=frozenset(LOW),
          eligible_upper_clubs=frozenset(TOP),
          certified_game_rosters=True,actual_season_standings=True,
          upper_expected_club_count=20,lower_expected_club_count=24,**kw)
    def test_three_direct_exchanges_preserve_division_sizes_and_IDs(self):
        rule=BoundaryRules("2027:en.2","2027:en.1",3,0,3)
        outcome=self.simulate(rule)
        self.assertEqual(outcome.promoted,LOW[:3])
        self.assertEqual(outcome.relegated,TOP[-3:])
        self.assertEqual(len(outcome.upper_after),20)
        self.assertEqual(len(outcome.lower_after),24)
        self.assertEqual(set(outcome.upper_after)|set(outcome.lower_after),set(TOP)|set(LOW))
    def test_serie_b_gameplay_always_playoff_winner(self):
        rule=BoundaryRules("2027:it.2","2027:it.1",2,1,3)
        with self.assertRaisesRegex(ValueError,"Explicit result"):
            self.simulate(rule)
        result=self.simulate(rule,playoff_promoted=(LOW[4],))
        self.assertEqual(result.promoted,(LOW[0],LOW[1],LOW[4]))
        self.assertEqual(result.relegated,TOP[-3:])
        with self.assertRaisesRegex(ValueError,"Play-off promotion winner"):
            self.simulate(rule,playoff_promoted=(LOW[0],))
    def test_france_optional_interdivision_result_not_fabricated(self):
        rule=BoundaryRules("2027:fr.2","2027:fr.1",2,0,2,1)
        with self.assertRaisesRegex(ValueError,"interdivision play-off winner"):
            self.simulate(rule)
        stayed=self.simulate(rule,interdivision_winner=TOP[-3])
        self.assertFalse(stayed.played_conditional_exchange)
        self.assertEqual(len(stayed.promoted),2)
        won=self.simulate(rule,interdivision_winner=LOW[2])
        self.assertTrue(won.played_conditional_exchange)
        self.assertEqual(len(won.promoted),3)
        self.assertEqual(won.relegated,TOP[-3:])
        with self.assertRaisesRegex(ValueError,"must be one of the two"):
            self.simulate(rule,interdivision_winner=LOW[-1])
    def test_reserve_sides_are_skipped_not_promoted(self):
        rule=BoundaryRules("2027:nl.2","2027:nl.1",2,0,2,1)
        eligible=frozenset(LOW[2:])
        outcome=resolve_boundary(
          rule,upper_ranked=TOP,lower_ranked=LOW,
          eligible_lower_clubs=eligible,
          eligible_upper_clubs=frozenset(TOP),
          certified_game_rosters=True,actual_season_standings=True,
          interdivision_winner=TOP[-3])
        self.assertEqual(outcome.promoted,(LOW[2],LOW[3]))
    def test_never_promote_uncertified_or_duplicate_clubs(self):
        rule=BoundaryRules("2027:en.2","2027:en.1",3,0,3)
        with self.assertRaisesRegex(ValueError,"registered squads"):
            resolve_boundary(rule,upper_ranked=TOP,lower_ranked=LOW,
                             eligible_lower_clubs=frozenset(LOW),
                             eligible_upper_clubs=frozenset(TOP),
                             actual_season_standings=True)
        with self.assertRaisesRegex(ValueError,"duplicate club"):
            resolve_boundary(rule,upper_ranked=TOP,lower_ranked=list(LOW[:-1])+[LOW[0]],
                             eligible_lower_clubs=frozenset(LOW),
                             eligible_upper_clubs=frozenset(TOP),
                             certified_game_rosters=True,actual_season_standings=True)
    def test_mls_2026_wildcard_qualification_requires_real_standings(self):
        east=rows("E",15);west=rows("W",15)
        with self.assertRaisesRegex(ValueError,"blocked"):
            mls_postseason_qualifiers(east,west)
        q=mls_postseason_qualifiers(east,west,season_match_results_certified=True)
        self.assertEqual(q.eastern_direct,east[:7])
        self.assertEqual(q.western_direct,west[:7])
        self.assertEqual(q.eastern_wild_card,(east[7],east[8]))
        self.assertEqual(q.western_wild_card,(west[7],west[8]))
        with self.assertRaisesRegex(ValueError,"both conferences"):
            mls_postseason_qualifiers(east,list(west[:-1])+[east[0]],
                                     season_match_results_certified=True)
if __name__=="__main__":
    unittest.main()

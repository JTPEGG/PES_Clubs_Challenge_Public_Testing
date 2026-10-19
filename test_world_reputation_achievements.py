"""Pure gameplay checks for non-stacking next-season trophy/Europe opportunities."""
import unittest

from world_reputation_achievements import (
    MODEL_VERSION,DOMESTIC_CUPS,EUROPEAN_ACCESS,EUROPEAN_TROPHIES,
    TOTAL_BONUS_CAP,calculate_opportunity_bonuses,
)
from world_reputation_progression import preview_progression


class OpportunityBonusTests(unittest.TestCase):
    def test_01_named_domestic_cups_have_distinct_strength(self):
        fa=calculate_opportunity_bonuses(domestic_cup="fa_cup")
        league=calculate_opportunity_bonuses(domestic_cup="league_cup")
        self.assertEqual(fa["temporary_bonus"],3)
        self.assertEqual(league["temporary_bonus"],2)
        self.assertEqual(calculate_opportunity_bonuses(legacy_cup_won=True)["cup_bonus"],1)
        with self.assertRaisesRegex(ValueError,"cannot both"):
            calculate_opportunity_bonuses(legacy_cup_won=True,domestic_cup="fa_cup")

    def test_02_european_opportunities_and_trophies(self):
        for tier,expected in (("champions_league",5),("europa_league",3),
                              ("conference_league",2)):
            self.assertEqual(calculate_opportunity_bonuses(
                continental_competition=tier)["continental_bonus"],expected)
        self.assertEqual(calculate_opportunity_bonuses(
            continental_trophy="champions_league")["continental_trophy_bonus"],4)
        self.assertEqual(calculate_opportunity_bonuses(
            continental_trophy="europa_league")["continental_trophy_bonus"],3)
        self.assertEqual(calculate_opportunity_bonuses(
            continental_trophy="conference_league")["continental_trophy_bonus"],2)

    def test_03_no_double_count_of_mixed_trophies_and_entry(self):
        award=calculate_opportunity_bonuses(
            domestic_cup="fa_cup",
            continental_competition="champions_league",
            continental_trophy="champions_league")
        self.assertEqual(award["raw_bonus"],12)
        self.assertEqual(award["temporary_bonus"],TOTAL_BONUS_CAP)
        self.assertEqual(award["overlap_cap"],4)
        self.assertEqual(award["cup_bonus"],3)
        self.assertEqual(award["continental_bonus"],5)
        self.assertEqual(award["continental_trophy_bonus"],4)

    def test_04_hull_third_with_champions_league_has_real_bonus(self):
        projected=preview_progression(
            old_score=69,old_competition="ENG1",next_competition="ENG1",
            old_form=-1,league_position=3,league_size=20,
            continental_competition="champions_league")
        self.assertEqual(projected["form_delta"],3)
        self.assertEqual(projected["underlying_appeal"],72)
        self.assertEqual(projected["temporary_bonus"],5)
        self.assertEqual(projected["projected"],77)
        # Important: current top-16 calculation gives 69 -> 72 before Europe.
        # The previous conversational 69 -> 73 was illustrative, not the algorithm.

    def test_05_european_bonus_expires_and_never_accumulates(self):
        first=preview_progression(
            old_score=69,old_competition="ENG1",next_competition="ENG1",
            old_form=-1,league_position=3,league_size=20,
            continental_competition="champions_league")
        no_qualification=preview_progression(
            old_score=first["projected"],old_underlying=first["underlying_appeal"],
            old_temporary_bonus=first["temporary_bonus"],old_form=first["new_form"],
            old_competition="ENG1",next_competition="ENG1",
            league_position=10,league_size=20)
        second_qualification=preview_progression(
            old_score=first["projected"],old_underlying=first["underlying_appeal"],
            old_temporary_bonus=first["temporary_bonus"],old_form=first["new_form"],
            old_competition="ENG1",next_competition="ENG1",
            league_position=10,league_size=20,
            continental_competition="champions_league")
        self.assertEqual(no_qualification["underlying_appeal"],70)
        self.assertEqual(no_qualification["projected"],70)
        self.assertEqual(second_qualification["underlying_appeal"],70)
        self.assertEqual(second_qualification["projected"],75)
        self.assertEqual(second_qualification["temporary_bonus"],5)

    def test_06_unknown_future_results_do_not_imply_qualification(self):
        third=preview_progression(
            old_score=69,old_competition="ENG1",next_competition="ENG1",
            old_form=-1,league_position=3,league_size=20)
        self.assertEqual(third["continental_bonus"],0)
        self.assertEqual(third["projected"],72)
        with self.assertRaises(ValueError):
            preview_progression(old_score=69,old_competition="ENG1",
                next_competition="ENG1",old_form=-1,league_position=3,
                league_size=20,continental_competition="unconfirmed_europe")

    def test_07_domestic_cup_not_counted_again_in_form(self):
        fa=preview_progression(
            old_score=69,old_competition="ENG1",next_competition="ENG1",
            old_form=-1,league_position=10,league_size=20,domestic_cup="fa_cup")
        league=preview_progression(
            old_score=69,old_competition="ENG1",next_competition="ENG1",
            old_form=-1,league_position=10,league_size=20,domestic_cup="league_cup")
        self.assertEqual(fa["form_delta"],1)
        self.assertEqual(fa["cup_bonus"],3)
        self.assertEqual(fa["projected"],73)
        self.assertEqual(league["cup_bonus"],2)
        self.assertEqual(league["projected"],72)


if __name__=="__main__":
    unittest.main()

"""Protect organic FC27 club decisions from reintroducing forced deals."""
import unittest

from world_ai_tactics import FORMATION_STARTERS
from world_fc27_market_choices import (
    select_recruiting_club,select_tactical_family,choose_development_focus,
    pursue_transfer,disruption_sale_premium)
from world_valuation import model_value,fc27_game_reference_value
from scripts.fc27_warehouse_world_bridge import explicit_source_alternative_positions

class AutonomousChoicesTests(unittest.TestCase):
    def test_a_market_pulse_picks_one_club_without_hard_club_shortlist(self):
        desks={club:48 for club in range(1,660)}
        first=select_recruiting_club(desks,draw=0)
        last=select_recruiting_club(desks,draw=999999)
        self.assertEqual(first,1)
        self.assertEqual(last,659)
        self.assertIsNone(select_recruiting_club({},draw=0))

    def test_voluntary_bidding_allows_real_market_inactivity(self):
        profile={"simulated_manager_financial_discipline":50}
        self.assertTrue(pursue_transfer(priority=80,profile=profile,draw=0))
        self.assertFalse(pursue_transfer(priority=80,profile=profile,draw=999))
        self.assertFalse(pursue_transfer(priority=0,profile=profile,draw=900))
        with self.assertRaises(ValueError):
            pursue_transfer(priority=0,profile=profile,draw=1000)

    def test_development_may_be_a_purpose_without_a_youth_quota(self):
        profile={"ambition_level":70,"simulated_manager_risk":65,
                 "financial_pressure_index":20}
        self.assertTrue(choose_development_focus(profile=profile,draw=0))
        self.assertFalse(choose_development_focus(profile=profile,draw=999))

    def test_keeper_and_wide_midfield_are_in_real_tactical_target_pool(self):
        needs={key:0 for key in ("GK","DEF","MID","FWD")}
        formation=FORMATION_STARTERS["4-4-2"]
        self.assertEqual(select_tactical_family(family_needs=needs,
            starting_roles=formation,draw=0),"GK")
        self.assertEqual(select_tactical_family(family_needs=needs,
            starting_roles=formation,draw=999999),"FWD")
        self.assertIn("LM",formation)
        self.assertIn("RM",formation)

    def test_no_punishment_for_surplus_sale_but_serious_lineup_damage_costs(self):
        ordinary={"valid":True,"formation_lineup_loss":0,
            "after_depth":4,"before_depth":5,"tactically_required":True,
            "starter_rating_drop":0,"protected_rotation":False,
            "below_target_cover":False}
        damage={**ordinary,"formation_lineup_loss":1,
            "after_depth":0,"before_depth":1,
            "starter_rating_drop":9,"protected_rotation":True,
            "below_target_cover":True}
        self.assertEqual(disruption_sale_premium(ordinary),0)
        self.assertGreater(disruption_sale_premium(damage),.4)
        self.assertLess(disruption_sale_premium(damage,
            seller_pressure=92,player_wants_exit=True),
            disruption_sale_premium(damage))
        self.assertLess(disruption_sale_premium(damage),1)

    def test_fc27_ability_and_source_wage_fix_extremely_low_elite_values(self):
        old=model_value(84,26,"DMF")
        modern=fc27_game_reference_value(
            baseline=old,overall=84,weekly_wage=110000)
        self.assertGreater(modern,old*2)
        self.assertGreaterEqual(fc27_game_reference_value(
            baseline=old,overall=84,weekly_wage=210000),modern)
        self.assertEqual(model_value(84,26,"DMF"),old)
        with self.assertRaises(ValueError):
            fc27_game_reference_value(
                baseline=old,overall=84,weekly_wage=-1)

    def test_only_real_source_alternatives_count_as_cover(self):
        self.assertEqual(explicit_source_alternative_positions(
            '["LMF","RMF","CF"]'),["CF","LMF","RMF"])
        self.assertEqual(explicit_source_alternative_positions(
            '[{"position":"CB"},{"position":"LB"}]'),["CB","LB"])
        self.assertEqual(explicit_source_alternative_positions("not JSON"),[])
        self.assertEqual(explicit_source_alternative_positions("null"),[])

if __name__=="__main__":unittest.main()

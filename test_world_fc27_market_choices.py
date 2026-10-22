"""Protect organic FC27 club decisions from reintroducing forced deals."""
import unittest

from world_ai_tactics import FORMATION_STARTERS
from world_fc27_market_choices import (
    select_recruiting_club,select_tactical_family,choose_development_focus,
    pursue_transfer,disruption_sale_premium,player_market_opportunity)
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

    def test_seller_retains_credible_bench_quality_without_absolute_veto(self):
        good={"valid":True,"formation_lineup_loss":0,
              "after_depth":5,"before_depth":6,
              "tactically_required":True,"starter_rating_drop":0,
              "backup_quality_drop":0,"rotation_quality_drop":0,
              "protected_rotation":False,"below_target_cover":False}
        thin={**good,"before_depth":3,"after_depth":2,
              "below_target_cover":True,
              "backup_quality_drop":8,"rotation_quality_drop":6}
        stable=disruption_sale_premium(good)
        urgent=disruption_sale_premium(thin)
        self.assertEqual(stable,0)
        self.assertGreater(urgent,.2)
        self.assertLess(urgent,.78)
        self.assertGreater(urgent,disruption_sale_premium(
            thin,seller_pressure=88,player_wants_exit=True))

    def test_career_fit_not_passport_or_cross_border_quota(self):
        args={"overall":84,"sporting_upgrade":6,
              "prospect":False,"buyer_ambition":86}
        step_up=player_market_opportunity(
            buyer_appeal=92,seller_appeal=78,**args)
        low_appeal=player_market_opportunity(
            buyer_appeal=57,seller_appeal=88,**args)
        self.assertGreater(step_up,low_appeal)
        self.assertGreater(player_market_opportunity(
            buyer_appeal=78,seller_appeal=75,**args),
            player_market_opportunity(
                buyer_appeal=78,seller_appeal=75,
                **{**args,"sporting_upgrade":0}))
        self.assertGreater(player_market_opportunity(
            buyer_appeal=60,seller_appeal=90,
            overall=70,sporting_upgrade=0,prospect=True,
            buyer_ambition=86),low_appeal-15)
        with self.assertRaises(ValueError):
            player_market_opportunity(buyer_appeal=110,
                seller_appeal=78,**args)

    def test_stronger_tactical_need_dominates_generic_formation_weight(self):
        formation={"GK":1,"CB":2,"LB":1,"RB":1,"CM":2,
                   "LW":1,"RW":1,"ST":2}
        ordinary={f:0 for f in ("GK","DEF","MID","FWD")}
        weak_defense={**ordinary,"DEF":80}
        counts=lambda needs:sum(select_tactical_family(
            family_needs=needs,starting_roles=formation,draw=i)
            =="DEF" for i in range(5000,1000000,5000))
        self.assertGreater(counts(weak_defense),counts(ordinary))

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

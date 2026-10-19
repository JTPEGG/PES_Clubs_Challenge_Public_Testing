"""Regression tests for the isolated development player/agent decision engine."""
import unittest
from world_player_decisions import (
    ROLES, SELECTABLE_ROLES, PLAYER_CURRENT_ROLES, ROLE_LABELS,
    canonical_role, role_satisfies, evaluate_player_choice_v2,
    agent_minimum_wage_v2,
)

BASE = dict(
    buyer_tier=1, seller_tier=1,
    buyer_score=75, seller_score=80,
    buyer_prestige=55, seller_prestige=85,
    overall=90, age=27,
    current_wage=150_000, current_role="key_player",
    transfer_listed=False, renewal_status="renewal_offered",
    buyer_europe="none", seller_europe="champions_league",
    offered_wage=15_000, role_promise="key_player",
)

class PlayerDecisionTests(unittest.TestCase):
    def choice(self, **updates):
        data = {**BASE, **updates}
        return evaluate_player_choice_v2(**data)

    def test_clean_squad_hierarchy(self):
        self.assertNotIn("important", ROLES)
        self.assertNotIn("important", SELECTABLE_ROLES)
        self.assertNotIn("important", PLAYER_CURRENT_ROLES)
        self.assertNotIn("important", ROLE_LABELS)
        self.assertTrue(role_satisfies("key_player", "regular_starter"))
        self.assertFalse(role_satisfies("regular_starter", "key_player"))
        self.assertTrue(role_satisfies("regular_starter", "rotation"))
        with self.assertRaises(ValueError):
            self.choice(role_promise="important")

    def test_contract_top_flight_starter_declines_routine_permanent_drop(self):
        # This modelled player is rated just 79, not 88+ elite. Earlier
        # rules incorrectly allowed contracted top-flight starters to join
        # Championship sides on ordinary wages and regular-starter promises.
        scenario=dict(overall=79,age=27,current_role="regular_starter",
            buyer_tier=2,seller_tier=1,
            buyer_score=73,seller_score=79,
            buyer_prestige=65,seller_prestige=80,
            buyer_europe="none",seller_europe="none",
            current_wage=20_000,transfer_listed=False,
            renewal_status="renewal_offered",
            offered_wage=None,role_promise="regular_starter")
        result=self.choice(**scenario)
        self.assertEqual(result["decision"],"uninterested")
        self.assertFalse(result["can_negotiate"])
        richer=self.choice(**{**scenario,"offered_wage":75_000,
            "role_promise":"key_player"})
        self.assertEqual(richer["decision"],"uninterested")

    def test_top_flight_young_rotation_player_not_sold_as_routine_upgrade(self):
        result=self.choice(overall=78,age=23,current_role="rotation",
            buyer_tier=2,seller_tier=1,
            buyer_score=73,seller_score=79,
            buyer_prestige=65,seller_prestige=80,
            buyer_europe="none",seller_europe="none",
            current_wage=14_000,transfer_listed=False,
            renewal_status="renewal_offered",
            offered_wage=40_000,role_promise="regular_starter")
        self.assertEqual(result["decision"],"uninterested")

    def test_even_listed_prime_age_top_flight_star_is_not_a_routine_permanent_drop(self):
        result=self.choice(overall=79,age=25,current_role="rotation",
            buyer_tier=2,seller_tier=1,buyer_score=73,seller_score=79,
            buyer_prestige=65,seller_prestige=80,
            buyer_europe="none",seller_europe="none",
            transfer_listed=True,renewal_status="not_offered",
            current_wage=16_000,offered_wage=70_000,
            role_promise="key_player")
        self.assertEqual(result["decision"],"uninterested")

    def test_31_year_old_premier_league_star_does_not_accept_modest_championship_move(self):
        # Caught by the 20-window QA: a high-rated experienced top-flight
        # player was moving to a lower division for an ordinary wage offer.
        result=self.choice(overall=82,age=31,current_role="fringe",
            buyer_tier=2,seller_tier=1,buyer_score=67,seller_score=84,
            buyer_prestige=56,seller_prestige=89,
            buyer_europe="none",seller_europe="champions_league",
            transfer_listed=True,renewal_status="not_offered",
            current_wage=12_000,offered_wage=20_000,
            role_promise="key_player")
        self.assertEqual(result["decision"],"uninterested")

    def test_older_listed_premier_league_fringe_requires_large_wage_uplift(self):
        scenario=dict(overall=80,age=34,current_role="fringe",
            buyer_tier=2,seller_tier=1,buyer_score=73,seller_score=79,
            buyer_prestige=65,seller_prestige=80,
            buyer_europe="none",seller_europe="none",
            transfer_listed=True,renewal_status="not_offered",
            current_wage=20_000,offered_wage=None,
            role_promise="regular_starter")
        choice=self.choice(**scenario)
        self.assertTrue(choice["can_negotiate"])
        self.assertGreaterEqual(choice["minimum_wage"],35_000)
        too_low=self.choice(**{**scenario,"offered_wage":24_000})
        self.assertEqual(too_low["decision"],"needs_assurances")

    def test_elite_arsenal_style_regular_refuses_no_europe(self):
        result = self.choice()
        self.assertEqual(result["decision"], "uninterested")
        self.assertFalse(result["can_negotiate"])
        self.assertIsNone(agent_minimum_wage_v2(choice=result))

    def test_money_cannot_buy_out_elite_european_refusal(self):
        result = self.choice(offered_wage=500_000)
        self.assertEqual(result["decision"], "uninterested")

    def test_unknown_contract_and_wages_do_not_become_facts(self):
        result = self.choice(current_wage=None, current_role="unknown",
                             transfer_listed=None, renewal_status="unknown",
                             seller_europe="unknown", buyer_europe="unknown")
        self.assertEqual(result["decision"], "review")
        self.assertFalse(result["can_negotiate"])
        self.assertIsNone(result["current_wage"])

    def test_transfer_listed_elite_requires_key_status_and_major_wages(self):
        result = self.choice(transfer_listed=True, renewal_status="not_offered",
                             offered_wage=200_000, role_promise="regular_starter")
        self.assertIn(result["decision"], ("needs_assurances", "uninterested"))
        if result["decision"] == "needs_assurances":
            self.assertEqual(result["required_role"], "key_player")
            self.assertFalse(result["role_satisfied"])
            self.assertGreaterEqual(result["minimum_wage"], 150_000)

    def test_key_player_status_not_confused_with_wage_deficiency(self):
        # Two different wage scenarios; values are offers, not invented player wages.
        for offered in (62_500, 87_500):
            with self.subTest(offered=offered):
                result = self.choice(
                    overall=82, age=27, current_role="regular_starter",
                    current_wage=90_000, transfer_listed=True,
                    renewal_status="not_offered",
                    seller_europe="none", buyer_europe="none",
                    buyer_score=80, seller_score=80,
                    buyer_prestige=80, seller_prestige=80,
                    offered_wage=offered, role_promise="key_player",
                )
                self.assertEqual(result["decision"], "needs_assurances")
                self.assertEqual(result["issue"], "wage")
                self.assertTrue(result["role_satisfied"])

    def test_backup_goalkeeper_can_consider_lower_league_starting_role(self):
        # Fictional 65-rated, third-choice goalkeeper: a meaningful sporting
        # drop can be acceptable, but ONLY for a credible starting opportunity.
        scenario=dict(
            buyer_tier=3,seller_tier=1,buyer_score=51,seller_score=82,
            buyer_prestige=42,seller_prestige=81,overall=65,age=34,
            current_wage=3500,current_role="fringe",
            transfer_listed=False,renewal_status="renewal_offered",
            buyer_europe="none",seller_europe="none")
        first=self.choice(**scenario,offered_wage=None,role_promise="unspecified")
        self.assertEqual(first["decision"],"needs_assurances")
        self.assertTrue(first["can_negotiate"])
        self.assertEqual(first["required_role"],"regular_starter")
        self.assertIn("backup",first["reason"].lower())

        good=self.choice(**scenario,offered_wage=5500,
                         role_promise="regular_starter")
        self.assertEqual(good["decision"],"open_to_talks")
        self.assertTrue(good["role_satisfied"])

        missing_role=self.choice(**scenario,offered_wage=8000,
                                 role_promise="rotation")
        self.assertEqual(missing_role["decision"],"needs_assurances")
        self.assertEqual(missing_role["issue"],"role")

        low_pay=self.choice(**scenario,offered_wage=2000,
                            role_promise="regular_starter")
        self.assertEqual(low_pay["decision"],"uninterested")
        self.assertIn("below",low_pay["reason"])

    def test_backup_opportunity_does_not_make_any_downgrade_acceptable(self):
        base=dict(
            buyer_tier=3,seller_tier=1,buyer_score=51,seller_score=82,
            buyer_prestige=42,seller_prestige=81,overall=65,age=34,
            current_wage=3500,current_role="fringe",transfer_listed=False,
            renewal_status="renewal_offered",buyer_europe="none",
            seller_europe="none",offered_wage=8000,
            role_promise="regular_starter")
        # Established starters do NOT gain the overlooked-player exception.
        regular=self.choice(**{**base,"current_role":"regular_starter"})
        self.assertEqual(regular["decision"],"uninterested")
        # A too-large decline remains implausible even for a backup.
        distant=self.choice(**{**base,"buyer_score":30})
        self.assertEqual(distant["decision"],"uninterested")
        too_many_divisions=self.choice(**{**base,"buyer_tier":4,
                                           "age":24})
        self.assertEqual(too_many_divisions["decision"],"uninterested")
        # This is not a backdoor for a 90-rated player regardless of rank.
        exceptional=self.choice(**{**base,"overall":90})
        self.assertEqual(exceptional["decision"],"uninterested")

    def test_experienced_third_choice_can_consider_league_two_starts(self):
        context=dict(buyer_tier=4,seller_tier=1,
            buyer_score=40,seller_score=82,
            buyer_prestige=32,seller_prestige=81,
            overall=65,age=32,current_wage=3500,
            current_role="fringe",transfer_listed=False,
            renewal_status="renewal_offered",buyer_europe="none",
            seller_europe="none")
        interested=self.choice(**context,offered_wage=None,
                               role_promise="unspecified")
        self.assertTrue(interested["can_negotiate"])
        self.assertEqual(interested["required_role"],"regular_starter")
        regular=self.choice(**context,offered_wage=8000,
                            role_promise="regular_starter")
        self.assertEqual(regular["decision"],"open_to_talks")
        unpromised=self.choice(**context,offered_wage=8000,
                               role_promise="fringe")
        self.assertEqual(unpromised["decision"],"needs_assurances")
        poorly_paid=self.choice(**context,offered_wage=1500,
                                role_promise="regular_starter")
        self.assertEqual(poorly_paid["decision"],"uninterested")
        # First-team veterans and less experienced reserve players retain
        # stricter protections against very large sporting downgrades.
        established=self.choice(**{**context,"current_role":"regular_starter"},
                                offered_wage=8000,role_promise="regular_starter")
        self.assertEqual(established["decision"],"uninterested")
        extreme=self.choice(**{**context,"buyer_score":25},
                            offered_wage=8000,role_promise="regular_starter")
        self.assertEqual(extreme["decision"],"uninterested")

    def test_regular_starter_promise_reduces_backup_wage_premium_but_not_to_zero(self):
        base=dict(
            buyer_tier=2,seller_tier=1,buyer_score=60,seller_score=78,
            buyer_prestige=45,seller_prestige=75,overall=67,age=32,
            current_wage=8000,current_role="rotation",transfer_listed=True,
            renewal_status="not_offered",buyer_europe="none",
            seller_europe="none",offered_wage=None)
        bench=self.choice(**base,role_promise="rotation")
        starter=self.choice(**base,role_promise="regular_starter")
        self.assertLess(starter["minimum_wage"],bench["minimum_wage"])
        self.assertGreaterEqual(starter["minimum_wage"],7200)

    def test_salary_benchmark_scales_with_current_pay(self):
        low = self.choice(overall=80, current_role="rotation",
                          transfer_listed=True, renewal_status="not_offered",
                          seller_europe="none", buyer_europe="none",
                          offered_wage=None, current_wage=20_000)
        high = self.choice(overall=80, current_role="rotation",
                           transfer_listed=True, renewal_status="not_offered",
                           seller_europe="none", buyer_europe="none",
                           offered_wage=None, current_wage=100_000)
        self.assertIsNotNone(low["minimum_wage"])
        self.assertGreater(high["minimum_wage"], low["minimum_wage"])

    def test_prestige_and_sporting_are_distinct(self):
        r = self.choice(overall=80, current_role="rotation",
                        transfer_listed=True, renewal_status="not_offered",
                        seller_europe="none", buyer_europe="none",
                        offered_wage=None)
        self.assertEqual(r["sporting_gap"], -5)
        self.assertEqual(r["prestige_gap"], -30)

if __name__ == "__main__":
    unittest.main()

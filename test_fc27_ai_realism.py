"""Read-only multi-party transfer realism regression; all inputs fictional.

No actual footballer is claimed to choose a hypothetical offer.
"""
import unittest
from warehouse.fc27_ai_realism_audit import (
    run_synthetic_scenarios,recruitment_fit,scenario
)
from world_transfer_affordability import assess_transfer_affordability

class FC27AIRealismTests(unittest.TestCase):
    def test_all_sporting_financial_player_board_scenarios(self):
        report=run_synthetic_scenarios()
        self.assertGreaterEqual(report["scenario_count"],12)
        self.assertTrue(report["all_scenario_assertions_passed"])
        self.assertTrue(report["no_career_or_PES_mutation"])
        self.assertTrue(report["all_player_choices_are_hypothetical"])
        self.assertTrue(report["recruitment_fit_is_proposed_qa_rule_not_current_live_ai"])
    def test_wage_oversubscription_is_unaffordable_not_validation_crash(self):
        a=assess_transfer_affordability(transfer_budget=10_000_000,
          wage_headroom=-50_000,transfer_fee=0,offered_weekly_wage=0,
          signing_on_fee=0,agent_fee=0,other_upfront_fees=0,
          contract_years=1)
        self.assertEqual(a["decision"],"unaffordable")
        self.assertEqual(a["remaining_weekly_wage_headroom"],-50_000)
        with self.assertRaisesRegex(ValueError,"valid integer"):
            assess_transfer_affordability(transfer_budget=-1, wage_headroom=0)
    def test_ignored_source_prestige_is_not_reconstructed_from_strength(self):
        r=scenario(player={"seller_prestige":None,"buyer_prestige":None})
        self.assertEqual(r["outcome"],"needs_information")
        self.assertEqual(r["player"]["decision"],"review")
        self.assertIsNone(r["player"].get("minimum_wage"))
    def test_mls_and_regional_game_source_must_never_guess_unknowns(self):
        r=recruitment_fit(target_overall=None,position="GK",
                          existing_position_overalls=[80,75,70])
        self.assertEqual(r["decision"],"needs_information")
        r=recruitment_fit(target_overall=72,position="CMF",
                          existing_position_overalls=[])
        self.assertEqual(r["decision"],"priority_vacancy")
        r=recruitment_fit(target_overall=70,position="GK",
                          existing_position_overalls=[82,75,68],
                          explicit_replacement_needed=True)
        self.assertEqual(r["decision"],"priority_replacement")
    def test_any_country_top_flight_downgrade_is_league_neutral(self):
        r=scenario(player={
            "overall":80,"age":27,"seller_tier":1,"buyer_tier":2,
            "buyer_score":68,"seller_score":84,
            "buyer_prestige":57,"seller_prestige":83,
            "transfer_listed":True,"renewal_status":"not_offered",
            "offered_wage":300000
        })
        self.assertEqual(r["player"]["decision"],"uninterested")
        self.assertNotIn("Premier League",r["player"]["reason"])
        self.assertIn("top-flight",r["player"]["reason"])

    def test_contract_expiring_does_not_override_player_consent(self):
        r=scenario(
           player={"overall":90,"age":28,"buyer_score":46,"seller_score":92,
                   "buyer_prestige":40,"seller_prestige":90,
                   "current_role":"key_player","transfer_listed":False,
                   "renewal_status":"renewal_offered",
                   "seller_europe":"champions_league","buyer_europe":"none"},
           seller={"contract_years":1,"offer_fee":250000000,
                   "transfer_listed":False,"player_wants_exit":False,
                   "seller_stance":"retain"},
           finances={"transfer_budget":500000000})
        self.assertEqual(r["player"]["decision"],"uninterested")
        self.assertEqual(r["outcome"],"blocked")

if __name__=="__main__":
    unittest.main()

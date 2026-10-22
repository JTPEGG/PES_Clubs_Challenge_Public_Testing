"""Independent regression for FC27 market choices versus protected older rules."""
import unittest
from world_ai_bidding import determine_offer,position_family
from world_selling_club import evaluate_selling_club

BASE={"career_id":"tactic-model","player_id":31,"club_id":5,
      "valuation":10_000_000,"available_budget":55_000_000,
      "need_score":80,"eligible_clubs":1}

class MarketDecisionTests(unittest.TestCase):
    def test_tactical_wide_midfield_is_not_conflated_with_forward(self):
        self.assertEqual(position_family("LM"),"MID")
        self.assertEqual(position_family("RMF"),"MID")
        self.assertEqual(position_family("LWF"),"FWD")

    def test_senior_urgent_buyers_can_pay_more_but_not_without_funds(self):
        basic=determine_offer(**BASE)
        flexible=determine_offer(**BASE,strategic_ceiling_uplift=.35)
        self.assertEqual(basic["fee"],flexible["fee"])
        self.assertGreater(flexible["maximum_sensible_fee"],
                           basic["maximum_sensible_fee"])
        with self.assertRaises(ValueError):
            determine_offer(**BASE,strategic_ceiling_uplift=.90)

    def test_old_buyers_keep_exact_unchanged_policy_by_default(self):
        old=determine_offer(**BASE)
        current=determine_offer(**BASE,strategic_ceiling_uplift=0.0)
        self.assertEqual(old,current)

    def test_retained_starter_always_has_price_in_fc27_autonomous_market(self):
        inputs={"market_value":12_000_000,"offer_fee":35_000_000,
            "contract_years":4,"squad_role":"key_player",
            "transfer_listed":False,"financial_state":"stable",
            "replacement":"difficult","seller_stance":"retain",
            "player_wants_exit":False}
        quote=evaluate_selling_club(**inputs,
            autonomous_market_reassessment=True)
        self.assertEqual(quote["decision"],"accept")
        self.assertLess(quote["asking_price"],inputs["offer_fee"])
        # Existing/manual cases remain allowed to explicitly retain a player.
        protected=evaluate_selling_club(**inputs)
        self.assertEqual(protected["decision"],"reject")

if __name__=="__main__":
    unittest.main()

"""Projected replacement options are SCOUTING candidates, not requirements."""
import unittest
from world_ai_replacement_outlook import assess_future_replacement
from world_selling_club import evaluate_selling_club

SELL=dict(valid=True,sporting_risk=38,requires_recruitment=True,
    replacement_priority="urgent",protected_rotation=True)
CONTEXT=dict(market_value=15_000_000,offer_fee=20_000_000,
    contract_years=4,squad_role="key_player",transfer_listed=False,
    financial_state="stable",replacement="difficult",
    seller_stance="retain",player_wants_exit=False)

class AIForwardReplacementTests(unittest.TestCase):
    def test_market_prospects_change_risk_but_never_become_signings(self):
        low=assess_future_replacement(sale=SELL,departing_overall=86,
                                      market_options=[71,73])
        high=assess_future_replacement(sale=SELL,departing_overall=86,
                                       market_options=[79,80,84,85,87,89])
        self.assertGreater(low["strategic_sale_risk_weight"],
                           high["strategic_sale_risk_weight"])
        self.assertEqual(high["forecast_replacement_outlook"],"available")
        self.assertEqual(low["forecast_replacement_outlook"],"difficult")
        for x in (low,high):
            self.assertTrue(x["sale_can_proceed_before_replacement"])
            self.assertEqual(x["replacements_assumed_signed"],0)
            self.assertEqual(x["post_sale_recruitment_priority"],"urgent")
    def test_even_no_market_options_is_risk_not_veto(self):
        x=assess_future_replacement(sale=SELL,departing_overall=90,market_options=[])
        self.assertTrue(x["sale_can_proceed_before_replacement"])
        self.assertGreater(x["strategic_sale_risk_weight"],0)
        self.assertEqual(x["replacements_assumed_signed"],0)
    def test_autonomous_retained_key_player_can_negotiate_before_replacement(self):
        low=evaluate_selling_club(**CONTEXT,autonomous_market_reassessment=True)
        self.assertEqual(low["decision"],"negotiate")
        self.assertGreater(low["asking_price"],CONTEXT["offer_fee"])
        huge=evaluate_selling_club(**{**CONTEXT,"offer_fee":95_000_000},
                                  autonomous_market_reassessment=True)
        self.assertEqual(huge["decision"],"accept")
        self.assertTrue(huge["autonomous_market_reassessment"])
        self.assertGreater(huge["asking_price"],CONTEXT["market_value"])
    def test_only_an_exceptional_ai_key_player_reaches_extreme_pricing(self):
        extreme=evaluate_selling_club(**CONTEXT,
            autonomous_market_reassessment=True)
        ordinary={**CONTEXT,"squad_role":"regular_starter",
                  "seller_stance":"neutral","contract_years":3,
                  "replacement":"available"}
        normal=evaluate_selling_club(**ordinary,
            autonomous_market_reassessment=True)
        self.assertGreater(extreme["asking_price"],normal["asking_price"])
        self.assertLess(extreme["asking_price"],CONTEXT["market_value"]*2.20)
        self.assertLess(normal["asking_price"],CONTEXT["market_value"]*1.55)
        self.assertEqual(normal["decision"],"negotiate" if
            ordinary["offer_fee"]<normal["asking_price"] else "accept")
        self.assertEqual(evaluate_selling_club(**{
            **ordinary,"offer_fee":normal["asking_price"]},
            autonomous_market_reassessment=True)["decision"],"accept")

    def test_existing_user_recorded_retain_policy_is_not_changed(self):
        old=evaluate_selling_club(**CONTEXT)
        self.assertEqual(old["decision"],"reject")
        self.assertIsNone(old["asking_price"])
        explicit=evaluate_selling_club(**CONTEXT,autonomous_market_reassessment=False)
        self.assertEqual(old,explicit)
    def test_financial_distress_and_exit_make_high_offer_easier(self):
        stable=evaluate_selling_club(**CONTEXT,autonomous_market_reassessment=True)
        pressured=evaluate_selling_club(**{**CONTEXT,
            "financial_state":"cash_needed","player_wants_exit":True},
            autonomous_market_reassessment=True)
        self.assertLess(pressured["asking_price"],stable["asking_price"])
    def test_no_hard_annual_net_departure_quota(self):
        # Function's inputs have no arrivals/sales count at all; the
        # simulated club evaluates source squad impact and economic case.
        a=assess_future_replacement(sale=SELL,departing_overall=83,
                                    market_options=[84,82,81])
        self.assertNotIn("max_departures",a)
        self.assertNotIn("signed_replacements_required",a)
    def test_unverified_future_rating_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            assess_future_replacement(sale=SELL,departing_overall=86,
                                      market_options=[81,None])
        with self.assertRaises(ValueError):
            assess_future_replacement(sale={"valid":False},
                departing_overall=86,market_options=[])
        with self.assertRaises(ValueError):
            evaluate_selling_club(**CONTEXT,autonomous_market_reassessment="true")

if __name__=="__main__":unittest.main()

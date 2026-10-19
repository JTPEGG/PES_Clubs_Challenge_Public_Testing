"""Financial capacity, ambition and underinvestment: factual-vs-scenario safeguards."""
import unittest
from world_career_resources import (expectation_with_resources,
                                    review_underinvestment)

BASE=dict(squad_rank=18,league_size=20,division_tier=1,
          opening_unreserved_funds=45_000_000,
          division_median_transfer_budget=45_000_000)

class ResourceExpectationTests(unittest.TestCase):
    def assessment(self,**kw):
        return expectation_with_resources(**{**BASE,
          "ambition":"consolidation","investment_mandate":"none",
          "investment_pool":0,**kw})

    def test_squad_alone_is_not_an_ambition_target(self):
        r=self.assessment()
        self.assertEqual(r["strength_rank"],18)
        self.assertEqual(r["expected_rank"],18)
        self.assertEqual(r["financial_shift"],0)

    def test_same_squad_stronger_expectation_when_board_funds_improvement(self):
        plain=self.assessment()
        funded=self.assessment(investment_mandate="required",
                               investment_pool=35_000_000,ambition="continental")
        self.assertLess(funded["expected_rank"],plain["expected_rank"])
        self.assertGreater(funded["financial_shift"],0)
        self.assertGreater(funded["ambition_shift"],0)

    def test_small_optional_warchest_does_not_force_extra_league_places(self):
        r=self.assessment(investment_mandate="optional",investment_pool=10_000_000)
        self.assertEqual(r["expected_rank"],18)

    def test_no_money_does_not_create_investment_expectation(self):
        r=expectation_with_resources(squad_rank=18,league_size=20,
            division_tier=1,ambition="consolidation",
            investment_mandate="required",investment_pool=0,
            opening_unreserved_funds=0,division_median_transfer_budget=45_000_000)
        self.assertEqual(r["expected_rank"],18)

    def test_cannot_promise_more_money_than_career_has(self):
        with self.assertRaisesRegex(ValueError,"earmark"):
            self.assessment(investment_mandate="required",investment_pool=46_000_000)

    def test_no_fake_promotion_target_in_premier_league(self):
        with self.assertRaises(ValueError):
            self.assessment(ambition="promotion")

    def test_underperforming_with_untouched_required_funds_is_penalised(self):
        a=review_underinvestment(actual_rank=15,expected_rank=12,
            committed_spend=0,mandated_funds=35_000_000,mandate="required")
        self.assertEqual(a["delta"],-3)
        self.assertEqual(a["unused"],35_000_000)

    def test_success_without_spending_is_not_penalised(self):
        a=review_underinvestment(actual_rank=10,expected_rank=12,
            committed_spend=0,mandated_funds=35_000_000,mandate="required")
        self.assertEqual(a["delta"],0)

    def test_actual_improvement_investment_avoids_unused_money_penalty(self):
        a=review_underinvestment(actual_rank=15,expected_rank=12,
            committed_spend=30_000_000,mandated_funds=35_000_000,mandate="required")
        self.assertEqual(a["delta"],0)

    def test_optional_investment_never_triggers_unspent_funds_penalty(self):
        a=review_underinvestment(actual_rank=16,expected_rank=12,
            committed_spend=0,mandated_funds=35_000_000,mandate="optional")
        self.assertEqual(a["delta"],0)

if __name__=="__main__":unittest.main()

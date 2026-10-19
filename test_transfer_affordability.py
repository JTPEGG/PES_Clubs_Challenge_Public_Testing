"""Regression coverage for buying-club affordability and negotiation veto."""
import unittest
from world_transfer_affordability import assess_transfer_affordability
from test_transfer_negotiations import PLAYER, SELLER
from world_transfer_negotiations import evaluate_transfer_negotiation


class AffordabilityTests(unittest.TestCase):
    def finance(self, **overrides):
        return assess_transfer_affordability(**{
            "transfer_budget":20_000_000, "wage_headroom":120_000,
            "transfer_fee":15_000_000, "offered_weekly_wage":90_000,
            "signing_on_fee":1_000_000, "agent_fee":500_000,
            "other_upfront_fees":0, "contract_years":3, **overrides,
        })

    def negotiation(self, **finance):
        return evaluate_transfer_negotiation(
            player=PLAYER, seller=SELLER, proposed_contract_years=3,
            buyer_finances={
                "transfer_budget":50_000_000,"wage_headroom":150_000,
                "signing_on_fee":0,"agent_fee":0,"other_upfront_fees":0,
                **finance,
            })

    def test_known_affordable_fee_and_wages(self):
        r=self.finance()
        self.assertEqual(r["decision"],"affordable")
        self.assertEqual(r["total_upfront_commitment"],16_500_000)
        self.assertEqual(r["remaining_transfer_budget"],3_500_000)
        self.assertEqual(r["remaining_weekly_wage_headroom"],30_000)
        self.assertEqual(r["annual_wage_commitment"],4_680_000)
        self.assertEqual(r["total_contract_wages"],14_040_000)

    def test_annual_salary_is_not_deducted_from_transfer_budget(self):
        r=self.finance()
        self.assertEqual(r["remaining_transfer_budget"],3_500_000)

    def test_fee_over_budget_blocks(self):
        r=self.finance(transfer_fee=20_000_000)
        self.assertEqual(r["decision"],"unaffordable")
        self.assertEqual(r["transfer_shortfall"],1_500_000)

    def test_wage_headroom_blocks(self):
        r=self.finance(wage_headroom=80_000)
        self.assertEqual(r["decision"],"unaffordable")
        self.assertEqual(r["weekly_wage_shortfall"],10_000)

    def test_fees_are_not_silently_zero(self):
        r=self.finance(agent_fee=None)
        self.assertEqual(r["decision"],"review")
        self.assertIsNone(r["total_upfront_commitment"])
        self.assertIn("agent fee",r["unknown_fields"])

    def test_unknown_budget_cannot_pass(self):
        r=self.finance(transfer_budget=None)
        self.assertEqual(r["decision"],"review")

    def test_unknown_wage_headroom_cannot_pass(self):
        r=self.finance(wage_headroom=None)
        self.assertEqual(r["decision"],"review")

    def test_visible_wage_shortfall_even_if_fee_unknown(self):
        r=self.finance(transfer_fee=None,wage_headroom=40_000)
        self.assertEqual(r["decision"],"unaffordable")
        self.assertEqual(r["weekly_wage_shortfall"],50_000)

    def test_reject_boolean_or_negative_money(self):
        for data in ({"transfer_budget":True},{"agent_fee":-1},
                     {"wage_headroom":1.5}):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    self.finance(**data)

    def test_no_agreement_when_financial_data_missing(self):
        r=evaluate_transfer_negotiation(
            player=PLAYER,seller=SELLER,proposed_contract_years=3)
        self.assertEqual(r["outcome"],"needs_information")
        self.assertEqual(r["buyer_affordability"]["decision"],"review")

    def test_provisional_requires_affordability(self):
        r=self.negotiation()
        self.assertEqual(r["outcome"],"provisional_agreement")
        self.assertEqual(r["buyer_affordability"]["decision"],"affordable")

    def test_insufficient_transfer_budget_veto(self):
        r=self.negotiation(transfer_budget=5_000_000)
        self.assertEqual(r["outcome"],"blocked")
        self.assertEqual(r["buyer_affordability"]["decision"],"unaffordable")

    def test_insufficient_wage_headroom_veto(self):
        r=self.negotiation(wage_headroom=20_000)
        self.assertEqual(r["outcome"],"blocked")

    def test_unknown_extra_fee_prevents_agreement(self):
        r=self.negotiation(agent_fee=None)
        self.assertEqual(r["outcome"],"needs_information")

if __name__ == "__main__":
    unittest.main()

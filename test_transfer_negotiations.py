"""Regression checks for the read-only three-party transfer coordinator."""
import unittest
from world_transfer_negotiations import evaluate_transfer_negotiation

PLAYER = dict(
    buyer_tier=1, seller_tier=1, buyer_score=82, seller_score=80,
    buyer_prestige=80, seller_prestige=80,
    overall=82, age=27, current_wage=70_000,
    current_role="regular_starter", transfer_listed=True,
    renewal_status="not_offered", buyer_europe="none",seller_europe="none",
    offered_wage=110_000, role_promise="key_player",
)
SELLER = dict(
    market_value=15_000_000, offer_fee=30_000_000,
    contract_years=2, squad_role="regular_starter",
    transfer_listed=True, player_wants_exit=True,
    financial_state="stable", replacement="available",
    seller_stance="sell", age=27,
)

class ThreePartyTests(unittest.TestCase):
    def scenario(self, player=None, seller=None, years=3, finances=None):
        return evaluate_transfer_negotiation(
            player={**PLAYER,**(player or {})},
            seller={**SELLER,**(seller or {})},
            proposed_contract_years=years,
            buyer_finances={**dict(transfer_budget=1_000_000_000,
                wage_headroom=1_000_000, signing_on_fee=0,
                agent_fee=0, other_upfront_fees=0), **(finances or {})},
        )

    def test_all_conditions_met_only_provisional(self):
        r=self.scenario()
        self.assertEqual(r["outcome"],"provisional_agreement")
        self.assertTrue(r["read_only"])
        self.assertEqual(r["selling_club"]["decision"],"accept")
        self.assertEqual(r["agent"]["status"],"acceptable")

    def test_seller_refusal_overrides_high_wages(self):
        r=self.scenario(
            player={"offered_wage":500_000},
            seller={"transfer_listed":False,"player_wants_exit":False,
                    "contract_years":5,"squad_role":"key_player",
                    "replacement":"difficult","seller_stance":"retain",
                    "offer_fee":300_000_000},
        )
        self.assertEqual(r["outcome"],"blocked")
        self.assertEqual(r["selling_club"]["decision"],"reject")

    def test_player_elite_european_refusal_overrides_fee(self):
        r=self.scenario(
            player={"overall":90, "current_wage":150_000,
                    "buyer_score":75,"seller_score":82,
                    "buyer_prestige":55,"seller_prestige":90,
                    "transfer_listed":False,"renewal_status":"renewal_offered",
                    "seller_europe":"champions_league",
                    "offered_wage":500_000},
            seller={"offer_fee":500_000_000},
        )
        self.assertEqual(r["outcome"],"blocked")
        self.assertEqual(r["player"]["decision"],"uninterested")

    def test_seller_counter_offer_independent_of_agent(self):
        r=self.scenario(seller={"offer_fee":1_000_000})
        self.assertEqual(r["outcome"],"counteroffer")
        self.assertEqual(r["selling_club"]["decision"],"negotiate")
        self.assertEqual(r["agent"]["status"],"acceptable")

    def test_wage_shortfall_when_role_already_met(self):
        r=self.scenario(player={"offered_wage":50_000})
        self.assertEqual(r["outcome"],"counteroffer")
        self.assertTrue(r["player"]["role_satisfied"])
        self.assertGreater(r["agent"]["wage_shortfall"],0)

    def test_one_year_contract_premium_is_enforced(self):
        baseline=self.scenario()
        short=self.scenario(years=1)
        self.assertGreater(short["agent"]["minimum_weekly_wage"],
                           baseline["agent"]["minimum_weekly_wage"])
        offered=short["agent"]["minimum_weekly_wage"]-500
        r=self.scenario(player={"offered_wage":offered},years=1)
        self.assertEqual(r["agent"]["status"],"counteroffer")
        self.assertEqual(r["agent"]["wage_shortfall"],500)

    def test_unoffered_wage_cannot_be_agreement(self):
        r=self.scenario(player={"offered_wage":None})
        self.assertNotEqual(r["outcome"],"provisional_agreement")
        self.assertEqual(r["agent"]["status"],"needs_information")

    def test_unknown_contract_not_inferred(self):
        r=self.scenario(seller={"contract_years":None})
        self.assertEqual(r["outcome"],"needs_information")
        self.assertIsNone(r["selling_club"]["asking_price"])

    def test_unknown_europe_or_current_wage_cannot_pass(self):
        for p in ({"seller_europe":"unknown"},{"current_wage":None}):
            with self.subTest(p=p):
                r=self.scenario(player=p)
                self.assertEqual(r["outcome"],"needs_information")
                self.assertEqual(r["player"]["decision"],"review")

    def test_missing_proposed_term_not_invented(self):
        r=self.scenario(years=None)
        self.assertEqual(r["outcome"],"needs_information")
        self.assertEqual(r["agent"]["status"],"needs_information")

    def test_invalid_contract_duration(self):
        with self.assertRaises(ValueError):
            self.scenario(years=6)

    def test_prestige_and_sporting_still_separate(self):
        r=self.scenario()
        self.assertEqual(r["player"]["sporting_gap"],2)
        self.assertEqual(r["player"]["prestige_gap"],0)

if __name__=="__main__":
    unittest.main()

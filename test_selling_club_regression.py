"""Deterministic tests for read-only fictional selling-club policy."""
import unittest
from world_selling_club import evaluate_selling_club, SQUAD_ROLES

BASE = dict(market_value=20_000_000, offer_fee=30_000_000,
            contract_years=4, squad_role="key_player",
            transfer_listed=False, player_wants_exit=False,
            financial_state="stable", replacement="difficult",
            seller_stance="neutral", age=27)

class SellingClubTests(unittest.TestCase):
    def choice(self, **kwargs):
        return evaluate_selling_club(**{**BASE, **kwargs})

    def test_unknown_never_invented(self):
        r=evaluate_selling_club()
        self.assertEqual(r["decision"],"review")
        self.assertIsNone(r["asking_price"])
        self.assertIsNone(r["market_value"])

    def test_key_player_protected_despite_large_bid(self):
        r=self.choice(offer_fee=150_000_000)
        self.assertEqual(r["decision"],"reject")
        self.assertIsNone(r["asking_price"])

    def test_retain_stance_blocks_unwanted_exit(self):
        self.assertEqual(self.choice(seller_stance="retain",
                          squad_role="rotation",replacement="available")["decision"],"reject")

    def test_transfer_listing_changes_seller_response(self):
        r=self.choice(transfer_listed=True,offer_fee=None)
        self.assertEqual(r["decision"],"negotiate")
        self.assertGreater(r["asking_price"],0)

    def test_low_bid_produces_counter(self):
        r=self.choice(transfer_listed=True,offer_fee=1_000_000)
        self.assertEqual(r["decision"],"negotiate")
        self.assertGreater(r["fee_shortfall"],0)

    def test_sufficient_bid_only_means_seller_approval(self):
        r=self.choice(transfer_listed=True,offer_fee=500_000_000)
        self.assertEqual(r["decision"],"accept")
        self.assertIn("player and agent consent",r["reason"])

    def test_existing_contract_increases_fee(self):
        shared=dict(squad_role="rotation",replacement="available",
                    financial_state="stable",seller_stance="neutral",
                    player_wants_exit=False,transfer_listed=False,
                    market_value=10_000_000,offer_fee=None)
        short=evaluate_selling_club(**shared,contract_years=1)
        long=evaluate_selling_club(**shared,contract_years=5)
        self.assertGreater(long["asking_price"],short["asking_price"])

    def test_distress_changes_fee_not_invents_finances(self):
        shared=dict(BASE,transfer_listed=True,offer_fee=None)
        stable=evaluate_selling_club(**shared)
        distressed=evaluate_selling_club(**{**shared,"financial_state":"distressed"})
        self.assertLess(distressed["asking_price"],stable["asking_price"])

    def test_role_hierarchy_no_important(self):
        self.assertEqual(SQUAD_ROLES,("key_player","regular_starter","rotation","fringe"))
        with self.assertRaises(ValueError):
            self.choice(squad_role="important")

    def test_sporting_and_prestige_not_seller_inputs(self):
        with self.assertRaises(TypeError):
            self.choice(buyer_prestige=100)

    def test_unknown_player_exit_not_assumed(self):
        r=self.choice(player_wants_exit=None)
        self.assertEqual(r["decision"],"review")
        self.assertIsNone(r["asking_price"])

if __name__ == "__main__":
    unittest.main()

"""Regressions for explicit board overrides and financial prudence vetoes."""
import unittest
from world_transfer_board import evaluate_seller_board, evaluate_buyer_board
from world_transfer_negotiations import evaluate_transfer_negotiation
from test_transfer_negotiations import PLAYER, SELLER


class BoardDecisionTests(unittest.TestCase):
    def deal(self, *, player=None, seller=None, seller_board=None, buyer_board=None):
        return evaluate_transfer_negotiation(
            player={**PLAYER,**(player or {})},
            seller={**SELLER,**(seller or {})},
            proposed_contract_years=3,
            buyer_finances=dict(transfer_budget=100_000_000,
                wage_headroom=200_000,signing_on_fee=0,
                agent_fee=0,other_upfront_fees=0),
            seller_board=seller_board,buyer_board=buyer_board)

    def test_board_disabled_does_not_override(self):
        r=self.deal()
        self.assertEqual(r["selling_board"]["decision"],"not_enabled")
        self.assertEqual(r["buying_board"]["decision"],"not_enabled")
        self.assertEqual(r["outcome"],"provisional_agreement")

    def test_manager_wants_retain_but_selling_board_forces_sale(self):
        retained=dict(transfer_listed=False,player_wants_exit=False,
                      seller_stance="retain",squad_role="key_player",
                      replacement="difficult",contract_years=5)
        normal=self.deal(seller=retained)
        self.assertEqual(normal["outcome"],"blocked")
        overridden=self.deal(seller=retained,seller_board=dict(
            intervene=True,approval_multiple_pct=180))
        self.assertEqual(overridden["selling_club"]["decision"],"reject")
        self.assertEqual(overridden["effective_selling_club"]["decision"],"accept")
        self.assertEqual(overridden["selling_board"]["decision"],"direct_sale")
        self.assertEqual(overridden["outcome"],"provisional_agreement")

    def test_selling_board_offer_below_threshold_does_not_intervene(self):
        r=self.deal(seller=dict(seller_stance="retain",
            transfer_listed=False,player_wants_exit=False),
            seller_board=dict(intervene=True,approval_multiple_pct=300))
        self.assertEqual(r["selling_board"]["decision"],"no_intervention")
        self.assertEqual(r["outcome"],"blocked")

    def test_board_does_not_override_player_refusal(self):
        r=self.deal(
            player=dict(overall=90,current_role="key_player",
                transfer_listed=False,renewal_status="renewal_offered",
                seller_europe="champions_league",buyer_europe="none",
                seller_score=90,buyer_score=75,seller_prestige=90,
                buyer_prestige=55,current_wage=150_000,offered_wage=500_000),
            seller_board=dict(intervene=True,approval_multiple_pct=150))
        self.assertEqual(r["selling_board"]["decision"],"direct_sale")
        self.assertEqual(r["player"]["decision"],"uninterested")
        self.assertEqual(r["outcome"],"blocked")

    def test_buying_board_can_veto_affordable_bad_value(self):
        r=self.deal(buyer_board=dict(
            intervene=True,max_fee_pct=150,max_headroom_use_pct=90))
        self.assertEqual(r["buyer_affordability"]["decision"],"affordable")
        self.assertEqual(r["buying_board"]["decision"],"veto")
        self.assertEqual(r["outcome"],"blocked")

    def test_buying_board_can_veto_wage_pressure(self):
        r=self.deal(buyer_board=dict(
            intervene=True,max_fee_pct=300,max_headroom_use_pct=40))
        self.assertEqual(r["buying_board"]["decision"],"veto")
        self.assertEqual(r["outcome"],"blocked")

    def test_board_can_approve_good_value_without_replacing_other_checks(self):
        r=self.deal(buyer_board=dict(
            intervene=True,max_fee_pct=250,max_headroom_use_pct=80))
        self.assertEqual(r["buying_board"]["decision"],"approved")
        self.assertEqual(r["outcome"],"provisional_agreement")

    def test_unknown_board_policy_blocks_unearned_approval(self):
        r=self.deal(buyer_board=dict(intervene=True))
        self.assertEqual(r["buying_board"]["decision"],"review")
        self.assertEqual(r["outcome"],"needs_information")

    def test_unknown_seller_threshold_does_not_force_sale(self):
        r=self.deal(seller=dict(seller_stance="retain",
            transfer_listed=False,player_wants_exit=False),
            seller_board=dict(intervene=True))
        self.assertEqual(r["selling_board"]["decision"],"review")
        self.assertEqual(r["outcome"],"blocked")

    def test_zero_market_value_never_claims_bargain(self):
        r=evaluate_seller_board(intervene=True,market_value=0,
             offer_fee=25_000_000,approval_multiple_pct=200)
        self.assertEqual(r["decision"],"review")

    def test_exact_board_thresholds_are_inclusive(self):
        r=evaluate_seller_board(intervene=True,market_value=15_000_000,
            offer_fee=30_000_000,approval_multiple_pct=200)
        self.assertEqual(r["decision"],"direct_sale")
        b=evaluate_buyer_board(intervene=True,market_value=20_000_000,
            offer_fee=30_000_000,offered_weekly_wage=50_000,
            wage_headroom=100_000,max_fee_pct=150,
            max_headroom_use_pct=50)
        self.assertEqual(b["decision"],"approved")

    def test_invalid_policies_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_seller_board(intervene=True,approval_multiple_pct=-1)
        with self.assertRaises(ValueError):
            evaluate_buyer_board(intervene=True,max_fee_pct=100.5)

if __name__=="__main__":
    unittest.main()

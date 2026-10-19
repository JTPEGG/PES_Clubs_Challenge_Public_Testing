"""Board context variation: explicit assumptions only, no club stereotypes."""
import unittest
from world_transfer_board import evaluate_seller_board, evaluate_buyer_board
from test_transfer_board import BoardDecisionTests

CONSERVATIVE = dict(financial_objective="cash_generation",ambition="survival",
                    ownership_priority="return_on_investment",manager_trust="low")
SUPPORTIVE = dict(financial_objective="growth",ambition="continental",
                  ownership_priority="sporting",manager_trust="high")
NEUTRAL = dict(financial_objective="balanced",ambition="consolidation",
               ownership_priority="balanced",manager_trust="medium")

class BoardContextTests(unittest.TestCase):
    def seller(self,context):
        return evaluate_seller_board(intervene=True,offer_fee=25_000_000,
            market_value=15_000_000,approval_multiple_pct=200,context=context)

    def buyer(self,context):
        return evaluate_buyer_board(intervene=True,offer_fee=30_000_000,
            market_value=20_000_000,offered_weekly_wage=80_000,
            wage_headroom=150_000,max_fee_pct=150,max_headroom_use_pct=60,
            context=context)

    def test_cash_generation_board_more_willing_to_force_sale(self):
        low=self.seller(CONSERVATIVE)
        high=self.seller(SUPPORTIVE)
        self.assertEqual(low["decision"],"direct_sale")
        self.assertEqual(high["decision"],"no_intervention")
        self.assertLess(low["required_offer"],high["required_offer"])

    def test_trust_in_manager_protects_selling_autonomy(self):
        low=self.seller({**NEUTRAL,"manager_trust":"low"})
        high=self.seller({**NEUTRAL,"manager_trust":"high"})
        self.assertGreater(high["required_offer"],low["required_offer"])

    def test_buyer_value_veto_stricter_when_cost_control(self):
        self.assertEqual(self.buyer(CONSERVATIVE)["decision"],"veto")
        self.assertEqual(self.buyer(SUPPORTIVE)["decision"],"approved")

    def test_buyer_trust_changes_wage_tolerance(self):
        low=self.buyer({**NEUTRAL,"manager_trust":"low"})
        high=self.buyer({**NEUTRAL,"manager_trust":"high"})
        self.assertLess(low["maximum_weekly_wage"],high["maximum_weekly_wage"])

    def test_neutral_context_preserves_user_manual_thresholds(self):
        plain=evaluate_seller_board(intervene=True,offer_fee=25_000_000,
            market_value=15_000_000,approval_multiple_pct=200)
        neutral=self.seller(NEUTRAL)
        self.assertEqual(plain["required_offer"],neutral["required_offer"])

    def test_unknown_context_not_made_up(self):
        unknown={**NEUTRAL,"ownership_priority":"unknown"}
        self.assertEqual(self.seller(unknown)["decision"],"review")
        self.assertEqual(self.buyer(unknown)["decision"],"review")

    def test_disabled_board_does_not_require_context(self):
        self.assertEqual(evaluate_seller_board(context=CONSERVATIVE)["decision"],"not_enabled")
        self.assertEqual(evaluate_buyer_board(context=CONSERVATIVE)["decision"],"not_enabled")

    def test_invalid_context_rejected(self):
        with self.assertRaises(ValueError):
            self.seller({**NEUTRAL,"ambition":"invented"})
        with self.assertRaises(ValueError):
            self.buyer({"ambition":"continental"})

    def test_full_transfer_selling_context_changes_manager_override(self):
        base=BoardDecisionTests()
        seller=dict(transfer_listed=False,player_wants_exit=False,
                    seller_stance="retain",squad_role="key_player",
                    replacement="difficult",contract_years=5)
        low=base.deal(seller=seller,seller_board=dict(intervene=True,
            approval_multiple_pct=200,context=CONSERVATIVE))
        high=base.deal(seller=seller,seller_board=dict(intervene=True,
            approval_multiple_pct=200,context=SUPPORTIVE))
        self.assertEqual(low["selling_board"]["decision"],"direct_sale")
        self.assertEqual(high["selling_board"]["decision"],"no_intervention")
        self.assertEqual(low["outcome"],"provisional_agreement")
        self.assertEqual(high["outcome"],"blocked")

    def test_full_transfer_buying_context_veto(self):
        base=BoardDecisionTests()
        strict=base.deal(buyer_board=dict(intervene=True,max_fee_pct=150,
            max_headroom_use_pct=60,context=CONSERVATIVE))
        lenient=base.deal(buyer_board=dict(intervene=True,max_fee_pct=150,
            max_headroom_use_pct=60,context=SUPPORTIVE))
        self.assertEqual(strict["outcome"],"blocked")
        self.assertEqual(lenient["outcome"],"provisional_agreement")

if __name__=="__main__":
    unittest.main()

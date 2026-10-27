"""Protect FC27 club board decisions from ignoring live squad damage."""
import unittest
from world_fc27_seller_value import (
    exceptional_seller_board_floor,honour_accepted_seller_quote)


class FC27BoardSellerTests(unittest.TestCase):
    def test_binding_seller_counter_honoured_only_when_squad_unchanged(self):
        import json
        old={"formation":"4-2-3-1","lineup_loss":0,
             "first_choice":True,"starter_quality_drop":6,
             "formation_quality_loss":14,"rotation_quality_drop":2,
             "after_specialist_depth":3}
        original={"effective_decision":"negotiate","asking_price":13_750_000,
                  "input_snapshot":json.dumps({
                      "tactical_squad_review":old})}
        current={"decision":"negotiate","tactical_squad_review":dict(old)}
        self.assertTrue(honour_accepted_seller_quote(
            saved_decision=original,current_review=current,
            fee=13_750_000,counter_accepted=True))
        self.assertFalse(honour_accepted_seller_quote(
            saved_decision=original,current_review=current,
            fee=13_750_000,counter_accepted=False))
        self.assertFalse(honour_accepted_seller_quote(
            saved_decision=original,current_review=current,
            fee=13_700_000,counter_accepted=True))
        changed={"decision":"negotiate","tactical_squad_review":
                 {**old,"formation_quality_loss":23}}
        self.assertFalse(honour_accepted_seller_quote(
            saved_decision=original,current_review=changed,
            fee=13_750_000,counter_accepted=True))
        rejected={**original,"effective_decision":"reject"}
        self.assertFalse(honour_accepted_seller_quote(
            saved_decision=rejected,current_review=current,
            fee=13_750_000,counter_accepted=True))

    def test_big_xi_loss_raises_exceptional_offer_but_never_vetoes_it(self):
        damaged=dict(valid=True,first_choice=True,
                     formation_quality_loss=15,formation_lineup_loss=0,
                     starter_rating_drop=12)
        threshold=exceptional_seller_board_floor(
            reference_value=7_000_000,base_board_floor=11_550_000,
            projected_squad_sale=damaged,risk_uplift=.65,club_ambition=85)
        self.assertGreater(threshold,11_550_000)
        # A truly exceptional £30m bid remains above the dynamic ask.
        self.assertLess(threshold,30_000_000)

    def test_surplus_outgoing_keeps_original_board_offer_threshold(self):
        surplus=dict(valid=True,first_choice=False,
                     formation_quality_loss=0,formation_lineup_loss=0,
                     starter_rating_drop=0)
        self.assertEqual(exceptional_seller_board_floor(
            reference_value=7_000_000,base_board_floor=11_550_000,
            projected_squad_sale=surplus,risk_uplift=.7,club_ambition=85),
            11_550_000)

    def test_tactical_ambition_matters_without_club_name_exception(self):
        damaged=dict(valid=True,first_choice=True,
                     formation_quality_loss=11,formation_lineup_loss=0,
                     starter_rating_drop=9)
        kwargs=dict(reference_value=7_000_000,base_board_floor=11_550_000,
                    projected_squad_sale=damaged,risk_uplift=.58)
        self.assertGreater(exceptional_seller_board_floor(
            **kwargs,club_ambition=92),
            exceptional_seller_board_floor(**kwargs,club_ambition=55))

    def test_only_live_positive_sourced_valuations_allowed(self):
        with self.assertRaises(ValueError):
            exceptional_seller_board_floor(
                reference_value=0,base_board_floor=1_000_000,
                projected_squad_sale={"valid":True},
                risk_uplift=.5,club_ambition=90)
        with self.assertRaises(ValueError):
            exceptional_seller_board_floor(
                reference_value=7_000_000,base_board_floor=1_000_000,
                projected_squad_sale={"valid":False},
                risk_uplift=.5,club_ambition=90)


if __name__=="__main__":
    unittest.main()

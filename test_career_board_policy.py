"""Regression checks: real career confidence drives configured board vetoes.

Missing confidence and valuations do not silently become permissions; old
careers without a policy retain prior behaviour. The transfer offer write is
vetoed inside its transaction before any record is inserted.
"""
import unittest
from world_career_board_policy import (
    initialize_career_board_policy,configure_policy,get_policy,
    career_board_decision,require_board_approval,
)
from world_career_management import set_initial_confidence,record_board_event
from test_career_management import fixture

SETTINGS=dict(financial_objective="balanced",ambition="consolidation",
              ownership_priority="balanced",source_note="Fictional governance assumptions",
              max_fee_pct=150,max_headroom_use_pct=60)

class CareerBoardPolicyTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture()
        self.db.execute("ALTER TABLE world_career_saves ADD COLUMN manager_club_id INTEGER")
        self.db.execute("ALTER TABLE world_career_saves ADD COLUMN state TEXT NOT NULL DEFAULT 'sandbox'")
        self.db.execute("UPDATE world_career_saves SET manager_club_id=1")
        self.db.commit()
        initialize_career_board_policy(self.db)
    def tearDown(self):
        self.db.close()
    def lock(self,**params):
        return configure_policy(self.db,career_id="career-a",club_id=1,
                                **{**SETTINGS,**params})
    def decide(self,**params):
        return career_board_decision(self.db,career_id="career-a",club_id=1,
                   offer_fee=14_000_000,market_value=10_000_000,**params)

    def test_old_career_no_policy_preserves_compatibility(self):
        self.assertEqual(self.decide(stage="fee")["decision"],"not_configured")

    def test_policy_not_silently_applied_to_other_career(self):
        self.lock()
        self.assertIsNone(get_policy(self.db,"career-b",1))
        self.assertEqual(career_board_decision(self.db,career_id="career-b",club_id=1,
            offer_fee=12,market_value=10,stage="fee")["decision"],"not_configured")

    def test_config_requires_managed_career_club(self):
        with self.assertRaises(ValueError):
            configure_policy(self.db,career_id="career-a",club_id=2,**SETTINGS)

    def test_configuration_idempotent_and_locked(self):
        self.assertTrue(self.lock())
        self.assertFalse(self.lock())
        with self.assertRaises(ValueError):
            self.lock(max_fee_pct=400)

    def test_missing_confidence_blocks_enabled_board(self):
        self.lock()
        result=self.decide(stage="fee")
        self.assertEqual(result["decision"],"review")
        with self.assertRaises(ValueError):
            require_board_approval(result)

    def test_low_trust_rejects_fee_high_trust_accepts(self):
        self.lock()
        set_initial_confidence(self.db,career_id="career-a",club_id=1,value=20)
        before=self.decide(stage="fee")
        self.assertEqual(before["decision"],"veto")
        # Real saved event now moves confidence, and thus board behaviour.
        for n in range(3):
            record_board_event(self.db,career_id="career-a",club_id=1,
                event_key=f"earned-{n}",event_type="promotion",
                event_date="2026-10-14",source_note="confirmed test scenario")
        after=self.decide(stage="fee")
        self.assertEqual(after["trust"],"high")
        self.assertEqual(after["decision"],"approved")
        self.assertGreater(after["maximum_fee"],before["maximum_fee"])

    def test_fee_only_stage_does_not_claim_wage_approval(self):
        self.lock()
        set_initial_confidence(self.db,career_id="career-a",club_id=1,value=70)
        d=self.decide(stage="fee")
        self.assertIn("wages still unassessed",d["reason"])

    def test_contract_stage_vetoes_wage_even_with_approved_fee(self):
        self.lock()
        set_initial_confidence(self.db,career_id="career-a",club_id=1,value=50)
        decision=self.decide(stage="terms",
            offered_wage=90_000,wage_headroom=100_000)
        self.assertEqual(decision["decision"],"veto")
        with self.assertRaises(ValueError):
            require_board_approval(decision)

    def test_approved_wages_and_fee_when_affordable(self):
        self.lock()
        set_initial_confidence(self.db,career_id="career-a",club_id=1,value=75)
        decision=self.decide(stage="terms",
            offered_wage=45_000,wage_headroom=100_000)
        self.assertEqual(decision["decision"],"approved")
        require_board_approval(decision)

    def test_unknown_wage_headroom_blocks_contract(self):
        self.lock()
        set_initial_confidence(self.db,career_id="career-a",club_id=1,value=75)
        self.assertEqual(self.decide(stage="terms",
            offered_wage=20_000)["decision"],"review")

    def test_no_market_valuation_blocks_fee_even_high_trust(self):
        self.lock()
        set_initial_confidence(self.db,career_id="career-a",club_id=1,value=80)
        decision=career_board_decision(self.db,career_id="career-a",club_id=1,
            offer_fee=10_000_000,market_value=None,stage="fee")
        self.assertEqual(decision["decision"],"review")

    def test_no_policy_requires_no_board_approval(self):
        require_board_approval(self.decide(stage="fee"))

    def test_invalid_setting_raises(self):
        with self.assertRaises(ValueError):
            self.lock(max_fee_pct=-1)

    def test_offer_veto_rollback_prevents_saved_offer(self):
        # End-to-end transaction boundary with existing career offer function.
        from world_careers import propose_offer
        from unittest.mock import patch
        self.db.execute("ALTER TABLE world_career_offers ADD COLUMN request_key TEXT")
        self.db.execute("ALTER TABLE world_career_offers ADD COLUMN player_id INTEGER")
        self.db.execute("ALTER TABLE world_career_saves ADD COLUMN dataset_id TEXT")
        self.db.execute("ALTER TABLE world_career_saves ADD COLUMN economy_version TEXT")
        self.db.execute("UPDATE world_career_saves SET dataset_id='scenario',economy_version='prototype-v1'")
        # Buyer must be able to afford the fee, otherwise the affordability
        # check correctly blocks the transaction before the board is consulted.
        self.db.execute("""UPDATE world_career_club_ledger SET transfer_budget=100000000
            WHERE career_id='career-a' AND club_id=1""")
        self.db.commit()
        self.lock()
        set_initial_confidence(self.db,career_id="career-a",club_id=1,value=20)
        with patch("world_careers._player_reference",return_value=(10_000_000,80)):
            with self.assertRaisesRegex(ValueError,"Buying board veto"):
                propose_offer(self.db,career_id="career-a",request_key="offer-veto",
                    player_id=102,buying_club_id=1,offered_fee=20_000_000,
                    agreement_date="2026-10-14")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM world_career_offers").fetchone()[0],2)

if __name__=="__main__":
    unittest.main()

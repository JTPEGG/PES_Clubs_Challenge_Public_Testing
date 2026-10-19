"""Career-seller integration and regression coverage on isolated career SQLite.

Checks opt-in compatibility, seller thresholds, board directions, locked
audits, counteroffers, career isolation and no PES registration changes.
"""
import sqlite3
import unittest
from unittest.mock import patch

from test_career_management import fixture
from world_career_management import set_initial_confidence,record_board_event
from world_career_selling import (
    initialize_career_selling,enable_career_selling,selling_enabled,
    get_seller_assumptions,record_seller_assumptions,
    evaluate_career_seller_bid,offer_decision,
)
from world_careers import propose_offer,accept_counter

NORMAL = dict(market_value=10_000_000,contract_years=3,
    squad_role="regular_starter",transfer_listed=False,
    player_wants_exit=True,financial_state="stable",
    replacement="available",seller_stance="neutral",
    board_enabled=False,exceptional_offer_pct=None,
    source_note="Hypothetical test scenario")
RETAIN = dict(market_value=10_000_000,contract_years=5,
    squad_role="key_player",transfer_listed=False,
    player_wants_exit=False,financial_state="stable",
    replacement="difficult",seller_stance="retain",
    board_enabled=False,exceptional_offer_pct=None,
    source_note="Assumed star who manager refuses to sell")
CONTEXT = dict(financial_objective="balanced",ambition="consolidation",
    ownership_priority="balanced",assumed_manager_trust="medium")


def career_fixture():
    c=fixture()
    c.executescript("""
    ALTER TABLE world_career_saves ADD COLUMN manager_club_id INTEGER;
    ALTER TABLE world_career_saves ADD COLUMN state TEXT NOT NULL DEFAULT 'sandbox';
    ALTER TABLE world_career_saves ADD COLUMN dataset_id TEXT;
    ALTER TABLE world_career_saves ADD COLUMN economy_version TEXT;
    ALTER TABLE world_career_saves ADD COLUMN pes_lock_date TEXT;
    ALTER TABLE world_career_saves ADD COLUMN next_summer_date TEXT;
    ALTER TABLE world_career_saves ADD COLUMN title TEXT;
    UPDATE world_career_saves SET manager_club_id=1,dataset_id='test',
      economy_version='prototype-v1',pes_lock_date='2026-08-01',
      next_summer_date='2027-07-01',title='Test Career';
    UPDATE world_career_club_ledger SET transfer_budget=300000000,
      weekly_wage_budget=700000 WHERE career_id='career-a';
    ALTER TABLE world_career_offers ADD COLUMN request_key TEXT;
    ALTER TABLE world_career_offers ADD COLUMN player_id INTEGER;
    ALTER TABLE world_career_offers ADD COLUMN selling_club_id INTEGER;
    ALTER TABLE world_career_offers ADD COLUMN agreement_date TEXT;
    ALTER TABLE world_career_offers ADD COLUMN source_rating INTEGER;
    ALTER TABLE world_career_offers ADD COLUMN economy_version TEXT;
    CREATE TABLE world_career_offer_events(
      event_id INTEGER PRIMARY KEY,offer_id INTEGER,event_type TEXT,detail TEXT
    );
    """)
    initialize_career_selling(c)
    from world_career_board_policy import initialize_career_board_policy
    initialize_career_board_policy(c)
    return c


class CareerSellerTests(unittest.TestCase):
    def setUp(self):
        self.db=career_fixture()
    def tearDown(self):
        self.db.close()
    def enable(self):
        return enable_career_selling(self.db,career_id="career-a",
            source_note="Opt-in fictional seller rules")
    def record(self,player_id=102,**kwargs):
        return record_seller_assumptions(self.db,career_id="career-a",
            player_id=player_id,**{**NORMAL,**kwargs})
    def bid(self,player_id=102,buying_club_id=1,fee=8_000_000,key="new-bid"):
        with patch("world_careers._player_reference",return_value=(10_000_000,78)):
            return propose_offer(self.db,career_id="career-a",
                request_key=key,player_id=player_id,
                buying_club_id=buying_club_id,offered_fee=fee,
                agreement_date="2026-10-14")
    def preview(self,player_id=102,fee=8_000_000,seller_id=2):
        return evaluate_career_seller_bid(self.db,career_id="career-a",
            player_id=player_id,seller_club_id=seller_id,offer_fee=fee)

    def test_legacy_mode_unchanged_before_opt_in(self):
        self.assertFalse(selling_enabled(self.db,"career-a"))
        self.assertEqual(self.preview()["decision"],"legacy")

    def test_activation_preserves_old_offers(self):
        count=self.db.execute("SELECT COUNT(*) FROM world_career_offers").fetchone()[0]
        self.enable()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM world_career_offers").fetchone()[0],count)
        self.assertTrue(selling_enabled(self.db,"career-a"))
        self.assertFalse(selling_enabled(self.db,"career-b"))

    def test_activation_note_mandatory_and_idempotent(self):
        with self.assertRaises(ValueError):
            enable_career_selling(self.db,career_id="career-a",source_note="")
        self.assertTrue(self.enable())
        self.assertFalse(self.enable())

    def test_unknown_facts_record_offer_as_awaiting_seller_review(self):
        self.enable()
        count=self.db.execute("SELECT COUNT(*) FROM world_career_offers").fetchone()[0]
        offer_id=self.bid()
        row=self.db.execute("SELECT status FROM world_career_offers WHERE offer_id=?",
                            (offer_id,)).fetchone()
        self.assertEqual(row[0],"proposed")
        self.assertIsNone(offer_decision(self.db,offer_id))
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM world_career_offers").fetchone()[0],count+1)
        self.assertEqual(self.db.execute(
            "SELECT club_id FROM world_career_registrations WHERE career_id='career-a' AND player_id=102"
        ).fetchone()[0],2)

    def test_pending_offer_reassessed_after_selling_information_is_supplied(self):
        from world_careers import review_pending_seller_offer
        self.enable()
        offer_id=self.bid()
        with self.assertRaisesRegex(ValueError,"Seller information still needed"):
            review_pending_seller_offer(self.db,career_id="career-a",offer_id=offer_id)
        self.record()
        result=review_pending_seller_offer(self.db,career_id="career-a",offer_id=offer_id)
        self.assertEqual(result,"countered")
        self.assertIsNotNone(offer_decision(self.db,offer_id))
        self.assertGreater(self.db.execute(
            "SELECT demanded_fee FROM world_career_offers WHERE offer_id=?",
            (offer_id,)).fetchone()[0],8_000_000)
        with self.assertRaises(ValueError):
            review_pending_seller_offer(self.db,career_id="career-a",offer_id=offer_id)

    def test_saved_unknown_does_not_become_yes(self):
        from world_careers import review_pending_seller_offer
        self.enable()
        self.record(contract_years=None)
        self.assertEqual(self.preview()["decision"],"review")
        offer_id=self.bid()
        self.assertEqual(self.db.execute(
            "SELECT status FROM world_career_offers WHERE offer_id=?",
            (offer_id,)).fetchone()[0],"proposed")
        with self.assertRaises(ValueError):
            review_pending_seller_offer(self.db,career_id="career-a",offer_id=offer_id)

    def test_live_rival_bids_raise_seller_counter_without_fabricating_interest(self):
        import json
        self.enable()
        self.record()
        baseline=self.preview(fee=8_000_000)
        self.assertEqual(baseline["decision"],"negotiate")
        self.assertEqual(baseline["market_competition"]["recorded_active_rival_clubs"],0)
        self.db.execute("INSERT INTO world_clubs(club_id) VALUES(3)")
        self.db.execute("""INSERT INTO world_career_club_ledger
            (career_id,club_id,transfer_budget,weekly_wage_budget,
             committed_fees,committed_wages)
            VALUES('career-a',3,25000000,400000,0,0)""")
        self.db.execute("""INSERT INTO world_career_offers
            (career_id,request_key,player_id,buying_club_id,selling_club_id,
             offered_fee,status,agreement_date,economy_version)
            VALUES('career-a','recorded-rival-3',102,3,2,
                9000000,'proposed','2026-10-14','prototype-v1')""")
        self.db.commit()
        crowded=evaluate_career_seller_bid(self.db,career_id="career-a",
            player_id=102,seller_club_id=2,buying_club_id=1,offer_fee=8_000_000)
        self.assertEqual(crowded["market_competition"]["recorded_active_rival_clubs"],1)
        self.assertEqual(crowded["market_competition"]["selling_club_counter_premium_pct"],4)
        self.assertGreater(crowded["asking_price"],baseline["asking_price"])
        snap=json.loads(crowded["snapshot"])
        self.assertEqual(snap["market_competition"]["recorded_active_rival_clubs"],1)
        self.assertEqual(snap["seller"]["asking_price"],crowded["asking_price"])
        # Another rejected offer from that same club cannot inflate demand.
        self.db.execute("""INSERT INTO world_career_offers
            (career_id,request_key,player_id,buying_club_id,selling_club_id,
             offered_fee,status,agreement_date,economy_version)
            VALUES('career-a','old-rejected-rival',102,3,2,
                7000000,'rejected','2026-10-14','prototype-v1')""")
        self.db.commit()
        repeat=evaluate_career_seller_bid(self.db,career_id="career-a",
            player_id=102,seller_club_id=2,buying_club_id=1,offer_fee=8_000_000)
        self.assertEqual(repeat["asking_price"],crowded["asking_price"])

    def test_firm_not_for_sale_not_forced_by_other_bids(self):
        self.enable()
        self.record(**RETAIN)
        self.db.execute("""INSERT INTO world_career_offers
            (career_id,request_key,player_id,buying_club_id,selling_club_id,
             offered_fee,status,agreement_date,economy_version)
            VALUES('career-a','rival-key-player',102,1,2,
                7000000,'proposed','2026-10-14','prototype-v1')""")
        self.db.commit()
        reviewed=evaluate_career_seller_bid(self.db,career_id="career-a",
            player_id=102,seller_club_id=2,buying_club_id=99,offer_fee=50_000_000)
        self.assertEqual(reviewed["decision"],"reject")
        self.assertEqual(reviewed["board_decision"],"not_enabled")

    def test_valid_seller_fee_counter_and_snapshot(self):
        self.enable()
        self.record()
        oid=self.bid()
        offer=self.db.execute("SELECT status,demanded_fee FROM world_career_offers WHERE offer_id=?",
                              (oid,)).fetchone()
        self.assertEqual(offer[0],"countered")
        self.assertGreater(offer[1],8_000_000)
        snap=offer_decision(self.db,oid)
        self.assertEqual(snap["effective_decision"],"negotiate")
        self.assertIn("seller",snap["input_snapshot"])
        self.assertEqual(snap["career_id"],"career-a")

    def test_accept_counter_preserves_snapshot_and_advances(self):
        self.enable()
        self.record()
        oid=self.bid()
        with patch("world_careers._player_reference",return_value=(10_000_000,78)):
            accept_counter(self.db,career_id="career-a",offer_id=oid)
        self.assertEqual(self.db.execute(
            "SELECT status FROM world_career_offers WHERE offer_id=?",(oid,)).fetchone()[0],
            "accepted_pending_contract")
        self.assertEqual(offer_decision(self.db,oid)["effective_decision"],"negotiate")

    def test_seller_retains_key_player_without_board(self):
        self.enable()
        self.record(**RETAIN)
        oid=self.bid(fee=100_000_000)
        self.assertEqual(self.db.execute(
            "SELECT status FROM world_career_offers WHERE offer_id=?",(oid,)).fetchone()[0],
            "rejected")
        self.assertEqual(offer_decision(self.db,oid)["board_decision"],"not_enabled")

    def test_board_forces_sale_against_managers_preference(self):
        self.enable()
        self.record(player_id=101,**{**RETAIN,**CONTEXT,
            "board_enabled":True,"exceptional_offer_pct":175})
        set_initial_confidence(self.db,career_id="career-a",club_id=1,value=20)
        oid=self.bid(player_id=101,buying_club_id=2,fee=20_000_000,key="ai-inbound")
        self.assertEqual(self.db.execute(
            "SELECT status FROM world_career_offers WHERE offer_id=?",(oid,)).fetchone()[0],
            "accepted_pending_contract")
        decision=offer_decision(self.db,oid)
        self.assertEqual(decision["board_decision"],"direct_sale")
        self.assertEqual(decision["effective_decision"],"accept")
        self.assertEqual(self.db.execute(
            "SELECT club_id FROM world_career_registrations WHERE career_id='career-a' AND player_id=101"
        ).fetchone()[0],1)

    def test_high_confidence_protects_star_compared_with_low_confidence(self):
        self.enable()
        self.record(player_id=101,**{**RETAIN,**CONTEXT,
            "board_enabled":True,"exceptional_offer_pct":175})
        set_initial_confidence(self.db,career_id="career-a",club_id=1,value=20)
        low=self.preview(player_id=101,seller_id=1,fee=17_000_000)
        self.assertEqual(low["board_decision"],"direct_sale")
        for n in range(4):
            record_board_event(self.db,career_id="career-a",club_id=1,
                event_key=f"earned-{n}",event_type="objective_exceeded",
                event_date="2026-10-14",source_note="Recorded hypothetical season performance")
        high=self.preview(player_id=101,seller_id=1,fee=17_000_000)
        self.assertEqual(high["board_decision"],"no_intervention")
        self.assertEqual(high["decision"],"reject")

    def test_external_seller_board_needs_explicit_manager_trust(self):
        self.enable()
        self.record(**{**RETAIN,**CONTEXT,
            "assumed_manager_trust":"unknown",
            "board_enabled":True,"exceptional_offer_pct":200})
        self.assertEqual(self.preview(fee=40_000_000)["decision"],"review")

    def test_recorded_external_seller_board_can_intervene(self):
        self.enable()
        self.record(**{**RETAIN,**CONTEXT,
            "board_enabled":True,"exceptional_offer_pct":150})
        outcome=self.preview(fee=20_000_000)
        self.assertEqual(outcome["board_decision"],"direct_sale")
        self.assertEqual(outcome["decision"],"accept")

    def test_source_scenario_cannot_change_historical_state(self):
        self.enable()
        self.record()
        self.assertFalse(self.record())
        with self.assertRaises(ValueError):
            self.record(market_value=15_000_000)

    def test_wrong_registration_protected(self):
        with self.assertRaises(ValueError):
            record_seller_assumptions(self.db,career_id="career-a",
                player_id=999,**NORMAL)

    def test_sporting_board_vetoes_mgr_approved_key_player_sale_at_final_gate(self):
        from world_career_transfer_protocol import (initialize_transfer_protocol,
            enable_transfer_protocol,final_board_exception)
        self.enable()
        initialize_transfer_protocol(self.db)
        enable_transfer_protocol(self.db,career_id="career-a",
            activation_note="Explicit seller board late-veto test")
        self.record(player_id=101,market_value=10_000_000,
            contract_years=2,squad_role="key_player",transfer_listed=False,
            player_wants_exit=False,financial_state="stable",
            replacement="difficult",seller_stance="sell",
            board_enabled=True,exceptional_offer_pct=200,
            financial_objective="balanced",ambition="continental",
            ownership_priority="sporting",assumed_manager_trust="unknown",
            source_note="Sporting ownership refuses low-fee sale of key player")
        set_initial_confidence(self.db,career_id="career-a",club_id=1,value=50)
        # Club's manager would accept an 18m fee, but the board protects a
        # key player when there is no replacement and European ambitions.
        with patch("world_careers._player_reference",
                   return_value=(10_000_000,88)):
            oid=self.bid(player_id=101,buying_club_id=2,
                fee=18_000_000,key="late-selling-board-veto")
            self.assertEqual(self.db.execute("""SELECT status FROM world_career_offers
                WHERE offer_id=?""",(oid,)).fetchone()[0],
                "accepted_pending_contract")
            with self.assertRaisesRegex(ValueError,"Exceptional seller-board veto"):
                final_board_exception(self.db,career_id="career-a",
                    offer_id=oid,weekly_wage=50_000)
        self.assertEqual(self.db.execute("""SELECT club_id FROM world_career_registrations
            WHERE career_id='career-a' AND player_id=101""").fetchone()[0],1)

    def test_board_disabled_never_forces_sale(self):
        self.enable()
        self.record(**{**RETAIN,**CONTEXT,
            "board_enabled":False,"exceptional_offer_pct":100})
        self.assertEqual(self.preview(fee=100_000_000)["decision"],"reject")

    def test_seller_acceptance_cannot_bypass_buyer_budget(self):
        self.enable()
        self.record(transfer_listed=True,contract_years=1,
                    squad_role="fringe",seller_stance="sell")
        self.db.execute("""UPDATE world_career_club_ledger
            SET transfer_budget=7000000 WHERE career_id='career-a' AND club_id=1""")
        self.db.commit()
        count=self.db.execute("SELECT COUNT(*) FROM world_career_offers").fetchone()[0]
        with self.assertRaisesRegex(ValueError,"unreserved transfer budget"):
            self.bid(fee=8_000_000)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM world_career_offers").fetchone()[0],count)

    def test_after_activation_no_double_spending_from_bid(self):
        self.enable()
        self.record()
        before=self.db.execute("SELECT committed_fees FROM world_career_club_ledger WHERE career_id='career-a' AND club_id=1").fetchone()[0]
        oid=self.bid()
        after=self.db.execute("SELECT committed_fees FROM world_career_club_ledger WHERE career_id='career-a' AND club_id=1").fetchone()[0]
        self.assertEqual(before,after)
        self.assertIsNotNone(offer_decision(self.db,oid))

if __name__=="__main__":
    unittest.main()

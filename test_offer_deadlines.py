"""Finite buyer patience: isolated transfer-window regression scenarios.

Run with python -m unittest -v test_offer_deadlines
All clubs/players are small fictional fixtures; no user career is touched.
"""
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch

from test_career_selling import career_fixture
from world_preseason_window import (
    initialise_preseason_windows,start_preseason_window,
    attach_offer_to_window,window_snapshot,
)
from world_career_incoming import initialize_incoming_approaches
from world_live_market import initialise_live_market,manager_respond
from world_offer_deadlines import (
    CONFIRM_SECONDS,EXTENSION_SECONDS,reconcile_confirmations,
    confirmation_state,request_confirmation_extension,require_live_confirmation,
)
from world_careers import budget_remaining

T0=datetime(2026,10,16,12,0,tzinfo=timezone.utc)
C="career-a"


class BuyerConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.db=career_fixture()
        initialise_preseason_windows(self.db)
        initialize_incoming_approaches(self.db)
        initialise_live_market(self.db)
        self.db.execute("""CREATE TABLE world_career_agent_terms(
            offer_id INTEGER PRIMARY KEY,career_id TEXT,status TEXT,
            role_promise TEXT,proposed_wage_weekly INTEGER)""")
        self.db.execute("""UPDATE world_career_offers
            SET player_id=101,buying_club_id=2,selling_club_id=1,
                status='accepted_pending_contract',offered_fee=2000000,
                demanded_fee=NULL,agreement_date='2026-10-14' WHERE offer_id=1""")
        self.db.execute("""INSERT INTO world_career_agent_terms
            VALUES(1,?,'accepted','regular_starter',20000)""",(C,))
        self.db.execute("""INSERT INTO world_career_incoming_approaches
            (offer_id,career_id,status,attempts,decision_reason,policy_version)
            VALUES(1,?,'terms_accepted',1,'Player accepted','test')""",(C,))
        self.db.commit()
        start_preseason_window(self.db,career_id=C,now=T0)
        attach_offer_to_window(self.db,career_id=C,offer_id=1,
                               now=T0+timedelta(seconds=1))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def at(self,minutes=1,seconds=0):
        return T0+timedelta(minutes=minutes,seconds=seconds)

    def clock(self,minutes=1,seconds=0):
        return confirmation_state(self.db,career_id=C,offer_id=1,
                                  now=self.at(minutes,seconds))

    def activate(self):
        return reconcile_confirmations(self.db,career_id=C,now=self.at(1))

    def test_no_early_signing_and_four_minute_clock(self):
        self.db.execute("""UPDATE world_career_incoming_approaches
             SET status='agent_counter' WHERE offer_id=1""")
        self.db.commit()
        self.assertEqual(self.activate(),{"opened":0,"expired":0})
        self.assertIsNone(self.clock())
        self.db.execute("""UPDATE world_career_incoming_approaches
             SET status='terms_accepted' WHERE offer_id=1""")
        self.db.commit()
        self.assertEqual(self.activate(),{"opened":1,"expired":0})
        state=self.clock()
        self.assertEqual(state["remaining_seconds"],CONFIRM_SECONDS)
        self.assertEqual(state["initial_deadline_at"],state["deadline_at"])
        self.assertEqual(self.activate(),{"opened":0,"expired":0})
        self.assertEqual(self.clock()["deadline_at"],state["deadline_at"])

    def test_buyer_withdraws_after_four_minutes_without_player_moving(self):
        self.activate()
        original=self.db.execute("""SELECT club_id FROM world_career_registrations
            WHERE career_id=? AND player_id=101""",(C,)).fetchone()[0]
        reserved=budget_remaining(self.db,C,2)
        self.assertEqual(self.clock(4,59)["remaining_seconds"],1)
        self.assertEqual(reconcile_confirmations(
            self.db,career_id=C,now=self.at(5)),{"opened":0,"expired":1})
        self.assertEqual(self.db.execute("""SELECT status
            FROM world_career_offers WHERE offer_id=1""").fetchone()[0],"withdrawn")
        self.assertEqual(self.db.execute("""SELECT club_id FROM world_career_registrations
            WHERE career_id=? AND player_id=101""",(C,)).fetchone()[0],original)
        self.assertEqual(budget_remaining(self.db,C,2),reserved+2000000)
        self.assertEqual(reconcile_confirmations(
            self.db,career_id=C,now=self.at(6))["expired"],0)
        self.assertEqual(self.db.execute("""SELECT COUNT(*) FROM world_career_offer_events
            WHERE offer_id=1 AND event_type='ai_buyer_confirmation_expired'""").fetchone()[0],1)

    def test_club_can_grant_one_two_minute_extension(self):
        self.activate()
        with patch("world_offer_deadlines._club_grants_extension",return_value=True):
            response=request_confirmation_extension(
                self.db,career_id=C,offer_id=1,now=self.at(4))
        self.assertTrue(response["accepted"])
        self.assertEqual(self.clock(4)["extension_requested"],1)
        self.assertEqual(self.clock(4)["extension_granted"],1)
        self.assertEqual(self.clock(4)["remaining_seconds"],180)
        with self.assertRaisesRegex(ValueError,"already requested"):
            request_confirmation_extension(
                self.db,career_id=C,offer_id=1,now=self.at(4,seconds=1))
        self.assertEqual(reconcile_confirmations(
            self.db,career_id=C,now=self.at(5))["expired"],0)
        self.assertEqual(reconcile_confirmations(
            self.db,career_id=C,now=self.at(7))["expired"],1)

    def test_club_can_refuse_extension_original_deadline_remains(self):
        self.activate()
        before=self.clock()["deadline_at"]
        with patch("world_offer_deadlines._club_grants_extension",return_value=False):
            response=request_confirmation_extension(
                self.db,career_id=C,offer_id=1,now=self.at(2))
        self.assertFalse(response["accepted"])
        self.assertEqual(self.clock()["deadline_at"],before)
        self.assertEqual(self.clock()["extension_requested"],1)
        self.assertEqual(self.clock()["extension_granted"],0)
        with self.assertRaisesRegex(ValueError,"already requested"):
            request_confirmation_extension(
                self.db,career_id=C,offer_id=1,now=self.at(3))

    def test_signing_denied_after_buying_club_expires(self):
        self.activate()
        require_live_confirmation(self.db,career_id=C,offer_id=1,now=self.at(4))
        with self.assertRaisesRegex(ValueError,"deadline|expired"):
            require_live_confirmation(self.db,career_id=C,offer_id=1,now=self.at(5))
        self.assertEqual(self.db.execute("""SELECT status FROM world_career_offers
            WHERE offer_id=1""").fetchone()[0],"withdrawn")
        with self.assertRaises(ValueError):
            manager_respond(self.db,career_id=C,offer_id=1,
                            action="finalise",now=self.at(6))

    def test_timer_never_exceeds_overall_thirty_minute_deadline(self):
        self.db.execute("""UPDATE world_career_incoming_approaches
            SET status='agent_counter' WHERE offer_id=1""")
        self.db.commit()
        self.activate()
        self.db.execute("""UPDATE world_career_incoming_approaches
            SET status='terms_accepted' WHERE offer_id=1""")
        self.db.commit()
        started=reconcile_confirmations(self.db,career_id=C,now=self.at(28))
        self.assertEqual(started["opened"],1)
        self.assertEqual(self.clock(28)["remaining_seconds"],120)
        with patch("world_offer_deadlines._club_grants_extension",return_value=True):
            extension=request_confirmation_extension(
                self.db,career_id=C,offer_id=1,now=self.at(29))
        self.assertFalse(extension["accepted"])
        self.assertEqual(self.clock(29)["remaining_seconds"],60)
        self.assertEqual(self.clock(29)["extension_requested"],1)

    def test_signed_transfer_is_not_withdrawn_when_clock_later_expires(self):
        self.activate()
        self.db.execute("""UPDATE world_career_offers SET status='agreed_future'
            WHERE offer_id=1""")
        self.db.commit()
        reconciled=reconcile_confirmations(self.db,career_id=C,now=self.at(8))
        self.assertEqual(reconciled["expired"],0)
        self.assertEqual(self.db.execute("""SELECT status FROM world_career_offers
            WHERE offer_id=1""").fetchone()[0],"agreed_future")
        self.assertIsNone(self.clock(8)["expired_at"])

    def test_manager_cancelled_offer_does_not_restart_or_expire(self):
        self.activate()
        self.db.execute("""UPDATE world_career_offers SET status='withdrawn'
            WHERE offer_id=1""")
        self.db.commit()
        reconciled=reconcile_confirmations(self.db,career_id=C,now=self.at(12))
        self.assertEqual(reconciled,{"opened":0,"expired":0})
        self.assertEqual(self.db.execute("""SELECT status FROM world_career_offers
            WHERE offer_id=1""").fetchone()[0],"withdrawn")
        self.assertEqual(self.db.execute("""SELECT COUNT(*) FROM world_career_offer_events
            WHERE offer_id=1 AND event_type='ai_buyer_confirmation_expired'""").fetchone()[0],0)

    def test_countering_a_second_bid_does_not_reset_first_buyers_timer(self):
        self.activate()
        expiry=self.clock()["deadline_at"]
        self.db.execute("INSERT INTO world_clubs(club_id) VALUES(3)")
        self.db.execute("""INSERT INTO world_career_club_ledger
            (career_id,club_id,transfer_budget,weekly_wage_budget,
             committed_fees,committed_wages)
            VALUES(?,3,15000000,150000,0,0)""",(C,))
        self.db.execute("""INSERT INTO world_career_offers
            (offer_id,career_id,request_key,player_id,buying_club_id,
             selling_club_id,status,offered_fee,agreement_date,economy_version)
            VALUES(35,?,'second-buyer',101,3,1,'proposed',2500000,
                   '2026-10-14','prototype-v1')""",(C,))
        attach_offer_to_window(self.db,career_id=C,offer_id=35,
                               now=self.at(1,seconds=1))
        self.db.commit()
        result=manager_respond(self.db,career_id=C,offer_id=35,
            action="counter",counter_fee=3000000,now=self.at(2))
        self.assertIn("Counteroffer",result)
        self.assertEqual(self.clock(2)["deadline_at"],expiry)
        self.assertEqual(self.db.execute("""SELECT status FROM world_career_offers
            WHERE offer_id=1""").fetchone()[0],"accepted_pending_contract")
        self.assertEqual(self.db.execute("""SELECT status FROM world_career_offers
            WHERE offer_id=35""").fetchone()[0],"countered")

if __name__=="__main__":
    unittest.main()

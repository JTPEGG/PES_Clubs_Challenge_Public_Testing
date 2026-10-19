"""Isolated 30-minute real-clock transfer-window and registration regressions."""
import sqlite3
import unittest
from datetime import datetime,timedelta,timezone
from test_career_selling import career_fixture
from world_preseason_window import (
    WINDOW_SECONDS,initialise_preseason_windows,window_snapshot,
    start_preseason_window,assert_window_allows_negotiation,
    attach_offer_to_window,finalise_preseason_window,
)

T0=datetime(2026,10,15,12,0,0,tzinfo=timezone.utc)

class PreseasonWindowTests(unittest.TestCase):
    def setUp(self):
        self.db=career_fixture()
        self.db.execute("""CREATE TABLE IF NOT EXISTS world_career_agent_terms(
            offer_id INTEGER PRIMARY KEY,
            career_id TEXT, status TEXT, proposed_wage_weekly INTEGER)""")
        # career_fixture deliberately models an early prototype offer table
        # without its modern effective_date field. Add only what the
        # registration-specific test uses.
        cols={r[1] for r in self.db.execute("PRAGMA table_info(world_career_offers)")}
        if "effective_date" not in cols:
            self.db.execute("""ALTER TABLE world_career_offers
                ADD COLUMN effective_date TEXT""")
        initialise_preseason_windows(self.db)

    def tearDown(self):
        self.db.close()

    def open(self,t=T0):
        return start_preseason_window(self.db,career_id="career-a",now=t)

    def snapshot(self,t):
        return window_snapshot(self.db,career_id="career-a",now=t)

    def insert_offer(self,offer_id,player_id,buyer,seller,fee,wage,status,
                     key=None):
        self.db.execute("""INSERT INTO world_career_offers
            (offer_id,career_id,request_key,player_id,buying_club_id,
             selling_club_id,offered_fee,offered_wage_weekly,status,
             agreement_date,economy_version)
            VALUES(?,'career-a',?,?,?,?,?,?,?,?,?)""",
            (offer_id,key or f"window-{offer_id}",player_id,buyer,seller,
             fee,wage,status,"2026-07-01","prototype-v1"))
        if status=="agreed_future":
            self.db.execute("""INSERT INTO world_career_agent_terms
                (offer_id,career_id,status,proposed_wage_weekly)
                VALUES(?,'career-a','accepted',?)""",(offer_id,wage))
        attach_offer_to_window(self.db,career_id="career-a",offer_id=offer_id,
                               now=T0+timedelta(minutes=1))
        self.db.commit()

    def test_immutable_real_time_30_minute_window(self):
        self.assertEqual(self.snapshot(T0)["state"],"not_started")
        row=self.open()
        self.assertEqual(row["state"],"open")
        self.assertEqual(row["remaining_seconds"],WINDOW_SECONDS)
        self.assertEqual(row["deadline_at"],"2026-10-15T12:30:00+00:00")
        self.assertEqual(self.snapshot(T0+timedelta(minutes=10))["remaining_seconds"],1200)
        self.assertEqual(self.open(T0+timedelta(minutes=20))["deadline_at"],row["deadline_at"])
        self.assertEqual(self.snapshot(T0+timedelta(minutes=30))["state"],"deadline_reached")
        self.assertEqual(self.snapshot(T0+timedelta(minutes=40))["remaining_seconds"],0)
        with self.assertRaisesRegex(ValueError,"deadline"):
            assert_window_allows_negotiation(self.db,career_id="career-a",
                now=T0+timedelta(minutes=30))

    def test_start_not_permitted_without_career_or_for_arbitrary_second_season(self):
        with self.assertRaisesRegex(ValueError,"verified season-transition"):
            start_preseason_window(self.db,career_id="career-a",
                                   season_index=2,now=T0)
        with self.assertRaises(ValueError):
            start_preseason_window(self.db,career_id="unknown",now=T0)
        with self.assertRaises(ValueError):
            start_preseason_window(self.db,career_id="career-a",
                                   now=datetime(2026,10,15,12))
        self.assertEqual(self.snapshot(T0)["state"],"not_started")

    def test_page_refresh_never_starts_or_closes_window(self):
        self.open()
        for n in range(20):
            self.snapshot(T0+timedelta(minutes=31+n))
        self.assertEqual(self.db.execute("""SELECT status FROM
            world_career_preseason_windows WHERE career_id='career-a'""").fetchone()[0],
            "open")

    def test_cannot_finalize_before_deadline(self):
        self.open()
        with self.assertRaisesRegex(ValueError,"before deadline"):
            finalise_preseason_window(self.db,career_id="career-a",
                now=T0+timedelta(minutes=29,seconds=59))
        self.assertEqual(self.snapshot(T0)["state"],"open")

    def test_signed_deal_moves_once_and_charges_fee_and_wage_once(self):
        self.open()
        self.insert_offer(20,102,1,2,3_250_000,17_500,"agreed_future")
        original=self.db.execute("""SELECT committed_fees,committed_wages
            FROM world_career_club_ledger WHERE career_id='career-a'
            AND club_id=1""").fetchone()
        before=self.db.execute("""SELECT club_id FROM world_career_registrations
            WHERE career_id='career-a' AND player_id=102""").fetchone()[0]
        self.assertEqual(before,2)
        result=finalise_preseason_window(self.db,career_id="career-a",
                 now=T0+timedelta(minutes=30))
        self.assertEqual(result["registered"],1)
        self.assertEqual(result["expired"],0)
        updated=self.db.execute("""SELECT club_id FROM world_career_registrations
            WHERE career_id='career-a' AND player_id=102""").fetchone()[0]
        self.assertEqual(updated,1)
        ledger=self.db.execute("""SELECT committed_fees,committed_wages
            FROM world_career_club_ledger WHERE career_id='career-a'
            AND club_id=1""").fetchone()
        self.assertEqual(ledger,(original[0]+3_250_000,original[1]+17_500))
        self.assertEqual(self.db.execute("""SELECT status,effective_date
            FROM world_career_offers WHERE offer_id=20""").fetchone(),
            ("completed","2026-08-01"))
        self.assertTrue(finalise_preseason_window(self.db,career_id="career-a",
                 now=T0+timedelta(hours=2))["already_closed"])
        self.assertEqual(ledger,self.db.execute("""SELECT committed_fees,committed_wages
            FROM world_career_club_ledger WHERE career_id='career-a'
            AND club_id=1""").fetchone())
        self.assertEqual(self.db.execute("""SELECT COUNT(*)
            FROM world_career_preseason_registration_events""").fetchone()[0],1)
        self.assertEqual(self.db.execute("""SELECT club_id FROM world_career_registrations
            WHERE career_id='career-b' AND player_id=101""").fetchone()[0],1)

    def test_unfinished_deals_expire_never_register_or_spend(self):
        self.open()
        self.insert_offer(20,102,1,2,3_250_000,None,"proposed")
        result=finalise_preseason_window(self.db,career_id="career-a",
                 now=T0+timedelta(minutes=31))
        self.assertEqual(result["registered"],0)
        self.assertEqual(result["expired"],1)
        self.assertEqual(self.db.execute("""SELECT club_id FROM world_career_registrations
            WHERE career_id='career-a' AND player_id=102""").fetchone()[0],2)
        self.assertEqual(self.db.execute("SELECT status FROM world_career_offers WHERE offer_id=20").fetchone()[0],"withdrawn")
        self.assertEqual(self.db.execute("""SELECT COUNT(*)
            FROM world_career_preseason_registration_events""").fetchone()[0],0)

    def test_pre_window_legacy_offers_are_preserved(self):
        self.open()
        original=self.db.execute("SELECT status FROM world_career_offers WHERE offer_id=2").fetchone()[0]
        finalise_preseason_window(self.db,career_id="career-a",
                 now=T0+timedelta(minutes=31))
        self.assertEqual(self.db.execute("SELECT status FROM world_career_offers WHERE offer_id=2").fetchone()[0],original)
        self.assertEqual(self.db.execute("""SELECT COUNT(*)
            FROM world_career_preseason_window_offers""").fetchone()[0],0)

    def test_cross_career_and_late_offer_cannot_be_added(self):
        self.open()
        self.insert_offer(20,102,1,2,3_250_000,None,"proposed")
        with self.assertRaises(ValueError):
            attach_offer_to_window(self.db,career_id="career-b",offer_id=20,now=T0)
        with self.assertRaisesRegex(ValueError,"deadline"):
            attach_offer_to_window(self.db,career_id="career-a",offer_id=20,
                now=T0+timedelta(minutes=30))
        self.assertFalse(attach_offer_to_window(self.db,career_id="career-a",
                    offer_id=20,now=T0+timedelta(minutes=3)))

    def test_inconsistent_signed_terms_fail_atomically(self):
        self.open()
        self.insert_offer(20,102,1,2,3_250_000,17_500,"agreed_future")
        self.db.execute("""UPDATE world_career_agent_terms
            SET status='countered' WHERE offer_id=20""")
        self.db.commit()
        with self.assertRaisesRegex(ValueError,"player/agent consent"):
            finalise_preseason_window(self.db,career_id="career-a",
                now=T0+timedelta(minutes=31))
        self.assertEqual(self.db.execute("SELECT status FROM world_career_offers WHERE offer_id=20").fetchone()[0],"agreed_future")
        self.assertEqual(self.db.execute("SELECT club_id FROM world_career_registrations WHERE career_id='career-a' AND player_id=102").fetchone()[0],2)
        self.assertEqual(self.db.execute("SELECT status FROM world_career_preseason_windows").fetchone()[0],"open")

    def test_existing_offer_submission_is_blocked_after_real_deadline(self):
        from world_careers import propose_offer
        # An expired window cannot be bypassed by calling the old offer
        # engine directly, even if the manager knows its POST endpoint.
        start_preseason_window(self.db,career_id="career-a",
             now=datetime.now(timezone.utc)-timedelta(minutes=31))
        with self.assertRaisesRegex(ValueError,"Transfer deadline passed"):
            propose_offer(self.db,career_id="career-a",
                request_key="late-window-bypass",player_id=102,
                buying_club_id=1,offered_fee=4_000_000,
                agreement_date="2026-10-15")
        self.assertIsNone(self.db.execute("""SELECT offer_id
            FROM world_career_offers WHERE request_key='late-window-bypass'""").fetchone())

    def test_zero_transfer_window_still_closes_and_freezes(self):
        self.open()
        done=finalise_preseason_window(self.db,career_id="career-a",
            now=T0+timedelta(minutes=30))
        self.assertEqual(done["registered"],0)
        self.assertEqual(self.snapshot(T0+timedelta(minutes=40))["state"],"closed")
        with self.assertRaisesRegex(ValueError,"deadline"):
            assert_window_allows_negotiation(self.db,career_id="career-a",
                now=T0+timedelta(minutes=40))

if __name__=="__main__":
    unittest.main()

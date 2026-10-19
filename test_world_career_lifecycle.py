"""Isolated loan/expiry lifecycle regression tests (fictional fixtures)."""
import sqlite3
import unittest
from datetime import datetime,timezone

from world_preseason_window import initialise_preseason_windows,start_preseason_window
from world_career_lifecycle import (
    initialize_career_lifecycle,agree_loan,activate_agreed_loans,
    reconcile_verified_season_end,
)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:",isolation_level=None)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE world_clubs(club_id INTEGER PRIMARY KEY);
            CREATE TABLE world_players(player_id INTEGER PRIMARY KEY);
            CREATE TABLE world_career_saves(
                career_id TEXT PRIMARY KEY, state TEXT,
                pes_lock_date TEXT, next_summer_date TEXT);
            CREATE TABLE world_career_registrations(
                career_id TEXT,player_id INTEGER,club_id INTEGER,
                PRIMARY KEY(career_id,player_id));
            CREATE TABLE world_career_club_ledger(
                career_id TEXT,club_id INTEGER,transfer_budget INTEGER,
                weekly_wage_budget INTEGER,committed_fees INTEGER DEFAULT 0,
                committed_wages INTEGER DEFAULT 0);
            CREATE TABLE world_career_offers(
                offer_id INTEGER PRIMARY KEY,career_id TEXT,player_id INTEGER,status TEXT);
            CREATE TABLE world_career_reputation_seasons(
                career_id TEXT,season_index INTEGER);
            INSERT INTO world_clubs VALUES (1),(2);
            INSERT INTO world_players VALUES (101),(102);
            INSERT INTO world_career_saves
                VALUES('case','sandbox','2026-08-01','2027-07-01');
            INSERT INTO world_career_registrations
                VALUES('case',101,1),('case',102,1);
            INSERT INTO world_career_club_ledger VALUES
                ('case',1,10000000,200000,0,0),
                ('case',2,10000000,200000,0,0);
        """)
        initialise_preseason_windows(self.db)
        initialize_career_lifecycle(self.db)
        self.db.execute("""INSERT INTO world_career_contract_snapshots
            VALUES('case',101,1,20000,'2028-06-30','open','verified-test')""")
        self.db.execute("""INSERT INTO world_career_contract_snapshots
            VALUES('case',102,1,15000,'2027-06-30','unwilling','verified-test')""")
        self.start=datetime(2026,7,1,12,tzinfo=timezone.utc)
        start_preseason_window(self.db,career_id="case",now=self.start)

    def tearDown(self):
        self.db.close()

    def loan(self,**kwargs):
        return agree_loan(self.db,career_id="case",player_id=101,
            borrower_club_id=2,loan_fee_gbp=100_000,
            borrower_wage_share_pct=50,
            lender_approved=True,borrower_approved=True,
            player_approved=True,board_approved=True,now=self.start,**kwargs)

    def test_no_unilateral_loan(self):
        with self.assertRaisesRegex(ValueError,"consent"):
            agree_loan(self.db,career_id="case",player_id=101,
                borrower_club_id=2,now=self.start)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM world_career_loan_agreements").fetchone()[0],0)

    def test_register_and_return_loan_without_doubling_wages(self):
        lid=self.loan()
        with self.assertRaises(sqlite3.IntegrityError):
            self.loan()
        self.db.execute("BEGIN IMMEDIATE")
        self.assertEqual(activate_agreed_loans(self.db,career_id="case",
                                                effective_date="2026-08-01"),1)
        self.db.commit()
        self.assertEqual(activate_agreed_loans(self.db,career_id="case",
                                                effective_date="2026-08-01"),0)
        self.assertEqual(self.db.execute("""SELECT club_id FROM
            world_career_registrations WHERE player_id=101""").fetchone()[0],2)
        self.assertEqual(self.db.execute("""SELECT committed_wages FROM
            world_career_club_ledger WHERE club_id=2""").fetchone()[0],10000)
        with self.assertRaisesRegex(ValueError,"season completion"):
            reconcile_verified_season_end(self.db,career_id="case",
                season_index=1,as_of="2027-07-01")
        self.db.execute("""UPDATE world_career_preseason_windows
            SET status='closed',closed_at='2026-07-01T12:30:00+00:00'
            WHERE career_id='case'""")
        self.db.execute("INSERT INTO world_career_reputation_seasons VALUES('case',1)")
        result=reconcile_verified_season_end(self.db,career_id="case",
            season_index=1,as_of="2027-07-01")
        self.assertEqual(result["loans_returned"],1)
        self.assertEqual(result["contracts_expired"],1)
        self.assertEqual(self.db.execute("""SELECT club_id FROM
            world_career_registrations WHERE player_id=101""").fetchone()[0],1)
        self.assertIsNone(self.db.execute("""SELECT 1 FROM
            world_career_registrations WHERE player_id=102""").fetchone())
        self.assertEqual(self.db.execute("""SELECT committed_wages FROM
            world_career_club_ledger WHERE club_id=2""").fetchone()[0],0)
        self.assertEqual(reconcile_verified_season_end(self.db,career_id="case",
            season_index=1,as_of="2027-07-01")["loans_returned"],0)


if __name__=="__main__":
    unittest.main()

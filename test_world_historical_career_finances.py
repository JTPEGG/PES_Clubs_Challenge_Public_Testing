"""Source-backed initial loan + payroll career lifecycle integration regression.

No production DB, fake original wage claims, or live career mutations.
"""
import sqlite3
import unittest
from unittest.mock import patch

from world_career_lifecycle import (
    initialize_career_lifecycle,seed_career_contracts,reconcile_verified_season_end
)
from world_historical_career_finances import seed_existing_loans_and_payroll


def make_db(*, expiry="2021-06-30", parent_budget=3000, borrower_budget=2500):
    conn=sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
      CREATE TABLE world_datasets(dataset_id TEXT PRIMARY KEY);
      CREATE TABLE world_players(player_id INTEGER PRIMARY KEY);
      CREATE TABLE world_clubs(club_id INTEGER PRIMARY KEY);
      CREATE TABLE world_career_saves(
         career_id TEXT PRIMARY KEY,dataset_id TEXT,
         state TEXT NOT NULL DEFAULT 'sandbox',
         next_summer_date TEXT NOT NULL,pes_lock_date TEXT NOT NULL
      );
      CREATE TABLE world_career_registrations(
         career_id TEXT NOT NULL,player_id INTEGER NOT NULL,
         club_id INTEGER NOT NULL, PRIMARY KEY(career_id,player_id)
      );
      CREATE TABLE world_career_club_ledger(
         career_id TEXT NOT NULL,club_id INTEGER NOT NULL,
         weekly_wage_budget INTEGER NOT NULL,
         committed_wages INTEGER NOT NULL DEFAULT 0,
         PRIMARY KEY(career_id,club_id)
      );
      CREATE TABLE world_dataset_contract_snapshots(
         dataset_id TEXT NOT NULL,player_id INTEGER NOT NULL,
         club_id INTEGER NOT NULL,weekly_wage_gbp INTEGER,
         expires_on TEXT,renewal_status TEXT NOT NULL,
         source_name TEXT NOT NULL,PRIMARY KEY(dataset_id,player_id)
      );
      CREATE TABLE world_career_reputation_seasons(
         career_id TEXT NOT NULL,season_index INTEGER NOT NULL,
         PRIMARY KEY(career_id,season_index)
      );
      INSERT INTO world_datasets VALUES ('historical_2020');
      INSERT INTO world_players VALUES (1),(2);
      INSERT INTO world_clubs VALUES (10),(20);
      INSERT INTO world_career_saves VALUES
          ('new_career','historical_2020','sandbox','2020-07-01','2019-08-01');
      INSERT INTO world_career_registrations VALUES
          ('new_career',1,20),('new_career',2,20);
      INSERT INTO world_career_reputation_seasons VALUES('new_career',1);
    """)
    conn.execute("""INSERT INTO world_career_club_ledger
      (career_id,club_id,weekly_wage_budget) VALUES ('new_career',10,?)""",
      (parent_budget,))
    conn.execute("""INSERT INTO world_career_club_ledger
      (career_id,club_id,weekly_wage_budget) VALUES ('new_career',20,?)""",
      (borrower_budget,))
    conn.execute("""INSERT INTO world_dataset_contract_snapshots
      VALUES('historical_2020',1,10,1000,?,'unknown','source_or_game_estimate')""",
      (expiry,))
    conn.execute("""INSERT INTO world_dataset_contract_snapshots
      VALUES('historical_2020',2,20,500,'2022-06-30','unknown','source_or_game_estimate')""")
    initialize_career_lifecycle(conn)
    conn.execute("""INSERT INTO world_dataset_historical_finance_policy
      VALUES('historical_2020','historical-wage-and-loan-v1','source_and_model')""")
    conn.execute("""INSERT INTO world_dataset_initial_loans
      VALUES('historical_2020',1,20,10,'2020-06-30',50,'source_parent_game_return')""")
    conn.commit()
    return conn


class InitialHistoricalLoanTests(unittest.TestCase):
    def _setup(self,db):
        count=seed_career_contracts(db,career_id="new_career",dataset_id="historical_2020")
        self.assertEqual(count,2)
        result=seed_existing_loans_and_payroll(
            db,career_id="new_career",dataset_id="historical_2020",
            pes_lock_date="2019-08-01",next_summer_date="2020-07-01")
        self.assertTrue(result["opted_in"])
        self.assertEqual(result["initial_loans"],1)
        self.assertEqual(result["starting_payroll_weekly"],1500)

    def test_loan_starts_active_and_payroll_split_once(self):
        with make_db() as db:
            self._setup(db)
            self.assertEqual(dict(db.execute("""SELECT club_id,committed_wages
              FROM world_career_club_ledger""").fetchall()),{10:500,20:1000})
            self.assertEqual(db.execute("""SELECT parent_club_id,borrower_club_id,
              wage_commitment_gbp,status,return_date FROM world_career_loan_agreements"""
              ).fetchone(),(10,20,500,"active","2020-06-30"))
            self.assertEqual(db.execute("""SELECT club_id FROM
              world_career_registrations WHERE player_id=1""").fetchone()[0],20)

    def test_no_season_evidence_means_no_return(self):
        with make_db() as db:
            self._setup(db)
            db.execute("DELETE FROM world_career_reputation_seasons")
            with self.assertRaises(ValueError):
                with patch("world_preseason_window.window_snapshot",
                           return_value={"state":"closed"}):
                    reconcile_verified_season_end(db,career_id="new_career",
                          season_index=1,as_of="2020-07-01")
            self.assertEqual(db.execute("SELECT status FROM world_career_loan_agreements"
                                        ).fetchone()[0],"active")

    def test_verified_end_returns_once_and_reallocates_parent_payroll(self):
        with make_db() as db:
            self._setup(db)
            db.commit()
            with patch("world_preseason_window.window_snapshot",
                       return_value={"state":"closed"}):
                result=reconcile_verified_season_end(db,career_id="new_career",
                    season_index=1,as_of="2020-07-01")
                again=reconcile_verified_season_end(db,career_id="new_career",
                    season_index=1,as_of="2020-07-01")
            self.assertEqual(result["loans_returned"],1)
            self.assertEqual(again["loans_returned"],0)
            self.assertEqual(db.execute("""SELECT club_id FROM
              world_career_registrations WHERE player_id=1""").fetchone()[0],10)
            self.assertEqual(dict(db.execute("""SELECT club_id,committed_wages
              FROM world_career_club_ledger""").fetchall()),{10:1000,20:500})

    def test_parent_contract_expires_after_loan_and_releases_payroll(self):
        with make_db(expiry="2020-06-30") as db:
            self._setup(db)
            db.commit()
            with patch("world_preseason_window.window_snapshot",
                       return_value={"state":"closed"}):
                result=reconcile_verified_season_end(db,career_id="new_career",
                    season_index=1,as_of="2020-07-01")
            self.assertEqual(result,{"loans_returned":1,"contracts_expired":1})
            self.assertIsNone(db.execute("""SELECT club_id FROM
              world_career_registrations WHERE player_id=1""").fetchone())
            self.assertEqual(dict(db.execute("""SELECT club_id,committed_wages
              FROM world_career_club_ledger""").fetchall()),{10:0,20:500})
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM
              world_career_free_agents WHERE player_id=1""").fetchone()[0],1)

    def test_inconsistent_parent_loan_refuses_to_seed(self):
        with make_db() as db:
            seed_career_contracts(db,career_id="new_career",dataset_id="historical_2020")
            db.execute("UPDATE world_dataset_initial_loans SET parent_club_id=20")
            with self.assertRaises(ValueError):
                seed_existing_loans_and_payroll(
                    db,career_id="new_career",dataset_id="historical_2020",
                    pes_lock_date="2019-08-01",next_summer_date="2020-07-01")

    def test_below_starting_payroll_budget_fails_closed(self):
        with make_db(parent_budget=100) as db:
            seed_career_contracts(db,career_id="new_career",dataset_id="historical_2020")
            with self.assertRaisesRegex(ValueError,"Starting payroll exceeds budget"):
                seed_existing_loans_and_payroll(
                    db,career_id="new_career",dataset_id="historical_2020",
                    pes_lock_date="2019-08-01",next_summer_date="2020-07-01")
            self.assertEqual(db.execute("""SELECT SUM(committed_wages)
              FROM world_career_club_ledger""").fetchone()[0],0)


if __name__=="__main__":
    unittest.main()

"""Isolated regression checks for FC27 signed-sale transfer budget credits."""
import sqlite3
import unittest

from world_career_sale_proceeds import (
    credit_signed_sale, allocation_basis_points, FC27_DATASET, POLICY_VERSION,
)


class SignedSaleBudgetTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(":memory:")
        self.conn.execute("""CREATE TABLE world_career_saves(
            career_id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL)""")
        self.conn.execute("""CREATE TABLE world_career_club_ledger(
            career_id TEXT,club_id INTEGER,transfer_budget INTEGER NOT NULL,
            committed_fees INTEGER DEFAULT 0,PRIMARY KEY(career_id,club_id))""")
        self.conn.execute("""CREATE TABLE world_fc27_club_ai_context(
            dataset_id TEXT,club_id INTEGER,financial_pressure_index INTEGER,
            financial_pressure_band TEXT,operating_approach TEXT,
            PRIMARY KEY(dataset_id,club_id))""")
        self.conn.execute("""INSERT INTO world_career_saves VALUES(?,?)""",
                          ("test-career",FC27_DATASET))
        self.conn.executemany("""INSERT INTO world_career_club_ledger
            (career_id,club_id,transfer_budget) VALUES(?,?,?)""",
            [("test-career",1,5_000_000),("test-career",2,5_000_000)])
        self.conn.executemany("""INSERT INTO world_fc27_club_ai_context VALUES(?,?,?,?,?)""",
            [(FC27_DATASET,1,0,"stable","balanced"),
             (FC27_DATASET,2,100,"distress","cost_control")])
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def budget(self,club):
        return self.conn.execute("""SELECT transfer_budget
            FROM world_career_club_ledger WHERE career_id='test-career'
            AND club_id=?""",(club,)).fetchone()[0]

    def credit(self,club,offer=101,fee=10_000_000):
        return credit_signed_sale(self.conn,career_id="test-career",
             offer_id=offer,seller_club_id=club,gross_fee=fee)

    def test_healthy_club_can_reinvest_all_of_confirmed_sale(self):
        result=self.credit(1)
        self.assertEqual(result["basis_points"],10000)
        self.assertEqual(result["allocated"],10_000_000)
        self.assertEqual(self.budget(1),15_000_000)
        self.assertEqual(self.budget(2),5_000_000)

    def test_distressed_club_reinvests_half_and_retains_half(self):
        result=self.credit(2)
        self.assertEqual(result["basis_points"],5000)
        self.assertEqual(result["allocated"],5_000_000)
        self.assertEqual(result["withheld"],5_000_000)
        self.assertEqual(self.budget(2),10_000_000)

    def test_same_sale_never_credits_twice(self):
        self.credit(1)
        second=self.credit(1)
        self.assertFalse(second["credited_now"])
        self.assertEqual(self.budget(1),15_000_000)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM world_career_sale_budget_credits").fetchone()[0],1)

    def test_mismatched_repeat_is_rejected(self):
        self.credit(1)
        with self.assertRaises(ValueError):
            self.credit(1,fee=9_000_000)
        self.assertEqual(self.budget(1),15_000_000)

    def test_rollback_reverts_both_credit_and_budget(self):
        self.conn.execute("BEGIN IMMEDIATE")
        self.credit(1)
        self.conn.rollback()
        self.assertEqual(self.budget(1),5_000_000)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='world_career_sale_budget_credits'").fetchone()[0],0)

    def test_legacy_career_economy_is_untouched(self):
        self.conn.execute("UPDATE world_career_saves SET dataset_id='legacy' WHERE career_id='test-career'")
        self.assertIsNone(self.credit(1))
        self.assertEqual(self.budget(1),5_000_000)

    def test_unverified_financial_pressure_cannot_fabricate_reinvestment(self):
        with self.assertRaises(ValueError):
            allocation_basis_points(pressure_index=None,
               financial_pressure_band="stable",operating_approach="balanced")
        with self.assertRaises(ValueError):
            allocation_basis_points(pressure_index=101,
               financial_pressure_band="stable",operating_approach="balanced")

    def test_moderate_financial_pressure_has_intermediate_reinvestment(self):
        share=allocation_basis_points(pressure_index=55,
            financial_pressure_band="tight",operating_approach="balanced")
        self.assertGreater(share,5000)
        self.assertLessEqual(share,9000)


if __name__=="__main__":
    unittest.main()

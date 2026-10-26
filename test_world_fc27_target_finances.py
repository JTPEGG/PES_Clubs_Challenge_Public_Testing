"""Regression for affordability-aware autonomous FC27 targeting.

Model source valuations are identical to the actual offer engine. Forecast
affordability changes shortlist priority, not whether a club/player can agree.
"""
import sqlite3
import unittest

from world_fc27_target_finances import (
    shortlist_reference_values,prospective_purchase_fit)
from world_careers import _player_reference

FC27="fc27-warehouse-659-mens-2026-27"
SALE=dict(valid=True,first_choice=False,protected_rotation=False,
          sporting_risk=0)


class TargetFinanceTests(unittest.TestCase):
    def test_expensive_star_loses_priority_when_cash_is_short(self):
        cheap=prospective_purchase_fit(
            valuation=12_000_000,transfer_headroom=40_000_000,
            weekly_wage=35000,wage_headroom=120000,sale=SALE)
        costly=prospective_purchase_fit(
            valuation=38_000_000,transfer_headroom=40_000_000,
            weekly_wage=150000,wage_headroom=120000,sale=SALE)
        self.assertTrue(cheap["budget_plausible"])
        self.assertFalse(costly["budget_plausible"])
        self.assertGreater(cheap["score"],costly["score"])
        self.assertGreater(costly["plausible_fee_gbp"],38000000)
        # The expensive player's score is still finite: a remarkably
        # strong sporting advantage can outweigh this financial concern.
        self.assertGreater(costly["score"],-200)

    def test_strategic_sale_risk_increases_expected_cost_softly(self):
        ordinary=prospective_purchase_fit(
            valuation=40_000_000,transfer_headroom=56_000_000,
            weekly_wage=None,wage_headroom=200000,sale=SALE)
        protected=prospective_purchase_fit(
            valuation=40_000_000,transfer_headroom=56_000_000,
            weekly_wage=None,wage_headroom=200000,
            sale={**SALE,"first_choice":True,"protected_rotation":True,
                  "sporting_risk":100})
        self.assertGreater(protected["plausible_fee_gbp"],
                           ordinary["plausible_fee_gbp"])
        self.assertGreater(ordinary["score"],protected["score"])
        self.assertTrue(ordinary["budget_plausible"])
        self.assertFalse(protected["budget_plausible"])
        # Unknown wages stay unknown, never silently set to zero.
        self.assertIsNone(ordinary["source_wage_headroom_ratio"])

    def test_batched_source_value_equals_seller_offer_model(self):
        db=sqlite3.connect(":memory:")
        try:
            db.executescript("""
              CREATE TABLE world_dataset_rosters(
                 dataset_id TEXT,player_id INTEGER,club_id INTEGER);
              CREATE TABLE world_dataset_ratings(
                 dataset_id TEXT,player_id INTEGER,overall INTEGER);
              CREATE TABLE world_players(
                 player_id INTEGER,birth_date TEXT,primary_position TEXT);
              CREATE TABLE world_datasets(
                 dataset_id TEXT,source_date TEXT);
              CREATE TABLE world_dataset_contract_snapshots(
                 dataset_id TEXT,player_id INTEGER,weekly_wage_gbp INTEGER);
            """)
            db.execute("INSERT INTO world_datasets VALUES(?,?)",
                       (FC27,"2026-08-01"))
            for pid,rating,pos,birth,wage in (
                (1,86,"CB","2000-01-01",125000),
                (2,68,"CM","2006-05-10",None),
                (3,93,"ST","1999-02-20",270000)):
                db.execute("INSERT INTO world_players VALUES(?,?,?)",
                           (pid,birth,pos))
                db.execute("INSERT INTO world_dataset_ratings VALUES(?,?,?)",
                           (FC27,pid,rating))
                db.execute("INSERT INTO world_dataset_rosters VALUES(?,?,?)",
                           (FC27,pid,1))
                if wage is not None:
                    db.execute("""INSERT INTO world_dataset_contract_snapshots
                        VALUES(?,?,?)""",(FC27,pid,wage))
            batch=shortlist_reference_values(
                db,dataset=FC27,player_ids=[3,2,1,1])
            self.assertEqual(set(batch),{1,2,3})
            for pid in (1,2,3):
                reference,_=_player_reference(db,FC27,pid)
                self.assertEqual(batch[pid][0],reference)
            self.assertIsNone(batch[2][1])
            self.assertEqual(batch[1][1],125000)
            with self.assertRaises(ValueError):
                shortlist_reference_values(
                    db,dataset="older-career",player_ids=[1])
        finally:
            db.close()

    def test_buyer_money_and_wage_headroom_must_be_observed(self):
        for kwargs in ({"valuation":-1},{"transfer_headroom":-1},
                       {"weekly_wage":-2},{"wage_headroom":-1},
                       {"sale":{"valid":False}}):
            inputs=dict(valuation=5000000,transfer_headroom=7000000,
                        weekly_wage=12000,wage_headroom=20000,sale=SALE)
            with self.assertRaises(ValueError):
                prospective_purchase_fit(**{**inputs,**kwargs})


if __name__=="__main__":
    unittest.main()

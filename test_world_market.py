"""Transfer market preview must not change saves or playable registrations."""
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from flask import Flask
from world_market import (
    allowed_effective_date, offer_result, tier_budget,
    create_market_blueprint, initialize_market
)


class MarketRulesTests(unittest.TestCase):
    def test_scenario_budget_tiers(self):
        self.assertGreater(tier_budget(1)[0],tier_budget(2)[0])
        self.assertGreater(tier_budget(3)[0],tier_budget(4)[0])
        self.assertEqual(tier_budget(2,0.5)[0],4_000_000)

    def test_reject_over_budget(self):
        self.assertEqual(offer_result(10_000_000,8_000_000,5_000_000)["status"],"blocked")

    def test_negotiate_counter_and_rival_premium(self):
        self.assertEqual(offer_result(1_000_000,1_000_000,3_000_000)["status"],"counteroffer")
        self.assertEqual(offer_result(1_400_000,1_000_000,3_000_000)["status"],"acceptable_for_discussion")
        self.assertLess(offer_result(1_400_000,1_000_000,3_000_000,"neutral")["asking"],
                        offer_result(1_400_000,1_000_000,3_000_000,"rival")["asking"])

    def test_unknown_value_requires_review(self):
        self.assertEqual(offer_result(500_000,None,2_000_000)["status"],"review")

    def test_pes_winter_deal_stays_next_summer(self):
        self.assertEqual(allowed_effective_date(
            date(2027,1,3),date(2027,1,31),date(2026,8,1),date(2027,7,1)),
            date(2027,7,1))
        self.assertEqual(allowed_effective_date(
            date(2026,7,1),date(2026,7,12),date(2026,8,1),date(2027,7,1)),
            date(2026,7,12))
        self.assertEqual(allowed_effective_date(
            date(2027,1,3),date(2027,1,31),date(2026,8,1),date(2027,7,1),active_pes=False),
            date(2027,1,31))

    def test_cannot_propose_before_agreement(self):
        with self.assertRaises(ValueError):
            allowed_effective_date(date(2027,1,30),date(2027,1,5),
                date(2026,8,1),date(2027,7,1))


class MarketPagesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.tmp.name)/"market.sqlite"
        cls.app=Flask(__name__)
        cls.app.register_blueprint(create_market_blueprint(cls.path))
        cls.client=cls.app.test_client()
        cls.initial=cls.client.get("/world/market")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_preview_page_renders(self):
        self.assertEqual(self.initial.status_code,200)
        self.assertIn(b"Transfer market sandbox",self.initial.data)
        self.assertIn(b"FICTIONAL scenario assumptions",self.initial.data)

    def test_preview_does_not_write_offers_or_budgets(self):
        response=self.client.get("/world/market?scale=1.5&fee=1000000&relationship=rival")
        self.assertEqual(response.status_code,200)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM world_market_offers").fetchone()[0],0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM world_market_scenarios").fetchone()[0],0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM world_market_scenario_clubs").fetchone()[0],0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM world_transfers").fetchone()[0],0)

    def test_unknown_dataset_404(self):
        self.assertEqual(self.client.get("/world/market?dataset=unknown").status_code,404)


if __name__=="__main__":
    unittest.main()

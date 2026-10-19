"""Read-only finance foundations and dataset isolation checks."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from flask import Flask
from world_finance import create_finance_blueprint, initialize_finance, financial_status
from world_v2 import initialize_world
from world_explorer import initialize_catalog
from world_valuation import contract_adjusted_value


class FinanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.temp.name)/"finances.sqlite"
        cls.app=Flask(__name__)
        cls.app.register_blueprint(create_finance_blueprint(cls.path))
        cls.client=cls.app.test_client()
        with sqlite3.connect(cls.path) as db:
            initialize_world(db)
            initialize_catalog(db)
            initialize_finance(db)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_finance_page_loads_and_is_unverified(self):
        response=self.client.get("/world/finances")
        self.assertEqual(response.status_code,200)
        self.assertIn(b"Club finances",response.data)
        self.assertIn(b"Not estimated",response.data)

    def test_club_finance_unknown_until_evidence(self):
        with sqlite3.connect(self.path) as db:
            cid=db.execute("SELECT club_id FROM world_clubs WHERE name='Arsenal'").fetchone()[0]
        response=self.client.get(f"/world/finances/club/{cid}")
        self.assertEqual(response.status_code,200)
        self.assertIn(b"Unknown",response.data)

    def test_no_fabricated_contracts_or_budgets(self):
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM world_dataset_club_finances").fetchone()[0],0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM world_dataset_player_contracts").fetchone()[0],0)
            status=financial_status(db,"england-2026-27-fc27")
            self.assertEqual(status["clubs"],92)
            self.assertEqual(status["source_clubs"],0)
            self.assertEqual(status["source_contracts"],0)

    def test_separate_dataset_financials_do_not_leak(self):
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR IGNORE INTO world_seasons(season_id,label) VALUES('2004/05','2004/05')")
            db.execute("""INSERT OR IGNORE INTO world_datasets
                (dataset_id,season_id,title,source_label,source_date,status)
                VALUES('finance-test-2004','2004/05','Test 2004','Fixture','2004-08-01','review')""")
            cid=db.execute("SELECT club_id FROM world_clubs WHERE name='Arsenal'").fetchone()[0]
            db.execute("""INSERT OR IGNORE INTO world_dataset_entries(dataset_id,competition_id,club_id)
                VALUES('finance-test-2004','ENG1',?)""",(cid,))
            db.execute("""INSERT OR IGNORE INTO world_dataset_club_finances(
                dataset_id,club_id,transfer_budget,financial_status,source_url)
                VALUES('finance-test-2004',?,5000000,'simulation-assumption','https://example.org')""",(cid,))
            db.commit()
        previous=self.client.get(f"/world/finances/club/{cid}?dataset=finance-test-2004")
        current=self.client.get(f"/world/finances/club/{cid}?dataset=england-2026-27-fc27")
        self.assertEqual(previous.status_code,200)
        self.assertIn(b"5.0m",previous.data)
        self.assertNotIn(b"5.0m",current.data)

    def test_contract_adjustment_requires_confirmed_term(self):
        self.assertEqual(contract_adjusted_value(10_000_000,0,confirmed=False),10_000_000)
        self.assertEqual(contract_adjusted_value(10_000_000,None,confirmed=True),10_000_000)
        self.assertLess(contract_adjusted_value(10_000_000,6,confirmed=True),10_000_000)
        self.assertEqual(contract_adjusted_value(10_000_000,24,confirmed=True),10_000_000)
        with self.assertRaises(ValueError):
            contract_adjusted_value(10_000_000,-1,confirmed=True)

    def test_missing_dataset_rejected(self):
        self.assertEqual(self.client.get("/world/finances?dataset=unknown-seas").status_code,404)


if __name__=="__main__":
    unittest.main()

"""Independent tests of historical import validation, rollback and valuations."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from world_v2 import initialize_world
from world_explorer import initialize_catalog, create_explorer_blueprint
from world_import import apply, preview, install_import_schema
from world_valuation import model_value, display_gbp


def sample():
    return {
        "dataset":{"id":"test-2004-05-v1","season":"2004/05",
          "title":"Historical 2004/05 prototype","source":"test fixture only",
          "source_date":"2004-08-01"},
        "clubs":[{"id":"historical-team-a","name":"Test Albion",
                  "competition":"ENG1"}],
        "players":[{"id":"historical-player-a","name":"Test Striker",
                   "club":"historical-team-a","birth_date":"1980-03-01",
                   "position":"ST","nationality":"England",
                   "rating":{"overall":76,"pace":70,"shooting":79}}]
    }


class HistoricalImporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t=tempfile.TemporaryDirectory()
        cls.path=Path(cls.t.name)/"test.sqlite"
        cls.conn=sqlite3.connect(cls.path,isolation_level=None)
        cls.conn.execute("PRAGMA foreign_keys=ON")
        initialize_world(cls.conn)
        initialize_catalog(cls.conn)
        install_import_schema(cls.conn)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        cls.t.cleanup()

    def test_01_preview_does_not_write(self):
        before=self.conn.execute("SELECT COUNT(*) FROM world_datasets").fetchone()[0]
        p=preview(sample(),self.conn)
        self.assertTrue(p["valid"],p)
        self.assertEqual(p["players"],1)
        self.assertEqual(before,self.conn.execute("SELECT COUNT(*) FROM world_datasets").fetchone()[0])

    def test_02_missing_player_club_fails(self):
        p=sample()
        p["players"][0]["club"]="not-a-club"
        self.assertFalse(preview(p,self.conn)["valid"])

    def test_03_apply_immutable_separate_season(self):
        original=self.conn.execute("SELECT COUNT(*) FROM world_dataset_rosters WHERE dataset_id='england-2026-27-fc27'").fetchone()[0]
        result=apply(sample(),self.conn)
        self.assertTrue(result["valid"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM world_dataset_rosters WHERE dataset_id='test-2004-05-v1'").fetchone()[0],1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM world_dataset_ratings WHERE dataset_id='test-2004-05-v1'").fetchone()[0],1)
        self.assertEqual(original,self.conn.execute("SELECT COUNT(*) FROM world_dataset_rosters WHERE dataset_id='england-2026-27-fc27'").fetchone()[0])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM world_datasets WHERE is_career_active=1").fetchone()[0],0)

    def test_04_existing_dataset_rejected(self):
        self.assertFalse(preview(sample(),self.conn)["valid"])
        with self.assertRaises(ValueError):
            apply(sample(),self.conn)

    def test_05_bad_rating_refused(self):
        payload=sample()
        payload["dataset"]["id"]="test-2004-05-v2"
        payload["players"][0]["rating"]["overall"]=120
        self.assertFalse(preview(payload,self.conn)["valid"])
        self.assertFalse(self.conn.execute("SELECT 1 FROM world_datasets WHERE dataset_id='test-2004-05-v2'").fetchone())

    def test_06_history_routes(self):
        app=__import__("flask").Flask(__name__)
        app.register_blueprint(create_explorer_blueprint(self.path))
        client=app.test_client()
        r=client.get("/world/explore?dataset=test-2004-05-v1")
        self.assertEqual(r.status_code,200)
        self.assertIn(b"Historical 2004/05 prototype",r.data)
        r=client.get("/world/explore/league/ENG1?dataset=test-2004-05-v1")
        self.assertEqual(r.status_code,200)
        self.assertIn(b"Test Albion",r.data)
        pid=self.conn.execute("SELECT player_id FROM world_dataset_rosters WHERE dataset_id='test-2004-05-v1'").fetchone()[0]
        r=client.get(f"/world/explore/player/{pid}?dataset=test-2004-05-v1")
        self.assertEqual(r.status_code,200)
        self.assertIn(b"Test Striker",r.data)
        self.assertIn(b"76",r.data)
        self.assertEqual(client.get(f"/world/explore/player/{pid}?dataset=england-2026-27-fc27").status_code,404)


class ValuationTests(unittest.TestCase):
    def test_missing_data_not_guessed(self):
        self.assertIsNone(model_value(None,25,"ST"))
        self.assertIsNone(model_value(70,None,"ST"))
    def test_young_scorer_exceeds_older_peer(self):
        self.assertGreater(model_value(78,22,"ST"),model_value(78,33,"ST"))
    def test_high_rated_player_exceeds_lower(self):
        self.assertGreater(model_value(82,26,"CM"),model_value(65,26,"CM"))
    def test_format(self):
        self.assertTrue(display_gbp(model_value(80,25,"ST")).startswith("£"))


if __name__=="__main__":
    unittest.main()

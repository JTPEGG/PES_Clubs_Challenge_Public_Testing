"""Smoke tests for season-aware squad explorer, dataset isolation, profiles."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from flask import Flask
from world_explorer import create_explorer_blueprint, initialize_catalog, age_on
from world_v2 import initialize_world


class ExplorerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.tmp.name)/"explore.sqlite"
        cls.app=Flask(__name__)
        cls.app.register_blueprint(create_explorer_blueprint(cls.path))
        cls.client=cls.app.test_client()
        response=cls.client.get("/world/explore")
        assert response.status_code==200, response.data[:400]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_league_and_squad_view(self):
        r=self.client.get("/world/explore/league/ENG2")
        self.assertEqual(r.status_code,200)
        self.assertIn(b"Championship",r.data)
        with sqlite3.connect(self.path) as db:
            arsenal=db.execute("SELECT club_id FROM world_clubs WHERE name='Arsenal'").fetchone()[0]
        r=self.client.get(f"/world/explore/club/{arsenal}?position=ST&sort=age_young")
        self.assertEqual(r.status_code,200)
        self.assertIn(b"Position",r.data)
        self.assertIn(b"Overall",r.data)

    def test_player_profile(self):
        with sqlite3.connect(self.path) as db:
            player=db.execute("""SELECT player_id FROM world_player_source_refs
                       WHERE source_name='EAFC27' AND external_id='239085'""").fetchone()[0]
        r=self.client.get(f"/world/explore/player/{player}")
        self.assertEqual(r.status_code,200)
        self.assertIn(b"Erling Haaland",r.data)
        self.assertIn(b"91",r.data)
        self.assertIn(b"Physicality",r.data)

    def test_age_is_snapshot_relative(self):
        self.assertEqual(age_on("2000-07-21","2026-09-12"),26)
        self.assertEqual(age_on("2000-07-21","2025-06-01"),24)
        self.assertIsNone(age_on(None,"2026-09-12"))

    def test_unknown_dataset_rejected(self):
        self.assertEqual(self.client.get("/world/explore?dataset=does-not-exist").status_code,404)

    def test_second_season_can_be_created_without_mutating_existing(self):
        with sqlite3.connect(self.path) as db:
            db.execute("PRAGMA foreign_keys=ON")
            original=db.execute("""SELECT COUNT(*) FROM world_dataset_rosters
              WHERE dataset_id='england-2026-27-fc27'""").fetchone()[0]
            db.execute("INSERT INTO world_seasons(season_id,label) VALUES('2004/05','2004/05')")
            db.execute("""INSERT INTO world_datasets(dataset_id,season_id,title,source_label,source_date,status)
              VALUES ('england-2004-05','2004/05','England 2004/05','Historical data awaiting import','2004-09-01','draft')""")
            db.commit()
        response=self.client.get("/world/explore?dataset=england-2004-05")
        self.assertEqual(response.status_code,200)
        self.assertIn(b"England 2004/05",response.data)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM world_dataset_rosters
                 WHERE dataset_id='england-2026-27-fc27'""").fetchone()[0],original)
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM world_dataset_rosters
                 WHERE dataset_id='england-2004-05'""").fetchone()[0],0)
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM world_dataset_ratings
                 WHERE dataset_id='england-2004-05'""").fetchone()[0],0)
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM world_dataset_ratings
                 WHERE dataset_id='england-2026-27-fc27'""").fetchone()[0],2498)


if __name__=="__main__":
    unittest.main()

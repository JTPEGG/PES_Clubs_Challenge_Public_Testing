"""Smoke tests for the independent PES 2.0 world scaffold."""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from flask import Flask
from world_v2 import create_world_blueprint
from world_2026_27_clubs import LEAGUE_MEMBERS, validate_memberships
from world_quality import audit_seed_sources, audit_database


class WorldPrototypeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "world.db"
        self.app = Flask(__name__)
        self.app.register_blueprint(create_world_blueprint(self.db))
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_world_index_seeds_four_leagues(self):
        response = self.client.get("/world")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"League Two", response.data)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM world_competitions").fetchone()[0], 10)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM world_entries").fetchone()[0], 92)
            self.assertEqual(dict(conn.execute("SELECT competition_id, COUNT(*) FROM world_entries GROUP BY competition_id").fetchall()), {"ENG1":20,"ENG2":24,"ENG3":24,"ENG4":24})
            self.assertGreaterEqual(conn.execute("SELECT COUNT(*) FROM world_players").fetchone()[0], 2498)
            self.assertGreaterEqual(conn.execute("SELECT COUNT(*) FROM world_rosters").fetchone()[0], 2498)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM world_player_source_refs").fetchone()[0], 3062)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM world_external_ratings").fetchone()[0], 2498)
            self.assertEqual(dict(conn.execute("""SELECT e.competition_id,COUNT(*) FROM world_external_ratings x JOIN world_rosters r ON r.player_id=x.player_id JOIN world_entries e ON e.club_id=r.club_id AND e.season_id=r.season_id WHERE r.season_id='2026/27' GROUP BY e.competition_id""").fetchall()), {"ENG1":612,"ENG2":669,"ENG3":612,"ENG4":605})

    def test_club_data_has_no_duplicates(self):
        self.assertEqual(validate_memberships(), [])
        self.assertEqual(len(set(name for _, clubs in LEAGUE_MEMBERS.values() for name in clubs)), 92)

    def test_known_club_page(self):
        self.client.get("/world")
        with sqlite3.connect(self.db) as conn:
            cid = conn.execute("SELECT club_id FROM world_clubs WHERE name='Arsenal'").fetchone()[0]
        response = self.client.get(f"/world/club/{cid}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Arsenal", response.data)

    def test_player_roster_is_provisional_and_idempotent(self):
        self.client.get("/world")
        self.client.get("/world")
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(DISTINCT external_id) FROM world_player_source_refs WHERE source_name='FPL'").fetchone()[0], 564)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM world_player_attributes").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM world_external_ratings").fetchone()[0], 2498)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM world_contracts").fetchone()[0], 0)
            team_id = conn.execute("SELECT club_id FROM world_clubs WHERE name='Arsenal'").fetchone()[0]
        response = self.client.get(f"/world/club/{team_id}")
        self.assertIn(b"Saka", response.data)

    def test_read_only_quality_dashboard_and_database_checks(self):
        response = self.client.get("/world/quality")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Player database quality", response.data)
        self.assertIn(b"Cross-source club/identity", response.data)
        with sqlite3.connect(self.db) as conn:
            metrics = audit_database(conn)
            self.assertEqual(metrics["ea_rated"], 2498)
            self.assertEqual(metrics["ea_source_refs"], 2498)
            self.assertEqual(metrics["fpl_source_refs"], 564)
            self.assertEqual(metrics["duplicate_ea_ids"], 0)
            self.assertEqual(metrics["duplicate_season_registrations"], 0)
            self.assertEqual(metrics["pes_id_matches"], 0)
            self.assertEqual(metrics["contracts"], 0)

    def test_source_mismatch_candidates_are_not_automatic_transfers(self):
        comparison = audit_seed_sources()
        self.assertEqual(comparison["ea_records"], 2498)
        self.assertEqual(comparison["fpl_records"], 564)
        self.assertGreater(len(comparison["possible_conflicts"]), 0)
        self.assertEqual(comparison["ea_unique_ids"], 2498)
        self.assertEqual(comparison["fpl_unique_ids"], 564)

    def test_unknown_league_404(self):
        self.assertEqual(self.client.get("/world/league/UNKNOWN").status_code, 404)

    def test_no_duplicate_seeding(self):
        self.client.get("/world")
        self.client.get("/world")
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM world_clubs").fetchone()[0], 92)


if __name__ == "__main__":
    unittest.main()

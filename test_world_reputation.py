"""Audit, season isolation and decision rules for provisional reputations."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from flask import Flask
from world_v2 import initialize_world
from world_explorer import initialize_catalog
from world_reputation import (
    MODEL_VERSION, initialize_reputations, create_reputation_blueprint,
    derive_club_appeal, assess_player_move, manager_reputation_from_results,
    assess_manager_application
)


class ReputationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t=tempfile.TemporaryDirectory()
        cls.path=Path(cls.t.name)/"reputation.sqlite"
        cls.db=sqlite3.connect(cls.path)
        cls.db.execute("PRAGMA foreign_keys=ON")
        initialize_world(cls.db)
        initialize_catalog(cls.db)
        initialize_reputations(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        cls.t.cleanup()

    def test_audit_covers_92_2026_clubs(self):
        d="england-2026-27-fc27"
        self.assertEqual(self.db.execute("""SELECT COUNT(*) FROM world_club_reputation_snapshots
            WHERE dataset_id=?""",(d,)).fetchone()[0],92)
        self.assertEqual(dict(self.db.execute("""SELECT competition_id,COUNT(*)
            FROM world_club_reputation_snapshots WHERE dataset_id=?
            GROUP BY competition_id""",(d,)).fetchall()),
            {"ENG1":20,"ENG2":24,"ENG3":24,"ENG4":24})
        self.assertEqual(self.db.execute("""SELECT COUNT(*) FROM world_league_reputation_snapshots
            WHERE dataset_id=?""",(d,)).fetchone()[0],4)
        self.assertEqual(self.db.execute("""SELECT COUNT(*) FROM world_club_reputation_snapshots
            WHERE dataset_id=? AND institutional_prestige IS NOT NULL""",(d,)).fetchone()[0],0)
        rated=self.db.execute("""SELECT COUNT(*) FROM world_club_reputation_snapshots
            WHERE dataset_id=? AND rated_players>0""",(d,)).fetchone()[0]
        self.assertGreater(rated,0)
        self.assertLessEqual(rated,92)
        self.assertEqual(self.db.execute("""SELECT COUNT(*) FROM world_club_reputation_snapshots
            WHERE dataset_id=? AND confidence IN ('source-proxy','limited-source','tier-only')""",
            (d,)).fetchone()[0],92)

    def test_reproducible_and_once_only(self):
        d="england-2026-27-fc27"
        original=self.db.execute("""SELECT working_appeal,top_squad_average,squad_adjustment
            FROM world_club_reputation_snapshots WHERE dataset_id=? ORDER BY club_id""",(d,)).fetchall()
        initialize_reputations(self.db)
        current=self.db.execute("""SELECT working_appeal,top_squad_average,squad_adjustment
            FROM world_club_reputation_snapshots WHERE dataset_id=? ORDER BY club_id""",(d,)).fetchall()
        self.assertEqual(original,current)
        self.assertEqual(derive_club_appeal("ENG1",[80]*20)[:3],(89,80.0,3))
        self.assertEqual(derive_club_appeal("ENG2",[]),(67,None,0,"tier-only"))

    def test_separate_historical_season_cannot_mutate_current(self):
        self.db.execute("INSERT OR IGNORE INTO world_seasons(season_id,label) VALUES('2004/05','2004/05')")
        self.db.execute("""INSERT OR IGNORE INTO world_datasets
          (dataset_id,season_id,title,source_label,source_date,status)
          VALUES ('rep-2004','2004/05','Example 2004 season','Test only','2004-08-01','review')""")
        club=self.db.execute("SELECT club_id FROM world_clubs WHERE name='Arsenal'").fetchone()[0]
        self.db.execute("INSERT OR IGNORE INTO world_dataset_entries(dataset_id,competition_id,club_id) VALUES('rep-2004','ENG1',?)",(club,))
        self.db.commit()
        original=self.db.execute("""SELECT working_appeal FROM world_club_reputation_snapshots
          WHERE dataset_id='england-2026-27-fc27' AND club_id=?""",(club,)).fetchone()[0]
        initialize_reputations(self.db)
        historic=self.db.execute("""SELECT working_appeal,rated_players FROM world_club_reputation_snapshots
          WHERE dataset_id='rep-2004' AND club_id=?""",(club,)).fetchone()
        self.assertEqual(historic,(86,0))
        self.assertEqual(self.db.execute("""SELECT working_appeal FROM world_club_reputation_snapshots
          WHERE dataset_id='england-2026-27-fc27' AND club_id=?""",(club,)).fetchone()[0],original)

    def test_player_decisions_cannot_be_bought_with_wages(self):
        refused=assess_player_move(buyer_tier=4,seller_tier=1,buyer_appeal=43,seller_appeal=90)
        self.assertEqual(refused["decision"],"uninterested")
        self.assertFalse(refused["can_negotiate"])
        self.assertEqual(assess_player_move(buyer_tier=2,seller_tier=1)["decision"],"needs_assurances")
        self.assertEqual(assess_player_move(buyer_tier=1,seller_tier=2)["decision"],"open_to_talks")
        self.assertEqual(assess_player_move(buyer_tier=None,seller_tier=1)["decision"],"review")

    def test_job_decisions_require_real_manager_history(self):
        self.assertIsNone(manager_reputation_from_results(None))
        with self.assertRaises(ValueError):
            manager_reputation_from_results([{"event":"promotion"}])
        reputation=manager_reputation_from_results([{"event":"promotion","source":"archive:test-season"}])
        self.assertEqual(reputation,33)
        job=assess_manager_application(manager_reputation=33,club_appeal=90,league_tier=1)
        self.assertEqual(job["status"],"unlikely")
        other=assess_manager_application(manager_reputation=80,club_appeal=90,league_tier=1)
        self.assertEqual(other["status"],"eligible_for_review")
        self.assertEqual(assess_manager_application(manager_reputation=None,club_appeal=90,league_tier=1)["status"],"unassessed")

    def test_readonly_audit_routes(self):
        app=Flask(__name__)
        app.register_blueprint(create_reputation_blueprint(self.path))
        client=app.test_client()
        home=client.get("/world/reputations/legacy")
        self.assertEqual(home.status_code,200)
        self.assertIn(b"Club &amp; League Reputation Audit",home.data)
        self.assertIn(b"Derby County",home.data)
        self.assertIn(b"source-proxy",home.data)
        cid=self.db.execute("SELECT club_id FROM world_clubs WHERE name='Derby County'").fetchone()[0]
        detail=client.get(f"/world/reputations/club/{cid}")
        self.assertEqual(detail.status_code,200)
        self.assertIn(b"Historical institutional prestige",detail.data)
        self.assertIn(b"Unknown",detail.data)
        self.assertEqual(client.get(f"/world/reputations/club/{cid}?dataset=nonexistent").status_code,404)
        hypothetical=client.get("/world/reputations/jobs?manager=30&experience=no")
        self.assertEqual(hypothetical.status_code,200)
        self.assertIn(b"Job Eligibility Lab",hypothetical.data)
        self.assertIn(b"Manchester City",hypothetical.data)
        self.assertIn(b"unlikely",hypothetical.data)
        unknown=client.get("/world/reputations/jobs")
        self.assertEqual(unknown.status_code,200)
        self.assertIn(b"unassessed",unknown.data)
        self.assertEqual(client.get("/world/reputations/jobs?manager=150").status_code,400)


if __name__=="__main__":
    unittest.main()

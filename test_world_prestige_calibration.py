"""Prestige calibration: sourced proposals, no approval or career mutation."""
import sqlite3
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from flask import Flask

from world_prestige_calibration import (
    VERSION,DATASET_ID,CLUBS,DIMENSIONS,domestic_points,stadium_points,
    score_club,check_calibration,
)
from world_prestige_calibration_ui import create_calibration_blueprint
from world_v2 import initialize_world
from world_explorer import initialize_catalog
from world_reputation_v2 import initialize_pyramid
from world_reputation_progression import initialize_progression


class PrestigeCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.dbpath=Path(cls.temp.name)/"calibration.sqlite"
        cls.conn=sqlite3.connect(cls.dbpath)
        cls.conn.row_factory=sqlite3.Row
        cls.conn.execute("PRAGMA foreign_keys=ON")
        initialize_world(cls.conn)
        initialize_catalog(cls.conn)
        initialize_pyramid(cls.conn)
        initialize_progression(cls.conn)
        cls.app=Flask(__name__)
        cls.app.register_blueprint(create_calibration_blueprint(cls.dbpath))
        cls.client=cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        cls.temp.cleanup()

    def test_01_15_clubs_across_four_actual_starting_divisions(self):
        self.assertTrue(check_calibration())
        self.assertEqual(len(CLUBS),15)
        self.assertEqual(Counter(c["league"] for c in CLUBS),
            {"ENG1":4,"ENG2":4,"ENG3":4,"ENG4":3})
        expected=dict(self.conn.execute("""SELECT c.name,e.competition_id
            FROM world_dataset_entries e JOIN world_clubs c ON c.club_id=e.club_id
            WHERE e.dataset_id=?""",(DATASET_ID,)).fetchall())
        for club in CLUBS:
            with self.subTest(club=club["name"]):
                self.assertEqual(expected.get(club["name"]),club["league"])
                self.assertGreaterEqual(len(club["sources"]),2)
                self.assertTrue(all(x[2].startswith("https://") for x in club["sources"]))

    def test_02_stable_weighted_rubric_and_range(self):
        self.assertEqual(sum(maximum for _,maximum in DIMENSIONS.values()),100)
        self.assertEqual({k:part[1] for k,part in DIMENSIONS.items()},{
            "domestic":25,"europe":15,"longevity":35,"scale":15,"identity":10})
        self.assertEqual(VERSION,"institutional-prestige-calibration-v2")
        self.assertEqual(domestic_points(0,0,0),0)
        self.assertEqual(domestic_points(14,14,5),25)
        self.assertEqual(domestic_points(1,0,0),4)
        self.assertGreater(domestic_points(14,14,2),domestic_points(2,1,0))
        self.assertEqual(domestic_points(0,0,0),0)
        self.assertEqual(stadium_points(60704),15)
        self.assertEqual(stadium_points(5108),5)
        for club in CLUBS:
            score=score_club(club)
            self.assertEqual(sum(score[k] for k in DIMENSIONS),score["score"])
            self.assertTrue(0<=score["score"]<=100)
            self.assertTrue(all(0<=score[k]<=DIMENSIONS[k][1] for k in DIMENSIONS))
        with self.assertRaises(ValueError):
            domestic_points(-1,0,0)
        with self.assertRaises(ValueError):
            stadium_points(0)

    def test_03_clear_separation_of_prestige_and_sporting_appeal(self):
        c={r["name"]:score_club(r)["score"] for r in CLUBS}
        self.assertGreater(c["Arsenal"]-c["Hull City"],50)
        self.assertGreater(c["West Ham United"],c["Hull City"])
        self.assertGreater(c["Sheffield Wednesday"],c["Bradford City"])
        self.assertGreater(c["Leicester City"],c["AFC Wimbledon"])
        self.assertGreater(c["Wrexham"],c["Salford City"])
        self.assertGreater(c["Derby County"],c["York City"])

    def test_035_new_versus_old_calibration_and_hull_history(self):
        rated={c["name"]:score_club(c) for c in CLUBS}
        self.assertEqual(rated["Hull City"]["score"],34)
        self.assertEqual(rated["Hull City"],{
            "domestic":0,"europe":1,"longevity":18,
            "scale":9,"identity":6,"score":34})
        self.assertEqual(rated["Arsenal"]["score"],94)
        self.assertEqual(rated["Wrexham"]["score"],35)
        self.assertEqual(rated["Grimsby Town"]["score"],32)
        self.assertEqual(rated["Salford City"]["score"],20)
        hull=next(c for c in CLUBS if c["name"]=="Hull City")
        self.assertIn("2020/21 League One",hull["heritage"])
        self.assertEqual(hull["league_titles"],0)
        self.assertEqual(domestic_points(hull["league_titles"],
            hull["fa_cups"],hull["league_cups"]),0)

    def test_04_proposed_numbers_do_not_create_approved_prestige(self):
        before=self.conn.execute(
            "SELECT COUNT(*) FROM world_reputation_prestige_reviews").fetchone()[0]
        before_career=self.conn.execute(
            "SELECT COUNT(*) FROM world_career_reputation_seasons").fetchone()[0]
        self.assertEqual(self.client.get("/world/reputations/prestige/calibration").status_code,200)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM world_reputation_prestige_reviews").fetchone()[0],before)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM world_career_reputation_seasons").fetchone()[0],before_career)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM world_career_offers").fetchone()[0]
            if self.conn.execute("""SELECT 1 FROM sqlite_master
                       WHERE name='world_career_offers'""").fetchone() else 0,0)

    def test_05_readable_club_comparison_and_sources(self):
        response=self.client.get("/world/reputations/prestige/calibration")
        self.assertEqual(response.status_code,200)
        self.assertIn(b"15-club Prestige Calibration",response.data)
        self.assertIn(b"Hull City",response.data)
        self.assertIn(b"Arsenal",response.data)
        self.assertIn(b"West Ham United",response.data)
        self.assertIn(b"Proposed only",response.data)
        self.assertIn(b"European",response.data)
        self.assertIn(b"Current sporting appeal",response.data)
        self.assertIn(b"35",response.data)
        self.assertIn(b"Major domestic honours",response.data)
        self.assertIn(b"34",response.data)
        self.assertIn(b"Historical level and continuity",response.data)

        league=self.client.get("/world/reputations/prestige/calibration?league=ENG4")
        self.assertEqual(league.status_code,200)
        self.assertIn(b"York City",league.data)
        self.assertNotIn(b"Arsenal",league.data)

        cid=self.conn.execute("SELECT club_id FROM world_clubs WHERE name='AFC Wimbledon'").fetchone()[0]
        detail=self.client.get("/world/reputations/prestige/calibration/"+str(cid))
        self.assertEqual(detail.status_code,200)
        self.assertIn(b"1988",detail.data)
        self.assertIn(b"not counted",detail.data)
        self.assertIn(b"Source evidence to inspect",detail.data)
        self.assertIn(b"Approved institutional prestige",detail.data)
        self.assertIn(b"Original editorial input",detail.data)
        hull_id=self.conn.execute(
            "SELECT club_id FROM world_clubs WHERE name='Hull City'").fetchone()[0]
        hull_detail=self.client.get(
            "/world/reputations/prestige/calibration/"+str(hull_id))
        self.assertEqual(hull_detail.status_code,200)
        self.assertIn(b"2020/21 League One",hull_detail.data)
        self.assertIn(b"not a major domestic honour",hull_detail.data)
        self.assertIn(b"34 / 100",hull_detail.data)
        self.assertIn(b"requires reviewer agreement",detail.data)
        self.assertIn(b"https://www.afcwimbledon.co.uk/club/",detail.data)

        self.assertEqual(self.client.post("/world/reputations/prestige/calibration").status_code,405)
        self.assertEqual(self.client.get("/world/reputations/prestige/calibration/9999999").status_code,404)

    def test_06_foreign_or_historic_datasets_never_inherit_2026_scores(self):
        ds=self.conn.execute("SELECT dataset_id FROM world_datasets WHERE dataset_id!=? LIMIT 1",
                             (DATASET_ID,)).fetchone()
        if ds:
            response=self.client.get("/world/reputations/prestige/calibration?dataset="+ds[0])
            self.assertEqual(response.status_code,200)
            self.assertIn(b"No calibrated prestige sample exists",response.data)
        self.assertEqual(self.client.get(
            "/world/reputations/prestige/calibration?dataset=unknown").status_code,404)


if __name__=="__main__":
    unittest.main()

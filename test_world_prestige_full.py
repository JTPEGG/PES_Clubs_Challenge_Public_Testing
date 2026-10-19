"""92-club draft coverage, source transparency, outlier and isolation tests.

All 92 scores are proposed editor inputs; passing this suite does NOT
independently verify every historical trophy count, venue or editorial band.
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from collections import Counter
from flask import Flask

from world_prestige_full import (
    ALL_92,PROVISIONAL_77,DIMENSIONS,FULL_VERSION,DATASET_ID,
    validate_catalogue,score_club,review_flags,
    HISTORY_SOURCE,CAPACITY_SOURCE,FA_SOURCE,LEAGUE_CUP_SOURCE,
)
from world_prestige_calibration import CLUBS as ORIGINAL_15
from world_2026_27_clubs import LEAGUE_MEMBERS
from world_prestige_full_ui import create_full_prestige_blueprint
from world_explorer import initialize_catalog
from world_reputation_v2 import initialize_pyramid
from world_reputation_progression import initialize_progression
from world_v2 import initialize_world


class FullPrestigeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.temp.name)/"all-prestige.sqlite"
        cls.db=sqlite3.connect(cls.path)
        cls.db.row_factory=sqlite3.Row
        cls.db.execute("PRAGMA foreign_keys=ON")
        initialize_world(cls.db)
        initialize_catalog(cls.db)
        initialize_pyramid(cls.db)
        initialize_progression(cls.db)
        cls.app=Flask(__name__)
        cls.app.register_blueprint(create_full_prestige_blueprint(cls.path))
        cls.client=cls.app.test_client()
        cls.row_by_name={x["name"]:x for x in ALL_92}
        cls.id_by_name=dict(cls.db.execute(
            "SELECT name,club_id FROM world_clubs").fetchall())

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        cls.temp.cleanup()

    def test_01_complete_unique_correct_memberships(self):
        self.assertEqual(len(ALL_92),92)
        self.assertEqual(len(PROVISIONAL_77),77)
        self.assertEqual(len(ORIGINAL_15),15)
        self.assertTrue(validate_catalogue(ALL_92))
        self.assertEqual(Counter(x["league"] for x in ALL_92),
                         {"ENG1":20,"ENG2":24,"ENG3":24,"ENG4":24})
        for league,(_ref,names) in LEAGUE_MEMBERS.items():
            for name in names:
                self.assertIn(name,self.row_by_name)
                self.assertEqual(self.row_by_name[name]["league"],league)
        self.assertEqual(sum(x["source_status"]=="original_15_review_only" for x in ALL_92),15)
        self.assertEqual(sum(x["source_status"]=="proposed_counts_pending_review" for x in ALL_92),77)

    def test_02_original_15_locked_across_expansion(self):
        for original in ORIGINAL_15:
            with self.subTest(original=original["name"]):
                full=self.row_by_name[original["name"]]
                self.assertEqual(score_club(full),score_club(original))
                for key in ("league_titles","fa_cups","league_cups",
                            "europe","longevity","identity","stadium"):
                    self.assertEqual(full[key],original[key])
        self.assertEqual(score_club(self.row_by_name["Hull City"])["score"],34)

    def test_03_major_honours_only_and_all_scores_bounded(self):
        self.assertEqual(sum(d[1] for d in DIMENSIONS.values()),100)
        for name,c in self.row_by_name.items():
            with self.subTest(name=name):
                self.assertGreater(c["stadium"],0)
                self.assertIn(c["source_status"],("original_15_review_only",
                                                "proposed_counts_pending_review"))
                self.assertEqual(set(score_club(c))-{"score"},set(DIMENSIONS))
                points=score_club(c)
                self.assertEqual(sum(points[k] for k in DIMENSIONS),points["score"])
                self.assertTrue(all(0<=points[k]<=DIMENSIONS[k][1] for k in DIMENSIONS))
                self.assertTrue(0<=points["score"]<=100)
                self.assertTrue(all(type(c[k]) is int and c[k]>=0
                                    for k in ("league_titles","fa_cups","league_cups")))
        self.assertEqual(self.row_by_name["AFC Wimbledon"]["fa_cups"],0)
        self.assertEqual(self.row_by_name["AFC Wimbledon"]["league_titles"],0)
        self.assertEqual(self.row_by_name["Accrington Stanley"]["fa_cups"],0)
        self.assertEqual(self.row_by_name["Accrington Stanley"]["league_titles"],0)
        self.assertEqual(self.row_by_name["Hull City"]["league_titles"],0)
        self.assertEqual(score_club(self.row_by_name["Hull City"])["domestic"],0)
        self.assertEqual(self.row_by_name["Newcastle United"]["league_cups"],1)
        self.assertEqual(self.row_by_name["Manchester City"]["league_cups"],9)
        self.assertEqual(self.row_by_name["Manchester City"]["fa_cups"],8)

    def test_04_every_new_profile_has_research_not_fabricated_approval(self):
        for c in PROVISIONAL_77:
            with self.subTest(club=c["name"]):
                self.assertIn("pending_review",c["source_status"])
                self.assertEqual(c["capacity_source"],CAPACITY_SOURCE)
                self.assertEqual(c["historical_source"],HISTORY_SOURCE)
                self.assertTrue(c["research_url"].startswith(
                    "https://en.wikipedia.org/w/index.php?search="))
                self.assertEqual(len(c["sources"]),4)
                self.assertTrue(all(source[2].startswith("https://")
                                    for source in c["sources"]))
        self.assertTrue(FA_SOURCE.startswith("https://www.thefa.com/"))
        self.assertTrue(LEAGUE_CUP_SOURCE.startswith("https://en.wikipedia.org/"))

    def test_05_explicit_comparison_flags(self):
        wrexham=self.row_by_name["Wrexham"]
        afc=self.row_by_name["AFC Wimbledon"]
        hull=self.row_by_name["Hull City"]
        self.assertTrue(any("Specific calibration boundary" in x
             for x in review_flags(hull)))
        self.assertTrue(any("Specific calibration boundary" in x
             for x in review_flags(wrexham)))
        self.assertTrue(any("Media/cultural identity high" in x
             for x in review_flags(afc)))
        self.assertTrue(any("gap" in x for x in review_flags(
            hull,sporting_appeal=90)))
        self.assertTrue(any("source review" in x for x in review_flags(
            self.row_by_name["Brentford"])))

    def test_06_full_review_is_read_only_and_has_four_league_tables(self):
        before_reviews=self.db.execute(
            "SELECT COUNT(*) FROM world_reputation_prestige_reviews").fetchone()[0]
        before_careers=self.db.execute(
            "SELECT COUNT(*) FROM world_career_reputation_seasons").fetchone()[0]
        for query in ("",
                      "?sort=name",
                      "?sort=gap",
                      "?attention=new",
                      "?attention=flags",
                      "?league=ENG1",
                      "?league=ENG2",
                      "?league=ENG3",
                      "?league=ENG4"):
            response=self.client.get("/world/reputations/prestige/all"+query)
            self.assertEqual(response.status_code,200)
            self.assertIn(b"92-club Historical Prestige Review",response.data)
            self.assertIn(b"provisional gameplay proposals",response.data)
        index=self.client.get("/world/reputations/prestige/all")
        for word in (b"Premier League",b"Championship",b"League One",b"League Two",
                     b"Arsenal",b"Hull City",b"Manchester United",
                     b"Salford City",b"Evidence status",b"77",b"92"):
            self.assertIn(word,index.data)
        ids=self.db.execute("""SELECT COUNT(*) FROM world_dataset_entries
            WHERE dataset_id=?""",(DATASET_ID,)).fetchone()[0]
        self.assertEqual(ids,92)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM world_reputation_prestige_reviews").fetchone()[0],
            before_reviews)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM world_career_reputation_seasons").fetchone()[0],
            before_careers)
        self.assertEqual(self.client.post("/world/reputations/prestige/all").status_code,405)

    def test_065_csv_export_92_rows_never_approves_scores(self):
        import csv
        import io
        before_reviews=self.db.execute(
            "SELECT COUNT(*) FROM world_reputation_prestige_reviews").fetchone()[0]
        response=self.client.get("/world/reputations/prestige/all.csv")
        self.assertEqual(response.status_code,200)
        self.assertIn("text/csv",response.mimetype)
        self.assertIn("attachment",response.headers["Content-Disposition"])
        records=list(csv.DictReader(io.StringIO(response.get_data(as_text=True))))
        self.assertEqual(len(records),92)
        self.assertEqual(len({r["club"] for r in records}),92)
        for field in ("2026_27_division","proposed_prestige","sporting_appeal",
                      "major_domestic_honours_points","european_points",
                      "historical_standing_points","stadium_scale_points",
                      "identity_points","top_division_titles","fa_cup_titles",
                      "league_cup_titles","stadium_capacity","source_status",
                      "historical_record_reference","stadium_reference",
                      "comparative_review_flags"):
            self.assertIn(field,records[0])
        by_club={r["club"]:r for r in records}
        self.assertEqual(int(by_club["Hull City"]["proposed_prestige"]),34)
        self.assertEqual(int(by_club["Hull City"]["top_division_titles"]),0)
        self.assertEqual(by_club["Manchester City"]["source_status"],
                         "proposed_counts_pending_review")
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM world_reputation_prestige_reviews").fetchone()[0],
            before_reviews)
        self.assertEqual(self.client.post("/world/reputations/prestige/all.csv").status_code,405)

    def test_07_details_show_context_and_review_not_approved(self):
        for name in ("Hull City","Manchester City","Accrington Stanley","AFC Wimbledon"):
            club_id=self.id_by_name[name]
            page=self.client.get("/world/reputations/prestige/all/"+str(club_id))
            self.assertEqual(page.status_code,200)
            self.assertIn(b"Proposed historical prestige",page.data)
            self.assertIn(b"Not approved",page.data)
            self.assertIn(b"Ground capacity",page.data)
            self.assertIn(b"Top-flight league championship",page.data)
            self.assertIn(b"Football Club History Database",page.data)
            self.assertIn(b"Source and review links",page.data)
        self.assertEqual(self.client.get(
            "/world/reputations/prestige/all/99999999").status_code,404)


if __name__=="__main__":
    unittest.main()

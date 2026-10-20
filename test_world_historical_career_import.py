"""Early-edition career eligibility and source-isolation smoke tests."""
import sqlite3,unittest
from world_historical_career_import import season,edition_options,load_new_world,SUPPORTED

class HistoricalIntegrationTests(unittest.TestCase):
    def test_only_fifa26_fc27_are_fully_mapped_in_phase_one(self):
        self.assertEqual(SUPPORTED,(2026,2027))
        self.assertEqual(season(2026),"2025/26")
        self.assertEqual(season(2027),"2026/27")
        with sqlite3.connect(":memory:") as db:
            db.execute("""CREATE TABLE editions (
                 edition INTEGER, season TEXT, imported_player_rows INTEGER,
                 club_count INTEGER, missing_league_clubs INTEGER)""")
            db.executemany("INSERT INTO editions VALUES (?,?,?,?,?)",
                [(2020,"2019/20",18278,698,698),
                 (2026,"2025/26",18405,662,0),
                 (2027,"2026/27",17849,670,0)])
            entries=edition_options(db)
            self.assertFalse(entries[0]["ready_to_import"])
            self.assertTrue(entries[1]["ready_to_import"])
            self.assertTrue(entries[2]["ready_to_import"])

    def test_older_years_fail_without_modifying_world(self):
        with sqlite3.connect(":memory:") as db:
            with self.assertRaisesRegex(ValueError,"no verified complete"):
                load_new_world(db,source="not-present",finances="not-present",
                    circumstances="not-present",edition=2020)
            self.assertFalse(db.execute(
               "SELECT name FROM sqlite_master WHERE type='table'").fetchall())

if __name__=="__main__":
    unittest.main()

"""Historical season selector is read-only and rejects unsupported inputs."""
import sqlite3,tempfile,unittest
from pathlib import Path
from flask import Flask
from world_historical_career_setup_ui import (
    EDITION_CHOICES,read_historical_setup,create_historical_setup_blueprint
)

class HistoricalSeasonPickerTests(unittest.TestCase):
    def test_all_22_editions_browse_even_without_installation(self):
        with sqlite3.connect(":memory:") as conn:
            before=conn.total_changes
            options,selected,clubs=read_historical_setup(conn)
            self.assertEqual(len(options),22)
            self.assertNotIn(2025,[o["edition"] for o in options])
            self.assertFalse(any(o["installed"] for o in options))
            self.assertIsNone(selected)
            self.assertEqual(clubs,[])
            self.assertEqual(conn.total_changes,before)

    def test_unimported_edition_has_no_fictional_clubs(self):
        with sqlite3.connect(":memory:") as conn:
            _,selected,clubs=read_historical_setup(conn,2020)
            self.assertEqual(selected["edition"],2020)
            self.assertEqual(clubs,[])
            with self.assertRaisesRegex(ValueError,"Unsupported edition"):
                read_historical_setup(conn,2025)

    def test_flask_preview_get_does_not_mutate_database(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"demo.sqlite"
            with sqlite3.connect(path) as conn:
                conn.execute("CREATE TABLE sentinel (v INTEGER)")
                conn.execute("INSERT INTO sentinel VALUES(7)")
                conn.commit()
            app=Flask("historical-picker-test")
            app.register_blueprint(create_historical_setup_blueprint(path))
            with app.test_client() as client:
                a=client.get("/world/historical-setup")
                self.assertEqual(a.status_code,200)
                self.assertIn(b"Choose a historical starting season",a.data)
                b=client.get("/world/historical-setup?edition=2026")
                self.assertEqual(b.status_code,200)
                self.assertIn(b"Historical world not yet imported",b.data)
                c=client.get("/world/historical-setup?edition=2025")
                self.assertEqual(c.status_code,404)
            with sqlite3.connect(path) as conn:
                self.assertEqual(conn.execute("SELECT v FROM sentinel").fetchone()[0],7)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0],1)

if __name__=="__main__":
    unittest.main()

"""Deletion is confined to the derived FC27 SQLite release, never source."""
import sqlite3
import unittest

from world_fc27_release_exclusions import sanitize_fc27_active_release


def fixture():
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
        CREATE TABLE edition_club_competitions (
          edition INTEGER, club_key TEXT, original_source_league TEXT,
          PRIMARY KEY(edition,club_key)
        );
        CREATE TABLE fc27_stage (
          edition INTEGER, club_key TEXT,
          FOREIGN KEY(edition,club_key) REFERENCES edition_club_competitions(edition,club_key)
        );
        CREATE TABLE edition_career_starting_league_candidates (
          edition INTEGER, club_key TEXT, starting_competition TEXT
        );
        CREATE TABLE source_league_groups (
          edition INTEGER, league_key TEXT, source_label TEXT
        );
        CREATE TABLE edition_readiness (
          edition INTEGER, total_clubs INTEGER, clubs_unresolved INTEGER, career_ready INTEGER
        );
        INSERT INTO edition_club_competitions VALUES
          (2027,'excluded1','ISL'),
          (2027,'excluded2','Indian Super League'),
          (2027,'keep','Premier League'),
          (2026,'old','ISL');
        INSERT INTO fc27_stage VALUES (2027,'excluded1'),(2027,'keep');
        INSERT INTO edition_career_starting_league_candidates VALUES
          (2027,'excluded1',NULL),(2027,'excluded2',NULL),
          (2027,'keep','2027:en.1'),(2026,'old',NULL);
        INSERT INTO source_league_groups VALUES
          (2027,'excluded','Indian Super League'),
          (2027,'keep','Premier League'),(2026,'old','ISL');
        INSERT INTO edition_readiness VALUES(2027,3,2,0);
    """)
    return db


class Derived2027ReleaseExclusionTests(unittest.TestCase):
    def test_removes_all_active_related_rows_without_touching_other_editions(self):
        with fixture() as db:
            self.assertEqual(sanitize_fc27_active_release(db, expected_exclusions=2), 2)
            self.assertEqual(db.execute(
                "SELECT club_key FROM edition_club_competitions WHERE edition=2027"
            ).fetchall(), [("keep",)])
            self.assertEqual(db.execute(
                "SELECT club_key FROM fc27_stage"
            ).fetchall(), [("keep",)])
            self.assertEqual(db.execute(
                "SELECT club_key FROM edition_career_starting_league_candidates WHERE edition=2027"
            ).fetchall(), [("keep",)])
            self.assertEqual(db.execute(
                "SELECT source_label FROM source_league_groups WHERE edition=2027"
            ).fetchall(), [("Premier League",)])
            self.assertEqual(db.execute(
                "SELECT total_clubs,clubs_unresolved,career_ready FROM edition_readiness"
            ).fetchone(), (1,0,0))
            self.assertEqual(db.execute(
                "SELECT original_source_league FROM edition_club_competitions WHERE edition=2026"
            ).fetchone(), ("ISL",))
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_refuses_an_unexpected_source_exclusion_count(self):
        with fixture() as db:
            with self.assertRaisesRegex(ValueError, "exclusion count changed"):
                sanitize_fc27_active_release(db, expected_exclusions=11)
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM edition_club_competitions WHERE edition=2027"
            ).fetchone()[0], 3)


if __name__ == "__main__":
    unittest.main()

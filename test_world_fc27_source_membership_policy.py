"""FC27 source-membership acceptance never adds clubs or proves playability."""
import sqlite3
import unittest

from world_fc27_source_membership_policy import (
    SOURCE_AS_PROVIDED_COUNTS, adopt_staged_memberships,
)


def fixture():
    db=sqlite3.connect(":memory:")
    db.executescript("""
    CREATE TABLE fc27_2026_27_complete_source_competition_alignment(
      edition INTEGER, club_key TEXT, club TEXT, starting_competition TEXT,
      evidence_origin TEXT,verification_scope TEXT);
    CREATE TABLE sourced_domestic_league_clubs(
      edition INTEGER,competition_code TEXT,club_name TEXT);
    CREATE TABLE edition_readiness(edition INTEGER,career_ready INTEGER);
    INSERT INTO edition_readiness VALUES(2027,0);
    """)
    for code,count in SOURCE_AS_PROVIDED_COUNTS.items():
        for i in range(count):
            db.execute("""
              INSERT INTO fc27_2026_27_complete_source_competition_alignment
              VALUES(?,?,?,?,?,?)
            """, (2027,f"{code}:{i}",f"FC27 original club {code} {i}",
                  code,"existing_source_evidence","source_clubs_not_certified"))
    db.execute("""
       INSERT INTO fc27_2026_27_complete_source_competition_alignment
       VALUES(2026,'old:club','Unchanged old club','2026:gr.1','old','old')
    """)
    return db


class FC27SourceAsProvidedPolicyTests(unittest.TestCase):
    def test_retains_all_33_groups_and_280_original_clubs(self):
        with fixture() as db:
            before=db.execute(
                "SELECT edition,club_key,club,starting_competition "
                "FROM fc27_2026_27_complete_source_competition_alignment"
            ).fetchall()
            report=adopt_staged_memberships(db,strict=False)
            self.assertEqual(report["accepted_source_as_provided_competitions"],33)
            self.assertEqual(report["retained_source_clubs_in_accepted_groups"],280)
            self.assertEqual(report["greece_2027_original_source_clubs_kept"],4)
            self.assertEqual(report["german_second_division_original_source_clubs_kept"],18)
            self.assertTrue(report["playability_unchanged"])
            self.assertEqual(before,db.execute(
                "SELECT edition,club_key,club,starting_competition "
                "FROM fc27_2026_27_complete_source_competition_alignment"
            ).fetchall())
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM fc27_accepted_source_as_provided_clubs"
            ).fetchone()[0],280)
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM fc27_source_as_provided_membership_policy "
                "WHERE independent_fixture_roster_verified=0 "
                "AND playability='not_changed_by_membership_policy'"
            ).fetchone()[0],33)
            self.assertEqual(db.execute(
                "SELECT career_ready FROM edition_readiness WHERE edition=2027"
            ).fetchone()[0],0)

    def test_rejects_club_count_drift_and_new_fixture_evidence(self):
        with fixture() as db:
            db.execute("""
              DELETE FROM fc27_2026_27_complete_source_competition_alignment
              WHERE club_key='2027:gr.1:0'
            """)
            with self.assertRaisesRegex(ValueError,"membership/count changed"):
                adopt_staged_memberships(db,strict=False)
        with fixture() as db:
            db.execute("""
              INSERT INTO sourced_domestic_league_clubs
              VALUES(2027,'2027:gr.1','Real dated fixture member')
            """)
            with self.assertRaisesRegex(ValueError,"now has independent fixtures"):
                adopt_staged_memberships(db,strict=False)

    def test_career_readiness_remains_closed(self):
        with fixture() as db:
            db.execute("UPDATE edition_readiness SET career_ready=1 WHERE edition=2027")
            with self.assertRaisesRegex(ValueError,"cannot activate"):
                adopt_staged_memberships(db,strict=False)


if __name__=="__main__":
    unittest.main()

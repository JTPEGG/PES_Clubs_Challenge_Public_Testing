"""Completed FC27 career -> source-key PES staging, no native IDs invented."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from test_world_fc27_app_pes_squad_sync import fixtures
from world_fc27_app_pes_squad_sync import install
from scripts.stage_fc27_completed_career_squads import (
    build_completed_career_review,STAGED_DB,REPORT)


def make_files(directory,*,closed=True,correct_owner=True):
    root=Path(directory)
    stage=root/"source_app_stage.sqlite"
    source_world,source_catalogue=fixtures(root)
    install(source_world,source_catalogue,strict=False)
    source_world.commit()
    with sqlite3.connect(stage) as disk:
        source_world.backup(disk)
    source_world.close()
    career=root/"isolated_career.sqlite"
    with sqlite3.connect(career) as db:
        db.executescript("""
            CREATE TABLE world_career_saves(
                career_id TEXT,dataset_id TEXT,state TEXT);
            CREATE TABLE world_career_preseason_windows(
                window_id INTEGER,career_id TEXT,season_index INTEGER,
                status TEXT,closed_at TEXT,duration_seconds INTEGER);
            CREATE TABLE world_career_offers(
                career_id TEXT,status TEXT);
            CREATE TABLE world_career_preseason_registration_events(
                window_id INTEGER,offer_id INTEGER,career_id TEXT,
                player_id INTEGER,from_club_id INTEGER,to_club_id INTEGER);
            CREATE TABLE world_career_registrations(
                career_id TEXT,player_id INTEGER,club_id INTEGER);
            CREATE TABLE world_dataset_pes_v2_player_map(
                dataset_id TEXT,source_key TEXT,world_id INTEGER);
            CREATE TABLE world_dataset_pes_v2_club_map(
                dataset_id TEXT,source_key TEXT,world_id INTEGER);
        """)
        dataset="fc27-warehouse-659-mens-2026-27"
        db.execute("INSERT INTO world_career_saves VALUES(?,?,'sandbox')",
                   ("career-1",dataset))
        db.execute("""INSERT INTO world_career_preseason_windows VALUES
            (8,'career-1',1,?, ?,1800)""",(
              "closed" if closed else "open",
              "2026-08-01T00:30:01+00:00" if closed else None))
        db.executemany("""INSERT INTO world_dataset_pes_v2_player_map
            VALUES(?,?,?)""",
            ((dataset,f"P{i}",i+100) for i in range(1,5)))
        db.executemany("""INSERT INTO world_dataset_pes_v2_club_map
            VALUES(?,?,?)""",
            ((dataset,f"C{i:03d}",i+1) for i in range(659)))
        db.execute("""INSERT INTO world_career_preseason_registration_events
                      VALUES(8,71,'career-1',104,345,1)""")
        db.execute("""INSERT INTO world_career_registrations
                      VALUES('career-1',104,?)""",
                      (1 if correct_owner else 345,))
    return stage,career


class CareerDeadlineSquadBridgeTests(unittest.TestCase):
    def test_closed_market_is_staged_using_exact_original_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage,career=make_files(tmp)
            output=Path(tmp)/"review"
            result=build_completed_career_review(stage,career,"career-1",
                output,strict_source_counts=False)
            self.assertEqual(result["handoff"]["deadline_events"],1)
            self.assertEqual(result["handoff"]["transfers_applied"],1)
            self.assertEqual(result["squad_preview"][
                "registered_players_currently_at_playable_clubs"],4)
            self.assertFalse(result["native_PES_EDIT_file_created"])
            self.assertTrue((output/REPORT).is_file())
            with sqlite3.connect(output/STAGED_DB) as db:
                self.assertEqual(db.execute("""SELECT current_club_key,
                    registration_revision FROM fc27_app_player_registration
                    WHERE player_key='P4'""").fetchone(),("C000",1))
                self.assertEqual(db.execute(
                    "SELECT COUNT(*) FROM fc27_app_transfer_ledger"
                ).fetchone()[0],1)
                self.assertEqual(db.execute(
                    "PRAGMA integrity_check").fetchone()[0],"ok")
            with sqlite3.connect(stage) as original:
                self.assertEqual(original.execute("""SELECT current_club_key
                    FROM fc27_app_player_registration
                    WHERE player_key='P4'""").fetchone()[0],"C344")
            with sqlite3.connect(career) as preserved:
                self.assertEqual(preserved.execute("""SELECT club_id FROM
                    world_career_registrations WHERE player_id=104"""
                    ).fetchone()[0],1)

    def test_unfinished_market_cannot_stage_a_transfer(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage,career=make_files(tmp,closed=False)
            out=Path(tmp)/"not_allowed"
            with self.assertRaisesRegex(ValueError,"must finish"):
                build_completed_career_review(
                    stage,career,"career-1",out,strict_source_counts=False)
            self.assertFalse(out.exists())

    def test_conflicting_original_registrations_fail_without_partial_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage,career=make_files(tmp,correct_owner=False)
            out=Path(tmp)/"bad-review"
            with self.assertRaisesRegex(ValueError,"sealed career registration"):
                build_completed_career_review(
                    stage,career,"career-1",out,strict_source_counts=False)
            self.assertFalse(out.exists())
            with sqlite3.connect(stage) as original:
                self.assertEqual(original.execute("""SELECT current_club_key
                  FROM fc27_app_player_registration WHERE player_key='P4'"""
                  ).fetchone()[0],"C344")

    def test_real_source_counts_required_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage,career=make_files(tmp)
            out=Path(tmp)/"not-full-source"
            with self.assertRaisesRegex(ValueError,"17,593"):
                build_completed_career_review(stage,career,"career-1",out)
            self.assertFalse(out.exists())


if __name__=="__main__":
    unittest.main()

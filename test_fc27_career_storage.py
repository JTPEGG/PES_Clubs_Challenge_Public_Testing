"""Isolated regression tests; never connect to a live Supabase project."""
import ast
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fc27_career_storage import (
    CareerSaveStore,
    assert_isolated_target,
    file_sha256,
    make_career_snapshot,
    restore_career_snapshot,
)

DEV = "bjahvrmzcpqrynmoxokb"
PROD = "pxuyddcajtpkntnsugdg"


class CareerSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db_path = self.root / "world.sqlite"
        with sqlite3.connect(self.db_path) as db:
            db.executescript("""
                CREATE TABLE world_dataset_entries (club_id TEXT PRIMARY KEY, rating INT);
                INSERT INTO world_dataset_entries VALUES ('hull', 75);
                CREATE TABLE world_career_saves (
                    career_id TEXT PRIMARY KEY, club_id TEXT NOT NULL
                );
                CREATE TABLE world_career_offers (
                    offer_id INTEGER PRIMARY KEY,
                    career_id TEXT REFERENCES world_career_saves(career_id),
                    fee INTEGER
                );
                """)
        self.frozen_copy = self.root / "frozen.sqlite"
        shutil.copy2(self.db_path, self.frozen_copy)
        self.source_sha = file_sha256(self.frozen_copy)

    def _career_changes(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute("INSERT INTO world_career_saves VALUES('jake', 'hull')")
            db.execute("INSERT INTO world_career_offers VALUES(1,'jake',2500000)")
            db.execute("INSERT INTO world_career_offers VALUES(2,'jake',3100000)")
            # These deliberately untrusted source alterations must not be saved.
            db.execute("UPDATE world_dataset_entries SET rating=99 WHERE club_id='hull'")

    def test_restore_only_career_rows_and_never_static_world(self):
        self._career_changes()
        blob = make_career_snapshot(self.db_path, self.source_sha)
        self.assertTrue(blob.startswith(b"FC27C1\x00"))
        self.assertLess(len(blob), 5000)
        shutil.copy2(self.frozen_copy, self.db_path)
        self.assertEqual(restore_career_snapshot(self.db_path, blob, self.source_sha), 2)
        with sqlite3.connect(self.db_path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM world_career_saves").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM world_career_offers").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT rating FROM world_dataset_entries").fetchone()[0], 75)
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_snapshot_restores_dynamic_tables_missing_from_frozen_world(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute("CREATE TABLE world_career_market_inbox(id TEXT PRIMARY KEY, message TEXT)")
            db.execute("INSERT INTO world_career_market_inbox VALUES('one','saved')")
        blob = make_career_snapshot(self.db_path, self.source_sha)
        shutil.copy2(self.frozen_copy, self.db_path)
        restore_career_snapshot(self.db_path, blob, self.source_sha)
        with sqlite3.connect(self.db_path) as db:
            self.assertEqual(db.execute("SELECT message FROM world_career_market_inbox").fetchone()[0], "saved")

    def test_different_source_fails_closed_without_modifying_careers(self):
        self._career_changes()
        blob = make_career_snapshot(self.db_path, self.source_sha)
        shutil.copy2(self.frozen_copy, self.db_path)
        with self.assertRaisesRegex(RuntimeError, "source release changed"):
            restore_career_snapshot(self.db_path, blob, "0" * 64)
        with sqlite3.connect(self.db_path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM world_career_offers").fetchone()[0], 0)

    def test_invalid_save_does_not_change_database(self):
        with self.assertRaisesRegex(RuntimeError, "header"):
            restore_career_snapshot(self.db_path, b"bad", self.source_sha)
        with self.assertRaisesRegex(RuntimeError, "decompressed"):
            restore_career_snapshot(self.db_path, b"FC27C1\x00broken", self.source_sha)
        self.assertEqual(file_sha256(self.frozen_copy), file_sha256(self.db_path))

    def test_no_connection_configuration_leaves_local_file_untouched(self):
        storage = CareerSaveStore(self.db_path, database_url="")
        self.assertFalse(storage.restore())
        storage.schedule_upload()
        self.assertFalse(storage.status()["enabled"])
        self.assertIsNone(storage.upload_thread)


class ConnectionIsolationTests(unittest.TestCase):
    def test_development_host_allowed(self):
        assert_isolated_target(f"postgresql://postgres:pw@db.{DEV}.supabase.co:5432/postgres")
        assert_isolated_target(
            f"postgresql://fc27_app.{DEV}:pw@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"
        )

    def test_production_and_unrelated_hosts_refused(self):
        for url in (
            f"postgresql://postgres:pw@db.{PROD}.supabase.co:5432/postgres",
            f"postgresql://fc27_app.{PROD}:pw@aws-0-eu-west-1.pooler.supabase.com:5432/postgres",
            "postgresql://postgres:pw@another-provider.example.com:5432/postgres",
        ):
            with self.subTest(url=url), self.assertRaisesRegex(RuntimeError, "non-development"):
                assert_isolated_target(url)


class SqliteCommitHookTests(unittest.TestCase):
    def test_only_successful_writes_trigger_backup(self):
        path = Path(__file__).with_name("world_career_play.py")
        syntax = ast.parse(path.read_text(encoding="utf-8"))
        factory_owner = next(
            node for node in syntax.body
            if isinstance(node, ast.FunctionDef) and node.name == "create_play_blueprint"
        )
        class_node = next(
            node for node in factory_owner.body
            if isinstance(node, ast.ClassDef) and node.name == "CareerPersistingConnection"
        )
        called = []
        scope = {"sqlite3": sqlite3, "on_career_commit": lambda: called.append(True)}
        exec(compile(ast.Module(body=[class_node], type_ignores=[]), str(path), "exec"), scope)
        with tempfile.TemporaryDirectory() as tmp:
            db = sqlite3.connect(str(Path(tmp) / "test.sqlite"),
                                 factory=scope["CareerPersistingConnection"])
            db.execute("CREATE TABLE test (x INT)")
            db.commit()
            db._persist_ready = True
            db.execute("SELECT * FROM test")
            db.commit()
            self.assertEqual(len(called), 0)
            with db:
                db.execute("INSERT INTO test VALUES (1)")
            self.assertEqual(len(called), 1)
            db.execute("INSERT INTO test VALUES (2)")
            db.commit()
            self.assertEqual(len(called), 2)
            try:
                with db:
                    db.execute("INSERT INTO test VALUES (3)")
                    raise ValueError("rollback")
            except ValueError:
                pass
            self.assertEqual(len(called), 2)
            db.close()


if __name__ == "__main__":
    unittest.main()

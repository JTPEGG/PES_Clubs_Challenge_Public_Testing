"""Persist only FC27 career state, never the immutable 659-club warehouse.

The frozen FC27 source database remains the local SQLite working database.
Only world_career_* tables are snapshotted into an isolated Supabase project.
Uploads run on one coalescing background thread so a scouting filter, inbox
decision or AI simulation does not wait for a PostgreSQL round-trip.

On startup, restore fails CLOSED if a remote save is expected but unavailable.
The same checksum-pinned FC27 source must be present on every restore.
"""
from __future__ import annotations

import atexit
import hashlib
import logging
import os
import sqlite3
import threading
import time
import zlib
from pathlib import Path
from urllib.parse import unquote, urlsplit

PROJECT_REF = "bjahvrmzcpqrynmoxokb"
SAVE_KEY = "fc27_manual_v2"
MAGIC = b"FC27C1\x00"
CAREER_PREFIX = "world_career_"
CAREER_EXTRAS = frozenset(("world_fc27_free_agent_offers",
                          "world_fc27_free_agent_events"))
META_TABLE = "_fc27_career_storage_meta"
LOG = logging.getLogger(__name__)


def assert_isolated_target(url: str) -> None:
    """Never allow FC27 credentials to point at the production save project."""
    if not url:
        return
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower()
    username = unquote(parsed.username or "")
    # Both roles are restricted to this dedicated development project.
    # The new preview uses its own role and save key, so credentials and
    # snapshots from the existing FC27 preview are never overwritten.
    authorised_roles = ("fc27_app", "fc27_v2_app")
    direct = (hostname == f"db.{PROJECT_REF}.supabase.co" and
              username in authorised_roles and parsed.port == 5432)
    pooler = (hostname.endswith(".pooler.supabase.com") and
              username in tuple(f"{role}.{PROJECT_REF}" for role in authorised_roles)
              and parsed.port == 5432)
    if parsed.scheme not in ("postgres", "postgresql") or not (
            parsed.password and (direct or pooler)):
        raise RuntimeError("FC27 career persistence refused a non-development database target")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _career_tables(db):
    return [(name, statement) for name, statement in db.execute(
        "SELECT name,sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL ORDER BY name"
    ) if name.startswith(CAREER_PREFIX) or name in CAREER_EXTRAS]


def _columns(db, table: str):
    # Names come only from SQLite's own schema, never form/user input.
    return [row[1] for row in db.execute(f'PRAGMA table_xinfo("{table}")') if row[6] == 0]


def make_career_snapshot(path: Path, frozen_sha256: str) -> bytes:
    """Build a small, independent SQLite image of mutable career tables."""
    payload = sqlite3.connect(":memory:")
    live = sqlite3.connect(f"file:{Path(path).resolve().as_posix()}?mode=ro",
                           uri=True, timeout=8)
    try:
        payload.execute("PRAGMA foreign_keys=OFF")
        live.execute("BEGIN")
        for table, statement in _career_tables(live):
            payload.execute(statement)
            columns = _columns(live, table)
            if not columns:
                raise RuntimeError(f"Career table has no insertable columns: {table}")
            names = ",".join(f'"{name}"' for name in columns)
            placeholders = ",".join("?" for _ in columns)
            query = f'SELECT {names} FROM "{table}"'
            insert = f'INSERT INTO "{table}"({names}) VALUES({placeholders})'
            cursor = live.execute(query)
            while rows := cursor.fetchmany(250):
                payload.executemany(insert, rows)
        live.rollback()
        payload.execute(
            f"CREATE TABLE {META_TABLE}(frozen_sha256 TEXT NOT NULL, format_version INTEGER NOT NULL)"
        )
        payload.execute(
            f"INSERT INTO {META_TABLE}(frozen_sha256,format_version) VALUES(?,1)",
            (frozen_sha256,),
        )
        payload.commit()
        if payload.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RuntimeError("FC27 career snapshot failed integrity check")
        return MAGIC + zlib.compress(payload.serialize(), level=6)
    finally:
        live.close()
        payload.close()


def restore_career_snapshot(path: Path, stored: bytes, frozen_sha256: str) -> int:
    """Validate before writing; transactionally apply the exact career tables."""
    if not stored.startswith(MAGIC):
        raise RuntimeError("Invalid FC27 career snapshot header")
    try:
        raw = zlib.decompress(stored[len(MAGIC):])
    except zlib.error as exc:
        raise RuntimeError("FC27 career snapshot cannot be decompressed") from exc
    snapshot = sqlite3.connect(":memory:")
    try:
        snapshot.deserialize(raw)
        if snapshot.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RuntimeError("FC27 career snapshot is corrupt")
        metadata = snapshot.execute(
            f"SELECT frozen_sha256,format_version FROM {META_TABLE}"
        ).fetchone()
        if metadata != (frozen_sha256, 1):
            raise RuntimeError("FC27 source release changed; refusing incompatible career restore")
        tables = _career_tables(snapshot)
        dest = sqlite3.connect(str(path), timeout=10)
        try:
            dest.execute("PRAGMA foreign_keys=OFF")
            dest.execute("BEGIN IMMEDIATE")
            for table, create_sql in tables:
                present = dest.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                if not present:
                    dest.execute(create_sql)
                src_cols = _columns(snapshot, table)
                dst_cols = _columns(dest, table)
                if not src_cols or not set(src_cols).issubset(dst_cols):
                    raise RuntimeError(f"FC27 career table schema incompatible: {table}")
                names = ",".join(f'"{name}"' for name in src_cols)
                placeholders = ",".join("?" for _ in src_cols)
                dest.execute(f'DELETE FROM "{table}"')
                rows = snapshot.execute(f'SELECT {names} FROM "{table}"').fetchall()
                if rows:
                    dest.executemany(
                        f'INSERT INTO "{table}"({names}) VALUES({placeholders})', rows
                    )
            if dest.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RuntimeError("Restored FC27 source failed SQLite integrity check")
            violated = dest.execute("PRAGMA foreign_key_check").fetchone()
            if violated is not None:
                raise RuntimeError(f"Restored FC27 career has invalid references: {violated}")
            dest.commit()
        except Exception:
            dest.rollback()
            raise
        finally:
            dest.close()
        return len(tables)
    finally:
        snapshot.close()


class CareerSaveStore:
    """One background save writer for all mutable FC27 career tables.

    The source fingerprint is based on pinned immutable release archives,
    not unstable SQLite file bytes or build-time index creation.
    """
    def __init__(self, path: Path, database_url: str | None = None,
                 source_fingerprint: str | None = None):
        self.path = Path(path)
        self.url = (os.getenv("FC27_DATABASE_URL", "") if database_url is None
                    else database_url)
        assert_isolated_target(self.url)
        self.frozen_sha256 = source_fingerprint or file_sha256(self.path)
        if (len(self.frozen_sha256)!=64 or any(c not in "0123456789abcdef"
                                               for c in self.frozen_sha256)):
            raise ValueError("Invalid immutable source fingerprint")
        self.lock = threading.Lock()
        self.pending_generation = 0
        self.saved_generation = 0
        self.upload_thread = None
        self.last_error = None
        self.last_saved_at = None
        if self.url:
            atexit.register(self.flush_on_exit)

    def _connect_pg(self):
        import psycopg2
        return psycopg2.connect(self.url, sslmode="require", connect_timeout=8)

    def restore(self):
        if not self.url:
            return False
        # A network error must fail startup, never silently drop saved careers.
        with self._connect_pg() as pg:
            with pg.cursor() as cur:
                cur.execute(
                    "SELECT db_bytes FROM fc27_storage.pes_save_store WHERE save_key=%s",
                    (SAVE_KEY,),
                )
                row = cur.fetchone()
        if not row:
            return False
        restored_tables = restore_career_snapshot(
            self.path, bytes(row[0]), self.frozen_sha256
        )
        LOG.info("FC27 career snapshot restored (%d mutable tables)", restored_tables)
        return True

    def _upload_once(self):
        blob = make_career_snapshot(self.path, self.frozen_sha256)
        with self._connect_pg() as pg:
            with pg.cursor() as cur:
                cur.execute(
                    """INSERT INTO fc27_storage.pes_save_store(save_key,db_bytes,updated_at)
                       VALUES(%s,%s,NOW())
                       ON CONFLICT(save_key)
                       DO UPDATE SET db_bytes=EXCLUDED.db_bytes,updated_at=NOW()""",
                    (SAVE_KEY, blob),
                )

    def schedule_upload(self):
        if not self.url:
            return
        with self.lock:
            self.pending_generation += 1
            if self.upload_thread is None or not self.upload_thread.is_alive():
                self.upload_thread = threading.Thread(
                    target=self._drain, name="fc27-career-save", daemon=True
                )
                self.upload_thread.start()

    def _drain(self):
        delay = 1
        while True:
            with self.lock:
                generation = self.pending_generation
            try:
                self._upload_once()
            except Exception as exc:
                self.last_error = str(exc)
                LOG.exception("FC27 career persistence failed; retrying")
                time.sleep(delay)
                delay = min(delay * 2, 30)
                continue
            delay = 1
            with self.lock:
                self.saved_generation = generation
                self.last_error = None
                self.last_saved_at = time.time()
                if self.pending_generation == generation:
                    self.upload_thread = None
                    return

    def flush_on_exit(self):
        with self.lock:
            thread = self.upload_thread
        if thread and thread.is_alive():
            thread.join(timeout=12)

    def status(self):
        with self.lock:
            return {
                "enabled": bool(self.url),
                "saved": self.saved_generation == self.pending_generation,
                "pending": self.pending_generation != self.saved_generation,
                "last_saved_at": self.last_saved_at,
                "error": bool(self.last_error),
            }

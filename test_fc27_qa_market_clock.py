"""QA-only virtual clock must not weaken the real 30-minute deadline."""
import sqlite3
import unittest
from datetime import datetime,timedelta,timezone

from scripts.fc27_warehouse_659_market_smoke import isolated_simulation_clock
from world_preseason_window import (
    _utc,assert_window_allows_negotiation,window_snapshot)


class FC27QAClockTests(unittest.TestCase):
    def test_expensive_simulation_uses_due_tick_and_restores_real_deadline(self):
        con=sqlite3.connect(":memory:")
        con.execute("""CREATE TABLE world_career_preseason_windows(
            window_id INTEGER PRIMARY KEY,career_id TEXT,season_index INTEGER,
            started_at TEXT,deadline_at TEXT,closed_at TEXT,status TEXT,
            duration_seconds INTEGER,policy_version TEXT)""")
        started=datetime(2026,1,1,tzinfo=timezone.utc)
        deadline=started+timedelta(seconds=1800)
        con.execute("""INSERT INTO world_career_preseason_windows VALUES(
            1,?,1,?,?,NULL,'open',1800,'qa')""",
            ("disposable",(started.isoformat(timespec="seconds")),
             deadline.isoformat(timespec="seconds")))
        due=started+timedelta(seconds=1766)
        try:
            # Actual real UTC is *months* after this disposable window.
            with self.assertRaisesRegex(ValueError,"deadline passed"):
                assert_window_allows_negotiation(con,career_id="disposable")
            with isolated_simulation_clock(due):
                self.assertEqual(
                    assert_window_allows_negotiation(
                        con,career_id="disposable")["remaining_seconds"],34)
                self.assertEqual(
                    window_snapshot(con,career_id="disposable")["state"],"open")
                with self.assertRaisesRegex(ValueError,"deadline passed"):
                    assert_window_allows_negotiation(
                        con,career_id="disposable",
                        now=deadline+timedelta(seconds=1))
            with self.assertRaisesRegex(ValueError,"deadline passed"):
                assert_window_allows_negotiation(con,career_id="disposable")
        finally:
            con.close()

    def test_simulation_clock_rejects_naive_datetime_and_reverts_on_exception(self):
        before=_utc()
        with self.assertRaisesRegex(ValueError,"timezone-aware"):
            with isolated_simulation_clock(datetime(2026,1,1)):
                pass
        with self.assertRaisesRegex(RuntimeError,"expected"):
            with isolated_simulation_clock(
                    datetime(2026,1,1,tzinfo=timezone.utc)):
                raise RuntimeError("expected")
        self.assertGreaterEqual(_utc(),before)


if __name__=="__main__":
    unittest.main()

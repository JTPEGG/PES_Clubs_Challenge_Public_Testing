"""Isolated SQLite regression suite for persistent per-career management."""
import sqlite3
import unittest
from world_career_management import (
    initialize_career_management,record_contract,set_initial_confidence,
    record_board_event,career_management_snapshot,
)


def fixture():
    c=sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys=ON")
    c.executescript("""
        CREATE TABLE world_career_saves(career_id TEXT PRIMARY KEY);
        CREATE TABLE world_clubs(club_id INTEGER PRIMARY KEY);
        CREATE TABLE world_players(player_id INTEGER PRIMARY KEY);
        CREATE TABLE world_career_club_ledger(
            career_id TEXT,club_id INTEGER,transfer_budget INTEGER,
            weekly_wage_budget INTEGER,committed_fees INTEGER,
            committed_wages INTEGER,
            PRIMARY KEY(career_id,club_id));
        CREATE TABLE world_career_registrations(
            career_id TEXT,player_id INTEGER,club_id INTEGER,
            PRIMARY KEY(career_id,player_id));
        CREATE TABLE world_career_offers(
            offer_id INTEGER PRIMARY KEY,career_id TEXT,buying_club_id INTEGER,
            offered_fee INTEGER,demanded_fee INTEGER,
            offered_wage_weekly INTEGER,status TEXT);
        INSERT INTO world_career_saves VALUES('career-a'),('career-b');
        INSERT INTO world_clubs VALUES(1),(2);
        INSERT INTO world_players VALUES(101),(102);
        INSERT INTO world_career_club_ledger VALUES
            ('career-a',1,10000000,200000,1000000,30000),
            ('career-a',2,20000000,400000,0,0),
            ('career-b',1,900000,10000,0,0);
        INSERT INTO world_career_registrations VALUES
            ('career-a',101,1),('career-a',102,2),('career-b',101,1);
        INSERT INTO world_career_offers VALUES
            (1,'career-a',1,2000000,2500000,5000,'countered'),
            (2,'career-a',1,1500000,1500000,7000,'agreed_future');
    """)
    initialize_career_management(c)
    return c

class CareerManagementTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture()
    def tearDown(self):
        self.db.close()

    def test_idempotent_migration_does_not_rewrite_existing_rows(self):
        record_contract(self.db,career_id="career-a",player_id=101,club_id=1,
                        wage_weekly=20000,source_note="sandbox input")
        initialize_career_management(self.db)
        self.assertEqual(len(self.db.execute(
            "SELECT * FROM world_career_management_contracts").fetchall()),1)

    def test_contracts_do_not_invent_wages_and_expiry(self):
        record_contract(self.db,career_id="career-a",player_id=101,club_id=1)
        row=self.db.execute(
            "SELECT wage_weekly,end_date FROM world_career_management_contracts").fetchone()
        self.assertEqual(row,(None,None))

    def test_contract_requires_correct_career_registration(self):
        with self.assertRaises(ValueError):
            record_contract(self.db,career_id="career-a",player_id=102,club_id=1)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM world_career_management_contracts").fetchone()[0],0)

    def test_contract_isolation_between_careers(self):
        record_contract(self.db,career_id="career-a",player_id=101,club_id=1,
                        wage_weekly=35000)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM world_career_management_contracts WHERE career_id='career-b'").fetchone()[0],0)

    def test_contract_does_not_silently_overwrite(self):
        data=dict(career_id="career-a",player_id=101,club_id=1,
                  wage_weekly=35000)
        self.assertTrue(record_contract(self.db,**data))
        self.assertFalse(record_contract(self.db,**data))
        with self.assertRaises(ValueError):
            record_contract(self.db,**{**data,"wage_weekly":40000})

    def test_trust_initially_unknown(self):
        snap=career_management_snapshot(self.db,career_id="career-a",club_id=1)
        self.assertIsNone(snap["board"]["manager_confidence"])

    def test_initial_confidence_is_explicit(self):
        kwargs=dict(career_id="career-a",club_id=1,value=50)
        self.assertTrue(set_initial_confidence(self.db,**kwargs))
        self.assertFalse(set_initial_confidence(self.db,**kwargs))
        with self.assertRaises(ValueError):
            set_initial_confidence(self.db,**{**kwargs,"value":80})

    def test_event_cannot_be_applied_without_initial_trust(self):
        with self.assertRaises(ValueError):
            record_board_event(self.db,career_id="career-a",club_id=1,
                event_key="season-1",event_type="promotion",
                event_date="2026-10-14",source_note="confirmed game event")

    def test_promotion_changes_only_target_club_trust(self):
        set_initial_confidence(self.db,career_id="career-a",club_id=1,value=75)
        result=record_board_event(self.db,career_id="career-a",club_id=1,
            event_key="season-1-promotion",event_type="promotion",
            event_date="2026-10-14",source_note="confirmed promotion")
        self.assertEqual(result,95)
        self.assertIsNone(career_management_snapshot(
            self.db,career_id="career-b",club_id=1)["board"]["manager_confidence"])

    def test_replay_does_not_double_apply(self):
        set_initial_confidence(self.db,career_id="career-a",club_id=1,value=55)
        args=dict(career_id="career-a",club_id=1,event_key="event-x",
                  event_type="objective_met",event_date="2026-10-14",
                  source_note="manager review")
        self.assertEqual(record_board_event(self.db,**args),60)
        self.assertEqual(record_board_event(self.db,**args),60)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM world_career_management_events").fetchone()[0],1)

    def test_idempotency_key_reuse_rejected(self):
        set_initial_confidence(self.db,career_id="career-a",club_id=1,value=55)
        args=dict(career_id="career-a",club_id=1,event_key="event-x",
                  event_type="objective_met",event_date="2026-10-14",
                  source_note="manager review")
        record_board_event(self.db,**args)
        with self.assertRaises(ValueError):
            record_board_event(self.db,**{**args,"event_type":"relegation"})

    def test_confidence_clamps_at_boundaries(self):
        set_initial_confidence(self.db,career_id="career-a",club_id=1,value=2)
        self.assertEqual(record_board_event(self.db,career_id="career-a",club_id=1,
            event_key="bad",event_type="relegation",event_date="2026-10-14",
            source_note="confirmed"),0)

    def test_snapshot_uses_existing_reserved_funds_once(self):
        snap=career_management_snapshot(self.db,career_id="career-a",club_id=1)
        self.assertEqual(snap["finances"]["available_transfer_budget"],5_000_000)
        self.assertEqual(snap["finances"]["weekly_wages"]["remaining"],163_000)

    def test_wrong_club_or_career_blocked(self):
        with self.assertRaises(ValueError):
            career_management_snapshot(self.db,career_id="career-b",club_id=2)

    def test_source_backed_requires_provenance(self):
        with self.assertRaises(ValueError):
            record_contract(self.db,career_id="career-a",player_id=101,
                club_id=1,wage_weekly=5000,source_kind="source_backed")

if __name__=="__main__":
    unittest.main()

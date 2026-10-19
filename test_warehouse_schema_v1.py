"""Test the warehouse specification without altering any existing career database."""
import re
import sqlite3
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCHEMA = (ROOT / "warehouse" / "schema_v1.sql").read_text(encoding="utf-8")
DICTIONARY = (ROOT / "docs" / "warehouse" / "DATA_DICTIONARY_V1.md").read_text(
    encoding="utf-8"
)
TABLES = tuple(re.findall(r"CREATE TABLE IF NOT EXISTS (wh_\w+)", SCHEMA))


class WarehouseSchemaV1Tests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("PRAGMA foreign_keys=ON")
        # Existing authoritative parent tables, deliberately kept separate.
        self.db.executescript("""
        CREATE TABLE world_datasets(dataset_id TEXT PRIMARY KEY);
        CREATE TABLE world_players(player_id INTEGER PRIMARY KEY);
        CREATE TABLE world_clubs(club_id INTEGER PRIMARY KEY);
        CREATE TABLE world_competitions(competition_id TEXT PRIMARY KEY);
        INSERT INTO world_datasets VALUES('england-2026-27-fc27');
        INSERT INTO world_players VALUES(11),(12);
        INSERT INTO world_clubs VALUES(31),(32);
        INSERT INTO world_competitions VALUES('ENG1');
        """)
        self.db.executescript(SCHEMA)
        self.db.execute("""INSERT INTO wh_sources
            (source_id,name,rights_basis,source_version)
            VALUES('test-source','Fictional QA','original_research','v1')""")
        self.dataset = "england-2026-27-fc27"

    def tearDown(self):
        self.db.close()

    def test_additive_and_repeatable(self):
        self.db.executescript(SCHEMA)
        self.assertEqual(
            set(TABLES),
            {row[0] for row in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'wh_%'"
            )}
        )
        self.assertNotIn(
            "world_career_saves",
            {row[0] for row in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
        )

    def test_multiple_alternatives_one_primary_and_optional_suitability(self):
        source = "test-source"
        for position, kind, suitability in [
            ("RB", "primary", 85),
            ("CB", "alternative", 81),
            ("LB", "alternative", None),
            ("DM", "alternative", 73),
        ]:
            self.db.execute("""INSERT INTO wh_player_positions
                (dataset_id,player_id,position_code,position_kind,
                 suitability_ovr,origin,source_id)
                 VALUES(?,?,?,?,?,'source',?)""",
                (self.dataset,11,position,kind,suitability,source))
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM wh_player_positions").fetchone()[0],
            4,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("""INSERT INTO wh_player_positions
                VALUES(?,11,'ST','primary',71,'source',?,'')""",
                (self.dataset,source))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("""INSERT INTO wh_player_positions
                VALUES(?,12,'CM','primary',100,'source',?,'')""",
                (self.dataset,source))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("""INSERT INTO wh_player_positions
                VALUES(?,12,'CB','alternative',75,'source','missing-source','')""",
                (self.dataset,))

    def test_no_alternative_is_not_same_as_unreviewed(self):
        self.db.execute("""INSERT INTO wh_player_positions
          (dataset_id,player_id,position_code,position_kind,origin,source_id)
          VALUES(?,11,'GK','primary','source','test-source')""",
          (self.dataset,))
        self.db.execute("""INSERT INTO wh_player_position_reviews
          (dataset_id,player_id,review_status,source_id)
          VALUES(?,11,'verified_complete','test-source')""",
          (self.dataset,))
        self.assertEqual(
            self.db.execute("""SELECT review_status FROM wh_player_position_reviews
            WHERE player_id=11""").fetchone()[0], "verified_complete"
        )
        self.assertIsNone(
            self.db.execute("""SELECT review_status FROM wh_player_position_reviews
            WHERE player_id=12""").fetchone()
        )

    def test_attribute_personality_and_source_guards(self):
        self.db.execute("""INSERT INTO wh_player_attributes
            (dataset_id,player_id,attribute_key,value,origin,source_id)
            VALUES(?,11,'sprint_speed',91,'source','test-source')""",(self.dataset,))
        self.db.execute("""INSERT INTO wh_player_traits
            (dataset_id,player_id,trait_key,score,origin,source_id,model_version)
            VALUES(?,11,'loyalty',72,'model','test-source','persona-v1')""",
            (self.dataset,))
        for table,fields,data in [
            ("wh_player_attributes",
             "dataset_id,player_id,attribute_key,value,origin,source_id",
             (self.dataset,12,'stamina',104,'source','test-source')),
            ("wh_player_traits",
             "dataset_id,player_id,trait_key,score,origin,source_id,model_version",
             (self.dataset,12,'ambition',120,'model','test-source','v1')),
            ("wh_player_traits",
             "dataset_id,player_id,trait_key,score,origin,source_id,model_version",
             (self.dataset,12,'loyalty',60,'model','test-source',None)),
        ]:
            with self.subTest(table=table,values=data):
                with self.assertRaises(sqlite3.IntegrityError):
                    placeholders = ",".join("?" for _ in data)
                    self.db.execute(
                        f"INSERT INTO {table} ({fields}) VALUES ({placeholders})",data
                    )

    def test_stadium_one_primary_home_and_null_unknowns(self):
        self.db.execute("""INSERT INTO wh_stadiums
            (stadium_id,name,source_id) VALUES('venue-a','Example Ground','test-source')""")
        self.db.execute("""INSERT INTO wh_stadiums
            (stadium_id,name,source_id) VALUES('venue-b','Other Ground','test-source')""")
        self.db.execute("""INSERT INTO wh_club_stadiums
            (dataset_id,club_id,stadium_id) VALUES(?,31,'venue-a')""",
            (self.dataset,))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("""INSERT INTO wh_club_stadiums
                (dataset_id,club_id,stadium_id) VALUES(?,31,'venue-b')""",
                (self.dataset,))
        row=self.db.execute(
            "SELECT capacity FROM wh_stadiums WHERE stadium_id='venue-a'"
        ).fetchone()
        self.assertEqual(row,(None,))

    def test_manager_identity_and_career_appointment(self):
        self.db.execute("INSERT INTO wh_managers(manager_id,full_name) VALUES('mgr-01','Test Manager')")
        self.db.execute("""INSERT INTO wh_manager_profiles
            (dataset_id,manager_id,negotiation_aggression,origin,source_id)
            VALUES(?,'mgr-01',85,'model','test-source')""",(self.dataset,))
        self.db.execute("""INSERT INTO wh_manager_appointments
            (appointment_id,dataset_id,manager_id,club_id,started_on,
             appointment_type,origin,source_id)
            VALUES('appt01',?,'mgr-01',31,'2026-07-01','permanent',
                   'model','test-source')""",(self.dataset,))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("""INSERT INTO wh_manager_appointments
                (appointment_id,dataset_id,manager_id,club_id,started_on,
                 ended_on,appointment_type,origin,source_id)
                VALUES('appt02',?,'mgr-01',32,'2026-08-01',
                       '2026-07-01','permanent','source','test-source')""",
                       (self.dataset,))

    def test_competition_rules_and_prizes(self):
        self.db.execute("""INSERT INTO wh_competition_rules
            (dataset_id,competition_id,format,participating_clubs,
             points_for_win,points_for_draw,relegated_places,origin,source_id)
            VALUES(?,'ENG1','league',20,3,1,3,'source','test-source')""",
            (self.dataset,))
        self.db.execute("""INSERT INTO wh_competition_prizes
            (dataset_id,competition_id,finish_position,source_id,origin)
            VALUES(?,'ENG1',1,'test-source','source')""",(self.dataset,))
        self.assertIsNone(self.db.execute(
            "SELECT prize_gbp FROM wh_competition_prizes"
        ).fetchone()[0])
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("""INSERT INTO wh_competition_rules
                (dataset_id,competition_id,format,
                participating_clubs,promoted_places,origin,source_id)
                VALUES(?,'ENG1','league',20,21,'source','test-source')""",
                (self.dataset,))

    def test_dictionary_documents_all_fields(self):
        self.assertEqual(len(TABLES),16)
        for table in TABLES:
            heading=f"## `{table}`"
            self.assertIn(heading,DICTIONARY)
            start=DICTIONARY.index(heading)
            end=DICTIONARY.find("\n## ",start+len(heading))
            section=DICTIONARY[start:] if end<0 else DICTIONARY[start:end]
            cols=self.db.execute(f"PRAGMA table_info({table})").fetchall()
            for col in cols:
                with self.subTest(table=table,column=col[1]):
                    self.assertIn(f"| `{col[1]}` |",section)


if __name__=="__main__":
    unittest.main()

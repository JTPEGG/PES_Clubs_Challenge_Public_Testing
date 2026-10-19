"""Historical data identity and provenance tests without third-party data."""
import sqlite3
import unittest
from world_historical_profiles import import_enrichment

class HistoricalProfilesTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:",isolation_level=None)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE world_datasets(dataset_id TEXT PRIMARY KEY);
            CREATE TABLE world_clubs(club_id INTEGER PRIMARY KEY);
            CREATE TABLE world_players(player_id INTEGER PRIMARY KEY);
            CREATE TABLE world_dataset_entries(dataset_id TEXT,club_id INTEGER);
            CREATE TABLE world_dataset_rosters(dataset_id TEXT,player_id INTEGER,club_id INTEGER);
            CREATE TABLE world_player_source_refs(player_id INTEGER,source_name TEXT,external_id TEXT);
            INSERT INTO world_datasets VALUES ('demo-historic');
            INSERT INTO world_clubs VALUES (10),(20);
            INSERT INTO world_players VALUES (100);
            INSERT INTO world_dataset_entries VALUES
                ('demo-historic',10),('demo-historic',20);
            INSERT INTO world_dataset_rosters VALUES ('demo-historic',100,10);
            INSERT INTO world_player_source_refs VALUES
                (100,'dataset-player:demo-historic','player-100');
        """)
        self.db.execute("""CREATE TABLE world_dataset_club_refs
            (source TEXT,external_id TEXT,club_id INTEGER)""")
        self.db.execute("""INSERT INTO world_dataset_club_refs VALUES
            ('dataset-club:demo-historic','home',10),
            ('dataset-club:demo-historic','away',20)""")

    def tearDown(self):
        self.db.close()

    def payload(self):
        return dict(
            dataset_id="demo-historic",source_name="licensed-fictional-fixture",
            rights_basis="licensed",rights_note="Fixture-only permission declaration",
            managers=[{"id":"boss-001","name":"Example Manager","club":"home",
                       "preferred_formation":"4-4-2"}],
            contracts=[{"player":"player-100","club":"home",
                        "expires_on":"2005-06-30","weekly_wage_gbp":1234}],
            transfers=[],attributes=[],
            club_finances=[{"club":"home","transfer_budget_gbp":1000000,
                            "weekly_wage_budget_gbp":50000}])

    def test_import_preserves_ids_and_null_unknown(self):
        result=import_enrichment(self.db,self.payload())
        self.assertEqual(result["contracts"],1)
        self.assertEqual(self.db.execute("""SELECT player_id,expires_on,renewal_status
            FROM world_dataset_contract_snapshots""").fetchone(),
            (100,"2005-06-30","unknown"))
        self.assertEqual(self.db.execute("""SELECT club_id,full_name FROM
            world_dataset_manager_profiles""").fetchone(),(10,"Example Manager"))
        with self.assertRaisesRegex(ValueError,"already has an enrichment"):
            import_enrichment(self.db,self.payload())

    def test_invalid_club_rolls_back_every_record(self):
        payload=self.payload()
        payload["contracts"][0]["club"]="away"
        with self.assertRaisesRegex(ValueError,"parent club"):
            import_enrichment(self.db,payload)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM world_dataset_data_rights").fetchone()[0],0)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM world_dataset_manager_profiles").fetchone()[0],0)

    def test_permission_provenance_is_required(self):
        payload=self.payload()
        del payload["rights_basis"]
        with self.assertRaisesRegex(ValueError,"rights basis"):
            import_enrichment(self.db,payload)


if __name__=="__main__":
    unittest.main()

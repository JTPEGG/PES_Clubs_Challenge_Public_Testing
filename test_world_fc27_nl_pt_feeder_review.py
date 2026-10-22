"""2026/27 NL and Portugal: named real feeder clubs, not fabricated players."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from world_fc27_nl_pt_feeder_review import stage,EXPECTED
from world_fc27_career_world_playability import SCHEMA as CAREER_SCHEMA

EXTRA=Path(__file__).parent/"data/warehouse/fc27_2026_27_netherlands_portugal_feeder_clubs.json"

def prep():
    db=sqlite3.connect(":memory:")
    db.execute("CREATE TABLE edition_club_competitions(edition INTEGER,club_key TEXT,PRIMARY KEY(edition,club_key))")
    db.execute("""
      CREATE TABLE fc27_2026_27_complete_source_competition_alignment
      (edition INTEGER,club_key TEXT,club TEXT,starting_competition TEXT)
    """)
    db.execute("""
      CREATE TABLE fc27_effective_world_league_movement_scope
      (edition INTEGER,competition_code TEXT)
    """)
    db.execute("""
      CREATE TABLE fc27_mls_playable_closed_league_approval
      (edition INTEGER,competition_code TEXT)
    """)
    db.execute("""
      CREATE TABLE fc27_eight_country_playable_approval
      (edition INTEGER,competition_code TEXT,country TEXT)
    """)
    db.execute("""
      CREATE VIEW fc27_effective_manager_selectable_competitions AS
      SELECT edition,competition_code,country,'open_pyramid' AS playing_format
      FROM fc27_eight_country_playable_approval
    """)
    db.executescript(CAREER_SCHEMA)
    for i in range(93):
        db.execute("""
          INSERT INTO fc27_sourced_real_one_hop_feeder_clubs
          VALUES(2027,'2027:it.3',?,'A',0,'https://www.seriec.com/clubs',
          'league_or_federation_published_2026_27_competition_membership',0,0,0)
        """,(f"Preexisting original feeder {i}",))
    for code in EXPECTED:
        db.execute("""
          INSERT INTO fc27_feeder_pool_readiness
          VALUES(2027,?,'Test',2,'Test',0,'name_only_not_eligible_for_promotion',0,0)
        """,(code,))
    db.execute("""
      INSERT INTO fc27_feeder_pool_readiness
      VALUES(2027,'2027:fr.3','France',3,'Ligue 3',18,'reviewed',0,0)
    """)
    db.execute("""
      INSERT INTO fc27_feeder_pool_readiness
      VALUES(2027,'2027:it.3','Italy',3,'Serie C',60,'reviewed',0,0)
    """)
    return db

class NewFeederPoolTests(unittest.TestCase):
    def test_two_complete_real_lists_are_added_not_playable(self):
        with prep() as db:
            res=stage(db,EXTRA,strict=False)
            self.assertEqual(res["newly_sourced_named_feeder_clubs"],38)
            self.assertEqual(res["open_feeders_without_real_named_club_members"],0)
            self.assertEqual(res["active_four_game_feeder_club_names"],116)
            self.assertEqual(db.execute("""
               SELECT COUNT(*) FROM fc27_sourced_real_one_hop_feeder_clubs
            """).fetchone()[0],131)
            self.assertEqual(db.execute("""
               SELECT feeder_code,published_real_club_names
               FROM fc27_feeder_pool_readiness
               WHERE feeder_code IN ('2027:nl.2','2027:pt.2')
               ORDER BY feeder_code
            """).fetchall(),[("2027:nl.2",20),("2027:pt.2",18)])
            self.assertEqual(db.execute("""
              SELECT COUNT(*) FROM fc27_sourced_real_one_hop_feeder_clubs
              WHERE PES_player_squad_imported=1 OR game_promotion_registered=1
            """).fetchone()[0],0)
    def test_rejects_false_players_and_invalid_reserve_flags(self):
        cfg=json.loads(EXTRA.read_text(encoding="utf-8"))
        self.assertEqual({g["feeder_competition_code"] for g in cfg["groups"]},set(EXPECTED))
        for changed in ("original_game_player_squad_imported","clubs"):
            with tempfile.TemporaryDirectory() as tmp:
                value=json.loads(json.dumps(cfg))
                if changed=="clubs":value["groups"][0]["clubs"][0]["reserve_or_youth"]=True
                else:value["groups"][0][changed]=True
                path=Path(tmp)/"changed.json";path.write_text(json.dumps(value))
                with prep() as db:
                    with self.assertRaises(ValueError):stage(db,path,strict=False)
if __name__=="__main__":
    unittest.main()

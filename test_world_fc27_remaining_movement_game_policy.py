"""FC27: 34 delegated movement decisions keep club source immutable."""
import json
import tempfile
import unittest
from pathlib import Path

from test_world_fc27_additional_movement_rules import fixture,CONFIG as ORIGINAL
from world_fc27_additional_movement_rules import stage as source_stage
from world_fc27_remaining_movement_game_policy import (
    stage_game_defaults, PINNED
)

CONFIG=Path(__file__).parent/"data/warehouse/fc27_remaining_34_gameplay_movement_policy.json"

def populated_fixture():
    db=fixture()
    source_stage(db,ORIGINAL,strict=False)
    config=json.loads(CONFIG.read_text(encoding="utf-8"))
    present={x[0] for x in db.execute("""
      SELECT competition_code FROM fc27_2026_27_active_domestic_competitions
    """)}
    for row in config["rules"]:
        code=row["upper_code"]
        if code in present:
            continue
        level=int(code.rsplit(".",1)[-1])
        db.execute("""
          INSERT INTO fc27_2026_27_active_domestic_competitions VALUES(?,?,?,?,?)
        """,(code,row["country"],level,code,PINNED.get(code,5)))
    return db

class FC27OtherLeagueGameplayDefaultsTests(unittest.TestCase):
    def test_34_competitions_and_single_nonplayable_feeder_names(self):
        with populated_fixture() as db:
            before=db.execute("""
              SELECT * FROM fc27_2026_27_active_domestic_competitions
              ORDER BY competition_code
            """).fetchall()
            result=stage_game_defaults(db,CONFIG,strict=False)
            self.assertEqual(result["source_competitions_with_new_game_rules"],34)
            self.assertEqual(result["closed_2026_27_game_competitions"],2)
            self.assertEqual(result["new_named_nonplayable_single_step_feeders_without_squads"],32)
            self.assertEqual(db.execute("""
              SELECT COUNT(*) FROM fc27_game_only_named_immediate_feeders
            """).fetchone()[0],32)
            self.assertEqual(db.execute("""
              SELECT COUNT(*) FROM fc27_simplified_game_movement_scope
              WHERE club_squad_pool_ready=0 AND career_activated=0
            """).fetchone()[0],34)
            self.assertEqual(before,db.execute("""
              SELECT * FROM fc27_2026_27_active_domestic_competitions
              ORDER BY competition_code
            """).fetchall())
            self.assertEqual(db.execute("""
              SELECT career_ready FROM edition_readiness WHERE edition=2027
            """).fetchone()[0],0)

    def test_italy_third_tier_poland_nordics_closed_leagues_and_korea_growth(self):
        with populated_fixture() as db:
            stage_game_defaults(db,CONFIG,strict=False)
            for code, expected in [
                ("2027:pl.1",(2,1,3,0)),
                ("2027:tr.1",(2,1,3,0)),
                ("2027:gr.1",(2,0,2,0)),
                ("2027:dk.1",(2,0,2,0)),
                ("2027:it.2",(4,0,4,0)),
                ("2027:kr.1",(3,0,1,2)),
                ("2027:mx.1",(0,0,0,0)),
                ("2027:au.1",(0,0,0,0)),
            ]:
                with self.subTest(league=code):
                    self.assertEqual(db.execute("""
                      SELECT direct_promotions,playoff_promotions,
                        direct_relegations,top_division_size_delta
                      FROM fc27_simplified_game_movement_scope
                      WHERE upper_code=?
                    """,(code,)).fetchone(),expected)
            self.assertEqual(db.execute("""
              SELECT immediate_lower_code FROM fc27_simplified_game_movement_scope
              WHERE upper_code='2027:it.2'
            """).fetchone()[0],"2027:it.3")
            self.assertEqual(db.execute("""
              SELECT COUNT(*) FROM fc27_game_only_named_immediate_feeders
              WHERE original_game_club_pool_verified=0
            """).fetchone()[0],32)

    def test_reject_incorrect_league_size_or_unsanctioned_feed(self):
        original=json.loads(CONFIG.read_text(encoding="utf-8"))
        for key,value in [
            ("top_division_club_count_delta_after_season",0),
            ("feeder_original_club_squads_verified",True),
            ("game_direct_promotions",0),
        ]:
            with self.subTest(field=key),tempfile.TemporaryDirectory() as folder:
                edited=json.loads(json.dumps(original))
                edited["rules"][20][key]=value  # K League +2 in 2027
                path=Path(folder)/"modified.json"
                path.write_text(json.dumps(edited),encoding="utf-8")
                with populated_fixture() as db:
                    with self.assertRaises(ValueError):
                        stage_game_defaults(db,path,strict=False)

    def test_reject_extra_game_club_and_career_ready(self):
        with populated_fixture() as db:
            db.execute("""
              UPDATE fc27_2026_27_active_domestic_competitions
              SET active_source_clubs=99 WHERE competition_code='2027:pl.1'
            """)
            with self.assertRaisesRegex(ValueError,"Original FC27 club group changed"):
                stage_game_defaults(db,CONFIG,strict=False)
        with populated_fixture() as db:
            db.execute("UPDATE edition_readiness SET career_ready=1 WHERE edition=2027")
            with self.assertRaisesRegex(ValueError,"Do not activate"):
                stage_game_defaults(db,CONFIG,strict=False)


if __name__=="__main__":
    unittest.main()

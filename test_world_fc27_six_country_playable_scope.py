"""Six-country FC27 playable targets; prior official and gameplay data stays intact."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from test_world_fc27_broader_closed_league_scope import full_scope_fixture
from world_fc27_broader_closed_league_scope import close_peripheral_leagues
from world_fc27_six_country_playable_scope import (
    apply_six_country_scope, COUNTRY_CODES, PLAYABLE_CODES, NEWLY_CLOSED_CODES
)

CFG=Path(__file__).parent/"data/warehouse/fc27_2026_27_six_country_playable_scope.json"

def prepared_fixture():
    db=full_scope_fixture()
    close_peripheral_leagues(db,strict=False)
    db.executescript("""
      CREATE TABLE edition_club_competitions(edition INTEGER,club_key TEXT);
      CREATE TABLE fc27_2026_27_complete_source_competition_alignment(
        edition INTEGER,club_key TEXT,club TEXT,starting_competition TEXT);
    """)
    for code,n in db.execute("""
        SELECT competition_code,original_game_source_clubs
        FROM fc27_effective_world_league_movement_scope
    """).fetchall():
        for i in range(n):
            key=f"{code}:{i}"
            db.execute("INSERT INTO edition_club_competitions VALUES(2027,?)",(key,))
            db.execute("""
                INSERT INTO fc27_2026_27_complete_source_competition_alignment
                VALUES(2027,?,?,?)
            """,(key,f"Original unit test club {i}",code))
    return db


class SixCountryGameScopeTests(unittest.TestCase):
    def test_only_twelve_leagues_are_playable_targets_and_nine_extra_close(self):
        with prepared_fixture() as db:
            baseline=db.execute("""
              SELECT COUNT(*) FROM edition_club_competitions
            """).fetchone()[0]
            result=apply_six_country_scope(db,CFG,strict=False)
            self.assertEqual(result["open_intended_playable_competitions"],12)
            self.assertEqual(result["closed_background_competitions"],41)
            self.assertEqual(result["original_clubs_in_intended_playable_competitions"],240)
            self.assertEqual(result["original_clubs_in_closed_background_competitions"],419)
            self.assertEqual(set(result["newly_closed_competition_codes"]),set(NEWLY_CLOSED_CODES))
            codes={x[0] for x in db.execute("""
              SELECT competition_code FROM fc27_six_country_playable_approval
            """)}
            self.assertEqual(codes,set(PLAYABLE_CODES))
            self.assertEqual(db.execute("""
              SELECT COUNT(*) FROM fc27_intended_playable_club_candidates
            """).fetchone()[0],240)
            self.assertEqual(db.execute("""
              SELECT COUNT(*) FROM fc27_effective_named_immediate_game_feeders
            """).fetchone()[0],3)
            self.assertEqual(baseline,db.execute("""
              SELECT COUNT(*) FROM edition_club_competitions
            """).fetchone()[0])
            self.assertEqual(db.execute("""
              SELECT COUNT(*) FROM edition_readiness WHERE edition=2027 AND career_ready=1
            """).fetchone()[0],0)

    def test_new_closed_countries_disable_german_and_other_source_boundaries(self):
        with prepared_fixture() as db:
            apply_six_country_scope(db,CFG,strict=False)
            for code in NEWLY_CLOSED_CODES:
                with self.subTest(league=code):
                    self.assertEqual(db.execute("""
                      SELECT movement_policy
                      FROM fc27_effective_world_league_movement_scope
                      WHERE competition_code=?
                    """,(code,)).fetchone(),("closed",))
            for code in ("2027:be.1","2027:nl.1","2027:at.1","2027:ch.1"):
                with self.subTest(sourced_boundary=code):
                    effective=db.execute("""
                       SELECT direct_promotions,playoff_promotions,
                              direct_relegations,interdivision_playoff_places
                       FROM fc27_effective_additional_movement_after_world_closure
                       WHERE upper_code=?
                    """,(code,)).fetchone()
                    self.assertEqual(effective,(0,0,0,0))
            self.assertEqual(db.execute("""
              SELECT COUNT(*) FROM fc27_effective_core_pyramid_game_boundaries
              WHERE game_enabled=0
            """).fetchone()[0],2)
            self.assertEqual(db.execute("""
              SELECT COUNT(*) FROM fc27_effective_core_pyramid_game_boundaries
              WHERE game_enabled=1
            """).fetchone()[0],5)
            self.assertEqual(db.execute("""
              SELECT direct_promotions,playoff_promotions,direct_relegations
              FROM fc27_effective_additional_movement_after_world_closure
              WHERE upper_code='2027:it.1'
            """).fetchone(),(2,1,3))
            self.assertEqual(db.execute("""
              SELECT direct_promotions,playoff_promotions,direct_relegations
              FROM fc27_effective_additional_game_movement_rules
              WHERE upper_code='2027:at.1'
            """).fetchone(),(1,0,1))
            self.assertEqual(db.execute("""
              SELECT direct_promotions,playoff_promotions,direct_relegations
              FROM fc27_effective_additional_movement_after_world_closure
              WHERE upper_code='2027:at.1'
            """).fetchone(),(0,0,0))

    def test_rejects_added_playable_country_and_stale_source_mapping(self):
        cfg=json.loads(CFG.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as path:
            fake=json.loads(json.dumps(cfg))
            fake["open_and_intended_playable_countries"].append({
                "country":"Germany","competition_codes":["2027:de.1"]
            })
            file=Path(path)/"bad-scope.json"
            file.write_text(json.dumps(fake),encoding="utf-8")
            with prepared_fixture() as db:
                with self.assertRaisesRegex(ValueError,"Exactly six"):
                    apply_six_country_scope(db,file,strict=False)
        with prepared_fixture() as db:
            db.execute("""
              UPDATE fc27_effective_world_league_movement_scope
              SET original_game_source_clubs=999
              WHERE competition_code='2027:it.1'
            """)
            with self.assertRaisesRegex(ValueError,"Expected 240"):
                apply_six_country_scope(db,CFG,strict=False)


if __name__=="__main__":
    unittest.main()

"""FC27 broad user-delegated closed leagues: 53 canonical source codes preserved."""
import json
import sqlite3
import unittest

from test_world_fc27_remaining_movement_game_policy import populated_fixture,CONFIG
from world_fc27_remaining_movement_game_policy import stage_game_defaults
from world_fc27_broader_closed_league_scope import close_peripheral_leagues
from world_fc27_movement_gameplay_policy import apply_gameplay_decisions
from test_world_fc27_movement_gameplay_policy import DECISIONS

# Original source fixture only sets up 43 national divisions; add exact
# England/Germany/Spain and the original MLS season-format canonical identity.
CORE={
 "2027:en.1":("England",1,20),
 "2027:en.2":("England",2,24),
 "2027:en.3":("England",3,24),
 "2027:en.4":("England",4,24),
 "2027:de.1":("Germany",1,18),
 "2027:de.2":("Germany",2,18),
 "2027:de.3":("Germany",3,20),
 "2027:es.1":("Spain",1,20),
 "2027:es.2":("Spain",2,22),
 "2027:us.mls":("United States",1,30),
}

def full_scope_fixture():
    db=populated_fixture()
    db.executescript("""
      CREATE TABLE season_non_pyramid_formats(
        edition INTEGER,competition_code TEXT,
        direct_promotions INTEGER,playoff_promotions INTEGER,
        direct_relegations INTEGER);
      INSERT INTO season_non_pyramid_formats
        VALUES(2027,'2027:us.mls',0,0,0);
    """)
    present={c for (c,) in db.execute("""
       SELECT competition_code FROM fc27_2026_27_active_domestic_competitions
    """)}
    for code,(country,tier,n) in CORE.items():
        if code not in present:
            db.execute("""
              INSERT INTO fc27_2026_27_active_domestic_competitions
              VALUES(?,?,?,?,?)
            """,(code,country,tier,code,n))
    # The user decision test fixture has no independent roster for other
    # source-group competition seasons; no original FC27 team is fabricated
    # in this synthetic in-memory regression test.
    apply_gameplay_decisions(db,DECISIONS,strict=False)
    stage_game_defaults(db,CONFIG,strict=False)
    return db


class FC27BroadClosedLeagueTests(unittest.TestCase):
    def test_broad_closure_53_clubs_preserved_and_fewer_feeders(self):
        with full_scope_fixture() as db:
            before=db.execute("""
              SELECT * FROM fc27_2026_27_active_domestic_competitions
              ORDER BY competition_code
            """).fetchall()
            result=close_peripheral_leagues(db,strict=False)
            self.assertEqual(result["closed_game_domestic_competitions"],32)
            self.assertEqual(result["open_game_domestic_competitions"],21)
            self.assertEqual(result["remaining_game_one_hop_named_feeders_without_rosters"],9)
            self.assertEqual(db.execute("""
                SELECT COUNT(*) FROM fc27_effective_world_league_movement_scope
                WHERE movement_policy='closed'
            """).fetchone()[0],32)
            self.assertEqual(db.execute("""
                SELECT COUNT(*) FROM fc27_effective_named_immediate_game_feeders
            """).fetchone()[0],9)
            self.assertEqual(before,db.execute("""
              SELECT * FROM fc27_2026_27_active_domestic_competitions
              ORDER BY competition_code
            """).fetchall())
            self.assertEqual(db.execute("""
              SELECT career_ready FROM edition_readiness WHERE edition=2027
            """).fetchone()[0],0)
    def test_closed_country_examples_and_source_italian_austrian_exceptions(self):
        with full_scope_fixture() as db:
            close_peripheral_leagues(db,strict=False)
            for code in (
                "2027:kr.1","2027:ro.1","2027:se.1","2027:no.1",
                "2027:gr.1","2027:dk.1","2027:br.1","2027:sa.1",
                "2027:ch.1","2027:au.1","2027:mx.1","2027:us.mls"
            ):
                with self.subTest(closed=code):
                    self.assertEqual(db.execute("""
                      SELECT movement_policy
                      FROM fc27_effective_world_league_movement_scope
                      WHERE competition_code=?
                    """,(code,)).fetchone()[0],"closed")
            for code in ("2027:en.1","2027:de.2","2027:it.1",
                         "2027:it.2","2027:at.1","2027:pl.1",
                         "2027:tr.1","2027:sco.1","2027:pt.1",
                         "2027:ar.1"):
                with self.subTest(open=code):
                    self.assertEqual(db.execute("""
                      SELECT movement_policy
                      FROM fc27_effective_world_league_movement_scope
                      WHERE competition_code=?
                    """,(code,)).fetchone()[0],"open_pyramid")
            values=db.execute("""
              SELECT direct_promotions,playoff_promotions,direct_relegations,
                     interdivision_playoff_places
              FROM fc27_effective_additional_movement_after_world_closure
              WHERE upper_code='2027:ch.1'
            """).fetchone()
            self.assertEqual(values,(0,0,0,0))
            self.assertEqual(db.execute("""
              SELECT direct_promotions,direct_relegations,
                     conditional_exchange_places
              FROM fc27_additional_movement_boundaries
              WHERE upper_code='2027:ch.1'
            """).fetchone(),(1,1,1))
            self.assertEqual(db.execute("""
              SELECT direct_promotions,playoff_promotions,direct_relegations
              FROM fc27_effective_additional_movement_after_world_closure
              WHERE upper_code='2027:it.1'
            """).fetchone(),(2,1,3))
            self.assertEqual(db.execute("""
              SELECT direct_promotions,playoff_promotions,direct_relegations
              FROM fc27_effective_additional_movement_after_world_closure
              WHERE upper_code='2027:at.1'
            """).fetchone(),(1,0,1))
            self.assertEqual(db.execute("""
              SELECT COUNT(*) FROM fc27_effective_named_immediate_game_feeders
              WHERE competition_code='2027:ch.2'
            """).fetchone()[0],0)

    def test_changing_approved_italy_override_must_fail(self):
        with full_scope_fixture() as db:
            db.execute("""
              UPDATE fc27_user_approved_movement_game_rules
              SET playoff_promotions=0 WHERE upper_code='2027:it.1'
            """)
            with self.assertRaisesRegex(ValueError,"Italian always-playoff"):
                close_peripheral_leagues(db,strict=False)


if __name__=="__main__":
    unittest.main()

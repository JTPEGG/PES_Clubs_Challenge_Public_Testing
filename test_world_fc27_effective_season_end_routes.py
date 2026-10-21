"""Every FC27 open-playable division has one real-source immediate lower route."""
import unittest
from pathlib import Path
from test_world_fc27_eight_country_playable_scope import prepared_fixture,CFG
from test_world_fc27_mls_playable_scope import MLS,populate_existing_mls_names
from world_fc27_eight_country_playable_scope import apply_eight_country_scope
from world_fc27_mls_playable_scope import stage_mls
from world_fc27_regional_feeder_rosters import stage as stage_regional
from world_fc27_effective_season_end_routes import stage,EXPECTED

REGIONAL=Path(__file__).parent/"data/warehouse/fc27_2026_27_es_de_regional_feeder_clubs.json"

def prepared():
    db=prepared_fixture()
    apply_eight_country_scope(db,CFG,strict=False)
    populate_existing_mls_names(db)
    stage_mls(db,MLS,strict=False)
    stage_regional(db,REGIONAL,strict=False)
    return db
class AllFC27EffectiveRoutesTests(unittest.TestCase):
    def test_all_16_effective_pyramids_and_mls_separate(self):
        with prepared() as db:
            result=stage(db,strict=False)
            self.assertEqual(result["open_playable_routes_with_derived_effective_rule"],16)
            self.assertEqual(result["source_core_routes"],7)
            self.assertEqual(result["sourced_country_game_rules"],6)
            self.assertEqual(result["delegated_one_hop_rules"],1)
            self.assertEqual(result["dated_regional_rules"],2)
            routes=dict(db.execute("""
               SELECT upper_code,lower_code FROM fc27_effective_playable_season_end_routes
            """))
            self.assertEqual(routes,EXPECTED)
            self.assertEqual(db.execute("""
               SELECT COUNT(*) FROM fc27_effective_playable_season_end_routes
               WHERE executable_career_movement!=0
            """).fetchone()[0],0)
            self.assertNotIn("2027:us.mls",routes)
            for code in ("2027:de.1","2027:de.2"):
                with self.subTest(german_survival_tie=code):
                    self.assertEqual(db.execute("""
                       SELECT direct_promotions,lower_playoff_promotions,
                              upper_direct_relegations,upper_conditional_survival_places
                       FROM fc27_effective_playable_season_end_routes
                       WHERE upper_code=?
                    """,(code,)).fetchone(),(2,0,2,1))
            self.assertEqual(db.execute("""
              SELECT direct_promotions,lower_playoff_promotions,
                     upper_direct_relegations
              FROM fc27_effective_playable_season_end_routes
              WHERE upper_code='2027:it.1'
            """).fetchone(),(2,1,3))
            self.assertEqual(db.execute("""
               SELECT COUNT(*) FROM fc27_effective_playable_season_end_routes
               WHERE route_type='regional_4_up_4_down'
            """).fetchone()[0],2)
    def test_cannot_activate_mls_as_relegation_pyramid(self):
        with prepared() as db:
            db.execute("""
              UPDATE fc27_mls_playable_closed_league_approval
              SET no_promotion_or_relegation=0
            """)
            with self.assertRaises(Exception):
                stage(db,strict=False)
    def test_reject_disabled_german_route(self):
        with prepared() as db:
            db.execute("""
               UPDATE fc27_effective_core_pyramid_game_boundaries
               SET game_enabled=0 WHERE upper_code='2027:de.3'
            """)
            with self.assertRaisesRegex(ValueError,"seven official"):
                stage(db,strict=False)
if __name__=="__main__":unittest.main()

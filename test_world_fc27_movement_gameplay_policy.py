"""FC27 user-authorised game rules are separate from published regulations."""
import json
import tempfile
import unittest
from pathlib import Path

from test_world_fc27_additional_movement_rules import CONFIG as SOURCES,fixture
from world_fc27_additional_movement_rules import stage
from world_fc27_movement_gameplay_policy import apply_gameplay_decisions

DECISIONS=Path(__file__).parent/"data/warehouse/fc27_2026_27_gameplay_movement_decisions.json"

class FC27GameRulesTests(unittest.TestCase):
    def test_italian_playoff_and_austrian_direct_exchange(self):
        with fixture() as db:
            stage(db,SOURCES,strict=False)
            source_before=db.execute("""
                SELECT lower_code,upper_code,direct_promotions,
                       direct_relegations,conditional_exchange_places,
                       conditional_format
                FROM fc27_additional_movement_boundaries ORDER BY lower_code
            """).fetchall()
            result=apply_gameplay_decisions(db,DECISIONS,strict=False)
            self.assertEqual(result["explicitly_logged_gameplay_assumptions"],2)
            self.assertTrue(result["balanced_exchange_rules"])
            self.assertEqual(source_before,db.execute("""
                SELECT lower_code,upper_code,direct_promotions,
                       direct_relegations,conditional_exchange_places,
                       conditional_format
                FROM fc27_additional_movement_boundaries ORDER BY lower_code
            """).fetchall())
            it=db.execute("""
                SELECT effective_direct_promotions,effective_playoff_promotions,
                       effective_direct_relegations,
                       effective_interdivision_playoff_places,
                       effective_rule_provenance,effective_playoff_description
                FROM fc27_effective_additional_game_movement_rules
                WHERE upper_code='2027:it.1'
            """).fetchone()
            self.assertEqual(it[:5],(2,1,3,0,"explicit_user_approved_gameplay_assumption"))
            self.assertIn("Always run the play-off",it[5])
            at=db.execute("""
                SELECT effective_direct_promotions,effective_playoff_promotions,
                       effective_direct_relegations,
                       effective_interdivision_playoff_places,effective_rule_provenance,
                       effective_playoff_description
                FROM fc27_effective_additional_game_movement_rules
                WHERE upper_code='2027:at.1'
            """).fetchone()
            self.assertEqual(at[:5],(1,0,1,0,"explicit_user_approved_gameplay_assumption"))
            self.assertIn("No promotion/relegation match",at[5])
            self.assertEqual(db.execute("""
                SELECT COUNT(*) FROM fc27_effective_additional_game_movement_rules
            """).fetchone()[0],9)
            self.assertEqual(db.execute("""
                SELECT COUNT(*) FROM fc27_user_approved_movement_game_rules
                WHERE status='gameplay_assumption_not_historical_fact'
                  AND career_activated=0
            """).fetchone()[0],2)
            self.assertEqual(db.execute("""
                SELECT career_ready FROM edition_readiness WHERE edition=2027
            """).fetchone()[0],0)

    def test_rejects_unapproved_automatic_extra_promotions(self):
        base=json.loads(DECISIONS.read_text(encoding="utf-8"))
        for bad_field,new_value in (
             ("gameplay_playoff_promotions",0),
             ("gameplay_interdivision_playoff_places",1),
             ("decision_source","source_confirmed"),
        ):
            with self.subTest(field=bad_field),tempfile.TemporaryDirectory() as tmp:
                fake=json.loads(json.dumps(base))
                fake["decisions"][0][bad_field]=new_value
                path=Path(tmp)/"bad.json"
                path.write_text(json.dumps(fake),encoding="utf-8")
                with fixture() as db:
                    stage(db,SOURCES,strict=False)
                    with self.assertRaises(ValueError):
                        apply_gameplay_decisions(db,path,strict=False)

    def test_rejects_unknown_league_and_career_unlock(self):
        base=json.loads(DECISIONS.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            fake=json.loads(json.dumps(base))
            fake["decisions"][1]["lower_code"]="2027:be.2"
            path=Path(tmp)/"bad.json"
            path.write_text(json.dumps(fake),encoding="utf-8")
            with fixture() as db:
                stage(db,SOURCES,strict=False)
                with self.assertRaisesRegex(ValueError,"Only agreed"):
                    apply_gameplay_decisions(db,path,strict=False)
        with fixture() as db:
            stage(db,SOURCES,strict=False)
            db.execute("UPDATE edition_readiness SET career_ready=1 WHERE edition=2027")
            with self.assertRaisesRegex(ValueError,"cannot enable"):
                apply_gameplay_decisions(db,DECISIONS,strict=False)


if __name__=="__main__":
    unittest.main()

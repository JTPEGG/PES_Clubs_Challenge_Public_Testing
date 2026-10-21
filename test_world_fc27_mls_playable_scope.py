"""MLS is playable without promotion or relegation, sourced 30-club conferences."""
import json
import tempfile
import unittest
from pathlib import Path
from test_world_fc27_eight_country_playable_scope import prepared_fixture, CFG
from world_fc27_eight_country_playable_scope import apply_eight_country_scope
from world_fc27_mls_playable_scope import stage_mls
MLS=Path(__file__).parent/"data/warehouse/fc27_2026_mls_playable_competition.json"

class MLSPlayable2026Tests(unittest.TestCase):
    def test_selectable_closed_league_2026_calendar_and_cup(self):
        with prepared_fixture() as db:
            apply_eight_country_scope(db,CFG,strict=False)
            original=db.execute("SELECT COUNT(*) FROM edition_club_competitions").fetchone()[0]
            res=stage_mls(db,MLS,strict=False)
            self.assertEqual(res["intended_selectable_original_game_clubs"],344)
            self.assertEqual(res["intended_playable_competition_codes"],17)
            self.assertEqual(res["mls_eastern_clubs"],15)
            self.assertEqual(res["mls_western_clubs"],15)
            self.assertEqual(db.execute("""
                SELECT movement_policy FROM fc27_effective_world_league_movement_scope
                WHERE competition_code='2027:us.mls'
            """).fetchone(),("closed",))
            self.assertEqual(db.execute("""
                SELECT regular_season_games_per_team,conference_playoff_qualifiers,
                       round_one_best_of,league_standings_and_playoffs_simulator_activated
                FROM fc27_mls_calendar_and_playoff_policy
            """).fetchone(),(34,9,3,0))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM edition_club_competitions").fetchone()[0],original)
            self.assertEqual(db.execute("""
              SELECT COUNT(*) FROM fc27_mls_official_conference_membership
              WHERE mapped_original_game_club_key IS NOT NULL
            """).fetchone()[0],0)
    def test_rejects_made_up_conference_members(self):
        config=json.loads(MLS.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            config["official_clubs"][0]["conference"]="Western"
            f=Path(tmp)/"tamper.json";f.write_text(json.dumps(config))
            with prepared_fixture() as db:
                apply_eight_country_scope(db,CFG,strict=False)
                with self.assertRaisesRegex(ValueError,"30 named official MLS"):
                    stage_mls(db,f,strict=False)
    def test_source_squad_readiness_remains_disabled(self):
        with prepared_fixture() as db:
            apply_eight_country_scope(db,CFG,strict=False)
            stage_mls(db,MLS,strict=False)
            self.assertEqual(db.execute("""
                SELECT SUM(PES_match_roster_verified),SUM(season_schedule_activated)
                FROM fc27_mls_playable_closed_league_approval
            """).fetchone(),(0,0))
            self.assertEqual(db.execute(
                "SELECT career_ready FROM edition_readiness WHERE edition=2027"
            ).fetchone()[0],0)
if __name__=="__main__":
    unittest.main()

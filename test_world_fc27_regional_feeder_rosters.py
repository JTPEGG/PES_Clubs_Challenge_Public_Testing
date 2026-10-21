"""FC27 2026/27 Spanish and German regional feeder real name / dry-run tests."""
import json
import tempfile
import unittest
from pathlib import Path
from collections import Counter
from test_world_fc27_eight_country_playable_scope import prepared_fixture,CFG
from world_fc27_eight_country_playable_scope import apply_eight_country_scope
from world_fc27_regional_feeder_rosters import stage,SPAIN,GERMANY
from world_fc27_regional_season_end import resolve_regional_movement

DATA=Path(__file__).parent/"data/warehouse/fc27_2026_27_es_de_regional_feeder_clubs.json"

def make(country):
    groups=SPAIN if country=="Spain" else GERMANY
    return {g:tuple(f"{country}:{g}:{i:02d}" for i in range(size))
            for g,size in groups.items()}
class FC27RegionalRealFeederTests(unittest.TestCase):
    def test_source_preserves_40_spanish_and_91_german_real_feeder_names(self):
        with prepared_fixture() as db:
            apply_eight_country_scope(db,CFG,strict=False)
            baseline=db.execute("SELECT COUNT(*) FROM edition_club_competitions").fetchone()[0]
            out=stage(db,DATA,strict=False)
            self.assertEqual(out["new_real_feeder_club_names"],131)
            self.assertEqual(out["regionalliga_bavaria_2026_27_real_team_count"],19)
            self.assertEqual(db.execute("""
              SELECT COUNT(*) FROM fc27_regional_feeder_2026_27_group
            """).fetchone()[0],7)
            self.assertEqual(db.execute("""
              SELECT COUNT(*) FROM fc27_regional_feeder_2026_27_club
              WHERE PES_player_squad_imported!=0 OR promotion_eligible_game_registration!=0
            """).fetchone()[0],0)
            self.assertEqual(db.execute("""
              SELECT country,SUM(expected_members)
              FROM fc27_regional_feeder_2026_27_group
              GROUP BY country ORDER BY country
            """).fetchall(),[("Germany",91),("Spain",40)])
            self.assertEqual(baseline,db.execute(
                "SELECT COUNT(*) FROM edition_club_competitions").fetchone()[0])
            self.assertEqual(db.execute("""
              SELECT COUNT(*) FROM edition_readiness WHERE edition=2027 AND career_ready=1
            """).fetchone()[0],0)
    def test_source_rejects_fictional_clubs_and_incomplete_groups(self):
        base=json.loads(DATA.read_text(encoding="utf-8"))
        for mutation in ("missing","invented_ratings"):
            config=json.loads(json.dumps(base))
            if mutation=="missing":config["groups"][0]["clubs"].pop()
            else:config["groups"][0]["clubs"][0]["game_ready_PES_player_roster"]=True
            with tempfile.TemporaryDirectory() as td:
                path=Path(td)/"tamper.json";path.write_text(json.dumps(config))
                with prepared_fixture() as db:
                    apply_eight_country_scope(db,CFG,strict=False)
                    with self.assertRaises(ValueError):stage(db,path,strict=False)
    def test_spanish_four_promotions_require_two_recorded_playoff_winners(self):
        groups=make("Spain");upper=tuple(f"Segunda:{i}" for i in range(22))
        allids=frozenset(v for g in groups.values() for v in g)|frozenset(upper)
        with self.assertRaisesRegex(ValueError,"Recorded two Spanish"):
            resolve_regional_movement(
               "Spain",region_ranked=groups,upper_ranked=upper,
               verified_eligible_game_club_ids=allids,
               certified_game_roster_club_ids=allids,recorded_playoff_winners=(),
               actual_final_tables_certified=True,expected_upper_team_count=22)
        result=resolve_regional_movement(
               "Spain",region_ranked=groups,upper_ranked=upper,
               verified_eligible_game_club_ids=allids,
               certified_game_roster_club_ids=allids,
               recorded_playoff_winners=(groups["1"][1],groups["2"][2]),
               actual_final_tables_certified=True,expected_upper_team_count=22)
        self.assertEqual(result.promoted,(groups["1"][0],groups["2"][0],
                                        groups["1"][1],groups["2"][2]))
        self.assertEqual(result.relegated,upper[-4:])
        self.assertEqual(len(result.upper_after),22)
        self.assertFalse(result.regional_destination_allocations_certified)
    def test_german_three_direct_plus_nord_bayern_playoff(self):
        groups=make("Germany");upper=tuple(f"D3:{i}" for i in range(20))
        allids=frozenset(v for g in groups.values() for v in g)|frozenset(upper)
        result=resolve_regional_movement(
            "Germany",region_ranked=groups,upper_ranked=upper,
            verified_eligible_game_club_ids=allids,
            certified_game_roster_club_ids=allids,
            recorded_playoff_winners=(groups["Bayern"][0],),
            actual_final_tables_certified=True,expected_upper_team_count=20)
        self.assertEqual(result.promoted,
            (groups["West"][0],groups["Südwest"][0],
             groups["Nordost"][0],groups["Bayern"][0]))
        self.assertEqual(len(result.upper_after),20)
        with self.assertRaisesRegex(ValueError,"North/Bavaria"):
            resolve_regional_movement(
                "Germany",region_ranked=groups,upper_ranked=upper,
                verified_eligible_game_club_ids=allids,
                certified_game_roster_club_ids=allids,
                recorded_playoff_winners=(groups["West"][1],),
                actual_final_tables_certified=True)
    def test_no_certified_game_squads_no_promotion_and_skip_reserves(self):
        groups=make("Spain");upper=tuple(f"LL2:{i}" for i in range(22))
        eligible=set(v for g in groups.values() for v in g)|set(upper)
        eligible.remove(groups["1"][0])  # in-game reserve club
        # first eligible senior club becomes eligible 'champion' game candidate,
        # so original group's third+ becomes playoff contenders.
        with self.assertRaisesRegex(ValueError,"standings"):
            resolve_regional_movement(
                "Spain",region_ranked=groups,upper_ranked=upper,
                verified_eligible_game_club_ids=frozenset(eligible),
                certified_game_roster_club_ids=frozenset(eligible),
                recorded_playoff_winners=(groups["1"][2],groups["2"][2]))
        outcome=resolve_regional_movement(
                "Spain",region_ranked=groups,upper_ranked=upper,
                verified_eligible_game_club_ids=frozenset(eligible),
                certified_game_roster_club_ids=frozenset(eligible),
                recorded_playoff_winners=(groups["1"][2],groups["2"][2]),
                actual_final_tables_certified=True)
        self.assertEqual(outcome.promoted[0],groups["1"][1])
        self.assertNotIn(groups["1"][0],outcome.promoted)

if __name__=="__main__": unittest.main()

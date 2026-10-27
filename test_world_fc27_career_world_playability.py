"""FC27 one-hop feeder official source snapshot: no phantom player squads."""
import json
import unittest
from collections import Counter
from pathlib import Path
from world_fc27_career_world_playability import (
  EXPECTED, EXPECTED_RESERVES, OFFICIAL_SOURCES, namekey
)

CONFIG=Path(__file__).parent/"data/warehouse/fc27_2026_27_verified_feeder_club_rosters.json"

class FeederSourceQualityTests(unittest.TestCase):
    def test_three_official_league_sources_and_ninety_three_genuine_club_names(self):
        source=json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(source["edition"],2027)
        self.assertEqual(source["version"],"fc27-one-hop-official-2026-27-feeder-memberships-v1")
        groups={g["feeder_competition_code"]:g for g in source["groups"]}
        self.assertEqual(set(groups),set(EXPECTED))
        self.assertEqual(sum(len(g["clubs"]) for g in groups.values()),93)
        for code,group in groups.items():
            with self.subTest(league=code):
                clubs=group["clubs"]
                self.assertEqual(group["source_official_url"],OFFICIAL_SOURCES[code])
                self.assertEqual(len(clubs),EXPECTED[code])
                self.assertEqual(group["roster_count"],EXPECTED[code])
                self.assertEqual(len({namekey(r["club_name"]) for r in clubs}),len(clubs))
                self.assertEqual(sum(r["reserve_or_youth"] for r in clubs),EXPECTED_RESERVES[code])
                self.assertFalse(group["original_game_player_squad_imported"])
        self.assertEqual(Counter(r["regional_group"] for r in groups["2027:it.3"]["clubs"]),
                         {"A":20,"B":20,"C":20})
    def test_no_claim_of_player_import_or_immediate_promotion(self):
        source=json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertIn("without inventing PES players",source["game_policy"])
        self.assertEqual(source["season"],"2026-27")
        for g in source["groups"]:
            self.assertTrue(g["source_official_url"].startswith("https://"))
            for item in g["clubs"]:
                self.assertEqual(type(item["reserve_or_youth"]),bool)
                self.assertTrue(item["club_name"])

if __name__=="__main__":
    unittest.main()

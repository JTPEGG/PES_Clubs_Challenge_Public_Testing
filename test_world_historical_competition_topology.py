"""Historical domestic divisions vs continental pools and season rules."""
import unittest
from world_historical_competition_topology import (
  SEASONS,topology,classify_league,assert_full_career_ready,RELEGATIONS
)

class CompetitionRuleTests(unittest.TestCase):
    def test_22_source_years_and_no_fictitious_fc25(self):
        self.assertEqual(len(SEASONS),22)
        self.assertNotIn(2025,SEASONS)
        self.assertIn(2005,SEASONS)

    def test_identical_league_names_are_not_merged_across_countries(self):
        self.assertEqual(classify_league(2026,"Premier League","13.0"),
                         ("ENG:PL","curated_source_competition_match"))
        self.assertEqual(classify_league(2026,"Premier League","332.0"),
                         (None,"requires_verified_competition_identity"))
        self.assertEqual(classify_league(2026,"Bundesliga","19.0")[0],"GER:BL1")
        self.assertNotEqual(classify_league(2026,"Bundesliga","80.0")[0],"GER:BL1")

    def test_conmebol_cups_cannot_become_domestic_leagues(self):
        self.assertEqual(classify_league(2027,"CONMEBOL Libertadores",None),
             ("CONMEBOL_LIBERTADORES","continental_cup_not_domestic_league"))
        self.assertEqual(classify_league(2027,"CONMEBOL Sudamericana",None)[1],
                         "continental_cup_not_domestic_league")

    def test_2027_championship_playoff_has_six_contenders(self):
        a=next(e for e in topology(2026)["promotion_edges"]
               if e["from"]=="ENG:CH")
        b=next(e for e in topology(2027)["promotion_edges"]
               if e["from"]=="ENG:CH")
        self.assertEqual(a["playoff_format"],"rank_3_to_6")
        self.assertEqual(b["playoff_format"],"rank_3_to_8")
        self.assertEqual(a["auto_promotions"],2)
        self.assertEqual(b["playoff_promotions"],1)
        self.assertEqual(b["automatic_relegations"],3)

    def test_england_germany_spain_graph_has_both_directions(self):
        for yr in (2026,2027):
            graph=topology(yr)
            node={x["id"]:x for x in graph["nodes"]}
            self.assertEqual(node["ENG:L2"]["tier"],4)
            self.assertEqual(node["GER:D3"]["tier"],3)
            self.assertEqual(node["ESP:LL2"]["tier"],2)
            for edge in graph["promotion_edges"]:
                self.assertIn(edge["from"],node)
                self.assertIn(edge["to"],node)
                self.assertLess(node[edge["to"]]["tier"],
                                node[edge["from"]]["tier"])
                self.assertEqual(edge["automatic_relegations"],
                    RELEGATIONS[(edge["to"],edge["from"])])
            self.assertEqual(
                next(e for e in graph["promotion_edges"]
                     if e["from"]=="GER:BL2")["playoff_format"],
                "third_vs_upper_16th")

    def test_nonplayable_feeder_requires_verified_club_pool(self):
        for yr in (2026,2027):
            g=topology(yr)
            self.assertFalse(g["full_world_activated"])
            for id in ("ENG:NL","GER:REG","ESP:RFEF"):
                row=next(x for x in g["nodes"] if x["id"]==id)
                self.assertEqual(row["player_club_pool_status"],
                                 "external_club_pool_required")

    def test_no_historical_career_can_claim_full_readiness_from_source_labels(self):
        audit={"full_career_editions_ready":[]}
        for yr in (2026,2027,2020):
            with self.assertRaisesRegex(ValueError,"incomplete"):
                assert_full_career_ready(audit,yr)


if __name__=="__main__":unittest.main()

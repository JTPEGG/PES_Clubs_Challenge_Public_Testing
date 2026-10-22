"""Regression for 659-club context-driven priorities (no real manager claims)."""
import sqlite3
import unittest
from world_fc27_ai_recruitment import (
    buyer_recruitment_priority,domestic_market_preference,
    modelled_seller_finances,modelled_financial_objective,read_fc27_profiles,
)

class ClubAIContextTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.squad={1:{
            "CB":[(1,88,"CB"),(2,85,"CB"),(3,79,"CB")],
            "RB":[(4,81,"RB")],
            "LB":[(5,83,"LB")],
            "CM":[(6,88,"CM"),(7,85,"CM"),(8,80,"CM")],
            "ST":[(9,86,"ST"),(10,79,"ST")],
            "GK":[(11,86,"GK"),(12,75,"GK")]}}
        self.profile={
            "ambition_level":83,"pressure_to_improve":86,
            "simulated_manager_risk":71,
            "simulated_manager_financial_discipline":66,
            "financial_pressure_index":20,
            "financial_pressure_band":"normal",
            "operating_approach":"high_ambition"}

    def tearDown(self):self.db.close()

    def test_old_careers_without_reference_table_are_unmodified(self):
        self.assertEqual(read_fc27_profiles(self.db,dataset="old"),{})
        self.assertEqual(modelled_seller_finances(None),"stable")
        self.assertEqual(modelled_financial_objective(None),"balanced")

    def test_copied_model_read_is_dataset_scoped(self):
        self.db.executescript("""CREATE TABLE world_fc27_club_ai_context(
            dataset_id TEXT,club_id INTEGER,sporting_appeal INTEGER,
            ambition_level INTEGER,pressure_to_improve INTEGER,
            operating_approach TEXT,financial_pressure_band TEXT,
            financial_pressure_index INTEGER,simulated_manager_risk INTEGER,
            simulated_manager_financial_discipline INTEGER,source_note TEXT);""")
        self.db.execute("INSERT INTO world_fc27_club_ai_context VALUES(?,?,?,?,?,?,?,?,?,?,?)",
          ("fc27",1,81,83,86,"high_ambition","normal",20,71,66,
           "fictional-game-model"))
        self.assertEqual(read_fc27_profiles(self.db,dataset="old"),{})
        self.assertEqual(read_fc27_profiles(self.db,dataset="fc27")[1]["ambition_level"],83)

    def test_ambitious_club_is_more_active_without_guaranteed_signings(self):
        baseline=buyer_recruitment_priority(self.squad,club=1,stable_variation=8)
        keen=buyer_recruitment_priority(self.squad,club=1,profile=self.profile,
                                        stable_variation=8)
        self.assertGreater(keen,baseline)
        self.assertGreater(keen,buyer_recruitment_priority(self.squad,club=1,
            profile=self.profile,previous_signings=2,stable_variation=8))

    def test_agreed_sale_generates_recruitment_priority_not_sale_veto(self):
        changed={1:{**self.squad[1],"RB":[]}}
        after=buyer_recruitment_priority(changed,club=1,
            departed_lanes={"RB"},stable_variation=8)
        before=buyer_recruitment_priority(self.squad,club=1,
            stable_variation=8)
        self.assertGreater(after,before)

    def test_financial_stress_decreases_spending_without_banning(self):
        distressed={**self.profile,"financial_pressure_band":"distress",
            "financial_pressure_index":93}
        self.assertEqual(modelled_seller_finances(distressed),"distressed")
        self.assertEqual(modelled_financial_objective(distressed),"cash_generation")
        self.assertEqual(modelled_seller_finances({**self.profile,
             "financial_pressure_band":"over_committed"}),"cash_needed")
        self.assertEqual(modelled_financial_objective({**self.profile,
             "financial_pressure_band":"tight"}),"cost_control")
        a=buyer_recruitment_priority(self.squad,club=1,profile=self.profile)
        b=buyer_recruitment_priority(self.squad,club=1,profile=distressed)
        self.assertLess(b,a)
        self.assertGreater(b,-100)

    def test_international_moves_remain_possible_under_soft_home_preference(self):
        self.assertGreater(domestic_market_preference(
            same_source_country=True,profile=self.profile),
            domestic_market_preference(same_source_country=False,profile=self.profile))
        self.assertIsInstance(domestic_market_preference(
            same_source_country=False,profile=self.profile),float)
        with self.assertRaises(ValueError):
            buyer_recruitment_priority(self.squad,club=1,stable_variation=28)

if __name__=="__main__":unittest.main()

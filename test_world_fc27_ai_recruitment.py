"""Regression for 659-club context-driven priorities (no real manager claims)."""
import sqlite3
import unittest
from world_fc27_ai_recruitment import (
    buyer_recruitment_priority,domestic_market_preference,
    modelled_seller_finances,modelled_financial_objective,read_fc27_profiles,
    positional_family_priorities,prospect_budget_penalty,
    candidate_sporting_priority,
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
        self.db.execute("INSERT INTO world_fc27_club_ai_context VALUES(?,?,?,?,?,?,?,?,?,?,?)",
          ("fc27",2,72,64,45,"balanced","tight",55,48,76,
           "fictional-game-model"))
        self.assertEqual(set(read_fc27_profiles(
            self.db,dataset="fc27",club_id=1)),{1})
        self.assertEqual(read_fc27_profiles(
            self.db,dataset="fc27",club_id=99),{})


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

    def test_specialist_need_not_global_goalkeeper_or_striker_market_quota(self):
        base=positional_family_priorities(self.squad,club=1)
        less_gk={1:{**self.squad[1],"GK":[(11,86,"GK")]}}
        thin=positional_family_priorities(less_gk,club=1)
        self.assertGreater(thin["GK"],base["GK"])
        # A forward recruitment need is unrelated to other clubs' deals.
        sold_starter={1:{**self.squad[1],"ST":[]}}
        urgent=positional_family_priorities(sold_starter,club=1,
                                            departed_lanes={"ST"})
        self.assertGreater(urgent["FWD"],base["FWD"])
        self.assertEqual(set(base),{"GK","DEF","MID","FWD"})

    def test_ambitious_strong_squad_continues_scouting(self):
        # A settled first XI can still be ambitious enough to consider
        # upgrading; an identifiable shortage remains urgent for any club.
        very_strong={1:{lane:[(pid,rating+10,position)
                for pid,rating,position in group]
                for lane,group in self.squad[1].items()}}
        same=buyer_recruitment_priority(self.squad,club=1,
            profile=self.profile,stable_variation=12)
        stronger=buyer_recruitment_priority(very_strong,club=1,
            profile=self.profile,stable_variation=12)
        self.assertGreater(stronger,same)

    def test_goalkeeper_market_priority_reflects_current_need(self):
        credible={"eligible":True,"score":70,"category":"first_team"}
        routine=candidate_sporting_priority(self.squad,club=1,
            position="GK",overall=90,fit=credible)
        strong_upgrade=candidate_sporting_priority(self.squad,club=1,
            position="GK",overall=95,fit=credible)
        depleted={1:{**self.squad[1],"GK":[(11,86,"GK")]}}
        urgency=candidate_sporting_priority(depleted,club=1,
            position="GK",overall=90,fit=credible,
            departed_lanes={"GK"})
        self.assertGreater(strong_upgrade,routine)
        self.assertGreater(urgency,routine)
        # An equivalent outfield starter improvement should generally
        # rank ahead of a discretionary second keeper improvement.
        midfield=candidate_sporting_priority(self.squad,club=1,
            position="CM",overall=90,fit=credible)
        self.assertGreater(midfield,routine)
        prospect={**credible,"category":"prospect"}
        self.assertLess(candidate_sporting_priority(self.squad,club=1,
            position="GK",overall=90,fit=prospect),routine)

    def test_soft_development_opportunity_cost_is_not_a_veto(self):
        low=prospect_budget_penalty(fee=2_000_000,
            available_budget=45_000_000,opening_budget=50_000_000)
        high=prospect_budget_penalty(fee=18_000_000,
            available_budget=45_000_000,opening_budget=50_000_000)
        self.assertGreater(high,low)
        self.assertIsInstance(high,float)
        self.assertLess(high,30)
        with self.assertRaises(ValueError):
            prospect_budget_penalty(fee=-1,
                available_budget=45_000_000,opening_budget=50_000_000)

    def test_international_moves_remain_possible_under_soft_home_preference(self):
        self.assertGreater(domestic_market_preference(
            same_source_country=True,profile=self.profile),
            domestic_market_preference(same_source_country=False,profile=self.profile)+15)
        self.assertIsInstance(domestic_market_preference(
            same_source_country=False,profile=self.profile),float)
        with self.assertRaises(ValueError):
            buyer_recruitment_priority(self.squad,club=1,stable_variation=28)

if __name__=="__main__":unittest.main()

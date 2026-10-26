"""FC27 strategy must complement, never replace, ordinary prospect recruitment.

The tests deliberately include two clubs taking opposite decisions from
similar ages, a selling club that can cash in WITHOUT buying a replacement,
and a valid youth acquisition which stays a 'prospect' instead of being
reclassified as a first-team signing.
"""
import sqlite3
import unittest

from world_fc27_long_term_strategy import (
    DATASET,source_ages,three_season_outlook,club_horizon,
    recruitment_horizon_score,seller_horizon_review)
from world_fc27_market_choices import choose_development_focus

PROFILE={"ambition_level":85,"pressure_to_improve":80,
         "financial_pressure_index":30,"simulated_manager_risk":53}
SALE={"valid":True,"first_choice":True,
      "formation_quality_loss":10,"starter_rating_drop":0}


class FC27ThreeSeasonStrategyTests(unittest.TestCase):
    def test_age_comes_from_source_snapshot_not_runtime_clock(self):
        con=sqlite3.connect(":memory:")
        try:
            con.execute("CREATE TABLE world_datasets(dataset_id TEXT,source_date TEXT)")
            con.execute("CREATE TABLE world_players(player_id INTEGER,birth_date TEXT)")
            con.execute("INSERT INTO world_datasets VALUES(?,?)",
                        (DATASET,"2026-08-01"))
            con.executemany("INSERT INTO world_players VALUES(?,?)",
                [(1,"1987-12-19"),(2,"1991-06-20"),(3,"2007-09-01")])
            ages=source_ages(con,dataset=DATASET,player_ids=[1,2,3,3])
            self.assertEqual(ages,{1:38,2:35,3:18})
            with self.assertRaises(ValueError):
                source_ages(con,dataset="legacy",player_ids=[1])
        finally:
            con.close()

    def test_three_season_decline_is_a_scenario_not_deterministic_pa(self):
        old=three_season_outlook(age=38,overall=82,position="CF")
        young=three_season_outlook(age=19,overall=70,position="CMF")
        self.assertEqual(len(old["scenarios"]),3)
        self.assertGreater(old["scenarios"][2]["decline_exposure"],0)
        self.assertEqual(young["scenarios"][2]["decline_exposure"],0)
        self.assertLess(young["scenarios"][2]["rating_scenario_low"],70)
        self.assertGreaterEqual(young["scenarios"][2]["rating_scenario_high"],70)
        self.assertEqual(old["projection_kind"],
                         "uncertain_age_exposure_not_sourced_potential")

    def test_older_starters_create_succession_without_forcing_deals(self):
        squad={"CF":[(1,82,"CF"),(2,73,"CF")],
               "CB":[(3,83,"CB"),(4,75,"CB")],
               "GK":[(5,79,"GK"),(6,67,"GK")]}
        ages={1:38,2:19,3:35,4:25,5:28,6:21}
        plan=club_horizon(profile=PROFILE,roster=squad,ages=ages,
                          starting_roles={"ST":1,"CB":1,"GK":1})
        self.assertEqual(plan["replacement_signings_assumed"],0)
        self.assertTrue(plan["forecast_is_not_guaranteed"])
        self.assertGreater(plan["succession_pressure"]["CB"],0)
        self.assertEqual(plan["family_succession_pressure"]["GK"],0)

    def test_prospect_recruitment_keeps_its_separate_validity_and_purpose(self):
        plan={"succession_pressure":{"CB":24},
              "youth_pipeline_priority":65,
              "current_competitive_pressure":75}
        prospect=recruitment_horizon_score(
            category="prospect",lane="CB",player_age=19,
            player_overall=72,plan=plan,existing_youth_in_lane=1)
        senior=recruitment_horizon_score(
            category="senior",lane="CB",player_age=32,
            player_overall=86,plan=plan,existing_youth_in_lane=1,
            immediate_starter_upgrade=True)
        self.assertEqual(prospect["kind"],"prospect_succession_option")
        self.assertFalse(prospect["promised_immediate_xi_improvement"])
        self.assertTrue(senior["promised_immediate_xi_improvement"])
        self.assertFalse(prospect["future_ability_verified"])
        # Even an old ageing specialist with succession needs leaves the
        # prospect search a nonzero chance, not a forced transaction.
        threshold=choose_development_focus(
            profile=PROFILE,draw=0,
            senior_upgrade_pressure=30,succession_pressure=70)
        no_promise=choose_development_focus(
            profile=PROFILE,draw=999,
            senior_upgrade_pressure=30,succession_pressure=70)
        self.assertTrue(threshold)
        self.assertFalse(no_promise)

    def test_succession_improves_prospect_case_without_age_only_ban(self):
        p0={"succession_pressure":{},
            "youth_pipeline_priority":35,
            "current_competitive_pressure":85}
        p1={"succession_pressure":{"CB":32},
            "youth_pipeline_priority":75,
            "current_competitive_pressure":85}
        def score(plan,category="prospect",age=19):
            return recruitment_horizon_score(
                category=category,lane="CB",player_age=age,
                player_overall=76,plan=plan)["score"]
        self.assertGreater(score(p1),score(p0))
        self.assertGreater(score(p1,"senior",34),-100)

    def test_cashing_in_on_older_player_is_still_allowed(self):
        older=seller_horizon_review(
            age=38,overall=82,position="CF",market_value=7_000_000,
            offered_fee=10_750_000,weekly_wage=44100,
            contract_years=2,squad_sale=SALE,profile=PROFILE)
        young=seller_horizon_review(
            age=25,overall=82,position="CF",market_value=7_000_000,
            offered_fee=10_750_000,weekly_wage=44100,
            contract_years=2,squad_sale=SALE,profile=PROFILE)
        self.assertLess(older["asking_price_shift_pct"],
                        young["asking_price_shift_pct"])
        self.assertFalse(older["future_replacement_assumed"])
        self.assertTrue(older["future_ability_is_scenario_only"])
        self.assertEqual(older["contract_wage_exposure_gbp"],44100*52*2)

    def test_immediate_title_objective_and_financial_pressure_disagree(self):
        a=seller_horizon_review(
            age=35,overall=82,position="CB",market_value=6_400_000,
            offered_fee=8_050_000,weekly_wage=51150,
            contract_years=1,squad_sale=SALE,
            profile={**PROFILE,"ambition_level":95,
                     "financial_pressure_index":12})
        b=seller_horizon_review(
            age=35,overall=82,position="CB",market_value=6_400_000,
            offered_fee=8_050_000,weekly_wage=51150,
            contract_years=1,squad_sale=SALE,
            profile={**PROFILE,"ambition_level":55,
                     "financial_pressure_index":80})
        self.assertGreater(a["asking_price_shift_pct"],
                           b["asking_price_shift_pct"])


if __name__=="__main__":
    unittest.main()

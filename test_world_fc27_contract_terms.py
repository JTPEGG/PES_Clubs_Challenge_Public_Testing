"""FC27-only source-game wage policy and sporting recruitment rationale."""
import unittest
from world_fc27_contract_terms import (
    fc27_agent_wage_floor,fc27_sporting_recruitment_case)


class Fc27ContractsAndSportingCases(unittest.TestCase):
    def test_senior_wage_remains_close_to_current_fc27_game_salary(self):
        # Regression: 83 OVR on £237,600 must NOT sign for £11,500/w.
        demand=fc27_agent_wage_floor(
            source_weekly_wage=237600,buyer_appeal=90,
            seller_appeal=91,offered_role="regular_starter",
            seller_first_choice=True)
        self.assertGreaterEqual(demand,237600)
        self.assertLess(demand,375000)
        self.assertEqual(demand%500,0)

    def test_sporting_downgrade_and_role_influence_salary(self):
        context={"source_weekly_wage":150000,
                 "seller_appeal":91,"seller_first_choice":True}
        drop=fc27_agent_wage_floor(
            **context,buyer_appeal=70,offered_role="rotation")
        step_up=fc27_agent_wage_floor(
            **context,buyer_appeal=95,offered_role="regular_starter")
        self.assertGreater(drop,step_up)
        self.assertGreater(drop,150000)

    def test_transfer_listed_reserve_may_consider_small_wage_concession(self):
        context={"source_weekly_wage":35000,"buyer_appeal":80,
                 "seller_appeal":90,"offered_role":"regular_starter"}
        bench=fc27_agent_wage_floor(
            **context,seller_first_choice=False,transfer_listed=True)
        starter=fc27_agent_wage_floor(
            **context,seller_first_choice=True,transfer_listed=False)
        self.assertLess(bench,starter)
        self.assertGreaterEqual(bench,35000*.9)

    def test_unknown_salary_cannot_be_inferred(self):
        with self.assertRaises(ValueError):
            fc27_agent_wage_floor(
                source_weekly_wage=None,buyer_appeal=80,
                seller_appeal=75,offered_role="rotation")
        with self.assertRaises(ValueError):
            fc27_agent_wage_floor(
                source_weekly_wage=-1,buyer_appeal=80,
                seller_appeal=75,offered_role="rotation")

    def test_stronger_starting_xi_target_beats_discretionary_elite_depth(self):
        inputs={"category":"senior","role_required":False,
                "team_standard":87,"overall":81,
                "ambition":92,"has_recent_departure":False}
        backup=fc27_sporting_recruitment_case(
            **inputs,starter_gain=-5)
        upgrade=fc27_sporting_recruitment_case(
            **{**inputs,"overall":89},starter_gain=5)
        self.assertEqual(backup["kind"],"discretionary_depth")
        self.assertFalse(backup["first_team_upgraded"])
        self.assertTrue(upgrade["first_team_upgraded"])
        self.assertGreater(upgrade["score"],backup["score"])

    def test_genuine_needed_rotation_stays_eligible(self):
        inputs={"category":"senior","starter_gain":0,
                "team_standard":87,"overall":79,"ambition":91,
                "has_recent_departure":False}
        rotation=fc27_sporting_recruitment_case(
            **inputs,role_required=True)
        discretionary=fc27_sporting_recruitment_case(
            **inputs,role_required=False)
        self.assertEqual(rotation["kind"],"needed_rotation_or_replacement")
        self.assertGreater(rotation["score"],discretionary["score"])
        self.assertFalse(rotation["first_team_upgraded"])

    def test_youth_is_development_not_fabricated_first_team_improvement(self):
        youth=fc27_sporting_recruitment_case(
            category="prospect",starter_gain=0,role_required=False,
            team_standard=88,overall=70,ambition=90)
        self.assertEqual(youth["kind"],"development")
        self.assertFalse(youth["first_team_upgraded"])


if __name__=="__main__":
    unittest.main()

"""Regression tests: prospect investment must not masquerade as an XI upgrade."""
import unittest
from world_recruitment_strategy import (
    age_on, prospect_fit, prospect_fee_cap, MAX_PROSPECTS_PER_WINDOW,
)
from world_squad_planner import recruitment_fit, lane_of

class LongTermRecruitmentTests(unittest.TestCase):
    def setUp(self):
        # Synthetic 86-rated starting XI with genuine ST depth.
        # A 78-rated 19-year-old is not a current first-team upgrade.
        self.squads={1:{
            "ST":[(10,90,"ST"),(11,87,"ST")],
            "CB":[(12,90,"CB"),(13,88,"CB"),(14,85,"CB")],
            "GK":[(15,89,"GK")],
            "CM":[(16,88,"CM"),(17,86,"CM")],
            "FB":[(18,86,"RB"),(19,84,"LB")],
            "W":[(20,87,"LW"),(21,85,"RW")],
        }}
        self.signals={
            "players":{99:(19,"ST",78),98:(22,"ST",69)},
            "cohorts":{"ST":[(19,v) for v in [58,62,65,68,69,72,74,76,78,79]]},
            "calibrated_potential":{},
            "source_date":"2004-08-01",
        }

    def test_historical_age_is_measured_at_save_start(self):
        self.assertEqual(age_on("1986-08-02","2004-08-01"),17)
        self.assertEqual(age_on("1986-08-01","2004-08-01"),18)
        self.assertIsNone(age_on(None,"2004-08-01"))
        self.assertEqual(lane_of("CAM"),"AM")
        self.assertEqual(lane_of("CDM"),"DM")

    def test_elite_club_can_invest_without_false_starter_claim(self):
        self.assertFalse(recruitment_fit(self.squads,buyer=1,
                                         position="ST",overall=78)["eligible"])
        candidate=prospect_fit(self.squads,buyer=1,player_id=99,
            overall=78,position="ST",signals=self.signals)
        self.assertTrue(candidate["eligible"])
        self.assertEqual(candidate["category"],"prospect")
        self.assertIn("future ability unknown",candidate["evidence"])
        self.assertLess(candidate["score"],85)

    def test_ordinary_youth_does_not_trigger_future_purchase(self):
        weak=prospect_fit(self.squads,buyer=1,player_id=98,
            overall=69,position="ST",signals=self.signals)
        self.assertFalse(weak["eligible"])

    def test_respect_prospect_quota_and_scoped_budget(self):
        self.assertFalse(prospect_fit(self.squads,buyer=1,player_id=99,
            overall=78,position="ST",signals=self.signals,
            existing_prospects=MAX_PROSPECTS_PER_WINDOW)["eligible"])
        self.assertEqual(prospect_fee_cap(initial_transfer_budget=45000000,
            available_budget=38000000),9000000)
        self.assertEqual(prospect_fee_cap(initial_transfer_budget=45000000,
            available_budget=2000000),2000000)

    def test_incomplete_cohort_does_not_invent_potential(self):
        self.signals["cohorts"]={"ST":[(19,v) for v in [76,78,79]]}
        self.assertFalse(prospect_fit(self.squads,buyer=1,player_id=99,
            overall=78,position="ST",signals=self.signals)["eligible"])

    def test_age_17_not_judged_by_22_year_old_peer_ratings(self):
        self.signals["players"][99]=(17,"ST",78)
        self.signals["cohorts"]={"ST":[(17,v) for v in
            (61,64,65,67,69,71,72,78,78)]+
            [(22,v) for v in (81,83,84,85,86,87,89,90,92)]}
        prospect=prospect_fit(self.squads,buyer=1,player_id=99,
            overall=78,position="ST",signals=self.signals)
        self.assertTrue(prospect["eligible"])

    def test_authorised_calibrated_potential_can_support_investment(self):
        self.signals["cohorts"]={"ST":[(19,v) for v in [76,78]]}
        self.signals["calibrated_potential"]={99:90}
        candidate=prospect_fit(self.squads,buyer=1,player_id=99,
            overall=78,position="ST",signals=self.signals)
        self.assertTrue(candidate["eligible"])
        self.assertIn("source-calibrated",candidate["evidence"])

    def test_fc27_contextual_youth_recruitment_has_no_transaction_quota(self):
        # Both the prospect count and existing young teammates can weaken
        # priority without making a genuinely credible target ineligible.
        self.signals["players"][10]=(20,"ST",90)
        self.signals["players"][11]=(21,"ST",87)
        candidate=prospect_fit(self.squads,buyer=1,player_id=99,
            overall=78,position="ST",signals=self.signals,
            existing_prospects=4,contextual_policy=True)
        self.assertTrue(candidate["eligible"])
        self.assertGreater(candidate["score"],0)
        # Old saved worlds continue to use their original deterministic policy.
        old=prospect_fit(self.squads,buyer=1,player_id=99,
            overall=78,position="ST",signals=self.signals,
            existing_prospects=4)
        self.assertFalse(old["eligible"])

    def test_no_youth_overstocking_same_position(self):
        self.signals["players"][10]=(20,"ST",90)
        self.signals["players"][11]=(21,"ST",87)
        self.assertFalse(prospect_fit(self.squads,buyer=1,player_id=99,
            overall=78,position="ST",signals=self.signals)["eligible"])

if __name__=="__main__":
    unittest.main()

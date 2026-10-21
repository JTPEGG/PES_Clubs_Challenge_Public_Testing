"""Pure QA of game-only elite transfer balance before integration."""
import unittest
from world_ai_elite_balance import assess_elite_net_departure, POLICY
def roster(overall=87):
    return {"GK":[(1,overall,"GK")],"CB":[(2,overall,"CB")],
        "CM":[(3,overall,"CM"),(4,overall,"CM")],
        "ST":[(5,overall,"ST")],"LW":[(6,overall,"LW")],
        "RB":[(7,overall,"RB")],"LB":[(8,overall,"LB")],
        "RW":[(9,overall,"RW")],"DM":[(10,overall,"DM")],
        "AM":[(11,overall,"AM")]}
class EliteBalancePolicyTests(unittest.TestCase):
    def check(self,**kwargs):
        return assess_elite_net_departure(projected_seller_roster=roster(),
              agreed_incoming=0,agreed_outgoing=0,**kwargs)
    def test_pure_sporting_strength_not_brand_name(self):
        x=self.check()
        self.assertTrue(x["allowed"])
        self.assertEqual(x["policy_version"],POLICY)
        lesser=assess_elite_net_departure(projected_seller_roster=roster(76),
             agreed_incoming=0,agreed_outgoing=4)
        self.assertTrue(lesser["allowed"])
        self.assertEqual(lesser["basis"],"not_elite_squad")
    def test_second_net_routine_sale_is_blocked(self):
        x=assess_elite_net_departure(projected_seller_roster=roster(),
            agreed_incoming=0,agreed_outgoing=1)
        self.assertFalse(x["allowed"])
        self.assertEqual(x["allowable_net_departures"],1)
    def test_signed_arrival_restores_sale_capacity(self):
        x=assess_elite_net_departure(projected_seller_roster=roster(),
            agreed_incoming=2,agreed_outgoing=2)
        self.assertTrue(x["allowed"])
        self.assertEqual(x["basis"],"within_normal_net_balance")
    def test_player_exit_exception_is_limited_not_a_free_for_all(self):
        x=assess_elite_net_departure(projected_seller_roster=roster(),
            agreed_incoming=0,agreed_outgoing=1,explicitly_wants_exit=True)
        self.assertTrue(x["allowed"])
        y=assess_elite_net_departure(projected_seller_roster=roster(),
            agreed_incoming=0,agreed_outgoing=2,explicitly_wants_exit=True)
        self.assertFalse(y["allowed"])
    def test_documented_financial_stress_can_trigger_second_exit(self):
        x=assess_elite_net_departure(projected_seller_roster=roster(),
            agreed_incoming=0,agreed_outgoing=1,financial_state="distressed")
        self.assertTrue(x["allowed"])
        self.assertEqual(x["basis"],"documented_pressure_exception")
    def test_transfer_listing_alone_does_not_force_extra_sale(self):
        x=assess_elite_net_departure(projected_seller_roster=roster(),
            agreed_incoming=0,agreed_outgoing=1,explicitly_transfer_listed=True)
        self.assertFalse(x["allowed"])
    def test_unknown_source_finance_does_not_buy_override(self):
        x=assess_elite_net_departure(projected_seller_roster=roster(),
            agreed_incoming=0,agreed_outgoing=1,financial_state="unknown")
        self.assertFalse(x["allowed"])
    def test_reject_invalid_counts_and_unverified_financial_status(self):
        with self.assertRaises(ValueError):
            assess_elite_net_departure(projected_seller_roster=roster(),
              agreed_incoming=-1,agreed_outgoing=1)
        with self.assertRaises(ValueError):
            assess_elite_net_departure(projected_seller_roster=roster(),
              agreed_incoming=1,agreed_outgoing=1,financial_state="pretend_owner_cash")
if __name__=="__main__":unittest.main()

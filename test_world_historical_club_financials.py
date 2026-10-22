"""Financial club-budget model regressions: estimates never become source facts."""
import unittest
from world_historical_club_financials import (
    capacity_band,estimate_finances,round_budget
)


class ClubBudgetTests(unittest.TestCase):
    def test_existing_payroll_is_always_reserved(self):
        for payroll in (0,1000,50000,500000,4500000):
            budget,headroom,cash=estimate_finances(
                starting_payroll=payroll,projected_payroll=max(20000,payroll),
                capacity_score=.8,max_player_wage=min(payroll,500000),
                roster_count=23)
            self.assertGreaterEqual(budget,payroll)
            self.assertEqual(headroom,budget-payroll)
            self.assertGreaterEqual(cash,2500)

    def test_relative_club_strength_scales_annual_transfer_funds(self):
        low=estimate_finances(starting_payroll=50000,projected_payroll=50000,
                capacity_score=.05,max_player_wage=10000,roster_count=25)
        high=estimate_finances(starting_payroll=3000000,projected_payroll=3000000,
                capacity_score=.98,max_player_wage=450000,roster_count=25)
        self.assertGreater(high[2],100*low[2])

    def test_wage_concentration_decreases_transfer_cash_not_squad_pay(self):
        plain=estimate_finances(starting_payroll=200000,projected_payroll=200000,
                capacity_score=.6,max_player_wage=20000,roster_count=25)
        extreme=estimate_finances(starting_payroll=200000,projected_payroll=200000,
                capacity_score=.6,max_player_wage=150000,roster_count=25)
        self.assertEqual(plain[:2],extreme[:2])
        self.assertGreater(plain[2],extreme[2])

    def test_estimates_are_deterministic_and_guarded(self):
        inputs=dict(starting_payroll=100000,projected_payroll=200000,
                    capacity_score=.55,max_player_wage=10000,roster_count=10)
        self.assertEqual(estimate_finances(**inputs),estimate_finances(**inputs))
        with self.assertRaises(ValueError):
            estimate_finances(**{**inputs,"projected_payroll":100})
        with self.assertRaises(ValueError):
            estimate_finances(**{**inputs,"capacity_score":2})
        self.assertEqual(round_budget(500),2500)
        self.assertEqual(capacity_band(.99),"elite_financial_proxy")


if __name__=="__main__":unittest.main()

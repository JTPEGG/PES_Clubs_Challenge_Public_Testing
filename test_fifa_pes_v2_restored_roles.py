"""Offline checks for position-balanced source restoration audit."""
import unittest
from scripts.audit_fifa_fc_restored_2015_2020 import select_spread, FAMILIES, YEARS


class HistoricalRoleSampleTests(unittest.TestCase):
    def test_all_families_and_six_years_are_covered(self):
        self.assertEqual(FAMILIES, ("GK", "DEF", "MID", "ATT"))
        self.assertEqual(YEARS, set(range(2015, 2021)))

    def test_evenly_spread_sample_does_not_just_take_first_players(self):
        values = list(range(1000))
        x = select_spread(values, 20)
        self.assertEqual(len(x), 20)
        self.assertEqual(x[0], 0)
        self.assertEqual(x[-1], 999)
        self.assertEqual(len(set(x)), 20)
        self.assertGreater(x[10], 400)
        with self.assertRaises(ValueError):
            select_spread([1, 2], 3)


if __name__ == "__main__":
    unittest.main()

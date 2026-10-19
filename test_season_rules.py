import unittest
from datetime import date
from season_rules import Fixture, validate_double_round_robin, first_allowed_registration_date


class SeasonRulesTests(unittest.TestCase):
    def setUp(self):
        self.clubs = ["A", "B", "C", "D"]
        self.valid = [
            Fixture(1, "A", "D"), Fixture(1, "B", "C"),
            Fixture(2, "C", "A"), Fixture(2, "D", "B"),
            Fixture(3, "A", "B"), Fixture(3, "C", "D"),
            Fixture(4, "D", "A"), Fixture(4, "C", "B"),
            Fixture(5, "A", "C"), Fixture(5, "B", "D"),
            Fixture(6, "B", "A"), Fixture(6, "D", "C"),
        ]

    def test_valid_balanced_season(self):
        self.assertEqual(validate_double_round_robin(self.clubs, self.valid), [])

    def test_wrong_return_venue_fails(self):
        altered = [Fixture(4, "A", "D") if f == Fixture(4, "D", "A") else f for f in self.valid]
        self.assertTrue(validate_double_round_robin(self.clubs, altered))

    def test_duplicate_round_participant_fails(self):
        altered = list(self.valid)
        altered[1] = Fixture(1, "A", "C")
        self.assertTrue(validate_double_round_robin(self.clubs, altered))

    def test_post_lock_transfer_deferred(self):
        self.assertEqual(
            first_allowed_registration_date(date(2027, 1, 12), date(2026, 8, 1), date(2027, 7, 1), True),
            date(2027, 7, 1)
        )

    def test_external_league_transfer_not_deferred(self):
        self.assertEqual(
            first_allowed_registration_date(date(2027, 1, 12), date(2026, 8, 1), date(2027, 7, 1), False),
            date(2027, 1, 12)
        )


if __name__ == "__main__":
    unittest.main()

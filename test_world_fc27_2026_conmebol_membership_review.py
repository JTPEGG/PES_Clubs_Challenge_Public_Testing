"""FC27 original cup club -> individual 2026 domestic division review guards."""
import copy
import json
import unittest
from pathlib import Path

from world_fc27_2026_conmebol_domestic_overlay import validate_individual_memberships

WAREHOUSE = Path(__file__).parent / "data" / "warehouse"


class FC27IndividualDomesticClubReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cups = json.loads((WAREHOUSE / "fc27_2026_conmebol_official_country_review.json").read_text(encoding="utf-8"))["entries"]
        cls.domestic = json.loads((WAREHOUSE / "fc27_2026_conmebol_domestic_participation_review.json").read_text(encoding="utf-8"))

    def test_all_40_original_cup_clubs_have_unique_season_dated_domestic_evidence(self):
        members = validate_individual_memberships(self.cups, self.domestic)
        self.assertEqual(len(members), 40)
        self.assertEqual(len({(x["continental_source_group"], x["original_source_club"]) for x in members.values()}), 40)
        self.assertTrue(all(x["verified_season"] == 2026 for x in members.values()))
        self.assertEqual(
            {x["national_association"] for x in members.values()},
            set(self.domestic["countries"])
        )

    def test_missing_club_does_not_fall_back_to_its_national_top_division(self):
        data = copy.deepcopy(self.domestic)
        data["individual_club_memberships"].pop()
        with self.assertRaisesRegex(ValueError, "separate 2026 domestic membership"):
            validate_individual_memberships(self.cups, data)

    def test_duplicate_or_invented_identity_rejected(self):
        data = copy.deepcopy(self.domestic)
        data["individual_club_memberships"][0]["original_source_club"] = "Imaginary FC"
        with self.assertRaisesRegex(ValueError, "Missing, duplicated or unexpected"):
            validate_individual_memberships(self.cups, data)

    def test_country_code_season_and_evidence_cannot_be_guessed(self):
        for field, value in [
            ("national_association", "Somewhere"),
            ("domestic_code", "unknown.1"),
            ("verified_season", 2027),
            ("domestic_membership_source", "no source"),
            ("domestic_2026_roster_club", ""),
        ]:
            with self.subTest(field=field):
                data = copy.deepcopy(self.domestic)
                data["individual_club_memberships"][0][field] = value
                with self.assertRaisesRegex(ValueError, "Unsupported 2026"):
                    validate_individual_memberships(self.cups, data)


if __name__ == "__main__":
    unittest.main()

"""Focused, offline regression tests for V2 quality gate and source coverage."""
import unittest
from qa_fifa_pes_v2_quality_audit import (
    audit_source_manifest, source_coverage_status, alias_candidate_pairs,
    accuracy_summary,
)


class SourceCoverageQualityAuditTests(unittest.TestCase):
    def test_10500_row_scraper_ceiling_is_not_certified_complete(self):
        self.assertEqual(
            source_coverage_status(2020, 10500, "lbenz730/fifa_model"),
            "KNOWN_SCRAPER_PAGE_LIMIT_REACHED_COVERAGE_UNVERIFIED")
        self.assertEqual(
            source_coverage_status(2011, 10478, "lbenz730/fifa_model"),
            "SOURCE_COVERAGE_NOT_INDEPENDENTLY_VERIFIED")
        self.assertEqual(
            source_coverage_status(2020, 18278, "independent/SoFIFA"),
            "SOURCE_COVERAGE_NOT_INDEPENDENTLY_VERIFIED")

    def test_fc25_is_excluded_even_if_downloaded(self):
        self.assertEqual(
            source_coverage_status(2025, 18205, "any-provider"),
            "EXCLUDED_FC25_NOT_CONVERTED")
        report = audit_source_manifest({"downloads": [
            {"edition": 2020, "catalog_source": "lbenz730/fifa_model",
             "player_rows": 10500, "status": "DOWNLOADED"},
            {"edition": 2025, "catalog_source": "any-provider",
             "player_rows": 18205, "status": "DOWNLOADED"},
        ]})
        self.assertEqual(report["known_fifaindex_700_page_scrape_years"],
                         [2020])
        self.assertEqual(report["confirmed_complete_editions"], [])
        self.assertIn("EXCLUDED", report["year_records"]["2025"][
            "coverage_status"])

    def test_name_alias_candidates_require_unique_player_and_club(self):
        f = [{"short_name": "L. Messi", "long_name": "Lionel Messi",
              "age": "32", "nationality": "Argentina",
              "club": "Barcelona", "player_positions": "RW",
              "overall": "94"}]
        p = [{"name": "Lionel Messi", "age": "32",
              "nationality": "Argentina", "team_name": "Barcelona"}]
        self.assertEqual(len(alias_candidate_pairs(f, p)), 1)
        self.assertEqual(len(alias_candidate_pairs(f, p+p)), 0)
        f.append(dict(f[0]))
        self.assertEqual(len(alias_candidate_pairs(f, p)), 0)

    def test_empty_candidates_do_not_look_like_validated_accuracy(self):
        report = accuracy_summary([])
        self.assertEqual(report["provisional_matches"], 0)
        self.assertEqual(report["holdout_players"], 0)
        self.assertEqual(report["holdout_position_accuracy"]["GK"][
            "reliability"], "insufficient_sample")


if __name__ == "__main__":
    unittest.main()

"""Only source-published historical EUR revenue may be attached to a club."""
import json,unittest
from datetime import date
from pathlib import Path
from world_historical_revenue_evidence import standard_club_name
from world_historical_financial_circumstances import preseason_date

DATA=Path("data/warehouse/historical_club_revenue_observations_v1.json")


class RevenueProvenanceTests(unittest.TestCase):
    def test_euro_sources_are_real_numbers_not_fx_simulated_cash(self):
        obj=json.loads(DATA.read_text(encoding="utf-8"))
        self.assertEqual(obj["scope"],"mens_only")
        self.assertGreaterEqual(len(obj["observations"]),20)
        self.assertEqual(len(obj["sector_benchmarks"]),5)
        for o in obj["observations"]:
            self.assertEqual(o["currency"],"EUR")
            self.assertGreater(o["value"],200000000)
            self.assertTrue(o["source_url"].startswith("https://"))
            self.assertLessEqual(int(o["financial_year_end"]),2025)
            self.assertEqual(o["metric"],"football_revenue")

    def test_latest_revenue_cannot_appear_before_publication(self):
        obj=json.loads(DATA.read_text(encoding="utf-8"))
        o=next(o for o in obj["observations"] if
               o["club"]=="Manchester City" and
               o["financial_year_end"]==2025)
        self.assertLess(preseason_date(2026),date.fromisoformat(o["date_published"]))
        self.assertGreater(preseason_date(2027),date.fromisoformat(o["date_published"]))

    def test_official_company_names_match_without_fuzzy_guess(self):
        self.assertEqual(standard_club_name("Barcelona"),
                         standard_club_name("FC Barcelona"))
        self.assertEqual(standard_club_name("West Ham"),
                         standard_club_name("West Ham United"))
        self.assertNotEqual(standard_club_name("Manchester City"),
                            standard_club_name("Manchester United"))


if __name__=="__main__":unittest.main()

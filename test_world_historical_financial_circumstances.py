"""Evidence-to-policy safety tests for men's 22-season financial overlay."""
import json,tempfile,unittest,sqlite3
from pathlib import Path
from world_historical_financial_circumstances import (
    load_evidence,preseason_date,impact,norm,build
)
EVIDENCE="data/warehouse/historical_club_financial_events_v1.json"


class HistoricalFinanceEvidenceTests(unittest.TestCase):
    def test_verified_events_have_unique_primary_source_references(self):
        events=load_evidence(EVIDENCE)
        self.assertGreaterEqual(len(events),40)
        self.assertEqual(len(set(e["id"] for e in events)),len(events))
        self.assertTrue(all("https://" in e["source_url"] for e in events))
        self.assertTrue(all(e.get("verified_financial_amount_gbp") is None for e in events))
        self.assertTrue(any(e["club"]=="Chelsea" and
                            e["event_type"]=="ownership_change" for e in events))

    def test_cannot_apply_postseason_data_early(self):
        events=load_evidence(EVIDENCE)
        later=next(e for e in events if e["id"]=="reading-2023-wages")
        self.assertGreater(later["date"],preseason_date(2024))
        former=next(e for e in events if e["id"]=="wigan-unpaid-wages-2023")
        self.assertLess(former["date"],preseason_date(2024))
        self.assertLess(preseason_date(2027),preseason_date(2028))

    def test_over_budget_is_permitted_not_falsely_solved(self):
        wage,headroom,cash,health=impact([{"event_type":"relegation"}],
           base_wage_budget=120000,base_transfer_budget=10000000,pay=115000)
        self.assertEqual(wage,84000)
        self.assertEqual(headroom,-31000)
        self.assertEqual(cash,4200000)
        self.assertEqual(health,"model_wages_over_budget")

    def test_promotion_raises_headroom_distress_freezes_transfers(self):
        base=dict(base_wage_budget=100000,base_transfer_budget=8000000,pay=80000)
        promoted=impact([{"event_type":"promotion"}],**base)
        trouble=impact([{"event_type":"financial_distress"}],**base)
        self.assertGreater(promoted[1],impact([],**base)[1])
        self.assertEqual(trouble[2],0)
        self.assertLess(trouble[1],0)
        self.assertEqual(trouble[3],"documented_distress")

    def test_ownership_change_does_not_invent_cash(self):
        normal=impact([],base_wage_budget=250000,
                      base_transfer_budget=14000000,pay=220000)
        takeover=impact([{"event_type":"ownership_change"}],
                        base_wage_budget=250000,
                        base_transfer_budget=14000000,pay=220000)
        self.assertEqual(normal,takeover)

    def test_explicit_team_aliases_and_no_guess(self):
        self.assertEqual(norm("West Ham United"),norm("West Ham"))
        self.assertEqual(norm("Newcastle United"),norm("Newcastle Utd"))
        self.assertNotEqual(norm("Manchester United"),norm("Manchester City"))
        self.assertNotEqual(norm("Atletico Madrid"),norm("Real Madrid"))


if __name__=="__main__":
    unittest.main()

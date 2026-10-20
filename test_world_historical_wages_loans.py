"""Regression and held-out quality checks for historical salary and source loans."""
import unittest

from world_historical_wages_loans import (
    VERSION,age_on,calibration_wages,coefficient,expiry_source,
    interpolated_baseline,money_source,predicted_wage,resolve_parent,
    _season_contract_end
)


class WageLoanModelTests(unittest.TestCase):
    def test_source_unit_and_unusable_wage_sentinels(self):
        self.assertEqual(money_source(2005,"10000")[0],None)
        self.assertEqual(money_source(2015,"0")[0],None)
        self.assertEqual(money_source(2012,"1")[0],None)
        self.assertEqual(money_source(2012,"107000")[0],107000)
        self.assertEqual(money_source(2020,"€10K")[0],8800)
        self.assertEqual(money_source(2024,"340K")[0],292400)
        self.assertEqual(money_source(2027,None)[0],None)
        self.assertEqual(money_source(2026,"200000000")[0],None)

    def test_contract_length_is_an_end_year_not_duration(self):
        self.assertEqual(expiry_source(2006,"2010"),2010)
        self.assertEqual(expiry_source(2026,"2029.0"),2029)
        self.assertEqual(expiry_source(2020,"5"),None)
        self.assertEqual(_season_contract_end(2006,"2010","id",26),
                         ("2010-06-30","source_end_year_game_date_june30"))
        self.assertTrue(_season_contract_end(2027,"","id",35)[0].endswith("-06-30"))
        self.assertEqual(_season_contract_end(2005,None,"id",28),
                         _season_contract_end(2005,None,"id",28))

    def test_club_matching_ambiguous_or_unavailable_never_assigned(self):
        clubs={"chelsea":{"c20:chelsea"},
               "nacional":{"c20:portugal","c20:uruguay"},
               "arsenal":{"c20:arsenal"}}
        self.assertEqual(resolve_parent("Chelsea","c20:derby",clubs),
                         ("c20:chelsea","resolved"))
        self.assertEqual(resolve_parent("Nacional","c20:derby",clubs),
                         (None,"ambiguous_parent"))
        self.assertEqual(resolve_parent("Unknown Club","c20:derby",clubs),
                         (None,"parent_not_found"))
        self.assertEqual(resolve_parent("Chelsea","c20:chelsea",clubs),
                         (None,"invalid_same_club"))
        self.assertEqual(resolve_parent("Chelsea",None,clubs),
                         (None,"borrower_unknown"))

    def test_wage_training_is_deterministic_and_held_out(self):
        def row(i):
            return dict(key=f"player-2016-{i}",year=2016,
                        club="A" if i%3 else "B",rating=65+i%21,
                        age=26,position="CMF",
                        observed=round(4200*coefficient(65+i%21,26,"CMF")),
                        raw_wage="5000")
        sample=[row(i) for i in range(210)]
        b,club,holdout=calibration_wages({2016:sample})
        self.assertIn(2016,b)
        self.assertGreater(len(holdout[2016]),20)
        self.assertLess(len(holdout[2016]),100)
        self.assertGreater(b[2016],0)
        self.assertEqual((b,club,holdout),calibration_wages({2016:sample}))
        baseline,label=interpolated_baseline(2005,b)
        self.assertLess(baseline,b[2016])
        self.assertIn("backcast",label)
        self.assertTrue(predicted_wage(sample[0],b[2016],club[2016],
                                       {"A":[72]*15,"B":[78]*15})>50)

    def test_age_and_position_are_bounded(self):
        self.assertEqual(age_on("bad",2020),26)
        self.assertGreater(coefficient(85,28,"CF"),coefficient(60,28,"GK"))
        self.assertTrue(VERSION.startswith("historical-wage"))


if __name__=="__main__":
    unittest.main()

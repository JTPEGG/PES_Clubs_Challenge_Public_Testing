"""Regression and held-out quality checks for historical salary and source loans."""
import unittest

from world_historical_wages_loans import (
    VERSION,age_on,calibration_wages,coefficient,expiry_source,
    interpolated_baseline,money_source,predicted_wage,resolve_parent,
    _season_contract_end,fc27_source_wage_index,revise_fc27_wage,
    infer_fc27_club_continuity
)


class WageLoanModelTests(unittest.TestCase):
    def test_source_unit_and_unusable_wage_sentinels(self):
        self.assertEqual(money_source(2005,"10000")[0],None)
        self.assertEqual(money_source(2015,"0")[0],None)
        self.assertEqual(money_source(2012,"1")[0],None)
        self.assertIsNone(money_source(2012,"107000")[0])
        self.assertEqual(money_source(2012,"107000")[1],"fifaindex_units_unverified")
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

    def test_fc27_keeps_mbappe_and_haaland_top_source_wage_levels(self):
        previous=[
          dict(key="26-mbappe",source_id="231747",dob="1998-12-20",
             nationality="France",rating=91,club_name="Real Madrid",
             observed=518500),
          dict(key="26-haaland",source_id="239085",dob="2000-07-21",
             nationality="Norway",rating=90,club_name="Manchester City",
             observed=221000),
        ]
        idx=fc27_source_wage_index(previous)
        for row,expected in (
            (dict(source_id="231747",dob="1998-12-20",nationality="France",
                  rating=91,club_name="Real Madrid"),557400),
            (dict(source_id="239085",dob="2000-07-21",nationality="Norway",
                  rating=91,club_name="Manchester City"),237550),
        ):
            got,provenance,match,ref,pid=revise_fc27_wage(row,120000,idx)
            self.assertAlmostEqual(got,expected,delta=50)
            self.assertIn("same_club",provenance)
            self.assertIn("verified_id_dob",match)
            self.assertEqual(ref,518500 if row["source_id"]=="231747" else 221000)

    def test_fc27_refuses_id_only_match_and_limits_new_club_wage(self):
        previous=[dict(key="26-star",source_id="112",dob="1999-01-02",
            nationality="France",rating=89,club_name="Liverpool",observed=300000)]
        idx=fc27_source_wage_index(previous)
        target=dict(source_id="112",dob="1999-01-02",
            nationality="France",rating=87,club_name="Trabzonspor")
        wage,provenance,_,ref,_=revise_fc27_wage(target,42000,idx)
        self.assertEqual(wage,225000)
        self.assertGreater(wage,42000)
        self.assertIn("changed_club",provenance)
        self.assertEqual(ref,300000)
        target["dob"]="2000-01-02"
        wage,provenance,_,ref,_=revise_fc27_wage(target,42000,idx)
        self.assertEqual(wage,42000)
        self.assertIsNone(ref)
        self.assertIn("unmatched",provenance)

    def test_nationality_labels_are_synonyms_only_when_explicit(self):
        prior=[dict(key="26-frenkie",source_id="228702",dob="1997-05-12",
                    nationality="Netherlands",rating=87,
                    club_name="FC Barcelona",observed=144500),
               dict(key="26-kenan",source_id="277954",dob="2005-05-04",
                    nationality="Türkiye",rating=79,
                    club_name="Juventus",observed=68000)]
        idx=fc27_source_wage_index(prior)
        for r,expected in [
            (dict(source_id="228702",dob="1997-05-12",
                  nationality="Holland",rating=86,age=29,
                  club_name="FC Barcelona"),155350),
            (dict(source_id="277954",dob="2005-05-04",
                  nationality="Turkey",rating=84,age=21,
                  club_name="Juventus"),73100)
        ]:
            val,status,match,_,_=revise_fc27_wage(r,42000,idx)
            self.assertAlmostEqual(val,expected,delta=50)
            self.assertIn("same_club",status)
        wrong=dict(source_id="228702",dob="1997-05-12",
                   nationality="France",rating=86,age=29,
                   club_name="FC Barcelona")
        self.assertIn("unmatched",revise_fc27_wage(wrong,42000,idx)[1])

    def test_roster_overlap_alias_never_infers_bulk_one_way_transfer(self):
        prev=[];new=[]
        for i in range(20):
            prev.append(dict(key=f"old-{i}",source_id=str(i),
                dob="1999-01-01",nationality="Italy",rating=78,
                club_name="Inter",observed=30000))
            new.append(dict(key=f"new-{i}",source_id=str(i),
                dob="1999-01-01",nationality="Italy",rating=78,age=27,
                club_name="Lombardia FC"))
        idx=fc27_source_wage_index(prev)
        aliases=infer_fc27_club_continuity(new,idx)
        self.assertIn(("inter","lombardiafc"),aliases)
        result=revise_fc27_wage(new[0],12000,idx,aliases)
        self.assertIn("same_club",result[1])
        # Bare one-player movement does not create a club alias.
        one=infer_fc27_club_continuity(new[:1],idx)
        self.assertFalse(one)

    def test_changed_club_respects_source_wage_floor_not_star_pay_collapse(self):
        idx=fc27_source_wage_index([dict(key="26-salah",source_id="209331",
            dob="1992-06-15",nationality="Egypt",rating=91,
            club_name="Liverpool",observed=314500)])
        row=dict(source_id="209331",dob="1992-06-15",
            nationality="Egypt",rating=87,age=34,
            club_name="Trabzonspor")
        wage,status,match,ref,_=revise_fc27_wage(row,41100,idx)
        self.assertEqual(wage,235900)
        self.assertEqual(ref,314500)
        self.assertIn("changed_club",status)
        self.assertIn("wage_floor",match)

    def test_fc27_rejects_duplicate_2026_source_id_dob_nationality(self):
        prior=dict(key="a",source_id="777",dob="1998-01-01",
                   nationality="Brazil",rating=88,club_name="Ajax",observed=90000)
        duplicate={**prior,"key":"b"}
        idx=fc27_source_wage_index([prior,duplicate])
        self.assertFalse(idx)

    def test_age_and_position_are_bounded(self):
        self.assertEqual(age_on("bad",2020),26)
        self.assertGreater(coefficient(85,28,"CF"),coefficient(60,28,"GK"))
        self.assertTrue(VERSION.startswith("historical-wage"))


if __name__=="__main__":
    unittest.main()

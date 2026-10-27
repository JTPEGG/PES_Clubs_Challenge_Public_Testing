"""FC27 source pool regression: one edition, source-only and no unsupported teams."""
import unittest
from scripts.collect_pinned_2027_domestic_memberships import (
    PIN,EDITION,SOURCES,ALIASES,canonical_team,parse_matches
)

class FC27CompetitionMembershipTests(unittest.TestCase):
    def test_edition_target_and_domestic_only_sources(self):
        self.assertEqual(EDITION,2027)
        self.assertEqual(len(PIN),40)
        self.assertEqual(len(SOURCES),16)
        self.assertEqual(len({x[0] for x in SOURCES}),len(SOURCES))
        self.assertTrue(all(x[4]>=10 for x in SOURCES))
        self.assertEqual(next(x for x in SOURCES if x[0]=="us.mls")[4],30)
        self.assertEqual(next(x for x in SOURCES if x[0]=="en.6n")[3],6)
    def test_known_source_variants_not_fuzzy_matching(self):
        self.assertEqual(canonical_team("Milton Keynes Dons"),"MK Dons")
        self.assertEqual(canonical_team("Los Angeles Football Club"),"LAFC")
        self.assertEqual(canonical_team("Orlando City SC"),"Orlando City")
        self.assertEqual(canonical_team("Airdrie Utd"),"Airdrieonians")
        self.assertEqual(canonical_team("Queen of Sth"),"Queen of South")
        self.assertEqual(canonical_team("Annan Athletic"),"Annan")
        self.assertEqual(canonical_team("Elgin"),"Elgin City")
        self.assertEqual(canonical_team("Forfar"),"Forfar Athletic")
        self.assertEqual(canonical_team("Manchester United"),"Manchester United")
    def test_reject_outside_starting_edition_dates(self):
        with self.assertRaises(ValueError):
            parse_matches("date,home,away\n2025-08-04,Arsenal,Chelsea\n",
                          calendar=False,code="en.3")
        with self.assertRaises(ValueError):
            parse_matches("date,home,away\n2027-02-01,LAFC,Chicago Fire\n",
                          calendar=True,code="us.mls")
    def test_no_mixed_nonleague_all_star_teams(self):
        data=("date,home,away\n"
              "2026-05-04,LAFC,San Diego FC\n"
              "2026-07-04,MLS All-Stars,Liga MX All-Stars\n"
              "2026-09-03,Los Angeles Football Club,FC Cincinnati\n")
        self.assertEqual(parse_matches(data,calendar=True,code="us.mls"),
             [("LAFC","San Diego FC"),("LAFC","FC Cincinnati")])
    def test_reject_unsupported_csv(self):
        with self.assertRaises(ValueError):
            parse_matches("Team1,Team2\nA,B\n",calendar=False,code="en.3")

if __name__=="__main__":unittest.main()

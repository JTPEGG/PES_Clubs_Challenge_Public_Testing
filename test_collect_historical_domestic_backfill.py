"""Data-backed and gap-specific historical league membership source collection."""
import unittest
from scripts.collect_historical_domestic_backfill import (
   source_targets,parse_fixture_source,EDITIONS,REPOS
)

class HistoricalDomesticBackfillTests(unittest.TestCase):
    def test_fifa_2022_japan_turkey_brazil_correct_starting_seasons(self):
        rows=source_targets(2022,set())
        j=next(x for x in rows if x[2]=="jp.1")
        tr=next(x for x in rows if x[2]=="tr.1")
        br=next(x for x in rows if x[2]=="br.1")
        self.assertTrue(j[6].endswith("/asia/japan/2021_jp1.txt"))
        self.assertTrue(tr[6].endswith("/turkey/2021-22_tr1.txt"))
        self.assertTrue(br[6].endswith("/brazil/2021_br1.txt"))
        self.assertEqual(j[1],"2021")
        self.assertEqual(tr[1],"2021-22")
    def test_no_prior_sourced_duplicate(self):
        rows=source_targets(2022,{(2022,"jp.1"),(2022,"tr.1"),(2022,"br.1")})
        self.assertFalse(any(x[2] in {"jp.1","tr.1","br.1"} for x in rows))
    def test_fc25_absent_and_22_original_editions(self):
        self.assertEqual(len(EDITIONS),22)
        self.assertNotIn(2025,EDITIONS)
        with self.assertRaises(ValueError):
            source_targets(2025,set())
    def test_old_legacy_csv_not_used_for_later_seasons(self):
        self.assertTrue(any(x[-1]=="fixturecsv" for x in source_targets(2012,set())))
        self.assertFalse(any(x[-1]=="fixturecsv" for x in source_targets(2020,set())))
    def test_fixture_parser_never_populates_games_or_squads(self):
        contents=("# Teams      10\n"+
            "  15:00  Team A            2-1 (0-0)  Team B\n"*60)
        with self.assertRaises(ValueError):
            parse_fixture_source(contents,"footballtxt")
        contents=("# Teams      2\n"+
            "  15:00  Team A            2-1 (0-0)  Team B\n"*60)
        with self.assertRaises(ValueError):
            parse_fixture_source(contents,"footballtxt")
    def test_no_unpinned_repositories(self):
        self.assertEqual(set(REPOS),{"world","europe","south","soccerverse"})
        self.assertTrue(all("/" in url and len(url.split("/")[-1])==40
                            for url in REPOS.values()))

if __name__=="__main__":
    unittest.main()

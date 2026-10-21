"""Never mistake club league evidence coverage for career readiness."""
import csv,sqlite3,tempfile,unittest
from pathlib import Path
from scripts.audit_historical_edition_readiness import audit

class EditionPilotReadinessTests(unittest.TestCase):
    def test_ranks_best_evidenced_year_without_opening_careers(self):
        with tempfile.TemporaryDirectory() as f:
            root=Path(f)
            with sqlite3.connect(root/"source.sqlite") as c:
                c.executescript("""
                CREATE TABLE edition_career_starting_league_candidates (
                  edition INT,club_key TEXT,club TEXT,starting_competition TEXT,
                  evidence_origin TEXT,career_status TEXT);
                CREATE TABLE edition_club_competitions(
                  edition INT,club_key TEXT,group_type TEXT,original_source_league TEXT);
                CREATE TABLE edition_readiness(edition INT,career_ready INT);
                CREATE TABLE competition_seasons(edition INT,code TEXT);
                CREATE TABLE sourced_nonplayable_feeder_clubs(edition INT);
                CREATE TABLE season_versioned_rules(
                  edition INT,lower TEXT,upper TEXT,feeder_verified INT);
                CREATE TABLE game_source_domestic_competitions(edition INT);
                """)
                c.executemany("INSERT INTO edition_club_competitions VALUES (?,?,'domestic_source_group',NULL)",[
                    (2017,'a'),(2017,'b'),(2018,'c'),(2018,'d')])
                c.executemany("INSERT INTO edition_career_starting_league_candidates VALUES (?,?,?,?,?,?)",[
                    (2017,'a','Team A',None,'unresolved','blocked'),
                    (2017,'b','Team B','2017:en.1','independent_fixture_evidence','blocked'),
                    (2018,'c','Team C','GAME:2018:12','original_fifa_game_source','blocked'),
                    (2018,'d','Team D','2018:en.1','independent_fixture_evidence','blocked')])
                c.executemany("INSERT INTO edition_readiness VALUES (?,0)",[(2017,),(2018,)])
                c.executemany("INSERT INTO competition_seasons VALUES (?,?)",[
                    (2017,'2017:en.1'),(2018,'2018:en.1')])
                c.execute("INSERT INTO season_versioned_rules VALUES(2018,'ENG:CH','ENG:PL',0)")
            r=audit(root/"source.sqlite",root/"out",strict=False)
            self.assertEqual(r["first_diagnostic_pilot_year"],2018)
            self.assertEqual(r["unresolved_game_club_seasons"],1)
            self.assertEqual(r["league_to_pyramid_links_needing_verification"],1)
            self.assertEqual(r["career_ready_editions"],0)
            with (root/"out/HISTORICAL_EDITION_CAREER_PILOT_READINESS.csv").open(
                encoding="utf-8-sig") as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),2)
            self.assertEqual(next(x for x in rows if x["Edition"]=="2018")["Can_Create_Career"],"no")
            self.assertEqual(next(x for x in rows if x["Edition"]=="2018")["Unverified_Feeder_Rules"],"1")
            self.assertEqual(r["pilot_readiness"],"read_only_evidence_diagnostic_not_career_enabled")

if __name__=="__main__":
    unittest.main()

"""The early-FIFA Spanish second division overlay cannot invent identities."""
import csv,sqlite3,tempfile,unittest
from pathlib import Path
from world_historical_legacy_segunda_overlay import build

class HistoricalSegundaOverlayTests(unittest.TestCase):
    def test_merges_only_real_same_edition_source_clubs(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with sqlite3.connect(root/"source.sqlite") as db:
                db.executescript("""
                  CREATE TABLE edition_club_competitions(
                    edition INT,club_key TEXT,club TEXT,group_type TEXT,
                    PRIMARY KEY(edition,club_key));
                  CREATE TABLE edition_readiness(edition INT,career_ready INT);
                  CREATE TABLE full_historical_club_starting_leagues(
                    edition INT,club_key TEXT,club TEXT,
                    starting_competition TEXT,evidence_origin TEXT,
                    game_league_id TEXT,game_league_name TEXT,
                    game_source_tier INT,career_status TEXT);
                """)
                db.executemany("INSERT INTO edition_club_competitions VALUES(?,?,?,'missing_original_source_league')",[
                    (2005,"almeria","UD Almería"),(2005,"cadiz","Cádiz CF"),(2006,"also","UD Almería")])
                db.executemany("INSERT INTO full_historical_club_starting_leagues VALUES(?,?,?,?,?,?,?,?,?)",[
                    (2005,"almeria","UD Almería",None,"unresolved",None,None,None,"blocked"),
                    (2005,"cadiz","Cádiz CF","2005:es.2","independent_fixture_evidence",None,None,None,"blocked"),
                    (2006,"also","UD Almería",None,"unresolved",None,None,None,"blocked"),
                ])
                db.execute("INSERT INTO edition_readiness VALUES(2005,0)")
            def write(filename,headers,rows):
                with (root/filename).open("w",newline="",encoding="utf-8") as f:
                    w=csv.writer(f);w.writerow(headers);w.writerows(rows)
            write("leagues.csv",
                  ["Edition","League_Code","Tier","Source_Clubs","Season","Evidence_Status","Source_URL","SHA256"],
                  [(2005,"es.2",2,22,"2004-05","pinned_CC0_dated_fixture_memberships","source","digest")])
            write("clubs.csv",["Edition","League_Code","Club","Source_URL","SHA256","Evidence_Status"],
                  [(2005,"es.2",x,"source","digest","dated_fixture_team_not_independently_game_verified")
                   for x in ["UD Almería","Cádiz CF"]+[f"Team {i:02}" for i in range(20)]])
            write("matches.csv",["Edition","FIFA_Club_Key","FIFA_Club","League_Code",
                    "Fixture_Club","Source_URL","SHA256","Evidence_Method"],
                  [(2005,"almeria","UD Almería","es.2","UD Almería","source","digest",
                    "unique_same_edition_canonical_name_provisional"),
                   (2005,"cadiz","Cádiz CF","es.2","Cádiz CF","source","digest",
                    "unique_same_edition_canonical_name_provisional")])
            report=build(root/"source.sqlite",root/"leagues.csv",root/"clubs.csv",
                         root/"matches.csv",root/"out",strict=False)
            self.assertEqual(report["old_starting_league_evidence"],1)
            self.assertEqual(report["new_early_fifa_club_division_candidates"],1)
            self.assertEqual(report["combined_game_club_seasons_with_league_evidence"],2)
            self.assertEqual(report["career_ready_editions"],0)
            with sqlite3.connect(root/"out/HISTORICAL_CAREER_DIVISION_CANDIDATES_22_EDITION.sqlite") as db:
                rows=db.execute("SELECT club_key,starting_competition FROM edition_career_starting_league_candidates ORDER BY edition,club_key").fetchall()
                self.assertEqual(rows,[("almeria","2005:es.2"),("cadiz","2005:es.2"),("also",None)])
                self.assertFalse(db.execute("PRAGMA foreign_key_check").fetchall())

if __name__=="__main__": unittest.main()

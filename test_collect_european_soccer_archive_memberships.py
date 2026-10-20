import csv,json,sqlite3,tempfile,unittest
from pathlib import Path
from scripts.collect_european_soccer_archive_memberships import extract,COUNTRIES,SOURCE_COMMIT

class EuropeanHistoricalClubPools(unittest.TestCase):
 def test_season_start_is_game_edition_and_deduplicates_by_country(self):
  with tempfile.TemporaryDirectory() as folder:
   d=Path(folder);src=d/"matches.sqlite"
   with sqlite3.connect(src) as db:
    db.executescript("""
     CREATE TABLE Country(id INTEGER,name TEXT);
     CREATE TABLE League(id INTEGER,country_id INTEGER);
     CREATE TABLE Team(team_api_id INTEGER,team_long_name TEXT);
     CREATE TABLE Match(id INTEGER,season TEXT,league_id INTEGER,home_team_api_id INTEGER,away_team_api_id INTEGER);
    """)
    db.execute("INSERT INTO Country VALUES(1,'England')")
    db.execute("INSERT INTO League VALUES(13,1)")
    db.executemany("INSERT INTO Team VALUES(?,?)",[(i,f"Club {i:02d}") for i in range(20)])
    db.executemany("INSERT INTO Match VALUES(?,?,?,?,?)",
       [(i+1,"2008/2009",13,i%20,(i+3)%20) for i in range(180)])
   result=extract(src,d/"output","examplehash")
   self.assertEqual(result["complete_season_divisions"],1)
   self.assertEqual(result["independent_season_club_memberships"],20)
   with (d/"output/EUROPEAN_MATCH_DOMESTIC_LEAGUE_SEASONS.csv").open(encoding="utf-8-sig") as f:
    seasons=list(csv.DictReader(f))
   self.assertEqual((seasons[0]["Edition"],seasons[0]["Edition_Code"]),("2009","2009:en.1"))
   self.assertTrue(SOURCE_COMMIT)
   self.assertEqual(len(COUNTRIES),11)
   self.assertFalse(result["historical_careers_ready"])
 def test_wrong_team_identity_is_not_fabricated(self):
  with tempfile.TemporaryDirectory() as folder:
   d=Path(folder);src=d/"matches.sqlite"
   with sqlite3.connect(src) as db:
    db.executescript("""
     CREATE TABLE Country(id INTEGER,name TEXT);
     CREATE TABLE League(id INTEGER,country_id INTEGER);
     CREATE TABLE Team(team_api_id INTEGER,team_long_name TEXT);
     CREATE TABLE Match(id INTEGER,season TEXT,league_id INTEGER,home_team_api_id INTEGER,away_team_api_id INTEGER);
    """)
    db.execute("INSERT INTO Country VALUES(1,'England')")
    db.execute("INSERT INTO League VALUES(13,1)")
    db.execute("INSERT INTO Team VALUES(1,'Arsenal')")
    db.execute("INSERT INTO Match VALUES(1,'2008/2009',13,1,2)")
   result=extract(src,d/"output")
   self.assertEqual(result["complete_season_divisions"],0)
   self.assertEqual(result["skipped_match_rows"].get("match_missing_team_identity"),1)

if __name__=="__main__":unittest.main()

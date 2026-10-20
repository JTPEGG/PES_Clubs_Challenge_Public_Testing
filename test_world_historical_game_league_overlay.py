"""Ensure genuine game league names survive in the consolidated SQLite world."""
import csv,json,sqlite3,tempfile,unittest
from pathlib import Path
from world_historical_game_league_overlay import build

class GameHomeLeagueOverlayTests(unittest.TestCase):
 def test_merges_direct_game_league_without_overriding_independent_fixture_league(self):
  with tempfile.TemporaryDirectory() as f:
   d=Path(f)
   with sqlite3.connect(d/"registry.sqlite") as db:
    db.executescript("""
    CREATE TABLE edition_club_competitions(edition INTEGER,club_key TEXT,club TEXT,evidence_competition TEXT,career_status TEXT,
    PRIMARY KEY(edition,club_key));
    CREATE TABLE edition_readiness(edition INTEGER,career_ready INTEGER);
    """)
    db.executemany("INSERT INTO edition_club_competitions VALUES (?,?,?,?,?)",[
      (2022,"a","Manchester United","2022:en.1","blocked"),
      (2022,"b","Arsenal",None,"blocked"),
      (2022,"c","Portsmouth",None,"blocked")])
    db.execute("INSERT INTO edition_readiness VALUES(2022,0)")
   with (d/"games.csv").open("w",newline="") as f:
    w=csv.writer(f)
    w.writerow(("Edition","FIFA_Club_Key","Original_FIFA_Club","EA_Team_ID","EA_Team_Name",
      "Game_League_ID","Game_League_Name","Game_League_Level",
      "Game_Club_Country","EA_Observation_Count","Name_Method","Evidence_Status"))
    w.writerows([
     (2022,"a","Manchester United",11,"Manchester United",13,"Premier League",1,"England",6,
      "unique_same_edition_exact_name","previous_fixture_evidence_corroborated"),
     (2022,"b","Arsenal",12,"Arsenal",13,"Premier League",1,"England",6,
      "unique_same_edition_exact_name","game_edition_home_league_identified"),
    ])
   result=build(d/"registry.sqlite",d/"games.csv",d/"output",strict=False)
   self.assertEqual(result["source_fixture_club_seasons_with_evidence"],1)
   self.assertEqual(result["game_home_leagues_filling_prior_gaps"],1)
   self.assertEqual(result["club_seasons_with_starting_league_evidence"],2)
   self.assertEqual(result["remaining_without_any_starting_league_evidence"],1)
   self.assertEqual(result["career_ready_editions"],0)
   with sqlite3.connect(d/"output/HISTORICAL_COMPETITION_REGISTER_WITH_ORIGINAL_FIFA_LEAGUES.sqlite") as db:
    rows=db.execute("SELECT club,starting_competition,evidence_origin FROM historical_club_starting_leagues ORDER BY club").fetchall()
    self.assertEqual(rows,[
       ("Arsenal","GAME:2022:13","original_fifa_game_source"),
       ("Manchester United","2022:en.1","independent_fixture_evidence"),
       ("Portsmouth",None,"unresolved")])
    self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0],"ok")
    self.assertEqual(db.execute("SELECT career_ready FROM edition_readiness").fetchone()[0],0)

 def test_reject_original_club_display_name_drift(self):
  with tempfile.TemporaryDirectory() as f:
   d=Path(f)
   with sqlite3.connect(d/"registry.sqlite") as db:
    db.executescript("""
    CREATE TABLE edition_club_competitions(edition INTEGER,club_key TEXT,club TEXT,evidence_competition TEXT,career_status TEXT,PRIMARY KEY(edition,club_key));
    CREATE TABLE edition_readiness(edition INTEGER,career_ready INTEGER);
    """)
    db.execute("INSERT INTO edition_club_competitions VALUES(2022,'a','Man Utd',NULL,'blocked')")
    db.execute("INSERT INTO edition_readiness VALUES(2022,0)")
   with (d/"games.csv").open("w",newline="") as f:
    w=csv.writer(f);w.writerow(("Edition","FIFA_Club_Key","Original_FIFA_Club",
       "EA_Team_ID","EA_Team_Name","Game_League_ID","Game_League_Name",
       "Game_League_Level","Game_Club_Country","EA_Observation_Count",
       "Name_Method","Evidence_Status"))
    w.writerow((2022,"a","Liverpool",11,"Liverpool",13,"Premier League",1,"England",3,
               "unique_same_edition_exact_name","game_edition_home_league_identified"))
   with self.assertRaises(ValueError):
    build(d/"registry.sqlite",d/"games.csv",d/"out",strict=False)

if __name__=="__main__":unittest.main()

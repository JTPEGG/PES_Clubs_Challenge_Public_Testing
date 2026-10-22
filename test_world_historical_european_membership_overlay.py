"""Guard original FIFA club identities against external archive name collisions."""
import csv,sqlite3,tempfile,unittest
from pathlib import Path
from world_historical_european_membership_overlay import build

class HistoricalEuropeanOverlayTests(unittest.TestCase):
 def test_only_unique_same_edition_source_clubs_fill_missing_game_assignments(self):
  with tempfile.TemporaryDirectory() as folder:
   d=Path(folder)
   with sqlite3.connect(d/"register.sqlite") as db:
    db.executescript("""
     PRAGMA foreign_keys=ON;
     CREATE TABLE edition_club_competitions(
       edition INTEGER,club_key TEXT,club TEXT,career_status TEXT,
       PRIMARY KEY(edition,club_key));
     CREATE TABLE edition_readiness(edition INTEGER,career_ready INTEGER);
     CREATE TABLE historical_club_starting_leagues(
       edition INTEGER,club_key TEXT,club TEXT,starting_competition TEXT,
       evidence_origin TEXT,game_league_id TEXT,game_league_name TEXT,
       game_source_tier INTEGER,career_status TEXT);
    """)
    db.executemany("INSERT INTO edition_club_competitions VALUES(?,?,?,'blocked')",[
      (2010,"A","Club Alpha"),(2010,"B","Club Beta"),
      (2010,"C","River Plate"),(2011,"D","Club Alpha")])
    db.executemany("INSERT INTO historical_club_starting_leagues VALUES(?,?,?,?,?,?,?,?,?)",[
      (2010,"A","Club Alpha",None,"unresolved",None,None,None,"blocked"),
      (2010,"B","Club Beta","GAME:2010:2","original_fifa_game_source","2","First",1,"blocked"),
      (2010,"C","River Plate",None,"unresolved",None,None,None,"blocked"),
      (2011,"D","Club Alpha",None,"unresolved",None,None,None,"blocked")])
    db.execute("INSERT INTO edition_readiness VALUES(2010,0)")
   with (d/"leagues.csv").open("w",newline="") as h:
    w=csv.writer(h)
    w.writerow(["Edition","Edition_Code","League_Code","Tier","Competition",
       "Country","Source_URL","Source_SHA256","Evidence_Status"])
    w.writerows([
      (2010,"2010:pt.1","pt.1",1,"League","Portugal","source","sha",
       "season_match_team_ids_crosschecked_non_game_id"),
      (2010,"2010:ar.1","ar.1",1,"League","Argentina","source","sha",
       "season_match_team_ids_crosschecked_non_game_id"),
      (2010,"2010:uy.1","uy.1",1,"League","Uruguay","source","sha",
       "season_match_team_ids_crosschecked_non_game_id")])
   with (d/"clubs.csv").open("w",newline="") as h:
    w=csv.writer(h);w.writerow(["Edition","League_Code","Country",
       "Club","Source_URL","Source_SHA256","Evidence_Status"])
    for code,country,name in [("pt.1","Portugal","Club Alpha"),
       ("pt.1","Portugal","Club Beta"),("ar.1","Argentina","River Plate"),
       ("uy.1","Uruguay","River Plate")]:
      w.writerow([2010,code,country,name,"source","sha",
        "independent_match_team_not_original_fifa_identity"])
   res=build(d/"register.sqlite",d/"leagues.csv",d/"clubs.csv",d/"out",strict=False)
   self.assertEqual(res["new_source_linked_club_seasons"],1)
   self.assertEqual(res["previous_league_evidence"],1)
   self.assertEqual(res["combined_club_seasons_with_league_evidence"],2)
   self.assertEqual(res["name_collisions_pending_manual_review"],1)
   self.assertEqual(res["career_ready_editions"],0)
   with sqlite3.connect(d/"out/HISTORICAL_COMPETITION_REGISTER_WITH_EUROPEAN_SOURCE_LEAGUES.sqlite") as db:
    assert db.execute("PRAGMA foreign_key_check").fetchall()==[]
    assert db.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
    mappings=db.execute("""SELECT club_key,starting_competition
       FROM expanded_historical_club_starting_leagues ORDER BY club_key""").fetchall()
    self.assertEqual(mappings,[("A","2010:pt.1"),("B","GAME:2010:2"),
                               ("C",None),("D",None)])

if __name__=="__main__":unittest.main()

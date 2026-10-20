import csv,sqlite3,tempfile,unittest
from pathlib import Path
from scripts.match_original_fifa_game_leagues import audit

class SameEditionGameLeagueTests(unittest.TestCase):
 def test_unique_game_name_recovers_actual_original_home_league_and_rejects_conflicts(self):
  with tempfile.TemporaryDirectory() as folder:
   d=Path(folder)
   with sqlite3.connect(d/"original.sqlite") as db:
    db.execute("CREATE TABLE clubs(edition INTEGER,club_key TEXT,name TEXT,league_key TEXT)")
    db.executemany("INSERT INTO clubs VALUES(?,?,?,?)",[
     (2022,"club1","Manchester United",None),
     (2022,"club2","Arsenal",None),
     (2022,"club3","Rangers",None),
     (2022,"club4","Same Name",None),
     (2022,"club5","Same Name",None),
     (2022,"club8","St Mirren",None),
     (2021,"club6","Manchester United",None),
     (2024,"club7","Arsenal",None)])
   with sqlite3.connect(d/"registry.sqlite") as db:
    db.execute("CREATE TABLE edition_club_competitions(edition INTEGER,club_key TEXT,evidence_competition TEXT)")
    db.execute("INSERT INTO edition_club_competitions VALUES(2022,'club2','2022:en.1')")
   with (d/"teams.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.writer(f);w.writerow(("fifa_version","team_name","team_id","league_id",
      "league_name","league_level","nationality_name","fifa_update"))
    w.writerows([
      ("22","Manchester United",11,13,"Premier League",1,"England","1"),
      ("22","Manchester United",11,13,"Premier League",1,"England","2"),
      ("22","Arsenal",12,13,"Premier League",1,"England","1"),
      ("22","Rangers",13,50,"Scottish Premiership",1,"Scotland","1"),
      ("22","Rangers",13,52,"EFL Championship",2,"England","2"),
      ("22","Same Name",14,13,"Premier League",1,"England","1"),
      ("22","Saint Mirren",16,50,"Scottish Premiership",1,"Scotland","1"),
      ("21","Arsenal",12,13,"Premier League",1,"England","1"),
      ("25","Manchester United",11,13,"Premier League",1,"England","1"),
      ("22","Southampton",15,0,"Rest of World",1,"England","1"),
     ])
   result=audit(d/"original.sqlite",d/"teams.csv",d/"out",d/"registry.sqlite")
   self.assertEqual(result["new_game_home_leagues_not_previously_in_fixture_register"],2)
   self.assertEqual(result["source_game_name_controlled_alias"],1)
   self.assertEqual(result["previous_independent_fixture_evidence_corroborated"],1)
   self.assertEqual(result["ambiguous_source_or_game_names"],3)
   self.assertEqual(result["unique_same_edition_name_domestic_league_matches"],3)
   with (d/"out/FIFA_GAME_EDITION_EXACT_CLUB_DOMESTIC_LEAGUES.csv").open(encoding="utf-8-sig") as f:
    rows=list(csv.DictReader(f))
   self.assertEqual({x["FIFA_Club_Key"] for x in rows},{"club1","club2","club8"})
   self.assertTrue(result["no_cross_year_inheritance"])
   self.assertFalse(result["modified_squads"])
   self.assertTrue(result["no_career_activation"])

if __name__=="__main__":unittest.main()

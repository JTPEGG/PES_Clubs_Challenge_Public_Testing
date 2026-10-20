import csv,sqlite3,tempfile,unittest
from pathlib import Path
from scripts.audit_historical_ea_team_id_leagues import audit,eid,edition_of,viable_league

class HistoricalSameVersionIdAuditTests(unittest.TestCase):
 def test_parse_only_explicit_team_id(self):
  self.assertEqual(eid("c2022:unspecified:id:111326-abc"),111326)
  self.assertIsNone(eid("c2022:unspecified:name:Liverpool"))
  self.assertEqual(edition_of("23"),2023)
  self.assertEqual(edition_of("2015"),2015)
  self.assertIsNone(edition_of("24"))
  self.assertIsNone(edition_of("2024"))
 def test_never_call_cup_or_rest_of_world_a_domestic_division(self):
  self.assertFalse(viable_league("Rest of World",1))
  self.assertFalse(viable_league("CONMEBOL Libertadores",1))
  self.assertFalse(viable_league("Premier League",""))
  self.assertTrue(viable_league("Premier League",1))
 def test_real_same_edition_id_and_avoid_future_game_team_leagues(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);db=p/"src.sqlite";f=p/"teams.csv"
   with sqlite3.connect(db) as c:
    c.execute("CREATE TABLE clubs(edition INTEGER,club_key TEXT,name TEXT,league_key TEXT)")
    c.executemany("INSERT INTO clubs VALUES (?,?,?,?)",[
      (2019,"c2019:id:1-foo","Club One",None),
      (2020,"c2020:id:1-bar","Club One",None),
      (2021,"c2021:id:2-baz","Liverpool",None),
      (2022,"c2022:no-game-id","Other",None)])
   with f.open("w",newline="") as h:
    w=csv.writer(h);w.writerow(("fifa_version","team_id","team_name",
       "league_id","league_name","league_level","nationality_name","fifa_update"))
    w.writerows([
      (19,1,"Club One",13,"Premier League",1,"England",2),
      (20,1,"Club One",14,"Championship",2,"England",2),
      (21,2,"Liverpool Uruguay",353,"Uruguay First Division",1,"Uruguay",2),
      (22,1,"Club One",14,"Championship",2,"England",2),
      (19,3,"Another Team",13,"Premier League",1,"England",2),
    ])
   result=audit(db,f,p/"out")
   self.assertEqual(result["same_edition_ea_game_ids_with_domestic_league"],2)
   self.assertEqual(result["exact_id_plus_name"],2)
   self.assertEqual(result["same_ea_id_name_discrepancy_review"],1)
   with (p/"out/EA_GAME_TEAM_LEAGUE_EXACT_ID_REVIEW.csv").open(
        encoding="utf-8-sig",newline="") as h:
    matches=list(csv.DictReader(h))
   self.assertEqual(len(matches),2)
   self.assertEqual([x["Game_League_Name"] for x in matches[:2]],
      ["Premier League","Championship"])
   self.assertTrue(all(x["Edition"]!="2022" for x in matches))
if __name__=="__main__":unittest.main()

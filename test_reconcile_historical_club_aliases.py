"""Tests for strict season-scoped historical FIFA club alias automation."""
import csv,sqlite3,tempfile,unittest
from pathlib import Path
from scripts.reconcile_historical_club_aliases import alias_key,reconcile

class ControlledHistoricalAliases(unittest.TestCase):
 def test_safe_club_name_abbreviations(self):
  self.assertEqual(alias_key("Man Utd"),alias_key("Manchester United"))
  self.assertEqual(alias_key("Nottm Forest"),alias_key("Nottingham Forest"))
  self.assertEqual(alias_key("St Mirren"),alias_key("Saint Mirren"))
  self.assertEqual(alias_key("QPR"),alias_key("Queens Park Rangers"))
  self.assertNotEqual(alias_key("Liverpool"),alias_key("Liverpool Uruguay"))
  self.assertNotEqual(alias_key("Manchester Utd"),alias_key("Manchester City"))

 def test_edition_scoping_identity_guard_and_no_squad_creation(self):
  with tempfile.TemporaryDirectory() as folder:
   d=Path(folder)
   source=d/"source.sqlite";registry=d/"register.sqlite"
   with sqlite3.connect(source) as db:
    db.execute("CREATE TABLE clubs(edition INTEGER,club_key TEXT,name TEXT,league_key TEXT)")
    db.executemany("INSERT INTO clubs VALUES (?,?,?,?)",[
       (2022,"man-1","Man Utd",None),
       (2022,"nottm-1","Nottm Forest",None),
       (2022,"river-1","River Plate",None),
       (2022,"no-1","Unlisted FC",None),
       (2023,"man-2","Man Utd",None),
       (2022,"taken","Other City",None),
    ])
   with sqlite3.connect(registry) as db:
    db.executescript("""
     CREATE TABLE edition_club_competitions(
      edition INTEGER,club_key TEXT,confidence TEXT,group_type TEXT);
     CREATE TABLE competition_seasons(code TEXT,edition INTEGER,country TEXT,tier INTEGER);
     CREATE TABLE sourced_domestic_league_clubs(
      edition INTEGER,competition_code TEXT,club_name TEXT,source_url TEXT,
      source_sha256 TEXT,verification TEXT);
     CREATE TABLE fixture_club_evidence(
      edition INTEGER,club_key TEXT,competition_code TEXT,fixture_club TEXT);
    """)
    db.executemany("INSERT INTO edition_club_competitions VALUES(?,?,?,?)",[
      (2022,x,"unresolved","missing_original_source_league")
      for x in ("man-1","nottm-1","river-1","no-1")]
      +[(2023,"man-2","unresolved","missing_original_source_league"),
        (2022,"taken","fixture_exact","domestic_source_group")])
    db.executemany("INSERT INTO competition_seasons VALUES (?,?,?,?)",[
     ("2022:en.1",2022,"England",1),("2022:ar.1",2022,"Argentina",1),
     ("2022:uy.1",2022,"Uruguay",1)])
    db.executemany("INSERT INTO sourced_domestic_league_clubs VALUES (?,?,?,?,?,?)",[
      (2022,"2022:en.1","Manchester United","https://a", "abc","independent_fixture_membership"),
      (2022,"2022:en.1","Nottingham Forest","https://a","abc","independent_fixture_membership"),
      (2022,"2022:ar.1","River Plate","https://b","def","independent_fixture_membership"),
      (2022,"2022:uy.1","River Plate","https://c","ghi","independent_fixture_membership"),
    ])
    db.execute("INSERT INTO fixture_club_evidence VALUES (2022,'taken','2022:en.1','Other City')")
   audit=reconcile(source,registry,d/"output")
   with (d/"output/AUTO_CONTROLLED_CLUB_ALIASES.csv").open(encoding="utf-8-sig") as f:
    rows=list(csv.DictReader(f))
   self.assertEqual(audit["controlled_unique_same_edition_name_links"],2)
   self.assertEqual({r["FIFA_Club_Key"] for r in rows},{"man-1","nottm-1"})
   self.assertEqual({r["Edition"] for r in rows},{"2022"})
   self.assertFalse(audit["career_ready"])
   self.assertEqual(audit["player_squads_created"],0)

 def test_alias_collision_between_game_clubs_rejected(self):
  with tempfile.TemporaryDirectory() as folder:
   d=Path(folder)
   with sqlite3.connect(d/"source.sqlite") as db:
    db.execute("CREATE TABLE clubs(edition INTEGER,club_key TEXT,name TEXT,league_key TEXT)")
    db.executemany("INSERT INTO clubs VALUES (?,?,?,?)",[
      (2022,"a","Man Utd",None),(2022,"b","Manchester Utd",None)])
   with sqlite3.connect(d/"registry.sqlite") as db:
    db.executescript("""
      CREATE TABLE edition_club_competitions(edition INTEGER,club_key TEXT,confidence TEXT,group_type TEXT);
      CREATE TABLE competition_seasons(code TEXT,edition INTEGER,country TEXT,tier INTEGER);
      CREATE TABLE sourced_domestic_league_clubs(edition INTEGER,competition_code TEXT,club_name TEXT,source_url TEXT,source_sha256 TEXT,verification TEXT);
      CREATE TABLE fixture_club_evidence(edition INTEGER,club_key TEXT,competition_code TEXT,fixture_club TEXT);
    """)
    db.executemany("INSERT INTO edition_club_competitions VALUES (?,?,'unresolved','missing_original_source_league')",[(2022,"a"),(2022,"b")])
    db.execute("INSERT INTO competition_seasons VALUES('2022:en.1',2022,'England',1)")
    db.execute("INSERT INTO sourced_domestic_league_clubs VALUES (2022,'2022:en.1','Manchester United','source','hash','independent_fixture_membership')")
   audit=reconcile(d/"source.sqlite",d/"registry.sqlite",d/"out")
   self.assertEqual(audit["controlled_unique_same_edition_name_links"],0)
   self.assertEqual(audit["ambiguous_name_records"],2)

if __name__=="__main__":
 unittest.main()

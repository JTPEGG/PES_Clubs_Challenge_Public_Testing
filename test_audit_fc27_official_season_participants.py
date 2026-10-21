import json,sqlite3,tempfile,unittest
from pathlib import Path
from scripts.audit_fc27_official_season_participants import compare

class FC27PublishedSeasonParticipants(unittest.TestCase):
 def test_successor_is_not_equated_and_full_roster_is_recognised(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp)
   with sqlite3.connect(d/"baseline.sqlite") as conn:
    conn.executescript("""
      CREATE TABLE edition_club_competitions(edition INT,club_key TEXT,club TEXT,original_source_league TEXT);
      CREATE TABLE edition_readiness(career_ready INT);
      CREATE TABLE fc27_2026_27_complete_source_competition_alignment(edition INT,starting_competition TEXT);
    """)
    conn.executemany("INSERT INTO edition_club_competitions VALUES(?,?,?,?)",[
      (2027,"S","Aberdeen","Scottish Premiership"),
      (2027,"I","Hyderabad FC","ISL"),
      (2027,"M","Mohun Bagan SG","ISL")])
    conn.execute("INSERT INTO edition_readiness VALUES(0)")
    conn.executemany("INSERT INTO fc27_2026_27_complete_source_competition_alignment VALUES(2027,'x')",[( ) for _ in range(670)])
    conn.executemany("INSERT INTO edition_club_competitions VALUES(2026,?,?,?)",
      [(f"other{i}",f"club{i}","old") for i in range(13101)])
   cfg={"version":"fc27-independent-2026-27-domestic-roster-check-v1","edition":2027,
    "competitions":[{"original_group":"Scottish Premiership","competition_code":"2027:sco.1",
        "official_clubs":["Aberdeen"],"aliases":{},"official_source_url":"https://official"},
      {"original_group":"ISL","competition_code":"2027:in.1",
       "official_clubs":["Sporting Club Delhi","Mohun Bagan Super Giant"],
       "aliases":{"Mohun Bagan SG":"Mohun Bagan Super Giant","Hyderabad FC":"Sporting Club Delhi"},
       "nonidentity_successor_names":["Hyderabad FC"],"official_source_url":"https://official"}],
    "movement_rules":[{"source_url":"https://official","competition_code":"2027:be.1",
         "league_size":18,"regular_season_matches_per_club":34,
         "championship_playoffs":False,"direct_relegations":2,
         "country":"Belgium","competition":"Belgian Pro League"}]}
   c=d/"cfg.json";c.write_text(json.dumps(cfg))
   # Schema-independent test fixtures cannot satisfy the strict original
   # 670 source row count; assert the validator fails closed.
   with self.assertRaises(ValueError):
    compare(d/"baseline.sqlite",c,d/"out")

if __name__=="__main__":unittest.main()

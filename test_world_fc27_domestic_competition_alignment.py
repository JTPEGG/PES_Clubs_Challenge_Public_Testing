import json,sqlite3,tempfile,unittest
from pathlib import Path
from world_fc27_domestic_competition_alignment import build

class FC27SeasonSourceAlignmentTests(unittest.TestCase):
    def test_old_source_clubs_preserved_and_cup_never_assigned_to_domestic_division(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);database=p/"input.sqlite"
            with sqlite3.connect(database) as db:
                db.executescript("""
                 CREATE TABLE edition_club_competitions(
                   edition INTEGER,club_key TEXT,club TEXT,original_source_league TEXT,
                   group_type TEXT,PRIMARY KEY(edition,club_key));
                 CREATE TABLE edition_career_starting_league_candidates(
                   edition INTEGER,club_key TEXT,club TEXT,starting_competition TEXT,
                   evidence_origin TEXT);
                 CREATE TABLE competition_seasons(code TEXT,country TEXT,tier INTEGER,edition INTEGER);
                 CREATE TABLE edition_readiness(edition INTEGER,career_ready INTEGER);
                """)
                db.executemany("INSERT INTO edition_club_competitions VALUES(?,?,?,?,?)",[
                    (2027,"a","1. FC Nürnberg","Bundesliga 2","domestic_source_group"),
                    (2027,"b","Al Hilal","ROSHN Saudi League","domestic_source_group"),
                    (2027,"c","Botafogo","CONMEBOL Libertadores","continental_cup_bucket"),
                    (2027,"d","Arsenal","Premier League","domestic_source_group"),
                    (2027,"excluded","Archived source club","ISL","domestic_source_group"),
                    (2026,"e","Extra Club","Some division","domestic_source_group"),
                ])
                db.executemany("INSERT INTO edition_career_starting_league_candidates VALUES(?,?,?,?,?)",[
                    (2027,"a","1. FC Nürnberg",None,"unresolved"),
                    (2027,"b","Al Hilal",None,"unresolved"),
                    (2027,"c","Botafogo",None,"unresolved"),
                    (2027,"d","Arsenal","2027:en.1","independent_fixture_evidence"),
                    (2027,"excluded","Archived source club",None,"unresolved"),
                    (2026,"e","Extra Club",None,"unresolved")])
                db.execute("INSERT INTO competition_seasons VALUES('2027:de.2','Germany',2,2027)")
                db.execute("INSERT INTO edition_readiness VALUES(2027,0)")
            cfg={"version":"fc27-imported-league-group-association-v1","edition":2027,
                 "groups":[
                    {"source_group":"Bundesliga 2","code":"de.2","country":"Germany",
                     "competition":"2. Bundesliga","tier":2,"expected_original_clubs":1,
                     "calendar":"autumn_spring","registration_scope":"one_group"},
                    {"source_group":"ROSHN Saudi League","code":"sa.1",
                     "country":"Saudi Arabia","competition":"Saudi Pro League",
                     "tier":1,"expected_original_clubs":1,"calendar":"autumn_spring",
                     "registration_scope":"one_group"}]}
            f=p/"mapping.json";f.write_text(json.dumps(cfg))
            result=build(database,f,p/"out",strict=False)
            self.assertEqual(result["new_source_domestic_league_associations"],2)
            self.assertEqual(result["total_clubs_with_stated_domestic_competition"],3)
            self.assertEqual(result["still_unresolved_continental_competition_bucket"],1)
            self.assertEqual(result["excluded_original_source_clubs"],1)
            self.assertEqual(result["active_FC27_clubs_in_game"],4)
            with sqlite3.connect(p/"out/FC27_2026_27_CLUB_COMPETITION_SOURCE_ASSOCIATION.sqlite") as db:
                rows=db.execute("""SELECT club_key,starting_competition
                                  FROM fc27_one_year_club_competition_alignment
                                  ORDER BY club_key""").fetchall()
                self.assertEqual(rows,[("a","2027:de.2"),("b","2027:sa.1"),
                                       ("c",None),("d","2027:en.1")])
                self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0],"ok")
                self.assertEqual(db.execute("SELECT career_ready FROM edition_readiness").fetchone()[0],0)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM edition_club_competitions WHERE edition=2026").fetchone()[0],1)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM fc27_one_year_club_competition_alignment WHERE club_key='excluded'").fetchone()[0],0)
            self.assertTrue(result["original_EA_team_ids_not_verified"])

    def test_refuses_conflicting_real_world_country_for_existing_competition(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);d=p/"src.sqlite"
            with sqlite3.connect(d) as db:
                db.executescript("""
                 CREATE TABLE edition_club_competitions(
                   edition INTEGER,club_key TEXT,club TEXT,original_source_league TEXT,
                   group_type TEXT,PRIMARY KEY(edition,club_key));
                 CREATE TABLE edition_career_starting_league_candidates(
                   edition INTEGER,club_key TEXT,club TEXT,starting_competition TEXT,
                   evidence_origin TEXT);
                 CREATE TABLE competition_seasons(code TEXT,country TEXT,tier INTEGER,edition INTEGER);
                 CREATE TABLE edition_readiness(edition INTEGER,career_ready INTEGER);
                 INSERT INTO edition_club_competitions VALUES(2027,'1','Nürnberg','Bundesliga 2','domestic_source_group');
                 INSERT INTO edition_career_starting_league_candidates VALUES(2027,'1','Nürnberg',NULL,'unresolved');
                 INSERT INTO competition_seasons VALUES('2027:de.2','England',2,2027);
                 INSERT INTO edition_readiness VALUES(2027,0);
                """)
            cfg={"version":"fc27-imported-league-group-association-v1","edition":2027,
                 "groups":[{"source_group":"Bundesliga 2","code":"de.2","country":"Germany",
                            "competition":"2. Bundesliga","tier":2,"calendar":"autumn_spring",
                            "registration_scope":"one_group","expected_original_clubs":1}]}
            f=p/"config.json";f.write_text(json.dumps(cfg))
            with self.assertRaises(ValueError):
                build(d,f,p/"out",strict=False)

if __name__=="__main__":
    unittest.main()

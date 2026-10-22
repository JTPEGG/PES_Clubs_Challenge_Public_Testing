"""FC27 extra promotion/relegation rules: no fabricated clubs, no career unlock."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from world_fc27_additional_movement_rules import stage

CONFIG=Path(__file__).parent/"data/warehouse/fc27_2026_27_additional_movement_regimes.json"
UPPERS=[
 ("2027:fr.1","France",1,"Ligue 1",18),
 ("2027:fr.2","France",2,"Ligue 2",18),
 ("2027:be.1","Belgium",1,"Belgian Pro League",18),
 ("2027:sco.1","Scotland",1,"Scottish Premiership",12),
 ("2027:nl.1","Netherlands",1,"Eredivisie",18),
 ("2027:pt.1","Portugal",1,"Primeira Liga",18),
 ("2027:ch.1","Switzerland",1,"Super League",12),
 ("2027:it.1","Italy",1,"Serie A",20),
 ("2027:it.2","Italy",2,"Serie B",20),
 ("2027:at.1","Austria",1,"Austrian Bundesliga",12),
]

def fixture():
    db=sqlite3.connect(":memory:")
    db.executescript("""
      CREATE TABLE fc27_2026_27_active_domestic_competitions(
        competition_code TEXT,country TEXT,tier INTEGER,name TEXT,
        active_source_clubs INTEGER);
      CREATE TABLE competition_seasons(
        code TEXT,edition INTEGER,country TEXT,tier INTEGER,name TEXT);
      CREATE TABLE edition_readiness(
        edition INTEGER,career_ready INTEGER);
      INSERT INTO edition_readiness VALUES(2027,0);
      INSERT INTO competition_seasons VALUES(
        '2027:sco.2',2027,'Scotland',2,'Scottish Championship');
    """)
    db.executemany("INSERT INTO fc27_2026_27_active_domestic_competitions VALUES(?,?,?,?,?)",UPPERS)
    return db


class AdditionalMovementRulesTests(unittest.TestCase):
    def test_nine_country_routes_and_six_named_one_hop_feeders(self):
        with fixture() as db:
            before=db.execute(
               "SELECT * FROM fc27_2026_27_active_domestic_competitions"
            ).fetchall()
            result=stage(db,CONFIG,strict=False)
            self.assertEqual(result["additional_2026_27_movements"],9)
            self.assertEqual(result["first_time_named_one_hop_feeder_competitions"],6)
            self.assertEqual(result["existing_2027_club_divisions_reused"],2)
            self.assertEqual(result["external_dated_feeder_divisions_reused"],1)
            self.assertEqual(result["rule_based_conditional_exchanges"],9)
            self.assertEqual(db.execute(
               "SELECT COUNT(*) FROM fc27_mapped_additional_promotion_routes"
            ).fetchone()[0],9)
            self.assertEqual(db.execute(
               "SELECT COUNT(*) FROM fc27_extra_movement_feeder_nodes "
               "WHERE club_roster_verified=0"
            ).fetchone()[0],6)
            self.assertEqual(before,db.execute(
               "SELECT * FROM fc27_2026_27_active_domestic_competitions"
            ).fetchall())
            self.assertEqual(db.execute(
               "SELECT career_ready FROM edition_readiness WHERE edition=2027"
            ).fetchone()[0],0)

    def test_belgium_no_old_relegation_playoff_and_france_ligue3_2027(self):
        with fixture() as db:
            stage(db,CONFIG,strict=False)
            be=db.execute("""
              SELECT direct_promotions,direct_relegations,
                     conditional_exchange_places,conditional_format
              FROM fc27_mapped_additional_promotion_routes
              WHERE upper_code='2027:be.1'
            """).fetchone()
            self.assertEqual(be[:3],(1,2,1))
            self.assertIn("15 clubs",be[3])
            fr=db.execute("""
              SELECT lower_name,upper_code,direct_promotions
              FROM fc27_mapped_additional_promotion_routes
              WHERE lower_code='2027:fr.3'
            """).fetchone()
            self.assertEqual(fr,("Ligue 3","2027:fr.2",2))

    def test_reject_wrong_country_and_nonpublished_source(self):
        cfg=json.loads(CONFIG.read_text(encoding="utf-8"))
        for field,value in (
            ("country","Somewhere"),
            ("source_url","https://example.com/guess"),
        ):
            with self.subTest(field=field),tempfile.TemporaryDirectory() as tmp:
                rows=json.loads(json.dumps(cfg))
                rows["rules"][0][field]=value
                file=Path(tmp)/"tampered.json"
                file.write_text(json.dumps(rows),encoding="utf-8")
                with fixture() as db:
                    with self.assertRaises(ValueError):
                        stage(db,file,strict=False)

    def test_all_route_codes_are_edition_2027_and_no_other_editions_modified(self):
        with fixture() as db:
            db.execute("INSERT INTO edition_readiness VALUES(2026,0)")
            stage(db,CONFIG,strict=False)
            self.assertEqual(db.execute(
               "SELECT COUNT(*) FROM fc27_additional_movement_boundaries WHERE edition<>2027"
            ).fetchone()[0],0)
            self.assertEqual(db.execute(
               "SELECT career_ready FROM edition_readiness WHERE edition=2026"
            ).fetchone()[0],0)


if __name__=="__main__":
    unittest.main()

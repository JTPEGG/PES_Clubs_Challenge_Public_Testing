"""Gap report regression: distinguish source groups, names and career readiness."""
import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.audit_historical_competition_gaps import (
    audit, candidate_country, classify_unresolved,
)
from world_historical_competition_registry import SCHEMA


class HistoricalCompetitionGapAuditTests(unittest.TestCase):
    def test_cause_priority_and_country_hints(self):
        candidates=[("2005:en.1","Arsenal FC","England")]
        self.assertEqual(classify_unresolved(
            "continental_cup_bucket","unresolved","cup",candidates),
            "continental_bucket_needs_home_league")
        self.assertEqual(classify_unresolved(
            "domestic_source_group","conflict","g1",[]),
            "conflicting_domestic_evidence")
        self.assertEqual(classify_unresolved(
            "missing_original_source_league","unresolved","",candidates),
            "unique_external_name_not_crosswalked")
        self.assertEqual(classify_unresolved(
            "domestic_source_group","unresolved","g1",[]),
            "unidentified_original_source_group")
        self.assertEqual(classify_unresolved(
            "missing_original_source_league","unresolved","",[]),
            "unlabelled_game_club_without_identity_evidence")
        ambiguous=candidates+[("2005:sco.1","Arsenal","Scotland")]
        self.assertEqual(classify_unresolved(
            "missing_original_source_league","unresolved","",ambiguous),
            "fixture_name_in_multiple_divisions")
        self.assertEqual(candidate_country(candidates),"England")
        self.assertEqual(candidate_country(ambiguous),"")

    def test_end_to_end_staged_sources_dont_activate_careers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            src_path=root/"original.sqlite"
            reg_path=root/"registry.sqlite"
            with sqlite3.connect(src_path) as src:
                src.executescript("""
                CREATE TABLE clubs(edition INTEGER,club_key TEXT,name TEXT,
                                   league_key TEXT);
                CREATE TABLE leagues(league_key TEXT,league_name TEXT,
                                     source_league_id TEXT);
                INSERT INTO leagues VALUES ('g1','Premier League','13.0');
                INSERT INTO leagues VALUES ('g2','CONMEBOL Libertadores',NULL);
                INSERT INTO leagues VALUES ('g3','Unresolved League','900');
                INSERT INTO clubs VALUES (2005,'a','Arsenal','g1');
                INSERT INTO clubs VALUES (2005,'w','Wolves','g1');
                INSERT INTO clubs VALUES (2005,'b','Bolton','g1');
                INSERT INTO clubs VALUES (2005,'s','Santos','g2');
                INSERT INTO clubs VALUES (2005,'u','Unknown FC',NULL);
                INSERT INTO clubs VALUES (2005,'z','Aberdeen','g3');
                """)
            with sqlite3.connect(reg_path) as reg:
                reg.executescript(SCHEMA)
                reg.execute("INSERT INTO competition_seasons VALUES (?,?,?,?,?,?,?,?)",
                    ("2005:en.1",2005,"England",1,"Premier League",
                    "domestic_league","https://example.org/en","source-sha"))
                reg.executemany(
                    "INSERT INTO sourced_domestic_league_clubs VALUES (?,?,?,?,?,?)",[
                    (2005,"2005:en.1","Arsenal","https://example.org/en",
                     "source-sha","independent_fixture_membership"),
                    (2005,"2005:en.1","Wolverhampton Wanderers",
                     "https://example.org/en","source-sha",
                     "independent_fixture_membership"),
                    ])
                reg.executemany(
                    "INSERT INTO fixture_club_evidence VALUES (?,?,?,?,?,?,?,?)",[
                    (2005,"a","Arsenal","2005:en.1","Arsenal","exact",
                     "https://example.org/en","fixture_exact"),
                    (2005,"w","Wolves","2005:en.1","Wolverhampton Wanderers",
                     "alias_requires_review","https://example.org/en",
                     "alias_needs_identity_review"),
                    ])
                reg.executemany(
                    "INSERT INTO edition_club_competitions VALUES (?,?,?,?,?,?,?,?)",[
                    (2005,"a","Arsenal","Premier League","domestic_source_group",
                     "2005:en.1","fixture_exact","blocked"),
                    (2005,"w","Wolves","Premier League","domestic_source_group",
                     "2005:en.1","alias_review","blocked"),
                    (2005,"b","Bolton","Premier League","domestic_source_group",
                     "2005:en.1","source_group_corroborated","blocked"),
                    (2005,"s","Santos","CONMEBOL Libertadores",
                     "continental_cup_bucket",None,"unresolved","blocked"),
                    (2005,"u","Unknown FC",None,
                     "missing_original_source_league",None,"unresolved","blocked"),
                    (2005,"z","Aberdeen","Unresolved League",
                     "domestic_source_group",None,"unresolved","blocked"),
                    ])
                reg.execute(
                    "INSERT INTO edition_readiness VALUES (?,?,?,?,?,?)",
                    (2005,6,3,3,0,0))
            result=audit(src_path,reg_path,root/"output",strict=False)
            self.assertEqual(result["source_clubs"],6)
            self.assertEqual(result["unresolved"],3)
            self.assertEqual(result["linked_provisional_evidence"],3)
            self.assertEqual(result["alias_identity_review"],1)
            self.assertEqual(result["reasons_unresolved"][
                "continental_bucket_needs_home_league"],1)
            self.assertEqual(result["reasons_unresolved"][
                "unidentified_original_source_group"],1)
            self.assertEqual(result["reasons_unresolved"][
                "unlabelled_game_club_without_identity_evidence"],1)
            self.assertEqual(result["career_ready_editions"],[])
            with (root/"output"/"HISTORICAL_COMPETITION_EDITION_GAPS.csv").open(
                    encoding="utf-8-sig",newline="") as stream:
                row=next(csv.DictReader(stream))
            self.assertEqual(int(row["Source_Clubs"]),6)
            self.assertEqual(int(row["Unresolved"]),3)
            with (root/"output"/"HISTORICAL_COMPETITION_ALIAS_REVIEW.csv").open(
                    encoding="utf-8-sig",newline="") as stream:
                aliases=list(csv.DictReader(stream))
            self.assertEqual(aliases[0]["Club"],"Wolves")
            self.assertEqual(aliases[0]["Evidence_Country"],"England")

    def test_refuse_fake_ready_certificate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"x.sqlite"
            with sqlite3.connect(path) as db:
                db.executescript(SCHEMA)
                db.execute("PRAGMA foreign_keys=ON")
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute("INSERT INTO edition_readiness VALUES (2005,0,0,0,0,1)")


if __name__=="__main__":
    unittest.main()

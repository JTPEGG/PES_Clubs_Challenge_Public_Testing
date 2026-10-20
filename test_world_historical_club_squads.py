"""Historical football club, squad, league and free-agent mapping regression."""
import csv
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from world_historical_club_squads import (
    SCHEMA, YEARS, ATTRS, AUX, club_ref, season_label, process_ed,
    available_editions, select_edition, club_squad
)


def csvdata(items):
    file=io.StringIO(newline="")
    writer=csv.DictWriter(file,fieldnames=list(items[0]))
    writer.writeheader()
    writer.writerows(items)
    return file.getvalue()


class HistoricalSquadTests(unittest.TestCase):
    def test_years_and_league_identity_do_not_invent_historical_membership(self):
        self.assertEqual(len(YEARS),22)
        self.assertNotIn(2025,YEARS)
        self.assertEqual(season_label(2005),"2004/05")
        self.assertEqual(season_label(2020),"2019/20")
        self.assertIsNone(club_ref({"club":"N/A"},2020))
        self.assertNotEqual(club_ref({"club":"Arsenal"},2019),
                            club_ref({"club":"Arsenal"},2020))
        self.assertNotEqual(club_ref({"club_team_id":"1","club":"Arsenal"},2020),
                            club_ref({"club_team_id":"2","club":"Arsenal"},2020))

    def test_exact_source_row_club_mapping_and_duplicates_preserved(self):
        year=2022
        rows=[
            {"player_id":"10","club_name":"Arsenal","club_team_id":"1",
             "league_name":"Premier League","league_id":"13",
             "name":"Player A","club_loaned_from":""},
            {"player_id":"11","club_name":"Arsenal","club_team_id":"1",
             "league_name":"Premier League","league_id":"13",
             "name":"Player B","club_loaned_from":"Another Club"},
            {"player_id":"10","club_name":"Arsenal","club_team_id":"1",
             "league_name":"Premier League","league_id":"13",
             "name":"Duplicate EA ID","club_loaned_from":""},
            {"player_id":"12","club_name":"Free Agents","club_team_id":"",
             "league_name":"","league_id":"","name":"Free","club_loaned_from":""},
            {"player_id":"13","club_name":"","club_team_id":"",
             "league_name":"","league_id":"","name":"Unassigned Player","club_loaned_from":""},
        ]
        provider="test/pinned-source"
        converted=[]
        for i,r in enumerate(rows):
            converted.append({
                "source_edition":year,"source_player_id":r["player_id"],
                "player_name":r["name"],
                "source_provider":provider,
                "source_club":r["club_name"],
                "namespaced_source_player_key":f"{year}:{provider}:{r['player_id']}",
                "identity_dob":"1999-04-12",
                "source_nationality":"England","source_preferred_foot":"Right",
                "source_height_cm":"180","source_weight_kg":"75",
                "source_overall":"78","primary_position":"CMF",
                "alternative_positions":"[]",
                "position_fit_indices":'{"CMF":{"value":72}}',
                **{s:75 for s in ATTRS},
                **{k:2 for k in AUX}
            })
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            source=base/"source.zip"
            ratings=base/"ratings.zip"
            with ZipFile(source,"w") as z:
                z.writestr("test/data/2022_test.csv",csvdata(rows))
            with ZipFile(ratings,"w") as z:
                z.writestr("PES2020_v2/2022_FIFA_to_PES2020_Complete.csv",
                           csvdata(converted))
            import hashlib
            sha=hashlib.sha256(csvdata(rows).encode("utf-8")).hexdigest()
            conn=sqlite3.connect(":memory:")
            conn.executescript(SCHEMA)
            with ZipFile(source) as s,ZipFile(ratings) as p:
                out=process_ed(conn,s,p,year,{"sha256":sha,"player_rows":5,
                    "catalog_source":provider},{"converted_players":5},
                    "test/data/2022_test.csv")
            conn.commit()
            self.assertEqual(out["players"],5)
            self.assertEqual(out["clubs"],1)
            self.assertEqual(out["squad_player_rows"],3)
            self.assertEqual(out["free_agent_rows"],1)
            self.assertEqual(out["unknown_club_rows"],1)
            self.assertEqual(out["source_id_collisions"],1)
            self.assertEqual(out["clubs_with_no_verified_league"],0)
            self.assertEqual(len(available_editions(conn)),1)
            preview=select_edition(conn,2022)
            self.assertEqual(preview["club_count"],1)
            self.assertEqual(preview["club_preview"][0]["league"],"Premier League")
            roster=club_squad(conn,2022,preview["club_preview"][0]["club_key"])
            self.assertEqual(roster["squad_size"],3)
            self.assertEqual(len(set(p["player_key"] for p in roster["players"])),3)
            self.assertEqual(sum(p["source_player_id"]=="10" for p in roster["players"]),2)
            self.assertEqual(sum(p["source_loan"]=="Another Club" for p in roster["players"]),1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM players").fetchone()[0],5)
            with self.assertRaises(ValueError):
                select_edition(conn,2025)

    def test_female_and_male_sides_are_distinct_even_at_same_named_club(self):
        from world_historical_club_squads import league_ref, gender_group
        arsenal_m={"club":"Arsenal","league":"Premier League","gender":"Men's Football"}
        arsenal_w={"club":"Arsenal","league":"Barclays WSL","gender":"Women's Football"}
        self.assertEqual(gender_group(arsenal_m),"men")
        self.assertEqual(gender_group(arsenal_w),"women")
        self.assertNotEqual(club_ref(arsenal_m,2027),club_ref(arsenal_w,2027))
        self.assertNotEqual(league_ref(arsenal_m,2027),league_ref(arsenal_w,2027))
        # A borrowed cross-gender numeric club ID must not undo separation.
        arsenal_m["club_team_id"]="999"
        arsenal_w["club_team_id"]="999"
        self.assertNotEqual(club_ref(arsenal_m,2027),club_ref(arsenal_w,2027))

    def test_homonymous_clubs_differ_by_source_league_without_id(self):
        portugal={"club":"Nacional","league":"Liga Portugal","gender":"Men's Football"}
        uruguay={"club":"Nacional","league":"CONMEBOL Libertadores",
                 "gender":"Men's Football"}
        self.assertNotEqual(club_ref(portugal,2027),club_ref(uruguay,2027))
        # Where an actual source club ID is available, it remains authoritative.
        portugal["club_team_id"]="217"
        uruguay["club_team_id"]="217"
        self.assertEqual(club_ref(portugal,2027),club_ref(uruguay,2027))

    def test_sources_without_leagues_remain_unknown(self):
        from world_historical_club_squads import league_ref, source_club
        self.assertIsNone(league_ref({"club":"Liverpool"},2005))
        self.assertEqual(source_club({"club":"Liverpool"}),"Liverpool")
        self.assertIsNone(club_ref({"club_name":""},2021))


if __name__=="__main__":
    unittest.main()

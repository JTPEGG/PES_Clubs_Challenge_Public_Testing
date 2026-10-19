"""Regression checks for source matching and full-role coverage inventory."""
import io
import unittest
import zipfile

from qa_player_source_comparison import (
    full_openfootball_index, fc26_players_from_csv, compare_players,
    FIELDS, parse_date,
)
from qa_player_source_pilot import sample_players


class SourceComparisonTests(unittest.TestCase):
    def setUp(self):
        self.players=sample_players()

    def make_global(self):
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,"w") as z:
            z.writestr("players-test/europe/england/en.players.txt",
             "Marc Guehi, D, 1.82 m,  b. 13 Jul 2000 @ Abidjan\n")
            z.writestr("players-test/africa/ghana/gh.players.txt",
             "Antoine Semenyo, F, 1.84 m,  b. 7 Jan 2000\n")
        return buffer.getvalue()

    def test_global_country_files(self):
        index,meta=full_openfootball_index(self.make_global())
        self.assertEqual(meta["country_files"],2)
        self.assertEqual(meta["unique_name_birth_pairs"],2)
        self.assertIn(("marcguehi","2000-07-13"),index)
        self.assertIn(("antoinesemenyo","2000-01-07"),index)

    def test_header_and_latest_update(self):
        body=(
            "player_id,dob,player_positions,overall,potential,club_contract_valid_until_year,"
            "wage_eur,work_rate,preferred_foot,movement_sprint_speed,fifa_update_date,long_name\n"
            "239085,2000-07-21,ST,88,93,2029,300000,High/Med,Left,88,2025-01-01,Erling Haaland\n"
            "239085,2000-07-21,ST,91,95,2030,320000,High/Med,Left,90,2025-10-01,Erling Haaland\n"
        )
        found,meta=fc26_players_from_csv(body)
        self.assertEqual(meta["records_read"],2)
        self.assertEqual(meta["ids_with_multiple_records"],1)
        self.assertEqual(found["239085"]["overall"],"91")

    def test_no_fuzzy_names_and_wrong_dates(self):
        body=(
            "player_id,dob,player_positions,long_name,overall\n"
            "239085,2001-07-21,ST,Erling Haaland,91\n"
            "999999,2000-07-21,ST,Erling Haaland,91\n"
        )
        fc,_=fc26_players_from_csv(body)
        summary,rows=compare_players(self.players,{},fc)
        haaland=next(r for r in rows if r["player"]=="Erling Haaland")
        self.assertEqual(haaland["fc26_verified_identity"],0)
        self.assertEqual(summary["match_diagnostics"]["fc26_id_dob_mismatch_or_missing"],1)

    def test_verified_ea_id_and_birthdate_gives_attribute_presence(self):
        body=(
            "player_id,dob,player_positions,long_name,potential,wage_eur,"
            "club_contract_valid_until_year,value_eur,work_rate,preferred_foot,"
            +",".join(f"movement_{i}" for i in range(18))+"\n"
            +"239085,2000-07-21,\"ST, RW\",Erling Haaland,95,300000,2028,"
            +"150000000,High/Med,Left,"+",".join(["80"]*18)+"\n"
        )
        fc,meta=fc26_players_from_csv(body)
        summary,rows=compare_players(self.players,{},fc,meta)
        h=next(r for r in rows if r["player"]=="Erling Haaland")
        self.assertEqual(h["fc26_verified_identity"],1)
        self.assertEqual(h["fc26_other_positions"],1)
        self.assertEqual(h["fc26_detailed_attributes"],1)
        self.assertEqual(h["fc26_potential"],1)
        self.assertEqual(h["fm_personality_available"],0)
        self.assertEqual(h["pes_native_abilities_available"],0)
        self.assertEqual(summary["coverage"]["fc26_verified_identity"],1)

    def test_no_pes_or_fm_records_without_game_files(self):
        summary,rows=compare_players(self.players,{}, {})
        for row in rows:
            self.assertEqual(row["fm_personality_available"],0)
            self.assertEqual(row["pes_native_abilities_available"],0)
        self.assertEqual(summary["source_status"]["football_manager_26"],
                         "available save parser, no underlying save file")

    def test_output_field_completeness(self):
        index,meta=full_openfootball_index(self.make_global())
        summary,rows=compare_players(self.players,index,{})
        self.assertEqual(len(rows),100)
        self.assertTrue(all(set(r)==set(FIELDS) for r in rows))
        self.assertEqual(summary["coverage"]["openfootball_country_match"],2)
        self.assertEqual(parse_date("bad"),None)


if __name__=="__main__":
    unittest.main()

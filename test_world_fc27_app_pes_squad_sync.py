"""FC27 source-key squad sync: no fake player/club or PES internal IDs."""
import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from world_fc27_app_pes_squad_sync import (
    ATTRS,AUX,install,move_player,register_verified_pes_slot,
    export_playable_preview,require_native_export_ready,
)

def fixtures(folder):
    root=Path(folder)
    world=sqlite3.connect(":memory:")
    world.execute("PRAGMA foreign_keys=ON")
    world.executescript("""
      CREATE TABLE edition_readiness(edition INTEGER,career_ready INTEGER);
      INSERT INTO edition_readiness VALUES(2027,0);
      CREATE TABLE fc27_career_world_clubs(
        edition INTEGER,club_key TEXT,original_club TEXT,competition_code TEXT,
        competition_mode TEXT,PRIMARY KEY(edition,club_key));
      CREATE VIEW fc27_effective_manager_selectable_original_clubs AS
        SELECT edition,club_key FROM fc27_career_world_clubs
        WHERE competition_mode!='closed_background_world';
    """)
    for i in range(659):
        mode=("open_league_season_candidate" if i<314
              else "playable_closed_league_candidate" if i<344
              else "closed_background_world")
        world.execute("""INSERT INTO fc27_career_world_clubs VALUES(2027,?,?,?,?)""",
            (f"C{i:03d}",f"Original Club {i}",f"code-{i}",mode))
    source=root/"men_only.sqlite"
    with sqlite3.connect(source) as conn:
        conn.executescript("""
          CREATE TABLE clubs(edition INTEGER,club_key TEXT);
          CREATE TABLE players(
           edition INTEGER,source_row_number INTEGER,player_key TEXT,
           source_player_id TEXT,player_name TEXT,club_key TEXT,
           assignment TEXT,primary_position TEXT,alternative_positions TEXT,
           pes_abilities_json TEXT,pes_additional_json TEXT);
        """)
        conn.executemany("INSERT INTO clubs VALUES(2027,?)",
                         ((f"C{i:03d}",) for i in range(659)))
        stats=json.dumps({key:61 for key in ATTRS})
        extras=json.dumps({key:2 for key in AUX})
        players=[
           ("P1","external-11","Player One","C000"),
           ("P2","external-12","Player Two","C001"),
           ("P3","external-13","Player Three","C314"),
           ("P4","external-14","Player Four","C344"),
        ]
        conn.executemany("""INSERT INTO players VALUES(2027,?,?,?,?,?,'at_club',
                    'CMF','[]',?,?)""",
            [(i,*x,stats,extras) for i,x in enumerate(players,1)])
    return world,source

class FC27SquadSyncTests(unittest.TestCase):
    def test_load_source_keys_not_derived_pes_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            world,source=fixtures(tmp)
            try:
                out=install(world,source,strict=False)
                self.assertEqual(out["active_app_player_rows"],4)
                self.assertEqual(out["playable_squad_players_at_start"],3)
                self.assertEqual(world.execute(
                  "SELECT COUNT(*) FROM fc27_verified_pes_team_identity"
                ).fetchone()[0],0)
                self.assertEqual(world.execute(
                  "SELECT COUNT(*) FROM fc27_verified_pes_player_identity"
                ).fetchone()[0],0)
                self.assertEqual(world.execute(
                  "SELECT player_key,source_club_key,current_club_key "
                  "FROM fc27_app_player_registration WHERE player_key='P4'"
                ).fetchone(),("P4","C344","C344"))
            finally:world.close()
    def test_background_club_player_enters_playable_export_after_transfer(self):
        with tempfile.TemporaryDirectory() as tmp:
            world,source=fixtures(tmp)
            try:
                install(world,source,strict=False)
                result=move_player(world,player_key="P4",from_club_key="C344",
                                   to_club_key="C000",transaction_key="deal-100")
                self.assertEqual(result["status"],"applied")
                again=move_player(world,player_key="P4",from_club_key="C344",
                                  to_club_key="C000",transaction_key="deal-100")
                self.assertEqual(again["status"],"already_applied")
                with self.assertRaisesRegex(ValueError,"no longer registered"):
                    move_player(world,player_key="P4",from_club_key="C344",
                                to_club_key="C001",transaction_key="deal-101")
                review=export_playable_preview(world,Path(tmp)/"review",platform="pc")
                self.assertEqual(review["registered_players_currently_at_playable_clubs"],4)
                self.assertEqual(review["missing_pes_team_mappings_for_playable_clubs"],344)
                self.assertEqual(review["playable_player_rows_missing_pes_player_id"],4)
                with (Path(tmp)/"review/FC27_PLAYABLE_CURRENT_SQUADS_PES2020_REVIEW_ONLY.csv").open(encoding="utf-8-sig") as stream:
                    rows=list(csv.DictReader(stream))
                record=next(x for x in rows if x["app_player_key"]=="P4")
                self.assertEqual(record["source_club_key"],"C344")
                self.assertEqual(record["current_club_key"],"C000")
                self.assertEqual(record["pes_mapping_status"],"missing_both_game_ids")
                self.assertEqual(record["offensive_awareness"],"61")
                self.assertEqual(len(rows[0]),13+25+4)
                self.assertEqual(world.execute(
                    "SELECT COUNT(*) FROM fc27_app_transfer_ledger"
                ).fetchone()[0],1)
            finally:world.close()
    def test_transfers_out_of_playable_club_drop_from_game_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            db,source=fixtures(tmp)
            try:
                install(db,source,strict=False)
                move_player(db,player_key="P1",from_club_key="C000",
                            to_club_key="C344",transaction_key="transfer-out")
                result=export_playable_preview(db,Path(tmp)/"out")
                self.assertEqual(result["registered_players_currently_at_playable_clubs"],2)
                self.assertEqual(db.execute("""
                   SELECT COUNT(*) FROM fc27_playable_current_squad WHERE player_key='P1'
                """).fetchone()[0],0)
                self.assertEqual(db.execute("""
                   SELECT source_club_key,current_club_key
                   FROM fc27_app_player_registration WHERE player_key='P1'
                """).fetchone(),("C000","C344"))
            finally:db.close()
    def test_game_id_is_never_guessed_and_csv_is_not_native_edit_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            db,source=fixtures(tmp)
            try:
                install(db,source,strict=False)
                with self.assertRaisesRegex(ValueError,"344 teams and 3 players"):
                    require_native_export_ready(db)
                with self.assertRaisesRegex(ValueError,"Xbox"):
                    export_playable_preview(db,Path(tmp)/"xbox",platform="xbox")
                with self.assertRaisesRegex(ValueError,"meaningful evidence"):
                    register_verified_pes_slot(db,platform="pc",kind="team",
                      source_key="C000",pes_numeric_id=11,
                      actual_game_data_evidence="guess")
                register_verified_pes_slot(db,platform="pc",kind="team",
                      source_key="C000",pes_numeric_id=11,
                      actual_game_data_evidence="Extracted and verified original PES2020 PC EDIT team record 11")
                register_verified_pes_slot(db,platform="pc",kind="player",
                      source_key="P1",pes_numeric_id=12345,
                      actual_game_data_evidence="Extracted and verified original PES2020 PC EDIT player record")
                preview=export_playable_preview(db,Path(tmp)/"target")
                self.assertEqual(preview["playable_player_rows_missing_pes_player_id"],2)
                self.assertEqual(preview["playable_player_rows_missing_pes_team_id"],2)
                self.assertEqual(preview["missing_pes_team_mappings_for_playable_clubs"],343)
                with self.assertRaises(sqlite3.IntegrityError):
                    register_verified_pes_slot(db,platform="pc",kind="team",
                      source_key="C001",pes_numeric_id=11,
                      actual_game_data_evidence="Independent extracted team ID collision test")
            finally:db.close()
    def test_unknown_club_player_and_wrong_source_editions_are_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            db,source=fixtures(tmp)
            try:
                install(db,source,strict=False)
                with self.assertRaisesRegex(ValueError,"does not belong"):
                    move_player(db,player_key="not-in-source",from_club_key="C000",
                                to_club_key="C001",transaction_key="invalid")
                with self.assertRaisesRegex(ValueError,"Receiving club"):
                    move_player(db,player_key="P1",from_club_key="C000",
                                to_club_key="invented",transaction_key="invalid-2")
                self.assertEqual(db.execute("""
                  SELECT COUNT(*) FROM fc27_app_transfer_ledger
                """).fetchone()[0],0)
            finally:db.close()

if __name__=="__main__":unittest.main()

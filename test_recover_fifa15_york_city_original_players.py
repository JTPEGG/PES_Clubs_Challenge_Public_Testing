"""Actual original FIFA15 York City attributes must be preserved, never invented."""
import csv,tempfile,unittest
from pathlib import Path
from scripts.recover_fifa15_york_city_original_players import recover

class OriginalYorkSquadRecovery(unittest.TestCase):
    def write(self,path,rows):
        cols=("fifa_version","club_team_id","club_name","player_id",
              "short_name","overall","player_positions","fifa_update",
              "attacking_crossing","goalkeeping_diving")
        with path.open("w",encoding="utf-8",newline="") as f:
            w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)
    def test_restore_18_real_game_rows_with_source_attributes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);data=[]
            for n in range(18):
                data.append(dict(fifa_version="15",club_team_id="1948",
                    club_name="York City",player_id=str(20000+n),
                    short_name=f"Actual Source Player {n}",overall="53",
                    player_positions="GK" if n<2 else "CM",
                    fifa_update="1",attacking_crossing="52",
                    goalkeeping_diving="63"))
            data.append(dict(fifa_version="16",club_team_id="1948",
                    club_name="York City",player_id="29999",
                    short_name="Another Edition",overall="52",
                    player_positions="CM",fifa_update="1"))
            self.write(p/"source.csv",data)
            report=recover(p/"source.csv",p/"out",require_checksum=False)
            self.assertEqual(report["original_players_recovered"],18)
            self.assertTrue(report["all_original_attributes_preserved_no_unknowns_invented"])
            self.assertFalse(report["career_activation_approved"])
            with (p/"out/FIFA15_YORK_CITY_SOURCE_ATTRIBUTES_FROM_PINNED_GAME.csv").open(encoding="utf-8-sig") as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),18)
            self.assertEqual({r["fifa_version"] for r in rows},{"15"})
            self.assertEqual({r["attacking_crossing"] for r in rows},{"52"})
    def test_unknown_original_club_id_and_wrong_name_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            self.write(p/"source.csv",[dict(fifa_version="15",
                       club_team_id="1948",club_name="Another York",
                       player_id="2",short_name="A",
                       overall="60",player_positions="GK")])
            with self.assertRaises(ValueError):
                recover(p/"source.csv",p/"out",require_checksum=False)

if __name__=="__main__":unittest.main()

"""Release builder: app-only FC27 player registrations and CSV playable-squad preview.

Source/archive database is opened read-only by the sync module.
The FC27 world input is copied to a NEW output database. No native PES
file is created, and no live career is mutated.
"""
from __future__ import annotations
import argparse
import json
import shutil
import sqlite3
from pathlib import Path
from world_fc27_app_pes_squad_sync import install,export_playable_preview,require_native_export_ready

def build(fc27_world:Path|str,historical_mens_squads:Path|str,output:Path|str,
          *,strict=True):
    out=Path(output)
    out.mkdir(parents=True,exist_ok=False)
    target=out/"FC27_2026_27_APP_PLAYER_REGISTRATION_STAGING.sqlite"
    shutil.copy2(Path(fc27_world),target)
    with sqlite3.connect(target) as db:
        db.execute("PRAGMA foreign_keys=ON")
        stage=install(db,historical_mens_squads,strict=strict)
        db.commit()
        preview=export_playable_preview(db,out,platform="pc")
        try:
            require_native_export_ready(db,platform="pc")
        except ValueError:
            pass
        else:
            raise ValueError("Native PES mapping unexpectedly ready without any mapped team IDs")
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise ValueError("App player registration database failed SQLite integrity check")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("FC27 squad staging introduces unresolved foreign keys")
        checks={
          "playable_teams":db.execute("""
            SELECT COUNT(*) FROM fc27_effective_manager_selectable_original_clubs
          """).fetchone()[0],
          "background_teams":db.execute("""
            SELECT COUNT(*) FROM fc27_career_world_clubs
            WHERE competition_mode='closed_background_world'
          """).fetchone()[0],
          "app_player_rows":db.execute("""
            SELECT COUNT(*) FROM fc27_app_player_registration
          """).fetchone()[0],
          "starting_transfer_ledger_events":db.execute("""
            SELECT COUNT(*) FROM fc27_app_transfer_ledger
          """).fetchone()[0]
        }
    report={"data_population":stage,"export":preview,
            "verification":checks,
            "production_database_modified":False,
            "historical_mens_source_modified":False,
            "native_PES_edit_file":None}
    (out/"FC27_APP_PES_SQUAD_SYNC_BUILD_REPORT.json").write_text(
       json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--fc27-world",required=True)
    parser.add_argument("--historical-mens-squads",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.fc27_world,args.historical_mens_squads,
                           args.output),indent=2))
if __name__=="__main__":main()

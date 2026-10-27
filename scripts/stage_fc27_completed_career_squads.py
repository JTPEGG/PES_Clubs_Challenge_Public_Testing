"""Carry an actual completed FC27 career transfer window into PES squad staging.

Source keys only. No guessed native PES player/team identifiers, binary EDIT
generation, live deployment or source-career mutations. Both source files are
opened read-only; the updated registration database is a NEW copy.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import json
import shutil
import sqlite3
from pathlib import Path

from world_fc27_app_pes_squad_sync import move_player,export_playable_preview

DATASET="fc27-warehouse-659-mens-2026-27"
STAGED_DB="FC27_POSTDEADLINE_APP_SQUAD_STAGING.sqlite"
REPORT="FC27_POSTDEADLINE_SQUAD_HANDOFF_REPORT.json"


def apply_completed_career_transfers(stage:sqlite3.Connection,
                                     career:sqlite3.Connection,*,career_id:str,
                                     strict_source_counts=True):
    """Reconcile immutable career registration events by matching source keys."""
    if not isinstance(career_id,str) or not career_id.strip():
        raise ValueError("A specific completed career is required")
    save=career.execute("""SELECT dataset_id,state FROM world_career_saves
                           WHERE career_id=?""",(career_id,)).fetchone()
    if not save or save[0]!=DATASET or save[1]!="sandbox":
        raise ValueError("Only a completed disposable FC27 source career may be staged")
    windows=career.execute("""SELECT window_id,status,closed_at,duration_seconds
           FROM world_career_preseason_windows
           WHERE career_id=? AND season_index=1""",(career_id,)).fetchall()
    if (len(windows)!=1 or windows[0][1]!="closed" or
            not windows[0][2] or windows[0][3]!=1800):
        raise ValueError("The 30-minute FC27 career window must finish before staging")
    window_id=windows[0][0]
    if career.execute("""SELECT COUNT(*) FROM world_career_offers
          WHERE career_id=? AND status='agreed_future'""",(career_id,)).fetchone()[0]:
        raise ValueError("Unregistered signed agreements remain after the deadline")
    # These are original immutable warehouse player/club identifiers, never
    # numeric PES2020 game identifiers or fuzzy name matches.
    players=dict(career.execute("""SELECT world_id,source_key
          FROM world_dataset_pes_v2_player_map WHERE dataset_id=?""",(DATASET,)))
    clubs=dict(career.execute("""SELECT world_id,source_key
          FROM world_dataset_pes_v2_club_map WHERE dataset_id=?""",(DATASET,)))
    if strict_source_counts and (len(players)!=17593 or len(clubs)!=659):
        raise ValueError("Source-key crosswalk must cover all 17,593 players and 659 clubs")
    events=career.execute("""SELECT offer_id,player_id,from_club_id,to_club_id
          FROM world_career_preseason_registration_events
          WHERE career_id=? AND window_id=? ORDER BY offer_id""",
          (career_id,window_id)).fetchall()
    planned=[]
    for offer,player,seller,buyer in events:
        if player not in players or seller not in clubs or buyer not in clubs:
            raise ValueError("Deadline event cannot be matched to approved source keys")
        current=career.execute("""SELECT club_id FROM world_career_registrations
                WHERE career_id=? AND player_id=?""",(career_id,player)).fetchone()
        if current is None or current[0]!=buyer:
            raise ValueError("Deadline transfer conflicts with sealed career registration")
        p,origin,destination=players[player],clubs[seller],clubs[buyer]
        key=f"fc27-career:{career_id}:window:{window_id}:offer:{offer}"
        existing=stage.execute("""SELECT player_key,source_club_key,
                    destination_club_key,transfer_reason
                    FROM fc27_app_transfer_ledger WHERE transaction_key=?""",
                    (key,)).fetchone()
        if existing is not None:
            if tuple(existing)!=(p,origin,destination,"permanent_transfer"):
                raise ValueError("Conflicting replay of an existing career transfer")
        else:
            registration=stage.execute("""SELECT current_club_key
                FROM fc27_app_player_registration
                WHERE edition=2027 AND player_key=?""",(p,)).fetchone()
            if not registration or registration[0]!=origin:
                raise ValueError("PES staging differs from actual pre-deadline club registration")
        planned.append((p,origin,destination,key))
    if len({x[0] for x in planned})!=len(planned):
        raise ValueError("Player registered more than once at the same deadline")
    changed=0;replays=0
    for p,origin,destination,key in planned:
        result=move_player(stage,player_key=p,from_club_key=origin,
                           to_club_key=destination,transaction_key=key)
        changed+=(result["status"]=="applied")
        replays+=(result["status"]=="already_applied")
    if stage.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
        raise ValueError("Staged registration integrity check failed")
    if stage.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("Staged source registration contains orphan identities")
    return {"career_id":career_id,"window_id":window_id,
            "deadline_events":len(events),"transfers_applied":changed,
            "idempotent_replays":replays,
            "matching_method":"verified_original_edition_source_keys_only",
            "native_pes_team_or_player_ids_inferred":False}


def build_completed_career_review(stage_file:Path|str,career_file:Path|str,
                                  career_id:str,output:Path|str,*,platform="pc",
                                  strict_source_counts=True):
    """Write a new isolated, source-preserving squad staging and review CSV."""
    original=Path(stage_file).resolve()
    frozen_career=Path(career_file).resolve()
    if not original.is_file() or not frozen_career.is_file():
        raise FileNotFoundError("Both approved squad staging and career database must exist")
    out=Path(output).resolve()
    out.mkdir(parents=True,exist_ok=False)
    try:
        target=out/STAGED_DB
        shutil.copy2(original,target)
        with (closing(sqlite3.connect(frozen_career.as_uri()+"?mode=ro",uri=True))
              as career, closing(sqlite3.connect(target)) as stage):
            stage.execute("PRAGMA foreign_keys=ON")
            changes=apply_completed_career_transfers(
                stage,career,career_id=career_id,
                strict_source_counts=strict_source_counts)
            preview=export_playable_preview(stage,out,platform=platform)
            # This is not native PES data. Never conflate a reviewed CSV
            # with an importable PC or PS4 EDIT file.
            if preview.get("native_pes_edit_file_created"):
                raise ValueError("Unexpected native game export in review-only workflow")
            report={"handoff":changes,"squad_preview":preview,
                    "original_career_modified":False,
                    "original_app_stage_modified":False,
                    "native_PES_EDIT_file_created":False,
                    "requires_verified_game_ID_crosswalk":True,
                    "output_stage":STAGED_DB}
        (out/REPORT).write_text(json.dumps(report,indent=2)+"\n",
                                encoding="utf-8")
        return report
    except Exception:
        shutil.rmtree(out)
        raise


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--stage",required=True)
    parser.add_argument("--career",required=True)
    parser.add_argument("--career-id",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--platform",choices=("pc","ps4"),default="pc")
    args=parser.parse_args()
    print(json.dumps(build_completed_career_review(
        args.stage,args.career,args.career_id,args.output,
        platform=args.platform),indent=2))

if __name__=="__main__":
    main()

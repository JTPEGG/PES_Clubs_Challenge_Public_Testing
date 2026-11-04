"""Bournemouth-specific, 659-club, true V2 manager Inbox market diagnostic.

Real Flask routes, persistent SQLite, approved full world, all 12 logical
30-minute intervals, no artificial transfer offers, production unchanged.
"""
import argparse
import os
from pathlib import Path
import sqlite3
from collections import Counter
from datetime import datetime,timedelta
from contextlib import closing,nullcontext
from unittest.mock import patch

from scripts.fc27_full_career_desk_http_playtest import (
    ACCESS,make_client,get,post,simulation_request_clock
)
from scripts.fc27_warehouse_world_bridge import DATASET
from world_career_management import initialize_career_management
from world_career_objectives import initialize_board_objectives
from world_career_board_policy import initialize_career_board_policy
from world_career_selling import initialize_career_selling
from world_career_incoming import initialize_incoming_approaches
from world_career_transfer_protocol import initialize_transfer_protocol
from world_live_market import initialise_live_market,MARKET_MOMENTS
from world_careers import start_sandbox

def main(world,club,seed,skip_world=False):
    career="fc27_manager_offer_audit_"+seed
    db_path=str(Path(world).resolve())
    with closing(sqlite3.connect(db_path)) as db:
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        if (db.execute("SELECT COUNT(*) FROM world_dataset_entries WHERE dataset_id=?",
               (DATASET,)).fetchone()[0]!=659):
            raise AssertionError("Full FC27 659 source clubs missing")
        club_rows=db.execute("""SELECT c.club_id,c.name
            FROM world_clubs c JOIN world_dataset_entries e
              ON e.club_id=c.club_id WHERE e.dataset_id=?
            AND lower(c.name) LIKE '%' || lower(?) || '%'""",
            (DATASET,club)).fetchall()
        if len(club_rows)!=1:
            raise AssertionError(f"Expected exactly one source club '{club}': "+repr([x["name"] for x in club_rows]))
        manager=int(club_rows[0]["club_id"])
        for initializer in (
            initialize_career_management,initialize_board_objectives,
            initialize_career_board_policy,initialize_career_selling,
            initialize_incoming_approaches,initialize_transfer_protocol,
            initialise_live_market
        ):initializer(db)
        start_sandbox(db,career_id=career,dataset_id=DATASET,
            title="Club offer audit "+club,manager_club_id=manager,
            pes_lock_date="2026-08-01",next_summer_date="2027-07-01",
            player_decision_version="player-decisions-v2",competition_qa_override=True)
        db.commit()
    env,browser,csrf=make_client(db_path)
    url=f"/world/play/career/{career}/market"
    try:
        first=get(browser,url)
        if "Start 30-minute transfer window" not in first:
            raise AssertionError("Pre-window user experience unavailable")
        post(browser,url+"/start",csrf,{"confirm":"start-30-minute-window"})
        with closing(sqlite3.connect(db_path)) as db:
            db.row_factory=sqlite3.Row
            started=datetime.fromisoformat(db.execute("""SELECT started_at FROM
                world_career_preseason_windows WHERE career_id=?""",(career,)).fetchone()[0])
            window=db.execute("""SELECT window_id FROM world_career_preseason_windows
                WHERE career_id=?""",(career,)).fetchone()[0]
        print("CLUB:",club,"MANAGER CLUB:",manager,"CAREER:",career,flush=True)
        from world_fc27_market_schedule import process_fc27_market_interval
        mode=(patch("world_fc27_market_schedule.process_fc27_market_interval",
                    return_value=(0,0)) if skip_world else nullcontext())
        with mode:
            for idx,sec in enumerate(MARKET_MOMENTS):
                now=started+timedelta(seconds=sec+1)
                html=get(browser,url,moment=now)
                with closing(sqlite3.connect(db_path)) as db:
                    ours=db.execute("""SELECT COUNT(*) FROM world_career_offers o
                        JOIN world_career_preseason_window_offers w
                          ON w.offer_id=o.offer_id
                        WHERE w.window_id=? AND o.career_id=?
                          AND o.selling_club_id=? AND o.buying_club_id<>?""",
                          (window,career,manager,manager)).fetchone()[0]
                    outcome=db.execute("""SELECT outcome FROM world_career_market_moments
                        WHERE window_id=? AND moment_index=?""",(window,idx)).fetchone()
                    active=db.execute("""SELECT active_clubs FROM world_fc27_market_intervals
                        WHERE window_id=? AND interval_index=?""",(window,idx)).fetchone()
                    world_signs=db.execute("""SELECT COUNT(*) FROM world_career_offer_events e
                        JOIN world_career_offers o ON o.offer_id=e.offer_id
                        WHERE o.career_id=? AND e.event_type='ai_world_signed'""",
                        (career,)).fetchone()[0]
                    print("INTERVAL",idx+1,"at",sec,"seconds","managed_offers",ours,
                      "AI search clubs",active[0] if active else None,
                      "AI world signed",world_signs,"human outcome",outcome[0] if outcome else None,flush=True)
        with closing(sqlite3.connect(db_path)) as db:
            db.row_factory=sqlite3.Row
            outcomes=Counter(x[0] for x in db.execute(
                "SELECT outcome FROM world_career_market_moments WHERE window_id=?",
                (window,)))
            rows=db.execute("""SELECT o.offer_id,p.full_name,cb.name AS buyer,
                    o.offered_fee,o.status
                  FROM world_career_offers o
                  JOIN world_players p ON p.player_id=o.player_id
                  JOIN world_clubs cb ON cb.club_id=o.buying_club_id
                  WHERE o.career_id=? AND o.selling_club_id=?
                    AND o.buying_club_id<>?
                  ORDER BY o.offer_id""",(career,manager,manager)).fetchall()
            status=Counter(x["status"] for x in rows)
            print("FINAL",dict(club=club,offers=len(rows),statuses=dict(status),
                    outcomes=dict(outcomes),examples=[dict(x) for x in rows[:15]]),flush=True)
            if len(list(db.execute("SELECT * FROM world_career_market_moments WHERE window_id=?",(window,))))!=12:
                raise AssertionError("Not all 12 market moments completed")
    finally:
        env.stop()

if __name__=="__main__":
    args=argparse.ArgumentParser()
    args.add_argument("--world",required=True)
    args.add_argument("--club",default="Bournemouth")
    args.add_argument("--seed",default="bournemouth")
    args.add_argument("--skip-world",action="store_true",
                     help="Fast, manager offers only, without AI-to-AI activity")
    opts=args.parse_args()
    os.environ["FC27_PRESEASON_PLAYTEST_ENABLED"]="1"
    os.environ["FC27_PREVIEW_DATASET"]=DATASET
    main(opts.world,opts.club,opts.seed,skip_world=opts.skip_world)

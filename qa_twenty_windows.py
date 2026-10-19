"""Twenty isolated 30-minute market windows with deterministic QA audits.

Usage:
    python qa_twenty_windows.py --windows 20 --output qa-20-windows.json

Creates ONLY temporary SQLite databases; NEVER uses Render, a user's live
career, the original PES app or existing save data. This invokes the actual
market engine, including player, seller, agent, board and deadline decisions.
Not a fixed-count transfer generator. Stats are printed only after running.
This file is a manual stress-test, NOT part of ordinary request handling.
"""
import argparse
import json
import sqlite3
import tempfile
from collections import Counter,defaultdict
from datetime import datetime,timedelta,timezone
from pathlib import Path

from world_v2 import initialize_world
from world_explorer import initialize_catalog
from world_market import initialize_market
from world_careers import initialize_career_engine,start_sandbox
from world_career_management import initialize_career_management
from world_career_objectives import initialize_board_objectives
from world_career_board_policy import initialize_career_board_policy
from world_career_selling import initialize_career_selling
from world_career_incoming import initialize_incoming_approaches
from world_career_transfer_protocol import initialize_transfer_protocol
from world_live_market import (
    initialise_live_market,start_live_market,process_live_market,MARKET_MOMENTS,
)
from world_preseason_window import window_snapshot
from world_squad_planner import lane_of,MIN_COVER

DATASET="england-2026-27-fc27"
ELITE=("Arsenal","Chelsea","Manchester City")
# Use the real test-process start for internal market APIs that invoke
# window_snapshot() without a forwarded clock. A fixed date in the distant past
# would make those API calls see an already-expired 30-minute window, causing
# zero transfers for the wrong reason.
FIXED_START=datetime.now(timezone.utc).replace(microsecond=0)
INITIALIZERS=(
    initialize_world,initialize_catalog,initialize_market,
    initialize_career_engine,initialize_career_management,
    initialize_board_objectives,initialize_career_board_policy,
    initialize_career_selling,initialize_incoming_approaches,
    initialize_transfer_protocol,initialise_live_market,
)


def connect(path):
    conn=sqlite3.connect(path,isolation_level=None)
    conn.row_factory=sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def make_template(path):
    with connect(path) as conn:
        for fn in INITIALIZERS:fn(conn)
        rows=conn.execute("""SELECT c.name FROM world_clubs c
            JOIN world_dataset_entries e ON e.club_id=c.club_id
            WHERE e.dataset_id=?""",(DATASET,)).fetchall()
        if len(rows)!=92:
            raise ValueError("Expected the source-backed 92-club English dataset")
        for name in ELITE:
            if name not in {x[0] for x in rows}:
                raise ValueError("Missing elite audit club "+name)
        conn.commit()


def snapshot(conn,career):
    """Specialist depth and rated players by active career ownership."""
    rows=conn.execute("""SELECT r.club_id,r.player_id,x.overall,p.primary_position
        FROM world_career_registrations r
        JOIN world_career_saves s ON s.career_id=r.career_id
        JOIN world_dataset_ratings x ON x.dataset_id=s.dataset_id
            AND x.player_id=r.player_id
        JOIN world_players p ON p.player_id=r.player_id
        WHERE r.career_id=? AND x.overall BETWEEN 1 AND 99""",
        (career,)).fetchall()
    result=defaultdict(lambda:defaultdict(list))
    for club,pid,ovr,pos in rows:
        lane=lane_of(pos)
        if lane:result[club][lane].append((pid,ovr))
    for roster in result.values():
        for group in roster.values():group.sort(key=lambda p:-p[1])
    return result


def score_window(conn,career,initial,final,index,market_outcome):
    names=dict(conn.execute("SELECT club_id,name FROM world_clubs").fetchall())
    moves=conn.execute("""SELECT e.offer_id,e.player_id,e.from_club_id,
        e.to_club_id,p.primary_position,x.overall,e.fee_gbp
        FROM world_career_preseason_registration_events e
        JOIN world_players p ON p.player_id=e.player_id
        JOIN world_career_saves s ON s.career_id=e.career_id
        JOIN world_dataset_ratings x ON x.dataset_id=s.dataset_id
            AND x.player_id=e.player_id
        WHERE e.career_id=? ORDER BY e.offer_id""",(career,)).fetchall()
    prospects={row[0] for row in conn.execute(
        """SELECT DISTINCT e.offer_id FROM world_career_offer_events e
           JOIN world_career_offers o ON o.offer_id=e.offer_id
           WHERE o.career_id=? AND e.event_type='ai_prospect_signed'""",
        (career,)).fetchall()}
    keepers=sum(lane_of(m[4])=="GK" for m in moves)
    out=Counter(m[2] for m in moves)
    into=Counter(m[3] for m in moves)
    quality_risks=[]
    for club,old in initial.items():
        new=final.get(club,{})
        for lane,peers in old.items():
            after=new.get(lane,[])
            old_starter=peers[0][1] if peers else 0
            new_starter=after[0][1] if after else 0
            if (len(after)<len(peers) and
                    len(after)<MIN_COVER[lane] and
                    len(peers)>=MIN_COVER[lane]):
                quality_risks.append({"club":names[club],"position":lane,
                    "reason":"New specialist-depth shortage",
                    "before":len(peers),"after":len(after)})
            if (lane=="CB" and old_starter-new_starter>5
                    and into[club]<=out[club]):
                quality_risks.append({"club":names[club],"position":lane,
                    "reason":"Major leading centre-back rating decrease",
                    "before":old_starter,"after":new_starter})
    finances=conn.execute("""SELECT c.name,l.transfer_budget,l.committed_fees,
        l.weekly_wage_budget,l.committed_wages
        FROM world_career_club_ledger l JOIN world_clubs c ON c.club_id=l.club_id
        WHERE l.career_id=? AND
        (l.committed_fees>l.transfer_budget OR
         l.committed_wages>l.weekly_wage_budget)""",(career,)).fetchall()
    if finances:
        raise AssertionError("Committed funds exceed budget: "+
                             str([tuple(f) for f in finances]))
    duplicate=conn.execute("""SELECT player_id,COUNT(*) n
        FROM world_career_preseason_registration_events
        WHERE career_id=? GROUP BY player_id HAVING COUNT(*)>1""",
        (career,)).fetchall()
    if duplicate:raise AssertionError("Player registered more than once")
    by_elite={}
    for name in ELITE:
        cid=next(cid for cid,n in names.items() if n==name)
        arrivals=[m for m in moves if m[3]==cid]
        departures=[m for m in moves if m[2]==cid]
        old_ratings=sorted((p[1] for group in initial.get(cid,{}).values()
                            for p in group),reverse=True)
        new_ratings=sorted((p[1] for group in final.get(cid,{}).values()
                            for p in group),reverse=True)
        def best_eleven(ovrs):
            return round(sum(ovrs[:11])/min(11,len(ovrs)),2) if ovrs else None
        by_elite[name]={"arrivals":len(arrivals),"departures":len(departures),
            "incoming_quality":[m[5] for m in arrivals],
            "incoming_prospects":sum(m[0] in prospects for m in arrivals),
            "original_top11_mean":best_eleven(old_ratings),
            "final_top11_mean":best_eleven(new_ratings),
            "original_cb_depth":len(initial.get(cid,{}).get("CB",[])),
            "final_cb_depth":len(final.get(cid,{}).get("CB",[]))}
    attempts=conn.execute("""SELECT COUNT(*) FROM world_career_ai_world_moments
        WHERE window_id=(SELECT window_id FROM world_career_preseason_windows
          WHERE career_id=? AND season_index=1)""",(career,)).fetchone()[0]
    considered=conn.execute("""SELECT COUNT(*) FROM world_career_offers
        WHERE career_id=?""",(career,)).fetchone()[0]
    return dict(index=index,completed_transfers=len(moves),offer_count=considered,
        ai_attempts=attempts,goalkeeper_transfers=keepers,
        prospect_signings=sum(m[0] in prospects for m in moves),
        elite=by_elite,defensive_coverage_flags=quality_risks,
        final_state=market_outcome["state"])


def one_window(template,workdir,index):
    path=workdir/f"qa-{index:02d}.sqlite"
    with connect(template) as base,connect(path) as conn:
        base.backup(conn)
    with connect(path) as conn:
        career=f"market-qa-{index:02d}"
        manager=conn.execute("""SELECT club_id FROM world_clubs
            WHERE name='Nottingham Forest'""").fetchone()[0]
        start_sandbox(conn,career_id=career,dataset_id=DATASET,
            title=f"Disposable market QA window {index}",
            manager_club_id=manager,pes_lock_date="2026-08-01",
            next_summer_date="2027-07-01",
            player_decision_version="player-decisions-v2")
        initial=snapshot(conn,career)
        start_live_market(conn,career_id=career,now=FIXED_START)
        # Call each actual tick in chronological order. Skipping straight
        # to deadline would close without processing any market moments.
        for off in MARKET_MOMENTS:
            process_live_market(conn,career_id=career,
                                now=FIXED_START+timedelta(seconds=off))
        outcome=process_live_market(conn,career_id=career,
                                    now=FIXED_START+timedelta(seconds=1801))
        if outcome["state"]!="closed":
            raise AssertionError("The window failed to close at its deadline")
        final=snapshot(conn,career)
        stats=score_window(conn,career,initial,final,index,outcome)
        # A second deadline reconciliation must not duplicate completed deals.
        again=process_live_market(conn,career_id=career,
                                  now=FIXED_START+timedelta(seconds=1850))
        if again["changed"]:
            raise AssertionError("Duplicate deadline reconciliation")
        return stats


def run(windows):
    if windows<1 or windows>100:raise ValueError("Windows must be 1..100")
    with tempfile.TemporaryDirectory(prefix="pes-qa-") as tmp:
        directory=Path(tmp)
        template=directory/"template.sqlite"
        make_template(template)
        results=[]
        for i in range(1,windows+1):
            stats=one_window(template,directory,i)
            results.append(stats)
            print(f"Completed QA {i}/{windows}: "
                  f"{stats['completed_transfers']} transfers, "
                  f"{stats['prospect_signings']} prospects, "
                  f"{len(stats['defensive_coverage_flags'])} coverage flags",
                  flush=True)
        elite_totals={}
        for name in ELITE:
            entries=[result["elite"][name] for result in results]
            elite_totals[name]={
                "arrivals":sum(x["arrivals"] for x in entries),
                "departures":sum(x["departures"] for x in entries),
                "prospect_arrivals":sum(x["incoming_prospects"] for x in entries),
                "window_with_incoming":sum(x["arrivals"]>0 for x in entries),
                "mean_start_top11":round(
                    sum(x["original_top11_mean"] for x in entries)/windows,2),
                "mean_end_top11":round(
                    sum(x["final_top11_mean"] for x in entries)/windows,2),
                "total_cb_losses":sum(max(0,
                    x["original_cb_depth"]-x["final_cb_depth"]) for x in entries),
            }
        return dict(version="market-qa-v1",source_dataset=DATASET,
            fixture="isolated seeded 92-club development world",
            simulated_windows=windows,
            elite_totals=elite_totals,
            **{"total_completed":sum(x["completed_transfers"] for x in results),
               "mean_completed":round(sum(x["completed_transfers"] for x in results)/windows,2),
               "goalkeeper_share":round(
                   sum(x["goalkeeper_transfers"] for x in results)/
                   max(1,sum(x["completed_transfers"] for x in results)),3),
               "prospect_share":round(
                   sum(x["prospect_signings"] for x in results)/
                   max(1,sum(x["completed_transfers"] for x in results)),3),
               "coverage_flag_count":sum(len(x["defensive_coverage_flags"])
                                          for x in results)},
            windows=results)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--windows",type=int,default=20)
    parser.add_argument("--output",default="qa-20-windows.json")
    args=parser.parse_args()
    report=run(args.windows)
    Path(args.output).write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="windows"},indent=2))

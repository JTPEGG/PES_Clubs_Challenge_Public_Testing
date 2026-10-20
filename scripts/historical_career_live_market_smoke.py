"""Full 30-minute autonomous window smoke test on a NEW historical career.

Only used against a copied, isolated CI database. Never starts a real career.
"""
import argparse,json,sqlite3
from datetime import datetime,timedelta,timezone
from world_careers import start_sandbox,wage_budget_breakdown
from world_live_market import (
    initialise_live_market,start_live_market,process_live_market,market_messages
)
from world_preseason_window import window_snapshot


def run(db_path,year):
    conn=sqlite3.connect(db_path)
    # The web-app connection uses sqlite3.Row; the autonomous inbox returns
    # dictionaries from rows, so this must match the real application.
    conn.row_factory=sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    ds=f"pes-v2-{year}-mens-01"
    club=conn.execute("""SELECT e.club_id FROM world_dataset_entries e
       JOIN world_dataset_rosters r ON r.dataset_id=e.dataset_id AND r.club_id=e.club_id
       WHERE e.dataset_id=? GROUP BY e.club_id
       HAVING COUNT(r.player_id)>=20 ORDER BY e.club_id LIMIT 1""",(ds,)).fetchone()
    if club is None:raise ValueError("No managed club with a complete source squad")
    cid=club[0];career=f"live_historical_{year}_ci"
    from world_career_transfer_protocol import initialize_transfer_protocol
    initialize_transfer_protocol(conn)
    from world_career_incoming import initialize_incoming_approaches
    initialize_incoming_approaches(conn)
    initialise_live_market(conn)
    start_sandbox(conn,career_id=career,dataset_id=ds,
        title=f"Sandbox FIFA {year} autonomous market validation",manager_club_id=cid,
        pes_lock_date=f"{year-1}-08-01",next_summer_date=f"{year}-07-01")
    t=datetime(2026,10,20,12,0,tzinfo=timezone.utc)
    snap=start_live_market(conn,career_id=career,now=t)
    if snap["state"]!="open" or snap["duration_seconds"]!=1800:
        raise ValueError("Autonomous market did not start with 30-minute deadline")
    source=conn.execute("""SELECT r.player_id, c.weekly_wage_gbp,
       a.current_wage_weekly, ctx.weekly_wage_estimate
       FROM world_career_registrations r
       JOIN world_career_contract_snapshots c ON c.career_id=r.career_id
            AND c.player_id=r.player_id
       JOIN world_career_player_circumstances a ON a.career_id=r.career_id
            AND a.player_id=r.player_id
       JOIN world_career_live_player_context ctx ON
            ctx.career_id=r.career_id AND ctx.player_id=r.player_id
       WHERE r.career_id=? AND r.club_id=?""",(career,cid)).fetchall()
    if len(source)<18 or any(contract!=a or contract!=ctx for _,contract,a,ctx in source):
        raise ValueError("Market is still inventing a second player wage")
    result=process_live_market(conn,career_id=career,now=t+timedelta(seconds=40))
    # The model must support a zero-offer window; do not force imaginary deals.
    if result["state"]!="open":
        raise ValueError("Market processed an early moment incorrectly")
    final=process_live_market(conn,career_id=career,now=t+timedelta(seconds=1801))
    if final["state"]!="closed":
        raise ValueError("Market failed to reconcile after 30 minutes")
    if conn.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
        raise ValueError("Career database failed SQL integrity check")
    if conn.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("Autonomous market created foreign-key defects")
    report={
        "edition":year,"career_id":career,"manager_club_id":cid,
        "window_minutes":30,"tested_source_wage_context_players":len(source),
        "initial_loan_count":conn.execute("""SELECT COUNT(*) FROM
           world_career_loan_agreements WHERE career_id=? AND status='active'""",
           (career,)).fetchone()[0],
        "due_40s":result,"at_1801s":final,
        "budget":wage_budget_breakdown(conn,career,cid),
        "messages":len(market_messages(conn,career_id=career))
    }
    conn.close()
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--db",required=True);p.add_argument("--edition",type=int,required=True)
    a=p.parse_args()
    print(json.dumps(run(a.db,a.edition),indent=2,default=str))

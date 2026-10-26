"""Fast diagnostic of true FC27 transfer evaluation failures on 659 clubs.

Uses an isolated disposable world. Investigates the actual cause of failed
senior/agent/seller decisions rather than guessing from aggregated outcomes.
Never finalises real user careers or modifies the approved source warehouse.
"""
from datetime import datetime,timedelta,timezone
from collections import Counter
import argparse,json,sqlite3
from world_careers import start_sandbox
from world_live_market import initialise_live_market,start_live_market,process_live_market,MARKET_MOMENTS
from scripts.fc27_warehouse_world_bridge import DATASET

def diagnose(world,iterations=3):
    con=sqlite3.connect(world,isolation_level=None)
    con.row_factory=sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    from world_career_transfer_protocol import initialize_transfer_protocol
    from world_career_incoming import initialize_incoming_approaches
    from world_career_management import initialize_career_management
    from world_career_objectives import initialize_board_objectives
    from world_career_board_policy import initialize_career_board_policy
    from world_career_selling import initialize_career_selling
    for setup in (initialize_career_management,initialize_board_objectives,
                  initialize_career_board_policy,initialize_career_selling,
                  initialize_incoming_approaches,initialize_transfer_protocol,
                  initialise_live_market):
        setup(con)
    manager=con.execute("""SELECT e.club_id FROM world_dataset_entries e
           JOIN world_dataset_rosters r ON r.dataset_id=e.dataset_id
                AND r.club_id=e.club_id
           WHERE e.dataset_id=?
           GROUP BY e.club_id HAVING COUNT(*)>=20
           ORDER BY e.club_id LIMIT 1""",(DATASET,)).fetchone()[0]
    career="fc27_qa_model_error_probe"
    start_sandbox(con,career_id=career,dataset_id=DATASET,
        title="Disposable short FC27 model error diagnosis",
        manager_club_id=manager,pes_lock_date="2026-08-01",
        next_summer_date="2027-07-01",competition_qa_override=True)
    now=datetime.now(timezone.utc)
    market=start_live_market(con,career_id=career,now=now)
    window=market["window_id"]
    for i,second in enumerate(MARKET_MOMENTS[:iterations]):
        process_live_market(con,career_id=career,
            now=now+timedelta(seconds=second+1),
            fc27_activity_scale_qa=3)
        stages=dict(con.execute("""SELECT result_stage,COUNT(*) FROM
            world_fc27_market_negotiation_diagnostics
            WHERE window_id=? GROUP BY result_stage""",(window,)))
        detailed=[{"phase":phase,"reason":reason,"count":n}
            for phase,reason,n in con.execute("""SELECT contract_phase,
              reason,COUNT(*) FROM world_fc27_market_negotiation_diagnostics
              WHERE window_id=? AND result_stage IN (
               'seller_or_offer_evaluation_failure',
               'negotiation_processing_error',
               'player_interest_evaluation_failure')
              GROUP BY contract_phase,reason ORDER BY COUNT(*) DESC""",
              (window,))]
        print(json.dumps({"interval":i+1,"stages":stages,
              "model_error_details":detailed},indent=2),flush=True)
    con.close()

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--world",required=True)
    a.add_argument("--intervals",type=int,default=3)
    opts=a.parse_args()
    diagnose(opts.world,iterations=opts.intervals)

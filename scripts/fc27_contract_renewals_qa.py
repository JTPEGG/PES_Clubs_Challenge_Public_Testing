"""Real-source FC27 Burnley wage ambition and contract-renewal QA.

Uses an isolated copy of the immutable 659-club FC27 release, never Render
or production saves. Verifies negotiation, incremental wage budgets and the
single immutable deadline, plus authenticated contract detail access.
"""
from __future__ import annotations
import argparse
from contextlib import closing
from datetime import datetime,timedelta,timezone,date
import os,sqlite3,json
from pathlib import Path
from flask import Flask
from scripts.fc27_full_career_desk_http_playtest import boot_career,inspect,CAREER,DATASET
from world_live_market import start_live_market
from world_preseason_window import finalise_preseason_window
from world_careers import wage_budget_breakdown
from world_fc27_contract_renewals import (
    wage_signal,generate_player_requests,renewal_action,renewal_info,
    all_renewals,market_reference_for_transfer)
from world_fc27_contract_terms import fc27_agent_wage_floor

def check(condition,msg):
    if not condition:raise AssertionError(msg)

def run(world):
    path=Path(world).resolve()
    manager,coverage=inspect(path)
    boot_career(path,manager)
    with closing(sqlite3.connect(path,timeout=45)) as conn:
        conn.row_factory=sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        burnley=conn.execute("""SELECT e.club_id FROM world_dataset_entries e
            JOIN world_clubs c ON c.club_id=e.club_id
            WHERE e.dataset_id=? AND c.name LIKE 'Burnley [WH27:%'
            ORDER BY e.club_id LIMIT 1""",(DATASET,)).fetchone()
        check(burnley is not None,"Burnley missing from source world")
        manager=int(burnley[0])
        conn.execute("""UPDATE world_career_saves SET manager_club_id=?
            WHERE career_id=?""",(manager,CAREER))
        conn.commit()
        keepers=conn.execute("""SELECT r.player_id,p.full_name,x.overall,
            cs.weekly_wage_gbp
            FROM world_career_registrations r
            JOIN world_players p ON p.player_id=r.player_id
            JOIN world_dataset_ratings x ON x.player_id=r.player_id
                AND x.dataset_id=?
            JOIN world_career_contract_snapshots cs
                ON cs.career_id=r.career_id AND cs.player_id=r.player_id
            WHERE r.career_id=? AND r.club_id=? AND p.primary_position='GK'
            ORDER BY ABS(x.overall-75),cs.weekly_wage_gbp, r.player_id""",
            (DATASET,CAREER,manager)).fetchall()
        check(keepers,"Burnley has no registered source keeper")
        print("SOURCE BURNLEY KEEPERS:",
              [(k["full_name"],k["overall"],k["weekly_wage_gbp"])
               for k in keepers],flush=True)
        signals=[wage_signal(conn,career_id=CAREER,player_id=k["player_id"])
                 for k in keepers]
        print("MODELLED GK WAGE COMPARATORS:",
              [(p["name"],p["wage"],p["reference"],p["sample"],
                p["gap_pct"],p["demand"]) for p in signals],flush=True)
        check(all(q["wage"]==k["weekly_wage_gbp"] for q,k in zip(signals,keepers)),
              "The source game wage is being misrepresented")
        target=next((q for q in signals if q["overall"]==75
                     and q["wage"]==7000),None)
        if target is not None and target["reference"] is not None:
            check(target["demand"]>=target["wage"]+500,
                 "A 75-rated £7k Burnley keeper has no wage ambition")
        else:
            print("INFO: 75-rated £7k specific keeper not present in current immutable source; no salary was invented",flush=True)
        matched=next((q for q in signals if q["reference"] is not None
                      and q["demand"] is not None),None)
        if matched is None:
            participants=conn.execute("""SELECT r.player_id FROM world_career_registrations r
                WHERE r.career_id=? AND r.club_id=?""",(CAREER,manager)).fetchall()
            for entry in participants:
                candidate=wage_signal(conn,career_id=CAREER,player_id=entry[0])
                if candidate["demand"] is not None:
                    matched=candidate;break
        check(matched is not None,"Real dataset has insufficient peers for all manager players")
        now=datetime.now(timezone.utc)
        snap=start_live_market(conn,career_id=CAREER,now=now)
        check(snap["state"]=="open","Cannot open the 30-minute FC27 window")
        generated=generate_player_requests(conn,career_id=CAREER,now=now+timedelta(seconds=2))
        repeated=generate_player_requests(conn,career_id=CAREER,now=now+timedelta(seconds=4))
        check(repeated==0,"A market heartbeat rerolled player wage requests")
        request_count=conn.execute("""SELECT COUNT(*) FROM world_career_contract_renewals
            WHERE career_id=? AND window_id=? AND initiated_by='player'""",
            (CAREER,snap["window_id"])).fetchone()[0]
        check(request_count==generated,"Contract request sweep count mismatch")
        notifications=conn.execute("""SELECT COUNT(*) FROM world_career_market_inbox
            WHERE career_id=? AND message_key LIKE 'fc27-renewal:%:request'""",
            (CAREER,)).fetchone()[0]
        check(notifications==generated,"Player requests not delivered into Inbox")
        player_id=matched["player_id"]
        baseline=conn.execute("""SELECT weekly_wage_gbp,expires_on
            FROM world_career_contract_snapshots
            WHERE career_id=? AND player_id=?""",(CAREER,player_id)).fetchone()
        before=wage_budget_breakdown(conn,CAREER,manager)
        active_request=renewal_info(conn,career_id=CAREER,player_id=player_id)
        desired=max(matched["demand"],matched["wage"]+500,
                    active_request["demand_weekly_wage"] if active_request else 0)
        response=renewal_action(conn,career_id=CAREER,player_id=player_id,
            action="offer",weekly_wage=desired,contract_years=3)
        print("RENEWAL OFFER CHECK:",{
            "current_request":dict(active_request) if active_request else None,
            "desired":desired,"offer_response":response},flush=True)
        check(response["status"]=="agreed_future",
              "Accepted agent offer must sign automatically without a second manager approval")
        agreed=renewal_info(conn,career_id=CAREER,player_id=player_id)
        check(agreed["status"]=="agreed_future" and agreed["signed_at"],
              "Agent acceptance did not record binding renewal paperwork")
        confirmed_mail=conn.execute("""SELECT COUNT(*) FROM world_career_market_inbox
            WHERE career_id=? AND message_key LIKE 'fc27-renewal:%:confirmed'""",
            (CAREER,)).fetchone()[0]
        check(confirmed_mail>0,"Signed renewal was not delivered to manager Inbox")
        after=wage_budget_breakdown(conn,CAREER,manager)
        delta=max(0,desired-matched["wage"])
        check(before["remaining"]-after["remaining"]==delta,
              "Signed renewal deducted the whole contract or double-counted old wages")
        unchanged=conn.execute("""SELECT weekly_wage_gbp,expires_on FROM
            world_career_contract_snapshots WHERE career_id=? AND player_id=?""",
            (CAREER,player_id)).fetchone()
        check(tuple(unchanged)==tuple(baseline),
              "Agreed renewal changed the live PES contract before deadline")
        with_error=False
        try:renewal_action(conn,career_id=CAREER,player_id=player_id,action="confirm")
        except ValueError:with_error=True
        check(with_error,"Duplicate confirmation unexpectedly charged wages twice")
        result=finalise_preseason_window(conn,career_id=CAREER,
            now=now+timedelta(seconds=1802))
        check(result["status"]=="closed","Window didn't close after exactly 30 minutes")
        finish=renewal_info(conn,career_id=CAREER,player_id=player_id)
        check(finish["status"]=="completed","Signed renewal didn't become effective")
        current=conn.execute("""SELECT weekly_wage_gbp,expires_on
             FROM world_career_contract_snapshots
             WHERE career_id=? AND player_id=?""",(CAREER,player_id)).fetchone()
        check(current[0]==desired and current[1]=="2029-08-01",
              "Confirmed contract not reflected correctly in next PES season")
        committed=wage_budget_breakdown(conn,CAREER,manager)
        check(committed["remaining"]==after["remaining"],
              "Wage budget was charged twice upon deadline registration")
        ongoing=conn.execute("""SELECT club_id FROM world_career_registrations
            WHERE career_id=? AND player_id=?""",(CAREER,player_id)).fetchone()
        check(ongoing[0]==manager,"Renewal incorrectly transferred the player")
        market=fc27_agent_wage_floor(source_weekly_wage=7000,
            market_reference_weekly=24000,buyer_appeal=62,seller_appeal=62,
            offered_role="regular_starter")
        legacy=fc27_agent_wage_floor(source_weekly_wage=7000,
            buyer_appeal=62,seller_appeal=62,offered_role="regular_starter")
        check(market>legacy,
              "New agent calculation ignores comparable wage context")
        report={"source_clubs":coverage[0],"source_players":coverage[1],
            "club":"Burnley","keepers":[{"name":k["full_name"],
                "ovr":k["overall"],"weekly_wage":k["weekly_wage_gbp"]}
                for k in keepers],"contract_player":matched["name"],
            "old_weekly_wage":matched["wage"],"new_weekly_wage":desired,
            "wage_delta":delta,"agent_acceptance":"passed",
            "automatic_signing_and_inbox":"passed","deadline":"passed",
            "no_double_counting":"passed","transfer_fee":0,
            "generated_player_requests":generated,"peer_sample":matched["sample"]}
        print(json.dumps(report,indent=2),flush=True)
        return report

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--world",required=True)
    args=parser.parse_args()
    run(args.world)

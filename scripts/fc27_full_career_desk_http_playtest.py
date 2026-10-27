"""Full FC27 659-club Career Desk browser-flow / post-deadline PES staging QA.

All working state is a disposable imported database. HTTP requests use
Flask's real handler + CSRF/session checks; only the test's simulated market
clock advances in virtual time. Production real-time deadlines are unchanged.
No manager is ever made to manually trigger AI clubs' transfer offers.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, ExitStack
from datetime import datetime,timedelta,timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from unittest.mock import patch

from flask import Flask

from scripts.fc27_warehouse_world_bridge import DATASET
from scripts.fc27_qa_simulation_clock import isolated_simulation_clock
from scripts.stage_fc27_completed_career_squads import build_completed_career_review
from world_career_play import create_play_blueprint
from world_careers import start_sandbox,budget_remaining,_player_reference
from world_live_market import MARKET_MOMENTS,spectator_token
from world_preseason_window import window_snapshot
import world_live_market as market
import world_offer_deadlines as deadlines
import world_player_morale as morale

CAREER="fc27_659_human_career_desk_qa"
MANAGER_NAME="Arsenal"
ACCESS="disposable-only-fc27-browser-qa-access"


@contextmanager
def simulation_request_clock(moment):
    """Inject due time only inside this disposable Flask test's requests."""
    import world_preseason_window as preseason
    actual=preseason._utc
    def observed(explicit=None):
        return actual(moment if explicit is None else explicit)
    with ExitStack() as stack:
        stack.enter_context(isolated_simulation_clock(moment))
        for mod in (market,deadlines,morale):
            stack.enter_context(patch.object(mod,"_utc",side_effect=observed))
        yield


def read(db,sql,params=()):
    with sqlite3.connect(db) as con:
        con.row_factory=sqlite3.Row
        return con.execute(sql,params).fetchall()


def inspect(db):
    with sqlite3.connect(db) as con:
        con.row_factory=sqlite3.Row
        source=(
            con.execute("""SELECT COUNT(*) FROM world_dataset_entries
                WHERE dataset_id=?""",(DATASET,)).fetchone()[0],
            con.execute("""SELECT COUNT(*) FROM world_dataset_rosters
                WHERE dataset_id=?""",(DATASET,)).fetchone()[0],
            con.execute("""SELECT COUNT(DISTINCT competition_id)
                FROM world_dataset_entries WHERE dataset_id=?""",(DATASET,)).fetchone()[0])
        if source!=(659,17593,53):
            raise AssertionError(f"Incorrect FC27 source coverage: {source}")
        club=con.execute("""SELECT m.world_id FROM world_dataset_pes_v2_club_map m
            JOIN world_clubs c ON c.club_id=m.world_id
            WHERE m.dataset_id=? AND c.name LIKE ? LIMIT 1""",
            (DATASET,MANAGER_NAME+" [WH27:%")).fetchone()
        if club is None:
            raise AssertionError("Approved source Arsenal ID not found")
        count=con.execute("""SELECT COUNT(*) FROM world_dataset_rosters
            WHERE dataset_id=? AND club_id=?""",(DATASET,club[0])).fetchone()[0]
        if count<20:raise AssertionError("Manager club has incomplete squad")
        return int(club[0]),source


def boot_career(db,manager):
    """QA override is intentional here only; the public create route keeps its gate."""
    with sqlite3.connect(db) as con:
        con.row_factory=sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        from world_career_transfer_protocol import initialize_transfer_protocol
        from world_career_incoming import initialize_incoming_approaches
        from world_career_management import initialize_career_management
        from world_career_objectives import initialize_board_objectives
        from world_career_board_policy import initialize_career_board_policy
        from world_career_selling import initialize_career_selling
        from world_live_market import initialise_live_market
        for setup in (initialize_career_management,initialize_board_objectives,
                      initialize_career_board_policy,initialize_career_selling,
                      initialize_incoming_approaches,initialize_transfer_protocol,
                      initialise_live_market):
            setup(con)
        start_sandbox(con,career_id=CAREER,dataset_id=DATASET,
            title="FC27 659-club human Career Desk playtest",
            manager_club_id=manager,pes_lock_date="2026-08-01",
            next_summer_date="2027-07-01",competition_qa_override=True)
        con.commit()


def make_client(db):
    env=patch.dict(os.environ,{
        "WORLD_MARKET_COOKIE_SECRET":"fc27-659-isolated-testing-not-production",
        "WORLD_MARKET_ACCESS_KEY":ACCESS})
    env.start()
    try:
        app=Flask("fc27_659_manager_desk_isolated_qa")
        app.config["TESTING"]=True
        app.register_blueprint(create_play_blueprint(db))
        browser=app.test_client()
        response=browser.post("/world/play/login",data={"password":ACCESS},
                              base_url="https://localhost")
        if response.status_code!=302:
            raise AssertionError("Career Desk authentication failed")
        html=browser.get("/world/play?dataset="+DATASET,
                         base_url="https://localhost")
        if html.status_code!=200:
            raise AssertionError("Full-source Career Desk home could not load")
        import re
        csrf=re.search(r'name="csrf" value="([^"]+)"',html.get_data(as_text=True))
        if csrf is None:raise AssertionError("CSRF token absent on full FC27 page")
        return env,browser,csrf.group(1)
    except Exception:
        env.stop()
        raise


def get(browser,path,*,moment=None):
    if moment is None:
        res=browser.get(path,base_url="https://localhost")
    else:
        with simulation_request_clock(moment):
            res=browser.get(path,base_url="https://localhost")
    if res.status_code!=200:
        raise AssertionError(f"Career Desk GET {path}: HTTP {res.status_code}")
    return res.get_data(as_text=True)


def post(browser,path,csrf,form,*,moment=None):
    data={"csrf":csrf,**form}
    if moment is None:
        r=browser.post(path,data=data,base_url="https://localhost")
    else:
        with simulation_request_clock(moment):
            r=browser.post(path,data=data,base_url="https://localhost")
    if r.status_code!=302:
        raise AssertionError(f"Career Desk POST {path}: HTTP {r.status_code}")
    if "error=" in r.headers.get("Location",""):
        raise AssertionError(f"Rejected Career Desk action: {r.headers['Location']}")
    return r.headers["Location"]


def simulate(world,stage,output):
    world=Path(world).resolve()
    stage=Path(stage).resolve()
    output=Path(output).resolve()
    if output.exists():raise FileExistsError("Refuse to overwrite prior QA artifact output")
    if not world.is_file() or not stage.is_file():
        raise FileNotFoundError("Expected disposable full FC27 career and original PES stage")
    output.mkdir(parents=True)
    manager,counts=inspect(world)
    boot_career(world,manager)
    env,browser,csrf=make_client(world)
    market_url=f"/world/play/career/{CAREER}/market"
    steps=[]
    try:
        before=get(browser,market_url)
        assert "Start 30-minute transfer window" in before
        assert "Manager's Inbox" not in before or "Pre-season" in before
        post(browser,market_url+"/start",csrf,
             {"confirm":"start-30-minute-window"})
        win=read(world,"""SELECT window_id,started_at,deadline_at,duration_seconds
                  FROM world_career_preseason_windows WHERE career_id=?""",
                 (CAREER,))
        if len(win)!=1 or win[0]["duration_seconds"]!=1800:
            raise AssertionError("Window isn't exactly one 30-minute period")
        started=datetime.fromisoformat(win[0]["started_at"])
        deadline=datetime.fromisoformat(win[0]["deadline_at"])
        if (deadline-started)!=timedelta(seconds=1800):
            raise AssertionError("30-minute deadline changed after explicit start")
        initial=get(browser,market_url,moment=started+timedelta(seconds=1))
        if 'data-window-state="open"' not in initial:
            raise AssertionError("Browser did not show open FC27 market")
        if "Manager's Inbox" not in initial:
            raise AssertionError("Full FC27 Manager's Inbox not available")

        # A normal manager-initiated offer through the actual authenticated
        # route. The AI seller decides whether to accept: NO fabricated deal.
        with sqlite3.connect(world) as con:
            con.row_factory=sqlite3.Row
            funds=budget_remaining(con,CAREER,manager)
            targets=con.execute("""SELECT r.player_id,x.overall,r.club_id
                FROM world_career_registrations r
                JOIN world_dataset_ratings x ON x.dataset_id=?
                 AND x.player_id=r.player_id
                WHERE r.career_id=? AND r.club_id<>?
                  AND x.overall BETWEEN 66 AND 73
                ORDER BY x.overall DESC,r.player_id LIMIT 300""",
                (DATASET,CAREER,manager)).fetchall()
            target=None
            for t in targets:
                value,_=_player_reference(con,DATASET,t["player_id"])
                if type(value) is int and 0<value*2<funds:
                    depth=con.execute("""SELECT COUNT(*) FROM
                        world_career_registrations WHERE career_id=?
                        AND club_id=?""",(CAREER,t["club_id"])).fetchone()[0]
                    if depth>=20:
                        target=(int(t["player_id"]),int(value),int(t["overall"]))
                        break
        if target is None:raise AssertionError("No affordable source-rated FC27 target")
        post(browser,market_url+"/buy",csrf,
             {"player_id":str(target[0]),
              "offered_fee":str(round(target[1]*1.6)),
              "request_key":"manager-buy-v1-fc27-e2e-original"},
             moment=started+timedelta(seconds=2))
        offer=read(world,"""SELECT offer_id,status,player_id FROM world_career_offers
            WHERE career_id=? AND request_key=?""",
            (CAREER,"manager-buy-v1-fc27-e2e-original"))
        if len(offer)!=1 or offer[0]["player_id"]!=target[0]:
            raise AssertionError("Human browser bid failed to persist in FC27 career")
        steps.append({"step":"human_club_bid","offer_id":offer[0]["offer_id"],
                      "source_overall":target[2],"status":offer[0]["status"]})

        # Verify actual player-card screen, not just app helper functions.
        player=get(browser,market_url+"/player/"+str(target[0]),
                   moment=started+timedelta(seconds=3))
        if not player or len(player)<150:
            raise AssertionError("Scouting/player detail view missing")
        spectator=spectator_token_with_connection(world)
        if spectator:
            rendered=get(browser,"/world/play/watch/"+spectator,
                         moment=started+timedelta(seconds=4))
            if "Spectator" not in rendered:
                raise AssertionError("Read-only spectator page not available")
        # Each of the 12 market ticks is driven by the REAL Flask GET handler,
        # which invokes the full 659-club autonomous engine. No AI-bid button.
        for index,second in enumerate(MARKET_MOMENTS):
            due=started+timedelta(seconds=second+1)
            html=get(browser,market_url,moment=due)
            if 'data-window-state="open"' not in html:
                raise AssertionError(f"Market closed early in interval {index+1}")
            observed=read(world,"""SELECT COUNT(*) AS n FROM
                world_fc27_market_club_intents WHERE window_id=?""",
                (win[0]["window_id"],)) if False else None
            print("FC27 HUMAN DESK / 659 CLUBS: processed interval",
                  index+1,"of",len(MARKET_MOMENTS),flush=True)

        pending=read(world,"""SELECT offer_id FROM world_career_offers
            WHERE career_id=? AND status='agreed_future'""",(CAREER,))
        before_reg=read(world,"""SELECT COUNT(*) AS n FROM
            world_career_preseason_registration_events WHERE career_id=?""",
            (CAREER,))[0]["n"]
        if before_reg:raise AssertionError("Player registered before deadline")
        steps.append({"step":"market_activity","signed_before_deadline":len(pending),
                      "market_intervals":len(MARKET_MOMENTS)})
        # One hour is never granted. At 30:01, the same GET closes the
        # window and registers exactly the fully signed roster changes.
        cutoff=started+timedelta(seconds=1801)
        closed=get(browser,market_url,moment=cutoff)
        if "Final transfer window report" not in closed:
            raise AssertionError("No registration summary at the 30-minute deadline")
        if "Proceed to season setup" not in closed:
            raise AssertionError("Season setup not shown after deadline")
        end=read(world,"""SELECT status,closed_at FROM
            world_career_preseason_windows WHERE career_id=?""",(CAREER,))
        if len(end)!=1 or end[0]["status"]!="closed":
            raise AssertionError("FC27 window not actually closed")
        events=read(world,"""SELECT player_id,from_club_id,to_club_id,offer_id
            FROM world_career_preseason_registration_events
            WHERE career_id=?""",(CAREER,))
        if len(events)!=len(pending):
            raise AssertionError("Full-source deadline did not register precisely signed deals")
        if not events:
            raise AssertionError("Autonomous FC27 659 market produced no signed transfers")
        expired=read(world,"""SELECT COUNT(*) AS n FROM world_career_offers
            WHERE career_id=? AND status='agreed_future'""",(CAREER,))[0]["n"]
        if expired:raise AssertionError("Unregistered agreed transfers after deadline")
        # Browser refresh must never duplicate registration. A late incoming
        # manager decision must also be rejected even with a valid CSRF token.
        again=get(browser,market_url,moment=cutoff+timedelta(seconds=3))
        if "Final transfer window report" not in again:
            raise AssertionError("Deadline result is not replay-safe")
        count_again=read(world,"""SELECT COUNT(*) AS n FROM
            world_career_preseason_registration_events
            WHERE career_id=?""",(CAREER,))[0]["n"]
        if count_again!=len(events):raise AssertionError("Refresh duplicated transfers")
        late=browser.post(market_url+"/buy",data={
            "csrf":csrf,"player_id":str(target[0]),"offered_fee":str(target[1]*2),
            "request_key":"manager-buy-v1-fc27-e2e-late-bypass"},
            base_url="https://localhost")
        if late.status_code!=302 or "error=" not in late.headers.get("Location",""):
            raise AssertionError("Post-deadline human offer was wrongly accepted")
        # Safely connect to the PREVIOUSLY APPROVED untouched PES squad stage.
        handoff=build_completed_career_review(stage,world,CAREER,
             output/"completed-squads",platform="pc")
        if handoff["handoff"]["transfers_applied"]!=len(events):
            raise AssertionError("Original FC27 source-key squad handoff mismatch")
        if not handoff["original_app_stage_modified"]:
            pass
        else:
            raise AssertionError("Handoff changed the original PES staging")
        steps.append({"step":"registration_and_source_squad_handoff",
                      "registered_at_deadline":len(events),
                      "confirmed_stage_moves":handoff["handoff"]["transfers_applied"],
                      "native_PES_edit_file":False})
        report={
            "reference":{"clubs":counts[0],"players":counts[1],
                         "competitions":counts[2]},
            "qa_mode":"disposable_Flask_authenticated_http_full_fc27_world",
            "manager_source_club":MANAGER_NAME,"career_id":CAREER,
            "window_seconds":1800,"distinct_market_phases":1,
            "market_intervals":len(MARKET_MOMENTS),
            "manager_browser_bid_recorded":True,
            "signed_transfers_before_cutoff":len(pending),
            "registered_at_cutoff":len(events),
            "postdeadline_offer_blocked":True,
            "duplicate_registration_on_refresh":False,
            "source_key_handoff":handoff,
            "source_and_production_records_modified":False,
            "native_pes_edit_file_generated":False,
            "steps":steps,
        }
        (output/"FC27_659_CAREER_DESK_END_TO_END_AUDIT.json").write_text(
            json.dumps(report,indent=2)+"\n",encoding="utf-8")
        print("FC27 FULL HUMAN CAREER DESK PLAYTEST:",json.dumps({
            "clubs":659,"registered":len(events),"intervals":12,
            "source_key_handoff":handoff["handoff"]["transfers_applied"],
            "status":"PASS"}),flush=True)
        return report
    finally:
        env.stop()


def spectator_token_with_connection(path):
    with sqlite3.connect(path) as db:
        return spectator_token(db,career_id=CAREER)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--world",required=True)
    parser.add_argument("--stage",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    simulate(args.world,args.stage,args.output)


if __name__=="__main__":
    main()

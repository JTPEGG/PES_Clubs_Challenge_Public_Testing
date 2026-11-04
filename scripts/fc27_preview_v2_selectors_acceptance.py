"""Chromium acceptance of FC27 V2 and country > league > team playtest UI."""
import argparse
import re
import os
from pathlib import Path
import sqlite3
import threading
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright

from fc27_playtest_app import app,COVERAGE
from scripts.fc27_warehouse_world_bridge import DATASET
from world_careers import player_circumstances,career_player_policy,player_move_interest
from world_fc27_manager_playability import approved_manager_club_ids, approved_world_competition_ids
from world_player_decisions import evaluate_player_choice_v2


def check(ok,message):
    if not ok:raise AssertionError(message)


def run(output):
    root=Path(output)
    root.mkdir(exist_ok=True,parents=True)
    check(COVERAGE==dict(clubs=659,players=17593,competitions=53),
          "Incorrect frozen source dataset")
    db_path=os.environ["DATABASE_PATH"]
    with sqlite3.connect(db_path) as db:
        db.row_factory=sqlite3.Row
        club=db.execute("""SELECT c.club_id,c.name,co.name AS league,co.country
          FROM world_clubs c JOIN world_dataset_entries e ON e.club_id=c.club_id
          JOIN world_competitions co ON co.competition_id=e.competition_id
          WHERE e.dataset_id=? AND c.name LIKE 'Arsenal [WH27:%'""",(DATASET,)).fetchone()
        check(club is not None,"Arsenal is missing from full FC27 world")
        cid,raw,league,country=tuple(club)
        league=league.replace(" [FC27-659]","")
        check(country and league and raw,"Missing source competition identity")
        approved=approved_manager_club_ids(db,dataset_id=DATASET)
        check(len(approved)==344,"Expected 344 user-approved manager clubs")
        check(len(approved_world_competition_ids())==17,"Expected 17 manager competitions")
        check(cid in approved,"Arsenal should remain manageable")
        nonplayable=db.execute("""SELECT e.club_id,cl.name
            FROM world_dataset_entries e
            JOIN world_clubs cl ON cl.club_id=e.club_id
            WHERE e.dataset_id=? AND e.club_id NOT IN (
                SELECT e2.club_id FROM world_dataset_entries e2
                WHERE e2.dataset_id=? AND e2.competition_id IN (
                  """+",".join("?" for _ in approved_world_competition_ids())+""")) 
            ORDER BY cl.name LIMIT 1""",
            (DATASET,DATASET,*approved_world_competition_ids())).fetchone()
        check(nonplayable is not None and nonplayable[0] not in approved,
              "No ineligible AI-only club to verify")
        check(db.execute("""SELECT COUNT(*) FROM world_dataset_entries
           WHERE dataset_id=?""",(DATASET,)).fetchone()[0]==659,
              "Restricting managers wrongly removed clubs from source market")
    server=make_server("127.0.0.1",0,app,threaded=True)
    port=server.server_port
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    errors=[]
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True,channel="chrome",args=["--no-sandbox"])
            page=browser.new_page(viewport={"width":1280,"height":900})
            page.set_default_timeout(18000)
            page.on("pageerror",lambda error:errors.append(str(error)))
            base=f"http://127.0.0.1:{port}"
            page.goto(base+"/world/play",wait_until="domcontentloaded")
            check(page.locator('form[action="/world/play/login"]').is_visible(),"Login gate missing")
            page.locator('input[name="password"]').fill(os.environ["WORLD_MARKET_ACCESS_KEY"])
            page.locator('form[action="/world/play/login"] button').click()
            page.goto(base+"/world/play",wait_until="domcontentloaded")
            check(page.locator('#manager-country').is_visible(),"Country selector not visible")
            check(page.locator('#manager-league').is_visible(),"League selector not visible")
            check(page.locator('#manager-club').is_disabled(),"Club selectable before country/league")
            check(page.locator('#manager-country option').count()==10,
                  "Exactly nine playable countries plus placeholder expected")
            check("344 manager-selectable clubs" in page.locator("body").inner_text(),
                  "Playable scope should be explained on setup screen")
            check(str(nonplayable[1]).split(" [WH27:")[0] not in
                  page.locator('select[name="manager_club_id"]').inner_text(),
                  "Non-playable AI club leaked into manager selector")
            page.locator('#manager-country').select_option(label=country)
            check(page.locator('#manager-league').is_enabled(),"League not enabled after country")
            page.locator('#manager-league').select_option(label=league)
            check(page.locator('#manager-club').is_enabled(),"Club not enabled after league")
            check(page.locator('#manager-club option').count()>1,"League clubs missing")
            page.locator('#manager-club').select_option(label="Arsenal")
            check(page.locator('#manager-club').input_value()==str(cid),
                  "Country/league/club cascade selected wrong source club")
            # Technical settings must not clutter the human-manager flow.
            for name in ("career_id","pes_lock_date","next_summer_date",
                         "economy_version","scale","player_decision_version"):
                check(page.locator(f'[name="{name}"]').count()==0,
                      f"Unnecessary developer setting exposed to manager: {name}")
            check(page.locator('#career-title').is_visible(),
                  "Optional career-name field missing")
            check(not page.locator('#career-title').get_attribute('required'),
                  "Career name should be optional")
            check(page.locator('form[action="/world/play"] select').count()==0,
                  "Technical dataset picker still visible in FC27 preview")
            page.screenshot(path=str(root/"01-fc27-country-league-club-v2.png"),full_page=True)
            # Reject forged POST with an otherwise valid (but AI-only)
            # source club ID; browser filtering alone is insufficient.
            with sqlite3.connect(db_path) as db:
                db.row_factory=sqlite3.Row
                from world_careers import start_sandbox
                try:
                    start_sandbox(
                      db,career_id="fc27_closed_club_cannot_manage",
                      dataset_id=DATASET,title="invalid closed division test",
                      manager_club_id=int(nonplayable[0]),
                      player_decision_version="player-decisions-v2",
                      pes_lock_date="2026-08-01",next_summer_date="2027-07-01")
                    raise AssertionError("Server allowed managing an AI-only FC27 club")
                except ValueError as exc:
                    check("not one of the 344 manager-playable" in str(exc),
                          "Closed club rejected for the wrong reason: "+str(exc))
                check(db.execute("""SELECT COUNT(*) FROM world_career_saves
                    WHERE career_id='fc27_closed_club_cannot_manage'""").fetchone()[0]==0,
                      "Failed closed-club career left partial saved state")
            form=page.locator('form[action="/world/play/create"]')
            # Simulate a stale/manipulated client: the server must override
            # attempts to alter the season rules, model or financial scale.
            form.evaluate("""form => {
               for(const [name,value] of Object.entries({
                 'pes_lock_date':'2030-01-01',
                 'next_summer_date':'2032-01-01',
                 'economy_version':'tampered',
                 'player_decision_version':'legacy-sporting-v2',
                 'scale':'1.5'
               })){
                 const i=document.createElement('input');
                 i.type='hidden';i.name=name;i.value=value;form.appendChild(i);
               }
            }""")
            form.locator('button[type="submit"]').click()
            page.wait_for_url(re.compile(r"/world/play/career/fc27-[a-f0-9]{16}/market$"),
                              timeout=30000)
            check("error=" not in page.url,"FC27 new career creation was refused")
            test_career=page.url.split("/career/")[1].split("/")[0]
            check(page.locator('button:has-text("Start 30-minute transfer window")').count()==1,
                  "New career did not open the pre-start Manager's Desk")
            with sqlite3.connect(db_path) as db:
                policy=career_player_policy(db,test_career)
                check(policy["version"]=="player-decisions-v2",
                      "Actual saved FC27 career did not use V2")
                saved=db.execute("""SELECT title,pes_lock_date,next_summer_date,
                    economy_version FROM world_career_saves WHERE career_id=?""",
                    (test_career,)).fetchone()
                check(saved==("Arsenal · 2026/27","2026-08-01",
                              "2027-07-01","prototype-v1"),
                      "Server-side career name/dates/economy defaults not enforced: "+str(saved))

                prestige_count=db.execute("""SELECT COUNT(*) FROM
                    world_career_prestige_snapshots WHERE career_id=?""",
                    (test_career,)).fetchone()[0]
                check(prestige_count==659,f"V2 frozen profiles {prestige_count} not 659")
                player=db.execute("""SELECT r.player_id FROM world_career_registrations r
                    JOIN world_career_contract_snapshots ct ON ct.career_id=r.career_id
                      AND ct.player_id=r.player_id
                    WHERE r.career_id=? AND r.club_id=?
                      AND ct.weekly_wage_gbp IS NOT NULL LIMIT 1""",
                      (test_career,cid)).fetchone()
                check(player is not None,"No source-backed Arsenal wages")
                context=player_circumstances(db,test_career,player[0])
                check(context and context["source_kind"].startswith("FC27_GAME_ESTIMATE")
                      and context["current_wage_weekly"]>=0
                      and context["current_role"]!="unknown"
                      and context["renewal_status"]!="unknown",
                      f"V2 cannot derive clearly-labelled autonomous source context: {context}")
            # Exercise the ACTUAL V2 Career Desk offer-evaluation route, not
            # only the pure decision helper, against two real FC27 clubs.
            with sqlite3.connect(db_path) as db:
                db.row_factory=sqlite3.Row
                candidate=db.execute("""SELECT r.player_id,r.club_id,x.overall
                    FROM world_career_registrations r
                    JOIN world_players p ON p.player_id=r.player_id
                    JOIN world_dataset_ratings x ON x.player_id=r.player_id
                      AND x.dataset_id=?
                    JOIN world_career_contract_snapshots ct ON ct.career_id=r.career_id
                      AND ct.player_id=r.player_id
                    WHERE r.career_id=? AND r.club_id<>? AND p.birth_date IS NOT NULL
                      AND x.overall BETWEEN 67 AND 78
                      AND ct.weekly_wage_gbp IS NOT NULL
                    ORDER BY x.overall DESC LIMIT 1""",
                    (DATASET,test_career,cid)).fetchone()
                check(candidate is not None,"No FC27 cross-club candidate for real V2 scenario")
                cur=db.execute("""INSERT INTO world_career_offers
                    (career_id,request_key,player_id,buying_club_id,
                     selling_club_id,offered_fee,status,agreement_date,
                     source_rating,economy_version)
                    VALUES(?,?,?,?,?,?,'accepted_pending_contract',?,?,'prototype-v1')""",
                    (test_career,"CI_FC27_V2_EVAL_ONLY",
                     candidate["player_id"],cid,candidate["club_id"],
                     1000000,"2026-08-01",candidate["overall"]))
                db.commit()
                interest=player_move_interest(db,career_id=test_career,
                                             offer_id=cur.lastrowid)
                check(interest["policy_version"]=="player-decisions-v2"
                      and interest["decision"]!="review",
                      f"Real FC27 V2 player agent evaluation stuck in review: {interest}")
            response=evaluate_player_choice_v2(
                buyer_tier=1,seller_tier=1,buyer_score=70,seller_score=70,
                buyer_prestige=70,seller_prestige=70,overall=78,age=26,
                current_wage=context["current_wage_weekly"],
                current_role=context["current_role"],transfer_listed=context["transfer_listed"],
                renewal_status=context["renewal_status"],buyer_europe="unknown",
                seller_europe="unknown",allow_unknown_europe_neutral=True)
            check(response["decision"]!="review",
                "FC27 V2 still blocked entirely on unverified Europe")
            strict=evaluate_player_choice_v2(
                buyer_tier=1,seller_tier=1,buyer_score=70,seller_score=70,
                buyer_prestige=70,seller_prestige=70,overall=78,age=26,
                current_wage=context["current_wage_weekly"],
                current_role=context["current_role"],transfer_listed=context["transfer_listed"],
                renewal_status=context["renewal_status"],buyer_europe="unknown",
                seller_europe="unknown")
            check(strict["decision"]=="review","Existing V2 protections inadvertently weakened")
            page.goto(base+"/world/play/career/"+test_career+"/market",
                wait_until="domcontentloaded")
            check(page.locator('button:has-text("Start 30-minute transfer window")').count()==1,
                "Single transfer-window start missing")
            page.screenshot(path=str(root/"02-fc27-v2-preseason-dashboard.png"),full_page=True)
            check(not errors,"Browser JS errors: "+repr(errors))
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=4)
    print(f"PASS FC27 REAL CHROME V2 PLAYABLE 344/659 SELECTORS: {country} > {league} > Arsenal, 659 club profiles, 17,593 players, actual career saved, source wage and game roles, legacy V2 strict, no JS errors",flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="preview-v2-qa")
    run(parser.parse_args().output)

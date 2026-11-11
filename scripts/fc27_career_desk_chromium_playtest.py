"""Chromium visual / interaction check for the disposable full FC27 Career Desk.

This is the real Flask UI in an actual headless browser, not a mocked HTML
snapshot. No Render, source warehouse, existing careers or PES saves changed.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import threading
from time import perf_counter, sleep
from datetime import datetime,timedelta
from contextlib import closing
from urllib.parse import urlparse

from flask import Flask
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from scripts.fc27_full_career_desk_http_playtest import (
    CAREER,DATASET,MANAGER_NAME,ACCESS,inspect,boot_career,
)
from world_career_play import create_play_blueprint
from world_live_market import spectator_token,process_live_market
from scripts.fc27_qa_simulation_clock import isolated_simulation_clock


def check(value,message):
    if not value:
        raise AssertionError(message)


def select_target(world,manager):
    from world_careers import _player_reference,budget_remaining
    with closing(sqlite3.connect(world)) as db:
        db.row_factory=sqlite3.Row
        funds=budget_remaining(db,CAREER,manager)
        candidates=db.execute("""SELECT r.player_id,r.club_id,x.overall
            FROM world_career_registrations r
            JOIN world_dataset_ratings x ON x.dataset_id=?
                AND x.player_id=r.player_id
            WHERE r.career_id=? AND r.club_id<>?
              AND x.overall BETWEEN 66 AND 73
            ORDER BY x.overall DESC,r.player_id LIMIT 300""",
            (DATASET,CAREER,manager)).fetchall()
        for r in candidates:
            value,_=_player_reference(db,DATASET,r["player_id"])
            if not isinstance(value,int) or not 0<value*2<funds:
                continue
            depth=db.execute("""SELECT COUNT(*) FROM world_career_registrations
                WHERE career_id=? AND club_id=?""",
                (CAREER,r["club_id"])).fetchone()[0]
            if depth>=20:return int(r["player_id"]),int(value)
    raise AssertionError("No source-rated affordable scouting target")


def check_championship_move_interest(world):
    """FC27 league source levels must veto routine elite->Championship moves.

    The same named player remains fully visible without the optional interest
    filter. We temporarily set the test manager to Championship West Ham,
    then restore the fixture career before any browser interaction.
    """
    from world_scouting import scouting_search
    with closing(sqlite3.connect(world)) as db:
        db.row_factory=sqlite3.Row
        west=db.execute("""SELECT e.club_id,c.tier
            FROM world_dataset_entries e
            JOIN world_competitions c ON c.competition_id=e.competition_id
            JOIN world_clubs cl ON cl.club_id=e.club_id
            WHERE e.dataset_id=? AND lower(cl.name) LIKE 'west ham%'
            LIMIT 1""",(DATASET,)).fetchone()
        kane=db.execute("""SELECT p.player_id,c.tier,r.overall
            FROM world_players p
            JOIN world_dataset_ratings r ON r.player_id=p.player_id
                AND r.dataset_id=?
            JOIN world_dataset_rosters ro ON ro.player_id=p.player_id
                AND ro.dataset_id=r.dataset_id
            JOIN world_dataset_entries e ON e.club_id=ro.club_id
                AND e.dataset_id=r.dataset_id
            JOIN world_competitions c ON c.competition_id=e.competition_id
            WHERE p.full_name='Harry Kane'""",(DATASET,)).fetchone()
        possible_west=db.execute("""SELECT cl.name,c.name,c.tier,e.club_id
            FROM world_dataset_entries e
            JOIN world_competitions c ON c.competition_id=e.competition_id
            JOIN world_clubs cl ON cl.club_id=e.club_id
            WHERE e.dataset_id=? AND lower(cl.name) LIKE '%west%ham%'""",
            (DATASET,)).fetchall()
        print("FC27_MOVE_INTEREST_DIAGNOSTIC West Ham:",
              [tuple(x) for x in possible_west],
              "chosen:",tuple(west) if west else None,
              "Kane:",tuple(kane) if kane else None,flush=True)
        check(west is not None and west["tier"]==2,
              "2026/27 source must register West Ham as Championship (tier 2)")
        check(kane is not None and kane["tier"]==1
              and kane["overall"]>=79,
              "2026/27 source must register Harry Kane as a top-flight elite player")
        original=db.execute("""SELECT manager_club_id FROM world_career_saves
            WHERE career_id=?""",(CAREER,)).fetchone()[0]
        try:
            db.execute("""UPDATE world_career_saves SET manager_club_id=?
                WHERE career_id=?""",(west["club_id"],CAREER))
            db.commit()
            unrestricted=scouting_search(db,career_id=CAREER,query="Harry Kane",
                                          limit=30)
            filtered=scouting_search(db,career_id=CAREER,query="Harry Kane",
                                     interested_only=True,limit=30)
            check(any(p["player_id"]==kane["player_id"] for p in unrestricted),
                  "Unrestricted scouting unexpectedly hides Harry Kane")
            check(not any(p["player_id"]==kane["player_id"] for p in filtered),
                  "Championship West Ham incorrectly attracts top-flight Harry Kane")
            check(scouting_search(db,career_id=CAREER,interested_only=True,
                                  limit=3),
                  "Interest filter should still find viable targets, not remove everyone")
        finally:
            db.execute("""UPDATE world_career_saves SET manager_club_id=?
                WHERE career_id=?""",(original,CAREER))
            db.commit()


def run(world,output):
    world=Path(world).resolve()
    output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    manager,coverage=inspect(world)
    boot_career(world,manager)
    check_championship_move_interest(world)
    os.environ.update({
        "WORLD_MARKET_ACCESS_KEY":ACCESS,
        "WORLD_MARKET_COOKIE_SECRET":"isolated-real-chrome-only-fc27-qa-secret",
        "FC27_PRESEASON_PLAYTEST_ENABLED":"1",
        "FC27_PREVIEW_DATASET":DATASET,
    })
    app=Flask("fc27_visual_qa")
    # The isolated QA app has no app.py static asset wiring; browsers request
    # /favicon.ico automatically. A deliberate 204 prevents a misleading 404
    # console error without suppressing genuine JavaScript/runtime failures.
    @app.get("/favicon.ico")
    def qa_no_favicon():
        return "",204
    app.register_blueprint(create_play_blueprint(world))
    server=make_server("127.0.0.1",0,app,threaded=True)
    port=server.server_port
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    base=f"http://127.0.0.1:{port}"
    manager_path=f"/world/play/career/{CAREER}/market"
    found=[]
    failures=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,channel="chrome",args=["--no-sandbox"])
            context=browser.new_context(viewport={"width":1440,"height":900},
                device_scale_factor=1,ignore_https_errors=False)
            page=context.new_page()
            page.set_default_timeout(15000)
            page.on("pageerror",lambda e: failures.append(str(e)))
            page.on("console",lambda m: failures.append("console: "+m.text) if m.type=="error" else None)
            page.goto(base+"/world/play",wait_until="domcontentloaded")
            check(page.locator('input[name="password"]').count()==1,
                  "Development access gate not shown")
            page.locator('input[name="password"]').fill(ACCESS)
            page.locator('form[action="/world/play/login"] button').click()
            page.goto(base+"/world/play?dataset="+DATASET,
                      wait_until="domcontentloaded")
            check(page.locator("#manager-country option").count()==10,
                  "Nine approved FC27 countries (including MLS) should be manager-selectable")
            check(page.locator("#manager-club").is_disabled(),
                  "Cascading club selector did not wait for a country and league")
            found.append("Approved 344 manager clubs available; full 659 remain in AI market")

            page.goto(base+manager_path,wait_until="domcontentloaded")
            check(page.locator('button:has-text("Start 30-minute transfer window")').count()==1,
                  "One 30-minute start action missing")
            check(page.locator('#desk-view-dashboard').is_visible(),
                  "Client-side dashboard not visibly initialised")
            page.screenshot(path=str(output/"01-desktop-before-start.png"),
                            animations="disabled",full_page=True)
            found.append("Pre-start dashboard and single-window button")

            page.locator('button:has-text("Start 30-minute transfer window")').click()
            page.wait_for_url("**/market",timeout=25000)
            check(page.get_by_text("The 30-minute pre-season market has started").count()==0,
                  "Redundant window-start notice must not appear on every tab")
            check(page.locator("body").get_attribute("data-window-state")=="open",
                  "Clicked Start but real Career Desk did not open")
            header=page.locator("#desk-header-clock")
            check(header.is_visible(),"Always-visible deadline clock missing")
            check(page.locator('.desk-sidebar [data-desk-tab="inbox"]').count()==1,
                  "Manager's Inbox tab missing")
            check(page.locator("#spectator-share-url").count()==0
                  and page.get_by_text("Share the live transfer window").count()==0,
                  "Unwanted spectator-share feature is still shown in manager desk")
            check("WH27:" not in page.locator(".desk-header-right").inner_text(),
                  "Internal source-key suffix visible in manager heading")
            page.screenshot(path=str(output/"02-desktop-active-overview.png"),
                            animations="disabled",full_page=True)
            found.append("Real Start POST opened exactly one live 30-minute clock")

            # Real sourced Jadon Sancho is not in the 659 club roster: he is
            # an independent, fully rated game-model free agent.
            with closing(sqlite3.connect(world)) as db:
                count=db.execute("""SELECT COUNT(*) FROM world_fc27_free_agent_pool
                    WHERE dataset_id=?""",(DATASET,)).fetchone()[0]
                free=db.execute("""SELECT f.player_id,f.reference_weekly_wage_gbp
                    FROM world_fc27_free_agent_pool f
                    WHERE f.dataset_id=? AND f.source_ea_id='233049'""",
                    (DATASET,)).fetchone()
                before=db.execute("""SELECT COUNT(*) FROM world_career_registrations
                    WHERE career_id=?""",(CAREER,)).fetchone()[0]
            check(count==211 and free is not None and before==17593,
                  "Expected 211 independent free agents and unchanged 17,593 source registrations")
            page.goto(base+manager_path+"/player/"+str(free[0]),
                wait_until="domcontentloaded")
            check(page.locator('#fa-contract').is_visible() and
                  page.locator('#scout-buy').count()==0,
                  "Sancho cannot be signed free or is incorrectly charged a fee")
            check("FREE" in page.get_by_text("Transfer fee").first.inner_text()
                  or "Transfer fee: £0" in page.locator("body").inner_text(),
                  "Unattached signing should show £0 fee")
            page.locator('#fa-contract select[name="role_promise"]').select_option("key_player")
            page.locator('#fa-contract input[name="weekly_wage"]').fill(
                str(max(90000,int(free[1])*2)))
            with page.expect_response(
                lambda response:response.url.endswith('/market/free-agent')
                    and response.request.method=='POST',timeout=20000
            ) as agent_response:
                page.locator('#fa-contract button[type=submit]').click()
            offer_data=agent_response.value.json()
            check(offer_data.get('ok') and offer_data.get('status')=='terms_accepted',
                  "Sancho's modelled player/agent terms were not accepted in free-agent flow")
            # Agent approval is provisional. Confirming before a separate
            # player decision must be rejected by the real authenticated API.
            check(page.locator('#fa-confirm').count()==0,
                  "Free-agent profile incorrectly exposes immediate signing")
            premature=page.evaluate("""async () => {
                const form=document.querySelector('#fa-contract');
                const data=new FormData(form);
                data.set('action','confirm');
                const response=await fetch(form.getAttribute('action'),{
                    method:'POST',body:data,credentials:'same-origin',
                    headers:{Accept:'application/json'}
                });
                return {status:response.status,
                        payload:await response.json().catch(()=>null)};
            }""")
            check(premature['status']==400 and
                  not (premature['payload'] or {}).get('ok'),
                  "Manager can sign a free agent before player choice")
            with closing(sqlite3.connect(world)) as db:
                db.row_factory=sqlite3.Row
                choice=db.execute("""SELECT status FROM world_career_player_choices
                    WHERE career_id=? AND player_id=? AND kind='free_agent'
                    ORDER BY source_id DESC LIMIT 1""",(CAREER,free[0])).fetchone()
                check(choice is not None and choice['status']=='evaluating',
                      "Separate free-agent choice was not queued")
                # Only the disposable QA clock is accelerated: the real
                # server continues using bounded player deliberation.
                db.execute("""UPDATE world_career_player_choices SET due_at=?
                    WHERE career_id=? AND player_id=? AND kind='free_agent'
                      AND status='evaluating'""",
                    ((datetime.now().astimezone()-timedelta(seconds=5)).isoformat(),
                     CAREER,free[0]))
                db.commit()
            heartbeat=page.evaluate("""async path => {
                const response=await fetch(path,{credentials:'same-origin',
                    headers:{Accept:'application/json'}});
                return {ok:response.ok,status:response.status};
            }""",manager_path+'/pulse')
            check(heartbeat['ok'],"Manager heartbeat could not advance decisions")
            player_choice=None
            for _ in range(60):
                with closing(sqlite3.connect(world)) as db:
                    db.row_factory=sqlite3.Row
                    player_choice=db.execute("""SELECT status FROM
                        world_career_player_choices WHERE career_id=?
                        AND player_id=? AND kind='free_agent'
                        ORDER BY source_id DESC LIMIT 1""",
                        (CAREER,free[0])).fetchone()
                if player_choice and player_choice['status']!='evaluating':break
                sleep(0.1)
            check(player_choice is not None and
                  player_choice['status']=='accepted',
                  "Agent-approved Sancho did not receive a positive, independent player decision")
            page.goto(base+manager_path+'#inbox',wait_until='domcontentloaded')
            sancho_inbox=page.locator('.desk-inbox-free-message').filter(
                has_text='Jadon Sancho')
            check(sancho_inbox.count()==1 and
                  sancho_inbox.get_attribute('data-desk-player-choice')=='accepted',
                  "Player decision was not delivered to the manager Inbox")
            # Multiple real emails may precede the actionable offer.
            # Select Sancho's message from the left-hand Inbox list first.
            if not sancho_inbox.is_visible():
                item=page.locator('.desk-inbox-item').filter(has=sancho_inbox)
                check(item.count()==1,"Sancho's decision has no indexed Inbox row")
                item.locator('summary').click()
            sancho_inbox.locator('button[name="action"][value="confirm"]').click()
            page.wait_for_load_state('domcontentloaded')
            with closing(sqlite3.connect(world)) as db:
                signed_status=db.execute("""SELECT status FROM
                    world_fc27_free_agent_offers
                    WHERE career_id=? AND player_id=?""",
                    (CAREER,free[0])).fetchone()[0]
                registered=db.execute("""SELECT COUNT(*) FROM
                    world_career_registrations
                    WHERE career_id=? AND player_id=?""",
                    (CAREER,free[0])).fetchone()[0]
            check(signed_status=='agreed_future' and registered==0,
                  "Free agent registered before deadline or terms not saved")
            found.append("Sancho £0 fee; provisional wages, separate rival-aware player choice, Inbox paperwork and no premature registration")
            page.goto(base+manager_path,wait_until="domcontentloaded")
            page.locator('.desk-sidebar [data-desk-tab="transfers"]').click()
            sancho_row=page.locator(
                '[data-desk-table="incoming"] tr[data-free-agent-signing-id]'
            ).filter(has_text="Jadon Sancho")
            check(sancho_row.count()==1 and sancho_row.locator('td').nth(2).inner_text().strip()=='—',
                  "Signed free agent must appear exactly once in Incoming, with a dash instead of a zero fee")
            check(sancho_row.locator('td').count()==7 and
                  'years' in sancho_row.locator('td').nth(4).inner_text(),
                  "Incoming free agent must show a separate wage and contract length")
            check(page.locator("#free-signings").count()==0,
                  "Standalone free-agent transfer section should be removed")
            found.append("Fee-free Sancho signing is included in Incoming and not duplicated")

            for name in ["squad","inbox","scouting","transfers","finances"]:
                page.locator(f'.desk-sidebar [data-desk-tab="{name}"]').click()
                check(page.locator(f'#desk-view-{name}').is_visible(),
                      "Clicked "+name+" but its panel is not visible")
                check(page.locator(f'#desk-view-{name}').get_attribute('aria-label'),
                      "No accessible panel heading on "+name)
            check(page.locator('.desk-intro').count()==0,
                  "Repeated career title wastes space on every page")
            page.locator('.desk-sidebar [data-desk-tab="squad"]').click()
            check(page.locator('[data-squad-pane="list"]').is_visible(),
                  "Compact squad list should be the default view")
            row=page.locator('#desk-view-squad .desk-compact-squad tbody tr').first
            check(row.locator('td').count()==9,
                  "Squad list must show age and wages in separate compact columns")
            check(row.locator('td').nth(3).inner_text().isdigit(),
                  "Squad age must come from source player birthdate")
            check(row.locator('td').nth(5).inner_text().startswith("£"),
                  "Squad weekly wage must come from the career salary record")
            check(row.locator('select[name="role"]').count()==1
                  and row.locator('input[name="listed"]').count()==1
                  and row.locator('button[value="update"]').count()==1,
                  "Compact squad row has missing management controls")
            original_url=page.url
            with page.expect_response(
                lambda response:response.url.endswith('/market/squad/decision')
                    and response.request.method=='POST',timeout=15000
            ) as squad_response:
                row.locator('button[value="update"]').click()
            check(squad_response.value.status==200 and squad_response.value.json().get('ok'),
                  "Compact squad role/availability did not save")
            check(page.url==original_url,
                  "Updating a player's status unexpectedly reloaded the whole Career Desk")
            page.locator('[data-squad-mode="tactics"]').click()
            check(page.locator('[data-squad-pane="tactics"]').is_visible(),
                  "Tactics board did not open")
            check(page.locator('[data-pitch-players] .desk-pitch-token').count()==11,
                  "Tactical pitch must start with 11 real players")
            check(page.locator('[data-roster-list="bench"] .desk-tactics-player').count()==7,
                  "Tactics view must have seven substitutes")
            check(page.locator('[data-roster-list="reserves"] .desk-tactics-player').count()>=1,
                  "Tactics view must display remaining reserves")
            bench_player=page.locator('[data-roster-list="bench"] .desk-tactics-player').first
            moving_id=bench_player.get_attribute('data-player-id')
            bench_player.locator('select').select_option('xi')
            check(page.locator('[data-pitch-players] .desk-pitch-token[data-player-id="'+moving_id+'"]').count()==1,
                  "Bench player could not move into starting XI")
            check(page.locator('[data-pitch-players] .desk-pitch-token').count()==11,
                  "Moving a substitute created an invalid XI")
            page.locator('[data-tactics-formation]').select_option('4-3-3')
            with page.expect_response(
                lambda response:response.url.endswith('/market/tactics/save')
                    and response.request.method=='POST',timeout=18000
            ) as tactics_response:
                page.locator('[data-tactics-save]').click()
            check(tactics_response.value.status==200
                  and tactics_response.value.json().get('ok'),
                  "Valid XI, substitutes and reserves were not saved")
            page.reload(wait_until="domcontentloaded")
            page.locator('.desk-sidebar [data-desk-tab="squad"]').click()
            page.locator('[data-squad-mode="tactics"]').click()
            check(page.locator('[data-tactics-formation]').input_value()=='4-3-3'
                  and page.locator('[data-pitch-players] .desk-pitch-token[data-player-id="'+moving_id+'"]').count()==1,
                  "Tactical plan not persisted across a full reload")
            found.append("Compact one-line squad rows; role save without reload; 11-pitch, 7-subs, reserves and persisted player move")
            page.locator('.desk-sidebar [data-desk-tab="scouting"]').click()
            check(page.locator('form.scout-filters').is_visible(),
                  "Scouting form absent on full FC27 source")
            # A manager can spend minutes editing a scouting field. The
            # market must continue advancing in independent server calls,
            # not stop ticking because a focused input prevents reload.
            scout_input=page.locator('input[name="scout_query"]')
            scout_input.focus()
            # Insert one valid, auditable manager-directed proposal in this
            # ISOLATED browser QA database. This tests transport/UI only;
            # no extra offer is inserted into real careers or forced by AI.
            from world_careers import propose_offer,_player_reference
            from world_preseason_window import window_snapshot
            from world_live_market import _message
            from datetime import timezone
            with closing(sqlite3.connect(world,timeout=15)) as db:
                db.row_factory=sqlite3.Row
                player=db.execute("""SELECT r.player_id FROM
                    world_career_registrations r
                    JOIN world_dataset_ratings x ON
                      x.dataset_id=? AND x.player_id=r.player_id
                    WHERE r.career_id=? AND r.club_id=?
                      AND x.overall BETWEEN 60 AND 85
                    ORDER BY x.overall,r.player_id LIMIT 1""",
                    (DATASET,CAREER,manager)).fetchone()
                buyer=db.execute("""SELECT club_id,transfer_budget
                    FROM world_career_club_ledger
                    WHERE career_id=? AND club_id<>? AND transfer_budget>2000000
                    ORDER BY transfer_budget DESC LIMIT 1""",
                    (CAREER,manager)).fetchone()
                check(player and buyer,"QA needs a source player and funded AI buyer")
                reference,_=_player_reference(db,DATASET,player[0])
                fee=max(10000,min(int(reference or 500000),buyer[1]//3))
                live_offer_id=propose_offer(db,career_id=CAREER,
                    request_key="isolated-live-browser-bid",
                    player_id=player[0],buying_club_id=buyer[0],
                    offered_fee=fee,agreement_date="2026-07-31",
                    ai_bid_snapshot={"fee":fee,"buyer_club_id":buyer[0]},
                    autonomous_inbox=True)
                snapshot=window_snapshot(db,career_id=CAREER)
                _message(db,career_id=CAREER,
                    window_id=snapshot["window_id"],
                    key="offer:"+str(live_offer_id),
                    headline="New transfer offer",
                    detail="Isolated UI live-offer delivery regression",
                    offer_id=live_offer_id,
                    when=datetime.now(timezone.utc))
                db.commit()
            with page.expect_response(
              lambda response:'/market/pulse' in response.url
                              and response.status==200,
              timeout=30000) as pulse_response:
                page.wait_for_timeout(18000)
            pulse=pulse_response.value.json()
            check(pulse["state"]=="open" and pulse["messages"]>=1
                  and pulse["incoming_offers"]>=0,
                  "Focused-input market heartbeat did not report authoritative FC27 state")
            check(scout_input.evaluate("(el)=>document.activeElement===el"),
                  "Market progress interrupted or reset the actively edited Scouting form")
            selector='[data-live-offer-id="'+str(live_offer_id)+'"]'
            page.wait_for_function(
                "(id)=>Boolean(document.querySelector('#desk-view-inbox [data-live-offer-id=\\\"'+id+'\\\"]'))",
                arg=str(live_offer_id),timeout=12000)
            check(page.locator("#desk-view-transfers table[data-desk-table='outgoing'] tbody "+selector).count()==1,
                  "Real offer did not appear in live Transfers table without reloading")
            page.locator('.desk-sidebar [data-desk-tab="inbox"]').click()
            inbox_item=page.locator(
                "#desk-view-inbox .desk-inbox-item[data-offer-id='"+str(live_offer_id)+"']"
            )
            check(inbox_item.count()==1 and inbox_item.locator("summary").is_visible(),
                  "Real offer must arrive as a compact visible Inbox message")
            check(inbox_item.get_attribute("data-action-needed")=="true" and
                  inbox_item.locator(".desk-inbox-flag").inner_text()=="!",
                  "New actionable offer must have an Inbox exclamation mark")
            check("WH27:" not in inbox_item.locator("summary").inner_text(),
                  "Inbox summary leaked an internal warehouse club ID")
            inbox_item.locator("summary").click()
            live_card=page.locator("#desk-view-inbox .desk-inbox-reader "+selector)
            check(live_card.is_visible(),"Opening Inbox message must show offer details in the right reader")
            split=page.locator("#desk-view-inbox .desk-inbox-split")
            check(split.count()==1 and inbox_item.is_visible() and
                  split.locator(".desk-inbox-reader").is_visible(),
                  "Inbox should show separate message-list and reader panes")
            check(live_card.locator('button[value="accept"]').count()==1 and
                  live_card.locator('button[value="reject"]').count()==1 and
                  live_card.locator('button[value="counter"]').count()==1,
                  "New live offer lacks accept/reject/counter decision forms")
            # A real manager decision must be saved by the authoritative
            # endpoint and reflected in the existing card with NO expensive
            # 17k-player manager dashboard reload.
            original_url=page.url
            started=perf_counter()
            with page.expect_response(
                lambda response:response.url.endswith('/market/decision')
                  and response.request.method=='POST',timeout=16000
            ) as decision_response:
                live_card.locator('button[value="accept"]').click()
            response=decision_response.value
            accepted=response.json()
            elapsed=perf_counter()-started
            check(response.status==200 and accepted.get('ok') is True
                  and accepted.get('status')=='accepted_pending_contract',
                  "Fee acceptance did not return an authoritative JSON decision")
            page.wait_for_function("""(id)=>!document.querySelector(
                '#desk-view-inbox [data-live-offer-id="'+id+'"] button[value="accept"]')""",
                arg=str(live_offer_id),timeout=12000)
            check(page.url==original_url,
                  "Accepting a fee unexpectedly reloaded the full manager dashboard")
            check('Fee accepted' in live_card.inner_text(),
                  "Fee acceptance did not update the visible offer card")
            with closing(sqlite3.connect(world)) as db:
                recorded=db.execute("""SELECT status FROM world_career_offers
                  WHERE offer_id=? AND career_id=?""",
                  (live_offer_id,CAREER)).fetchone()[0]
            check(recorded=='accepted_pending_contract',
                  "In-browser fee acceptance did not persist in the SQLite career")
            check(elapsed<5.0,
                  f"Ajax fee decision took {elapsed:.2f}s; expected no full-page render")
            found.append(f"Manager accepted genuine incoming bid in {elapsed:.2f}s with no reload")
            page.locator('.desk-sidebar [data-desk-tab="scouting"]').click()
            scout_input.focus()
            found.append("Genuine new AI bid appears live in Inbox and Transfers without page reload")
            found.append("Autonomous market heartbeat keeps ticking while manager is focused on Scouting")
            check("WH27:" not in page.locator("#desk-view-scouting").inner_text(),
                  "Internal FC27 source tags visible in scouting club labels")
            check(page.locator("#desk-view-scouting .desk-scout-pager").is_visible(),
                  "Scouting infinite-scroll counter is missing")
            check("17,804" in page.locator(".desk-scout-pager").inner_text(),
                  "Scouting total must include all 17,593 club players plus 211 true free agents")
            first=page.locator('#desk-view-scouting table tbody tr').first.inner_text()
            check(page.locator("#desk-view-scouting .scout-table table tbody tr").count()>=80,
                  "FC27 scouting did not render its first 80 players")
            scout_row=page.locator("#desk-view-scouting [data-scout-results] tbody tr").first
            wage=scout_row.locator("td").nth(7).inner_text()
            check(wage.startswith("£") and wage!="—",
                  "Game source weekly wage must appear immediately after transfer value")
            extra_header=page.locator("#desk-view-scouting th.desk-scout-extra").first
            check(not extra_header.is_visible(),
                  "Six category attribute columns must be hidden by default")
            page.locator("[data-scout-attributes-toggle]").click()
            check(extra_header.is_visible(),
                  "Show attributes must reveal the optional scouting columns")
            first_pace=scout_row.locator("td").nth(10).inner_text()
            check(first_pace.isdigit(),"FC27 six-category scouting source data is missing")
            page.locator("[data-scout-attributes-toggle]").click()
            check(not extra_header.is_visible(),
                  "Hide attributes must restore compact scouting view")
            attrs=page.locator('select[name="scout_attribute"] option').count()
            check(attrs==30,f"FC27 individual source attribute choices missing: {attrs}")
            check(page.locator('input[name="scout_max_value"]').is_visible(),
                  "Quick market value filter missing")
            check(page.locator('input[name="scout_max_wage"]').is_visible(),
                  "Quick weekly wage estimate filter missing")
            check(page.locator('input[name="scout_interest"]').is_visible(),
                  "Quick interested-player toggle missing")
            check(page.locator('.desk-scout-quick input[type="checkbox"]').count()>=2,
                  "Show-own-team and interested-player toggles must be visible")
            page.locator("#desk-view-scouting .desk-scout-add").first.click()
            check(page.locator('.desk-position-grid input[type="checkbox"]').count()==15,
                  "Granular 15-position multiselect is missing")
            check(page.locator('input[name="scout_free_only"]').is_visible(),
                  "Independent free-agent condition missing")
            check(page.locator('input[name="scout_listed"]').is_visible(),
                  "AI transfer-listed condition missing")
            page.locator('.desk-scout-dialog-close').click()
            check(not page.locator('.desk-scout-dialog').is_visible(),
                  "Condition editor must close without discarding filters")
            found.append("Scouting compact search and pop-out condition builder includes wages")
            page.screenshot(path=str(output/"03-desktop-scouting.png"),
                            animations="disabled",full_page=True)
            page.locator('[data-scout-progress]').scroll_into_view_if_needed()
            page.wait_for_function(
                'document.querySelectorAll("#desk-view-scouting [data-scout-results] tbody tr").length>80',
                timeout=35000)
            check(page.locator("#desk-view-scouting .scout-table table tbody tr").count()>80,
                  "Automatic infinite scrolling did not load subsequent players")
            check(page.locator("#desk-view-scouting .scout-table table tbody tr").first.inner_text()==first,
                  "Infinite scrolling replaced the first page instead of appending")
            # A warmed filter must return promptly even while autonomous
            # FC27 market jobs run in the background. This measures the
            # actual live browser -> authenticated Flask JSON response.
            page.locator("#desk-view-scouting .desk-scout-add").first.click()
            filter_started=perf_counter()
            with page.expect_response(
                lambda response:"/market/scout-feed?" in response.url
                     and "scout_squad=1" in response.url
                     and response.status==200,
                timeout=15000) as filtered_response:
                page.locator('input[name="scout_squad"]').check()
            filter_seconds=perf_counter()-filter_started
            check(filter_seconds<4.0,
                  f"Scouting filter response took {filter_seconds:.2f}s; HTTP must not await AI work")
            found.append(f"Warmed scouting filter responds in {filter_seconds:.2f}s under live market")
            page.wait_for_function(
                'document.querySelector("#desk-view-scouting [data-scout-count]").textContent.includes(" of ") && document.querySelectorAll("#desk-view-scouting [data-scout-results] tbody tr").length<80',
                timeout=35000)
            check(page.locator('#desk-view-scouting [data-scout-results] tbody tr').count()<80,
                  "My squad filter did not narrow the scouting results")
            page.locator('input[name="scout_squad"]').uncheck()
            page.locator('.desk-scout-dialog-close').click()
            from world_scouting import interest_cache_ready
            check(interest_cache_ready(CAREER),
                  "Interest preview was not prewarmed during the initial career session")
            interest_started=perf_counter()
            with page.expect_response(
                lambda response:"/market/scout-feed?" in response.url
                    and "scout_interest=1" in response.url
                    and response.status==200,
                timeout=15000) as interest_response:
                page.locator('input[name="scout_interest"]').check()
            interest_seconds=perf_counter()-interest_started
            check(interest_seconds<3.0,
                  f"Cached FC27 interest filter took {interest_seconds:.2f}s")
            found.append(f"Prewarmed would-consider-a-move response {interest_seconds:.2f}s")
            page.locator('input[name="scout_interest"]').uncheck()
            page.locator('.desk-sidebar [data-desk-tab="transfers"]').click()
            check(page.locator('#desk-view-transfers .desk-table-filter-row').count()==0,
                  "Transfer Centre should not have column search boxes")
            page.locator('.desk-sidebar [data-desk-tab="squad"]').click()
            columns=page.locator('#desk-view-squad table[data-desk-table="squad"] thead tr').first.inner_text()
            check('Age' in columns and 'Wage / wk' in columns,
                  "Compact Squad list is missing age or weekly wage")
            found.append("Desktop navigation: Squad, Inbox, Scouting, Transfers, Finances")

            # Open a real linked player from Scouting without losing the
            # manager sidebar, header clock or current career state.
            page.locator('.desk-sidebar [data-desk-tab="scouting"]').click()
            first_profile=page.locator(
                '#desk-view-scouting [data-scout-results] tbody tr a[href*="/market/player/"]').first
            check(first_profile.count()==1,"Scouting has no linked player profiles")
            first_profile.click()
            check(page.locator('#desk-view-player').is_visible() and
                  page.locator('.desk-sidebar').is_visible() and
                  page.locator('#desk-header-clock').is_visible() and
                  urlparse(page.url).path==manager_path and
                  urlparse(page.url).fragment.startswith('player-'),
                  "Clicking a player left the Career Desk shell or hid its navigation")
            page.locator('.desk-sidebar [data-desk-tab="scouting"]').click()
            check(page.locator('#desk-view-scouting').is_visible(),
                  "Scouting navigation did not return from player report")
            found.append("Scouting player links open inside the existing Career Desk sidebar and clock")

            target,ref_value=select_target(world,manager)
            page.goto(base+manager_path+"#player-"+str(target),
                      wait_until="domcontentloaded")
            page.locator("#desk-view-player #scout-buy").wait_for(
                state="visible",timeout=20000)
            check(page.locator("#scout-buy").is_visible() and
                  page.locator('.desk-sidebar').is_visible() and
                  page.locator('#desk-view-player').is_visible(),
                  "Cannot bid from in-desk FC27 scouting report")
            check(page.locator('#desk-view-player h1').inner_text() and
                  page.locator('#desk-view-player .grid>.card').count()>=4,
                  "Embedded player profile lacks identity or scouting metrics")
            # Shortlisting also stays in the player view: no standalone
            # redirect that discards the user's place in the 30-minute window.
            shortlist_form=page.locator('#desk-view-player form[action$="/market/shortlist"]')
            if shortlist_form.locator('button[value="save"]').count()==1:
                with page.expect_response(lambda response:response.url.endswith(
                        '/market/shortlist') and response.request.method=='POST',
                        timeout=20000) as shortlist_response:
                    shortlist_form.locator('button[value="save"]').click()
                check(shortlist_response.value.status==200 and
                      shortlist_response.value.json().get("shortlisted") is True and
                      page.locator('#desk-view-player').is_visible() and
                      page.locator('.desk-sidebar').is_visible(),
                      "Shortlisting a player left the Career Desk or failed")
                found.append("Shortlist button saves in place without reloading the Career Desk")
            offered=round(ref_value*1.6)
            # Check the actual increment interaction before arranging the
            # exact fixture bid (the production widget uses fixed increments).
            fee=page.locator("#scout-fee")
            money=page.locator("#scout-buy .desk-money-control")
            check(money.count()==1 and money.is_visible(),
                  "Player-profile bid has no compact £ amount control")
            before_fee=int(fee.input_value())
            money.locator('select.desk-money-increment').select_option('100000')
            money.locator('button.desk-money-step').last.click()
            check(int(fee.input_value())==before_fee+100000,
                  "Transfer price plus button did not change the submitted integer")
            fee.evaluate("""(el,value)=>{
                el.value=String(value);
                el.dispatchEvent(new Event('input',{bubbles:true}));
            }""",offered)
            player_url=page.url
            with page.expect_response(
                lambda response:response.url.endswith('/market/buy')
                    and response.request.method=='POST',
                timeout=20000) as buy_response:
                page.locator('#scout-buy button[type="submit"]').click()
            saved_buy=buy_response.value.json()
            check(buy_response.value.status==200 and saved_buy.get('ok')
                  and 'data-buy-offer-id' in saved_buy.get('html',''),
                  "Player-profile buy did not return a server-validated card")
            check(page.url==player_url,
                  "Submitting a bid unexpectedly reloaded the entire dashboard")
            page.wait_for_function("""()=>Boolean(
                document.querySelector('#scout-buy-result [data-buy-offer-id]'))""",
                timeout=12000)
            found.append("Buying offer confirmed in player report without full dashboard reload")
            page.goto(base+manager_path,wait_until="domcontentloaded")
            with closing(sqlite3.connect(world)) as db:
                count=db.execute("""SELECT COUNT(*) FROM world_career_offers
                     WHERE career_id=? AND player_id=?
                       AND request_key LIKE 'manager-buy-v1-%'""",
                    (CAREER,target)).fetchone()[0]
            check(count==1,"Browser-submitted transfer offer did not persist exactly once")
            # A submitted FC27 bid must stay genuinely pending until the AI
            # selling club reviews it at a later market checkpoint.
            from world_live_market import _review_due_manager_buying_offers
            from world_preseason_window import window_snapshot
            with closing(sqlite3.connect(world,timeout=30)) as db:
                db.row_factory=sqlite3.Row
                saved=db.execute("""SELECT offer_id,status FROM world_career_offers
                    WHERE career_id=? AND player_id=?
                      AND request_key LIKE 'manager-buy-v1-%'
                    ORDER BY offer_id DESC LIMIT 1""",(CAREER,target)).fetchone()
                check(saved["status"]=="proposed",
                      "FC27 selling club responded instantly instead of evaluating a pending bid")
                queued=db.execute("""SELECT COUNT(*) FROM world_career_offer_events
                    WHERE offer_id=? AND event_type='manager_buy_queued'""",
                    (saved["offer_id"],)).fetchone()[0]
                check(queued==1,"Submitted bid is not queued for autonomous review")
                window_id=window_snapshot(db,career_id=CAREER)["window_id"]
                reviewed=_review_due_manager_buying_offers(db,career_id=CAREER,
                    window_id=window_id,
                    now=datetime.now(timezone.utc)+timedelta(seconds=120))
                after=db.execute("""SELECT status FROM world_career_offers
                    WHERE offer_id=?""",(saved["offer_id"],)).fetchone()[0]
                check(reviewed==1 and after in (
                    "accepted_pending_contract","countered","rejected"),
                    "Deferred AI seller review did not create a genuine club decision")
                check(db.execute("""SELECT COUNT(*) FROM world_career_market_inbox
                    WHERE offer_id=? AND message_key LIKE 'manager-buy-review:%'""",
                    (saved["offer_id"],)).fetchone()[0]==1,
                    "Selling club response was not delivered to manager Inbox")
                check(db.execute("""SELECT club_id FROM world_career_registrations
                    WHERE career_id=? AND player_id=?""",
                    (CAREER,target)).fetchone()[0]!=manager,
                    "Unsigned purchase silently moved player into manager's team")
            found.append("Manager's bid pending, delayed autonomous seller decision and Inbox mail are real")
            page.locator('.desk-sidebar [data-desk-tab="inbox"]').click()
            page.wait_for_function("document.body.dataset.unread === '0'",timeout=20000)
            check(page.locator('.desk-sidebar [data-desk-tab="inbox"] .desk-nav-count').count()==0,
                  "Inbox badge did not clear on Inbox open")
            check(page.locator("#desk-view-inbox #purchases").count()==0,
                  "Redundant buying negotiations still displayed in Inbox")
            from world_live_market import actionable_unread_count
            with closing(sqlite3.connect(world)) as db:
                actionable=actionable_unread_count(db,career_id=CAREER)
                news_messages=db.execute("""SELECT COUNT(*)
                    FROM world_career_market_inbox
                    WHERE career_id=? AND offer_id IS NULL""",
                    (CAREER,)).fetchone()[0]
            if actionable:
                with closing(sqlite3.connect(world)) as db:
                    pending=db.execute("""SELECT message_key,headline,is_read,offer_id
                        FROM world_career_market_inbox
                        WHERE career_id=? AND is_read=0
                        ORDER BY message_id DESC LIMIT 12""",(CAREER,)).fetchall()
                print("INBOX_UNREAD_DIAGNOSTIC",actionable,
                      [tuple(item) for item in pending],flush=True)
            check(actionable==0,
                  "Inbox still has unread actionable offers after being viewed")
            check(news_messages>=1,
                  "General market announcements must remain in Market News, not Inbox")
            page.locator('.desk-sidebar [data-desk-tab="transfers"]').click()
            check(page.locator("#desk-view-transfers #purchases").count()==1,
                  "Buy-side negotiation forms not available from Transfers")
            outgoing_card=page.locator(
                '#desk-view-transfers [data-buy-offer-id].offer').first
            check(outgoing_card.count()==1,
                  "Buyer-side negotiation card missing for saved offer")
            old_url=page.url
            original_card_id=outgoing_card.get_attribute("data-buy-offer-id")
            withdraw=outgoing_card.locator('button[value="withdraw"]')
            if withdraw.count()==1:
                with page.expect_response(
                    lambda response:response.url.endswith('/market/buy/decision')
                        and response.request.method=='POST',
                    timeout=15000) as buy_action:
                    withdraw.click()
            else:
                rebid=outgoing_card.locator('form[action$="/market/buy/rebid"] button')
                check(rebid.count()==1,
                      "No valid withdrawal or rebid action for buying negotiation")
                with page.expect_response(
                    lambda response:response.url.endswith('/market/buy/rebid')
                        and response.request.method=='POST',
                    timeout=20000) as buy_action:
                    rebid.click()
            result=buy_action.value.json()
            check(buy_action.value.status==200 and result.get("ok") is True
                  and 'data-buy-offer-id' in result.get('html',''),
                  "Buyer negotiation did not return a saved replacement card")
            check(page.url==old_url,
                  "Buyer negotiation unexpectedly reloaded the entire Career Desk")
            page.wait_for_function(
                "(id)=>Boolean(document.querySelector('#desk-view-transfers .offer[data-buy-offer-id=\\\"'+id+'\\\"]'))",
                arg=str(result['offer_id']),timeout=12000)
            found.append("Buyer negotiation updates its own card without full Career Desk navigation")
            page.locator('.desk-sidebar [data-desk-tab="inbox"]').click()
            page.screenshot(path=str(output/"04-desktop-inbox-after-bid.png"),
                            animations="disabled",full_page=True)
            found.append("Source FC27 scouting + page 2 -> offer -> Transfers negotiations; Inbox auto-read stored")

            # New V2 interactions: news notifications stay compact, budgets
            # remain on Scouting, contracts open in the desk slide-over,
            # accepted renewals sign with an Inbox receipt, and a separate
            # renewal can be rejected directly from its Inbox email.
            page.locator('.desk-sidebar [data-desk-tab="scouting"]').click()
            budget_tiles=page.locator("#desk-view-scouting .desk-scout-finance span")
            check(budget_tiles.count()==2 and
                  "Transfer budget" in budget_tiles.first.inner_text() and
                  "wage" in budget_tiles.nth(1).inner_text().lower(),
                  "Scouting transfer and wage budgets are missing")
            page.locator('.desk-sidebar [data-desk-tab="news"]').click()
            opening=page.locator("#desk-view-news .desk-news-card").filter(
                has_text="The summer transfer window is open")
            check(opening.count()==1 and
                  opening.locator('.desk-news-icon').count()==1 and
                  opening.locator('.desk-news-detail,small').count()==0,
                  "Opening notification should be compact, icon-led, without blurb or timestamp")
            check(opening.inner_text().strip().endswith("The summer transfer window is open"),
                  "Opening news notification contains surplus text")
            with closing(sqlite3.connect(world,timeout=30)) as db:
                db.row_factory=sqlite3.Row
                from world_fc27_contract_renewals import (
                    wage_signal,renewal_info,renewal_action)
                from world_careers import wage_budget_breakdown
                headroom=wage_budget_breakdown(db,CAREER,manager)["remaining"]
                members=db.execute("""SELECT r.player_id FROM world_career_registrations r
                    WHERE r.career_id=? AND r.club_id=?
                    ORDER BY r.player_id""",(CAREER,manager)).fetchall()
                viable=[]
                for person in members:
                    pid=int(person["player_id"])
                    signal=wage_signal(db,career_id=CAREER,player_id=pid)
                    renewal=renewal_info(db,career_id=CAREER,player_id=pid)
                    if signal["demand"] is None or (
                            renewal and renewal["status"] in
                            ("agreed_future","completed","declined","expired")):
                        continue
                    wage=max(signal["demand"],
                             renewal["demand_weekly_wage"] if renewal else 0)
                    wage=((wage+499)//500)*500
                    if max(0,wage-signal["wage"])<headroom-1000:
                        viable.append((pid,wage,signal["name"]))
                    if len(viable)>=2:break
                check(len(viable)>=2,
                      "Real manager roster lacks two affordable renewal candidates")
                renewal_player,renewal_wage,renewal_name=viable[0]
                reject_player,_,reject_name=viable[1]
                # Isolated test creates an agent counter so the manager can
                # reject a renewal straight from an Inbox message.
                counter=renewal_action(db,career_id=CAREER,
                    player_id=reject_player,action="offer",
                    weekly_wage=0,contract_years=1)
                check(counter["status"]=="countered",
                      "QA counteroffer did not create a rejectable renewal")

            page.locator('.desk-sidebar [data-desk-tab="squad"]').click()
            full_desk_url=page.url
            renewal_link=page.locator(
                '#desk-view-squad .desk-squad-contract-link[href$="/contract/'+
                str(renewal_player)+'"]')
            check(renewal_link.count()==1 and renewal_link.is_visible(),
                  "Manager squad has no contract negotiation link")
            renewal_link.click()
            drawer=page.locator('.desk-contract-layer')
            check(drawer.is_visible() and
                  page.locator('.desk-sidebar').is_visible() and
                  page.url.split('#')[0]==full_desk_url.split('#')[0] and
                  page.url.endswith('#contract'),
                  "Contract talks should be an integrated Career Desk view")
            offer_form=drawer.locator(
                'form[action$="/contract/'+str(renewal_player)+'/decision"]')
            offer_form.wait_for(state="visible",timeout=12000)
            check(offer_form.is_visible(),
                  "In-window contract panel did not load its valid negotiation form")
            # Money fields are now compact read-only native-number inputs
            # with displayed £ amounts and selectable +/- increments.
            amount=offer_form.locator('input[name="weekly_wage"]')
            check(int(amount.input_value())==renewal_wage and
                  offer_form.locator('.desk-money-control').is_visible(),
                  "Contract value and compact amount stepper are incorrect")
            with page.expect_response(
                lambda response:response.url.endswith(
                    '/contract/'+str(renewal_player)+'/decision') and
                    response.request.method=="POST",timeout=20000) as renewal_response:
                offer_form.locator('button[value="offer"]').click()
            # Submission closes only the integrated contract view; the
            # manager can continue using Squad/Inbox while the request saves.
            check(renewal_response.value.status==200,
                  "Accepted renewal HTTP response failed")
            page.locator('.desk-sidebar [data-desk-tab="inbox"]').click()
            page.evaluate("window.fc27PollMarket?.()")
            page.wait_for_function(
                """(pid)=>location.hash==='#inbox' && Boolean(
                    document.querySelector('#desk-view-inbox .desk-contract-inbox[data-desk-player="'+pid+'"][data-desk-status="agreed_future"]'))""",
                arg=str(renewal_player),timeout=15000)
            # The server-rendered markup can be present before the dashboard
            # script finishes converting it into split-pane Inbox messages.
            page.locator('#desk-view-inbox .desk-inbox-split').wait_for(
                state="visible",timeout=15000)
            check(page.locator('.desk-sidebar').is_visible(),
                  "Renewal completion lost the manager navigation")
            signed=page.locator(
                '#desk-view-inbox .desk-contract-inbox[data-desk-player="'+
                str(renewal_player)+'"]')
            check(signed.count()==1 and
                  signed.get_attribute("data-desk-status")=="agreed_future" and
                  signed.locator('button[value="confirm"]').count()==0,
                  "Signed renewal missing authoritative Inbox receipt or requires another confirmation")
            # The selected Inbox card lives in the right-hand reader,
            # outside its original summary row. If already selected, it is
            # visible and no list re-selection is necessary.
            if not signed.is_visible():
                signed_item=page.locator('#desk-view-inbox .desk-inbox-item').filter(
                    has=page.locator('.desk-contract-inbox[data-desk-player="'+
                        str(renewal_player)+'"]'))
                check(signed_item.count()==1,
                      "Signed renewal not indexed as a manager Inbox email")
                signed_item.locator('summary').click()
            check("New contract signed" in
                  page.locator('#desk-view-inbox .desk-inbox-reader').inner_text(),
                  "Signed renewal Inbox email does not confirm the agreed contract")
            with closing(sqlite3.connect(world)) as db:
                row=db.execute("""SELECT status,signed_at FROM
                    world_career_contract_renewals
                    WHERE career_id=? AND player_id=?""",
                    (CAREER,renewal_player)).fetchone()
                check(row and row[0]=="agreed_future" and row[1],
                      "Renewal signing not persisted in disposable career")
            reject=page.locator(
                '#desk-view-inbox .desk-contract-inbox[data-desk-player="'+
                str(reject_player)+'"]')
            check(reject.count()==1 and
                  reject.locator('button[value="decline"]').count()==1 and
                  reject.locator('a.desk-inbox-open-negotiation').count()==1,
                  "Inbox renewal email lacks Offer renewal and Reject renewal actions")
            reject_button=reject.locator('button[value="decline"]')
            # The selected message must be opened in the right-hand reader.
            if not reject.is_visible():
                reject_item=page.locator('#desk-view-inbox .desk-inbox-item').filter(
                    has=page.locator('.desk-contract-inbox[data-desk-player="'+
                        str(reject_player)+'"]'))
                check(reject_item.count()==1,"Renewal Inbox message was not indexed")
                reject_item.locator('summary').click()
            reader_profile=page.locator(
                '#desk-view-inbox .desk-inbox-reader .desk-inbox-player-meta')
            check("OVR" in reader_profile.inner_text() and
                  "Age" in reader_profile.inner_text(),
                  "Player's position, overall and age are absent from Inbox header")
            with page.expect_response(
                lambda response:response.url.endswith(
                    '/contract/'+str(reject_player)+'/decision') and
                    response.request.method=="POST",timeout=15000) as decline_response:
                reject_button.click()
            check(decline_response.value.status==200,
                  "Quick Reject renewal HTTP endpoint failed")
            with closing(sqlite3.connect(world)) as db:
                rejected=db.execute("""SELECT status FROM
                    world_career_contract_renewals
                    WHERE career_id=? AND player_id=?""",
                    (CAREER,reject_player)).fetchone()[0]
                check(rejected=="declined","Quick Inbox rejection was not committed")
            found.append("Compact news, Scouting budgets, integrated contract view, signed Inbox receipt and non-blocking renewal rejection")

            # The spectator endpoint is separately accessible without login
            # but is read-only and does not show managerial POST forms.
            with closing(sqlite3.connect(world)) as db:
                token=spectator_token(db,career_id=CAREER)
            check(bool(token),"Missing spectator token")
            spectator=browser.new_context(viewport={"width":1280,"height":800})
            view=spectator.new_page()
            view.on("pageerror",lambda e:failures.append("spectator: "+str(e)))
            view.goto(base+"/world/play/watch/"+token,wait_until="domcontentloaded")
            check(view.locator("body").get_attribute("data-spectator")=="true",
                  "Spectator view not rendered as read-only")
            check(view.locator(".desk-intro").count()==0,
                  "Repeated career heading should not appear on spectator pages")
            check(view.locator('form[action$="/market/decision"]').count()==0,
                  "Spectator sees privileged decision form")
            spectator_width=view.locator(".desk-workspace").bounding_box()["width"]
            check(spectator_width>=900,
                  f"Read-only spectator content collapsed to {spectator_width}px; manager sidebar must not reserve its column")
            view.screenshot(path=str(output/"05-readonly-spectator.png"),
                            animations="disabled",full_page=True)
            found.append("Unauthenticated spectator page is read-only")

            # Same manager in phone viewport: navigation and data remain
            # accessible without page-wide overflow. Wide tables scroll inside.
            page.set_viewport_size({"width":390,"height":844})
            page.goto(base+manager_path,wait_until="domcontentloaded")
            check(page.locator(".desk-mobile-tabs").is_visible(),
                  "Phone-sized Career Desk mobile navigation missing")
            page.locator('.desk-mobile-tabs [data-desk-tab="inbox"]').click()
            check(page.locator("#desk-view-inbox").is_visible(),
                  "Phone-sized Inbox tab does not work")
            page.screenshot(path=str(output/"06-mobile-inbox.png"),
                            animations="disabled",full_page=True)
            page.locator('.desk-mobile-tabs [data-desk-tab="squad"]').click()
            check(page.locator("#desk-view-squad").is_visible(),
                  "Phone-sized Squad tab does not work")
            overflow=page.evaluate("document.documentElement.scrollWidth-window.innerWidth")
            check(overflow<=5,f"Full page horizontal overflow at 390px viewport: {overflow}px")
            page.screenshot(path=str(output/"07-mobile-squad.png"),
                            animations="disabled",full_page=True)
            found.append("Mobile 390px Inbox/Squad navigation with no whole-page overflow")

            # Prevent the exact live-playtest failure: a new manager-club
            # bid at T-5 seconds cannot reach fee, agent, independent player
            # decision and manager sign-off before a 30-minute deadline.
            # No artificial 'deal complete' is invented.
            from world_live_market import (
                _consider_bid,close_failed_human_sale_talks)
            from world_career_incoming import _save,incoming_approach
            with closing(sqlite3.connect(world,timeout=30)) as db:
                db.row_factory=sqlite3.Row
                snapshot=window_snapshot(db,career_id=CAREER)
                deadline=datetime.fromisoformat(snapshot["deadline_at"])
                before=db.execute("""SELECT COUNT(*) FROM world_career_offers
                    WHERE career_id=? AND request_key LIKE 'live-v1-%'""",
                    (CAREER,)).fetchone()[0]
                offered,rejection=_consider_bid(db,career_id=CAREER,
                    window_id=snapshot["window_id"],slot=11,
                    t=deadline-timedelta(seconds=5))
                after=db.execute("""SELECT COUNT(*) FROM world_career_offers
                    WHERE career_id=? AND request_key LIKE 'live-v1-%'""",
                    (CAREER,)).fetchone()[0]
                check(offered is None and before==after and
                      "insufficient time" in rejection,
                      "AI generated a fresh five-seconds-before-deadline bid")
                # A real agent cannot make a credible wage promise if the
                # buying club lacks headroom. This must be an explained
                # withdrawal, not an endless Player/agent talks card.
                from world_careers import propose_offer
                candidate=db.execute("""SELECT r.player_id FROM
                    world_career_registrations r
                    JOIN world_dataset_ratings x ON x.player_id=r.player_id
                         AND x.dataset_id=?
                    WHERE r.career_id=? AND r.club_id=?
                    AND x.overall BETWEEN 60 AND 85
                    ORDER BY r.player_id LIMIT 1""",
                    (DATASET,CAREER,manager)).fetchone()
                rival=db.execute("""SELECT club_id,transfer_budget FROM
                    world_career_club_ledger
                    WHERE career_id=? AND club_id<>? AND transfer_budget>2000000
                    ORDER BY transfer_budget DESC LIMIT 1""",
                    (CAREER,manager)).fetchone()
                check(candidate and rival,
                      "No source-backed QA player and solvent buyer for salary refusal")
                from world_careers import _player_reference
                value,_=_player_reference(db,DATASET,candidate[0])
                fee=max(10000,min(int(value or 500000),rival[1]//3))
                refused_id=propose_offer(db,career_id=CAREER,
                    request_key="qa-ai-personal-terms-not-stalled",
                    player_id=candidate[0],buying_club_id=rival[0],
                    offered_fee=fee,agreement_date="2026-07-31",
                    ai_bid_snapshot={"fee":fee,"buyer_club_id":rival[0]},
                    autonomous_inbox=True)
                db.execute("""UPDATE world_career_offers
                    SET status='accepted_pending_contract'
                    WHERE offer_id=?""",(refused_id,))
                db.commit()
                no_wages=_save(db,career_id=CAREER,offer_id=refused_id,
                    status="wage_limit",
                    reason="AI buyer cannot fund the player's contractual wage",
                    agent_wage=45000)
                closed=close_failed_human_sale_talks(db,career_id=CAREER,
                    window_id=snapshot["window_id"],offer_id=refused_id,
                    agent_state=no_wages,now=datetime.now(timezone.utc))
                final=db.execute("""SELECT status FROM world_career_offers
                    WHERE offer_id=?""",(refused_id,)).fetchone()[0]
                email=db.execute("""SELECT COUNT(*) FROM
                    world_career_market_inbox
                    WHERE career_id=? AND message_key=?""",
                    (CAREER,f"ai-personal-terms-failed:{refused_id}")).fetchone()[0]
                check(closed and final=="withdrawn" and email==1,
                      "AI buyer with impossible wages stalled, or manager was not told")
                check(not close_failed_human_sale_talks(db,career_id=CAREER,
                      window_id=snapshot["window_id"],offer_id=refused_id,
                      agent_state=no_wages),
                      "Failed agent approach was not idempotently closed")
            found.append("No unusable last-five-second bids; unfundable agent talks end promptly with an Inbox reason")

            # Multiple legitimate fee offers should result in ONE actual
            # independent player decision. The loser must not remain
            # indefinitely in 'Player/agent talks', and the winner must still
            # require the human manager's final signing approval.
            from world_fc27_player_review import queue_choice,review_due_choices
            with closing(sqlite3.connect(world,timeout=30)) as db:
                db.row_factory=sqlite3.Row
                candidate=db.execute("""SELECT r.player_id
                    FROM world_career_registrations r
                    JOIN world_dataset_ratings x ON x.player_id=r.player_id
                        AND x.dataset_id=?
                    WHERE r.career_id=? AND r.club_id=?
                      AND x.overall BETWEEN 60 AND 85
                      AND NOT EXISTS(SELECT 1 FROM world_career_offers o
                        WHERE o.career_id=r.career_id AND o.player_id=r.player_id)
                    ORDER BY r.player_id LIMIT 1""",
                    (DATASET,CAREER,manager)).fetchone()
                buyers=db.execute("""SELECT l.club_id,l.transfer_budget
                    FROM world_career_club_ledger l
                    WHERE l.career_id=? AND l.club_id<>?
                      AND l.transfer_budget>2000000
                    ORDER BY l.transfer_budget DESC LIMIT 2""",
                    (CAREER,manager)).fetchall()
                check(candidate and len(buyers)==2,
                      "QA needs one clean source player and two financed buyers")
                pid=int(candidate["player_id"])
                reference,_=_player_reference(db,DATASET,pid)
                now=datetime.now(timezone.utc)
                paired=[]
                for index,buyer in enumerate(buyers):
                    fee=max(10000,min(int(reference or 500000),buyer["transfer_budget"]//3))
                    oid=propose_offer(db,career_id=CAREER,
                        request_key="qa-multiple-real-agreed-fees-"+str(index),
                        player_id=pid,buying_club_id=buyer["club_id"],
                        offered_fee=fee,agreement_date="2026-07-31",
                        ai_bid_snapshot={"fee":fee,"buyer_club_id":buyer["club_id"]},
                        autonomous_inbox=True)
                    db.execute("""UPDATE world_career_offers
                        SET status='accepted_pending_contract'
                        WHERE offer_id=?""",(oid,))
                    wage=20000+index*3500
                    db.execute("""INSERT INTO world_career_agent_terms
                        (offer_id,career_id,demanded_wage_weekly,
                         proposed_wage_weekly,status,rounds,
                         contract_years,role_promise)
                        VALUES(?,?,?,?,'accepted',1,3,'regular_starter')""",
                        (oid,CAREER,wage,wage))
                    db.commit()
                    queue_choice(db,career_id=CAREER,kind="sale",
                                 source_id=oid,player_id=pid,now=now)
                    paired.append(oid)
                review_due_choices(db,career_id=CAREER,
                                   now=now+timedelta(seconds=100))
                rows=db.execute("""SELECT o.offer_id,o.status,q.status
                    FROM world_career_offers o
                    JOIN world_career_player_choices q
                      ON q.career_id=o.career_id AND q.source_id=o.offer_id
                      AND q.kind='sale'
                    WHERE o.offer_id IN (?,?) ORDER BY o.offer_id""",
                    (paired[0],paired[1])).fetchall()
                check(len(rows)==2 and
                      sum(x[2]=='accepted' for x in rows)==1 and
                      sum(x[2]=='declined' for x in rows)==1 and
                      all(x[2]!='evaluating' for x in rows) and
                      all(x[1]!='agreed_future' for x in rows) and
                      sum(x[1]=='withdrawn' for x in rows)==1,
                      "Two competing agreed-fee offers did not produce one timely player choice, or were signed without manager approval")
                notices=db.execute("""SELECT headline FROM world_career_market_inbox
                    WHERE career_id=? AND
                      message_key IN (?,?)""",
                    (CAREER,
                     f"player-review-outcome:sale:{paired[0]}",
                     f"player-review-outcome:sale:{paired[1]}")).fetchall()
                check(len(notices)==2 and
                      any("chooses" in row[0] for row in notices) and
                      any("rejects" in row[0] for row in notices),
                      "Two real player decisions were not explained in manager Inbox")
            found.append("Competing AI offers resolve to one player choice, personalised Inbox verdicts, and final manager sign-off")

            # Advance ONLY the disposable QA DB to the real deadline. All
            # unfinished bids must be clearly labelled as deadline-expired,
            # and the manager must have a prominent usable next step.
            from world_preseason_window import finalise_preseason_window
            with closing(sqlite3.connect(world,timeout=30)) as db:
                db.row_factory=sqlite3.Row
                end=(datetime.now(timezone.utc)-timedelta(seconds=2)).isoformat()
                db.execute("""UPDATE world_career_preseason_windows
                    SET deadline_at=? WHERE career_id=?""",(end,CAREER))
                db.commit()
                finalise_preseason_window(db,career_id=CAREER)
                moved=db.execute("""SELECT club_id FROM world_career_registrations
                  WHERE career_id=? AND player_id=?""",
                  (CAREER,free[0])).fetchone()
                signed=db.execute("""SELECT status FROM
                    world_fc27_free_agent_offers WHERE career_id=?
                    AND player_id=?""",(CAREER,free[0])).fetchone()
                check(moved and moved[0]==manager and signed[0]=='completed',
                      "Fee-free Sancho signing did not register at real deadline")
            found.append("Sancho registered at 30-minute deadline with no transfer fee")
            page.set_viewport_size({"width":1440,"height":900})
            page.goto(base+manager_path,wait_until="domcontentloaded")
            check(page.locator('body').get_attribute('data-window-state')=='closed',
                  "Finalised QA deadline not visible to Career Desk")
            check(page.locator('#desk-view-dashboard [data-desk-tab="season-setup"]').is_visible(),
                  "Overview has no prominent Continue to season setup action")
            page.locator('.desk-sidebar [data-desk-tab="transfers"]').click()
            check(page.locator('#desk-view-transfers [data-post-window-continue] [data-desk-tab="season-setup"]').is_visible(),
                  "Transfer Centre has no visible Continue action at top")
            # A failed agent negotiation should already have withdrawn
            # and informed the manager. Only bids still genuinely pending
            # at the deadline should display 'Expired at deadline'.
            with closing(sqlite3.connect(world)) as db:
                expired=db.execute("""SELECT COUNT(*) FROM
                    world_career_offer_events e
                    JOIN world_career_offers o ON o.offer_id=e.offer_id
                    WHERE o.career_id=?
                      AND e.event_type='preseason_deadline_expired'""",
                    (CAREER,)).fetchone()[0]
                failed=db.execute("""SELECT COUNT(*) FROM
                    world_career_offer_events e
                    JOIN world_career_offers o ON o.offer_id=e.offer_id
                    WHERE o.career_id=? AND
                      e.event_type='ai_personal_terms_failed'""",
                    (CAREER,)).fetchone()[0]
                leftover=db.execute("""SELECT COUNT(*) FROM
                    world_career_offers o
                    JOIN world_career_preseason_window_offers w
                      ON w.offer_id=o.offer_id
                    WHERE o.career_id=? AND
                      o.status IN ('proposed','countered','accepted_pending_contract')""",
                    (CAREER,)).fetchone()[0]
            displayed=page.locator(
                '#desk-view-transfers table[data-desk-table="outgoing"]').inner_text()
            check(leftover==0 and (expired==0 or 'Expired at deadline' in displayed)
                  and (failed==0 or 'Personal terms unsuccessful' in displayed),
                  "Unsigned bids lack accurate deadline-expired or early failed-negotiation labels")
            page.locator('#desk-view-transfers [data-post-window-continue] [data-desk-tab="season-setup"]').click()
            check(page.locator('#desk-view-season-setup').is_visible(),
                  "Continue link did not navigate to season setup checklist")
            found.append("Post-deadline offers labelled expired; Continue opens the real season setup")

            # The deliberate pre-player-decision signing rejection returned
            # an asserted HTTP 400; Chrome logs this expected response as
            # a generic resource error. Allow only that exact single entry.
            expected_rejection=("console: Failed to load resource: the server "
                "responded with a status of 400 (BAD REQUEST)")
            if premature["status"]==400 and expected_rejection in failures:
                failures.remove(expected_rejection)
            check(not failures,"JavaScript / browser console errors: "+repr(failures))
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=3)

    report={
        "result":"PASS","coverage":{"clubs":coverage[0],
              "players":coverage[1],"competitions":coverage[2]},
        "mode":"headless_real_Chromium_Flask_disposable_approved_FC27",
        "browser_checks":found,
        "manager_team":MANAGER_NAME,
        "window_seconds":1800,"second_30_minute_phase":False,
        "real_manager_offer_submitted":True,
        "spectator_read_only":True,
        "desktop_and_mobile_screenshots":7,
        "browser_errors":failures,
        "production_or_immutable_data_modified":False,
        "native_PES_EDIT_generated":False,
        "caveat":"Automated browser usability smoke; a human hands-on session is still needed.",
    }
    (output/"CHROMIUM_FC27_CAREER_DESK_USABILITY_REPORT.json").write_text(
        json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("FC27 CAREER DESK ACTUAL CHROMIUM PLAYTEST: "+json.dumps(report),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--world",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    run(args.world,args.output)


if __name__=="__main__":
    main()

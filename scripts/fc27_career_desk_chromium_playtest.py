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
from time import perf_counter
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
            page.wait_for_function(
                "()=>!document.querySelector('#fa-confirm').hidden",
                timeout=12000)
            with page.expect_response(
                lambda response:response.url.endswith('/market/free-agent')
                    and response.request.method=='POST',timeout=16000
            ) as signing_response:
                page.locator('#fa-confirm button[type=submit]').click()
            signing=signing_response.value.json()
            check(signing.get('ok') and signing.get('status')=='agreed_future',
                  "Manager could not confirm agreed Sancho wage-only signing")
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
            found.append("Sancho available, £0 transfer fee, agent wage agreed, manager signed, not registered early")
            page.goto(base+manager_path,wait_until="domcontentloaded")
            page.locator('.desk-sidebar [data-desk-tab="transfers"]').click()
            sancho_row=page.locator(
                '[data-desk-table="incoming"] tr[data-free-agent-signing-id]'
            ).filter(has_text="Jadon Sancho")
            check(sancho_row.count()==1 and "FREE" in sancho_row.inner_text(),
                  "Signed free agent must appear exactly once alongside purchased players in Incoming")
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
            wage=scout_row.locator("td").nth(6).inner_text()
            check(wage.startswith("£") and wage!="—",
                  "Game source weekly wage must appear immediately after transfer value")
            extra_header=page.locator("#desk-view-scouting th.desk-scout-extra").first
            check(not extra_header.is_visible(),
                  "Six category attribute columns must be hidden by default")
            page.locator("[data-scout-attributes-toggle]").click()
            check(extra_header.is_visible(),
                  "Show attributes must reveal the optional scouting columns")
            first_pace=scout_row.locator("td").nth(9).inner_text()
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

            target,ref_value=select_target(world,manager)
            page.goto(base+manager_path+"/player/"+str(target),
                      wait_until="domcontentloaded")
            check(page.locator("#scout-buy").is_visible(),
                  "Cannot bid from a full FC27 player's scouting report")
            offered=round(ref_value*1.6)
            page.locator("#scout-fee").fill(str(offered))
            player_url=page.url
            with page.expect_response(
                lambda response:response.url.endswith('/market/buy')
                    and response.request.method=='POST',
                timeout=20000) as buy_response:
                page.locator("#scout-buy button").click()
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
            check('Expired at deadline' in page.locator(
                  '#desk-view-transfers table[data-desk-table="outgoing"]').inner_text(),
                  "Unsigned bids at deadline incorrectly labelled as voluntary withdrawals")
            page.locator('#desk-view-transfers [data-post-window-continue] [data-desk-tab="season-setup"]').click()
            check(page.locator('#desk-view-season-setup').is_visible(),
                  "Continue link did not navigate to season setup checklist")
            found.append("Post-deadline offers labelled expired; Continue opens the real season setup")

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

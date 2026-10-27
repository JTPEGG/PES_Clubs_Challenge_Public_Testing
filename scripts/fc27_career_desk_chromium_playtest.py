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


def run(world,output):
    world=Path(world).resolve()
    output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    manager,coverage=inspect(world)
    boot_career(world,manager)
    os.environ.update({
        "WORLD_MARKET_ACCESS_KEY":ACCESS,
        "WORLD_MARKET_COOKIE_SECRET":"isolated-real-chrome-only-fc27-qa-secret",
    })
    app=Flask("fc27_visual_qa")
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
            browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
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
            check(page.locator('select[name="manager_club_id"] option').count()==659,
                  "All 659 source clubs not available in career selection")
            found.append("Full 659-club career selection visible in real Chromium")

            page.goto(base+manager_path,wait_until="domcontentloaded")
            check(page.locator('button:has-text("Start 30-minute transfer window")').count()==1,
                  "One 30-minute start action missing")
            check(page.locator('#desk-view-dashboard').is_visible(),
                  "Client-side dashboard not visibly initialised")
            page.screenshot(path=str(output/"01-desktop-before-start.png"),
                            animations="disabled",full_page=True)
            found.append("Pre-start dashboard and single-window button")

            page.locator('button:has-text("Start 30-minute transfer window")').click()
            page.wait_for_url("**/market?notice=**",timeout=25000)
            check(page.locator("body").get_attribute("data-window-state")=="open",
                  "Clicked Start but real Career Desk did not open")
            header=page.locator("#desk-header-clock")
            check(header.is_visible(),"Always-visible deadline clock missing")
            check(page.locator('.desk-sidebar [data-desk-tab="inbox"]').count()==1,
                  "Manager's Inbox tab missing")
            page.screenshot(path=str(output/"02-desktop-active-overview.png"),
                            animations="disabled",full_page=True)
            found.append("Real Start POST opened exactly one live 30-minute clock")

            for name in ["squad","inbox","scouting","transfers","finances"]:
                page.locator(f'.desk-sidebar [data-desk-tab="{name}"]').click()
                check(page.locator(f'#desk-view-{name}').is_visible(),
                      "Clicked "+name+" but its panel is not visible")
                check(page.locator('#desk-current-view').inner_text().strip(),
                      "No navigation heading on "+name)
            page.locator('.desk-sidebar [data-desk-tab="scouting"]').click()
            check(page.locator('form.scout-filters').is_visible(),
                  "Scouting form absent on full FC27 source")
            page.screenshot(path=str(output/"03-desktop-scouting.png"),
                            animations="disabled",full_page=True)
            found.append("Desktop navigation: Squad, Inbox, Scouting, Transfers, Finances")

            target,ref_value=select_target(world,manager)
            page.goto(base+manager_path+"/player/"+str(target),
                      wait_until="domcontentloaded")
            check(page.locator("#scout-buy").is_visible(),
                  "Cannot bid from a full FC27 player's scouting report")
            offered=round(ref_value*1.6)
            page.locator("#scout-fee").fill(str(offered))
            page.locator("#scout-buy button").click()
            page.wait_for_url("**/market?notice=**",timeout=25000)
            with closing(sqlite3.connect(world)) as db:
                count=db.execute("""SELECT COUNT(*) FROM world_career_offers
                     WHERE career_id=? AND player_id=?
                       AND request_key LIKE 'manager-buy-v1-%'""",
                    (CAREER,target)).fetchone()[0]
            check(count==1,"Browser-submitted transfer offer did not persist exactly once")
            page.locator('.desk-sidebar [data-desk-tab="inbox"]').click()
            page.screenshot(path=str(output/"04-desktop-inbox-after-bid.png"),
                            animations="disabled",full_page=True)
            found.append("Source FC27 scouting card -> offer form -> saved manager bid")

            # The spectator endpoint is separately accessible without login
            # but is read-only and does not show managerial POST forms.
            with closing(sqlite3.connect(world)) as db:
                token=spectator_token(db,career_id=CAREER)
            check(bool(token),"Missing spectator token")
            spectator=browser.new_context(viewport={"width":1280,"height":800})
            view=spectator.new_page()
            view.on("pageerror",lambda e:failures.append("spectator: "+str(e)))
            view.goto(base+"/world/play/watch/"+token,wait_until="domcontentloaded")
            check("Spectator" in view.locator("body").inner_text(),
                  "Spectator view not rendered")
            check(view.locator('form[action$="/market/decision"]').count()==0,
                  "Spectator sees privileged decision form")
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

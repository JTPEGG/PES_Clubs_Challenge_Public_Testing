"""Authenticated, real-seeded end-to-end checks for automatic transfer inbox.

Disposable SQLite and Flask test client only: no actual club, live transfer,
PES console registration, user career or production service is modified.
"""
import os
import re
import sqlite3
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from world_career_play import create_play_blueprint
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
from world_preseason_window import window_snapshot
from world_live_market import market_messages

DATASET="england-2026-27-fc27"
CAREER="auto-inbox-test-2627"

class LiveMarketHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.temp.name)/"live-market.sqlite"
        db=sqlite3.connect(cls.path)
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        for initializer in (
            initialize_world,initialize_catalog,initialize_market,
            initialize_career_engine,initialize_career_management,
            initialize_board_objectives,initialize_career_board_policy,
            initialize_career_selling,initialize_incoming_approaches,
            initialize_transfer_protocol):
            initializer(db)
        manager=db.execute("""SELECT club_id FROM world_clubs
            WHERE name='Nottingham Forest'""").fetchone()
        if manager is None:raise AssertionError("Missing real seeded Forest club")
        start_sandbox(db,career_id=CAREER,dataset_id=DATASET,
            title="Autonomous test — Nottingham Forest",
            manager_club_id=manager[0],pes_lock_date="2026-08-01",
            next_summer_date="2027-07-01",
            player_decision_version="player-decisions-v2")
        db.close()
        cls.env=patch.dict(os.environ,{
            "WORLD_MARKET_COOKIE_SECRET":"only-for-isolated-live-market-test",
            "WORLD_MARKET_ACCESS_KEY":"only-for-isolated-market-access"})
        cls.env.start()
        cls.app=Flask("isolated_live_market")
        cls.app.config["TESTING"]=True
        cls.app.register_blueprint(create_play_blueprint(cls.path))
        cls.client=cls.app.test_client()
        signin=cls.client.post("/world/play/login",
            data={"password":"only-for-isolated-market-access"},
            base_url="https://localhost")
        if signin.status_code!=302:raise AssertionError("Test login failed")
        content=cls.client.get("/world/play",base_url="https://localhost").get_data(as_text=True)
        match=re.search(r'name="csrf" value="([^"]+)"',content)
        if match is None:raise AssertionError("Missing CSRF token")
        cls.csrf=match.group(1)

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        cls.temp.cleanup()

    def connect_db(self):
        db=sqlite3.connect(self.path)
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def test_password_free_dev_access_preserves_csrf_write_protection(self):
        # The no-password option is exclusively activated by an empty
        # development access key; no browser sign-in cookie is required.
        with patch.dict(os.environ, {"WORLD_MARKET_ACCESS_KEY": ""}):
            visitor=self.app.test_client()
            home=visitor.get("/world/play",base_url="https://localhost")
            self.assertEqual(home.status_code,200)
            html=home.get_data(as_text=True)
            self.assertIn("Career Transfer Desk",html)
            self.assertNotIn("Development access passphrase",html)
            self.assertNotIn("Sign out",html)
            market=visitor.get("/world/play/career/"+CAREER+"/market",
                               base_url="https://localhost")
            self.assertEqual(market.status_code,200)
            # Public access does NOT remove the signed CSRF requirement.
            denied=visitor.post("/world/play/career/"+CAREER+"/market/start",
                data={"confirm":"start-30-minute-window"},
                base_url="https://localhost")
            self.assertEqual(denied.status_code,403)

    def test_login_url_browser_navigation_redirects_instead_of_405(self):
        browser=self.app.test_client().get("/world/play/login",
                                           base_url="https://localhost")
        self.assertEqual(browser.status_code,302)
        self.assertTrue(browser.headers["Location"].endswith("/world/play"))

    def test_00_window_not_started_by_get_or_login(self):
        path="/world/play/career/"+CAREER+"/market"
        first=self.client.get(path,base_url="https://localhost")
        self.assertEqual(first.status_code,200)
        html=first.get_data(as_text=True)
        self.assertIn("Start 30-minute transfer window",html)
        self.assertNotIn("Lock seller circumstances",html)
        self.assertNotIn("Simulate AI",html)
        with self.connect_db() as db:
            self.assertEqual(window_snapshot(db,career_id=CAREER)["state"],
                             "not_started")
            self.assertEqual(db.execute("""SELECT COUNT(*)
                FROM world_career_market_inbox""").fetchone()[0],0)
        # An unsigned spectator URL never exposes privileged data.
        denied=self.app.test_client().get("/world/play/watch/not-a-valid-token",
                                        base_url="https://localhost")
        self.assertEqual(denied.status_code,404)

    def test_00a_dashboard_shell_and_dynamic_navigation_before_window(self):
        url=f"/world/play/career/{CAREER}/market"
        page=self.client.get(url,base_url="https://localhost")
        self.assertEqual(page.status_code,200)
        html=page.get_data(as_text=True)
        self.assertIn('class="desk-shell"',html)
        self.assertIn('id="desk-view-host"',html)
        self.assertIn('id="desk-screen-source"',html)
        self.assertIn('id="desk-header-clock"',html)
        self.assertIn('data-window-state="not_started"',html)
        for screen in ("dashboard","inbox","transfers","scouting",
                       "shortlist","finances","news"):
            self.assertIn(f'data-desk-tab="{screen}"',html)
        self.assertIn("Start 30-minute transfer window",html)
        self.assertIn("switchView(",html)
        self.assertIn("history.pushState",html)
        self.assertIn("Your transfer window",html)
        # A simple GET or tab switch must not start the deadline.
        with self.connect_db() as db:
            self.assertEqual(window_snapshot(db,career_id=CAREER)["state"],
                             "not_started")

    def test_00b_shortlist_accessible_before_window_starts(self):
        base=f"/world/play/career/{CAREER}/market"
        before=self.client.get(base,base_url="https://localhost")
        self.assertEqual(before.status_code,200)
        self.assertIn("Open saved shortlist",before.get_data(as_text=True))
        shortlist=self.client.get(base+"/shortlist",base_url="https://localhost")
        self.assertEqual(shortlist.status_code,200)
        self.assertIn("My transfer shortlist",shortlist.get_data(as_text=True))
        anonymous=self.app.test_client().get(base+"/shortlist",
                                             base_url="https://localhost")
        self.assertEqual(anonymous.status_code,302)

    def test_00c_preseason_squad_listings_update_career_without_starting_clock(self):
        base=f"/world/play/career/{CAREER}/market"
        from world_squad_desk import squad_preview
        with self.connect_db() as db:
            current=squad_preview(db,career_id=CAREER)
            self.assertGreater(len(current["players"]),10)
            player=current["players"][-1]
            pid=player["player_id"]
            before=db.execute("""SELECT current_role,transfer_listed
                 FROM world_career_player_circumstances WHERE career_id=?
                   AND player_id=?""",(CAREER,pid)).fetchone()
        page=self.client.get(base,base_url="https://localhost")
        self.assertEqual(page.status_code,200)
        html=page.get_data(as_text=True)
        self.assertIn('id="squad"',html)
        self.assertIn('data-desk-tab="squad"',html)
        posted=self.client.post(base+"/squad/decision",data={
            "csrf":self.csrf,"player_id":pid,"role":"fringe",
            "listed":"1","action":"update"},base_url="https://localhost")
        self.assertEqual(posted.status_code,302)
        self.assertNotIn("error=",posted.headers["Location"])
        with self.connect_db() as db:
            status=db.execute("""SELECT current_role,transfer_listed
                FROM world_career_player_circumstances WHERE career_id=?
                  AND player_id=?""",(CAREER,pid)).fetchone()
            self.assertEqual(tuple(status),("fringe",1))
            self.assertEqual(window_snapshot(db,career_id=CAREER)["state"],
                             "not_started")
            # Restore the original player instructions so other simulation
            # tests start from the same career assumptions.
            if before:
                db.execute("""UPDATE world_career_player_circumstances
                    SET current_role=?,transfer_listed=? WHERE career_id=?
                    AND player_id=?""",(before[0],before[1],CAREER,pid))
            else:
                db.execute("""DELETE FROM world_career_player_circumstances
                   WHERE career_id=? AND player_id=?""",(CAREER,pid))
            db.commit()

    def test_01_manager_starts_explicit_one_time_window(self):
        url="/world/play/career/"+CAREER+"/market/start"
        noauth=self.app.test_client().post(url,
            data={"csrf":self.csrf,"confirm":"start-30-minute-window"},
            base_url="https://localhost")
        self.assertIn(noauth.status_code,(302,403))
        with self.connect_db() as db:
            self.assertEqual(window_snapshot(db,career_id=CAREER)["state"],
                             "not_started")
        started=self.client.post(url,data={"csrf":self.csrf,
            "confirm":"start-30-minute-window"},
            base_url="https://localhost")
        self.assertEqual(started.status_code,302)
        self.assertNotIn("error=",started.headers["Location"])
        with self.connect_db() as db:
            snap=window_snapshot(db,career_id=CAREER)
            self.assertEqual(snap["state"],"open")
            self.assertEqual(snap["duration_seconds"],1800)
            self.assertGreaterEqual(snap["remaining_seconds"],1700)
            contexts=db.execute("""SELECT COUNT(*) FROM world_career_live_player_context
                WHERE career_id=?""",(CAREER,)).fetchone()[0]
            self.assertGreater(contexts,10)
            keepers=db.execute("""SELECT x.overall,c.squad_role_estimate
                FROM world_career_live_player_context c
                JOIN world_players p ON p.player_id=c.player_id
                JOIN world_career_registrations r ON r.player_id=c.player_id
                   AND r.career_id=c.career_id
                JOIN world_dataset_ratings x ON x.player_id=c.player_id
                   AND x.dataset_id=(SELECT dataset_id
                       FROM world_career_saves WHERE career_id=c.career_id)
                WHERE c.career_id=? AND p.primary_position='GK'
                ORDER BY x.overall DESC,c.player_id""",(CAREER,)).fetchall()
            if keepers:
                self.assertIn(keepers[0][1],("key_player","regular_starter"))
            if len(keepers)>=2:
                self.assertEqual(keepers[1][1],"rotation")
            if len(keepers)>=3:
                self.assertEqual(keepers[2][1],"fringe")
            self.assertEqual(db.execute("""SELECT COUNT(*)
                FROM world_career_market_inbox
                WHERE career_id=?""",(CAREER,)).fetchone()[0],1)
            token=db.execute("""SELECT spectator_token
                FROM world_career_live_market_access""").fetchone()[0]
        self.assertGreater(len(token),25)
        again=self.client.post(url,data={"csrf":self.csrf,
            "confirm":"start-30-minute-window"},
            base_url="https://localhost")
        self.assertEqual(again.status_code,302)
        with self.connect_db() as db:
            self.assertEqual(db.execute("""SELECT COUNT(*)
                FROM world_career_preseason_windows""").fetchone()[0],1)
            self.assertEqual(db.execute("""SELECT COUNT(*)
                FROM world_career_market_inbox""").fetchone()[0],1)
        self.__class__.token=token

    def test_market_money_formatting(self):
        from world_career_play import format_market_gbp
        from world_live_market import _market_money
        expected={0:"£0",950:"£950",125_000:"£125k",
                  1_250_000:"£1.25m",12_345_678:"£12.35m",
                  -2_000_000:"-£2.00m"}
        for amount,display in expected.items():
            with self.subTest(amount=amount):
                self.assertEqual(format_market_gbp(amount),display)
                self.assertEqual(_market_money(amount),display)

    def test_01b_scouting_filters_and_budget_preview(self):
        from world_scouting import scouting_search,scouting_attributes
        url=f"/world/play/career/{CAREER}/market"
        page=self.client.get(url,base_url="https://localhost")
        self.assertEqual(page.status_code,200)
        html=page.get_data(as_text=True)
        self.assertIn("Scouting &amp; squad values",html)
        self.assertIn('id="budget-panel"',html)
        self.assertIn('data-budget-fee',html)
        self.assertNotIn("Share this read-only link",html)
        with self.connect_db() as db:
            attrs=scouting_attributes(db,career_id=CAREER)
            squad=scouting_search(db,career_id=CAREER,squad_only=True,limit=80)
            self.assertTrue(squad)
            self.assertTrue(all(p["owned"] for p in squad))
            self.assertTrue(all(p["market_value"] is None or
                                p["market_value"]>0 for p in squad))
            rated=scouting_search(db,career_id=CAREER,min_overall=80,limit=80)
            self.assertTrue(all(p["overall"]>=80 for p in rated))
            max_age=scouting_search(db,career_id=CAREER,max_age=23,limit=80)
            self.assertTrue(all(p["age"] is not None and p["age"]<=23
                                for p in max_age))
            expiring=scouting_search(db,career_id=CAREER,contract="expiring")
            self.assertTrue(all(p["years_left"] is not None and
                                p["years_left"]<=1.0 for p in expiring))
            if attrs:
                specific=scouting_search(db,career_id=CAREER,
                                         attribute=attrs[0],min_attribute=70)
                self.assertTrue(all(p["detail_attribute"] is not None
                                    and p["detail_attribute"]>=70
                                    for p in specific))
        filtered=self.client.get(url+"?scout_min_overall=80&scout_squad=1",
                                 base_url="https://localhost")
        self.assertEqual(filtered.status_code,200)
        self.assertIn("Scouting &amp; squad values",
                      filtered.get_data(as_text=True))

    def test_01c_scout_profile_shortlist_and_sort(self):
        from world_scouting import scouting_search
        base=f"/world/play/career/{CAREER}/market"
        with self.connect_db() as db:
            initial=scouting_search(db,career_id=CAREER,sort_by="overall")
            self.assertGreater(len(initial),0)
            self.assertEqual([x["overall"] for x in initial],
                             sorted([x["overall"] for x in initial],reverse=True))
            reverse=scouting_search(db,career_id=CAREER,sort_by="overall",
                                    descending=False)
            self.assertEqual([x["overall"] for x in reverse],
                             sorted([x["overall"] for x in reverse]))
            player=initial[0]
            pid=player["player_id"]
        profile=self.client.get(base+f"/player/{pid}",base_url="https://localhost")
        self.assertEqual(profile.status_code,200)
        self.assertIn("Estimated weekly wage expectation",
                      profile.get_data(as_text=True))
        saved=self.client.post(base+"/shortlist",data={
            "csrf":self.csrf,"player_id":str(pid),"action":"save"},
            base_url="https://localhost")
        self.assertEqual(saved.status_code,302)
        with self.connect_db() as db:
            shortlist=scouting_search(db,career_id=CAREER,shortlist_only=True)
            self.assertIn(pid,[p["player_id"] for p in shortlist])
        listed=self.client.get(base+"?scout_shortlist=1",
                               base_url="https://localhost")
        self.assertEqual(listed.status_code,200)
        self.assertIn(player["full_name"],listed.get_data(as_text=True))
        removed=self.client.post(base+"/shortlist",data={
            "csrf":self.csrf,"player_id":str(pid),"action":"remove"},
            base_url="https://localhost")
        self.assertEqual(removed.status_code,302)
        with self.connect_db() as db:
            shortlist=scouting_search(db,career_id=CAREER,shortlist_only=True)
            self.assertNotIn(pid,[p["player_id"] for p in shortlist])
        unauthed=self.app.test_client().post(base+"/shortlist",data={
            "csrf":self.csrf,"player_id":str(pid),"action":"save"},
            base_url="https://localhost")
        self.assertEqual(unauthed.status_code,403)

    def test_01d_recruitment_shortlist_and_direct_bid_form(self):
        from world_scouting import recruitment_recommendations,scouting_search
        base=f"/world/play/career/{CAREER}/market"
        with self.connect_db() as db:
            results=recruitment_recommendations(db,career_id=CAREER,limit=8)
            self.assertLessEqual(len(results),8)
            funds=db.execute("""SELECT transfer_budget-committed_fees
                FROM world_career_club_ledger WHERE career_id=?
                AND club_id=(SELECT manager_club_id FROM world_career_saves
                              WHERE career_id=?)""",(CAREER,CAREER)).fetchone()[0]
            self.assertTrue(all(p["market_value"]<=funds for p in results))
            targets=scouting_search(db,career_id=CAREER,limit=100)
            target=next(p for p in targets if not p["owned"])
        page=self.client.get(base,base_url="https://localhost")
        self.assertEqual(page.status_code,200)
        body=page.get_data(as_text=True)
        self.assertIn("Scouting &amp; squad values",body)
        self.assertIn("My transfer shortlist",body)
        self.assertNotIn("<h3>Suggested targets</h3>",body)
        profile=self.client.get(base+f"/player/{target['player_id']}",
                                base_url="https://localhost")
        self.assertEqual(profile.status_code,200)
        report=profile.get_data(as_text=True)
        self.assertIn("Approach to buy",report)
        self.assertIn('name="request_key"',report)
        self.assertIn('name="offered_fee"',report)
        self.assertIn('name="player_id"',report)
        self.assertIn("After this proposed bid:",report)

    def test_02_autonomous_bids_and_read_only_squad(self):
        # Fast-forward a disposable TEST clock; the real site never offers
        # this ability to a manager or a spectator.
        now=datetime.now(timezone.utc)
        with self.connect_db() as db:
            started=now-timedelta(minutes=7)
            db.execute("""UPDATE world_career_preseason_windows
                SET started_at=?,deadline_at=? WHERE career_id=?""",
                (started.isoformat(timespec="seconds"),
                 (started+timedelta(minutes=30)).isoformat(timespec="seconds"),
                 CAREER))
            db.commit()
        url="/world/play/career/"+CAREER+"/market"
        first=self.client.get(url,base_url="https://localhost")
        self.assertEqual(first.status_code,200)
        html=first.get_data(as_text=True)
        self.assertIn("Manager's Inbox",html)
        self.assertIn("Indicative market value:",html)
        self.assertIn("Bid versus valuation:",html)
        with self.connect_db() as db:
            slots=db.execute("""SELECT COUNT(*) FROM world_career_market_moments""").fetchone()[0]
            self.assertGreater(slots,1)
            news=market_messages(db,career_id=CAREER)
            self.assertTrue(any(m["headline"]=="The summer transfer window is open"
                                for m in news))
            offers=db.execute("""SELECT offer_id,offered_fee,status FROM
                world_career_offers WHERE request_key LIKE 'live-v1-%'""").fetchall()
            self.assertTrue(offers,"Real seeded Forest squad should attract a qualifying bid")
            self.assertTrue(all(o["status"]=="proposed" for o in offers))
            from world_live_market import _modelled_europe
            context=db.execute("""SELECT buyer_europe,seller_europe,source_kind,
                o.buying_club_id,o.selling_club_id
                FROM world_career_offer_europe e
                JOIN world_career_offers o ON o.offer_id=e.offer_id
                WHERE o.offer_id=?""",(offers[0]["offer_id"],)).fetchone()
            self.assertIsNotNone(context)
            self.assertEqual(context["source_kind"],
                             "fictional-preseason-prestige-seeding-v1")
            self.assertEqual(context["buyer_europe"],_modelled_europe(
                db,career_id=CAREER,club_id=context["buying_club_id"]))
            self.assertEqual(context["seller_europe"],_modelled_europe(
                db,career_id=CAREER,club_id=context["selling_club_id"]))
            self.assertIn(context["buyer_europe"],(
                "none","conference_league","europa_league",
                "champions_league","unknown"))
            count=len(offers)
            ai_before=db.execute("""SELECT COUNT(*) FROM
                world_career_ai_world_moments WHERE window_id=(
                  SELECT window_id FROM world_career_preseason_windows
                  WHERE career_id=?)""",(CAREER,)).fetchone()[0]
            self.assertGreaterEqual(ai_before,slots)
            # Realism v2 schedules 5–18 independent world-market checks
            # per due moment while preserving historical checkpoint IDs.
            self.assertLessEqual(ai_before,slots*18)
            ai_signed=db.execute("""SELECT o.offer_id,o.player_id,o.selling_club_id,
                    o.buying_club_id,o.status,t.status AS agent_status
                FROM world_career_offers o
                JOIN world_career_offer_events e ON e.offer_id=o.offer_id
                LEFT JOIN world_career_agent_terms t ON t.offer_id=o.offer_id
                WHERE o.career_id=? AND e.event_type='ai_world_signed'""",
                (CAREER,)).fetchall()
            managed=db.execute("""SELECT manager_club_id FROM world_career_saves
                WHERE career_id=?""",(CAREER,)).fetchone()[0]
            for deal in ai_signed:
                self.assertNotEqual(deal["selling_club_id"],managed)
                self.assertNotEqual(deal["buying_club_id"],managed)
                self.assertEqual(deal["status"],"agreed_future")
                self.assertEqual(deal["agent_status"],"accepted")
        second=self.client.get(url,base_url="https://localhost")
        self.assertEqual(second.status_code,200)
        with self.connect_db() as db:
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM
                world_career_offers WHERE request_key LIKE 'live-v1-%'""").fetchone()[0],count)
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM
                world_career_market_moments""").fetchone()[0],slots)
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM
                world_career_ai_world_moments""").fetchone()[0],ai_before)
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM
                world_career_offer_events WHERE event_type='ai_world_signed'"""
                ).fetchone()[0],len(ai_signed))
            self.__class__.offer_id=offers[0]["offer_id"]
        spectator=self.app.test_client().get("/world/play/watch/"+self.token,
                                            base_url="https://localhost")
        text=spectator.get_data(as_text=True)
        self.assertEqual(spectator.status_code,200)
        self.assertIn("Read only",text)
        self.assertIn("Manager's Inbox",text)
        self.assertNotIn("Accept fee</button>",text)
        self.assertNotIn("Reject</button>",text)
        self.assertNotIn("csrf",text)
        self.assertIn("no-store",spectator.headers["Cache-Control"])
        unauth=self.app.test_client().post(url+"/decision",
            data=dict(csrf=self.csrf,offer_id=self.offer_id,decision="reject"),
            base_url="https://localhost")
        self.assertIn(unauth.status_code,(302,403))

    def test_02a_inbox_preserves_forms_inside_groupable_offer_cards(self):
        url=f"/world/play/career/{CAREER}/market"
        response=self.client.get(url,base_url="https://localhost")
        self.assertEqual(response.status_code,200)
        html=response.get_data(as_text=True)
        self.assertIn('data-window-state="open"',html)
        self.assertIn('data-desk-player="',html)
        self.assertIn('data-desk-player-name="',html)
        self.assertIn('data-desk-status="',html)
        self.assertIn("desk-grouped-offer",html)
        self.assertIn("data-desk-filter-player=",html)
        self.assertIn("Action needed",html)
        self.assertIn("Find a player or buying club",html)
        self.assertIn("Cancel transfer",html)
        self.assertIn("name=\"csrf\"",html)
        self.assertIn('action="/world/play/career/'+CAREER+'/market/decision"',html)

    def test_02b_manager_can_search_and_bid_to_buy_without_seller_questionnaire(self):
        from urllib.parse import quote
        from world_careers import _player_reference
        from world_live_buying import manager_targets
        # Use real seeded players, not invented records; find a low-division
        # fringe player to keep Forest's test transfer budget realistic.
        with self.connect_db() as db:
            rows=db.execute("""WITH ranked AS (
              SELECT r.player_id,p.full_name,r.club_id,x.overall,c.tier,
                ROW_NUMBER() OVER (PARTITION BY r.club_id
                   ORDER BY x.overall DESC,r.player_id) AS squad_rank
              FROM world_career_registrations r
              JOIN world_career_saves s ON s.career_id=r.career_id
              JOIN world_players p ON p.player_id=r.player_id
              JOIN world_dataset_ratings x ON x.dataset_id=s.dataset_id
                 AND x.player_id=r.player_id
              JOIN world_dataset_entries e ON e.dataset_id=s.dataset_id
                 AND e.club_id=r.club_id
              JOIN world_competitions c ON c.competition_id=e.competition_id
              WHERE r.career_id=? AND x.overall IS NOT NULL)
              SELECT player_id,full_name,overall FROM ranked
              WHERE tier>=3 AND squad_rank>=17 AND overall BETWEEN 50 AND 72
              ORDER BY overall ASC,player_id LIMIT 60""",(CAREER,)).fetchall()
            candidates=[]
            for p in rows:
                value,_=_player_reference(db,DATASET,p["player_id"])
                if value is not None and 0<value<1_000_000:
                    candidates.append((p["player_id"],p["full_name"],value))
            self.assertTrue(candidates,"Need a real rated and affordable squad candidate")
            target_id,name,value=candidates[0]
        q=name[:min(12,len(name))]
        page=self.client.get(f"/world/play/career/{CAREER}/market?player_search="+quote(q),
                             base_url="https://localhost")
        self.assertEqual(page.status_code,200)
        markup=page.get_data(as_text=True)
        self.assertNotIn('id="buy-players"',markup)
        self.assertIn('id="scouting"',markup)
        profile=self.client.get(
            f"/world/play/career/{CAREER}/market/player/{target_id}",
            base_url="https://localhost")
        self.assertEqual(profile.status_code,200)
        self.assertIn("Approach to buy",profile.get_data(as_text=True))
        self.assertIn("Submit transfer offer",profile.get_data(as_text=True))
        self.assertNotIn("Lock seller circumstances",markup)
        with self.connect_db() as db:
            self.assertIn(target_id,[p["player_id"] for p in
                manager_targets(db,career_id=CAREER,query=q)])
        fee=int(value*1.4)+1000
        key="manager-buy-v1-isolated-http-" + str(target_id)
        url=f"/world/play/career/{CAREER}/market/buy"
        posted=self.client.post(url,data=dict(csrf=self.csrf,
            player_id=target_id,offered_fee=fee,request_key=key),
            base_url="https://localhost")
        self.assertEqual(posted.status_code,302)
        self.assertNotIn("error=",posted.headers["Location"],posted.headers["Location"])
        with self.connect_db() as db:
            row=db.execute("""SELECT offer_id,status,buying_club_id
                FROM world_career_offers WHERE career_id=? AND request_key=?""",
                (CAREER,key)).fetchone()
            self.assertIsNotNone(row)
            self.assertIn(row["status"],(
                "accepted_pending_contract","countered","rejected"))
            buyer=db.execute("""SELECT manager_club_id FROM world_career_saves
                WHERE career_id=?""",(CAREER,)).fetchone()[0]
            self.assertEqual(row["buying_club_id"],buyer)
            recorded=db.execute("""SELECT source_note FROM
                world_career_seller_assumptions WHERE career_id=? AND player_id=?""",
                (CAREER,target_id)).fetchone()
            self.assertIsNotNone(recorded)
            self.assertIn("fictional-autonomous-seller",recorded[0])
            self.assertEqual(db.execute("""SELECT source_kind FROM
                world_career_player_circumstances
                WHERE career_id=? AND player_id=?""",
                (CAREER,target_id)).fetchone()[0],
                "fictional-autonomous-seller-v1")
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM
                world_career_preseason_window_offers WHERE offer_id=?""",
                (row["offer_id"],)).fetchone()[0],1)
            self.__class__.buy_offer_id=row["offer_id"]
        visible=self.client.get(f"/world/play/career/{CAREER}/market",
                                base_url="https://localhost").get_data(as_text=True)
        self.assertIn("Transfer Centre",visible)
        self.assertIn(name,visible)
        spectator=self.app.test_client().get("/world/play/watch/"+self.token,
                          base_url="https://localhost").get_data(as_text=True)
        self.assertIn("Transfer Centre",spectator)
        self.assertNotIn("Submit transfer offer",spectator)
        again=self.client.post(url,data=dict(csrf=self.csrf,
            player_id=target_id,offered_fee=fee,request_key=key),
            base_url="https://localhost")
        self.assertEqual(again.status_code,302)
        with self.connect_db() as db:
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM world_career_offers
               WHERE career_id=? AND request_key=?""",(CAREER,key)).fetchone()[0],1)

    def test_02c_manager_can_offer_listed_outfield_player_to_clubs_once(self):
        base=f"/world/play/career/{CAREER}/market"
        from world_squad_desk import squad_preview
        from world_ai_bidding import position_family
        with self.connect_db() as db:
            roster=squad_preview(db,career_id=CAREER)["players"]
            available=[p for p in roster if not p["incoming"] and
                       position_family(p["position"])!="GK"]
            self.assertTrue(available)
            player=available[-1]
            pid=player["player_id"]
            original=db.execute("""SELECT squad_role_estimate,transfer_listed_estimate
                FROM world_career_live_player_context
                WHERE career_id=? AND player_id=?""",(CAREER,pid)).fetchone()
            before=db.execute("""SELECT COUNT(*) FROM world_career_offers
                WHERE career_id=?""",(CAREER,)).fetchone()[0]
        url=base+"/squad/decision"
        posted=self.client.post(url,data={
            "csrf":self.csrf,"player_id":pid,"role":"fringe",
            "listed":"1","action":"offer"},base_url="https://localhost")
        self.assertEqual(posted.status_code,302)
        self.assertNotIn("error=",posted.headers["Location"])
        with self.connect_db() as db:
            instruction=db.execute("""SELECT current_role,transfer_listed
                FROM world_career_player_circumstances
                WHERE career_id=? AND player_id=?""",(CAREER,pid)).fetchone()
            self.assertEqual(tuple(instruction),("fringe",1))
            ctx=db.execute("""SELECT squad_role_estimate,transfer_listed_estimate
                FROM world_career_live_player_context
                WHERE career_id=? AND player_id=?""",(CAREER,pid)).fetchone()
            self.assertEqual(tuple(ctx),("fringe",1))
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM
                world_career_squad_outreach
                WHERE career_id=? AND player_id=?""",(CAREER,pid)).fetchone()[0],1)
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM world_career_offers
                WHERE career_id=?""",(CAREER,)).fetchone()[0],before)
        duplicate=self.client.post(url,data={
            "csrf":self.csrf,"player_id":pid,"role":"fringe",
            "listed":"1","action":"offer"},base_url="https://localhost")
        self.assertIn("error=",duplicate.headers["Location"])
        with self.connect_db() as db:
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM
                world_career_squad_outreach
                WHERE career_id=? AND player_id=?""",(CAREER,pid)).fetchone()[0],1)
            if original:
                db.execute("""UPDATE world_career_live_player_context
                    SET squad_role_estimate=?,transfer_listed_estimate=?
                    WHERE career_id=? AND player_id=?""",
                    (original[0],original[1],CAREER,pid))
            db.execute("""DELETE FROM world_career_player_circumstances
                WHERE career_id=? AND player_id=?""",(CAREER,pid))
            db.commit()

    def test_02d_buying_manager_can_negotiate_seller_counter(self):
        base=f"/world/play/career/{CAREER}/market"
        with self.connect_db() as db:
            offer=db.execute("""SELECT offer_id,offered_fee FROM world_career_offers
                WHERE career_id=? AND request_key LIKE
                  'manager-buy-v1-isolated-http-%' LIMIT 1""",(CAREER,)).fetchone()
            self.assertIsNotNone(offer)
            oid,previous=offer
            ask=int(previous*1.8)+1000
            db.execute("""UPDATE world_career_offers
                SET status='countered',demanded_fee=? WHERE offer_id=?""",
                (ask,oid))
            db.commit()
        revised=(previous+ask)//2
        r=self.client.post(base+"/buy/decision",data={
            "csrf":self.csrf,"offer_id":oid,
            "decision":"negotiate_counter","negotiated_fee":revised},
            base_url="https://localhost")
        self.assertEqual(r.status_code,302)
        self.assertNotIn("error=",r.headers["Location"],r.headers["Location"])
        with self.connect_db() as db:
            state=db.execute("""SELECT status,offered_fee,demanded_fee
                FROM world_career_offers WHERE offer_id=?""",(oid,)).fetchone()
            self.assertEqual(state["offered_fee"],revised)
            self.assertIn(state["status"],("countered","accepted_pending_contract"))
            self.assertEqual(db.execute("""SELECT COUNT(*)
               FROM world_career_offer_events WHERE offer_id=?
                 AND event_type='buyer_revised_bid'""",(oid,)).fetchone()[0],1)
        visible=self.client.get(base,base_url="https://localhost").get_data(as_text=True)
        self.assertIn("Transfer Centre",visible)
        self.assertIn("Outgoing bids",visible)

    def test_02e_second_revision_and_invalid_bid_are_safely_handled(self):
        base=f"/world/play/career/{CAREER}/market"
        with self.connect_db() as db:
            row=db.execute("""SELECT offer_id,offered_fee,demanded_fee,status
                FROM world_career_offers
                WHERE career_id=? AND request_key LIKE
                  'manager-buy-v1-isolated-http-%' LIMIT 1""",(CAREER,)).fetchone()
            self.assertIsNotNone(row)
        oid,prior,counter,status=row
        if status=="countered" and counter is not None and counter>prior+2:
            too_low=self.client.post(base+"/buy/decision",data={
                "csrf":self.csrf,"offer_id":oid,
                "decision":"negotiate_counter","negotiated_fee":prior},
                base_url="https://localhost")
            self.assertIn("error=",too_low.headers["Location"])
            close=counter-1
            response=self.client.post(base+"/buy/decision",data={
                "csrf":self.csrf,"offer_id":oid,
                "decision":"negotiate_counter","negotiated_fee":close},
                base_url="https://localhost")
            self.assertEqual(response.status_code,302)
            self.assertNotIn("error=",response.headers["Location"])
            with self.connect_db() as db:
                revised=db.execute("""SELECT status,offered_fee
                    FROM world_career_offers WHERE offer_id=?""",
                    (oid,)).fetchone()
                self.assertEqual(revised[1],close)
                self.assertIn(revised[0],
                    ("accepted_pending_contract","countered"))
        else:
            self.assertIn(status,("accepted_pending_contract","countered"))

    def test_02f_rejected_player_links_and_improved_rebid(self):
        base=f"/world/play/career/{CAREER}/market"
        with self.connect_db() as db:
            original=db.execute("""SELECT offer_id,player_id,offered_fee
                FROM world_career_offers
                WHERE career_id=? AND request_key LIKE
                  'manager-buy-v1-isolated-http-%' LIMIT 1""",
                (CAREER,)).fetchone()
            oid,pid,prior=original
            db.execute("""UPDATE world_career_offers
                SET status='rejected',demanded_fee=NULL WHERE offer_id=?""",(oid,))
            db.commit()
        page=self.client.get(base,base_url="https://localhost").get_data(as_text=True)
        self.assertIn(f'/market/player/{pid}',page)
        self.assertIn("Make new offer",page)
        low=self.client.post(base+"/buy/rebid",data={"csrf":self.csrf,
            "offer_id":oid,"offered_fee":prior},base_url="https://localhost")
        self.assertIn("error=",low.headers["Location"])
        improved=prior+max(1000,prior//10)
        revised=self.client.post(base+"/buy/rebid",data={"csrf":self.csrf,
            "offer_id":oid,"offered_fee":improved},base_url="https://localhost")
        self.assertEqual(revised.status_code,302)
        self.assertNotIn("error=",revised.headers["Location"],revised.headers["Location"])
        with self.connect_db() as db:
            follow=db.execute("""SELECT offer_id,offered_fee FROM world_career_offers
                WHERE career_id=? AND request_key LIKE 'manager-buy-v1-rebid-%'
                ORDER BY offer_id DESC LIMIT 1""",(CAREER,)).fetchone()
            self.assertIsNotNone(follow)
            self.assertEqual(follow["offered_fee"],improved)

    def test_02g_agreed_fee_can_request_agent_opening_quote(self):
        from world_live_buying import act_on_buy_offer
        from world_live_buying import _agent_opening_quote
        with self.connect_db() as db:
            original=db.execute("""SELECT offer_id FROM world_career_offers
                WHERE career_id=? AND request_key LIKE
                  'manager-buy-v1-rebid-%' ORDER BY offer_id DESC LIMIT 1""",
                (CAREER,)).fetchone()
            self.assertIsNotNone(original)
            oid=original[0]
            db.execute("""UPDATE world_career_offers
                SET status='accepted_pending_contract',demanded_fee=NULL
                WHERE offer_id=?""",(oid,))
            db.commit()
            # The existing agent may reject talks for sporting reasons.
            # Confirm that no guessed default wage is offered in the UI,
            # and that requesting a quote is a deliberate supported action.
        page=self.client.get(f"/world/play/career/{CAREER}/market",
                             base_url="https://localhost").get_data(as_text=True)
        self.assertTrue("Request agent's opening wage" in page or
                        "Agent opening request:" in page,
                        "A negotiation must show an agent opening wage or an explicit quote request")
        self.assertNotIn('value="20000" required',page)

    def test_03_manager_decides_without_questionnaire(self):
        path=f"/world/play/career/{CAREER}/market/decision"
        result=self.client.post(path,data=dict(csrf=self.csrf,
            offer_id=self.offer_id,decision="reject"),
            base_url="https://localhost")
        self.assertEqual(result.status_code,302)
        self.assertNotIn("error=",result.headers["Location"])
        with self.connect_db() as db:
            o=db.execute("""SELECT status FROM world_career_offers
                WHERE offer_id=?""",(self.offer_id,)).fetchone()
            self.assertEqual(o["status"],"rejected")
            events=db.execute("""SELECT event_type FROM world_career_offer_events
                WHERE offer_id=?""",(self.offer_id,)).fetchall()
            self.assertIn("manager_rejected",[r[0] for r in events])
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM
                world_career_preseason_registration_events""").fetchone()[0],0)

    def test_03b_accepted_fee_enters_independent_agent_talks(self):
        path=f"/world/play/career/{CAREER}/market/decision"
        with self.connect_db() as db:
            bid=db.execute("""SELECT offer_id FROM world_career_offers
                WHERE career_id=? AND status='proposed'
                  AND request_key LIKE 'live-v1-%'
                ORDER BY offer_id LIMIT 1""",(CAREER,)).fetchone()
            self.assertIsNotNone(bid,"At least two rated-squad bids expected in seeded market")
            oid=bid[0]
        accepted=self.client.post(path,data=dict(csrf=self.csrf,
            offer_id=oid,decision="accept"),base_url="https://localhost")
        self.assertEqual(accepted.status_code,302)
        self.assertNotIn("error=",accepted.headers["Location"])
        with self.connect_db() as db:
            self.assertEqual(db.execute("""SELECT status FROM world_career_offers
                WHERE offer_id=?""",(oid,)).fetchone()[0],"accepted_pending_contract")
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM
                world_career_preseason_registration_events""").fetchone()[0],0)
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM
                world_career_offer_events WHERE offer_id=?
                  AND event_type='human_fee_accepted'""",(oid,)).fetchone()[0],1)
            t=datetime.now(timezone.utc)
            db.execute("""UPDATE world_career_preseason_windows SET started_at=?,
                deadline_at=? WHERE career_id=?""",
                ((t-timedelta(minutes=14)).isoformat(timespec="seconds"),
                 (t+timedelta(minutes=16)).isoformat(timespec="seconds"),
                 CAREER))
            db.commit()
        page=self.client.get(f"/world/play/career/{CAREER}/market",
            base_url="https://localhost")
        self.assertEqual(page.status_code,200)
        with self.connect_db() as db:
            # Player/agent may accept, counter or refuse. No simulated
            # agent step alone may sign the sale without manager consent.
            state=db.execute("""SELECT status,decision_reason
                FROM world_career_incoming_approaches
                WHERE offer_id=?""",(oid,)).fetchone()
            self.assertIsNotNone(state)
            self.assertIn(state[0],(
                "player_refused","role_refused","wage_limit",
                "agent_counter","terms_accepted","needs_information"))
            self.assertNotEqual(db.execute("""SELECT status FROM world_career_offers
                WHERE offer_id=?""",(oid,)).fetchone()[0],"completed")
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM
                world_career_preseason_registration_events""").fetchone()[0],0)
        self.__class__.accepted_offer_id=oid

    def test_03c_manager_counter_forces_ai_buyer_to_respond_later(self):
        path=f"/world/play/career/{CAREER}/market/decision"
        with self.connect_db() as db:
            bid=db.execute("""SELECT offer_id,offered_fee
                FROM world_career_offers WHERE career_id=? AND status='proposed'
                 AND request_key LIKE 'live-v1-%' ORDER BY offer_id LIMIT 1""",
                (CAREER,)).fetchone()
            self.assertIsNotNone(bid,"At least one other credible bid expected")
            oid,fee=bid[0],bid[1]
            asked=fee+max(5000,fee//10)
        countered=self.client.post(path,data=dict(csrf=self.csrf,
            offer_id=oid,decision="counter",counter_fee=str(asked)),
            base_url="https://localhost")
        self.assertEqual(countered.status_code,302)
        self.assertNotIn("error=",countered.headers["Location"])
        with self.connect_db() as db:
            self.assertEqual(tuple(db.execute("""SELECT status,demanded_fee
                FROM world_career_offers WHERE offer_id=?""",(oid,)).fetchone()),
                ("countered",asked))
            t=datetime.now(timezone.utc)
            db.execute("""UPDATE world_career_preseason_windows SET started_at=?,
                deadline_at=? WHERE career_id=?""",
                ((t-timedelta(minutes=21)).isoformat(timespec="seconds"),
                 (t+timedelta(minutes=9)).isoformat(timespec="seconds"),CAREER))
            db.commit()
        page=self.client.get(f"/world/play/career/{CAREER}/market",
            base_url="https://localhost")
        self.assertEqual(page.status_code,200)
        with self.connect_db() as db:
            state=db.execute("SELECT status FROM world_career_offers WHERE offer_id=?",
                             (oid,)).fetchone()[0]
            # A buyer may accept the fee and still lose the player later:
            # an independent player refusal correctly ends as 'withdrawn'.
            self.assertIn(state,("accepted_pending_contract","rejected","withdrawn"))
            history=[r[0] for r in db.execute("""SELECT event_type
                FROM world_career_offer_events WHERE offer_id=?""",(oid,))]
            self.assertTrue(any(v.startswith("ai_counter_") for v in history))
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM
                world_career_preseason_registration_events""").fetchone()[0],0)

    def test_03d_legacy_manual_apis_blocked_and_inbox_read_tracking(self):
        base=f"/world/play/career/{CAREER}"
        # Timed-career players cannot bypass the autonomous inbox by
        # invoking development-only seller or AI-simulation endpoints.
        for path in ("/ai-inbound","/selling/circumstances",
                     "/management/contract"):
            result=self.client.post(base+path,
                data={"csrf":self.csrf,"player_id":"101"},
                base_url="https://localhost")
            self.assertEqual(result.status_code,403,path)
        for path in ("/management","/selling"):
            result=self.client.get(base+path,base_url="https://localhost")
            self.assertEqual(result.status_code,302)
            self.assertIn(base+"/market",result.headers["Location"])
        unauthorized=self.app.test_client().post(base+"/market/read",
            data={"csrf":self.csrf},base_url="https://localhost")
        self.assertEqual(unauthorized.status_code,403)
        self.assertIn(self.client.post(base+"/market/read",
             data={"csrf":self.csrf},
             base_url="https://localhost").status_code,(302,))
        with self.connect_db() as db:
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM
                world_career_market_inbox WHERE career_id=? AND is_read=0""",
                (CAREER,)).fetchone()[0],0)

    def test_03e_competing_offers_and_cancel_unsigned_transfer(self):
        from world_career_incoming import competing_player_choice
        url=f"/world/play/career/{CAREER}/market"
        html=self.client.get(url,base_url="https://localhost").get_data(as_text=True)
        self.assertIn("Cancel transfer",html)
        self.assertIn("Finalise transfer",html) if (
            'value="finalise"' in html) else None
        with self.connect_db() as db:
            target=db.execute("""SELECT o.offer_id,o.player_id
                FROM world_career_offers o
                WHERE o.career_id=? AND o.status='accepted_pending_contract'
                AND o.selling_club_id=(SELECT manager_club_id
                    FROM world_career_saves WHERE career_id=?)
                ORDER BY o.offer_id LIMIT 1""",(CAREER,CAREER)).fetchone()
            if target:
                # Competing player-choice evaluation must never silently
                # sign a transfer or move the player.
                before=db.execute("""SELECT club_id FROM world_career_registrations
                    WHERE career_id=? AND player_id=?""",
                    (CAREER,target["player_id"])).fetchone()[0]
                outcome=competing_player_choice(db,career_id=CAREER,
                                                offer_id=target["offer_id"])
                self.assertIn(outcome["decision"],("ready","delayed","refused"))
                self.assertEqual(db.execute("""SELECT club_id FROM
                    world_career_registrations WHERE career_id=? AND player_id=?""",
                    (CAREER,target["player_id"])).fetchone()[0],before)
                oid=target["offer_id"]
            else:
                oid=self.offer_id
        result=self.client.post(url+"/decision",data=dict(
            csrf=self.csrf,offer_id=oid,decision="cancel"),
            base_url="https://localhost")
        self.assertEqual(result.status_code,302)
        self.assertNotIn("error=",result.headers["Location"])
        with self.connect_db() as db:
            status=db.execute("""SELECT status FROM world_career_offers
                 WHERE offer_id=?""",(oid,)).fetchone()[0]
            self.assertEqual(status,"withdrawn")
        second=self.client.post(url+"/decision",data=dict(
            csrf=self.csrf,offer_id=oid,decision="finalise"),
            base_url="https://localhost")
        self.assertIn("error=",second.headers["Location"])

    def test_03f_late_market_moments_and_goalkeeper_balance(self):
        from world_live_market import MARKET_MOMENTS
        from world_preseason_window import window_snapshot
        t=datetime.now(timezone.utc)
        with self.connect_db() as db:
            db.execute("""UPDATE world_career_preseason_windows
                SET started_at=?,deadline_at=? WHERE career_id=?""",
                ((t-timedelta(seconds=1790)).isoformat(timespec="seconds"),
                 (t+timedelta(seconds=10)).isoformat(timespec="seconds"),
                 CAREER))
            db.commit()
        # Processing the backlog of 112 independent opportunities takes
        # real wall time in CI. Freeze ONLY this disposable HTTP test clock
        # at ten seconds before the deadline, so an initially open market
        # cannot age into a closed one halfway through a test request.
        import world_preseason_window as clock_module
        import world_live_market as live_module
        actual_utc=clock_module._utc
        def frozen_utc(now=None):
            return actual_utc(t if now is None else now)
        with patch.object(clock_module,"_utc",side_effect=frozen_utc), \
             patch.object(live_module,"_utc",side_effect=frozen_utc):
            page=self.client.get(f"/world/play/career/{CAREER}/market",
                                 base_url="https://localhost")
        self.assertEqual(page.status_code,200)
        html=page.get_data(as_text=True)
        self.assertIn('data-window-state="open"',html)
        # Restore a real, consistent 30-minute countdown with enough room
        # for subsequent player-unrest and deadline-registration tests.
        now=datetime.now(timezone.utc)
        with self.connect_db() as db:
            db.execute("""UPDATE world_career_preseason_windows
                SET started_at=?,deadline_at=? WHERE career_id=?""",
                ((now-timedelta(minutes=25)).isoformat(timespec="seconds"),
                 (now+timedelta(minutes=5)).isoformat(timespec="seconds"),
                 CAREER))
            db.commit()
            moments=db.execute("""SELECT COUNT(*)
                FROM world_career_market_moments""").fetchone()[0]
            self.assertEqual(moments,len(MARKET_MOMENTS))
            attempts=db.execute("""SELECT COUNT(*) FROM
                world_career_ai_world_moments WHERE window_id=(
                SELECT window_id FROM world_career_preseason_windows
                WHERE career_id=?)""",(CAREER,)).fetchone()[0]
            self.assertGreater(attempts,moments,
                "Late window should expose several independent AI deal opportunities")
            world_signed=db.execute("""SELECT COUNT(DISTINCT o.offer_id)
                FROM world_career_offers o
                JOIN world_career_offer_events e ON e.offer_id=o.offer_id
                WHERE o.career_id=? AND e.event_type='ai_world_signed'""",
                (CAREER,)).fetchone()[0]
            print(f"SEEDED_AI_WORLD_DEALS={world_signed};WORLD_ATTEMPTS={attempts}")
            self.assertGreater(world_signed,5,
                "A multi-league window should not remain stuck at five world signings")
            keeper_world=db.execute("""SELECT COUNT(*) FROM world_career_offer_events e
                JOIN world_career_offers o ON o.offer_id=e.offer_id
                JOIN world_players p ON p.player_id=o.player_id
                WHERE o.career_id=? AND e.event_type='ai_world_signed'
                AND p.primary_position='GK'""",(CAREER,)).fetchone()[0]
            print(f"AI_WORLD_KEEPER_SIGNINGS={keeper_world};OUTFIELD_SIGNINGS={world_signed-keeper_world}")
            self.assertLessEqual(keeper_world,max(2,world_signed//3),
                "Goalkeepers should no longer dominate all completed market transfers")
            # FC27 and current live markets deliberately have NO global
            # incoming or GK deal quota. Test real routing/ledger identity,
            # not removed arbitrary cap constants from a legacy prototype.
            incoming=db.execute("""SELECT COUNT(*) FROM world_career_offers
                WHERE request_key LIKE 'live-v1-%'""").fetchone()[0]
            routed=db.execute("""SELECT COUNT(*) FROM world_career_offers o
                JOIN world_career_preseason_window_offers wo ON wo.offer_id=o.offer_id
                JOIN world_career_saves c ON c.career_id=o.career_id
                JOIN world_career_preseason_windows w ON w.window_id=wo.window_id
                WHERE o.career_id=? AND o.request_key LIKE 'live-v1-%'
                  AND o.selling_club_id=c.manager_club_id
                  AND o.buying_club_id<>c.manager_club_id
                  AND w.career_id=o.career_id AND w.season_index=1""",
                  (CAREER,)).fetchone()[0]
            self.assertGreater(incoming,0)
            self.assertEqual(routed,incoming,
                "Autonomous incoming bids must all belong to the manager's live career window")
            self.assertEqual(db.execute("""SELECT COUNT(DISTINCT request_key)
                 FROM world_career_offers
                 WHERE request_key LIKE 'live-v1-%'""").fetchone()[0],incoming,
                 "Every autonomous incoming offer has an idempotent request key")
            self.assertEqual(window_snapshot(db,career_id=CAREER)["state"],"open")

    def test_03g_morale_request_vs_refusal_and_squad_eligibility(self):
        from world_player_morale import is_unavailable
        from world_squad_desk import squad_preview
        base=f"/world/play/career/{CAREER}/market"
        with self.connect_db() as db:
            snap=window_snapshot(db,career_id=CAREER)
            manager=db.execute("""SELECT manager_club_id
                FROM world_career_saves WHERE career_id=?""",(CAREER,)).fetchone()[0]
            roster=squad_preview(db,career_id=CAREER)["players"]
            unsold=next((p for p in roster if not p["incoming"] and
                         not p["departing"] and
                         not db.execute("""SELECT 1 FROM world_career_offers
                             WHERE career_id=? AND player_id=? AND
                             status IN ('agreed_future','completed')""",
                             (CAREER,p["player_id"])).fetchone()),None)
            self.assertIsNotNone(unsold)
            pid=unsold["player_id"]
            db.execute("""INSERT INTO world_career_player_morale
                (career_id,window_id,player_id,club_id,status,reason,requested_at)
                VALUES(?,?,?,?,'transfer_requested','Wants first-team football',
                       '2026-10-17T12:00:00+00:00')""",
                (CAREER,snap["window_id"],pid,manager))
            db.commit()
            self.assertFalse(is_unavailable(db,career_id=CAREER,
                             window_id=snap["window_id"],player_id=pid))
            self.assertIn(pid,{p["player_id"] for p in squad_preview(
                db,career_id=CAREER)["players"]})
            db.execute("""UPDATE world_career_player_morale
                SET status='refusing_to_play',
                 reason='Two credible moves blocked',
                 refused_at='2026-10-17T12:15:00+00:00'
                WHERE career_id=? AND window_id=? AND player_id=?""",
                (CAREER,snap["window_id"],pid))
            db.commit()
            self.assertTrue(is_unavailable(db,career_id=CAREER,
                window_id=snap["window_id"],player_id=pid))
            roster=squad_preview(db,career_id=CAREER)
            self.assertNotIn(pid,{p["player_id"] for p in roster["players"]})
            self.assertIn(pid,{p["player_id"] for p in roster["unavailable"]})
            self.assertEqual(db.execute("""SELECT club_id
                FROM world_career_registrations WHERE career_id=?
                AND player_id=?""",(CAREER,pid)).fetchone()[0],manager)
        html=self.client.get(base,base_url="https://localhost").get_data(as_text=True)
        self.assertIn("Unavailable for the PES season",html)

    def test_03ga_squad_role_promotion_can_resolve_transfer_request(self):
        from world_player_morale import reconcile_player_morale
        from world_squad_desk import squad_preview
        with self.connect_db() as db:
            snap=window_snapshot(db,career_id=CAREER)
            manager=db.execute("""SELECT manager_club_id
                FROM world_career_saves WHERE career_id=?""",(CAREER,)).fetchone()[0]
            candidates=[p for p in squad_preview(db,career_id=CAREER)["players"]
                if p["player_id"] not in {r[0] for r in db.execute(
                    """SELECT player_id FROM world_career_player_morale
                    WHERE career_id=?""",(CAREER,)).fetchall()}]
            pid=next(p["player_id"] for p in candidates
                     if not db.execute("""SELECT 1 FROM world_career_offers
                       WHERE career_id=? AND player_id=? AND status='rejected'""",
                       (CAREER,p["player_id"])).fetchone())
            before=db.execute("""SELECT current_role FROM
                world_career_player_circumstances
                WHERE career_id=? AND player_id=?""",(CAREER,pid)).fetchone()
            db.execute("""INSERT INTO world_career_player_morale
               (career_id,window_id,player_id,club_id,status,reason,requested_at)
               VALUES(?,?,?,?,'transfer_requested',
               'Not playing enough','2026-10-17T12:00:00+00:00')""",
               (CAREER,snap["window_id"],pid,manager))
            db.execute("""UPDATE world_career_player_circumstances
                SET current_role='regular_starter' WHERE career_id=? AND player_id=?""",
                (CAREER,pid))
            db.commit()
            test_time=datetime.fromisoformat(snap["started_at"])+timedelta(minutes=20)
            with patch("world_player_morale._probability",return_value=0.99):
                result=reconcile_player_morale(db,career_id=CAREER,now=test_time)
            self.assertGreaterEqual(result["resolved"],1)
            self.assertIsNone(db.execute("""SELECT status FROM
                world_career_player_morale WHERE career_id=? AND player_id=?""",
                (CAREER,pid)).fetchone())
            if before:
                db.execute("""UPDATE world_career_player_circumstances
                    SET current_role=? WHERE career_id=? AND player_id=?""",
                    (before[0],CAREER,pid))
            db.commit()

    def test_03gc_blocked_outfield_player_can_request_then_refuse(self):
        from world_player_morale import reconcile_player_morale,is_unavailable
        from world_squad_desk import squad_preview
        from world_ai_bidding import position_family
        from world_preseason_window import window_snapshot
        with self.connect_db() as db:
            snap=window_snapshot(db,career_id=CAREER)
            club=db.execute("""SELECT manager_club_id FROM world_career_saves
                WHERE career_id=?""",(CAREER,)).fetchone()[0]
            excluded={r[0] for r in db.execute("""SELECT player_id
                FROM world_career_player_morale
                WHERE career_id=?""",(CAREER,)).fetchall()}
            pending={r[0] for r in db.execute("""SELECT player_id
                FROM world_career_offers WHERE career_id=? AND
                status IN ('agreed_future','completed')""",(CAREER,)).fetchall()}
            options=[p for p in squad_preview(db,career_id=CAREER)["players"]
                if p["role"]=="fringe" and position_family(p["position"])!="GK"
                and p["player_id"] not in excluded|pending
                and p["market_value"]]
            self.assertTrue(options,"Need an outfield fringe candidate for modelled refusal")
            choice=options[0]
            pid=choice["player_id"]
            buyer=db.execute("""SELECT club_id FROM world_clubs
                WHERE club_id<>? ORDER BY club_id LIMIT 1""",(club,)).fetchone()[0]
            for n in (1,2):
                cur=db.execute("""INSERT INTO world_career_offers
                    (career_id,request_key,player_id,buying_club_id,
                     selling_club_id,offered_fee,status,agreement_date,economy_version)
                    VALUES(?,?,?,?,?,?,'rejected','2026-07-31','prototype-v1')""",
                    (CAREER,f"qa-blocked-morale-{pid}-{n}",pid,buyer,club,
                     choice["market_value"]))
                db.execute("""INSERT INTO world_career_preseason_window_offers
                    (window_id,offer_id,tagged_at) VALUES(?,?,?)""",
                    (snap["window_id"],cur.lastrowid,snap["started_at"]))
            db.commit()
            start=datetime.fromisoformat(snap["started_at"])
            def targeted_roll(*parts):
                return 0.0 if pid in parts else 1.0
            with patch("world_player_morale._probability",side_effect=targeted_roll):
                first=reconcile_player_morale(db,career_id=CAREER,
                       now=start+timedelta(seconds=1100))
                self.assertEqual(first["requested"],1)
                self.assertFalse(is_unavailable(db,career_id=CAREER,
                    window_id=snap["window_id"],player_id=pid))
                second=reconcile_player_morale(db,career_id=CAREER,
                       now=start+timedelta(seconds=1610))
            self.assertEqual(second["refusing"],1)
            self.assertTrue(is_unavailable(db,career_id=CAREER,
                window_id=snap["window_id"],player_id=pid))
            self.assertNotIn(pid,{p["player_id"] for p in
                squad_preview(db,career_id=CAREER)["players"]})
            # Keep roster ownership to preserve the original signed-contract
            # history; season eligibility is a separate authoritative fact.
            self.assertEqual(db.execute("""SELECT club_id FROM
                world_career_registrations WHERE career_id=? AND player_id=?""",
                (CAREER,pid)).fetchone()[0],club)

    def test_04_deadline_freezes_incomplete_bids_and_preserves_history(self):
        with self.connect_db() as db:
            now=datetime.now(timezone.utc)
            db.execute("""UPDATE world_career_preseason_windows
                SET started_at=?,deadline_at=? WHERE career_id=?""",
                ((now-timedelta(minutes=40)).isoformat(timespec="seconds"),
                 (now-timedelta(minutes=10)).isoformat(timespec="seconds"),
                 CAREER))
            before=db.execute("""SELECT player_id,club_id FROM
                world_career_registrations WHERE career_id=?
                ORDER BY player_id""",(CAREER,)).fetchall()
            signed=db.execute("""SELECT o.player_id,o.buying_club_id
                FROM world_career_offers o
                JOIN world_career_preseason_window_offers wo
                  ON wo.offer_id=o.offer_id
                WHERE o.career_id=? AND o.status='agreed_future'""",
                (CAREER,)).fetchall()
            expected_moves={r["player_id"]:r["buying_club_id"] for r in signed}
            self.assertEqual(len(expected_moves),len(signed),
                "AI world and manager must not sign the same player twice")
            db.commit()
        url=f"/world/play/career/{CAREER}/market"
        html=self.client.get(url,base_url="https://localhost")
        self.assertEqual(html.status_code,200)
        self.assertIn("Closed — squads locked",html.get_data(as_text=True))
        report=html.get_data(as_text=True)
        self.assertIn("Final transfer window report",report)
        self.assertIn("Proceed to season setup",report)
        self.assertIn("View transfer summary",report)
        self.assertIn("Transfers between other clubs:",report)
        self.assertIn("Fees spent:",report)
        self.assertIn("negotiations expired at the deadline",report)
        # Repeated deadline reconciliation must not duplicate registrations.
        refreshed=self.client.get(url,base_url="https://localhost")
        self.assertIn("Final transfer window report",
                      refreshed.get_data(as_text=True))
        with self.connect_db() as db:
            closed=window_snapshot(db,career_id=CAREER)
            self.assertEqual(closed["state"],"closed")
            after=db.execute("""SELECT player_id,club_id FROM
                world_career_registrations WHERE career_id=?
                ORDER BY player_id""",(CAREER,)).fetchall()
            initial=dict(tuple(x) for x in before)
            final=dict(tuple(x) for x in after)
            for pid,club in initial.items():
                self.assertEqual(final[pid],expected_moves.get(pid,club))
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM
                world_career_preseason_registration_events""").fetchone()[0],
                len(signed))
            for offer in db.execute("""SELECT o.status,t.status AS agent_status,
                    t.proposed_wage_weekly,o.offered_wage_weekly
                FROM world_career_preseason_registration_events r
                JOIN world_career_offers o ON o.offer_id=r.offer_id
                JOIN world_career_agent_terms t ON t.offer_id=o.offer_id"""):
                self.assertEqual(offer["status"],"completed")
                self.assertEqual(offer["agent_status"],"accepted")
                self.assertEqual(offer["proposed_wage_weekly"],
                                 offer["offered_wage_weekly"])
        attempted=self.client.post(url+"/decision",data=dict(
            csrf=self.csrf,offer_id=self.offer_id,decision="accept"),
            base_url="https://localhost")
        self.assertEqual(attempted.status_code,302)
        self.assertIn("error=",attempted.headers["Location"])

    def test_05_season_setup_checklist_persists_after_deadline(self):
        from world_season_setup import checklist
        base=f"/world/play/career/{CAREER}/market"
        page=self.client.get(base,base_url="https://localhost")
        self.assertEqual(page.status_code,200)
        markup=page.get_data(as_text=True)
        self.assertIn("Season setup",markup)
        self.assertIn('data-desk-tab="season-setup"',markup)
        self.assertIn('name="step" value="review"',markup)
        for step in ("review","apply_pes","verify_squads"):
            action=self.client.post(base+"/season/step",data={
                "csrf":self.csrf,"step":step,"done":"1"},
                base_url="https://localhost")
            self.assertEqual(action.status_code,302)
            self.assertNotIn("error=",action.headers["Location"])
        with self.connect_db() as db:
            result=checklist(db,career_id=CAREER)
            self.assertTrue(result["completed"])
            self.assertEqual(set(result["steps"]),{
                "review","apply_pes","verify_squads"})
        again=self.client.get(base,base_url="https://localhost")
        self.assertIn("Ready for the new season",again.get_data(as_text=True))

if __name__=="__main__":
    unittest.main()

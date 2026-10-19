"""Authenticated Flask request tests for the career selling-club journey.

Uses a disposable SQLite career, the actual signed-cookie/CSRF routes and a
Flask test client. Not a visual browser test and never accesses production.
"""
import os
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from flask import Flask

from test_career_selling import career_fixture
from world_career_play import create_play_blueprint


class SellingHttpJourneyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dbpath=Path(self.temp.name)/"sandbox-test.db"
        source=career_fixture()
        source.executescript("""
        ALTER TABLE world_players ADD COLUMN full_name TEXT;
        UPDATE world_players SET full_name=CASE player_id
            WHEN 101 THEN 'Home Star' ELSE 'Away Prospect' END;
        ALTER TABLE world_clubs ADD COLUMN name TEXT;
        UPDATE world_clubs SET name=CASE club_id
            WHEN 1 THEN 'Home FC' ELSE 'Away FC' END;
        """)
        destination=sqlite3.connect(self.dbpath)
        source.backup(destination)
        destination.close()
        source.close()
        self.env=patch.dict(os.environ,{
            "WORLD_MARKET_COOKIE_SECRET":"isolated-test-only-signing-key",
            "WORLD_MARKET_ACCESS_KEY":"local-test-password",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.patches=[
            patch("world_v2.initialize_world"),
            patch("world_career_play.initialize_catalog"),
            patch("world_career_play.initialize_market"),
            patch("world_career_play.initialize_career_engine"),
            patch("world_career_play.initialize_career_management"),
            patch("world_career_play.initialize_board_objectives"),
            patch("world_career_play.initialize_career_board_policy"),
            patch("world_reputation_v2.initialize_pyramid"),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.app=Flask("test_career_selling_routes")
        self.app.register_blueprint(create_play_blueprint(self.dbpath))
        self.client=self.app.test_client()
        self.url="/world/play/career/career-a/selling"
        self.host=dict(base_url="https://localhost")

    def csrf(self,html):
        matched=re.search(r'name="csrf" value="([^"]+)"',html)
        if not matched:raise AssertionError("CSRF field missing from seller form")
        return matched.group(1)

    def login(self):
        r=self.client.post("/world/play/login",data={
            "password":"local-test-password"},**self.host)
        self.assertEqual(r.status_code,302)

    def get(self,query=""):
        return self.client.get(self.url+query,**self.host)

    def test_mobile_signin_cookie_persists_and_missing_cookie_explained(self):
        # Auth flow via HTTPS using the same cookie semantics as iPhone browsers.
        r=self.client.post("/world/play/login",data={
            "password":"local-test-password"},**self.host)
        self.assertEqual(r.status_code,302)
        self.assertIn("/world/play?signin=1",r.headers["Location"])
        header=r.headers.get("Set-Cookie","")
        self.assertIn("SameSite=Lax",header)
        self.assertIn("Secure",header)
        self.assertIn("HttpOnly",header)
        self.assertIn("Path=/world",header)
        auth=self.get("?player_id=101")
        self.assertEqual(auth.status_code,200)
        self.assertIn(b"Selling Clubs",auth.data)
        self.client.delete_cookie("world_play_access",path="/world")
        missing=self.client.get("/world/play?signin=1",**self.host)
        self.assertEqual(missing.status_code,200)
        self.assertIn(b"Sign-in did not stick",missing.data)
        self.assertIn(b"Safari",missing.data)

    def test_login_needed_to_view_seller_settings(self):
        r=self.get()
        self.assertEqual(r.status_code,302)
        self.assertIn("/world/play",r.headers["Location"])

    def test_unauthorised_write_rejected(self):
        r=self.client.post(self.url+"/enable",data={
            "source_note":"Untrusted"},**self.host)
        self.assertEqual(r.status_code,403)

    def test_full_authorised_activation_record_preview_and_reload(self):
        self.login()
        page=self.get("?player_id=102")
        self.assertEqual(page.status_code,200)
        self.assertIn(b"Away Prospect",page.data)
        token=self.csrf(page.get_data(as_text=True))
        enabled=self.client.post(self.url+"/enable",data=dict(
            csrf=token,source_note="Explicit sandbox opt-in"),**self.host)
        self.assertEqual(enabled.status_code,302)
        form=self.get("?player_id=102")
        self.assertEqual(form.status_code,200)
        self.assertIn(b"Active for new offers",form.data)
        payload=dict(
            csrf=self.csrf(form.get_data(as_text=True)),
            player_id="102",market_value="10000000",contract_years="3",
            squad_role="regular_starter",transfer_listed="no",
            player_wants_exit="yes",financial_state="stable",
            replacement="available",seller_stance="neutral",
            board_enabled="no",exceptional_offer_pct="",
            financial_objective="unknown",ambition="unknown",
            ownership_priority="unknown",assumed_manager_trust="unknown",
            source_note="Fictional scenario inputs only")
        posted=self.client.post(self.url+"/circumstances",data=payload,**self.host)
        self.assertEqual(posted.status_code,302)
        saved=self.get("?player_id=102")
        self.assertEqual(saved.status_code,200)
        self.assertIn(b"Scenario locked",saved.data)
        assessed=self.get("?player_id=102&offer_fee=8000000")
        self.assertEqual(assessed.status_code,200)
        self.assertIn(b"Seller decision:",assessed.data)
        self.assertIn(b"Negotiate",assessed.data)
        self.assertRegex(assessed.get_data(as_text=True),
            r'name="offer_fee" min="0" max="1000000000"\s+step="1"')
        # New SQLite connection proves the write survived a reload.
        db=sqlite3.connect(self.dbpath)
        try:
            count=db.execute("""SELECT COUNT(*) FROM world_career_seller_assumptions
                WHERE career_id='career-a' AND player_id=102""").fetchone()[0]
            self.assertEqual(count,1)
        finally:
            db.close()

    def test_unrounded_prefilled_valuation_is_browser_valid_and_saves(self):
        """Regression for browser's 'enter a valid value' step mismatch.

        A source-model valuation like 1,234,567 GBP is valid server-side.
        Its input must NOT demand multiples of GBP 50k, nor should a
        documented 137% board limit need to be a multiple of 5%.
        """
        from html.parser import HTMLParser

        class NumberInputs(HTMLParser):
            def __init__(self):
                super().__init__()
                self.by_name={}
            def handle_starttag(self,tag,attrs):
                if tag=="input":
                    record=dict(attrs)
                    if record.get("type")=="number":
                        self.by_name[record.get("name")]=record

        self.login()
        db=sqlite3.connect(self.dbpath)
        try:
            # Minimal source-table presence: in a complete career these
            # tables are populated. Stub valuation is deliberate and exact.
            db.execute("CREATE TABLE world_dataset_rosters(dummy INTEGER)")
            db.execute("CREATE TABLE world_dataset_ratings(dummy INTEGER)")
            db.commit()
        finally:
            db.close()

        with patch("world_career_play._player_reference",
                   return_value=(1_234_567,74)):
            form=self.get("?player_id=101")
        self.assertEqual(form.status_code,200)
        inputs=NumberInputs()
        inputs.feed(form.get_data(as_text=True))
        market=inputs.by_name["market_value"]
        self.assertEqual(market.get("value"),"1234567")
        self.assertEqual(market.get("min"),"0")
        self.assertEqual(market.get("max"),"1000000000")
        self.assertEqual(market.get("step"),"1")
        self.assertEqual(inputs.by_name["exceptional_offer_pct"].get("step"),"1")

        token=self.csrf(form.get_data(as_text=True))
        payload=dict(csrf=token,player_id="101",market_value="1234567",
            contract_years="2",squad_role="regular_starter",
            transfer_listed="no",player_wants_exit="no",
            financial_state="stable",replacement="available",
            seller_stance="neutral",board_enabled="no",
            exceptional_offer_pct="137",
            financial_objective="unknown",ambition="unknown",
            ownership_priority="unknown",assumed_manager_trust="unknown",
            source_note="Explicit simulated player facts")
        result=self.client.post(self.url+"/circumstances",
            data=payload,**self.host)
        self.assertEqual(result.status_code,302)
        self.assertNotIn("error=",result.headers.get("Location",""))
        with sqlite3.connect(self.dbpath) as db:
            row=db.execute("""SELECT market_value,exceptional_offer_pct
                FROM world_career_seller_assumptions
                WHERE career_id='career-a' AND player_id=101""").fetchone()
            self.assertEqual(row,(1_234_567,137))
        # The preview HTML has the same browser step correction. A separate
        # existing HTTP journey tests preview responses against a complete
        # fixture, rather than the two fake tables used above.
        from world_career_selling_ui import SELLING_CAREER_PAGE
        self.assertRegex(SELLING_CAREER_PAGE,
            r'name="offer_fee" min="0" max="1000000000"\s+step="1"')

    def test_authenticated_offer_and_counter_use_seller_snapshot(self):
        from unittest.mock import patch
        self.login()
        first=self.get("?player_id=102")
        token=self.csrf(first.get_data(as_text=True))
        enabled=self.client.post(self.url+"/enable",data=dict(
            csrf=token,source_note="Opt in"),**self.host)
        self.assertEqual(enabled.status_code,302)
        payload=dict(
            csrf=token,player_id="102",market_value="10000000",
            contract_years="3",squad_role="regular_starter",
            transfer_listed="no",player_wants_exit="yes",
            financial_state="stable",replacement="available",
            seller_stance="neutral",board_enabled="no",
            exceptional_offer_pct="",financial_objective="unknown",
            ambition="unknown",ownership_priority="unknown",
            assumed_manager_trust="unknown",
            source_note="Verified fictional test fixture")
        self.assertEqual(self.client.post(self.url+"/circumstances",
            data=payload,**self.host).status_code,302)
        with patch("world_careers._player_reference",return_value=(10_000_000,78)):
            response=self.client.post("/world/play/career/career-a/offer",
                data=dict(csrf=token,request_key="web-journey-01",
                    player_id="102",buying_club_id="1",offered_fee="8000000",
                    agreement_date="2026-10-14",seller_stance="neutral"),
                **self.host)
            self.assertEqual(response.status_code,302)
            db=sqlite3.connect(self.dbpath)
            try:
                row=db.execute("""SELECT offer_id,status,demanded_fee FROM world_career_offers
                    WHERE career_id='career-a' AND request_key='web-journey-01'""").fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[1],"countered")
                self.assertGreater(row[2],8_000_000)
                snapshot=db.execute("""SELECT effective_decision,board_decision
                    FROM world_career_seller_offer_decisions
                    WHERE offer_id=?""",(row[0],)).fetchone()
                self.assertEqual(snapshot,("negotiate","not_enabled"))
            finally:
                db.close()
            accepted=self.client.post("/world/play/career/career-a/accept",
                data=dict(csrf=token,offer_id=str(row[0])),**self.host)
            self.assertEqual(accepted.status_code,302)
            db=sqlite3.connect(self.dbpath)
            try:
                final=db.execute("SELECT status FROM world_career_offers WHERE offer_id=?",
                    (row[0],)).fetchone()[0]
                self.assertEqual(final,"accepted_pending_contract")
                self.assertEqual(db.execute("""SELECT club_id
                    FROM world_career_registrations
                    WHERE career_id='career-a' AND player_id=102""").fetchone()[0],2)
            finally:
                db.close()

    def test_incoming_bid_manager_board_forces_sale_without_transfer(self):
        from world_career_management import set_initial_confidence
        self.login()
        first=self.get("?player_id=101")
        token=self.csrf(first.get_data(as_text=True))
        self.assertEqual(self.client.post(self.url+"/enable",
            data=dict(csrf=token,source_note="Explicit sandbox selling rules"),
            **self.host).status_code,302)
        seller_data=dict(
            csrf=token,player_id="101",market_value="10000000",
            contract_years="5",squad_role="key_player",
            transfer_listed="no",player_wants_exit="no",
            financial_state="stable",replacement="difficult",
            seller_stance="retain",board_enabled="yes",
            exceptional_offer_pct="100",financial_objective="balanced",
            ambition="consolidation",ownership_priority="balanced",
            assumed_manager_trust="unknown",
            source_note="Fictional protected star with exceptional-sale board rule")
        saved_reply=self.client.post(self.url+"/circumstances",
            data=seller_data,**self.host)
        self.assertEqual(saved_reply.status_code,302)
        self.assertNotIn("error=",saved_reply.headers.get("Location",""),
            "Seller assumptions were not saved: "+saved_reply.headers.get("Location",""))
        with sqlite3.connect(self.dbpath) as db:
            set_initial_confidence(db,career_id="career-a",club_id=1,value=20)
        with patch("world_careers.ai_interest",
                   return_value=[{"club_id":2,"club_name":"Away FC",
                                  "available_budget":20_000_000,
                                  "need_score":75}]),patch(
                   "world_careers._player_reference",
                   return_value=(10_000_000,90)),patch(
                   "world_ai_bidding.determine_offer",
                   return_value={"fee":13_000_000,"buyer_club_id":2,
                                 "round":1,"demand_premium_pct":0,
                                 "eligible_competing_clubs":1,
                                 "buyer_need_score":75,"last_offer":None,
                                 "reason":"Controlled seller-board HTTP fixture"}):
            result=self.client.post(
                "/world/play/career/career-a/ai-inbound",
                data=dict(csrf=token,player_id="101"),**self.host)
        self.assertEqual(result.status_code,302)
        self.assertNotIn("error=",result.headers.get("Location",""),
            "Incoming bid route failed: "+result.headers.get("Location",""))
        with sqlite3.connect(self.dbpath) as db:
            bid=db.execute("""SELECT offer_id,status,offered_fee,offered_wage_weekly
                FROM world_career_offers
                WHERE career_id='career-a' AND request_key='ai-v1-101-2'""").fetchone()
            self.assertIsNotNone(bid,
                "No bid created: "+result.headers.get("Location","")+
                "; seller="+str(db.execute("""SELECT board_enabled,
                market_value,squad_role,financial_state
                FROM world_career_seller_assumptions
                WHERE career_id='career-a' AND player_id=101""").fetchone())+
                "; buyer budget="+str(db.execute("""SELECT transfer_budget,
                committed_fees FROM world_career_club_ledger
                WHERE career_id='career-a' AND club_id=2""").fetchone()))
            self.assertEqual(bid[1],"accepted_pending_contract")
            self.assertEqual(bid[2],13_000_000)
            self.assertIsNone(bid[3])
            ruling=db.execute("""SELECT effective_decision,board_decision,input_snapshot
                FROM world_career_seller_offer_decisions WHERE offer_id=?""",
                (bid[0],)).fetchone()
            self.assertEqual(ruling[:2],("accept","direct_sale"))
            self.assertIn('"decision": "reject"',ruling[2])
            self.assertEqual(db.execute("""SELECT club_id
                FROM world_career_registrations
                WHERE career_id='career-a' AND player_id=101""").fetchone()[0],1)
        replay=self.client.post("/world/play/career/career-a/ai-inbound",
            data=dict(csrf=token,player_id="101"),**self.host)
        self.assertEqual(replay.status_code,302)
        with sqlite3.connect(self.dbpath) as db:
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM world_career_offers
                WHERE career_id='career-a' AND request_key='ai-v1-101-2'""").fetchone()[0],1)

    def test_incoming_bid_without_seller_assumptions_cannot_force_sale(self):
        self.login()
        first=self.get("?player_id=101")
        token=self.csrf(first.get_data(as_text=True))
        self.assertEqual(self.client.post(self.url+"/enable",
            data=dict(csrf=token,source_note="Explicit sandbox selling rules"),
            **self.host).status_code,302)
        with patch("world_careers.ai_interest",
                   return_value=[{"club_id":2,"club_name":"Away FC",
                                  "available_budget":20_000_000,
                                  "need_score":75}]),patch(
                   "world_careers._player_reference",
                   return_value=(10_000_000,90)),patch(
                   "world_ai_bidding.determine_offer",
                   return_value={"fee":13_000_000,"buyer_club_id":2,
                                 "round":1,"demand_premium_pct":0,
                                 "eligible_competing_clubs":1,
                                 "buyer_need_score":75,"last_offer":None,
                                 "reason":"Controlled seller-board HTTP fixture"}):
            reply=self.client.post("/world/play/career/career-a/ai-inbound",
                data=dict(csrf=token,player_id="101"),**self.host)
        self.assertEqual(reply.status_code,302)
        with sqlite3.connect(self.dbpath) as db:
            pending=db.execute("""SELECT offer_id,status FROM world_career_offers
                WHERE career_id='career-a' AND request_key='ai-v1-101-2'""").fetchone()
            self.assertIsNotNone(pending)
            self.assertEqual(pending[1],"proposed")
            self.assertIsNone(db.execute("""SELECT 1
                FROM world_career_seller_offer_decisions WHERE offer_id=?""",
                (pending[0],)).fetchone())
            # No invented seller consent and no transfer registration.

            self.assertEqual(db.execute("""SELECT club_id
                FROM world_career_registrations
                WHERE career_id='career-a' AND player_id=101""").fetchone()[0],1)

    def test_human_rejection_then_revised_ai_offer_via_authenticated_career_desk(self):
        import json
        self.login()
        page=self.get("?player_id=101")
        token=self.csrf(page.get_data(as_text=True))
        enabled=self.client.post(self.url+"/enable",
            data=dict(csrf=token,source_note="Explicit sandbox selling rules"),
            **self.host)
        self.assertEqual(enabled.status_code,302)
        clubs=[{"club_id":2,"club_name":"Away FC",
                "available_budget":20_000_000,"need_score":70}]
        with patch("world_careers.ai_interest",return_value=clubs),patch(
                "world_careers._player_reference",return_value=(10_000_000,75)):
            first=self.client.post("/world/play/career/career-a/ai-inbound",
                data=dict(csrf=token,player_id="101"),**self.host)
        self.assertEqual(first.status_code,302)
        self.assertIn("notice=",first.headers["Location"])
        with sqlite3.connect(self.dbpath) as db:
            offer=db.execute("""SELECT offer_id,status,offered_fee
                FROM world_career_offers
                WHERE career_id='career-a' AND request_key='ai-v1-101-2'""").fetchone()
            self.assertIsNotNone(offer)
            self.assertEqual(offer[1],"proposed")
            first_id,_,first_fee=offer
        # The actual signed-in seller route records a rejection rather than
        # misleadingly treating it as a BUYER withdrawal.
        refused=self.client.post("/world/play/career/career-a/incoming/cancel",
            data=dict(csrf=token,offer_id=str(first_id)),**self.host)
        self.assertEqual(refused.status_code,302)
        self.assertIn("notice=",refused.headers["Location"])
        with sqlite3.connect(self.dbpath) as db:
            self.assertEqual(db.execute(
                "SELECT status FROM world_career_offers WHERE offer_id=?",
                (first_id,)).fetchone()[0],"rejected")
        with patch("world_careers.ai_interest",return_value=clubs),patch(
                "world_careers._player_reference",return_value=(10_000_000,75)):
            followup=self.client.post("/world/play/career/career-a/ai-inbound",
                data=dict(csrf=token,player_id="101"),**self.host)
        self.assertEqual(followup.status_code,302)
        with sqlite3.connect(self.dbpath) as db:
            revised=db.execute("""SELECT offer_id,status,offered_fee
                FROM world_career_offers
                WHERE career_id='career-a' AND request_key='ai-v2-101-2-r2'""").fetchone()
            self.assertIsNotNone(revised)
            self.assertGreater(revised[2],first_fee)
            self.assertEqual(revised[1],"proposed")
            snapshot=json.loads(db.execute("""SELECT detail FROM world_career_offer_events
                WHERE offer_id=? AND event_type='ai_bid_pricing'""",
                (revised[0],)).fetchone()[0])
            self.assertEqual(snapshot["prior_offer_id"],first_id)
            self.assertEqual(snapshot["round"],2)
            self.assertEqual(db.execute("""SELECT club_id FROM world_career_registrations
                WHERE career_id='career-a' AND player_id=101""").fetchone()[0],1)
        # A second click while the revised bid awaits seller information
        # must not manufacture a third-round offer.
        with patch("world_careers.ai_interest",return_value=clubs),patch(
                "world_careers._player_reference",return_value=(10_000_000,75)):
            same=self.client.post("/world/play/career/career-a/ai-inbound",
                data=dict(csrf=token,player_id="101"),**self.host)
        self.assertEqual(same.status_code,302)
        with sqlite3.connect(self.dbpath) as db:
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM world_career_offers
                WHERE career_id='career-a' AND player_id=101
                  AND buying_club_id=2 AND request_key LIKE 'ai-v2-%'""").fetchone()[0],1)

    def test_authenticated_wrong_csrf_rejected(self):
        self.login()
        r=self.client.post(self.url+"/enable",data=dict(
            csrf="wrong",source_note="Attempted edit"),**self.host)
        self.assertEqual(r.status_code,403)

    def test_cannot_save_player_from_another_career(self):
        self.login()
        page=self.get("?player_id=102")
        token=self.csrf(page.get_data(as_text=True))
        posted=self.client.post(self.url+"/circumstances",data=dict(
            csrf=token,player_id="999",market_value="1000000",
            source_note="Not in career"),**self.host)
        self.assertEqual(posted.status_code,302)
        self.assertIn("error=",posted.headers["Location"])
        db=sqlite3.connect(self.dbpath)
        try:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM world_career_seller_assumptions"
            ).fetchone()[0],0)
        finally:
            db.close()

if __name__=="__main__":
    unittest.main()

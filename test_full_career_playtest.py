"""Controlled full-career playtest against the actual seeded 2026/27 sandbox.

No production database, Render account, real transfer, or historical result is
changed. HTTP actions use Flask's authenticated client against one disposable
file-backed SQLite career. Club/player records come from the real app seeds;
contract and sporting scenarios are explicitly fictional. Every assertion
tests a user-visible stage or a saved financial/registration invariant.
"""
import os
import re
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from flask import Flask
from world_career_play import create_play_blueprint
from world_v2 import initialize_world
from world_explorer import initialize_catalog
from world_market import initialize_market
from world_careers import (
    initialize_career_engine,_player_reference,budget_remaining,
    wage_budget_breakdown,career_player_policy,
)
from world_career_management import initialize_career_management
from world_career_objectives import initialize_board_objectives
from world_career_board_policy import initialize_career_board_policy,career_board_decision
from world_career_selling import initialize_career_selling
from world_reputation_v2 import initialize_pyramid
from world_player_decisions import DECISION_V2_VERSION

DATASET = "england-2026-27-fc27"
CAREER = "isolated-playtest-2627"
DATE = "2026-10-14"


class FullCareerPlaytest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.dbpath=Path(cls.temp.name)/"full-career-playtest.sqlite"
        conn=sqlite3.connect(cls.dbpath)
        conn.row_factory=sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        for fn in (initialize_world,initialize_catalog,initialize_market,
                   initialize_career_engine,initialize_career_management,
                   initialize_board_objectives,initialize_career_board_policy,
                   initialize_career_selling,initialize_pyramid):
            fn(conn)
        conn.commit()
        cls.manager_id=conn.execute(
            "SELECT club_id FROM world_clubs WHERE name='Nottingham Forest'"
        ).fetchone()[0]
        # Identify real seeded, rated players; valuations and ages remain
        # separate from the purely hypothetical seller/contract assumptions.
        sample=conn.execute("""SELECT p.player_id,p.full_name
            FROM world_dataset_rosters r
            JOIN world_players p ON p.player_id=r.player_id
            JOIN world_dataset_ratings x ON x.dataset_id=r.dataset_id
                AND x.player_id=r.player_id
            JOIN world_dataset_entries e ON e.club_id=r.club_id
                AND e.dataset_id=r.dataset_id
            JOIN world_competitions c ON c.competition_id=e.competition_id
            WHERE r.dataset_id=? AND c.tier=4 AND p.birth_date IS NOT NULL
              AND x.overall BETWEEN 55 AND 73
            ORDER BY x.overall,p.player_id LIMIT 150""",(DATASET,)).fetchall()
        candidates=[]
        for row in sample:
            valuation,overall=_player_reference(conn,DATASET,row["player_id"])
            if valuation is not None and 0<valuation<3_000_000:
                candidates.append((row["player_id"],valuation,overall))
        if not candidates:
            raise AssertionError("No suitable low-league seeded player; cannot invent one")
        cls.target_id,cls.target_value,cls.target_rating=candidates[0]
        cls.second_target_id=candidates[1][0] if len(candidates)>1 else None
        sample=conn.execute("""SELECT p.player_id FROM world_dataset_rosters r
            JOIN world_players p ON p.player_id=r.player_id
            JOIN world_dataset_ratings x ON x.player_id=p.player_id
                AND x.dataset_id=r.dataset_id
            WHERE r.dataset_id=? AND r.club_id=?
            ORDER BY x.overall,p.player_id""",(DATASET,cls.manager_id)).fetchall()
        home=[]
        for row in sample:
            ref,_=_player_reference(conn,DATASET,row["player_id"])
            if ref is not None and 0<ref<=15_000_000:
                home.append((row["player_id"],ref))
        if not home:
            raise AssertionError("No rated Forest player affordable to simulated rivals")
        cls.home_player_id,cls.home_value=home[0]
        conn.close()
        cls.env=patch.dict(os.environ,{
            "WORLD_MARKET_COOKIE_SECRET":"playtest-private-cookie-signing-only",
            "WORLD_MARKET_ACCESS_KEY":"playtest-disposable-password",
        })
        cls.env.start()
        cls.app=Flask("full_career_playtest")
        cls.app.config["TESTING"]=True
        cls.app.register_blueprint(create_play_blueprint(cls.dbpath))

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        cls.temp.cleanup()

    def db(self):
        db=sqlite3.connect(self.dbpath)
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def get(self,path):
        response=self.client.get(path,base_url="https://localhost")
        self.assertEqual(response.status_code,200,
            "GET "+path+" returned "+str(response.status_code)+": "+
            response.get_data(as_text=True)[:450])
        return response.get_data(as_text=True)

    def post(self,path,**data):
        result=self.client.post(path,
            data={"csrf":self.csrf,**data},base_url="https://localhost")
        self.assertEqual(result.status_code,302,
            "POST "+path+" returned "+str(result.status_code))
        self.assertNotIn("error=",result.headers.get("Location",""),
            "POST "+path+" failed: "+result.headers.get("Location",""))
        return result

    def read(self,sql,args=()):
        with self.db() as db:
            return db.execute(sql,args).fetchone()

    def test_strength_based_objective_uses_real_source_ranking(self):
        from world_career_strength import strength_baseline
        auto_id="strength-auto-forest-2627"
        with self.db() as db:
            source=strength_baseline(db,career_id=CAREER,club_id=self.manager_id) if (
                db.execute("SELECT 1 FROM world_career_saves WHERE career_id=?",
                (CAREER,)).fetchone()) else None
        # The secondary career is isolated from the manual 19th-place
        # fictional objective in the primary playtest.
        self.client=self.app.test_client()
        logged=self.client.post("/world/play/login",
            data={"password":"playtest-disposable-password"},
            base_url="https://localhost")
        self.assertEqual(logged.status_code,302)
        page=self.get("/world/play")
        csrf=re.search(r'name="csrf" value="([^"]+)"',page)
        self.assertIsNotNone(csrf)
        self.csrf=csrf.group(1)
        self.post("/world/play/create",career_id=auto_id,
            dataset_id=DATASET,title="Source-ranked Forest expectations",
            manager_club_id=str(self.manager_id),
            pes_lock_date="2026-08-01",next_summer_date="2027-07-01",
            economy_version="prototype-v1",scale="1",
            player_decision_version=DECISION_V2_VERSION)
        with self.db() as db:
            baseline=strength_baseline(db,career_id=auto_id,
                                      club_id=self.manager_id)
        self.assertTrue(baseline["available"],baseline.get("reason"))
        self.assertEqual(len(baseline["clubs"]),baseline["league_size"])
        self.assertEqual(baseline["rank"],
            next(row["rank"] for row in baseline["clubs"]
                 if row["club_id"]==self.manager_id))
        self.assertGreaterEqual(min(c["sample_players"] for c in baseline["clubs"]),8)
        url="/world/play/career/"+auto_id+"/management"
        html=self.get(url)
        self.assertIn("Lock squad strength + financial expectations",html)
        self.assertIn(str(baseline["rank"])+" of "+str(baseline["league_size"]),html)
        self.post(url+"/objective/auto",season_key="2026-27")
        self.assertIn("2026-27",self.get(url))
        with self.db() as db:
            stored=db.execute("""SELECT expected_rank,league_size,strength_source
                FROM world_career_season_objectives
                WHERE career_id=? AND club_id=? AND season_key='2026-27'""",
                (auto_id,self.manager_id)).fetchone()
            self.assertEqual(tuple(stored),(baseline["rank"],baseline["league_size"],
                                            "squad_strength_proxy"))
            frozen=db.execute("""SELECT frozen_rankings_json
                FROM world_career_objective_strength_snapshots
                WHERE career_id=? AND season_key='2026-27'""",
                (auto_id,)).fetchone()
            self.assertIsNotNone(frozen)
            self.assertIn("top 16",frozen[0])
        self.post(url+"/objective/auto",season_key="2026-27")
        # Manual source spoofing is blocked: users can enter alternatives only
        # when correctly labelled as sandbox assumptions.
        illegal=self.client.post(url+"/objective",data=dict(
            csrf=self.csrf,season_key="2027-28",
            expected_rank="19",league_size="20",
            strength_source="squad_strength_proxy",source_note="Unverified"),
            base_url="https://localhost")
        self.assertEqual(illegal.status_code,302)
        self.assertIn("error=",illegal.headers["Location"])

    def test_resource_ambition_moves_expectations_without_signing_players(self):
        from world_career_strength import strength_baseline
        career_id="resource-accountability-2627"
        self.client=self.app.test_client()
        login=self.client.post("/world/play/login",
            data={"password":"playtest-disposable-password"},
            base_url="https://localhost")
        self.assertEqual(login.status_code,302)
        self.csrf=re.search(r'name="csrf" value="([^"]+)"',
                            self.get("/world/play")).group(1)
        self.post("/world/play/create",career_id=career_id,
            dataset_id=DATASET,title="Funded board objectives test",
            manager_club_id=str(self.manager_id),
            pes_lock_date="2026-08-01",next_summer_date="2027-07-01",
            economy_version="prototype-v1",scale="1",
            player_decision_version=DECISION_V2_VERSION)
        with self.db() as db:
            baseline=strength_baseline(db,career_id=career_id,
                                      club_id=self.manager_id)
        self.assertTrue(baseline["available"])
        mgmt="/world/play/career/"+career_id+"/management"
        self.post(mgmt+"/confidence",value="60")
        self.post(mgmt+"/objective/auto",season_key="2026-27",
            ambition="continental",investment_mandate="required",
            investment_pool="35000000",
            commitment_note="Explicit fictional board instruction to improve the squad")
        expected=self.read("""SELECT expected_rank,strength_source
            FROM world_career_season_objectives WHERE career_id=?""",
            (career_id,))
        self.assertLess(expected[0],baseline["rank"],
            "Investment capacity and continental ambitions must raise expectation")
        self.assertEqual(expected[1],"resource_adjusted_proxy")
        self.assertIn("Required",self.get(mgmt))
        self.assertEqual(self.read("""SELECT financial_shift+ambition_shift
            FROM world_career_resource_expectations WHERE career_id=?""",
            (career_id,))[0],baseline["rank"]-expected[0])
        # Same strong squad, no improvements, and below board target:
        # accountable for unused funds, not rewarded for leaving cash idle.
        finish=expected[0]+2
        self.assertLessEqual(finish,20)
        self.post(mgmt+"/review",season_key="2026-27",
            actual_rank=str(finish),promoted="no",relegated="no",
            cup_result="expected",
            result_note="Fictional board accountability regression, NOT real league result")
        review=self.read("""SELECT confidence_delta,unused_mandated_funds
            FROM world_career_resource_reviews WHERE career_id=?""",
            (career_id,))
        self.assertEqual(tuple(review),(-3,35000000))
        self.assertEqual(self.read("""SELECT COUNT(*) FROM world_career_offers
            WHERE career_id=?""",(career_id,))[0],0)

    def test_five_stage_manager_finalisation_and_exceptional_board_veto(self):
        career_id="transfer-final-stage-2627"
        self.client=self.app.test_client()
        self.assertEqual(self.client.post("/world/play/login",
            data={"password":"playtest-disposable-password"},
            base_url="https://localhost").status_code,302)
        self.csrf=re.search(r'name="csrf" value="([^"]+)"',
                            self.get("/world/play")).group(1)
        self.post("/world/play/create",career_id=career_id,
            dataset_id=DATASET,title="Five-stage transfer playtest",
            manager_club_id=str(self.manager_id),
            pes_lock_date="2026-08-01",next_summer_date="2027-07-01",
            economy_version="prototype-v1",scale="1",
            player_decision_version=DECISION_V2_VERSION)
        prefix="/world/play/career/"+career_id
        self.assertIn("five stages",self.get(prefix))
        self.post(prefix+"/protocol/enable",
            activation_note="Explicit career five-stage test")
        self.assertIn("Five-stage protocol active",self.get(prefix))
        mgmt=prefix+"/management"
        self.post(mgmt+"/confidence",value="60")
        self.post(mgmt+"/buying-board",max_fee_pct="100",
            max_headroom_use_pct="60",financial_objective="balanced",
            ambition="consolidation",ownership_priority="balanced",
            source_note="Scenario purchase value policy — veto only at final gate")
        selling=prefix+"/selling"
        # Enhanced seller mode is already enabled by start_sandbox.
        self.assertIn("Active for new offers",self.get(
            selling+"?player_id="+str(self.target_id)))
        from world_career_selling import DEFAULT_ACTIVATION_NOTE
        self.assertEqual(self.read("""SELECT source_note
            FROM world_career_selling_modes WHERE career_id=?""",
            (career_id,))[0],DEFAULT_ACTIVATION_NOTE)
        players=[(self.target_id,self.target_value)]
        if self.second_target_id is not None:
            with self.db() as db:
                other_value,_=_player_reference(db,DATASET,self.second_target_id)
            players.append((self.second_target_id,other_value))
        self.assertGreaterEqual(len(players),2)
        for player_id,value in players:
            self.post(selling+"/circumstances",
                player_id=str(player_id),market_value=str(value),
                contract_years="1",squad_role="fringe",
                transfer_listed="yes",player_wants_exit="yes",
                financial_state="stable",replacement="available",
                seller_stance="sell",board_enabled="no",
                exceptional_offer_pct="",financial_objective="unknown",
                ambition="unknown",ownership_priority="unknown",
                assumed_manager_trust="unknown",
                source_note="Synthetic low-league player listed for transfer")
        def negotiate(pid,fee,key):
            self.post(prefix+"/offer",request_key=key,
                player_id=str(pid),buying_club_id=str(self.manager_id),
                offered_fee=str(fee),agreement_date=DATE,
                seller_stance="neutral")
            offer=self.read("""SELECT offer_id,status FROM world_career_offers
                WHERE career_id=? AND request_key=?""",(career_id,key))
            self.assertIsNotNone(offer)
            self.assertEqual(offer["status"],"accepted_pending_contract")
            self.post(prefix+"/circumstances",
                offer_id=str(offer["offer_id"]),
                current_wage_weekly="1000",current_role="fringe",
                transfer_listed="yes",renewal_status="not_offered",
                buyer_europe="none",seller_europe="none")
            self.post(prefix+"/agree",offer_id=str(offer["offer_id"]),
                weekly_wage="35000",contract_years="3",
                role_promise="key_player",agreement_date=DATE)
            self.assertEqual(self.read("""SELECT status FROM world_career_agent_terms
                WHERE offer_id=?""",(offer["offer_id"],))[0],"accepted")
            self.assertEqual(self.read("""SELECT status FROM world_career_offers
                WHERE offer_id=?""",(offer["offer_id"],))[0],
                "accepted_pending_contract")
            self.assertIn("Stage 4",self.get(prefix))
            return offer["offer_id"]
        # Board allows fee enquiry and player talks, then vetoes exception at
        # Stage 5 because price exceeds configured value.
        high=max(100_000,players[0][1]*2)
        vetoed=negotiate(players[0][0],high,"five-stage-veto")
        veto_response=self.client.post(prefix+"/confirm",
            data={"csrf":self.csrf,"offer_id":str(vetoed),
                  "agreement_date":DATE},base_url="https://localhost")
        self.assertEqual(veto_response.status_code,302)
        self.assertIn("error=",veto_response.headers["Location"])
        self.assertEqual(self.read("""SELECT status FROM world_career_offers
            WHERE offer_id=?""",(vetoed,))[0],"accepted_pending_contract")
        self.assertEqual(self.read("""SELECT COUNT(*) FROM world_career_transfer_final_reviews
            WHERE offer_id=?""",(vetoed,))[0],0)
        # Human manager can still walk away after player has agreed.
        self.post(prefix+"/withdraw",offer_id=str(vetoed))
        self.assertEqual(self.read("""SELECT status FROM world_career_offers
            WHERE offer_id=?""",(vetoed,))[0],"withdrawn")
        second_id,second_value=players[1]
        approved=negotiate(second_id,second_value,"five-stage-approved")
        self.post(prefix+"/confirm",offer_id=str(approved),
                  agreement_date=DATE)
        signed=self.read("""SELECT status,effective_date
            FROM world_career_offers WHERE offer_id=?""",(approved,))
        self.assertEqual(signed["status"],"agreed_future")
        self.assertGreaterEqual(signed["effective_date"],"2027-07-01")
        final_review=self.read("""SELECT confirmed_by_club_id,board_decision
            FROM world_career_transfer_final_reviews WHERE offer_id=?""",
            (approved,))
        self.assertEqual(tuple(final_review),(self.manager_id,"approved"))
        self.assertNotEqual(self.read("""SELECT club_id FROM world_career_registrations
            WHERE career_id=? AND player_id=?""",(career_id,second_id))[0],
            self.manager_id)
        final_backout=self.client.post(prefix+"/withdraw",
            data={"csrf":self.csrf,"offer_id":str(approved)},
            base_url="https://localhost")
        self.assertIn("error=",final_backout.headers.get("Location",""))
        self.assertEqual(self.read("""SELECT status FROM world_career_offers
            WHERE offer_id=?""",(approved,))[0],"agreed_future")

    def test_search_any_target_pending_offer_and_later_seller_response(self):
        """A full browser-like test of the previously silent offer path."""
        from urllib.parse import quote
        career_id="pending-selling-information-playtest"
        self.client=self.app.test_client()
        login=self.client.post("/world/play/login",
            data={"password":"playtest-disposable-password"},
            base_url="https://localhost")
        self.assertEqual(login.status_code,302)
        self.csrf=re.search(r'name="csrf" value="([^"]+)"',
                            self.get("/world/play")).group(1)
        self.post("/world/play/create",career_id=career_id,
            dataset_id=DATASET,title="Seller pending flow playtest",
            manager_club_id=str(self.manager_id),
            pes_lock_date="2026-08-01",next_summer_date="2027-07-01",
            economy_version="prototype-v1",scale="1",
            player_decision_version=DECISION_V2_VERSION)
        prefix="/world/play/career/"+career_id
        # Search is not restricted to a global top-300 cohort.
        name=self.read("SELECT full_name FROM world_players WHERE player_id=?",
                       (self.target_id,))[0]
        search=self.get(prefix+"?player_search="+quote(name))
        self.assertIn(name,search)
        self.assertIn('name="player_search"',search)
        # Compare user names against actual seeded registrations, without
        # claiming names exist where the source dataset lacks them.
        for term in ("Wood","Maguire"):
            with self.db() as db:
                expected=db.execute("""SELECT COUNT(*) FROM world_career_registrations r
                  JOIN world_players p ON p.player_id=r.player_id
                  WHERE r.career_id=? AND r.club_id!=?
                    AND lower(p.full_name) LIKE ?""",
                  (career_id,self.manager_id,"%"+term.lower()+"%")).fetchone()[0]
            page=self.get(prefix+"?player_search="+quote(term))
            if expected:
                self.assertIn("matching targets shown",page)
            else:
                self.assertIn("0 matching targets",page)

        # No saved selling-club assumptions: fee submission is persisted as
        # pending, not falsely accepted or silently dropped.
        offer_fee=max(100_000,self.target_value)
        result=self.post(prefix+"/offer",request_key="visible-pending-offer",
            player_search=name,player_id=str(self.target_id),
            buying_club_id=str(self.manager_id),
            offered_fee=str(offer_fee),agreement_date=DATE,
            seller_stance="neutral")
        self.assertIn("notice=",result.headers["Location"])
        offer=self.read("""SELECT offer_id,status FROM world_career_offers
            WHERE career_id=? AND request_key='visible-pending-offer'""",
            (career_id,))
        self.assertEqual(offer["status"],"proposed")
        view=self.get(prefix+"?player_search="+quote(name))
        self.assertIn("Offer recorded — awaiting selling club information",view)
        self.assertIn("Get selling club response",view)
        self.assertIn("selling?player_id="+str(self.target_id),view)
        self.assertEqual(self.read("""SELECT COUNT(*) FROM world_career_seller_offer_decisions
            WHERE offer_id=?""",(offer["offer_id"],))[0],0)

        # Button without seller information explains exactly what is missing.
        blocked=self.client.post(prefix+"/seller/review",
            data={"csrf":self.csrf,"offer_id":str(offer["offer_id"])},
            base_url="https://localhost")
        self.assertEqual(blocked.status_code,302)
        self.assertIn("error=",blocked.headers["Location"])
        self.assertEqual(self.read("""SELECT status FROM world_career_offers
            WHERE offer_id=?""",(offer["offer_id"],))[0],"proposed")

        selling=prefix+"/selling"
        self.post(selling+"/circumstances",player_id=str(self.target_id),
            market_value=str(self.target_value),contract_years="1",
            squad_role="fringe",transfer_listed="yes",player_wants_exit="yes",
            financial_state="stable",replacement="available",
            seller_stance="sell",board_enabled="no",exceptional_offer_pct="",
            financial_objective="unknown",ambition="unknown",
            ownership_priority="unknown",assumed_manager_trust="unknown",
            source_note="Explicit hypothetical seller details for pending offer")
        review=self.post(prefix+"/seller/review",offer_id=str(offer["offer_id"]))
        self.assertIn("notice=",review.headers["Location"])
        final=self.read("""SELECT status FROM world_career_offers
            WHERE offer_id=?""",(offer["offer_id"],))[0]
        self.assertIn(final,("accepted_pending_contract","countered","rejected"))
        self.assertEqual(self.read("""SELECT COUNT(*) FROM world_career_seller_offer_decisions
            WHERE offer_id=?""",(offer["offer_id"],))[0],1)

    def test_no_ai_bidders_returns_specific_explanation_in_career_screen(self):
        from unittest.mock import patch
        from urllib.parse import unquote_plus
        career_id="no-silent-ai-bids-playtest"
        self.client=self.app.test_client()
        login=self.client.post("/world/play/login",
            data={"password":"playtest-disposable-password"},
            base_url="https://localhost")
        self.assertEqual(login.status_code,302)
        self.csrf=re.search(r'name="csrf" value="([^"]+)"',
                            self.get("/world/play")).group(1)
        self.post("/world/play/create",career_id=career_id,
            dataset_id=DATASET,title="AI feedback playtest",
            manager_club_id=str(self.manager_id),
            pes_lock_date="2026-08-01",next_summer_date="2027-07-01",
            economy_version="prototype-v1",scale="1",
            player_decision_version=DECISION_V2_VERSION)
        with patch("world_careers.ai_interest",return_value=[]):
            reply=self.post("/world/play/career/"+career_id+"/ai-inbound",
                player_id=str(self.home_player_id))
        self.assertIn("notice=",reply.headers["Location"])
        self.assertIn("No eligible AI buyers",unquote_plus(reply.headers["Location"]))
        # The outcome must appear beside the incoming-offers form on reload.
        location=reply.headers["Location"].split("#",1)[0]
        page=self.get(location)
        self.assertIn("No eligible AI buyers",page)
        self.assertIn('role="status"',page)
        self.assertEqual(self.read("""SELECT COUNT(*) FROM world_career_offers
            WHERE career_id=?""",(career_id,))[0],0)

    def test_full_authenticated_career_lifecycle(self):
        self.client=self.app.test_client()
        self.assertEqual(self.client.get("/world/play/career/"+CAREER,
            base_url="https://localhost").status_code,302)

        # A real route, authenticated login, and creation from the seeded dataset.
        signin=self.client.post("/world/play/login",
            data={"password":"playtest-disposable-password"},
            base_url="https://localhost")
        self.assertEqual(signin.status_code,302)
        index=self.get("/world/play")
        token=re.search(r'name="csrf" value="([^"]+)"',index)
        self.assertIsNotNone(token,"The career login did not return a CSRF token")
        self.csrf=token.group(1)
        self.post("/world/play/create",career_id=CAREER,
            dataset_id=DATASET,title="Disposable Nottingham Forest Playtest",
            manager_club_id=str(self.manager_id),
            pes_lock_date="2026-08-01",next_summer_date="2027-07-01",
            economy_version="prototype-v1",scale="1",
            player_decision_version=DECISION_V2_VERSION)

        # A credible AI buyer must be able to afford the player AND have
        # a genuine modelled squad fit; pick a seeded Forest player that
        # meets both rather than forcing interest in the cheapest player.
        from world_careers import ai_interest
        with self.db() as db:
            options=db.execute("""SELECT player_id FROM world_career_registrations
                WHERE career_id=? AND club_id=?""",
                (CAREER,self.manager_id)).fetchall()
            credible=[]
            for item in options:
                pid=item["player_id"]
                reference,_=_player_reference(db,DATASET,pid)
                if reference is None or reference>15_000_000:
                    continue
                interested=ai_interest(db,career_id=CAREER,player_id=pid)
                if interested:
                    credible.append((reference,pid))
            if not credible:
                self.fail("No genuinely squad-compatible, affordable buyer was available in this seeded test; do not fabricate one")
            self.home_value,self.home_player_id=max(credible)
        prefix="/world/play/career/"+CAREER
        self.assertIn("Nottingham Forest",self.get(prefix))
        management=prefix+"/management"
        self.assertIn("Board confidence",self.get(management))
        self.post(management+"/confidence",value="60")
        self.post(management+"/contract",player_id=str(self.home_player_id),
            wage_weekly="50000",end_date="2028-06-30",
            squad_role="regular_starter",
            source_kind="user_sandbox_assumption",
            source_note="Synthetic initial contract for isolated playtest")
        contract=self.read("""SELECT wage_weekly,end_date,squad_role,source_kind
            FROM world_career_management_contracts
            WHERE career_id=? AND player_id=?""",(CAREER,self.home_player_id))
        self.assertEqual(tuple(contract),
            (50000,"2028-06-30","regular_starter","user_sandbox_assumption"))
        self.post(management+"/objective",season_key="2026-27",
            expected_rank="19",league_size="20",expected_relegation="yes",
            strength_source="user_sandbox_assumption",
            source_note="Synthetic 19th-place expectation; not a real-season forecast")
        # A failed duplicate setup cannot overwrite locked expectations.
        changed=self.client.post(management+"/objective",data={
            "csrf":self.csrf,"season_key":"2026-27","expected_rank":"1",
            "league_size":"20","expected_relegation":"no",
            "strength_source":"user_sandbox_assumption",
            "source_note":"Attempted retroactive change"},
            base_url="https://localhost")
        self.assertIn("error=",changed.headers.get("Location",""))
        self.post(management+"/buying-board",max_fee_pct="130",
            max_headroom_use_pct="60",financial_objective="balanced",
            ambition="consolidation",ownership_priority="balanced",
            source_note="Synthetic board spending limits")
        self.assertIn("Board policy active",self.get(management))

        selling=prefix+"/selling"
        # Enhanced seller mode is already enabled for this new career.
        self.assertIn("Active for new offers",self.get(
            selling+"?player_id="+str(self.target_id)))
        from world_career_selling import DEFAULT_ACTIVATION_NOTE
        self.assertEqual(self.read("""SELECT source_note
            FROM world_career_selling_modes WHERE career_id=?""",
            (CAREER,))[0],DEFAULT_ACTIVATION_NOTE)
        self.assertIn("Active for new offers",self.get(
            selling+"?player_id="+str(self.target_id)))
        self.post(selling+"/circumstances",player_id=str(self.target_id),
            market_value=str(self.target_value),contract_years="1",
            squad_role="fringe",transfer_listed="yes",player_wants_exit="yes",
            financial_state="stable",replacement="available",
            seller_stance="sell",board_enabled="no",
            exceptional_offer_pct="",financial_objective="unknown",
            ambition="unknown",ownership_priority="unknown",
            assumed_manager_trust="unknown",
            source_note="Synthetic outgoing fringe player scenario")

        # A bid at 135% of rated value is affordable but beyond the board's
        # initial 130% fee ceiling. Nothing should enter the offers table.
        fee=max(100_000,((self.target_value*135+99)//100+9999)//10000*10000)
        bidkey="playtest-outgoing-fee"
        before=self.read("""SELECT COUNT(*) FROM world_career_offers
            WHERE career_id=?""",(CAREER,))[0]
        bad=self.client.post(prefix+"/offer",data={
            "csrf":self.csrf,"request_key":bidkey,
            "player_id":str(self.target_id),
            "buying_club_id":str(self.manager_id),
            "offered_fee":str(fee),"agreement_date":DATE,
            "seller_stance":"neutral"},base_url="https://localhost")
        self.assertEqual(bad.status_code,302)
        self.assertIn("error=",bad.headers.get("Location",""))
        self.assertEqual(self.read("SELECT COUNT(*) FROM world_career_offers WHERE career_id=?",
            (CAREER,))[0],before)

        # Confirm the synthetic 10th-place finish: the +18 performance
        # outperformance should move confidence across the trust tier.
        self.post(management+"/review",season_key="2026-27",
            actual_rank="10",promoted="no",relegated="no",
            cup_result="expected",
            result_note="SYNTHETIC playtest result: 10th place")
        confidence=self.read("""SELECT manager_confidence FROM world_career_management_board
            WHERE career_id=? AND club_id=?""",(CAREER,self.manager_id))[0]
        self.assertEqual(confidence,78)
        self.assertIn("2026-27",self.get(management))
        extra=self.client.post(management+"/review",data=dict(
            csrf=self.csrf,season_key="2026-27",actual_rank="1",
            promoted="no",relegated="no",cup_result="above",
            result_note="Changed actual after the fact"),base_url="https://localhost")
        self.assertIn("error=",extra.headers.get("Location",""))
        self.assertEqual(self.read("""SELECT manager_confidence FROM world_career_management_board
            WHERE career_id=? AND club_id=?""",(CAREER,self.manager_id))[0],78)

        self.post(prefix+"/offer",request_key=bidkey,
            player_id=str(self.target_id),buying_club_id=str(self.manager_id),
            offered_fee=str(fee),agreement_date=DATE,seller_stance="neutral")
        offer=self.read("""SELECT * FROM world_career_offers
            WHERE career_id=? AND request_key=?""",(CAREER,bidkey))
        self.assertIsNotNone(offer)
        self.assertEqual(offer["status"],"accepted_pending_contract")
        self.assertIn("Selling",self.get(prefix))

        # V2 player and agent require verified scenario conditions. Without
        # those, wages alone must not make the player sign.
        refusal=self.client.post(prefix+"/agree",data=dict(
            csrf=self.csrf,offer_id=str(offer["offer_id"]),weekly_wage="35000",
            contract_years="3",role_promise="key_player",
            agreement_date=DATE),base_url="https://localhost")
        self.assertIn("error=",refusal.headers.get("Location",""))
        self.post(prefix+"/circumstances",offer_id=str(offer["offer_id"]),
            current_wage_weekly="1000",current_role="fringe",
            transfer_listed="yes",renewal_status="not_offered",
            buyer_europe="none",seller_europe="none")
        self.post(prefix+"/agree",offer_id=str(offer["offer_id"]),
            weekly_wage="35000",contract_years="3",
            role_promise="key_player",agreement_date=DATE)
        agent=self.read("""SELECT status,proposed_wage_weekly FROM
            world_career_agent_terms WHERE offer_id=?""",(offer["offer_id"],))
        self.assertEqual(agent["status"],"accepted")
        self.assertEqual(agent["proposed_wage_weekly"],35000)
        # Only an explicit confirmation reserves a future agreement.
        self.assertEqual(self.read("SELECT status FROM world_career_offers WHERE offer_id=?",
            (offer["offer_id"],))[0],"accepted_pending_contract")
        self.post(prefix+"/confirm",offer_id=str(offer["offer_id"]),
                  agreement_date=DATE)
        pending=self.read("""SELECT status,effective_date FROM world_career_offers
            WHERE offer_id=?""",(offer["offer_id"],))
        self.assertEqual(pending["status"],"agreed_future")
        self.assertGreaterEqual(pending["effective_date"],"2027-07-01")
        self.assertEqual(self.read("""SELECT club_id FROM world_career_registrations
            WHERE career_id=? AND player_id=?""",(CAREER,self.target_id))[0],
            self.read("""SELECT selling_club_id FROM world_career_offers
                WHERE offer_id=?""",(offer["offer_id"],))[0])
        with self.db() as db:
            finances=wage_budget_breakdown(db,CAREER,self.manager_id)
            self.assertEqual(finances["reserved_future"],35000)
            self.assertLess(budget_remaining(db,CAREER,self.manager_id),45_000_000)
        self.assertIn("Future deal agreed",self.get(prefix))
        # Do not allow a second deal to reuse funds already reserved for the
        # first. This is a different seeded player to distinguish it from the
        # separate "already negotiating for this player" protection.
        if self.second_target_id is not None:
            count_before=self.read("""SELECT COUNT(*) FROM world_career_offers
                WHERE career_id=?""",(CAREER,))[0]
            second=self.client.post(prefix+"/offer",data=dict(
                csrf=self.csrf,request_key="second-overspend",
                player_id=str(self.second_target_id),
                buying_club_id=str(self.manager_id),
                offered_fee="45000000",agreement_date=DATE),
                base_url="https://localhost")
            self.assertEqual(second.status_code,302)
            self.assertIn("unreserved",second.headers.get("Location",""))
            self.assertEqual(self.read("""SELECT COUNT(*) FROM world_career_offers
                WHERE career_id=?""",(CAREER,))[0],count_before)

        # Incoming AI offer: board may direct the fee but no player can be
        # involuntarily registered elsewhere on this user-triggered event.
        self.post(selling+"/circumstances",player_id=str(self.home_player_id),
            market_value=str(self.home_value),contract_years="5",
            squad_role="key_player",transfer_listed="no",
            player_wants_exit="no",financial_state="stable",
            replacement="difficult",seller_stance="retain",
            board_enabled="yes",exceptional_offer_pct="50",
            financial_objective="balanced",ambition="consolidation",
            ownership_priority="balanced",assumed_manager_trust="unknown",
            source_note="Synthetic board-directed sale of protected player")
        self.post(prefix+"/ai-inbound",player_id=str(self.home_player_id))
        bids=self.read("""SELECT COUNT(*) FROM world_career_offers
            WHERE career_id=? AND player_id=? AND buying_club_id<>?""",
            (CAREER,self.home_player_id,self.manager_id))[0]
        self.assertGreater(bids,0)
        direct=self.read("""SELECT COUNT(*) FROM world_career_seller_offer_decisions d
            JOIN world_career_offers o ON o.offer_id=d.offer_id
            WHERE o.career_id=? AND o.player_id=?
              AND d.board_decision='direct_sale' AND o.status='accepted_pending_contract'""",
            (CAREER,self.home_player_id))[0]
        self.assertGreater(direct,0)
        self.assertEqual(self.read("""SELECT club_id FROM world_career_registrations
            WHERE career_id=? AND player_id=?""",
            (CAREER,self.home_player_id))[0],self.manager_id)

        # The AI bid now advances to independent player negotiations.
        # Unknown contract/European circumstances must NOT grant consent.
        inbound=self.read("""SELECT offer_id FROM world_career_offers
            WHERE career_id=? AND player_id=? AND buying_club_id<>?
              AND status='accepted_pending_contract' ORDER BY offer_id LIMIT 1""",
            (CAREER,self.home_player_id,self.manager_id))
        self.assertIsNotNone(inbound)
        self.post(prefix+"/incoming/advance",offer_id=str(inbound["offer_id"]))
        first=self.read("""SELECT status FROM world_career_incoming_approaches
            WHERE offer_id=?""",(inbound["offer_id"],))
        self.assertEqual(first["status"],"needs_information")
        self.assertEqual(self.read("""SELECT club_id FROM world_career_registrations
            WHERE career_id=? AND player_id=?""",
            (CAREER,self.home_player_id))[0],self.manager_id)
        self.post(prefix+"/incoming/circumstances",
            offer_id=str(inbound["offer_id"]),current_wage_weekly="50000",
            current_role="regular_starter",transfer_listed="no",
            renewal_status="renewal_offered",
            buyer_europe="none",seller_europe="none")
        self.post(prefix+"/incoming/advance",offer_id=str(inbound["offer_id"]))
        last=self.read("""SELECT status,decision_reason
            FROM world_career_incoming_approaches WHERE offer_id=?""",
            (inbound["offer_id"],))
        self.assertIn(last["status"],("player_refused","role_refused",
            "wage_limit","agent_counter","terms_accepted"))
        self.assertEqual(self.read("""SELECT club_id FROM world_career_registrations
            WHERE career_id=? AND player_id=?""",
            (CAREER,self.home_player_id))[0],self.manager_id)

        # Reload through entirely new HTTP requests AND fresh SQLite connections.
        self.assertIn("Selling",self.get(prefix))
        self.assertIn("2026-27",self.get(management))
        self.assertIn("Scenario locked",self.get(selling+"?player_id="+str(self.home_player_id)))
        with self.db() as db:
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM world_career_season_reviews
                WHERE career_id=?""",(CAREER,)).fetchone()[0],1)
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM world_career_offers
                WHERE career_id=? AND status='agreed_future'""",
                (CAREER,)).fetchone()[0],1)
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(),[])

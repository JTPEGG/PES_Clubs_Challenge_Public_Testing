"""Tests for isolated career negotiations, economy versions and registrations."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from flask import Flask
from world_v2 import initialize_world
from world_explorer import initialize_catalog
from world_careers import (
    initialize_career_engine,start_sandbox,propose_offer,accept_counter,
    settle_future_deal,withdraw_offer,budget_remaining,ai_interest,agent_terms,negotiate_agent,wage_budget_breakdown,confirm_future_agreement,player_move_interest
)
from world_careers_ui import create_careers_blueprint


class CareerMarketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.tmp.name)/"career.sqlite"
        cls.db=sqlite3.connect(cls.path,isolation_level=None)
        cls.db.execute("PRAGMA foreign_keys=ON")
        initialize_world(cls.db)
        initialize_catalog(cls.db)
        initialize_career_engine(cls.db)
        cls.arsenal=cls.db.execute("SELECT club_id FROM world_clubs WHERE name='Arsenal'").fetchone()[0]
        cls.city=cls.db.execute("SELECT club_id FROM world_clubs WHERE name='Manchester City'").fetchone()[0]
        cls.haaland=cls.db.execute("""SELECT player_id FROM world_player_source_refs
            WHERE source_name='EAFC27' AND external_id='239085'""").fetchone()[0]
        cls.target=cls.db.execute("""SELECT r.player_id FROM world_dataset_rosters r
            JOIN world_dataset_ratings x ON x.player_id=r.player_id AND x.dataset_id=r.dataset_id
            WHERE r.dataset_id='england-2026-27-fc27' AND r.club_id!=?
            AND x.overall BETWEEN 60 AND 65 LIMIT 1""",(cls.arsenal,)).fetchone()[0]
        start_sandbox(cls.db,career_id="test-26",dataset_id="england-2026-27-fc27",
            title="Test career",manager_club_id=cls.arsenal,
            pes_lock_date="2026-08-01",next_summer_date="2027-07-01")

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        cls.tmp.cleanup()

    def test_01_existing_career_is_untouched(self):
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM world_transfers").fetchone()[0],0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM world_dataset_rosters WHERE dataset_id='england-2026-27-fc27'").fetchone()[0],
                         self.db.execute("SELECT COUNT(*) FROM world_career_registrations WHERE career_id='test-26'").fetchone()[0])

    def test_02_first_offer_idempotency(self):
        before=budget_remaining(self.db,"test-26",self.arsenal)
        oid=propose_offer(self.db,career_id="test-26",request_key="deal-a",player_id=self.target,
            buying_club_id=self.arsenal,offered_fee=1_000_000,agreement_date="2027-01-05")
        duplicate=propose_offer(self.db,career_id="test-26",request_key="deal-a",player_id=self.target,
            buying_club_id=self.arsenal,offered_fee=1_000_000,agreement_date="2027-01-05")
        self.assertEqual(oid,duplicate)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM world_career_offers").fetchone()[0],1)
        self.assertLess(budget_remaining(self.db,"test-26",self.arsenal),before)

    def test_03_duplicate_negotiation_blocked(self):
        with self.assertRaises(ValueError):
            propose_offer(self.db,career_id="test-26",request_key="another-key",player_id=self.target,
                buying_club_id=self.arsenal,offered_fee=2_000_000,agreement_date="2027-01-06")

    def test_04_rejected_offer_not_reserved_and_withdraw_releases(self):
        oid=self.db.execute("SELECT offer_id FROM world_career_offers WHERE request_key='deal-a'").fetchone()[0]
        before=budget_remaining(self.db,"test-26",self.arsenal)
        withdraw_offer(self.db,career_id="test-26",offer_id=oid)
        self.assertGreater(budget_remaining(self.db,"test-26",self.arsenal),before)
        self.assertNotEqual(self.db.execute("SELECT club_id FROM world_career_registrations WHERE career_id='test-26' AND player_id=?",(self.target,)).fetchone()[0],self.arsenal)

    def test_05_future_deal_pending_wages(self):
        # Uses lower-cost non-star reference target: to keep agreement within
        # Arsenal's synthetic budget and avoid inventing a real player's deal.
        target=self.target
        oid=propose_offer(self.db,career_id="test-26",request_key="deal-b",player_id=target,
            buying_club_id=self.arsenal,offered_fee=10_000_000,agreement_date="2027-01-05")
        status=self.db.execute("SELECT status FROM world_career_offers WHERE offer_id=?",(oid,)).fetchone()[0]
        self.assertEqual(status,"accepted_pending_contract")
        with self.assertRaisesRegex(ValueError,"agent terms"):
            settle_future_deal(self.db,career_id="test-26",offer_id=oid,
                weekly_wage=20_000,agreement_date="2027-01-05")
        terms=agent_terms(self.db,career_id="test-26",offer_id=oid)
        proposed=max(20_000,terms["demanded_wage_weekly"])
        self.assertEqual(negotiate_agent(self.db,career_id="test-26",offer_id=oid,
            weekly_wage=proposed,contract_years=3,agreement_date="2027-01-05"),"accepted")
        date=confirm_future_agreement(self.db,career_id="test-26",offer_id=oid,
            agreement_date="2027-01-05")
        self.assertEqual(date,"2027-07-01")
        self.assertEqual(self.db.execute("SELECT status FROM world_career_offers WHERE offer_id=?",(oid,)).fetchone()[0],"agreed_future")
        self.assertGreater(self.db.execute("SELECT COUNT(*) FROM world_career_offer_events WHERE offer_id=?",(oid,)).fetchone()[0],1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM world_transfers").fetchone()[0],0)

    def test_055_agent_counter_then_accepts_and_future_registration(self):
        from world_careers import propose_offer
        row=self.db.execute("""SELECT r.player_id FROM world_dataset_rosters r
            JOIN world_dataset_ratings x ON x.player_id=r.player_id AND x.dataset_id=r.dataset_id
            WHERE r.dataset_id='england-2026-27-fc27' AND r.club_id!=?
            AND x.overall BETWEEN 66 AND 68 LIMIT 1""",(self.arsenal,)).fetchone()
        self.assertIsNotNone(row)
        pid=row[0]
        oid=propose_offer(self.db,career_id="test-26",request_key="agent-test",
            player_id=pid,buying_club_id=self.arsenal,offered_fee=10_000_000,
            agreement_date="2027-01-06")
        self.assertEqual(self.db.execute("SELECT status FROM world_career_offers WHERE offer_id=?",(oid,)).fetchone()[0],
                         "accepted_pending_contract")
        terms=agent_terms(self.db,career_id="test-26",offer_id=oid)
        self.assertGreater(terms["demanded_wage_weekly"],0)
        self.assertIn(negotiate_agent(self.db,career_id="test-26",offer_id=oid,
            weekly_wage=1000,contract_years=3,agreement_date="2027-01-07"),
            ("countered","rejected"))
        self.assertEqual(self.db.execute("SELECT status FROM world_career_offers WHERE offer_id=?",(oid,)).fetchone()[0],
                         "accepted_pending_contract")
        result=negotiate_agent(self.db,career_id="test-26",offer_id=oid,
            weekly_wage=terms["demanded_wage_weekly"],contract_years=3,
            agreement_date="2027-01-08")
        self.assertEqual(result,"accepted")
        self.assertEqual(self.db.execute("SELECT status FROM world_career_offers WHERE offer_id=?",(oid,)).fetchone()[0],"accepted_pending_contract")
        self.assertIsNone(self.db.execute("SELECT effective_date FROM world_career_offers WHERE offer_id=?",(oid,)).fetchone()[0])
        self.assertIn("signal",player_move_interest(self.db,career_id="test-26",offer_id=oid))
        self.assertEqual(confirm_future_agreement(self.db,career_id="test-26",offer_id=oid,agreement_date="2027-01-08"),"2027-07-01")
        self.assertEqual(self.db.execute("SELECT effective_date FROM world_career_offers WHERE offer_id=?",(oid,)).fetchone()[0],"2027-07-01")
        self.assertNotEqual(self.db.execute("SELECT club_id FROM world_career_registrations WHERE career_id='test-26' AND player_id=?",(pid,)).fetchone()[0],self.arsenal)

    def test_056_wage_headroom_includes_future_agreements(self):
        wages=wage_budget_breakdown(self.db,"test-26",self.arsenal)
        self.assertGreater(wages["total"],0)
        self.assertEqual(wages["remaining"],
                         wages["total"]-wages["committed"]-wages["reserved_future"])
        future=self.db.execute("""SELECT COALESCE(SUM(offered_wage_weekly),0)
            FROM world_career_offers WHERE career_id='test-26'
            AND buying_club_id=? AND status='agreed_future'""",(self.arsenal,)).fetchone()[0]
        self.assertEqual(wages["reserved_future"],future)
        self.assertGreater(wages["reserved_future"],0)

    def test_057_lower_league_move_requires_sporting_assurances(self):
        from world_careers import start_sandbox
        lower=self.db.execute("SELECT club_id FROM world_clubs WHERE name='Bradford City'").fetchone()[0]
        start_sandbox(self.db,career_id="reputation-roles",dataset_id="england-2026-27-fc27",
            title="Role requirements",manager_club_id=lower,
            pes_lock_date="2026-08-01",next_summer_date="2027-07-01")
        championship=self.db.execute("""SELECT r.player_id,r.club_id FROM world_dataset_rosters r
            JOIN world_dataset_entries e ON e.club_id=r.club_id AND e.dataset_id=r.dataset_id
            JOIN world_dataset_ratings x ON x.player_id=r.player_id AND x.dataset_id=r.dataset_id
            JOIN world_clubs c ON c.club_id=r.club_id
            WHERE r.dataset_id='england-2026-27-fc27' AND e.competition_id='ENG2'
            AND c.name='Derby County' AND x.overall BETWEEN 60 AND 65 LIMIT 1""").fetchone()
        self.assertIsNotNone(championship)
        pid,seller=championship
        oid=self.db.execute("""INSERT INTO world_career_offers(
            career_id,request_key,player_id,buying_club_id,selling_club_id,
            offered_fee,status,agreement_date,economy_version)
            VALUES('reputation-roles','role-case',?,?,?,250000,'accepted_pending_contract',
                   '2027-01-08','prototype-v1')""",(pid,lower,seller)).lastrowid
        interest=player_move_interest(self.db,career_id="reputation-roles",offer_id=oid)
        self.assertEqual(interest["decision"],"needs_assurances")
        with self.assertRaisesRegex(ValueError,"first-team"):
            negotiate_agent(self.db,career_id="reputation-roles",offer_id=oid,
                weekly_wage=20000,contract_years=3,
                agreement_date="2027-01-08",role_promise="rotation")
        outcome=negotiate_agent(self.db,career_id="reputation-roles",offer_id=oid,
            weekly_wage=20000,contract_years=3,
            agreement_date="2027-01-08",role_promise="key_player")
        self.assertEqual(outcome,"accepted")
        self.assertEqual(self.db.execute("SELECT role_promise FROM world_career_agent_terms WHERE offer_id=?",
            (oid,)).fetchone()[0],"key_player")
        self.assertEqual(self.db.execute("SELECT status FROM world_career_offers WHERE offer_id=?",
            (oid,)).fetchone()[0],"accepted_pending_contract")
        # A truly large disparity still blocks unrealistic moves regardless of pay.
        from world_reputation_v2 import assess_player_interest
        self.assertFalse(assess_player_interest(buyer_tier=4,seller_tier=1,
            buyer_score=30,seller_score=95)["can_negotiate"])

    def test_06_ai_interest_is_advisory(self):
        offers=self.db.execute("SELECT COUNT(*) FROM world_career_offers").fetchone()[0]
        result=ai_interest(self.db,career_id="test-26",player_id=self.haaland)
        self.assertIsInstance(result,list)
        self.assertEqual(offers,self.db.execute("SELECT COUNT(*) FROM world_career_offers").fetchone()[0])

    def test_07_dashboard_read_only(self):
        app=Flask(__name__)
        app.register_blueprint(create_careers_blueprint(self.path))
        import os
        from unittest.mock import patch
        from itsdangerous import URLSafeTimedSerializer
        with patch.dict(os.environ,{"WORLD_MARKET_COOKIE_SECRET":"test-signing-key"}):
            client=app.test_client()
            self.assertEqual(client.get("/world/careers").status_code,302)
            token=URLSafeTimedSerializer("test-signing-key",salt="pes-world-play-v1").dumps("market-admin")
            client.set_cookie("world_play_access",token)
            response=client.get("/world/careers?career=test-26")
        self.assertEqual(response.status_code,200)
        self.assertIn(b"Career transfer negotiations",response.data)
        self.assertIn(b"Test career",response.data)


if __name__=="__main__":
    unittest.main()

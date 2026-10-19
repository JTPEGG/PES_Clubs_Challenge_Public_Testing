"""Versioned fictional player/agent decisions and save isolation tests.

These are gameplay fixtures, NOT assertions about any real player's consent.
Historic prestige snapshots here remain explicitly provisional and do not
activate on pre-existing career saves.
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from flask import Flask

from world_v2 import initialize_world
from world_explorer import initialize_catalog
from world_reputation_v2 import initialize_pyramid,assess_player_interest
from world_reputation_progression import initialize_progression
from world_careers import (
    initialize_career_engine,start_sandbox,career_player_policy,prestige_snapshot,
    player_move_interest,agent_terms,negotiate_agent,confirm_future_agreement,
    wage_budget_breakdown,
)
from world_player_decisions import (
    DECISION_VERSION,LEGACY_VERSION,phase_for_age,evaluate_player_choice,
    agent_minimum_wage,competitor_advantage,contract_length_consideration,
)
from world_player_decisions_ui import create_player_decisions_blueprint

DATASET="england-2026-27-fc27"


class PlayerDecisionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.temp.name)/"player-decisions.sqlite"
        cls.db=sqlite3.connect(cls.path)
        cls.db.row_factory=sqlite3.Row
        cls.db.execute("PRAGMA foreign_keys=ON")
        initialize_world(cls.db)
        initialize_catalog(cls.db)
        initialize_pyramid(cls.db)
        initialize_career_engine(cls.db)
        initialize_progression(cls.db)
        cls.ids=dict(cls.db.execute("SELECT name,club_id FROM world_clubs"))
        for career,version in (("decisions-new",DECISION_VERSION),
                               ("decisions-older",LEGACY_VERSION)):
            start_sandbox(cls.db,career_id=career,dataset_id=DATASET,
                title="Fictional decision model unit test",
                manager_club_id=cls.ids["Hull City"],
                pes_lock_date="2026-08-01",next_summer_date="2027-07-01",
                player_decision_version=version)
        cls.target=cls.db.execute("""SELECT r.player_id FROM world_dataset_rosters r
            JOIN world_clubs c ON c.club_id=r.club_id
            JOIN world_dataset_ratings x ON x.dataset_id=r.dataset_id
                                   AND x.player_id=r.player_id
            JOIN world_players p ON p.player_id=r.player_id
            WHERE r.dataset_id=? AND c.name='West Ham United'
            AND x.overall BETWEEN 62 AND 78 AND p.birth_date IS NOT NULL
            ORDER BY x.overall LIMIT 1""",(DATASET,)).fetchone()[0]

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        cls.temp.cleanup()

    def _pending_offer(self,career,request_key,buyer_name):
        seller=self.ids["West Ham United"]
        return self.db.execute("""INSERT INTO world_career_offers(
            career_id,request_key,player_id,buying_club_id,selling_club_id,
            offered_fee,status,agreement_date,economy_version)
            VALUES(?,?,?,?,?,250000,'accepted_pending_contract',
                   '2027-01-10','prototype-v1')""",
            (career,request_key,self.target,self.ids[buyer_name],seller)).lastrowid

    def test_01_frozen_reputation_snapshots_in_new_only(self):
        self.assertEqual(career_player_policy(self.db,"decisions-new")["version"],
                         DECISION_VERSION)
        self.assertEqual(career_player_policy(self.db,"decisions-older")["version"],
                         LEGACY_VERSION)
        self.assertEqual(self.db.execute("""SELECT COUNT(*) FROM world_career_prestige_snapshots
            WHERE career_id='decisions-new'""").fetchone()[0],92)
        self.assertEqual(self.db.execute("""SELECT COUNT(*) FROM world_career_prestige_snapshots
            WHERE career_id='decisions-older'""").fetchone()[0],0)
        hull=prestige_snapshot(self.db,"decisions-new",self.ids["Hull City"])
        self.assertEqual(hull["score"],34)
        self.assertEqual(prestige_snapshot(
            self.db,"decisions-new",self.ids["Arsenal"])["score"],94)
        self.assertIn("review",hull["review_status"])
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM world_reputation_prestige_reviews").fetchone()[0],0)
        with self.assertRaisesRegex(ValueError,"92-club prestige"):
            start_sandbox(self.db,career_id="different-dataset",dataset_id="bogus",
                title="invalid",manager_club_id=self.ids["Hull City"],
                pes_lock_date="2026-08-01",next_summer_date="2027-07-01",
                player_decision_version=DECISION_VERSION)

    def test_02_age_stage_changes_preference_for_equal_club_facts(self):
        self.assertEqual(phase_for_age(21),"development")
        self.assertEqual(phase_for_age(27),"prime")
        self.assertEqual(phase_for_age(34),"veteran")
        self.assertEqual(phase_for_age(None),"unassessed")
        args=dict(buyer_tier=1,seller_tier=1,buyer_score=78,seller_score=78,
                  buyer_prestige=55,seller_prestige=80,overall=77)
        youth=evaluate_player_choice(**args,age=21)
        peak=evaluate_player_choice(**args,age=27)
        veteran=evaluate_player_choice(**args,age=34)
        self.assertEqual(youth["decision"],"open_to_talks")
        self.assertEqual(peak["decision"],"needs_assurances")
        self.assertEqual(veteran["decision"],"open_to_talks")
        assertRole=evaluate_player_choice(**args,age=27,role_promise="important")
        self.assertEqual(assertRole["decision"],"open_to_talks")

    def test_03_hard_reject_cannot_be_overridden_by_salaries(self):
        huge_drop=evaluate_player_choice(
            buyer_tier=4,seller_tier=1,buyer_score=24,seller_score=95,
            buyer_prestige=20,seller_prestige=98,overall=91,age=27,
            role_promise="key_player")
        self.assertEqual(huge_drop["decision"],"uninterested")
        self.assertFalse(huge_drop["can_negotiate"])
        self.assertIsNone(agent_minimum_wage(base_wage=300_000,choice=huge_drop))
        missing=evaluate_player_choice(
            buyer_tier=1,seller_tier=1,buyer_score=70,seller_score=70,
            buyer_prestige=None,seller_prestige=90,overall=70,age=22)
        self.assertEqual(missing["decision"],"review")
        self.assertFalse(missing["can_negotiate"])

    def test_04_role_required_and_wage_premium_in_live_new_career(self):
        oid=self._pending_offer("decisions-new","hull-west-ham","Hull City")
        self.db.commit()
        preview=player_move_interest(self.db,career_id="decisions-new",offer_id=oid)
        self.assertEqual(preview["policy_version"],DECISION_VERSION)
        self.assertEqual(preview["decision"],"needs_assurances")
        self.assertEqual(preview["required_role"],"important")
        self.assertEqual(preview["buyer_prestige"],34)
        self.assertEqual(preview["seller_prestige"],70)
        self.assertEqual(preview["competing_pressure"],0)
        offered=player_move_interest(self.db,career_id="decisions-new",
                                      offer_id=oid,role_promise="important")
        self.assertEqual(offered["decision"],"open_to_talks")
        terms=agent_terms(self.db,career_id="decisions-new",offer_id=oid)
        self.assertGreater(terms["demanded_wage_weekly"],0)
        self.assertEqual(terms["status"],"awaiting_offer")
        with self.assertRaisesRegex(ValueError,"first-team"):
            negotiate_agent(self.db,career_id="decisions-new",offer_id=oid,
                weekly_wage=terms["demanded_wage_weekly"],contract_years=3,
                agreement_date="2027-01-10",role_promise="rotation")
        result=negotiate_agent(self.db,career_id="decisions-new",offer_id=oid,
            weekly_wage=terms["demanded_wage_weekly"],contract_years=3,
            agreement_date="2027-01-10",role_promise="important")
        self.assertEqual(result,"accepted")
        prior=self.db.execute("""SELECT club_id FROM world_career_registrations
            WHERE career_id='decisions-new' AND player_id=?""",(self.target,)).fetchone()[0]
        self.assertEqual(prior,self.ids["West Ham United"])
        self.assertEqual(confirm_future_agreement(self.db,career_id="decisions-new",
            offer_id=oid,agreement_date="2027-01-10"),"2027-07-01")
        self.assertEqual(self.db.execute("""SELECT club_id FROM world_career_registrations
            WHERE career_id='decisions-new' AND player_id=?""",(self.target,)).fetchone()[0],prior)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM world_transfers").fetchone()[0],0)

    def test_05_older_career_keeps_sporting_only_rules(self):
        oid=self._pending_offer("decisions-older","older-west-ham","Hull City")
        self.db.commit()
        outcome=player_move_interest(self.db,career_id="decisions-older",offer_id=oid)
        self.assertEqual(outcome["policy_version"],LEGACY_VERSION)
        self.assertNotIn("buyer_prestige",outcome)
        self.assertNotIn("player_phase",outcome)
        self.assertEqual(outcome["decision"],"open_to_talks")
        self.assertIsNone(prestige_snapshot(self.db,"decisions-older",
                                            self.ids["Hull City"]))
        assert self.db.execute("""SELECT COUNT(*) FROM world_career_registrations
            WHERE career_id='decisions-older'""").fetchone()[0]>0

    def test_06_recorded_rival_bid_only_increases_pressure_when_present(self):
        oid=self._pending_offer("decisions-new","new-rival-target","Hull City")
        self.db.commit()
        without=player_move_interest(self.db,career_id="decisions-new",offer_id=oid)
        self.assertEqual(without["competing_pressure"],0)
        agent_before=agent_minimum_wage(
            base_wage=5000,choice=without,competing_bid=False)
        rival=self._pending_offer("decisions-new","rival-arsenal","Arsenal")
        self.db.commit()
        after=player_move_interest(self.db,career_id="decisions-new",offer_id=oid)
        self.assertGreaterEqual(after["competing_pressure"],13)
        self.assertEqual(after["required_role"],"important")
        agent_after=agent_minimum_wage(
            base_wage=5000,choice=after,competing_bid=True)
        self.assertGreater(agent_after,agent_before)
        self.db.execute("""UPDATE world_career_offers SET status='withdrawn'
            WHERE offer_id=?""",(rival,))
        self.db.commit()
        withdrawn=player_move_interest(self.db,career_id="decisions-new",offer_id=oid)
        self.assertEqual(withdrawn["competing_pressure"],0)

    def test_07_career_snapshot_survives_global_calibration_changes(self):
        snapshot=prestige_snapshot(self.db,"decisions-new",self.ids["Hull City"])
        from unittest.mock import patch
        with patch("world_prestige_full.score_club",
                   side_effect=RuntimeError("Global rubric changed")):
            self.assertEqual(prestige_snapshot(
                self.db,"decisions-new",self.ids["Hull City"]),snapshot)
        self.assertEqual(self.db.execute("""SELECT COUNT(*) FROM world_career_player_policies
            WHERE career_id='decisions-older'""").fetchone()[0],0)

    def test_08_contract_and_agent_requirements_use_finite_premiums(self):
        args=dict(buyer_tier=1,seller_tier=1,buyer_score=75,seller_score=75,
                  buyer_prestige=45,seller_prestige=70,overall=75,age=27,
                  role_promise="important")
        choice=evaluate_player_choice(**args)
        self.assertEqual(choice["decision"],"open_to_talks")
        self.assertTrue(0<agent_minimum_wage(base_wage=5000,choice=choice)<9000)
        self.assertEqual(competitor_advantage(
            rival_sporting=90,rival_prestige=90,
            buyer_sporting=65,buyer_prestige=40),25)
        self.assertIsNotNone(contract_length_consideration(phase="prime",years=1))
        self.assertIsNone(contract_length_consideration(phase="veteran",years=1))
        self.assertLessEqual(agent_minimum_wage(base_wage=500_000,choice=choice),350_000)

    def test_09_public_lab_is_get_only_and_cannot_modify_careers(self):
        app=Flask(__name__)
        app.register_blueprint(create_player_decisions_blueprint(self.path))
        client=app.test_client()
        before=self.db.execute(
            "SELECT COUNT(*) FROM world_career_offers").fetchone()[0]
        for query in ("",
                      "?buyer=4&seller=7&age=22&overall=72&role=important",
                      "?age=27&overall=88&role=key_player&wage=500000&rival=32"):
            res=client.get("/world/player-decisions"+query)
            self.assertEqual(res.status_code,200)
            self.assertIn(b"Player &amp; Agent Decision Laboratory",res.data)
            self.assertIn(b"provisional",res.data.lower())
            self.assertIn(b"fictional",res.data.lower())
            self.assertIn(b"Player decision",res.data)
            self.assertIn(b"Agent negotiation preview",res.data)
        self.assertEqual(client.post("/world/player-decisions").status_code,405)
        self.assertEqual(client.get("/world/player-decisions?age=110").status_code,400)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM world_career_offers").fetchone()[0],before)


if __name__=="__main__":
    unittest.main()

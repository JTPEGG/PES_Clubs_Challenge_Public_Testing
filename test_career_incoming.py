"""Automated season baselines and simulated inbound consent guards.

All test transfers are fictional and career-scoped; no live database is edited.
"""
import unittest
from unittest.mock import patch
from world_career_incoming import (
    initialize_incoming_approaches,incoming_approach,advance_incoming_approach,
    finalise_incoming_approach,
)
from world_career_strength import strength_baseline
from test_career_selling import career_fixture
from world_career_selling import enable_career_selling
from world_careers import career_player_policy


class GoalkeeperPlayingTimeTests(unittest.TestCase):
    def test_goalkeeper_starter_promise_is_position_specific(self):
        import sqlite3
        from world_career_incoming import _role_for_ai
        db=sqlite3.connect(":memory:")
        try:
            db.executescript("""
            CREATE TABLE world_career_saves(career_id TEXT,dataset_id TEXT);
            CREATE TABLE world_players(player_id INTEGER,primary_position TEXT);
            CREATE TABLE world_career_registrations(
                career_id TEXT,player_id INTEGER,club_id INTEGER);
            CREATE TABLE world_dataset_ratings(
                dataset_id TEXT,player_id INTEGER,overall INTEGER);
            INSERT INTO world_career_saves VALUES('career-a','test');
            """)
            # An AI club whose outfield squad is much stronger than its keepers.
            squad=[(1,60,"GK"),(2,58,"GK")]+[
                (10+n,73+n,"CF") for n in range(12)]
            for pid,ovr,pos in squad:
                db.execute("INSERT INTO world_players VALUES(?,?)",(pid,pos))
                db.execute("INSERT INTO world_career_registrations VALUES(?,?,2)",
                           ("career-a",pid))
                db.execute("INSERT INTO world_dataset_ratings VALUES('test',?,?)",
                           (pid,ovr))
            db.execute("INSERT INTO world_players VALUES(99,'GK')")
            db.commit()
            with patch("world_careers._player_reference",
                       return_value=(150000,65)):
                self.assertEqual(_role_for_ai(db,career_id="career-a",
                    player_id=99,buyer_club_id=2,
                    required_role="regular_starter"),"regular_starter")
            # A weaker alternative keeper should NOT be promised the same
            # regular-starter status in this prospective buyer squad.
            with patch("world_careers._player_reference",
                       return_value=(150000,59)):
                self.assertIsNone(_role_for_ai(db,career_id="career-a",
                    player_id=99,buyer_club_id=2,
                    required_role="regular_starter"))
                self.assertEqual(_role_for_ai(db,career_id="career-a",
                    player_id=99,buyer_club_id=2,
                    required_role="none"),"rotation")
        finally:
            db.close()


class IncomingDecisionTests(unittest.TestCase):
    def setUp(self):
        self.db=career_fixture()
        # The incoming rival-choice code reads club display names. The older
        # minimal seller fixture has only IDs; mirror the real world_clubs schema.
        self.db.execute("ALTER TABLE world_clubs ADD COLUMN name TEXT")
        self.db.execute("UPDATE world_clubs SET name='Fixture club ' || club_id")
        self.db.execute("ALTER TABLE world_career_offers ADD COLUMN effective_date TEXT")
        initialize_incoming_approaches(self.db)
        from world_career_transfer_protocol import (initialize_transfer_protocol,
                                                      enable_transfer_protocol)
        initialize_transfer_protocol(self.db)
        enable_transfer_protocol(self.db,career_id="career-a",
            activation_note="Explicit fictional five-stage playtest")
        enable_career_selling(self.db,career_id="career-a",
            source_note="Opt-in simulated selling terms")
        self.db.execute("""UPDATE world_career_offers SET player_id=101,
            buying_club_id=2,selling_club_id=1,
            status='accepted_pending_contract',offered_fee=2000000,
            agreement_date='2026-10-14' WHERE offer_id=1""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS world_career_player_policies (
            career_id TEXT PRIMARY KEY,decision_version TEXT,prestige_source_version TEXT)""")
        self.db.execute("""INSERT INTO world_career_player_policies
            VALUES('career-a','player-decisions-v2','test')""")
        self.db.commit()
    def tearDown(self):
        self.db.close()
    def advance(self):
        return advance_incoming_approach(self.db,career_id="career-a",offer_id=1)
    def test_missing_player_details_never_mean_agreement(self):
        with patch("world_careers.player_move_interest",
            return_value={"decision":"review","can_negotiate":False,
                          "reason":"Current wage unknown"}):
            result=self.advance()
        self.assertEqual(result["status"],"needs_information")
        self.assertEqual(self.db.execute("SELECT status FROM world_career_offers WHERE offer_id=1").fetchone()[0],
                         "accepted_pending_contract")
        self.assertEqual(self.db.execute("SELECT club_id FROM world_career_registrations WHERE career_id='career-a' AND player_id=101").fetchone()[0],1)

    def test_player_refusal_overrides_board_sale_and_closes_offer(self):
        with patch("world_careers.player_move_interest",
            return_value={"decision":"uninterested","can_negotiate":False,
                          "reason":"No credible sporting motivation"}):
            result=self.advance()
        self.assertEqual(result["status"],"player_refused")
        self.assertEqual(self.db.execute("SELECT status FROM world_career_offers WHERE offer_id=1").fetchone()[0],
                         "withdrawn")
        self.assertEqual(self.db.execute("SELECT club_id FROM world_career_registrations WHERE career_id='career-a' AND player_id=101").fetchone()[0],1)
        self.assertEqual(self.advance()["status"],"player_refused")

    def test_uncredible_key_player_promise_stalls_no_registration(self):
        with patch("world_careers.player_move_interest",
            return_value={"decision":"needs_assurances","can_negotiate":True,
                          "required_role":"key_player","reason":"Wants a key player role"}),patch(
                "world_career_incoming._role_for_ai",return_value=None):
            response=self.advance()
        self.assertEqual(response["status"],"role_refused")
        self.assertEqual(self.db.execute("SELECT status FROM world_career_offers WHERE offer_id=1").fetchone()[0],
                         "accepted_pending_contract")

    def test_agent_counter_then_accept_then_explicit_future_agreement(self):
        # Stub only the player's exact willingness and the buyer/agent
        # economic policy. Exercise the actual persistent multi-stage
        # transition and existing offer state; no squad registration changes.
        self.db.executescript("""
        CREATE TABLE world_career_agent_terms(
          offer_id INTEGER PRIMARY KEY,career_id TEXT,status TEXT,
          demanded_wage_weekly INTEGER,rounds INTEGER,
          proposed_wage_weekly INTEGER,role_promise TEXT);
        """)
        signal={"decision":"open_to_talks","can_negotiate":True,
                "required_role":"none","reason":"Scenario player open to talks"}
        def agent_init(conn,*,career_id,offer_id):
            conn.execute("""INSERT OR IGNORE INTO world_career_agent_terms
                (offer_id,career_id,status,demanded_wage_weekly,rounds)
                VALUES(?,?,'awaiting_offer',10000,0)""",(offer_id,career_id))
            conn.commit()
            return {}
        def agent_reply(conn,*,career_id,offer_id,weekly_wage,contract_years,
                        agreement_date,role_promise):
            status="accepted" if weekly_wage>=10000 else "countered"
            conn.execute("""UPDATE world_career_agent_terms
                SET status=?,proposed_wage_weekly=?,rounds=rounds+1
                WHERE offer_id=?""",(status,weekly_wage,offer_id))
            conn.commit()
            return status
        def finish(conn,*,career_id,offer_id,agreement_date):
            conn.execute("""UPDATE world_career_offers SET status='agreed_future',
                offered_wage_weekly=10000,effective_date='2027-07-01'
                WHERE offer_id=?""",(offer_id,))
            conn.commit()
            return "2027-07-01"
        with patch("world_careers.player_move_interest",return_value=signal),patch(
            "world_career_incoming._role_for_ai",return_value="regular_starter"),patch(
            "world_careers.agent_terms",side_effect=agent_init),patch(
            "world_careers.negotiate_agent",side_effect=agent_reply),patch(
            "world_careers.confirm_future_agreement",side_effect=finish):
            first=self.advance()
            self.assertEqual(first["status"],"agent_counter")
            self.assertEqual(first["offered_wage_weekly"],9000)
            second=self.advance()
            self.assertEqual(second["status"],"terms_accepted")
            self.assertEqual(second["offered_wage_weekly"],10000)
            # Repeated AI negotiation steps can never sign a transfer.
            third=self.advance()
            self.assertEqual(third["status"],"terms_accepted")
            self.assertEqual(self.db.execute(
                "SELECT status FROM world_career_offers WHERE offer_id=1").fetchone()[0],
                "accepted_pending_contract")
            signed=finalise_incoming_approach(self.db,career_id="career-a",offer_id=1)
            self.assertEqual(signed["status"],"future_agreed")
            self.assertEqual(finalise_incoming_approach(
                self.db,career_id="career-a",offer_id=1)["status"],"future_agreed")
        self.assertEqual(self.db.execute("SELECT status FROM world_career_offers WHERE offer_id=1").fetchone()[0],
                         "agreed_future")
        self.assertEqual(self.db.execute("""SELECT club_id FROM world_career_registrations
            WHERE career_id='career-a' AND player_id=101""").fetchone()[0],1)

    def test_legacy_offer_keeps_legacy_rules_after_career_opt_in(self):
        from world_career_transfer_protocol import offer_uses_five_stages
        # This fixture's offer preceded activation; enabling the career
        # must not retroactively alter its transfer protocol.
        self.assertFalse(offer_uses_five_stages(self.db,1))

    def test_only_own_squad_incoming_offer_may_advance(self):
        self.db.execute("UPDATE world_career_offers SET selling_club_id=2 WHERE offer_id=1")
        self.db.commit()
        with self.assertRaises(ValueError):
            self.advance()

    def test_does_not_change_existing_career_or_other_offer(self):
        self.db.execute("UPDATE world_career_offers SET career_id='career-b' WHERE offer_id=1")
        self.db.commit()
        with self.assertRaises(ValueError):
            self.advance()


class StrengthProxyTests(unittest.TestCase):
    def test_career_must_exist_before_strength_baseline(self):
        from world_career_strength import strength_baseline
        conn=career_fixture()
        try:
            with self.assertRaisesRegex(ValueError,"active sandbox"):
                strength_baseline(conn,career_id="nonexistent",club_id=1)
        finally:
            conn.close()

if __name__=="__main__":
    unittest.main()

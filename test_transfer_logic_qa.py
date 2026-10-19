"""QA: competing offers and final player choice — disposable SQLite only.

These are fictional transfer test cases, not assertions about real players.
Run with: python -m unittest -v test_transfer_logic_qa
"""
import unittest
from unittest.mock import patch

from test_career_selling import career_fixture
from world_career_incoming import competing_player_choice


class CompetingOfferLogicQA(unittest.TestCase):
    def setUp(self):
        self.db=career_fixture()
        self.db.execute("ALTER TABLE world_clubs ADD COLUMN name TEXT")
        self.db.execute("UPDATE world_clubs SET name='Fixture club ' || club_id")
        self.db.execute("INSERT INTO world_clubs(club_id,name) VALUES(3,'Third club')")
        self.db.execute("""UPDATE world_career_offers
             SET player_id=101,buying_club_id=2,selling_club_id=1,
                 status='accepted_pending_contract',offered_fee=2000000,
                 agreement_date='2026-10-14',request_key='qa-bid-2'
             WHERE offer_id=1""")
        self.db.execute("""INSERT INTO world_career_offers
            (offer_id,career_id,request_key,player_id,buying_club_id,
             selling_club_id,status,offered_fee,agreement_date,economy_version)
            VALUES(35,'career-a','qa-bid-3',101,3,1,
                   'accepted_pending_contract',2100000,'2026-10-14','prototype-v1')""")
        self.db.execute("""CREATE TABLE world_career_agent_terms(
            offer_id INTEGER PRIMARY KEY,career_id TEXT,status TEXT,
            role_promise TEXT,proposed_wage_weekly INTEGER)""")
        self.db.execute("""INSERT INTO world_career_agent_terms VALUES
             (1,'career-a','accepted','regular_starter',20000)""")
        self.db.commit()
        self.interest=patch("world_careers.player_move_interest",
            return_value={"can_negotiate":True,"decision":"open_to_talks",
                          "reason":"Credible sporting opportunity"})
        self.prestige=patch("world_careers.current_career_prestige",
            side_effect=lambda conn,career_id,club_id:
                {"score":{1:64,2:70,3:88}[club_id]})
        self.interest.start()
        self.prestige.start()

    def tearDown(self):
        self.prestige.stop()
        self.interest.stop()
        self.db.close()

    def pick(self,offer_id=1):
        return competing_player_choice(self.db,career_id="career-a",offer_id=offer_id)

    def rival_accepts_personal_terms(self,wage=20000):
        self.db.execute("""INSERT INTO world_career_agent_terms VALUES
            (35,'career-a','accepted','regular_starter',?)""",(wage,))
        self.db.commit()

    def test_competing_fee_acceptance_does_not_equal_player_signature(self):
        self.assertEqual(self.pick()["decision"],"delayed")
        self.assertIn("weighing",self.pick()["reason"].lower())
        self.assertEqual(self.db.execute("""SELECT status FROM world_career_offers
            WHERE offer_id=1""").fetchone()[0],"accepted_pending_contract")

    def test_player_rejects_weak_offer_after_rival_personal_terms(self):
        self.rival_accepts_personal_terms()
        self.assertEqual(self.pick(1)["decision"],"refused")
        self.assertEqual(self.pick(35)["decision"],"ready")

    def test_very_close_clubs_make_player_delay(self):
        self.rival_accepts_personal_terms()
        with patch("world_careers.current_career_prestige",
                   side_effect=lambda db,career,club:{"score":70}):
            self.assertEqual(self.pick(1)["decision"],"delayed")
            self.assertEqual(self.pick(35)["decision"],"delayed")

    def test_rejected_competitor_does_not_block_signature(self):
        self.db.execute("UPDATE world_career_offers SET status='rejected' WHERE offer_id=35")
        self.db.commit()
        self.assertEqual(self.pick()["decision"],"ready")

    def test_manager_buying_does_not_bypass_competing_player_choice(self):
        # Buying-side signing must not bypass an accepted rival fee.
        # No real club is signed and all records live only in this fixture.
        from world_live_buying import act_on_buy_offer
        self.db.execute("""UPDATE world_career_offers
            SET player_id=102,buying_club_id=1,selling_club_id=2
            WHERE offer_id=1""")
        self.db.execute("""UPDATE world_career_offers
            SET player_id=102,selling_club_id=2 WHERE offer_id=35""")
        self.db.execute("""CREATE TABLE world_career_preseason_window_offers(
            window_id INTEGER,offer_id INTEGER)""")
        self.db.execute("""INSERT INTO world_career_preseason_window_offers
            VALUES(42,1)""")
        self.db.commit()
        with patch("world_live_buying.assert_window_allows_negotiation",
                   return_value={"window_id":42}),patch(
                   "world_live_buying.confirm_future_agreement") as confirm,patch(
                   "world_live_buying._message"):
            with self.assertRaisesRegex(ValueError,
                                        "competing|weighing|player|rival"):
                act_on_buy_offer(self.db,career_id="career-a",
                                 offer_id=1,action="sign")
            confirm.assert_not_called()
        self.assertEqual(self.db.execute("""SELECT status FROM
            world_career_offers WHERE offer_id=1""").fetchone()[0],
            "accepted_pending_contract")

    def test_core_final_agreement_cannot_duplicate_player_signature(self):
        # Independent of the user-facing incoming/outgoing transfer routes:
        # even a direct domain-service call must honour an existing signature.
        from world_careers import settle_future_deal
        self.db.execute("""UPDATE world_career_offers
            SET status='agreed_future' WHERE offer_id=35""")
        self.db.commit()
        with self.assertRaisesRegex(ValueError,"already signed|another club"):
            settle_future_deal(self.db,career_id="career-a",offer_id=1,
                               weekly_wage=20000,agreement_date="2026-10-14")
        self.assertEqual(self.db.execute("""SELECT status FROM
            world_career_offers WHERE offer_id=1""").fetchone()[0],
            "accepted_pending_contract")

    def test_rival_already_signed_vetoes_second_signature(self):
        self.db.execute("UPDATE world_career_offers SET status='agreed_future' WHERE offer_id=35")
        self.db.commit()
        outcome=self.pick()
        self.assertEqual(outcome["decision"],"refused")
        self.assertIn("already signed",outcome["reason"])

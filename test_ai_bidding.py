"""Pure and career-persistent regressions for differentiated competitive AI bids.

All club finances, ratings and seller preferences are explicit fictional test
fixtures. No real world transfer rumours or money is asserted.
"""
import json
import unittest
from unittest.mock import patch
from world_ai_bidding import (
    determine_offer,club_need,position_family,MAX_ROUNDS,AI_BID_VERSION)
from world_careers import (
    simulate_ai_bids,reject_incoming_offer,budget_remaining)
from test_career_selling import career_fixture

def bid(**extra):
    data=dict(career_id="isolated-sandbox",player_id=101,club_id=2,
        valuation=10_000_000,available_budget=40_000_000,
        need_score=65,eligible_clubs=3,active_rival_clubs=0,
        seller_assumptions=None,prior_fee=None,round_number=1)
    data.update(extra)
    return determine_offer(**data)

class WorldNeedAndSalaryTests(unittest.TestCase):
    def test_defender_need_includes_starting_four_and_depth(self):
        from world_ai_world import _need_for_family
        ratings=[80,79,78,76,73,70,67,65]
        defender=_need_for_family(family="DEF",overall=77,
                                  ratings=ratings)
        midfielder=_need_for_family(family="MID",overall=77,
                                    ratings=ratings)
        goalkeeper=_need_for_family(family="GK",overall=77,
                                    ratings=ratings)
        self.assertGreater(defender,midfielder)
        self.assertGreater(defender,goalkeeper)
        self.assertGreaterEqual(defender,57)

    def test_goalkeeper_share_needs_substantial_outfield_activity(self):
        from world_ai_world import _keeper_slot_open
        self.assertTrue(_keeper_slot_open(0,0))
        self.assertFalse(_keeper_slot_open(1,0))
        self.assertFalse(_keeper_slot_open(1,7))
        self.assertTrue(_keeper_slot_open(1,12))

    def test_ai_wage_initial_offers_are_below_agent_demand_for_most_clubs(self):
        from world_ai_world import _ai_wage_opening
        offers=[_ai_wage_opening(demand=20_000,career_id="qa-career",
                buyer=i,player_id=100+i) for i in range(100)]
        self.assertTrue(all(500<=value<=20_000 for value,_ in offers))
        self.assertGreater(sum(value<20_000 for value,_ in offers),65)
        self.assertTrue(any(value==20_000 for value,_ in offers))
        self.assertEqual(_ai_wage_opening(demand=20_000,career_id="qa-career",
                        buyer=27,player_id=127),offers[27])

class BidPriceTests(unittest.TestCase):
    def test_distinct_clubs_with_distinct_needs_offer_distinct_prices(self):
        offers=[bid(club_id=x,need_score=score) for x,score in
                ((2,95),(3,50),(4,25))]
        self.assertEqual(len({o["fee"] for o in offers}),3)
        self.assertTrue(all(o["model_version"]==AI_BID_VERSION for o in offers))
        self.assertTrue(all(o["fee"]<=40_000_000 for o in offers))

    def test_competing_clubs_raise_same_buyers_modelled_bid(self):
        alone=bid(eligible_clubs=1)
        demand=bid(eligible_clubs=5)
        self.assertGreater(demand["fee"],alone["fee"])
        self.assertEqual(alone["demand_premium_pct"],0)
        self.assertEqual(demand["demand_premium_pct"],14)

    def test_competitor_counts_capped_and_reproducible(self):
        self.assertEqual(bid(eligible_clubs=10),bid(eligible_clubs=10))
        self.assertEqual(bid(eligible_clubs=50)["demand_premium_pct"],14)

    def test_active_rival_adds_pressure_without_overwhelming_market(self):
        quiet=bid(active_rival_clubs=0)
        contested=bid(active_rival_clubs=5)
        self.assertGreater(contested["fee"],quiet["fee"])
        self.assertEqual(contested["active_rival_premium_pct"],3)

    def test_recorded_contract_and_listing_only_affect_price_if_known(self):
        standard=bid()
        listed=bid(seller_assumptions={
            "transfer_listed":1,"player_wants_exit":1,
            "contract_years":1,"squad_role":"fringe"})
        key=bid(seller_assumptions={
            "transfer_listed":0,"player_wants_exit":0,
            "contract_years":5,"squad_role":"key_player"})
        self.assertLess(listed["fee"],standard["fee"])
        self.assertGreater(key["fee"],standard["fee"])

    def test_follow_up_is_strictly_higher_but_two_attempts_only(self):
        first=bid()
        second=bid(round_number=2,prior_fee=first["fee"])
        third=bid(round_number=3,prior_fee=second["fee"])
        self.assertLess(first["fee"],second["fee"])
        self.assertLess(second["fee"],third["fee"])
        self.assertEqual(second["round"],2)
        with self.assertRaises(ValueError):
            bid(round_number=MAX_ROUNDS+1,prior_fee=third["fee"])

    def test_reject_bid_beyond_ceiling_not_automatically_accepted(self):
        no=bid(round_number=2,prior_fee=16_000_000)
        self.assertIsNone(no["fee"])
        self.assertIn("valuation ceiling",no["reason"])

    def test_no_silent_overspend(self):
        no=bid(available_budget=6_000_000)
        self.assertIsNone(no["fee"])
        self.assertIn("cannot afford",no["reason"])

    def test_relative_positional_need_is_evidence_based(self):
        self.assertEqual(position_family("DMF"),"MID")
        self.assertEqual(position_family("CB"),"DEF")
        self.assertIsNone(position_family(None))
        upgrade=club_need(overall=78,ratings=[70,68,66],position_group="DEF")
        fringe=club_need(overall=65,ratings=[80,79,78],position_group="DEF")
        self.assertGreater(upgrade["score"],fringe["score"])


class CareerAiBidHistoryTests(unittest.TestCase):
    def setUp(self):
        self.db=career_fixture()
        # Career-a includes seller 1 and buyer 2. These explicit fictional
        # extra clubs let us test three different bids against identical
        # modelled budgets without touching user saves.
        self.db.executemany("INSERT INTO world_clubs(club_id) VALUES(?)",
                            [(3,),(4,)])
        self.db.executemany("""INSERT INTO world_career_club_ledger
            (career_id,club_id,transfer_budget,weekly_wage_budget,
             committed_fees,committed_wages) VALUES('career-a',?,?,400000,0,0)""",
            [(3,45_000_000),(4,45_000_000)])
        self.db.commit()
        from world_career_selling import enable_career_selling
        enable_career_selling(self.db,career_id="career-a",
            source_note="Explicit fictional AI bidding scenario")
        self.clubs=[{"club_id":cid,"club_name":name,
                     "available_budget":40_000_000,
                     "need_score":need,"position_family":"DEF",
                     "squad_fit_floor":65,"need_reason":"Rated starter upgrade"}
                    for cid,name,need in ((2,"Away FC",85),(3,"Other FC",60),(4,"Rival FC",35))]
        self.ref=patch("world_careers._player_reference",
                       return_value=(10_000_000,75))
        self.interest=patch("world_careers.ai_interest",
                            return_value=self.clubs)
        self.ref.start()
        self.interest.start()

    def tearDown(self):
        self.interest.stop()
        self.ref.stop()
        self.db.close()

    def run_round(self):
        return simulate_ai_bids(self.db,career_id="career-a",
            player_id=101,max_bids=3,report=True)

    def offers(self):
        return self.db.execute("""SELECT offer_id,buying_club_id,
            request_key,offered_fee,status FROM world_career_offers
            WHERE career_id='career-a' AND player_id=101
            ORDER BY offer_id""").fetchall()

    def test_three_clubs_offer_different_fees_and_keep_audit_records(self):
        summary=self.run_round()
        self.assertEqual(summary["new"],3)
        self.assertEqual(summary["eligible"],3)
        self.assertGreater(summary["demand_premium_pct"],0)
        rows=self.offers()
        self.assertEqual(len(rows),3)
        self.assertEqual(len({r[3] for r in rows}),3)
        self.assertTrue(all(r[4]=="proposed" for r in rows))
        for row in rows:
            event=self.db.execute("""SELECT detail FROM world_career_offer_events
                WHERE offer_id=? AND event_type='ai_bid_pricing'""",(row[0],)).fetchone()
            self.assertIsNotNone(event)
            data=json.loads(event[0])
            self.assertEqual(data["fee"],row[3])
            self.assertEqual(data["eligible_competing_clubs"],3)
            self.assertEqual(data["round"],1)
            self.assertIn("buyer_need_score",data)
        self.assertEqual(self.db.execute("""SELECT club_id FROM world_career_registrations
            WHERE career_id='career-a' AND player_id=101""").fetchone()[0],1)

    def test_waiting_bids_never_raise_on_repeat_click(self):
        self.run_round()
        fees=self.offers()
        result=self.run_round()
        self.assertEqual(result["new"],0)
        self.assertEqual(len(self.offers()),3)
        self.assertEqual(self.offers(),fees)
        self.assertIn("already",result["reason"])

    def test_human_rejection_allows_two_higher_rebids_not_infinite(self):
        self.run_round()
        first=self.offers()[0]
        reject_incoming_offer(self.db,career_id="career-a",offer_id=first[0])
        self.assertEqual(self.db.execute(
            "SELECT status FROM world_career_offers WHERE offer_id=?",
            (first[0],)).fetchone()[0],"rejected")
        second_round=self.run_round()
        self.assertEqual(second_round["increased"],1)
        new=[r for r in self.offers() if r[1]==first[1]]
        self.assertEqual(len(new),2)
        self.assertGreater(new[1][3],new[0][3])
        self.assertIn("-r2",new[1][2])
        audit=json.loads(self.db.execute("""SELECT detail FROM world_career_offer_events
             WHERE offer_id=? AND event_type='ai_bid_pricing'""",
             (new[1][0],)).fetchone()[0])
        self.assertEqual(audit["prior_offer_id"],new[0][0])
        reject_incoming_offer(self.db,career_id="career-a",offer_id=new[1][0])
        third_round=self.run_round()
        self.assertEqual(third_round["increased"],1)
        group=[r for r in self.offers() if r[1]==first[1]]
        self.assertEqual(len(group),3)
        self.assertGreater(group[2][3],group[1][3])
        self.assertIn("-r3",group[2][2])
        reject_incoming_offer(self.db,career_id="career-a",offer_id=group[2][0])
        finished=self.run_round()
        self.assertEqual(finished["increased"],0)
        self.assertEqual(len([r for r in self.offers() if r[1]==first[1]]),3)
        self.assertTrue(any("maximum" in failure for failure in finished["failures"]))
        self.assertEqual(self.db.execute("""SELECT club_id FROM world_career_registrations
            WHERE career_id='career-a' AND player_id=101""").fetchone()[0],1)

    def test_ai_never_rebids_after_firm_manager_stance(self):
        from world_career_selling import record_seller_assumptions
        record_seller_assumptions(self.db,career_id="career-a",player_id=101,
            market_value=10_000_000,contract_years=4,
            squad_role="key_player",transfer_listed=False,
            player_wants_exit=False,financial_state="stable",
            replacement="difficult",seller_stance="retain",
            board_enabled=False,
            source_note="Firm no-sale fictional test scenario")
        first=self.run_round()
        self.assertEqual(first["new"],3)
        self.assertTrue(all(r[4]=="rejected" for r in self.offers()))
        repeated=self.run_round()
        self.assertEqual(repeated["new"],0)
        self.assertIn("not-for-sale",repeated["reason"])
        self.assertEqual(len(self.offers()),3)

    def test_buyer_budget_reservations_and_no_cross_career_offers(self):
        first=self.run_round()
        self.assertEqual(first["new"],3)
        for row in self.offers():
            self.assertGreaterEqual(budget_remaining(self.db,"career-a",row[1]),0)
        self.assertEqual(self.db.execute("""SELECT COUNT(*) FROM world_career_offers
            WHERE career_id='career-b' AND player_id=101""").fetchone()[0],0)

if __name__=="__main__":
    unittest.main()

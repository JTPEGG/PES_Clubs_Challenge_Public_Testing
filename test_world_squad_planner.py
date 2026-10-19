"""Regression checks for position-aware projected transfers."""
import sqlite3
import unittest

from world_squad_planner import (
    lane_of, projected_squads, recruitment_fit, departure_guard,
    sale_profile, effective_cover, assign_available_players,
)


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.db.executescript("""
            CREATE TABLE world_career_registrations(career_id TEXT,player_id INTEGER,club_id INTEGER);
            CREATE TABLE world_dataset_ratings(dataset_id TEXT,player_id INTEGER,overall INTEGER);
            CREATE TABLE world_players(player_id INTEGER,primary_position TEXT);
            CREATE TABLE world_career_offers(career_id TEXT,player_id INTEGER,
                selling_club_id INTEGER,buying_club_id INTEGER,status TEXT,offer_id INTEGER);
        """)
        self.next_id=1

    def tearDown(self):
        self.db.close()

    def player(self,club,pos,rating):
        pid=self.next_id
        self.next_id+=1
        self.db.execute("INSERT INTO world_players VALUES(?,?)",(pid,pos))
        self.db.execute("INSERT INTO world_career_registrations VALUES('test',?,?)",(pid,club))
        self.db.execute("INSERT INTO world_dataset_ratings VALUES('2026',?,?)",(pid,rating))
        return pid

    def squads(self):
        return projected_squads(self.db,career_id="test",dataset="2026")

    def test_centres_are_not_interchangeable_with_full_backs(self):
        self.assertEqual(lane_of("CB"),"CB")
        self.assertEqual(lane_of("LB"),"LB")
        self.assertEqual(lane_of("RB"),"RB")
        self.assertEqual(lane_of("RW"),"RW")
        self.assertEqual(lane_of("LW"),"LW")
        self.assertEqual(lane_of("RWF"),"RW")

    def test_elite_club_does_not_buy_ordinary_backup_as_upgrade(self):
        # Three strong starters and a solid XI; the third-best forward
        # is not evidence that an 83-rated player improves a 91-rated side.
        for pos,ratings in (("CF",[93,91]),("LWF",[92,90,88]),
                            ("CB",[93,91,89,86]),("CMF",[92,90,87]),
                            ("GK",[94,82]),("LB",[90,85,81])):
            for r in ratings:self.player(1,pos,r)
        fit=recruitment_fit(self.squads(),buyer=1,position="CF",overall=83)
        self.assertFalse(fit["eligible"])

    def test_cannot_sell_last_right_back_just_because_left_backs_exist(self):
        right=self.player(2,"RB",80)
        self.player(2,"LB",92)
        self.player(2,"LB",88)
        rejected=departure_guard(self.squads(),seller=2,player_id=right,
            position="RB",overall=80)
        self.assertFalse(rejected["allowed"])
        # A new right-back is an upgrade despite strong unrelated LBs.
        fit=recruitment_fit(self.squads(),buyer=2,
                            position="RB",overall=85)
        self.assertTrue(fit["eligible"])

    def test_left_and_right_wingers_keep_separate_coverage(self):
        left=self.player(2,"LW",79)
        self.player(2,"RW",91)
        self.player(2,"RW",87)
        rejected=departure_guard(self.squads(),seller=2,player_id=left,
            position="LW",overall=79)
        self.assertFalse(rejected["allowed"])

    def test_selling_only_attacking_midfielder_is_a_safe_rejection(self):
        only_am=self.player(2,"CAM",82)
        decision=departure_guard(self.squads(),seller=2,
            player_id=only_am,position="CAM",overall=82)
        self.assertFalse(decision["allowed"])
        self.assertIn("no player",decision["reason"])

    def test_sensible_starter_upgrades_remain_possible(self):
        for pos,ratings in (("CF",[77,70]),("CB",[78,76,73]),
                            ("CMF",[77,75,72]),("GK",[78,72]),
                            ("LB",[76,73]),("LWF",[77,74])):
            for r in ratings:self.player(1,pos,r)
        fit=recruitment_fit(self.squads(),buyer=1,position="CF",overall=85)
        self.assertTrue(fit["eligible"])
        self.assertGreaterEqual(fit["score"],60)

    def test_excess_centre_back_sales_blocked(self):
        pids=[self.player(2,"CB",r) for r in (90,88,80,74)]
        plan=self.squads()
        self.assertFalse(departure_guard(plan,seller=2,player_id=pids[0],
                        position="CB",overall=90)["allowed"])
        self.assertTrue(departure_guard(plan,seller=2,player_id=pids[-1],
                        position="CB",overall=74)["allowed"])
        # A signed sale is included in the projected roster, leaving 3 CBs.
        self.db.execute("""INSERT INTO world_career_offers
            VALUES('test',?,?,?,'agreed_future',1)""",(pids[-1],2,3))
        plan=self.squads()
        self.assertFalse(departure_guard(plan,seller=2,player_id=pids[1],
                        position="CB",overall=88)["allowed"])

    def test_surplus_sale_needs_no_replacement(self):
        backups=[self.player(2,"CB",v) for v in (87,82,78,76,73)]
        case=sale_profile(self.squads(),seller=2,
            player_id=backups[-1],position="CB",overall=73)
        self.assertTrue(case["valid"])
        self.assertTrue(case["surplus_sale"])
        self.assertFalse(case["requires_recruitment"])

    def test_sell_first_key_starter_is_scored_as_follow_up_not_a_veto(self):
        sole=self.player(2,"RB",91)
        case=sale_profile(self.squads(),seller=2,
            player_id=sole,position="RB",overall=91)
        self.assertTrue(case["valid"])
        self.assertEqual(case["replacement_priority"],"urgent")
        self.assertTrue(case["requires_recruitment"])
        # Normal seller/agent/board approval is deliberately assessed later.
        self.assertFalse(departure_guard(self.squads(),seller=2,
                         player_id=sole,position="RB",overall=91)["allowed"])

    def test_sold_starter_creates_buyer_need_without_advance_replacement(self):
        starter=self.player(2,"LW",84)
        for pos,v in (("GK",83),("CB",83),("CM",82),("ST",81)):
            for _ in range(3):self.player(2,pos,v)
        self.db.execute("""INSERT INTO world_career_offers
            VALUES('test',?,?,?,'agreed_future',5)""",(starter,2,3))
        plan=self.squads()
        self.assertNotIn("LW",plan[2])
        new=recruitment_fit(plan,buyer=2,position="LW",overall=85)
        self.assertTrue(new["eligible"])
        self.assertTrue(new["depth_shortage"])

    def _test_alternative_position_source(self, player_id):
        self.db.execute("""CREATE TABLE IF NOT EXISTS
            world_player_source_refs(
                player_id INTEGER, source_name TEXT,external_id TEXT)""")
        self.db.execute("""INSERT INTO world_player_source_refs
            VALUES(?,'EAFC27','231936')""",(player_id,))
        self.db.execute("""UPDATE world_dataset_ratings
            SET dataset_id='england-2026-27-fc27'""")
        return projected_squads(self.db,career_id="test",
            dataset="england-2026-27-fc27")

    def test_ben_white_verified_alternative_cb_without_double_counting(self):
        for rating in (89,88,84,78):
            self.player(2,"CB",rating)
        white=self.player(2,"RB",81)
        self.player(2,"RB",84)  # Timber can still start at right-back
        squad=self._test_alternative_position_source(white)
        self.assertEqual(len(squad[2]["CB"]),4)
        self.assertEqual(len(effective_cover(squad,2,"CB")),5)
        self.assertEqual(len(effective_cover(squad,2,"RB")),2)
        self.assertEqual(len({x[0] for x in effective_cover(squad,2,"CB")}),5)
        # Selling Timber leaves no other natural RB starter.
        timber=next(x[0] for x in squad[2]["RB"] if x[0]!=white)
        self.assertEqual(len(effective_cover(squad,2,"CB",
                                           exclude_player=timber)),4)

    def test_many_alternative_positions_are_stored_as_separate_rows(self):
        flexible=self.player(2,"RB",82)
        starter_rb=self.player(2,"RB",79)
        self.db.execute("""CREATE TABLE world_player_alternative_positions(
            dataset_id TEXT,player_id INTEGER,position TEXT,source_note TEXT,
            PRIMARY KEY(dataset_id,player_id,position))""")
        for alt in ("CB","CDM","LB"):
            self.db.execute("""INSERT INTO world_player_alternative_positions
                VALUES('2026',?,?,?)""",(flexible,alt,"test-evidenced"))
        squads=self.squads()
        self.assertEqual(set(squads.alternative_positions[flexible]),
                         {"CB","DM","LB"})
        for lane in ("CB","DM","LB"):
            self.assertEqual([p[0] for p in effective_cover(squads,2,lane)],
                             [flexible])
        # Multi-position does not mean three additional footballers.
        assignment=assign_available_players(squads,2,
            {"RB":1,"CB":1,"DM":1,"LB":1})
        self.assertEqual(assignment["filled"],2)
        self.assertEqual(assignment["unfilled"],2)
        self.assertEqual(len({x["player_id"] for x in
                              assignment["assignments"]}),2)
        self.assertIn(starter_rb,{x["player_id"] for x in
                                  assignment["assignments"]})

    def test_alternative_position_eligibility_is_not_inferred(self):
        p=self.player(2,"RB",84)
        self.player(2,"RB",78)
        self.assertEqual(effective_cover(self.squads(),2,"CB"),[])
        assigned=assign_available_players(self.squads(),2,
            {"RB":1,"CB":1})
        self.assertEqual(assigned["unfilled"],1)

    def test_elite_arsenal_rather_sells_mosquera_than_konsa(self):
        self.player(2,"CB",89)  # Gabriel
        self.player(2,"CB",88)  # Saliba
        konsa=self.player(2,"CB",84)
        mosquera=self.player(2,"CB",78)
        white=self.player(2,"RB",81)
        self.player(2,"RB",84)
        for pos,rating in (
            ("LB",84),("LB",82),("GK",88),("CM",86),("ST",86)):
            self.player(2,pos,rating)
        squad=self._test_alternative_position_source(white)
        konsa_case=sale_profile(squad,seller=2,player_id=konsa,
                                position="CB",overall=84)
        mosquera_case=sale_profile(squad,seller=2,player_id=mosquera,
                                  position="CB",overall=78)
        self.assertTrue(konsa_case["protected_rotation"])
        self.assertGreater(konsa_case["backup_quality_drop"],0)
        self.assertFalse(mosquera_case["protected_rotation"])
        self.assertTrue(mosquera_case["surplus_sale"])
        self.assertGreater(konsa_case["sporting_risk"],
                           mosquera_case["sporting_risk"])

    def test_two_quality_cb_sales_increase_rotation_risk_sequentially(self):
        self.player(2,"CB",87)
        self.player(2,"CB",85)
        gvardiol=self.player(2,"CB",85)
        khusanov=self.player(2,"CB",82)
        for rating in (76,73,69):
            self.player(2,"CB",rating)
        for pos,rating in (("GK",89),("LB",84),("RB",83),
                           ("CM",85),("RW",86)):
            self.player(2,pos,rating)
        before=self.squads()
        first=sale_profile(before,seller=2,player_id=gvardiol,
                           position="CB",overall=85)
        self.db.execute("""INSERT INTO world_career_offers
            VALUES('test',?,?,?,'agreed_future',9)""",
            (gvardiol,2,3))
        after=self.squads()
        second=sale_profile(after,seller=2,player_id=khusanov,
                            position="CB",overall=82)
        self.assertTrue(first["protected_rotation"])
        self.assertTrue(second["protected_rotation"])
        self.assertLess(len(effective_cover(after,2,"CB")),
                        len(effective_cover(before,2,"CB")))

    def test_signed_arrival_revises_both_clubs_immediately(self):
        p=self.player(2,"CB",88)
        for rating in (87,81,78):self.player(1,"CB",rating)
        before=self.squads()
        self.assertNotIn(p,[x[0] for x in before[1]["CB"]])
        self.db.execute("""INSERT INTO world_career_offers
            VALUES('test',?,?,?,'agreed_future',1)""",(p,2,1))
        after=self.squads()
        self.assertIn(p,[x[0] for x in after[1]["CB"]])
        self.assertNotIn(p,[x[0] for x in after[2].get("CB",[])])

    def test_duplicate_signed_player_is_not_silently_assigned(self):
        p=self.player(2,"CB",80)
        for n in (1,2):
            self.db.execute("""INSERT INTO world_career_offers
                VALUES('test',?,?,?,'agreed_future',?)""",(p,2,3+n,n))
        with self.assertRaisesRegex(ValueError,"Conflicting"):
            self.squads()


if __name__=="__main__":
    unittest.main()

"""Player choice v2: a 90 OVR Arsenal regular is NOT a £15k Forest target.

All circumstances in this file are *fictional test inputs*. The actual
world data does not imply a real player salary, squad role or renewal status.
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from flask import Flask

from world_player_decisions import (
    DECISION_V2_VERSION,evaluate_player_choice_v2,agent_minimum_wage_v2)
from world_v2 import initialize_world
from world_explorer import initialize_catalog
from world_reputation_v2 import initialize_pyramid
from world_careers import (
    initialize_career_engine,start_sandbox,player_move_interest,
    set_player_circumstances,player_circumstances,offer_europe_context,
    agent_terms,negotiate_agent,
    career_player_policy,prestige_snapshot)
from world_career_play import create_play_blueprint
from world_player_decisions_ui import create_player_decisions_blueprint


class SalaryAndStatusTests(unittest.TestCase):
    def base_case(self,**changes):
        payload=dict(
            buyer_tier=1,seller_tier=1,buyer_score=80,seller_score=98,
            buyer_prestige=72,seller_prestige=94,
            overall=90,age=27,current_wage=150000,
            current_role="key_player",transfer_listed=False,
            renewal_status="renewal_offered",
            offered_wage=15000,role_promise="unspecified")
        payload.update(changes)
        return evaluate_player_choice_v2(**payload)

    def test_01_arsenal_to_forest_15k_is_immediate_refusal(self):
        case=self.base_case()
        self.assertEqual(case["decision"],"uninterested")
        self.assertFalse(case["can_negotiate"])
        self.assertEqual(case["policy_version"],DECISION_V2_VERSION)
        self.assertIn("Established elite first-team",case["reason"])
        self.assertIsNone(agent_minimum_wage_v2(choice=case))

    def test_02_lots_of_money_without_exit_cause_does_not_beat_contract(self):
        case=self.base_case(offered_wage=500000,role_promise="key_player")
        self.assertEqual(case["decision"],"uninterested")
        self.assertFalse(case["can_negotiate"])

    def test_03_not_renewed_or_listed_with_excellent_money_can_trigger_talks(self):
        for values in (dict(renewal_status="not_offered"),
                       dict(transfer_listed=True)):
            with self.subTest(values=values):
                low=self.base_case(**values)
                self.assertEqual(low["decision"],"uninterested")
                high=self.base_case(**values,offered_wage=280000,
                                    role_promise="key_player")
                self.assertEqual(high["decision"],"open_to_talks")
                self.assertTrue(high["can_negotiate"])
                self.assertGreaterEqual(high["minimum_wage"],225000)
                self.assertGreater(high["minimum_wage"],150000)
                self.assertEqual(agent_minimum_wage_v2(choice=high),
                                 high["minimum_wage"])

    def test_04_high_salary_without_role_gives_counter_not_agreement(self):
        pending=self.base_case(renewal_status="not_offered",
                               offered_wage=280000,role_promise="unspecified")
        self.assertEqual(pending["decision"],"needs_assurances")
        self.assertEqual(pending["required_role"],"key_player")

    def test_05_missing_real_circumstances_cannot_default_to_available(self):
        for changed in (dict(current_wage=None),
                        dict(current_role="unknown"),
                        dict(transfer_listed=None),
                        dict(renewal_status="unknown")):
            with self.subTest(changed=changed):
                c=self.base_case(**changed)
                self.assertEqual(c["decision"],"review")
                self.assertFalse(c["can_negotiate"])

    def test_06_nonelite_young_fringe_can_trade_stature_for_playtime(self):
        case=self.base_case(
            age=20,overall=74,current_role="fringe",
            current_wage=12000,offered_wage=18000,
            buyer_score=80,seller_score=86,
            buyer_prestige=60,seller_prestige=80)
        self.assertEqual(case["decision"],"open_to_talks")
        self.assertTrue(case["can_negotiate"])

    def test_07_current_wage_cut_blocks_regular_even_if_not_elite(self):
        case=self.base_case(age=30,overall=80,current_role="regular_starter",
                            current_wage=100000,offered_wage=15000)
        self.assertEqual(case["decision"],"uninterested")
        self.assertIn("far below",case["reason"])

    def test_075_champions_league_regular_refuses_worse_football(self):
        # Equal sporting score/prestige isolates the European effect.
        case=self.base_case(buyer_score=89,seller_score=89,
            buyer_prestige=82,seller_prestige=82,
            buyer_europe="none",seller_europe="champions_league",
            offered_wage=500_000,role_promise="key_player")
        self.assertEqual(case["decision"],"uninterested")
        self.assertFalse(case["can_negotiate"])
        self.assertIn("Champions League",case["reason"])
        self.assertEqual(case["european_gap"],-5)

    def test_076_european_loss_requires_financial_and_career_reason(self):
        low=self.base_case(transfer_listed=True,renewal_status="not_offered",
            buyer_europe="none",seller_europe="champions_league",
            offered_wage=15000,role_promise="key_player")
        self.assertEqual(low["decision"],"uninterested")
        high=self.base_case(transfer_listed=True,renewal_status="not_offered",
            buyer_europe="none",seller_europe="champions_league",
            offered_wage=360000,role_promise="key_player")
        self.assertEqual(high["decision"],"open_to_talks")
        self.assertGreaterEqual(high["minimum_wage"],262500)
        self.assertEqual(high["seller_europe"],"champions_league")
        self.assertEqual(high["buyer_europe"],"none")

    def test_077_unknown_europe_is_not_assumed_from_prestige(self):
        missing=self.base_case(buyer_europe="unknown")
        self.assertEqual(missing["decision"],"review")
        self.assertFalse(missing["can_negotiate"])
        self.assertIn("Continental",missing["reason"])
        with self.assertRaisesRegex(ValueError,"European participation"):
            self.base_case(seller_europe="invented_cup")

    def test_078_key_player_promise_does_not_waive_wage_counter(self):
        # Illustrative salary levels matching the user's £62.5k / £87.5k
        # observations; these are NOT actual player wages.
        for wage,expected in ((50_000,62_500),(70_000,87_500)):
            with self.subTest(current_salary=wage):
                result=self.base_case(
                    age=27,overall=80,
                    buyer_score=86,seller_score=95,
                    buyer_prestige=90,seller_prestige=100,
                    current_wage=wage,offered_wage=wage,
                    current_role="key_player",role_promise="key_player")
                self.assertEqual(result["decision"],"needs_assurances")
                self.assertEqual(result["required_role"],"regular_starter")
                self.assertEqual(result["role_satisfied"],True)
                self.assertEqual(result["issue"],"wage")
                self.assertEqual(result["minimum_wage"],expected)
                self.assertEqual(result["wage_shortfall"],expected-wage)
                self.assertIn("already meets",result["reason"])
                self.assertIn(f"£{expected:,}",result["reason"])
                adjusted=self.base_case(
                    age=27,overall=80,
                    buyer_score=86,seller_score=95,
                    buyer_prestige=90,seller_prestige=100,
                    current_wage=wage,offered_wage=expected,
                    current_role="key_player",role_promise="key_player")
                self.assertEqual(adjusted["decision"],"open_to_talks")
                self.assertTrue(adjusted["role_satisfied"])

    def test_079_regular_starter_is_a_real_second_tier(self):
        from world_player_decisions import (
            ROLES,SELECTABLE_ROLES,canonical_role,role_satisfies,ROLE_LABELS)
        self.assertEqual(SELECTABLE_ROLES,(
            "unspecified","key_player","regular_starter","rotation","fringe"))
        self.assertEqual(canonical_role("important"),"regular_starter")
        self.assertTrue(role_satisfies("key_player","regular_starter"))
        self.assertTrue(role_satisfies("regular_starter","important"))
        self.assertFalse(role_satisfies("regular_starter","key_player"))
        self.assertFalse(role_satisfies("rotation","regular_starter"))
        self.assertEqual(ROLE_LABELS["important"],"Regular Starter")
        self.assertEqual(ROLE_LABELS["regular_starter"],"Regular Starter")
        self.assertIn("important",ROLES)  # accepted only for compatibility
        alias=self.base_case(
            current_role="important",offered_wage=100000,
            overall=77,age=29,
            buyer_score=90,seller_score=90,
            buyer_prestige=90,seller_prestige=90,
            role_promise="important")
        self.assertEqual(alias["current_role"],"regular_starter")

    def test_08_bad_inputs_rejected(self):
        with self.assertRaises(ValueError):
            self.base_case(current_wage=-1)
        with self.assertRaises(ValueError):
            self.base_case(transfer_listed="yes")
        with self.assertRaises(ValueError):
            self.base_case(renewal_status="invented")
        with self.assertRaises(ValueError):
            self.base_case(current_role="starboy")


class CareerPlayerContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.temp.name)/"career-context.sqlite"
        cls.db=sqlite3.connect(cls.path)
        cls.db.row_factory=sqlite3.Row
        cls.db.execute("PRAGMA foreign_keys=ON")
        initialize_world(cls.db)
        initialize_catalog(cls.db)
        initialize_pyramid(cls.db)
        initialize_career_engine(cls.db)
        cls.ids=dict(cls.db.execute("SELECT name,club_id FROM world_clubs"))
        start_sandbox(cls.db,career_id="context-v2",
                      dataset_id="england-2026-27-fc27",
                      title="Player circumstances test",manager_club_id=cls.ids["Nottingham Forest"],
                      pes_lock_date="2026-08-01",next_summer_date="2027-07-01",
                      player_decision_version=DECISION_V2_VERSION)
        cls.player=cls.db.execute("""SELECT r.player_id FROM world_dataset_rosters r
            JOIN world_players p ON p.player_id=r.player_id
            JOIN world_dataset_ratings x
              ON x.dataset_id=r.dataset_id AND x.player_id=r.player_id
            WHERE r.dataset_id='england-2026-27-fc27' AND r.club_id=?
              AND x.overall BETWEEN 75 AND 85
              AND p.birth_date IS NOT NULL
            ORDER BY x.overall LIMIT 1""",(cls.ids["Arsenal"],)).fetchone()[0]
        cls.offer=cls.db.execute("""INSERT INTO world_career_offers
            (career_id,request_key,player_id,buying_club_id,selling_club_id,
             offered_fee,status,agreement_date,economy_version)
            VALUES('context-v2','player-context-1',?,?,?,1000000,
                   'accepted_pending_contract','2027-01-05','prototype-v1')""",
            (cls.player,cls.ids["Nottingham Forest"],cls.ids["Arsenal"])).lastrowid
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        cls.temp.cleanup()

    def test_09_unknown_salary_and_role_block_player_assessment(self):
        self.assertEqual(career_player_policy(self.db,"context-v2")["version"],
                         DECISION_V2_VERSION)
        self.assertEqual(self.db.execute("""SELECT COUNT(*)
            FROM world_career_prestige_snapshots WHERE career_id='context-v2'""").fetchone()[0],92)
        self.assertIsNone(player_circumstances(self.db,"context-v2",self.player))
        result=player_move_interest(self.db,career_id="context-v2",offer_id=self.offer)
        self.assertEqual(result["decision"],"review")
        self.assertFalse(result["can_negotiate"])
        with self.assertRaisesRegex(ValueError,"not currently willing"):
            negotiate_agent(self.db,career_id="context-v2",offer_id=self.offer,
                weekly_wage=100000,contract_years=3,
                agreement_date="2027-01-05",role_promise="key_player")
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM world_career_agent_terms").fetchone()[0],0)

    def test_10_manager_explicit_input_is_isolated_and_audited(self):
        set_player_circumstances(self.db,career_id="context-v2",offer_id=self.offer,
            current_wage_weekly=100000,current_role="key_player",
            transfer_listed=False,renewal_status="renewal_offered")
        ctx=player_circumstances(self.db,"context-v2",self.player)
        self.assertEqual(ctx["current_wage_weekly"],100000)
        self.assertEqual(ctx["source_kind"],"user_sandbox_assumption")
        self.assertFalse(ctx["transfer_listed"])
        self.assertEqual(offer_europe_context(
            self.db,"context-v2",self.offer)["buyer_europe"],"unknown")
        self.assertEqual(player_move_interest(
            self.db,career_id="context-v2",offer_id=self.offer)["decision"],"review")
        self.assertEqual(self.db.execute("""SELECT COUNT(*) FROM world_career_offer_events
            WHERE offer_id=? AND event_type='player_circumstances'""",
            (self.offer,)).fetchone()[0],1)
        with self.assertRaisesRegex(ValueError,"Only your pending offer"):
            ai=self.db.execute("""INSERT INTO world_career_offers
                (career_id,request_key,player_id,buying_club_id,selling_club_id,
                 offered_fee,status,agreement_date,economy_version)
                 VALUES('context-v2','ai-context',?,?,?,200000,
                        'accepted_pending_contract','2027-01-05','prototype-v1')""",
                 (self.player,self.ids["Chelsea"],self.ids["Arsenal"])).lastrowid
            self.db.commit()
            set_player_circumstances(self.db,career_id="context-v2",offer_id=ai,
                current_wage_weekly=5000,current_role="rotation",
                transfer_listed=True,renewal_status="not_offered")

    def test_11_explicit_exit_allows_wage_and_role_talks_but_no_registration(self):
        set_player_circumstances(self.db,career_id="context-v2",offer_id=self.offer,
            current_wage_weekly=20000,current_role="regular_starter",
            transfer_listed=True,renewal_status="not_offered",
            buyer_europe="none",seller_europe="champions_league")
        preview=player_move_interest(self.db,career_id="context-v2",offer_id=self.offer)
        self.assertEqual(preview["decision"],"needs_assurances")
        self.assertEqual(preview["european_gap"],-5)
        self.assertEqual(offer_europe_context(
            self.db,"context-v2",self.offer)["seller_europe"],"champions_league")
        self.assertIsNotNone(preview["minimum_wage"])
        chosen_role=preview["required_role"]
        assert chosen_role in ("none","regular_starter","key_player")
        proposed_role=("key_player" if chosen_role=="key_player" else "regular_starter")
        contract=agent_terms(self.db,career_id="context-v2",offer_id=self.offer)
        offered=max(contract["demanded_wage_weekly"]+2000,100000)
        outcome=negotiate_agent(self.db,career_id="context-v2",offer_id=self.offer,
            weekly_wage=offered,contract_years=3,
            agreement_date="2027-01-05",role_promise=proposed_role)
        self.assertEqual(outcome,"accepted")
        self.assertEqual(self.db.execute("""SELECT club_id FROM world_career_registrations
            WHERE career_id='context-v2' AND player_id=?""",(self.player,)).fetchone()[0],
                         self.ids["Arsenal"])
        with self.assertRaisesRegex(ValueError,"locked"):
            set_player_circumstances(self.db,career_id="context-v2",offer_id=self.offer,
                current_wage_weekly=1,current_role="fringe",
                transfer_listed=True,renewal_status="not_offered")

    def test_12_default_lab_matches_specific_user_scenario(self):
        app=Flask(__name__)
        app.register_blueprint(create_player_decisions_blueprint(self.path))
        client=app.test_client()
        page=client.get("/world/player-decisions")
        self.assertEqual(page.status_code,200)
        self.assertIn(b"Not Interested",page.data)
        self.assertIn(b"Arsenal",page.data)
        self.assertIn(b"Nottingham Forest",page.data)
        self.assertIn(b"150,000",page.data)
        self.assertIn(b"15,000",page.data)
        self.assertIn(b"Current weekly wage",page.data)
        self.assertIn(b"Transfer-listed",page.data)
        self.assertIn(b"Regular Starter",page.data)
        self.assertIn(b"Key Player",page.data)
        self.assertNotIn(b"Important first team",page.data)
        self.assertNotIn(b"Key player / regular starter",page.data)
        self.assertIn(b"renewal",page.data.lower())
        self.assertIn(b"European football at current club",page.data)
        self.assertIn(b"Champions League",page.data)
        self.assertIn(b"European football at interested club",page.data)
        unknown=client.get("/world/player-decisions?buyer_europe=unknown")
        self.assertEqual(unknown.status_code,200)
        self.assertIn(b"Continental participation",unknown.data)
        self.assertEqual(client.post("/world/player-decisions").status_code,405)
        self.assertEqual(client.get("/world/player-decisions?current_wage=-10").status_code,400)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM world_transfers").fetchone()[0],0)


class RoleMigrationTests(unittest.TestCase):
    def test_13_old_important_context_migrates_without_losing_contract_facts(self):
        with tempfile.TemporaryDirectory() as folder:
            db=sqlite3.connect(str(Path(folder)/"role-migrate.sqlite"))
            db.execute("PRAGMA foreign_keys=ON")
            initialize_world(db)
            initialize_catalog(db)
            initialize_career_engine(db)
            forest=db.execute(
                "SELECT club_id FROM world_clubs WHERE name='Nottingham Forest'"
            ).fetchone()[0]
            player=db.execute("SELECT player_id FROM world_players LIMIT 1").fetchone()[0]
            start_sandbox(db,career_id="role-migration-example",
                dataset_id="england-2026-27-fc27",
                title="Role migration fixture",manager_club_id=forest,
                pes_lock_date="2026-08-01",next_summer_date="2027-07-01")
            db.execute("DROP TABLE world_career_player_circumstances")
            db.execute("""CREATE TABLE world_career_player_circumstances(
                career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
                player_id INTEGER NOT NULL REFERENCES world_players(player_id),
                current_wage_weekly INTEGER NOT NULL CHECK(current_wage_weekly BETWEEN 0 AND 1000000),
                current_role TEXT NOT NULL CHECK(current_role IN
                    ('key_player','important','rotation','fringe')),
                transfer_listed INTEGER NOT NULL CHECK(transfer_listed IN (0,1)),
                renewal_status TEXT NOT NULL CHECK(renewal_status IN
                    ('unknown','renewal_offered','not_offered')),
                source_kind TEXT NOT NULL DEFAULT 'user_sandbox_assumption',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(career_id,player_id)
            )""")
            db.execute("""INSERT INTO world_career_player_circumstances
                (career_id,player_id,current_wage_weekly,current_role,transfer_listed,
                 renewal_status,source_kind,updated_at)
                VALUES (?,?,?,'important',0,'renewal_offered',
                        'user_sandbox_assumption','2026-10-14 11:45:00')""",
                ("role-migration-example",player,62500))
            db.commit()
            initialize_career_engine(db)
            info=player_circumstances(db,"role-migration-example",player)
            self.assertEqual(info["current_role"],"regular_starter")
            self.assertEqual(info["current_wage_weekly"],62500)
            self.assertEqual(info["renewal_status"],"renewal_offered")
            self.assertEqual(info["updated_at"],"2026-10-14 11:45:00")
            saved=db.execute("""SELECT current_role,source_kind FROM
                world_career_player_circumstances WHERE career_id=? AND player_id=?""",
                ("role-migration-example",player)).fetchone()
            self.assertEqual(saved,("regular_starter","user_sandbox_assumption"))
            # Second init is a no-op; new tier now passes SQLite CHECK.
            initialize_career_engine(db)
            db.execute("""UPDATE world_career_player_circumstances
                SET current_role='key_player' WHERE career_id=? AND player_id=?""",
                ("role-migration-example",player))
            db.commit()
            self.assertEqual(player_circumstances(
                db,"role-migration-example",player)["current_role"],"key_player")
            db.close()


if __name__=="__main__":
    unittest.main()

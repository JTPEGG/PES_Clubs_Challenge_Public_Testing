"""Security and smoke tests for the playable development transfer desk."""
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from flask import Flask
from world_career_play import create_play_blueprint


class PlayDeskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.db=Path(cls.tmp.name)/"play.db"
        cls.app=Flask(__name__)
        cls.app.register_blueprint(create_play_blueprint(cls.db))
        cls.client=cls.app.test_client()
        cls.client.environ_base["wsgi.url_scheme"]="https"
        cls.settings=patch.dict(os.environ,{
            "WORLD_MARKET_ACCESS_KEY":"test-local-access",
            "WORLD_MARKET_COOKIE_SECRET":"local-cookie-secret-do-not-use-on-render",
        })
        cls.settings.start()

    @classmethod
    def tearDownClass(cls):
        cls.settings.stop()
        cls.tmp.cleanup()

    def test_00_offer_method_routing(self):
        rules=[r for r in self.app.url_map.iter_rules()
               if r.rule=="/world/play/career/<career_id>/offer"]
        self.assertEqual(len(rules),1)
        self.assertIn("POST",rules[0].methods)
        self.assertIn("GET",rules[0].methods)
        response=self.client.get("/world/play/career/no-such-career/offer")
        self.assertEqual(response.status_code,302)
        self.assertIn("Send+offer+form",response.location)
        # Without login, POST must reach the expected handler and return
        # an authorization error, not a method error.
        response=self.client.post("/world/play/career/no-such-career/offer",data={})
        self.assertEqual(response.status_code,403)

    def test_01_login_gate_and_csrf(self):
        page=self.client.get("/world/play")
        self.assertEqual(page.status_code,200)
        self.assertIn(b"Development access passphrase",page.data)
        self.assertEqual(self.client.post("/world/play/login",data={"password":"wrong"}).status_code,403)
        self.assertEqual(self.client.post("/world/play/create",data={"career_id":"bad"}).status_code,403)
        login=self.client.post("/world/play/login",data={"password":"test-local-access"})
        self.assertEqual(login.status_code,302)
        self.assertIn("HttpOnly",login.headers.get("Set-Cookie",""))
        self.assertIn("Path=/world",login.headers.get("Set-Cookie",""))
        self.assertNotIn("Path=/world/play",login.headers.get("Set-Cookie",""))
        self.assertEqual(self.client.post("/world/play/create",data={"career_id":"bad"}).status_code,403)

    def test_02_create_career_and_offer(self):
        from world_career_play import create_play_blueprint
        import re
        page=self.client.get("/world/play")
        self.assertEqual(page.status_code,200)
        csrf=re.search(rb'name="csrf" value="([^"]+)"',page.data).group(1).decode()
        with sqlite3.connect(self.db) as conn:
            manager=conn.execute("SELECT club_id FROM world_clubs WHERE name='Arsenal'").fetchone()[0]
        new=self.client.post("/world/play/create",data={
            "csrf":csrf,"career_id":"play-test-one","title":"Play test",
            "dataset_id":"england-2026-27-fc27","manager_club_id":manager,
            "economy_version":"prototype-v1","scale":"1",
            "pes_lock_date":"2026-08-01","next_summer_date":"2027-07-01",
        })
        self.assertEqual(new.status_code,302)
        self.assertIn("/world/play/career/play-test-one",new.location)
        detail=self.client.get(new.location)
        self.assertEqual(detail.status_code,200)
        self.assertIn(b"Play test",detail.data)
        self.assertIn(b"Reputation audit",detail.data)
        self.assertIn(b"Total weekly wage budget",detail.data)
        self.assertIn(b"Reserved for future deals",detail.data)
        self.assertIn(b"Remaining weekly wage budget",detail.data)
        self.assertIn(b"Headroom if accepted",detail.data)
        self.assertIn(b"Existing squad wages have not yet been imported",detail.data)
        csrf=re.search(rb'name="csrf" value="([^"]+)"',detail.data).group(1).decode()
        with sqlite3.connect(self.db) as conn:
            target=conn.execute("""SELECT r.player_id FROM world_career_registrations r
                JOIN world_dataset_ratings x ON x.player_id=r.player_id
                 AND x.dataset_id='england-2026-27-fc27'
                WHERE r.career_id='play-test-one' AND r.club_id<>?
                AND x.overall BETWEEN 60 AND 65 LIMIT 1""",(manager,)).fetchone()[0]
        response=self.client.post("/world/play/career/play-test-one/offer",data={
            "csrf":csrf,"request_key":"request-001",
            "player_id":target,"buying_club_id":manager,
            "offered_fee":1000000,"agreement_date":"2027-01-05","seller_stance":"neutral",
        })
        self.assertEqual(response.status_code,302)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("""SELECT COUNT(*) FROM world_career_offers
                WHERE career_id='play-test-one'""").fetchone()[0],1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM world_transfers").fetchone()[0],0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM world_market_offers").fetchone()[0],0)

    def test_03_manager_cannot_control_ai_or_other_clubs(self):
        import re
        detail=self.client.get("/world/play/career/play-test-one")
        csrf=re.search(rb'name="csrf" value="([^"]+)"',detail.data).group(1).decode()
        with sqlite3.connect(self.db) as conn:
            manager=conn.execute("SELECT manager_club_id FROM world_career_saves WHERE career_id='play-test-one'").fetchone()[0]
            another=conn.execute("SELECT club_id FROM world_clubs WHERE name='Manchester City'").fetchone()[0]
            target=conn.execute("""SELECT player_id FROM world_career_registrations
                WHERE career_id='play-test-one' AND club_id=? LIMIT 1""",(another,)).fetchone()[0]
        r=self.client.post("/world/play/career/play-test-one/offer",data={
            "csrf":csrf,"request_key":"unauthorized-buyer",
            "player_id":target,"buying_club_id":another,
            "offered_fee":"1000000","agreement_date":"2027-01-05",
        })
        self.assertEqual(r.status_code,403)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM world_career_offers WHERE request_key='unauthorized-buyer'").fetchone()[0],0)

    def test_035_club_names_visible_for_competing_offers(self):
        detail=self.client.get("/world/play/career/play-test-one")
        self.assertEqual(detail.status_code,200)
        self.assertIn(b"Buying club",detail.data)
        self.assertIn(b"Selling club",detail.data)
        self.assertIn(b"Your club",detail.data)

    def test_036_explicit_new_career_decision_policy_is_frozen(self):
        from world_player_decisions import DECISION_VERSION
        import re
        page=self.client.get("/world/play")
        self.assertEqual(page.status_code,200)
        self.assertIn(b"Player and agent decision model",page.data)
        self.assertIn(b"player-decisions-v1",page.data)
        csrf=re.search(rb'name="csrf" value="([^"]+)"',page.data).group(1).decode()
        with sqlite3.connect(self.db) as db:
            hull=db.execute(
                "SELECT club_id FROM world_clubs WHERE name='Hull City'").fetchone()[0]
        response=self.client.post("/world/play/create",data={
            "csrf":csrf,"career_id":"policy-test-frozen",
            "title":"Policy isolated career",
            "dataset_id":"england-2026-27-fc27",
            "manager_club_id":hull,"economy_version":"prototype-v1",
            "scale":"1","pes_lock_date":"2026-08-01",
            "next_summer_date":"2027-07-01",
            "player_decision_version":DECISION_VERSION,
        })
        self.assertEqual(response.status_code,302)
        with sqlite3.connect(self.db) as db:
            policy=db.execute("""SELECT decision_version FROM world_career_player_policies
                WHERE career_id='policy-test-frozen'""").fetchone()[0]
            self.assertEqual(policy,DECISION_VERSION)
            self.assertEqual(db.execute("""SELECT COUNT(*)
                FROM world_career_prestige_snapshots
                WHERE career_id='policy-test-frozen'""").fetchone()[0],92)
            self.assertEqual(db.execute("""SELECT prestige_score
                FROM world_career_prestige_snapshots
                WHERE career_id='policy-test-frozen' AND club_id=?""",
                (hull,)).fetchone()[0],34)
            self.assertEqual(db.execute("""SELECT COUNT(*)
                FROM world_career_prestige_snapshots
                WHERE career_id='play-test-one'""").fetchone()[0],0)
        details=self.client.get("/world/play/career/policy-test-frozen")
        self.assertEqual(details.status_code,200)
        self.assertIn(b"Player/agent rules:",details.data)
        self.assertIn(b"player-decisions-v1",details.data)
        self.assertIn(b"frozen proposal",details.data)

    def test_037_v2_player_context_requires_manager_and_csrf(self):
        import re
        from world_player_decisions import DECISION_V2_VERSION
        page=self.client.get("/world/play")
        csrf=re.search(rb'name="csrf" value="([^"]+)"',page.data).group(1).decode()
        with sqlite3.connect(self.db) as conn:
            forest=conn.execute(
                "SELECT club_id FROM world_clubs WHERE name='Nottingham Forest'").fetchone()[0]
            arsenal=conn.execute(
                "SELECT club_id FROM world_clubs WHERE name='Arsenal'").fetchone()[0]
            player=conn.execute("""SELECT player_id FROM world_dataset_rosters
                WHERE dataset_id='england-2026-27-fc27' AND club_id=?
                LIMIT 1""",(arsenal,)).fetchone()[0]
        response=self.client.post("/world/play/create",data={
            "csrf":csrf,"career_id":"policy-test-v2-context",
            "title":"Current contract test",
            "dataset_id":"england-2026-27-fc27",
            "manager_club_id":forest,"economy_version":"prototype-v1",
            "scale":"1","pes_lock_date":"2026-08-01",
            "next_summer_date":"2027-07-01",
            "player_decision_version":DECISION_V2_VERSION,
        })
        self.assertEqual(response.status_code,302)
        with sqlite3.connect(self.db) as conn:
            oid=conn.execute("""INSERT INTO world_career_offers
                (career_id,request_key,player_id,buying_club_id,selling_club_id,
                 offered_fee,status,agreement_date,economy_version)
                VALUES('policy-test-v2-context','player-circumstance-ui',?,?,?,
                    1000000,'accepted_pending_contract','2027-01-05','prototype-v1')""",
                (player,forest,arsenal)).lastrowid
            conn.commit()
        form_url="/world/play/career/policy-test-v2-context/circumstances"
        assumptions={
            "offer_id":str(oid),"current_wage_weekly":"150000",
            "current_role":"key_player","transfer_listed":"no",
            "renewal_status":"renewal_offered",
            "seller_europe":"champions_league","buyer_europe":"none",
        }
        self.assertEqual(self.client.post(form_url,data=assumptions).status_code,403)
        self.assertEqual(self.client.post(
            form_url,data={**assumptions,"csrf":"incorrect"}).status_code,403)
        res=self.client.post(form_url,data={**assumptions,"csrf":csrf})
        self.assertEqual(res.status_code,302)
        with sqlite3.connect(self.db) as conn:
            record=conn.execute("""SELECT current_wage_weekly,current_role,transfer_listed,
                       renewal_status,source_kind
                FROM world_career_player_circumstances
                WHERE career_id='policy-test-v2-context' AND player_id=?""",
                (player,)).fetchone()
            self.assertEqual(record,(150000,"key_player",0,
                                     "renewal_offered","user_sandbox_assumption"))
            european=conn.execute("""SELECT seller_europe,buyer_europe,source_kind
                 FROM world_career_offer_europe
                 WHERE career_id='policy-test-v2-context' AND offer_id=?""",
                 (oid,)).fetchone()
            self.assertEqual(european,("champions_league","none",
                                      "user_sandbox_assumption"))
            self.assertEqual(conn.execute("""SELECT COUNT(*)
                FROM world_career_player_circumstances
                WHERE career_id='policy-test-frozen'""").fetchone()[0],0)
        detail=self.client.get("/world/play/career/policy-test-v2-context")
        self.assertEqual(detail.status_code,200)
        self.assertIn(b"Current salary:",detail.data)
        self.assertIn(b"150k",detail.data)
        self.assertIn(b"Current player's circumstances",detail.data)
        self.assertIn(b"European participation at player's current club",detail.data)
        self.assertIn(b"European participation at interested club",detail.data)
        self.assertIn(b"champions league",detail.data.lower())

    def test_04_no_other_career_mutation(self):
        with sqlite3.connect(self.db) as conn:
            count=conn.execute("SELECT COUNT(*) FROM world_dataset_rosters WHERE dataset_id='england-2026-27-fc27'").fetchone()[0]
        self.client.get("/world/play/career/play-test-one")
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM world_dataset_rosters WHERE dataset_id='england-2026-27-fc27'").fetchone()[0],count)


if __name__=="__main__":
    unittest.main()

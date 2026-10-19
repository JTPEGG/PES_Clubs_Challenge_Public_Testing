"""Career-isolated, source-attested dynamic reputation engine tests.

These results are deliberately synthetic unit-test fixtures, not statements
about 2026/27 football results or a user's actual PES challenge record.
"""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from flask import Flask
from itsdangerous import URLSafeTimedSerializer

from world_v2 import initialize_world
from world_explorer import initialize_catalog
from world_reputation_v2 import initialize_pyramid
from world_careers import (initialize_career_engine,start_sandbox,
    player_move_interest,prestige_snapshot,current_career_prestige)
from world_reputation_progression import (
    initialize_progression,preview_progression,finalize_career_season,
    current_career_appeal,latest_season_index,verify_prestige,
    add_prestige_evidence,review_prestige_evidence,project_prestige
)
from world_reputation_progression_ui import create_progression_blueprint


class ProgressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.temp.name)/"dynamic.sqlite"
        cls.conn=sqlite3.connect(cls.path)
        cls.conn.row_factory=sqlite3.Row
        cls.conn.execute("PRAGMA foreign_keys=ON")
        initialize_world(cls.conn)
        initialize_catalog(cls.conn)
        initialize_career_engine(cls.conn)
        initialize_pyramid(cls.conn)
        initialize_progression(cls.conn)
        cls.dataset="england-2026-27-fc27"
        cls.names={r["name"]:r["club_id"] for r in cls.conn.execute(
            "SELECT name,club_id FROM world_clubs")}
        for cid in ("progr-career","untouched-career"):
            start_sandbox(cls.conn,career_id=cid,dataset_id=cls.dataset,
                title="Test only",manager_club_id=cls.names["Hull City"],
                pes_lock_date="2026-08-01",next_summer_date="2027-07-01")
        cls.raw=cls.conn.execute("""SELECT e.club_id,e.competition_id,c.name
            FROM world_dataset_entries e JOIN world_clubs c ON c.club_id=e.club_id
            WHERE e.dataset_id=? ORDER BY e.competition_id,c.name""",
            (cls.dataset,)).fetchall()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        cls.temp.cleanup()

    @classmethod
    def _make_outcomes(cls):
        divisions={}
        for r in cls.raw:
            divisions.setdefault(r["competition_id"],[]).append(r)
        # Synthetic test-only promotions: 3 PL/Champ, 3 Champ/L1, 4 L1/L2.
        # This is NOT a claim about any real football season or PES career.
        moves_up={
            "West Ham United":"ENG1",
            "Wolverhampton Wanderers":"ENG1",
            "Burnley":"ENG1",
            "Leicester City":"ENG2",
            "Oxford United":"ENG2",
            "Sheffield Wednesday":"ENG2",
            "Salford City":"ENG3",
            "Port Vale":"ENG3",
            "Chesterfield":"ENG3",
            "Northampton Town":"ENG3",
        }
        moves_down={
            "Hull City":"ENG2",
            "Coventry City":"ENG2",
            "Ipswich Town":"ENG2",
            "Bolton Wanderers":"ENG3",
            "Lincoln City":"ENG3",
            "Cardiff City":"ENG3",
            "Burton Albion":"ENG4",
            "Cambridge United":"ENG4",
            "Peterborough United":"ENG4",
            "AFC Wimbledon":"ENG4",
        }
        promote=set(moves_up)
        relegate=set(moves_down)
        transitions={**moves_up,**moves_down}
        results=[]
        for division,members in divisions.items():
            top=[r for r in members if r["name"] in promote]
            bottom=[r for r in members if r["name"] in relegate]
            middle=[r for r in members if r["name"] not in promote|relegate]
            ordered=top+middle+bottom
            for pos,club in enumerate(ordered,1):
                results.append({
                    "club_id":club["club_id"],
                    "next_competition_id":transitions.get(club["name"],division),
                    "league_position":pos,
                    "league_size":len(members),
                    "cup_won":False,
                    "source_ref":f"archive:TEST-FIXTURE-{division}-{club['club_id']}",
                })
        return results

    def test_01_hypothetical_preview_is_pure(self):
        cid=self.names["Hull City"]
        before=current_career_appeal(self.conn,"progr-career",cid)
        p=preview_progression(old_score=before["score"],
            old_competition="ENG1",next_competition="ENG2",
            old_form=before["form"],league_position=20,league_size=20)
        self.assertEqual(p["division_delta"],-4)
        self.assertLess(p["projected"],before["score"])
        self.assertEqual(p["previous"],before["score"])
        self.assertEqual(latest_season_index(self.conn,"progr-career"),0)
        self.assertEqual(current_career_appeal(self.conn,"progr-career",cid),before)
        with self.assertRaises(ValueError):
            preview_progression(old_score=69,old_competition="ENG1",
                next_competition="ENG4",old_form=-1,league_position=20,league_size=20)
        with self.assertRaises(ValueError):
            preview_progression(old_score=69,old_competition="ENG1",
                next_competition="ENG2",old_form=-1,league_position=21,league_size=20)

    def test_02_incomplete_or_fabricated_input_cannot_finalize(self):
        r=self._make_outcomes()
        with self.assertRaisesRegex(ValueError,"every club"):
            finalize_career_season(self.conn,career_id="progr-career",
                source_season="2026/27",outcomes=r[:-1],submitted_by="Test operator")
        self.assertEqual(latest_season_index(self.conn,"progr-career"),0)
        r[0]["continental_competition"]="champions_league"
        with self.assertRaisesRegex(ValueError,"separate source"):
            finalize_career_season(self.conn,career_id="progr-career",
                source_season="2026/27",outcomes=r,submitted_by="Test operator")
        del r[0]["continental_competition"]
        with self.assertRaisesRegex(ValueError,"does not match"):
            finalize_career_season(self.conn,career_id="progr-career",
                source_season="2025/26",outcomes=r,submitted_by="Test operator")
        r[0]["source_ref"]="nonsense"
        with self.assertRaisesRegex(ValueError,"source URL"):
            finalize_career_season(self.conn,career_id="progr-career",
                source_season="2026/27",outcomes=r,submitted_by="Test operator")
        self.assertEqual(latest_season_index(self.conn,"progr-career"),0)

    def test_03_full_attested_transition_is_atomic_and_idempotent(self):
        results=self._make_outcomes()
        hull=self.names["Hull City"]
        west=self.names["West Ham United"]
        arsenal=self.names["Arsenal"]
        start_hull=current_career_appeal(self.conn,"progr-career",hull)
        start_west=current_career_appeal(self.conn,"progr-career",west)
        start_arsenal=current_career_appeal(self.conn,"progr-career",arsenal)
        ledger_before=self.conn.execute("""SELECT transfer_budget,weekly_wage_budget,
            committed_fees,committed_wages FROM world_career_club_ledger
            WHERE career_id='progr-career' AND club_id=?""",(hull,)).fetchone()
        source_before=self.conn.execute("""SELECT sporting_appeal FROM world_pyramid_club_appeal
            WHERE dataset_id=? AND club_id=?""",(self.dataset,hull)).fetchone()[0]
        for item in results:
            if item["club_id"]==arsenal:
                item.update({
                    "domestic_cup":"fa_cup",
                    "cup_source_ref":"archive:TEST-ONLY-ARSENAL-FA",
                    "continental_competition":"champions_league",
                    "continental_source_ref":"archive:TEST-ONLY-ARSENAL-QUALIFIED",
                    "continental_trophy":"champions_league",
                    "trophy_source_ref":"archive:TEST-ONLY-ARSENAL-UEFA",
                })
                break
        number=finalize_career_season(self.conn,career_id="progr-career",
            source_season="2026/27",outcomes=results,submitted_by="Test operator")
        self.assertEqual(number,1)
        after_hull=current_career_appeal(self.conn,"progr-career",hull)
        after_west=current_career_appeal(self.conn,"progr-career",west)
        self.assertEqual(after_hull["competition_id"],"ENG2")
        self.assertEqual(after_west["competition_id"],"ENG1")
        arsenal_awards=self.conn.execute("""SELECT cup_bonus,continental_bonus,
            continental_trophy_bonus,temporary_bonus,bonus_overlap_reduction,
            cup_source_ref,continental_source_ref,trophy_source_ref
            FROM world_career_reputation_outcomes
            WHERE career_id='progr-career' AND season_index=1 AND club_id=?""",
            (arsenal,)).fetchone()
        self.assertEqual(tuple(arsenal_awards[:5]),(3,5,4,8,4))
        self.assertTrue(all(a.startswith("archive:TEST-ONLY-") for a in arsenal_awards[5:]))
        self.assertEqual(current_career_appeal(self.conn,"progr-career",arsenal)["temporary_bonus"],8)
        self.assertLess(after_hull["score"],start_hull["score"])
        self.assertGreater(after_west["score"],start_west["score"])
        self.assertEqual(self.conn.execute("""SELECT COUNT(*) FROM world_career_reputation_seasons
            WHERE career_id='progr-career'""").fetchone()[0],184)
        anchors=self.conn.execute("""SELECT season_index,squad_anchor FROM world_career_reputation_seasons
            WHERE career_id='progr-career' AND club_id=? ORDER BY season_index""",
            (hull,)).fetchall()
        self.assertEqual(len(anchors),2)
        self.assertIsNotNone(anchors[0][1])
        self.assertEqual(anchors[0][1],anchors[1][1])
        self.assertEqual(self.conn.execute("""SELECT COUNT(*) FROM world_career_reputation_outcomes
            WHERE career_id='progr-career'""").fetchone()[0],92)
        self.assertEqual(finalize_career_season(self.conn,career_id="progr-career",
            source_season="2026/27",outcomes=results,submitted_by="Test operator"),1)
        self.assertEqual(latest_season_index(self.conn,"progr-career"),1)
        modified=self._make_outcomes()
        modified[0]["cup_won"]=True
        with self.assertRaisesRegex(ValueError,"already finalised"):
            finalize_career_season(self.conn,career_id="progr-career",
                source_season="2026/27",outcomes=modified,submitted_by="Test operator")
        self.assertEqual(self.conn.execute("""SELECT COUNT(*) FROM world_career_reputation_seasons
            WHERE career_id='progr-career'""").fetchone()[0],184)
        self.assertEqual(current_career_appeal(self.conn,"untouched-career",hull),start_hull)
        self.assertEqual(current_career_appeal(self.conn,"untouched-career",arsenal),start_arsenal)
        self.assertEqual(self.conn.execute("""SELECT sporting_appeal FROM world_pyramid_club_appeal
            WHERE dataset_id=? AND club_id=?""",(self.dataset,hull)).fetchone()[0],source_before)
        self.assertEqual(tuple(self.conn.execute("""SELECT transfer_budget,weekly_wage_budget,
            committed_fees,committed_wages FROM world_career_club_ledger
            WHERE career_id='progr-career' AND club_id=?""",(hull,)).fetchone()),tuple(ledger_before))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM world_transfers").fetchone()[0],0)
        self.assertEqual(self.conn.execute("""SELECT COUNT(*) FROM world_career_offers
            WHERE career_id='progr-career'""").fetchone()[0],0)
        self.assertEqual(self.conn.execute("""SELECT COUNT(*) FROM world_career_registrations
            WHERE career_id='progr-career'""").fetchone()[0],
            self.conn.execute("SELECT COUNT(*) FROM world_dataset_rosters WHERE dataset_id=?",
                              (self.dataset,)).fetchone()[0])

    def test_03z_future_transfer_interest_uses_completed_season(self):
        from world_reputation_v2 import assess_player_interest
        hull=self.names["Hull City"]
        west=self.names["West Ham United"]
        source_hull=current_career_appeal(self.conn,"untouched-career",hull)
        source_west=current_career_appeal(self.conn,"untouched-career",west)
        before=assess_player_interest(buyer_tier=1,seller_tier=2,
            buyer_score=source_hull["score"],seller_score=source_west["score"])
        self.assertEqual(before["decision"],"open_to_talks")
        player=self.conn.execute("""SELECT player_id FROM world_dataset_rosters
            WHERE dataset_id=? AND club_id=? ORDER BY player_id LIMIT 1""",
            (self.dataset,west)).fetchone()[0]
        offer_id=self.conn.execute("""INSERT INTO world_career_offers
            (career_id,request_key,player_id,buying_club_id,selling_club_id,
             offered_fee,status,agreement_date,economy_version)
            VALUES('progr-career','post-season-player-check',?,?,?,
                   1000000,'accepted_pending_contract','2027-08-01','prototype-v1')""",
            (player,hull,west)).lastrowid
        self.conn.commit()
        after=player_move_interest(self.conn,career_id="progr-career",offer_id=offer_id)
        self.assertEqual(after["decision"],"needs_assurances")
        self.assertTrue(after["can_negotiate"])
        self.assertNotEqual(after["decision"],before["decision"])
        self.assertEqual(latest_season_index(self.conn,"untouched-career"),0)
        self.assertEqual(self.conn.execute("""SELECT COUNT(*) FROM world_career_registrations
            WHERE career_id='progr-career'""").fetchone()[0],
            self.conn.execute("SELECT COUNT(*) FROM world_dataset_rosters WHERE dataset_id=?",
                              (self.dataset,)).fetchone()[0])

    def test_04_prestige_requires_reviewed_facts(self):
        hull=self.names["Hull City"]
        with self.assertRaisesRegex(ValueError,"three reviewed"):
            verify_prestige(self.conn,dataset_id=self.dataset,club_id=hull,
                prestige_score=60,reviewer="Unit Tester",
                methodology_note="Explicit unit-test score; not a real-world club reputation assessment.")
        self.assertIsNone(current_career_appeal(self.conn,"untouched-career",hull)["prestige"])
        for i,(category,url) in enumerate([
            ("honours","https://example.org/club-honours"),
            ("support","https://example.net/club-support"),
            ("longevity","https://example.net/club-history")]):
            add_prestige_evidence(self.conn,dataset_id=self.dataset,club_id=hull,
                evidence_id=f"TEST-{i}",category=category,
                factual_claim="Synthetic unit-test evidence only",source_url=url)
            review_prestige_evidence(self.conn,dataset_id=self.dataset,club_id=hull,
                evidence_id=f"TEST-{i}",reviewer="Unit Tester",approved=True)
        verify_prestige(self.conn,dataset_id=self.dataset,club_id=hull,
            prestige_score=60,reviewer="Unit Tester",
            methodology_note="Synthetic unit test demonstrating reviewed evidence requirements only.")
        self.assertEqual(current_career_appeal(self.conn,"untouched-career",hull)["prestige"],60)
        self.assertIsNone(current_career_appeal(self.conn,"progr-career",hull)["prestige"])
        self.assertEqual(project_prestige(previous=None,old_competition="ENG1",
            next_competition="ENG2",league_position=20,cup_won=False),(None,0))
        self.assertEqual(project_prestige(previous=60,old_competition="ENG1",
            next_competition="ENG2",league_position=20,cup_won=False),(59,-1))
        self.assertEqual(project_prestige(previous=60,old_competition="ENG1",
            next_competition="ENG1",league_position=1,cup_won=True),(62,2))
        with self.assertRaisesRegex(ValueError,"already reviewed"):
            review_prestige_evidence(self.conn,dataset_id=self.dataset,club_id=hull,
                evidence_id="TEST-0",reviewer="Unit Tester",approved=True)

    def test_06_temporary_awards_expire_after_next_season(self):
        """Two real database transitions, both with wholly synthetic outcomes."""
        cid="test-two-season-opportunity"
        start_sandbox(self.conn,career_id=cid,dataset_id=self.dataset,
            title="Non-stacking awards test only",
            manager_club_id=self.names["Leeds United"],
            pes_lock_date="2026-08-01",next_summer_date="2027-07-01")
        first=self._make_outcomes()
        leeds=self.names["Leeds United"]
        for o in first:
            if o["club_id"]==leeds:
                o.update({
                    "domestic_cup":"fa_cup",
                    "cup_source_ref":"archive:UNIT-TEST-LEEDS-FA",
                    "continental_competition":"europa_league",
                    "continental_source_ref":"archive:UNIT-TEST-LEEDS-EUROPA",
                })
                break
        self.assertEqual(finalize_career_season(self.conn,career_id=cid,
            source_season="2026/27",outcomes=first,submitted_by="Unit-test operator"),1)
        after_first=current_career_appeal(self.conn,cid,leeds)
        self.assertEqual(after_first["temporary_bonus"],6)

        # For the second synthetic season, reverse the exact 3/3/4
        # promotions/relegations; do NOT assume any real-world outcome.
        original={r["club_id"]:r["competition_id"] for r in self.raw}
        current=self.conn.execute("""SELECT r.club_id,r.competition_id,c.name
            FROM world_career_reputation_seasons r JOIN world_clubs c
            ON c.club_id=r.club_id WHERE r.career_id=? AND r.season_index=1
            ORDER BY r.competition_id,c.name""",(cid,)).fetchall()
        groups={}
        for c in current:
            groups.setdefault(c["competition_id"],[]).append(c)
        second=[]
        for division,teams in groups.items():
            to_promote=sorted((c for c in teams if int(original[c["club_id"]][-1])<
                int(division[-1])),key=lambda c:c["name"])
            to_relegate=sorted((c for c in teams if int(original[c["club_id"]][-1])>
                int(division[-1])),key=lambda c:c["name"])
            stationary=sorted((c for c in teams if original[c["club_id"]]==division),
                key=lambda c:c["name"])
            for pos,c in enumerate(to_promote+stationary+to_relegate,1):
                second.append({
                    "club_id":c["club_id"],
                    "next_competition_id":original[c["club_id"]],
                    "league_position":pos,
                    "league_size":len(teams),
                    "cup_won":False,
                    "source_ref":f"archive:TEST-SECOND-SEASON-{c['club_id']}",
                })
        self.assertEqual(finalize_career_season(self.conn,career_id=cid,
            source_season="2027/28",outcomes=second,submitted_by="Unit-test operator"),2)
        after_second=current_career_appeal(self.conn,cid,leeds)
        self.assertEqual(after_second["temporary_bonus"],0)
        self.assertEqual(after_second["cup_bonus"],0)
        self.assertEqual(after_second["continental_bonus"],0)
        self.assertEqual(after_second["score"],after_second["underlying_appeal"])
        self.assertNotEqual(after_second["score"],after_first["score"]+6)
        self.assertEqual(latest_season_index(self.conn,"untouched-career"),0)
        expected_registrations=self.conn.execute("""SELECT COUNT(*) FROM world_dataset_rosters
            WHERE dataset_id=?""",(self.dataset,)).fetchone()[0]
        self.assertEqual(self.conn.execute("""SELECT COUNT(*) FROM world_career_registrations
            WHERE career_id=?""",(cid,)).fetchone()[0],expected_registrations)

    def test_07_new_career_initial_prestige_is_frozen_then_evolves(self):
        """Synthetic relegation can change the career prestige, not its baseline."""
        from world_player_decisions import DECISION_VERSION
        career="synthetic-prestige-progression"
        start_sandbox(self.conn,career_id=career,dataset_id=self.dataset,
            title="Only a synthetic season-transition test",
            manager_club_id=self.names["Hull City"],pes_lock_date="2026-08-01",
            next_summer_date="2027-07-01",
            player_decision_version=DECISION_VERSION)
        hull=self.names["Hull City"]
        self.assertEqual(prestige_snapshot(self.conn,career,hull)["score"],34)
        records=self._make_outcomes()
        self.assertEqual(finalize_career_season(
            self.conn,career_id=career,source_season="2026/27",
            outcomes=records,submitted_by="Test operator"),1)
        self.assertEqual(prestige_snapshot(self.conn,career,hull)["score"],34)
        self.assertEqual(current_career_prestige(self.conn,career,hull)["score"],33)
        self.assertEqual(current_career_appeal(self.conn,career,hull)["prestige"],33)
        self.assertEqual(self.conn.execute("""SELECT prestige_at_snapshot
            FROM world_career_reputation_seasons
            WHERE career_id=? AND season_index=0 AND club_id=?""",
            (career,hull)).fetchone()[0],34)
        self.assertEqual(self.conn.execute("""SELECT prestige_delta
            FROM world_career_reputation_outcomes
            WHERE career_id=? AND season_index=1 AND club_id=?""",
            (career,hull)).fetchone()[0],-1)
        player=self.conn.execute("""SELECT r.player_id
            FROM world_dataset_rosters r
            JOIN world_players p ON p.player_id=r.player_id
            JOIN world_dataset_ratings x ON x.dataset_id=r.dataset_id
              AND x.player_id=r.player_id
            WHERE r.dataset_id=? AND r.club_id=? AND p.birth_date IS NOT NULL
            AND x.overall BETWEEN 62 AND 78 LIMIT 1""",
            (self.dataset,self.names["West Ham United"])).fetchone()[0]
        oid=self.conn.execute("""INSERT INTO world_career_offers
            (career_id,request_key,player_id,buying_club_id,selling_club_id,
             offered_fee,status,agreement_date,economy_version)
            VALUES(?,?,?,?,?,500000,'accepted_pending_contract',
                   '2027-08-05','prototype-v1')""",
            (career,"after-season-prestige-check",player,hull,
             self.names["West Ham United"])).lastrowid
        self.conn.commit()
        interest=player_move_interest(self.conn,career_id=career,offer_id=oid)
        self.assertEqual(interest["buyer_prestige"],33)
        self.assertEqual(interest["seller_prestige"],70)
        self.assertEqual(interest["policy_version"],DECISION_VERSION)
        self.assertEqual(prestige_snapshot(
            self.conn,"progr-career",hull),None)

    def test_05_routes_are_read_only_and_history_protected(self):
        app=Flask(__name__)
        app.register_blueprint(create_progression_blueprint(self.path))
        client=app.test_client()
        r=client.get("/world/reputations/progression")
        self.assertEqual(r.status_code,200)
        self.assertIn(b"Season Reputation Preview",r.data)
        self.assertIn(b"Hypothetical scenario only",r.data)
        r=client.get("/world/reputations/progression?position=3&continental=champions_league")
        self.assertEqual(r.status_code,200)
        self.assertIn(b"European participation",r.data)
        self.assertIn(b"Effective temporary bonus",r.data)
        self.assertIn(b"+5",r.data)
        r=client.get("/world/reputations/prestige")
        self.assertEqual(r.status_code,200)
        self.assertIn(b"Institutional Prestige Evidence",r.data)
        self.assertEqual(client.get("/world/reputations/career/progr-career").status_code,302)
        with patch.dict(os.environ,{"WORLD_MARKET_COOKIE_SECRET":"local-test-key"}):
            token=URLSafeTimedSerializer("local-test-key",salt="pes-world-play-v1").dumps("market-admin")
            client.set_cookie("world_play_access",token)
            r=client.get("/world/reputations/career/progr-career")
            self.assertEqual(r.status_code,200)
            self.assertIn(b"Reputation History",r.data)
            self.assertIn(b"Only recorded",r.data)
        self.assertEqual(client.post("/world/reputations/progression").status_code,405)


if __name__=="__main__":
    unittest.main()

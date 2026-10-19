"""Expectation fairness and isolated locked-objective persistence tests."""
import sqlite3
import unittest
from world_board_objectives import evaluate_objective,proxy_rankings
from world_career_objectives import (
    initialize_board_objectives,lock_objective,review_season,objective_history,
)
from test_career_management import fixture
from world_career_management import set_initial_confidence

class BoardObjectiveTests(unittest.TestCase):
    def test_newly_promoted_underdog_tenth_is_exceptional(self):
        r=evaluate_objective(expected_rank=19,actual_rank=10,league_size=20,
                             expected_relegation=True)
        self.assertEqual(r["grade"],"exceptional")
        self.assertGreaterEqual(r["confidence_delta"],12)

    def test_favourite_promoted_second_is_modest(self):
        r=evaluate_objective(expected_rank=1,actual_rank=2,league_size=24,
                             promoted=True,expected_relegation=False)
        self.assertEqual(r["grade"],"met")
        self.assertLessEqual(r["confidence_delta"],4)

    def test_expected_relegation_not_harsh_extra_penalty(self):
        expected=evaluate_objective(expected_rank=20,actual_rank=18,
                                    league_size=20,expected_relegation=True,
                                    relegated=True)
        surprise=evaluate_objective(expected_rank=10,actual_rank=18,
                                    league_size=20,expected_relegation=False,
                                    relegated=True)
        self.assertGreater(expected["confidence_delta"],surprise["confidence_delta"])
        self.assertEqual(expected["relegation_delta"],0)

    def test_promotion_not_awarded_twenty_points(self):
        r=evaluate_objective(expected_rank=1,actual_rank=1,league_size=24,
                             promoted=True)
        self.assertLess(r["confidence_delta"],10)

    def test_cup_minor_non_duplicate_adjustment(self):
        a=evaluate_objective(expected_rank=9,actual_rank=9,league_size=20)
        b=evaluate_objective(expected_rank=9,actual_rank=9,league_size=20,
                             cup_result="above")
        self.assertEqual(b["confidence_delta"]-a["confidence_delta"],2)

    def test_proxy_missing_data_remains_unknown(self):
        clubs=[dict(club_id=i,strength=(None if i==3 else 80-i)) for i in range(1,21)]
        self.assertIsNone(proxy_rankings(clubs=clubs))

    def test_proxy_ranks_from_strength_not_actual_league_table(self):
        clubs=[dict(club_id=i,strength=100-i) for i in range(1,21)]
        self.assertEqual(proxy_rankings(clubs=clubs)[1],1)
        self.assertEqual(proxy_rankings(clubs=clubs)[20],20)

    def test_bad_ranks_and_conflicting_status_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_objective(expected_rank=21,actual_rank=10,league_size=20)
        with self.assertRaises(ValueError):
            evaluate_objective(expected_rank=19,actual_rank=10,league_size=20,
                               promoted=True,relegated=True)


class ObjectiveStorageTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture()
        self.db.execute("ALTER TABLE world_career_saves ADD COLUMN manager_club_id INTEGER")
        self.db.execute("ALTER TABLE world_career_saves ADD COLUMN state TEXT NOT NULL DEFAULT 'sandbox'")
        self.db.execute("UPDATE world_career_saves SET manager_club_id=1")
        self.db.commit()
        initialize_board_objectives(self.db)
        set_initial_confidence(self.db,career_id="career-a",club_id=1,value=50)

    def tearDown(self):
        self.db.close()

    def lock(self,**overrides):
        args=dict(career_id="career-a",club_id=1,season_key="2026-27",
            expected_rank=19,league_size=20,expected_relegation=True,
            source_note="Explicit fictional starting expectation for test",
            strength_source="user_sandbox_assumption")
        return lock_objective(self.db,**{**args,**overrides})

    def review(self,**overrides):
        args=dict(career_id="career-a",club_id=1,season_key="2026-27",
            actual_rank=10,promoted=False,relegated=False,
            cup_result="not_assessed",result_note="Verified final league table")
        return review_season(self.db,**{**args,**overrides})

    def test_lock_is_idempotent_and_uneditable(self):
        self.assertTrue(self.lock())
        self.assertFalse(self.lock())
        with self.assertRaises(ValueError):
            self.lock(expected_rank=20)

    def test_review_requires_preseason_objective(self):
        with self.assertRaises(ValueError):
            self.review()

    def test_confirmed_review_updates_confidence_once(self):
        self.lock()
        first=self.review()
        second=self.review()
        self.assertFalse(first["replayed"])
        self.assertTrue(second["replayed"])
        self.assertEqual(first["confidence_after"],second["confidence_after"])
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM world_career_season_reviews").fetchone()[0],1)

    def test_review_does_not_allow_rewriting_result(self):
        self.lock()
        self.review()
        with self.assertRaises(ValueError):
            self.review(actual_rank=17)

    def test_wrong_career_club_cannot_be_changed(self):
        with self.assertRaises(ValueError):
            self.lock(club_id=2)

    def test_history_is_career_specific(self):
        self.lock()
        self.review()
        hist=objective_history(self.db,career_id="career-a",club_id=1)
        self.assertEqual(len(hist),1)
        self.assertEqual(hist[0]["actual_rank"],10)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM world_career_season_objectives WHERE career_id='career-b'").fetchone()[0],0)

    def test_absent_initial_board_confidence_blocks_review(self):
        self.lock()
        self.db.execute("DELETE FROM world_career_management_board")
        self.db.commit()
        with self.assertRaises(ValueError):
            self.review()

    def test_atomic_rollback_on_invalid_review(self):
        self.lock()
        with self.assertRaises(ValueError):
            self.review(actual_rank=0)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM world_career_season_reviews").fetchone()[0],0)

    def test_cannot_double_count_promotion_after_objective_locked(self):
        from world_career_management import record_board_event
        self.lock()
        with self.assertRaises(ValueError):
            record_board_event(self.db,career_id="career-a",club_id=1,
                event_key="season1-promotion",event_type="promotion",
                event_date="2026-10-14",source_note="Confirmed")
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM world_career_management_events").fetchone()[0],0)

    def test_relegation_does_not_auto_penalise_favourite_to_drop(self):
        self.lock(expected_rank=20)
        r=self.review(actual_rank=18,relegated=True)
        self.assertGreaterEqual(r["evaluation"]["confidence_delta"],0)

if __name__=="__main__":
    unittest.main()

"""Only one real-world feeder level below the selected PES playable floor."""
import sqlite3
import tempfile
import unittest
from world_lightweight_feeder import (
    ENGLISH_LEAGUE_TWO,ENGLISH_NATIONAL,ENGLISH_NORTH,ENGLISH_SOUTH,
    FLOOR_MODE,VERSION,load_english_feeder_pools,rollover,
)

def clubs(prefix,n=24):
    return tuple(f"{prefix} Town {i:02d}" for i in range(n))

def pools():
    return {ENGLISH_LEAGUE_TWO:clubs("L2"),
            ENGLISH_NATIONAL:clubs("National"),
            ENGLISH_NORTH:clubs("North"),ENGLISH_SOUTH:clubs("South")}

class LightweightOneHopFeederTests(unittest.TestCase):
    def test_no_synthetic_pyramid_below_north_south(self):
        self.assertEqual(FLOOR_MODE["league_two"]["feeders"],(ENGLISH_NATIONAL,))
        self.assertEqual(FLOOR_MODE["national_league"]["feeders"],
                         (ENGLISH_NORTH,ENGLISH_SOUTH))
        self.assertEqual(len(FLOOR_MODE),2)
        self.assertTrue(VERSION)
        with self.assertRaises(ValueError):
            rollover(pools(),playable_floor="league_one",starting_season=2026,
                     relegated_from_playable=[])
    def test_l2_replaces_two_from_real_national_league_without_squads(self):
        original=pools()
        demoted=original[ENGLISH_LEAGUE_TWO][:2]
        first=rollover(original,playable_floor="league_two",starting_season=2026,
                       relegated_from_playable=demoted)
        second=rollover(original,playable_floor="league_two",starting_season=2026,
                       relegated_from_playable=demoted)
        self.assertEqual(first,second)
        self.assertEqual(len(first["promoted_into_playable"]),2)
        self.assertEqual(len(first["simulated_feeders"]),1)
        self.assertEqual(first["simulated_feeders"],[ENGLISH_NATIONAL])
        self.assertEqual(first["club_pools_after"][ENGLISH_NATIONAL][-2:],list(demoted))
        self.assertEqual(len(first["club_pools_after"][ENGLISH_LEAGUE_TWO]),24)
        self.assertTrue(set(first["promoted_into_playable"]).issubset(original[ENGLISH_NATIONAL]))
        self.assertEqual(len(original[ENGLISH_NATIONAL]),24)
        self.assertTrue(first["no_game_squads_generated"])
        self.assertFalse(first["career_activation_approved"])
    def test_option_nl_playable_uses_north_south_no_step_three_four(self):
        original=pools()
        demoted=original[ENGLISH_NATIONAL][:4]
        regions={demoted[0]:ENGLISH_NORTH,demoted[1]:ENGLISH_NORTH,
                 demoted[2]:ENGLISH_SOUTH,demoted[3]:ENGLISH_SOUTH}
        result=rollover(original,playable_floor="national_league",
                       starting_season=2026,relegated_from_playable=demoted,
                       destination_regions=regions)
        self.assertEqual(len(result["promoted_into_playable"]),4)
        self.assertEqual(set(result["simulated_feeders"]),{ENGLISH_NORTH,ENGLISH_SOUTH})
        self.assertEqual(result["bottom_external_depth"],1)
        self.assertEqual(len(result["club_pools_after"][ENGLISH_NATIONAL]),24)
        self.assertEqual(len(result["club_pools_after"][ENGLISH_NORTH]),24)
        self.assertEqual(len(result["club_pools_after"][ENGLISH_SOUTH]),24)
        self.assertFalse(any("en.7" in x for x in result["club_pools_after"]))
        self.assertFalse(result["career_activation_approved"])
    def test_no_guessing_geographic_relegation(self):
        demoted=pools()[ENGLISH_NATIONAL][:4]
        with self.assertRaises(ValueError):
            rollover(pools(),playable_floor="national_league",
                     starting_season=2026,relegated_from_playable=demoted)
        with self.assertRaises(ValueError):
            rollover(pools(),playable_floor="national_league",
                     starting_season=2026,relegated_from_playable=demoted,
                     destination_regions={name:ENGLISH_NORTH for name in demoted})
    def test_fictitious_relegated_club_rejected(self):
        with self.assertRaises(ValueError):
            rollover(pools(),playable_floor="league_two",starting_season=2026,
                     relegated_from_playable=["Made Up FC","L2 Town 00"])
        with self.assertRaises(ValueError):
            rollover(pools(),playable_floor="league_two",starting_season=2026,
                     relegated_from_playable=["L2 Town 00","L2 Town 00"])
        with self.assertRaises(ValueError):
            rollover(pools(),playable_floor="league_two",starting_season=2026,
                     relegated_from_playable=["L2 Town 00"])
    def test_original_registry_required_for_real_feeder_pools(self):
        with sqlite3.connect(":memory:") as db:
            with self.assertRaises((sqlite3.OperationalError,ValueError)):
                load_english_feeder_pools(db)
            with self.assertRaises(ValueError):
                load_english_feeder_pools(db,edition=2026)

if __name__=="__main__":
    unittest.main()

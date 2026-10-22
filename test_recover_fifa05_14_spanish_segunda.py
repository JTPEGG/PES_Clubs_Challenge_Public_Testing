import unittest
from scripts.recover_fifa05_14_spanish_segunda import match_teams,team_name,EDITION_RANGE,PIN

class FifaLegacySegundaTests(unittest.TestCase):
    def test_real_club_names_not_betting_place_markers(self):
        self.assertEqual(team_name("Real Valladolid CF (1)"),"Real Valladolid CF")
        self.assertEqual(team_name("Racing Ferrol (5)"),"Racing Ferrol")
        self.assertEqual(team_name("Real Madrid Castilla"),"Real Madrid Castilla")
        self.assertEqual(len(PIN),40)
        self.assertEqual(EDITION_RANGE,tuple(range(2005,2015)))

    def test_requires_complete_22_club_source_roster(self):
        lines=["Round,Date,Team 1,FT,HT,Team 2"]
        for i in range(230):
            a=i%22
            b=(i+1)%22
            lines.append(f'?,2004-09-01,Club {a:02d} (1),2-1,1-0,Club {b:02d} (1)')
        names,games=match_teams("\n".join(lines))
        self.assertEqual(len(names),22)
        self.assertEqual(games,230)
        self.assertEqual(names[0],"Club 00")

    def test_reject_incomplete_and_self_playing_fixtures(self):
        lines=["Round,Date,Team 1,FT,HT,Team 2"]
        lines.extend("?,2004-08-01,Arsenal (1),2-1,1-0,Club (1)" for _ in range(20))
        with self.assertRaises(ValueError):
            match_teams("\n".join(lines))
        with self.assertRaises(ValueError):
            match_teams("Round,Date,Team 1,FT,HT,Team 2\n?,2004,Arsenal (1),2-1,1-0,Arsenal (1)")

if __name__=="__main__":
    unittest.main()

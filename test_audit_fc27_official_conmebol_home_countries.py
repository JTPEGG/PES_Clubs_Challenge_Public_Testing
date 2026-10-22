import unittest
from scripts.audit_fc27_official_conmebol_home_countries import (
 parse_country_directory,namekey,COUNTRIES
)

class OfficialClubCountryAuditTests(unittest.TestCase):
 def test_country_is_from_continental_official_directory_not_the_club_name(self):
  countries=list(sorted(COUNTRIES))
  html="<html><h2>All teams</h2>"+"".join(
     f"<div><p>Club {i} City</p><span>{countries[i%len(countries)]}</span></div>"
     for i in range(30))+"</html>"
  names,pairs=parse_country_directory(html)
  self.assertEqual(len(pairs),30)
  self.assertEqual(names[namekey("Club 4 City")],{countries[4%len(countries)]})
  self.assertEqual(namekey("Alianza Atltico"),namekey("Alianza Atlético"))
  self.assertNotEqual(namekey("Libertad"),namekey("Liverpool"))
 def test_rejects_incomplete_or_non_official_club_team_lists(self):
  with self.assertRaises(ValueError):
   parse_country_directory("<html><p>Not teams</p><p>Brazil</p></html>")
  with self.assertRaises(ValueError):
   parse_country_directory("<h2>All teams</h2><p>Arsenal</p><p>England</p>")

if __name__=="__main__":
 unittest.main()

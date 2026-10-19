"""Verified initial 2026/27 English league membership.

Only club names, league memberships and source URLs. No ratings or player
registrations inferred from these lists. Never use this module for later
in-universe promotions/relegations: those are saved as separate seasons.
"""
LEAGUE_MEMBERS = {
 "ENG1": (
  "https://www.premierleague.com/en/news/4365156",
  ("AFC Bournemouth","Arsenal","Aston Villa","Brentford",
   "Brighton & Hove Albion","Chelsea","Coventry City","Crystal Palace",
   "Everton","Fulham","Hull City","Ipswich Town","Leeds United",
   "Liverpool","Manchester City","Manchester United",
   "Newcastle United","Nottingham Forest","Sunderland","Tottenham Hotspur")
 ),
 "ENG2": (
  "https://www.wba.co.uk/news/202627-sky-bet-championship-line-confirmed",
  ("Birmingham City","Blackburn Rovers","Bolton Wanderers","Bristol City",
   "Burnley","Cardiff City","Charlton Athletic","Derby County",
   "Lincoln City","Middlesbrough","Millwall","Norwich City",
   "Portsmouth","Preston North End","Queens Park Rangers",
   "Sheffield United","Southampton","Stoke City","Swansea City",
   "Watford","West Bromwich Albion","West Ham United",
   "Wolverhampton Wanderers","Wrexham")
 ),
 "ENG3": (
  "https://www.transfermarkt.co.uk/liga-1/teilnehmer/pokalwettbewerb/GB3",
  ("AFC Wimbledon","Barnsley","Blackpool","Bradford City","Bromley",
   "Burton Albion","Cambridge United","Doncaster Rovers",
   "Huddersfield Town","Leicester City","Leyton Orient","Luton Town",
   "Mansfield Town","Milton Keynes Dons","Notts County","Oxford United",
   "Peterborough United","Plymouth Argyle","Reading",
   "Sheffield Wednesday","Stevenage","Stockport County",
   "Wigan Athletic","Wycombe Wanderers")
 ),
 "ENG4": (
  "https://www.transfermarkt.co.uk/league-two/teilnehmer/pokalwettbewerb/GB4",
  ("Accrington Stanley","Barnet","Bristol Rovers","Cheltenham Town",
   "Chesterfield","Colchester United","Crawley Town","Crewe Alexandra",
   "Exeter City","Fleetwood Town","Gillingham","Grimsby Town",
   "Newport County","Northampton Town","Oldham Athletic","Port Vale",
   "Rochdale","Rotherham United","Salford City","Shrewsbury Town",
   "Swindon Town","Tranmere Rovers","Walsall","York City")
 )
}
EXPECTED_SIZES = {"ENG1":20,"ENG2":24,"ENG3":24,"ENG4":24}


def validate_memberships(leagues=LEAGUE_MEMBERS):
    errors = []
    seen = {}
    for league, (_, members) in leagues.items():
        if len(members) != EXPECTED_SIZES[league]:
            errors.append(f"{league}: expected {EXPECTED_SIZES[league]}, got {len(members)}")
        for club in members:
            if club in seen:
                errors.append(f"{club}: duplicated in {seen[club]} and {league}")
            seen[club] = league
    if set(leagues) != set(EXPECTED_SIZES):
        errors.append("Competition list does not match required four divisions")
    if len(seen) != 92:
        errors.append(f"Expected 92 distinct clubs, got {len(seen)}")
    return errors

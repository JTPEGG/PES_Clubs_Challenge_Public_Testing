"""Visual club identity for isolated FC27 Career Desk presentation.

Verified image URL mappings reused from the user's Anderlecht challenge
frontend. These are display-only and do not alter the 659-club source.
Unmapped clubs receive an honest monogram, never a mismatched crest.
"""
import re

CREST_URLS = {
  "Barnsley": "https://assets.footylogos.com/logos/barnsley/barnsley-logo-footylogos.svg",
  "Birmingham City": "https://assets.footylogos.com/logos/birmingham-city/birmingham-city-logo-footylogos.svg",
  "Blackburn Rovers": "https://crests.football-data.org/59.png",
  "Brentford": "https://crests.football-data.org/402.png",
  "Bristol City": "https://crests.football-data.org/387.png",
  "Cardiff City": "https://crests.football-data.org/715.png",
  "Charlton Athletic": "https://assets.footylogos.com/logos/charlton-athletic/charlton-athletic-logo-footylogos.svg",
  "Derby County": "https://crests.football-data.org/342.png",
  "Fulham": "https://crests.football-data.org/63.png",
  "Huddersfield Town": "https://crests.football-data.org/394.png",
  "Hull City": "https://crests.football-data.org/322.png",
  "Leeds United": "https://crests.football-data.org/341.png",
  "Luton Town": "https://crests.football-data.org/389.png",
  "Middlesbrough": "https://crests.football-data.org/343.png",
  "Millwall": "https://crests.football-data.org/384.png",
  "Nottingham Forest": "https://crests.football-data.org/351.png",
  "Preston North End": "https://crests.football-data.org/1081.png",
  "QPR": "https://crests.football-data.org/69.png",
  "Reading": "https://crests.football-data.org/355.png",
  "Sheffield Wednesday": "https://crests.football-data.org/345.png",
  "Stoke City": "https://crests.football-data.org/70.png",
  "Swansea City": "https://crests.football-data.org/72.png",
  "West Bromwich Albion": "https://crests.football-data.org/74.png",
  "Wigan Athletic": "https://crests.football-data.org/75.png",
  "Preston": "https://crests.football-data.org/1081.png",
  "West Brom": "https://crests.football-data.org/74.png",
  "Nottm Forest": "https://crests.football-data.org/351.png",
  "Sheff Wed": "https://crests.football-data.org/345.png",
  "Burnley": "https://crests.football-data.org/328.png",
  "Coventry City": "https://crests.football-data.org/1076.png",
  "Norwich City": "https://crests.football-data.org/68.png",
  "Oxford United": "https://crests.football-data.org/1082.png",
  "Plymouth Argyle": "https://crests.football-data.org/1138.png",
  "Portsmouth": "https://crests.football-data.org/325.png",
  "Rotherham United": "https://crests.football-data.org/385.png",
  "Sheffield United": "https://crests.football-data.org/356.png",
  "Sunderland": "https://crests.football-data.org/71.png",
  "Watford": "https://crests.football-data.org/346.png",
  "Arsenal": "https://crests.football-data.org/57.png",
  "Aston Villa": "https://crests.football-data.org/58.png",
  "AFC Bournemouth": "https://crests.football-data.org/1044.png",
  "Brighton & Hove Albion": "https://crests.football-data.org/397.png",
  "Chelsea": "https://crests.football-data.org/61.png",
  "Crystal Palace": "https://crests.football-data.org/354.png",
  "Everton": "https://crests.football-data.org/62.png",
  "Leicester City": "https://crests.football-data.org/338.png",
  "Liverpool": "https://crests.football-data.org/64.png",
  "Manchester City": "https://crests.football-data.org/65.png",
  "Manchester United": "https://crests.football-data.org/66.png",
  "Newcastle United": "https://crests.football-data.org/67.png",
  "Southampton": "https://crests.football-data.org/340.png",
  "Tottenham Hotspur": "https://crests.football-data.org/73.png",
  "West Ham United": "https://crests.football-data.org/563.png",
  "Wolverhampton Wanderers": "https://crests.football-data.org/76.png",
  "Anderlecht": "https://assets.footylogos.com/logos/rsc-anderlecht/rsc-anderlecht-logo-footylogos.svg",
  "Antwerp": "https://assets.footylogos.com/logos/royal-antwerp/royal-antwerp-logo-footylogos.svg",
  "Cercle Brugge": "https://assets.footylogos.com/logos/cercle-brugge/cercle-brugge-logo-footylogos.svg",
  "Club Brugge": "https://assets.footylogos.com/logos/club-brugge/club-brugge-logo-footylogos.svg",
  "Genk": "https://assets.footylogos.com/logos/krc-genk/krc-genk-logo-footylogos.svg",
  "Gent": "https://assets.footylogos.com/logos/kaa-gent/kaa-gent-logo-footylogos.svg",
  "Eupen": "https://assets.footylogos.com/logos/kas-eupen/kas-eupen-logo-footylogos.svg",
  "Kortrijk": "https://assets.footylogos.com/logos/kv-kortrijk/kv-kortrijk-logo-footylogos.svg",
  "Oostende": "https://assets.footylogos.com/logos/kv-oostende/kv-oostende-logo-footylogos.svg",
  "Mechelen": "https://assets.footylogos.com/logos/kv-mechelen/kv-mechelen-logo-footylogos.svg",
  "Mouscron": "https://img.sofascore.com/api/v1/team/44019/image",
  "St Truiden": "https://assets.footylogos.com/logos/sint-truiden/sint-truiden-logo-footylogos.svg",
  "Charleroi": "https://assets.footylogos.com/logos/sporting-charleroi/sporting-charleroi-logo-footylogos.svg",
  "Standard": "https://assets.footylogos.com/logos/standard-liege/standard-liege-logo-footylogos.svg",
  "Waasland-Beveren": "https://img.sofascore.com/api/v1/team/4859/image",
  "Waregem": "https://assets.footylogos.com/logos/zulte-waregem-logo-footylogos.svg"
}
ALIASES = {
  "Queens Park Rangers": "QPR",
  "RSC Anderlecht": "Anderlecht",
  "KRC Genk": "Genk",
  "KAA Gent": "Gent",
  "Royal Antwerp": "Antwerp",
  "Wolves": "Wolverhampton Wanderers"
}
KITS = {
  "Arsenal": [
    "#EF0107",
    "#FFFFFF"
  ],
  "Aston Villa": [
    "#670E36",
    "#95BFE5"
  ],
  "Brentford": [
    "#D21D33",
    "#F9F9F9"
  ],
  "Chelsea": [
    "#034694",
    "#FFFFFF"
  ],
  "Liverpool": [
    "#C8102E",
    "#F6EFB1"
  ],
  "Manchester City": [
    "#6CABDD",
    "#FFFFFF"
  ],
  "Manchester United": [
    "#DA291C",
    "#FFFFFF"
  ],
  "Tottenham Hotspur": [
    "#132257",
    "#FFFFFF"
  ],
  "Everton": [
    "#003399",
    "#FFFFFF"
  ],
  "West Ham United": [
    "#7A263A",
    "#1BB1E7"
  ],
  "Newcastle United": [
    "#161616",
    "#F6F6F6"
  ],
  "Nottingham Forest": [
    "#E63227",
    "#FFFFFF"
  ],
  "Crystal Palace": [
    "#1B458F",
    "#C41230"
  ],
  "Brighton & Hove Albion": [
    "#0057B8",
    "#FFFFFF"
  ],
  "AFC Bournemouth": [
    "#D51D29",
    "#171717"
  ],
  "Fulham": [
    "#111111",
    "#FFFFFF"
  ],
  "Burnley": [
    "#6C1D45",
    "#99D6EA"
  ],
  "Bristol City": [
    "#D50024",
    "#FFFFFF"
  ],
  "Birmingham City": [
    "#0033A0",
    "#FFFFFF"
  ],
  "Blackburn Rovers": [
    "#1677BD",
    "#FFFFFF"
  ],
  "Bolton Wanderers": [
    "#FFFFFF",
    "#17295D"
  ],
  "Cardiff City": [
    "#0070B5",
    "#FFFFFF"
  ],
  "Charlton Athletic": [
    "#D32027",
    "#FFFFFF"
  ],
  "Coventry City": [
    "#81C4EA",
    "#FFFFFF"
  ],
  "Derby County": [
    "#111111",
    "#FFFFFF"
  ],
  "Leeds United": [
    "#FFFFFF",
    "#1D428A"
  ],
  "Leicester City": [
    "#003090",
    "#FFFFFF"
  ],
  "Lincoln City": [
    "#C8102E",
    "#FFFFFF"
  ],
  "Middlesbrough": [
    "#E50025",
    "#FFFFFF"
  ],
  "Millwall": [
    "#002D56",
    "#FFFFFF"
  ],
  "Norwich City": [
    "#FFF200",
    "#008B4A"
  ],
  "Portsmouth": [
    "#004D9F",
    "#FFFFFF"
  ],
  "Preston North End": [
    "#FFFFFF",
    "#001D4A"
  ],
  "Queens Park Rangers": [
    "#116BC2",
    "#FFFFFF"
  ],
  "Sheffield United": [
    "#E5282C",
    "#FFFFFF"
  ],
  "Sheffield Wednesday": [
    "#0052A5",
    "#FFFFFF"
  ],
  "Southampton": [
    "#D71920",
    "#FFFFFF"
  ],
  "Stoke City": [
    "#DD111B",
    "#FFFFFF"
  ],
  "Sunderland": [
    "#E2231A",
    "#FFFFFF"
  ],
  "Swansea City": [
    "#FFFFFF",
    "#121212"
  ],
  "Watford": [
    "#F5D800",
    "#D21D24"
  ],
  "West Bromwich Albion": [
    "#132257",
    "#FFFFFF"
  ],
  "Wolverhampton Wanderers": [
    "#FDB913",
    "#231F20"
  ],
  "Wrexham": [
    "#D9272E",
    "#FFFFFF"
  ],
  "Oxford United": [
    "#FFDA00",
    "#12295A"
  ],
  "Reading": [
    "#0055B8",
    "#FFFFFF"
  ],
  "Blackpool": [
    "#FF6600",
    "#FFFFFF"
  ],
  "Barnsley": [
    "#E20613",
    "#FFFFFF"
  ],
  "RSC Anderlecht": [
    "#522492",
    "#FFFFFF"
  ],
  "Anderlecht": [
    "#522492",
    "#FFFFFF"
  ],
  "Club Brugge": [
    "#0059A4",
    "#111111"
  ],
  "Cercle Brugge": [
    "#00853E",
    "#111111"
  ],
  "Genk": [
    "#0055AA",
    "#FFFFFF"
  ],
  "Gent": [
    "#194BA0",
    "#FFFFFF"
  ],
  "Antwerp": [
    "#C9082A",
    "#FFFFFF"
  ],
  "Standard": [
    "#D81B2B",
    "#FFFFFF"
  ],
  "Charleroi": [
    "#111111",
    "#FFFFFF"
  ],
  "Mechelen": [
    "#F2C600",
    "#D11F26"
  ],
  "Inter": [
    "#0068A8",
    "#161616"
  ],
  "AC Milan": [
    "#BE1723",
    "#111111"
  ],
  "Juventus": [
    "#111111",
    "#FFFFFF"
  ],
  "Real Madrid": [
    "#FFFFFF",
    "#2B3A79"
  ],
  "Barcelona": [
    "#A50044",
    "#004D98"
  ],
  "Bayern Munich": [
    "#DC052D",
    "#FFFFFF"
  ]
}

def club_brand(raw_name):
    name=re.sub(r"\s*\[WH27:[^\]]+\]\s*$","",str(raw_name or "")).strip()
    alias=ALIASES.get(name,name)
    crest=CREST_URLS.get(alias)
    primary,trim=KITS.get(name,KITS.get(alias,("#242B26","#FFD230")))
    color=primary.lstrip("#")
    r,g,b=(int(color[i:i+2],16)/255 for i in (0,2,4))
    luminance=.2126*r+.7152*g+.0722*b
    initials="".join(x[0] for x in re.findall(r"[A-Za-z]+",name)[:3]).upper() or "FC"
    return dict(name=name,logo=crest,initials=initials,primary=primary,
                trim=trim,text="#171917" if luminance>.60 else "#FFFFFF",
                real_crest=bool(crest))

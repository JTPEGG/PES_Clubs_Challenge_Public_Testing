"""Provisional, auditable all-92 English institutional prestige draft.

The existing 15 calibrations are kept unchanged. This module adds 77
explicit game-design proposals, all flagged UNVERIFIED/REVIEW NEEDED.
Nothing here writes an approved prestige record or modifies a career.

Research references:
 - https://www.fchd.info/ (historical league records, 2025/26 updated)
 - https://www.thefa.com/competitions/thefacup/results-archive
 - https://en.wikipedia.org/wiki/List_of_football_stadiums_in_England
 - https://www.reuters.com/sports/soccer/list-english-league-cup-winners-2025-03-16/
 - https://www.thefa.com/news/2026/may/16/emirates-fa-cup-final-chelsea-v-manchester-city-report-20261605
 - https://en.wikipedia.org/wiki/List_of_EFL_Cup_finals
Reviewed values can differ from rough source listings. Historical, European
and identity bands are discretionary calibration inputs, not sourced rankings.
All named major-title counts below must be rechecked against club records
before approved production use; e.g. 2026 honours need 2026 results checks.
"""
from urllib.parse import quote
from world_2026_27_clubs import LEAGUE_MEMBERS,EXPECTED_SIZES
from world_prestige_calibration import (
    CLUBS as ORIGINAL_15,DATASET_ID,DIMENSIONS,score_club,stadium_points,VERSION
)

FULL_VERSION="institutional-prestige-pyramid-draft-v1"
CAPACITY_SOURCE="https://en.wikipedia.org/wiki/List_of_football_stadiums_in_England"
HISTORY_SOURCE="https://www.fchd.info/"
FA_SOURCE="https://www.thefa.com/competitions/thefacup/results-archive"
LEAGUE_CUP_SOURCE="https://en.wikipedia.org/wiki/List_of_EFL_Cup_finals"
ENGLISH_TITLES_SOURCE="https://www.fchd.info/lghist/lghistsummary.htm"

# Name | top-flight league titles | FA Cups | League Cups
# | European (editorial 0-20) | historical continuity (editorial 0-20)
# | cultural identity (editorial 0-10) | home-ground capacity reference
# | compact editor note about the differentiating historical factor.
#
# Major honours do NOT include EFL Trophy, Community Shield,
# promotions, second/third/fourth-tier championships or FA Trophy.
# Scores are NEVER automatically approved. Zero denotes a provisional
# record of 0 relevant major titles, not proof of exhaustive fact checking.
_NEW_ROWS = """
AFC Bournemouth|0|0|0|1|11|7|11307|Modern sustained top-flight period; small stadium for current playing level
Brentford|0|0|0|1|11|7|17250|Established west-London club with recent Premier League continuity
Brighton & Hove Albion|0|0|0|3|13|8|31876|Historic lower-league roots and established modern Premier League period
Chelsea|6|8|5|20|19|10|40044|Multiple English league and European championships; established global following
Coventry City|0|1|0|0|15|8|32609|1987 FA Cup and long past uninterrupted top-flight residence
Crystal Palace|0|1|0|2|14|8|25194|2025 FA Cup winners; established modern Premier League participation
Everton|9|5|0|11|20|10|52769|Historic English champions; long continuous top-flight history
Fulham|0|0|0|4|14|8|27782|Long-standing London club; 2010 UEFA Europa League runners-up
Ipswich Town|1|1|0|13|17|9|29813|English champions, FA Cup and UEFA Cup winners in historic high point
Leeds United|3|1|1|12|19|10|37645|English league championships, UEFA finals and prominent fanbase
Liverpool|20|8|10|20|20|10|61276|Record-level domestic and European success; historic global support
Manchester City|10|8|9|20|19|10|61038|Multiple recent top-flight and major cup wins; 2023 European champions
Manchester United|20|13|6|20|20|10|74244|Long English and European honours record with global following
Newcastle United|4|6|1|9|19|10|52719|Historic top-flight and FA Cup successes; won League Cup in 2025
Sunderland|6|2|0|1|19|9|48095|Six English league titles and a long historic top-tier presence
Tottenham Hotspur|2|8|4|18|19|10|62850|Major FA Cup pedigree and European silverware
Birmingham City|0|0|2|3|17|8|29409|Two League Cups; extensive top-two-divisions history
Blackburn Rovers|3|6|1|7|19|9|31363|English champions including 1995; major historic FA Cup record
Bolton Wanderers|0|4|0|3|17|8|28018|Four FA Cups and long top-flight football periods
Bristol City|0|0|0|0|14|7|27000|Long-established Football League side with top-flight history
Burnley|2|1|0|3|18|8|21990|Two English top-flight championships and 1914 FA Cup
Cardiff City|0|1|0|1|14|8|33280|1927 FA Cup winners with substantial Welsh football identity
Charlton Athletic|0|1|0|1|15|8|27111|1947 FA Cup winners and historic top-division spells
Lincoln City|0|0|0|0|11|7|10780|Long Football League history and recent upward movement
Middlesbrough|0|0|1|6|17|8|33931|2004 League Cup victory; 2006 UEFA Cup final
Millwall|0|0|0|1|13|9|19369|Long-standing local identity and 2004 FA Cup final
Norwich City|0|0|2|3|16|8|27359|Two League Cups and multiple Premier League/First Division spells
Preston North End|2|2|0|0|19|9|23404|Original Invincibles and founding Football League membership
Queens Park Rangers|0|0|1|3|15|8|18193|1967 League Cup and later top-flight football
Sheffield United|1|4|0|0|18|9|32050|Historic English league champions and four FA Cups
Southampton|0|1|0|4|17|8|32384|1976 FA Cup winners; prolonged top-flight presence
Stoke City|0|0|1|2|18|8|30089|1972 League Cup winners; established First Division/PL history
Swansea City|0|0|1|3|15|8|20996|2013 League Cup winners, later European football and PL spell
Watford|0|0|0|2|15|8|22200|Long Football League history and repeated top-flight spells
West Bromwich Albion|1|5|1|2|19|9|26688|Founding Football League club; title and five FA Cups
Wolverhampton Wanderers|3|4|2|10|19|9|31750|Historic English champions and major FA Cup/League Cup success
Barnsley|0|1|0|0|15|7|23287|1912 FA Cup winners with long Football League continuity
Blackpool|0|1|0|0|16|8|16616|1953 FA Cup winners and historic First Division years
Bromley|0|0|0|0|5|6|5000|Recent English Football League arrival and London club identity
Burton Albion|0|0|0|0|7|6|7088|Modern Football League entry and a spell in the Championship
Cambridge United|0|0|0|0|11|7|8024|Established lower-league presence with historic cup runs
Doncaster Rovers|0|0|0|0|12|7|15148|Long lower-league and Football League record
Huddersfield Town|3|1|0|0|17|8|24329|Three successive English titles in the 1920s and FA Cup win
Leyton Orient|0|0|0|0|13|8|9253|Historic London Football League club with an enduring local identity
Luton Town|0|0|1|0|15|8|10265|1988 League Cup and Premier League return
Mansfield Town|0|0|0|0|11|7|9376|Long-established Football League club
Milton Keynes Dons|0|0|0|0|6|5|30303|Large modern stadium; club founded in modern MK era and continuity disputed
Notts County|0|1|0|0|19|9|19841|1894 FA Cup and foundation-era English Football League heritage
Oxford United|0|0|1|0|12|7|12537|1986 League Cup winners after historic high-tier spell
Peterborough United|0|0|0|0|12|7|13513|Longstanding professional league presence
Plymouth Argyle|0|0|0|0|13|8|17904|Long-standing Football League identity, substantial southwest following
Reading|0|0|0|0|13|7|24376|Long Football League history including recent Premier League period
Stevenage|0|0|0|0|7|6|7426|Modern Football League history and notable cup runs
Stockport County|0|0|0|0|13|7|10800|Historic league club and sustained Football League periods
Wigan Athletic|0|1|0|2|11|8|25133|Won 2013 FA Cup and played in Europa League
Wycombe Wanderers|0|0|0|0|10|7|9558|Non-league to Football League rise and Championship spell
Accrington Stanley|0|0|0|0|7|6|5278|Current club's history is separate from the earlier Accrington Stanley
Barnet|0|0|0|0|8|6|5233|Modern non-league and Football League spells
Bristol Rovers|0|0|0|0|13|7|12500|Established Football League tradition in Bristol
Cheltenham Town|0|0|0|0|9|6|6923|Modern Football League record after 1999 promotion
Chesterfield|0|0|0|0|13|7|10400|Established Football League history with well-known cup runs
Colchester United|0|0|0|0|11|6|10105|Established post-war Football League history
Crawley Town|0|0|0|0|7|6|5907|Recent EFL history from non-league origins
Crewe Alexandra|0|0|0|0|13|7|10109|Extensive Football League record and youth development identity
Exeter City|0|0|0|0|12|7|8714|Long-standing Football League identity in Devon
Fleetwood Town|0|0|0|0|7|6|5137|Re-established modern club rose through the pyramid
Gillingham|0|0|0|0|13|7|11582|Long-standing Football League club in Kent
Newport County|0|0|0|0|11|7|8722|Modern reformed club and predecessors require distinct records
Northampton Town|0|0|0|0|12|7|8203|Long English Football League history
Oldham Athletic|0|0|0|0|15|8|13513|Founding Premier League era and traditional Football League footprint
Port Vale|0|0|0|0|13|7|15036|Long-established Staffordshire Football League club
Rochdale|0|0|0|0|12|6|9507|Lengthy Football League participation
Rotherham United|0|0|0|0|13|7|12088|Long standing EFL history with numerous Championship seasons
Shrewsbury Town|0|0|0|0|12|7|9875|Long professional Football League club with a local fanbase
Swindon Town|0|0|1|0|14|7|15547|1969 League Cup winners; one Premier League campaign
Tranmere Rovers|0|0|0|0|13|7|15012|Established Merseyside Football League club
Walsall|0|0|0|0|12|7|10863|Long-standing West Midlands Football League club
""".strip()


def _club_history_search(name):
    """A SEARCH link only, explicitly NOT a verified club-specific source URL."""
    return "https://en.wikipedia.org/w/index.php?search="+quote(name+" football club honours history")


def _decode_rows():
    output=[]
    for raw in _NEW_ROWS.splitlines():
        parts=raw.split("|")
        if len(parts)!=9:
            raise AssertionError("Invalid full-pyramid data row: "+raw[:80])
        name=parts[0]
        try:
            titles,fa,league_cups,europe,history,identity,capacity=map(int,parts[1:8])
        except ValueError as exc:
            raise AssertionError("Noninteger documented rating input for "+name) from exc
        note=parts[8]
        output.append({
            "name":name,
            "league_titles":titles,
            "fa_cups":fa,
            "league_cups":league_cups,
            "europe":europe,
            "longevity":history,
            "identity":identity,
            "stadium":capacity,
            "heritage":note,
            "rationale":"Provisional cross-club calibration only; editorial history, European and identity bands require scrutiny.",
            "sources":(
                ("historical archive","Football Club History Database index",HISTORY_SOURCE,
                 "Historical seasonal record index. Club-specific page and title totals require human verification."),
                ("honours","FA Cup official historical archive",FA_SOURCE,
                 "FA Cup results and historical wins; club-specific count not yet independently checked."),
                ("honours","EFL Cup finals history",LEAGUE_CUP_SOURCE,
                 "Chronological League Cup title record; club-specific count needs checking."),
                ("stadium","Ground capacities directory",CAPACITY_SOURCE,
                 "Ground-capacity table for the club; current capacity and permitted seats may differ."),
            ),
            "research_url":_club_history_search(name),
            "source_status":"proposed_counts_pending_review",
            "capacity_source":CAPACITY_SOURCE,
            "historical_source":HISTORY_SOURCE,
        })
    return tuple(output)


PROVISIONAL_77=_decode_rows()


def complete_catalogue():
    """Return 92 uniformly scored proposals with audit metadata, never SQL writes."""
    membership={club:league
                for league,(_source,teams) in LEAGUE_MEMBERS.items()
                for club in teams}
    results=[]
    for club in ORIGINAL_15:
        item=dict(club)
        item["source_status"]="original_15_review_only"
        item["research_url"]=_club_history_search(club["name"])
        item["capacity_source"]=CAPACITY_SOURCE
        item["historical_source"]=HISTORY_SOURCE
        results.append(item)
    for club in PROVISIONAL_77:
        item=dict(club)
        item["league"]=membership.get(club["name"])
        if item["league"] is None:
            raise ValueError("Prestige proposal has no 2026/27 English club match: "+item["name"])
        results.append(item)
    results.sort(key=lambda c:(int(c["league"][-1]),-score_club(c)["score"],c["name"]))
    validate_catalogue(results)
    return tuple(results)


def validate_catalogue(rows):
    names=[c["name"] for c in rows]
    membership={club:league
                for league,(_source,teams) in LEAGUE_MEMBERS.items()
                for club in teams}
    if len(rows)!=92 or len(set(names))!=92 or set(names)!=set(membership):
        missing=sorted(set(membership)-set(names))
        extra=sorted(set(names)-set(membership))
        raise AssertionError("Prestige coverage must be exact 92. Missing="+str(missing)+" Extra="+str(extra))
    for c in rows:
        if c["league"]!=membership[c["name"]]:
            raise AssertionError("Prestige club in wrong 2026/27 division: "+c["name"])
        if c["source_status"] not in ("original_15_review_only","proposed_counts_pending_review"):
            raise AssertionError("Missing prominent evidence-review status for "+c["name"])
        if not c.get("capacity_source") or not c.get("research_url"):
            raise AssertionError("Missing traceable source pointer for "+c["name"])
        if c["name"]=="AFC Wimbledon" and (c["fa_cups"],c["league_titles"])!=(0,0):
            raise AssertionError("Do not transfer Wimbledon FC's historic honours to AFC Wimbledon")
        if c["name"]=="Accrington Stanley" and (c["fa_cups"],c["league_titles"])!=(0,0):
            raise AssertionError("Do not transfer original Accrington Stanley honours to successor club")
        score_club(c)
    return True


def review_flags(club, *,score=None,sporting_appeal=None):
    """Explain *why* a proposal deserves manual attention; never silently edit it."""
    if score is None:
        score=score_club(club)["score"]
    issues=[]
    if club["source_status"]=="proposed_counts_pending_review":
        issues.append("Honours counts and editorial bands need source review")
    if sporting_appeal is not None and abs(sporting_appeal-score)>=25:
        issues.append("Sporting-appeal/prestige gap ≥25: check expected, not necessarily an error")
    if club["stadium"]>=30000 and club["longevity"]<=8:
        issues.append("Large stadium with short continuity: check relative institutional standing")
    if club["identity"]>=9 and club["longevity"]<=11:
        issues.append("Media/cultural identity high against short league history")
    if club["europe"]>=8 and club["league_titles"]==0 and club["fa_cups"]==0:
        issues.append("European prestige despite limited major English honours: inspect record")
    if club["name"] in ("Hull City","Wrexham","Grimsby Town"):
        issues.append("Specific calibration boundary: Hull / Wrexham / Grimsby")
    return tuple(issues)


ALL_92=complete_catalogue()

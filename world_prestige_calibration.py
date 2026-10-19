"""Source-linked, REVIEW-ONLY club prestige calibration for 2026/27.

No historical prestige is auto-approved, saved into career ledgers, or
consumed by player/job decisions. These fifteen numerical ratings are game
design PROPOSALS backed by cited historical observations and explicit
editorial bands. Sources substantiate facts; they do not endorse scores.
"""
from math import log1p

VERSION="institutional-prestige-calibration-v2"
DATASET_ID="england-2026-27-fc27"
DIMENSIONS={
    "domestic": ("Major domestic honours",25),
    "europe": ("Continental achievement",15),
    "longevity": ("Historical level and continuity",35),
    "scale": ("Home-ground scale proxy",15),
    "identity": ("Cultural identity and reach",10),
}
STADIUM_SOURCE="https://footballgroundguide.com/news/list-of-england-football-stadium-ordered-by-capacity.html"

# The factual counts below are conservative, dated reference values.
# Existing editorial Europe and longevity INPUT bands remain 0-20 for continuity
# with calibration v1. The v2 scoring method transparently normalises them to
# 0-15 European and 0-35 history points without silently regrading any club.
# Editorial identity is still a subjective 0-10 score.
# No bracket here is a verified fanbase or global visibility measurement.
CLUBS=(
    dict(name="Arsenal",league="ENG1",league_titles=14,fa_cups=14,league_cups=2,
        europe=13,longevity=20,identity=10,stadium=60704,
        heritage="Continuous century-long top-flight presence, 14 league titles and 14 FA Cups; UEFA Cup Winners' Cup winners in 1994.",
        rationale="Historical elite status; a major club even through occasional weaker seasons.",
        sources=(
            ("honours","Arsenal club history and honours","https://www.arsenal.com/history","Club honours include 14 FA Cups and two League Cups."),
            ("longevity","14th top-flight title, 2025/26","https://www.arsenal.com/news/arsenal-crowned-202526-premier-league-champions-aOhcw4T06mFw","Arsenal marked a hundred consecutive seasons in England's top division."),
            ("european","1994 Cup Winners' Cup","https://www.uefa.com/news-media/news/0126-0f84329db58d-9290f97d54c8-1000--1993-94-arsenal-frustrate-parma-s-double-hopes/","Arsenal defeated Parma in the 1994 Cup Winners' Cup final."),
        )),
    dict(name="Aston Villa",league="ENG1",league_titles=7,fa_cups=7,league_cups=5,
        europe=20,longevity=20,identity=9,stadium=42918,
        heritage="Founder-linked Football League history; seven English championships, seven FA Cups, 1982 European Cup and 2026 Europa League.",
        rationale="European champions and a long-established institution; prestige should persist through relegation.",
        sources=(
            ("honours","Aston Villa club timeline","https://www.avfc.co.uk/history/timeline/","Seven domestic top-flight titles and seven FA Cups feature in Villa's timeline."),
            ("european","UEFA: Villa's 1982 European Cup","https://www.uefa.com/uefasupercup/history/1982/","Aston Villa won the 1982 European Cup and subsequent UEFA Super Cup."),
            ("european","UEFA: 2025/26 Europa League","https://www.uefa.com/uefaeuropaleague/news/02a1-1fce257db598-8d600e9b2af4-1000--2025-26-europa-league-meet-the-knockout-phase-teams/","Aston Villa won the 2025/26 Europa League."),
        )),
    dict(name="Nottingham Forest",league="ENG1",league_titles=1,fa_cups=2,league_cups=4,
        europe=20,longevity=16,identity=9,stadium=30404,
        heritage="1978 First Division champions and back-to-back European Cup winners in 1979 and 1980.",
        rationale="Exceptional European heritage raises prestige well above what modern league position alone would imply.",
        sources=(
            ("european","UEFA: 1979 and 1980 European Cups","https://www.uefa.com/uefasupercup/history/1979/","Forest won European Cups in consecutive seasons in 1979 and 1980."),
            ("european","UEFA: retained European Cup","https://www.uefa.com/uefachampionsleague/history/seasons/1979/","Nottingham Forest were 1980 European Cup champions."),
            ("longevity","Nottingham Forest club history","https://www.fchd.info/NOTTINGF.HTM","Forest's historical league record includes long periods in the top division."),
        )),
    dict(name="Hull City",league="ENG1",league_titles=0,fa_cups=0,league_cups=0,
        europe=1,longevity=10,identity=6,stadium=25586,
        heritage="Established Football League history, 2020/21 League One champions, several Premier League spells and FA Cup finalists in 2014. The League One title is acknowledged historically but is not a major domestic honour under this agreed rubric.",
        rationale="Sustained league and top-flight experience influences the historical-continuity component; lower-division titles are not counted again as major silverware.",
        sources=(
            ("honours","Hull City honours archive","https://tigerbase.hullcity.com/tigers-honours.php","Hull's 2014 FA Cup final appearance and 2013/14 top-flight finish are recorded."),
            ("honours","Arsenal's 2014 FA Cup final retrospective","https://www.arsenal.com/feature/when-did-arsenal-win-the-fa-cup-anXj08y0v46j","Hull reached the 2014 FA Cup final against Arsenal."),
            ("longevity","Hull honours and promotion record","https://tigerbase.hullcity.com/tigers-honours.php","The club reached the Premier League through the 2007/08 play-offs and won League One in 2020/21; the lower-tier title is not scored as a major domestic honour."),
            ("european","UEFA: Hull 2014 Europa League debut","https://www.uefa.com/uefaeuropaleague/news/0217-0e8b68714c96-1c88e18aa19c-1000--first-tests-lined-up-for-psv-lyon-and-la-real/","UEFA recorded Hull City as a newcomer in the 2014/15 Europa League qualifying competition."),
        )),
    dict(name="West Ham United",league="ENG2",league_titles=0,fa_cups=3,league_cups=0,
        europe=13,longevity=18,identity=9,stadium=62500,
        heritage="Three FA Cups, 1965 Cup Winners' Cup and 2023 Europa Conference League, with extensive top-flight history.",
        rationale="Significant historic stature despite the hypothetical 2026/27 Championship starting division.",
        sources=(
            ("honours","West Ham official honours","https://www.whufc.com/en/the-club/history/honours-and-records/honours","West Ham won the FA Cup in 1964, 1975 and 1980."),
            ("european","UEFA: 2023 Conference League win","https://www.uefa.com/uefaconferenceleague/news/0282-1833ad184f9c-3bd42a7f4d8e-1000--fiorentina-1-2-west-ham-bowen-arrows-hammers-to-europa-conf/","West Ham won the 2023 Conference League, following their 1965 Cup Winners' Cup success."),
            ("longevity","West Ham honours and records","https://www.whufc.com/en/the-club/history/honours-and-records/honours","Their club record lists decades of national and continental honours."),
        )),
    dict(name="Derby County",league="ENG2",league_titles=2,fa_cups=1,league_cups=0,
        europe=3,longevity=16,identity=8,stadium=33597,
        heritage="English champions in 1972 and 1975, FA Cup winners in 1946, and European Cup semi-finalists.",
        rationale="A substantial historical institution, with ambition and tradition not wholly reflected by present division.",
        sources=(
            ("honours","Derby County official honours","https://www.dcfc.co.uk/page/derby-county-club-honours","Derby won the First Division in 1971/72 and 1974/75, and the FA Cup in 1946."),
            ("european","Derby European Cup heritage","https://www.dcfc.co.uk/page/the-history-of-derby-county","Derby's club history chronicles the Brian Clough championship era."),
            ("longevity","Historical Derby County record","https://www.fchd.info/DERBYCO.HTM","Derby had notable First Division successes and European participation."),
        )),
    dict(name="Portsmouth",league="ENG2",league_titles=2,fa_cups=2,league_cups=0,
        europe=2,longevity=16,identity=8,stadium=20688,
        heritage="Top-flight champions in 1949 and 1950 and FA Cup winners in 1939 and 2008.",
        rationale="Major historical trophies and a traditional club identity; not equivalent to current Championship squad strength.",
        sources=(
            ("honours","Portsmouth honours overview","https://www.theportsmouthnews.com/honours","Portsmouth won two First Division championships and two FA Cups."),
            ("honours","The FA: 2008 Portsmouth FA Cup","https://www.thefa.com/news/2019/nov/30/emirates-fa-cup-second-round-301119","The FA identifies Portsmouth as winners of the 2008 FA Cup."),
            ("european","UEFA: 2008 Portsmouth European debut","https://www.uefa.com/uefaeuropaleague/news/01d3-0e7078855fae-057001917835-1000--milan-qualify-for-next-stage-after-late-show/","Portsmouth played AC Milan during their European debut season."),
        )),
    dict(name="Wrexham",league="ENG2",league_titles=0,fa_cups=0,league_cups=0,
        europe=0,longevity=10,identity=10,stadium=12600,
        heritage="Founded in 1864; three consecutive promotions culminated in reaching the Championship in 2025.",
        rationale="Historic continuity and unusually high modern worldwide recognition, without invented English top-flight trophies.",
        sources=(
            ("longevity","Wrexham club and Racecourse history","https://footballgroundguide.com/leagues/conference/conference-premier/wrexham-afc-racecourse-ground.html","Wrexham have played at the Racecourse since the club's 1864 founding, except a short interval."),
            ("longevity","Welsh Government: three promotions","https://www.wales.com/news/united-kingdom/wrexham-afc-promoted-championship","Three successive promotions took Wrexham to the Championship in 2025."),
            ("support","Racecourse stadium footprint","https://footballgroundguide.com/leagues/conference/conference-premier/wrexham-afc-racecourse-ground.html","The Racecourse has a documented 12,600-capacity listing, subject to redevelopment."),
        )),
    dict(name="Leicester City",league="ENG3",league_titles=1,fa_cups=1,league_cups=3,
        europe=4,longevity=17,identity=9,stadium=32261,
        heritage="Premier League champions in 2016, FA Cup winners in 2021 and three League Cups.",
        rationale="Successful modern honours and strong long-term football identity survive a fall into League One.",
        sources=(
            ("honours","Leicester City's official men's honours","https://www.lcfc.com/history-honours-men","Leicester won the Premier League in 2016, FA Cup in 2021 and three League Cups."),
            ("european","Leicester City European record","https://www.lcfc.com/history-honours-men-european-record","Leicester reached the Champions League last eight in 2016/17."),
            ("longevity","Club history and honours","https://www.lcfc.com/history-honours-men","Leicester have an extensive history across England's top two divisions."),
        )),
    dict(name="Sheffield Wednesday",league="ENG3",league_titles=4,fa_cups=3,league_cups=1,
        europe=0,longevity=18,identity=9,stadium=39859,
        heritage="Four top-flight championships, three FA Cups and the 1991 League Cup.",
        rationale="Strong historical heritage despite periods in lower divisions; prestige shouldn't disappear with relegation.",
        sources=(
            ("honours","Sheffield Wednesday historical honours","https://www.footballhistory.org/club/sheffield-wednesday.html","Wednesday won four top-flight titles and three FA Cups."),
            ("honours","EFL: 1991 League Cup","https://www.efl.com/news/2020/february/the-league-cup-1990-1999","Sheffield Wednesday defeated Manchester United to win the 1991 League Cup."),
            ("longevity","Sheffield Wednesday historical record","https://www.fchd.info/SHEFFIEW.HTM","The historical league archive traces Wednesday's long top-tier history."),
        )),
    dict(name="Bradford City",league="ENG3",league_titles=0,fa_cups=1,league_cups=0,
        europe=0,longevity=12,identity=7,stadium=25136,
        heritage="Bradford City won the 1911 FA Cup; their cup heritage is especially well documented.",
        rationale="Historic cup pedigree and substantial local club identity beyond immediate league standing.",
        sources=(
            ("honours","The FA: Bradford City 1911 winners","https://www.thefa.com/news/2014/nov/28/fa-cup-preview-bradford-v-dartford","Bradford City were the first winners of the redesigned FA Cup in 1911."),
            ("honours","The FA: 1911 cup heritage","https://www.thefa.com/news/2024/oct/11/emirates-fa-cup-first-round-proper-draw-bradford-20242309","The FA describes Bradford City's 1911 triumph as its sole major honour as of 2024."),
            ("longevity","Historic Bradford City seasons","https://www.fchd.info/BRADFORC.HTM","Bradford City have a historical record that includes top-flight football."),
        )),
    dict(name="AFC Wimbledon",league="ENG3",league_titles=0,fa_cups=0,league_cups=0,
        europe=0,longevity=6,identity=9,stadium=9300,
        heritage="Supporter-founded in 2002, returned to the Football League in 2011; its 1988 Wimbledon FC heritage is recognised as identity, not counted as an AFC Wimbledon trophy.",
        rationale="Exceptional supporter identity, but the predecessor club's 1988 FA Cup isn't automatically assigned to AFC Wimbledon.",
        sources=(
            ("longevity","AFC Wimbledon official club story","https://www.afcwimbledon.co.uk/club/","The current supporter-owned club was reformed in 2002; Plough Lane opened in 2020."),
            ("longevity","2011 Football League promotion","https://www.skysports.com/football/news/6943985/afc-wimbledon-earn-promotion","AFC Wimbledon won entry to the Football League through 2011 play-offs."),
            ("identity","AFC Wimbledon official continuity statement","https://www.afcwimbledon.co.uk/club/","The club cites an identity connection to Wimbledon FC's 1988 FA Cup history."),
        )),
    dict(name="Grimsby Town",league="ENG4",league_titles=0,fa_cups=0,league_cups=0,
        europe=0,longevity=12,identity=6,stadium=9546,
        heritage="Substantial Football League history, including a highest-ever fifth-place top-flight finish in 1934/35.",
        rationale="A historically established league club despite the current lower-division environment.",
        sources=(
            ("longevity","Grimsby history: George Tweedy","https://gtfc.co.uk/from-understudy-to-england-international-the-remarkable-story-of-george-tweedy/","Grimsby Town finished fifth in the First Division in 1934/35."),
            ("longevity","Grimsby historical league record","https://www.fchd.info/GRIMSBYT.HTM","Grimsby Town have a long Football League history."),
            ("support","Blundell Park venue profile","https://footballgroundguide.com/leagues/england/league-two/blundell-park-grimsby-town.html","Blundell Park has a capacity listed at 9,546."),
        )),
    dict(name="York City",league="ENG4",league_titles=0,fa_cups=0,league_cups=0,
        europe=0,longevity=9,identity=6,stadium=8005,
        heritage="Long-established Football League club with FA Trophy victories in 2012 and 2017.",
        rationale="Recognisable local heritage and league history without invented major top-flight trophies.",
        sources=(
            ("longevity","York City official club history","https://yorkcityfootballclubstore.co.uk/club-history/","York spent approximately 75 years in the Football League before 2004."),
            ("honours","The FA: York's 2017 FA Trophy","https://www.thefa.com/news/2017/may/21/macclesfield-v-york-report-210517","York won a second FA Trophy in 2017."),
            ("support","York's LNER stadium","https://footballgroundguide.com/leagues/york-city-stadium.html","The LNER Community Stadium is listed with an 8,005 capacity."),
        )),
    dict(name="Salford City",league="ENG4",league_titles=0,fa_cups=0,league_cups=0,
        europe=0,longevity=4,identity=8,stadium=5108,
        heritage="Reached the Football League in 2019 and won the EFL Trophy in 2020, with modern ownership-driven visibility.",
        rationale="A notable emerging club identity, but a relatively short Football League institutional record.",
        sources=(
            ("honours","Salford City club ownership and history","https://www.salfordcityfc.co.uk/news/2024/august/02/gary-neville-acquires-peter-lim-interest-in-salford-city/","The club confirms arrival in the EFL in 2019 and the EFL Trophy in 2020."),
            ("identity","Salford's Class of 92 ownership","https://www.salfordcityfc.co.uk/news/2024/august/02/gary-neville-acquires-peter-lim-interest-in-salford-city/","Salford identifies a prominent former-player ownership group."),
            ("support","Peninsula Stadium venue profile","https://footballgroundguide.com/leagues/england/league-two/salford-city-moor-lane.html","The Peninsula Stadium is listed with a capacity of 5,108."),
        )),
)


def domestic_points(league_titles, fa_cups, league_cups):
    """Explicit, diminishing-return silverware component; no auto-transfer."""
    for value in (league_titles,fa_cups,league_cups):
        if type(value) is not int or value<0:
            raise ValueError("Trophy counts must be nonnegative integers")
    # The reference maxima are calibration anchors, not official possible limits.
    def component(count,maximum,reference):
        return round(maximum*min(1.0,log1p(count)/log1p(reference)))
    return min(25,
        component(league_titles,15,14)+
        component(fa_cups,8,14)+
        component(league_cups,2,5))


def stadium_points(capacity):
    """Venue capacity is a weak, openly labelled SIZE proxy, not attendance."""
    if type(capacity) is not int or capacity<=0:
        raise ValueError("Documented positive venue capacity required")
    return (15 if capacity>=60000 else
            13 if capacity>=40000 else
            11 if capacity>=30000 else
            9 if capacity>=20000 else
            7 if capacity>=10000 else
            5 if capacity>=5000 else 3)


def score_club(club):
    # Historical editorial inputs are frozen at their original v1 bands so
    # changes in v2 arise *only* from user-approved weighting changes.
    for field,maximum in (("europe",20),("longevity",20),("identity",10)):
        value=club[field]
        if type(value) is not int or not 0<=value<=maximum:
            raise ValueError("Editorial band outside rubric: "+field)
    sub={
        "domestic":domestic_points(club["league_titles"],club["fa_cups"],club["league_cups"]),
        "europe":round(club["europe"]*15/20),
        "longevity":round(club["longevity"]*35/20),
        "scale":stadium_points(club["stadium"]),
        "identity":club["identity"],
    }
    score=sum(sub.values())
    if not 0<=score<=100:
        raise AssertionError("Prestige score outside 0-100")
    return {**sub,"score":score}


def check_calibration():
    names=set()
    counts={}
    for c in CLUBS:
        if c["name"] in names:raise AssertionError("Duplicate prestige club")
        names.add(c["name"])
        if c["league"] not in ("ENG1","ENG2","ENG3","ENG4"):
            raise AssertionError("Unknown starting league")
        counts[c["league"]]=counts.get(c["league"],0)+1
        if len(c["sources"])<2:
            raise AssertionError("Insufficient cited historical data: "+c["name"])
        for category,title,url,claim in c["sources"]:
            if not url.startswith("https://") or not claim or not title:
                raise AssertionError("Missing readable citation: "+c["name"])
        score_club(c)
    if counts!={"ENG1":4,"ENG2":4,"ENG3":4,"ENG4":3}:
        raise AssertionError("Need 15 representative clubs across the four divisions")
    return True


check_calibration()

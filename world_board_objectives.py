"""Expectation-relative, auditable board objectives for PES career sandboxes.

A pre-season strength ranking is a PROXY, not an actual predicted finish.
Set/lock it explicitly for a career season. Promotions/relegations contribute
only as small contextual adjustments; league under/over-performance dominates.
No standings, results or managerial achievements are inferred.
"""
OBJECTIVES_VERSION = "board-objectives-v1"
TIERS = ("exceptional","above","met","below","severe")


def _rank(name,value,size):
    if type(value) is not int or not 1<=value<=size:
        raise ValueError(name+" must be between 1 and division size")


def objective_band(*, expected_rank, league_size):
    _rank("Expected rank",expected_rank,league_size)
    return (max(1,expected_rank-2),min(league_size,expected_rank+2))


def evaluate_objective(*,expected_rank,actual_rank,league_size,
                       expected_relegation=None,promoted=False,relegated=False,
                       cup_result="not_assessed"):
    """Review a verified finish against locked initial expectations.

    The band gives a modest buffer for noise. League rank differences are
    scaled by the number of places to avoid over-rewarding favourites.
    Relegation and promotion are never free +20/-22 event awards.
    """
    if type(league_size) is not int or not 10<=league_size<=30:
        raise ValueError("Division size must be between 10 and 30")
    _rank("Expected rank",expected_rank,league_size)
    _rank("Actual rank",actual_rank,league_size)
    if expected_relegation is not None and type(expected_relegation) is not bool:
        raise ValueError("Expected relegation must be true/false/unknown")
    if type(promoted) is not bool or type(relegated) is not bool or (promoted and relegated):
        raise ValueError("Invalid promotion/relegation outcome")
    if cup_result not in ("not_assessed","expected","above","below"):
        raise ValueError("Unrecognised cup result")
    best,worst=objective_band(expected_rank=expected_rank,league_size=league_size)
    # Headline point changes reflect the size of the actual relative outperformance.
    improvement=expected_rank-actual_rank
    if actual_rank<best:
        grade="exceptional" if improvement>=7 else "above"
        league_delta=min(18,4+2*(best-actual_rank))
    elif actual_rank>worst:
        grade="severe" if -improvement>=7 else "below"
        league_delta=max(-18,-4-2*(actual_rank-worst))
    else:
        grade="met"
        league_delta=2 if improvement>=0 else 0

    # Promotion gets only a small *incremental* reward when it was not
    # an expected result; most recognition is already in league performance.
    promotion_bonus=0
    if promoted and expected_rank>2:
        promotion_bonus=2
    # Relegation is not a second large penalty when a team was projected to
    # be relegated. If survival was projected, a small extra accountability cost.
    relegation_penalty=0
    if relegated and expected_relegation is False:
        relegation_penalty=-2
    cup_delta={"not_assessed":0,"expected":0,"above":2,"below":-2}[cup_result]
    total=max(-20,min(20,league_delta+promotion_bonus+relegation_penalty+cup_delta))
    return {
        "version":OBJECTIVES_VERSION,"expected_rank":expected_rank,
        "actual_rank":actual_rank,"league_size":league_size,
        "expected_band":[best,worst],"places_above_expectation":improvement,
        "grade":grade,"league_delta":league_delta,"promotion_delta":promotion_bonus,
        "relegation_delta":relegation_penalty,"cup_delta":cup_delta,
        "confidence_delta":total,
        "reason":f"Finished {actual_rank} of {league_size} against locked pre-season strength proxy {expected_rank} (objective band {best}–{worst}).",
    }


def proxy_rankings(*,clubs):
    """Return proxy positions only if EVERY club has a unique ID and strength.

    This avoids fabricating strength for clubs lacking usable ratings.
    Equal strengths share a proxy rank; alphabetical IDs break order only.
    """
    if not clubs or not 10<=len(clubs)<=30:
        return None
    ids=[c["club_id"] for c in clubs]
    if len(set(ids))!=len(ids):
        raise ValueError("Duplicate clubs in division")
    if any(type(c["strength"]) not in (int,float) for c in clubs):
        return None
    ordered=sorted(clubs,key=lambda x:(-x["strength"],x["club_id"]))
    ranks={}
    for i,entry in enumerate(ordered):
        ranks[entry["club_id"]]=1+sum(c["strength"]>entry["strength"] for c in ordered)
    return ranks

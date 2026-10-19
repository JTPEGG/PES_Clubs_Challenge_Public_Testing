"""Immutable relative squad-strength baselines for a career's league.

The league rank is NOT a betting forecast or guaranteed final position:
it is a transparent ordering of the top-16 rated players per club from the
saved source snapshot. Incomplete league coverage disables auto objectives.
"""
from world_reputation_v2 import MODEL_VERSION as STRENGTH_MODEL, MIN_RATED_PLAYERS
from world_board_objectives import proxy_rankings, objective_band

STRENGTH_OBJECTIVE_VERSION = "squad-strength-baseline-v1"


def strength_baseline(conn, *, career_id, club_id):
    career=conn.execute("""SELECT dataset_id,manager_club_id FROM world_career_saves
        WHERE career_id=? AND state='sandbox'""",(career_id,)).fetchone()
    if not career or career[1]!=club_id:
        raise ValueError("The managed club must belong to an active sandbox career")
    team=conn.execute("""SELECT e.competition_id,c.tier,d.source_date
        FROM world_dataset_entries e
        JOIN world_competitions c ON c.competition_id=e.competition_id
        JOIN world_datasets d ON d.dataset_id=e.dataset_id
        WHERE e.dataset_id=? AND e.club_id=?""",(career[0],club_id)).fetchone()
    if not team:
        raise ValueError("Managed club has no source competition")
    rows=conn.execute("""SELECT e.club_id,c.name,p.squad_average,p.sample_players,
        p.roster_players,p.confidence
        FROM world_dataset_entries e
        JOIN world_clubs c ON c.club_id=e.club_id
        LEFT JOIN world_pyramid_club_appeal p
          ON p.dataset_id=e.dataset_id AND p.club_id=e.club_id
          AND p.model_version=?
        WHERE e.dataset_id=? AND e.competition_id=? ORDER BY c.name""",
        (STRENGTH_MODEL,career[0],team[0])).fetchall()
    total=len(rows)
    if not 10<=total<=30:
        return {"available":False,"reason":"Division size is not supported.",
                "rank":None,"clubs":[],"league_size":total}
    data=[{"club_id":r[0],"name":r[1],"strength":r[2],
           "sample_players":r[3],"roster_players":r[4],
           "rating_confidence":r[5]} for r in rows]
    missing=[t["name"] for t in data
             if t["strength"] is None or
             t["sample_players"] is None or
             t["sample_players"]<MIN_RATED_PLAYERS]
    if missing:
        return {"available":False,"reason":
            f"Insufficient rated top-16 player samples for {len(missing)} of {total} clubs.",
            "missing_clubs":missing,"rank":None,"clubs":data,"league_size":total}
    ranks=proxy_rankings(clubs=data)
    if not ranks or club_id not in ranks:
        return {"available":False,"reason":"A complete relative league ranking could not be established.",
                "rank":None,"clubs":data,"league_size":total}
    ordered=sorted(data,key=lambda c:(-c["strength"],c["name"],c["club_id"]))
    for c in ordered:
        c["rank"]=ranks[c["club_id"]]
        c["strength"]=round(c["strength"],2)
    ranking=ranks[club_id]
    upper,lower=objective_band(expected_rank=ranking,league_size=total)
    # Premier League bottom three is a transparent *squad-strength expectation
    # proxy*. Other league relegation boundaries need distinct competition rules.
    expected_relegation=(ranking>total-3) if team[1]==1 else None
    return {
        "available":True,"career_id":career_id,"club_id":club_id,
        "dataset_id":career[0],"source_date":team[2],
        "competition_id":team[0],"model_version":STRENGTH_OBJECTIVE_VERSION,
        "underlying_strength_version":STRENGTH_MODEL,
        "method":f"Relative rank by mean OVR of top 16 source-rated players; at least {MIN_RATED_PLAYERS} required per club.",
        "rank":ranking,"league_size":total,"band":[upper,lower],
        "expected_relegation":expected_relegation,
        "clubs":ordered,
        "note":"A squad-strength baseline, not a forecast from real results or club reputation.",
    }

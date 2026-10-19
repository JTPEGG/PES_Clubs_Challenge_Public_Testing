"""Long-term recruitment for PES career AI clubs.

This is an independent football-manager-inspired model, NOT Football Manager
source code or a claim about a real player's potential. Proven/authorised
projection inputs take priority; otherwise strong current ability relative
to same-age, same-position players is a scouting SIGNAL, not a PA forecast.
"""
from collections import defaultdict
from datetime import date
from world_squad_planner import lane_of

VERSION = "club-development-recruitment-v1"
MAX_PROSPECTS_PER_WINDOW = 1
PROSPECT_BUDGET_SHARE = 0.20
MAX_PROSPECT_AGE = 22
MIN_PEERS = 8

def age_on(birth_date, as_of):
    """Date-aware age; historical saves are measured at their own snapshot."""
    if not birth_date or not as_of:
        return None
    try:
        birth=date.fromisoformat(birth_date)
        today=date.fromisoformat(as_of)
    except (TypeError,ValueError):
        return None
    age=today.year-birth.year-((today.month,today.day)<(birth.month,birth.day))
    return age if 0<=age<=120 else None

def development_signals(conn, *, dataset):
    """Build contextual scouting evidence once per market assessment."""
    row=conn.execute("SELECT source_date FROM world_datasets WHERE dataset_id=?",
                     (dataset,)).fetchone()
    as_of=row[0] if row else None
    rated=conn.execute("""SELECT p.player_id,p.birth_date,p.primary_position,
        r.overall FROM world_dataset_ratings r
        JOIN world_players p ON p.player_id=r.player_id
        WHERE r.dataset_id=? AND r.overall BETWEEN 1 AND 99""",
        (dataset,)).fetchall()
    cohorts=defaultdict(list)
    players={}
    for pid,birth,pos,overall in rated:
        lane=lane_of(pos)
        age=age_on(birth,as_of)
        if not lane or age is None or not 16<=age<=MAX_PROSPECT_AGE:
            continue
        cohorts[lane].append((age,int(overall)))
        players[pid]=(age,lane,int(overall))
    # This table exists only for legitimately imported historical enrichment.
    # "potential_overall" must be a calibrated 1-99 PES-compatible score,
    # NOT FM's raw 1-200 potential ability: those are distinct scales.
    explicit={}
    schema=conn.execute("""SELECT 1 FROM sqlite_master
        WHERE type='table' AND name='world_dataset_extended_attributes'""").fetchone()
    if schema:
        explicit={pid:value for pid,value in conn.execute(
            """SELECT player_id,value FROM world_dataset_extended_attributes
            WHERE dataset_id=? AND attribute='potential_overall'
              AND value BETWEEN 1 AND 99""",(dataset,)).fetchall()}
    return {"players":players,"cohorts":cohorts,
            "calibrated_potential":explicit,"source_date":as_of}

def prospect_fit(squads, *, buyer, player_id, overall, position,
                 signals, existing_prospects=0):
    """Distinguish a youth investment from a claimed starting-XI improvement.

    A high same-age percentile is evidence of high *current* achievement;
    it is not a prediction of future growth. Source-backed PES-scale potential
    can be used when separately supplied with provenance.
    """
    slot=lane_of(position)
    youth=signals["players"].get(player_id)
    if not slot or youth is None or youth[1]!=slot or youth[2]!=overall:
        return {"eligible":False,"reason":"No supported age and position evidence"}
    if existing_prospects>=MAX_PROSPECTS_PER_WINDOW:
        return {"eligible":False,"reason":"Development signing limit reached"}
    roster=squads.get(buyer,{})
    all_ratings=sorted((p[1] for group in roster.values() for p in group),
                       reverse=True)
    if len(all_ratings)<8:
        return {"eligible":False,"reason":"Insufficient buyer squad evidence"}
    # Never purchase a very weak player on hypothetical 15-point growth.
    senior_baseline=all_ratings[min(10,len(all_ratings)-1)]
    if overall<senior_baseline-13:
        return {"eligible":False,"reason":"Not a credible future first-team candidate"}
    # No more than two same-lane prospects in the buyer's current projection.
    # Buyers can still recruit adult depth through recruitment_fit().
    colleagues=roster.get(slot,[])
    existing_high_potential=sum(
        1 for pid,rating,_ in colleagues
        if pid in signals["players"] and
        signals["players"][pid][0]<=MAX_PROSPECT_AGE)
    if existing_high_potential>=2:
        return {"eligible":False,"reason":"Development depth already exists here"}
    age,_,_=youth
    known=signals["calibrated_potential"].get(player_id)
    if known is not None:
        if known<max(overall+4,senior_baseline-2):
            return {"eligible":False,"reason":"Source projection lacks a credible ceiling"}
        evidence="source-calibrated potential, not present OVR"
        percent=None
        score=67+min(10,(known-overall)//2)
    else:
        all_peers=signals["cohorts"].get(slot,[])
        same_age=[rating for peer_age,rating in all_peers
                  if abs(peer_age-age)<=2]
        if len(same_age)<MIN_PEERS:
            same_age=[rating for peer_age,rating in all_peers
                      if abs(peer_age-age)<=3]
        if len(same_age)<MIN_PEERS:
            return {"eligible":False,"reason":"Insufficient age-cohort scouting sample"}
        percent=sum(r<=overall for r in same_age)/len(same_age)
        if percent<0.88:
            return {"eligible":False,"reason":"Youth is not among the strongest age peers"}
        evidence="age-relative present rating; future ability unknown"
        score=58+round((percent-.88)*70)+max(0,20-age)
    return {"eligible":True,"score":min(80,score),
            "category":"prospect","lane":slot,"age":age,
            "cohort_percentile":None if percent is None else round(percent,3),
            "evidence":evidence,
            "reason":"Long-term development investment, not immediate starter upgrade"}

def prospect_fee_cap(*, initial_transfer_budget, available_budget):
    """Prospect expenditure never consumes the club's entire recruitment pot."""
    if (type(initial_transfer_budget) is not int or
            type(available_budget) is not int or
            initial_transfer_budget<0 or available_budget<0):
        raise ValueError("Invalid club budget")
    return min(available_budget,int(initial_transfer_budget*PROSPECT_BUDGET_SHARE))

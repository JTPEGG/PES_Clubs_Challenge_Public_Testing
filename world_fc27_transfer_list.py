"""Autonomous FC27 transfer-list decisions for the in-game market.

Scored from source contracts, positional depth and modelled club financial pressure.
These flags are a seller's willingness to invite bids; a sale is not guaranteed,
and every subsequent fee / sporting / replacement decision remains autonomous.
"""
from collections import defaultdict
from datetime import date
from world_squad_planner import lane_of

def listing_score(*,position_depth,overall,age,years_left,financial_pressure):
    """Continuous evidence score; no cap on the number of listed players."""
    depth=max(0,int(position_depth))
    pressure=max(0,min(100,int(financial_pressure or 0)))
    # Depth is a signal, not a fixed listing quota or transfer permission.
    score=min(0.52,max(0,depth-1)*0.17)
    if years_left is not None:
        score+=max(0,2.3-float(years_left))*0.18
    if age is not None and age>=28:
        score+=min(0.15,(age-27)*0.025)
    score+=pressure/100*0.24
    if overall>=85 and depth<=1:score-=0.55
    elif depth==0:score-=0.32
    return score

def modelled_ai_listed_ids(conn,*,career_id,dataset,manager,rows,asof):
    if dataset!="fc27-warehouse-659-mens-2026-27":return set()
    current=date.fromisoformat(asof)
    pressures={}
    if conn.execute("""SELECT 1 FROM sqlite_master WHERE type='table'
        AND name='world_fc27_club_ai_context'""").fetchone():
        pressures=dict(conn.execute("""SELECT club_id,financial_pressure_index
            FROM world_fc27_club_ai_context WHERE dataset_id=?""",
            (dataset,)).fetchall())
    depth=defaultdict(int)
    eligible=set()
    for row in rows:
        club=row["club_id"]
        if club is None or club==manager:continue
        pid=row["player_id"]
        lane=lane_of(row["primary_position"]) or row["primary_position"]
        key=(club,lane)
        rank=depth[key]
        depth[key]+=1
        expiry=row["expires"]
        try:
            years_left=(date.fromisoformat(expiry)-current).days/365.25 if expiry else None
        except ValueError:
            years_left=None
        birth=row["birth_date"]
        try:
            birthday=date.fromisoformat(birth)
            age=current.year-birthday.year-((current.month,current.day)<(birthday.month,birthday.day))
        except (TypeError,ValueError):
            age=None
        if listing_score(position_depth=rank,overall=row["overall"],
            age=age,years_left=years_left,
            financial_pressure=pressures.get(club,0))>=0.54:
            eligible.add(pid)
    return eligible

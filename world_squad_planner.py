"""Projected club recruitment plans for the PES pre-season transfer window.

All decisions use source-rated players in THIS career plus genuinely agreed
future transfers. They never infer PES results or change gameplay attributes.
The projected roster is rebuilt after each agreement, not cached at window start.
"""
from collections import defaultdict

PLANNER_VERSION = "projected-squad-planner-v1"

LANES = {
    "GK": "GK", "GOALKEEPER": "GK",
    "CB": "CB", "SW": "CB", "CENTREBACK": "CB",
    "LB": "LB", "RB": "RB", "LWB": "LB", "RWB": "RB", "FULLBACK": "FB",
    "DM": "DM", "DMF": "DM", "CDM": "DM",
    "CM": "CM", "CMF": "CM",
    "AM": "AM", "AMF": "AM", "CAM": "AM",
    "LM": "LW", "LMF": "LW", "RM": "RW", "RMF": "RW",
    "LW": "LW", "RW": "RW", "LWF": "LW", "RWF": "RW",
    "CF": "ST", "ST": "ST", "SS": "ST", "STRIKER": "ST",
}
FAMILY = {"GK":"GK", "CB":"DEF", "LB":"DEF", "RB":"DEF", "FB":"DEF",
          "DM":"MID", "CM":"MID", "AM":"MID",
          "LW":"FWD", "RW":"FWD", "ST":"FWD"}
STARTERS = {"GK":1,"CB":2,"LB":1,"RB":1,"FB":1,
            "DM":1,"CM":2,"AM":1,"LW":1,"RW":1,"ST":1}
# Conservative minimum viable positional coverage after a departure.
# A deficit cannot be cured with unrelated players from the same broad family.
MIN_COVER = {"GK":2,"CB":3,"LB":1,"RB":1,"FB":1,
             "DM":1,"CM":2,"AM":0,"LW":1,"RW":1,"ST":1}


def lane_of(position):
    code = str(position or "").upper().replace(" ", "").replace("-", "")
    return LANES.get(code)


def projected_squads(conn, *, career_id, dataset):
    """{club: {lane: [(player_id, overall, position), ...]}}.

    The source registrations stay immutable during the 30-minute window.
    Only signed agreed_future transfers alter the projected owner. Undecided
    bids and merely accepted fees never change the plan.
    """
    registrations = conn.execute("""SELECT r.player_id,r.club_id,x.overall,
        p.primary_position FROM world_career_registrations r
        JOIN world_dataset_ratings x ON x.dataset_id=? AND x.player_id=r.player_id
        JOIN world_players p ON p.player_id=r.player_id
        WHERE r.career_id=? AND x.overall BETWEEN 1 AND 99
        ORDER BY r.club_id,r.player_id""", (dataset,career_id)).fetchall()
    owners = {pid:club for pid,club,_overall,_pos in registrations}
    moves = conn.execute("""SELECT player_id,selling_club_id,buying_club_id
        FROM world_career_offers WHERE career_id=? AND status='agreed_future'
        ORDER BY offer_id""",(career_id,)).fetchall()
    seen=set()
    for pid,seller,buyer in moves:
        if pid in seen:
            raise ValueError("Conflicting signed transfers for the same player")
        seen.add(pid)
        if owners.get(pid)!=seller:
            raise ValueError("Projected transfer seller does not match registration")
        owners[pid]=buyer
    squads=defaultdict(lambda:defaultdict(list))
    for pid,_original,overall,pos in registrations:
        lane=lane_of(pos)
        if lane:
            squads[owners[pid]][lane].append((pid,int(overall),pos))
    for roster in squads.values():
        for players in roster.values():
            players.sort(key=lambda x:(-x[1],x[0]))
    return squads


def recruitment_fit(squads, *, buyer, position, overall):
    """Evaluate actual starter upgrade and depth need, not third-best DEF/FWD.

    Lack of verified potential prevents labelling an inferior target as a
    wonderkid. Such targets can be recruited later with a licensed potential
    signal, but not by an ungrounded 'young and promising' guess.
    """
    slot=lane_of(position)
    if not slot or not 1<=overall<=99:
        return {"eligible":False,"score":0,"reason":"Unknown position or rating"}
    roster=squads.get(buyer,{})
    peers=roster.get(slot,[])
    all_ratings=sorted((entry[1] for group in roster.values()
                        for entry in group),reverse=True)
    if not all_ratings:
        return {"eligible":False,"score":0,"reason":"No rated buyer squad"}
    starter_n=STARTERS[slot]
    baseline=peers[min(starter_n-1,len(peers)-1)][1] if peers else None
    team_baseline=all_ratings[min(10,len(all_ratings)-1)]
    thin=len(peers)<max(MIN_COVER[slot],STARTERS[slot])
    # First-team upgrades require meaningful improvement to the actual
    # starter; an 83-rated attacker is not a first-team upgrade to a 90+ XI.
    improvement=(overall-baseline) if baseline is not None else 0
    # Missing a usable starter is an urgent need, not a demand to
    # obtain the replacement BEFORE selling the previous player.
    credible_depth=thin and overall>=team_baseline-8
    credible_upgrade=(baseline is not None and improvement>=3 and
                      overall>=team_baseline-3)
    if not (credible_depth or credible_upgrade):
        return {"eligible":False,"score":0,"lane":slot,
                "reason":"Not a credible starter upgrade or necessary depth"}
    score=min(98,max(50,52+max(0,improvement)*5+
                     (20 if credible_depth else 0)+
                     (8 if credible_upgrade else 0)))
    return {"eligible":True,"score":score,"lane":slot,
            "upgrade":improvement,"depth_shortage":thin,
            "reason":("Required positional cover" if credible_depth else
                      "Meaningful first-team positional upgrade")}



def sale_profile(squads, *, seller, player_id, position, overall):
    """Describe sporting consequences; never veto a transfer by itself.

    Surplus is not a vacancy. A genuine replacement search can BEGIN after
    selling, and external seller/board/player decisions determine consent.
    This must assess actual specialist positions, not pooled DEF/MID/FWD.
    """
    slot=lane_of(position)
    if not slot:
        return {"valid":False,"reason":"Unknown specialist position"}
    peers=squads.get(seller,{}).get(slot,[])
    selected=[p for p in peers if p[0]==player_id]
    if len(selected)!=1:
        return {"valid":False,"reason":"Player not on projected seller squad"}
    remaining=[p for p in peers if p[0]!=player_id]
    starter_n=STARTERS[slot]
    required=max(starter_n,MIN_COVER[slot])
    rank=next(i for i,p in enumerate(peers) if p[0]==player_id)
    before=peers[min(starter_n-1,len(peers)-1)][1]
    after=(remaining[min(starter_n-1,len(remaining)-1)][1]
           if remaining else None)
    starter_drop=max(0,before-after) if after is not None else before
    is_first_choice=rank<starter_n
    cover_breach=len(remaining)<required
    material_drop=is_first_choice and starter_drop>4
    needs_recruitment=cover_breach or material_drop
    return {
        "valid":True,"lane":slot,"rank":rank,"first_choice":is_first_choice,
        "before_depth":len(peers),"after_depth":len(remaining),
        "before_starter_floor":before,"after_starter_floor":after,
        "starter_rating_drop":starter_drop,"below_target_cover":cover_breach,
        "replacement_priority":("urgent" if cover_breach else
                                "improve_starter" if material_drop else "none"),
        "requires_recruitment":needs_recruitment,
        "surplus_sale":not needs_recruitment and not is_first_choice,
        "reason":("Club can sell from existing positional surplus" if
                  not needs_recruitment and not is_first_choice else
                  "Sale is viable without a pre-agreed replacement but needs follow-up"
                  if needs_recruitment else
                  "Projected specialist starting standard remains acceptable"),
    }


def departure_guard(squads, *, seller, player_id, position, overall):
    """Block avoidable destruction of a starting XI or specialist position.

    Exceptional financial/board sales require a separate explicit board
    decision and replacement policy, not a loophole in this guard.
    """
    slot=lane_of(position)
    if not slot:
        return {"allowed":False,"reason":"Unknown specialist position"}
    roster=squads.get(seller,{})
    peers=roster.get(slot,[])
    remaining=[p for p in peers if p[0]!=player_id]
    if len(remaining)==len(peers):
        return {"allowed":False,"reason":"Player not in projected seller squad"}
    if len(remaining)<MIN_COVER[slot]:
        return {"allowed":False,"reason":"Departure would create a positional shortage"}
    if not remaining:
        return {"allowed":False,
                "reason":"Departure would leave no player in this specialist position"}
    starter_n=STARTERS[slot]
    rank=next(i for i,p in enumerate(peers) if p[0]==player_id)
    if rank<starter_n:
        # Do not sell the best specialist and pretend an unrelated full-back
        # replaces a centre-back. Comparable signed arrivals already appear.
        replacement=remaining[min(starter_n-1,len(remaining)-1)][1]
        if overall-replacement>5:
            return {"allowed":False,
                    "reason":"Starter departure lacks a comparable signed replacement"}
    return {"allowed":True,"reason":"Projected positional cover retained"}

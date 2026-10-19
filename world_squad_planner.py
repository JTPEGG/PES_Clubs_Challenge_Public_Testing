"""Projected club recruitment plans for the PES pre-season transfer window.

All decisions use source-rated players in THIS career plus genuinely agreed
future transfers. They never infer PES results or change gameplay attributes.
The projected roster is rebuilt after each agreement, not cached at window start.
"""
from collections import defaultdict
import sqlite3

# User-verified secondary eligibility in this provisional 2026/27 dataset.
# These are NOT present in the FC27 primary-position source. Do not infer
# secondary positions from the broad DEF/MID/FWD group.
EXPLICIT_SECONDARIES = {
    "england-2026-27-fc27": {
        "231936": {"CB": "User-confirmed Ben White centre-back cover, 19 Oct 2026"},
    },
}

class ProjectedSquads(defaultdict):
    """Original primary-position roster plus nonduplicating secondary cover."""
    def __init__(self):
        super().__init__(lambda: defaultdict(list))
        self.secondary = {}

def effective_cover(squads, club, lane, exclude_player=None):
    """Credible options at one position, counting each person once.

    An eligible second-position player counts as rotation cover only when
    enough other starters remain in their *primary* position. This avoids
    describing the same footballer as two simultaneous starters.
    """
    roster=squads.get(club,{})
    options={p[0]: p for p in roster.get(lane,())
             if p[0]!=exclude_player}
    evidence=getattr(squads,"secondary",{})
    for origin,primary_players in roster.items():
        if origin==lane:
            continue
        for pid,ovr,pos in primary_players:
            if pid==exclude_player or pid in options:
                continue
            if lane not in evidence.get(pid,{}):
                continue
            other_starters=sum(
                1 for p in primary_players
                if p[0] not in (pid,exclude_player))
            if other_starters<STARTERS.get(origin,1):
                continue
            options[pid]=(pid,ovr,pos)
    return sorted(options.values(),key=lambda p:(-p[1],p[0]))


def squad_standard(roster):
    """Rated standard of the best XI, without double-counting secondary roles."""
    rated=sorted((p[1] for players in roster.values()
                  for p in players),reverse=True)
    return sum(rated[:11])/min(len(rated),11) if rated else 0


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
    squads=ProjectedSquads()
    for pid,_original,overall,pos in registrations:
        lane=lane_of(pos)
        if lane:
            squads[owners[pid]][lane].append((pid,int(overall),pos))
    # Resolve the explicit user-supplied eligibility through stable EA IDs,
    # never name similarity. Imported historic datasets have no implied cover.
    ids=EXPLICIT_SECONDARIES.get(dataset,{})
    if ids:
        try:
            rows=conn.execute("""SELECT player_id,external_id
                FROM world_player_source_refs
                WHERE source_name='EAFC27'""").fetchall()
            squads.secondary={
                int(pid):ids[str(ea_id)] for pid,ea_id in rows
                if str(ea_id) in ids}
        except sqlite3.OperationalError:
            # Minimal synthetic planner fixtures may omit source-ref tables.
            squads.secondary={}
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
    peers=effective_cover(squads,buyer,slot)
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
    """Sporting cost of selling, considering genuine secondary positions.

    No advance signing is REQUIRED. Elite rotation quality is protected via a
    higher hurdle for *routine* sales, with separate seller, board, contract
    and player-pressure exceptions. The next agreed sale is always rechecked
    against the projected roster (previous sales have already been removed).
    """
    slot=lane_of(position)
    if slot is None:
        return {"valid":False,"reason":"Unknown specialist position"}
    roster=squads.get(seller,{})
    peers=roster.get(slot,[])
    selected=[p for p in peers if p[0]==player_id]
    if len(selected)!=1:
        return {"valid":False,"reason":"Player not in projected seller squad"}
    rank=next(i for i,p in enumerate(peers) if p[0]==player_id)
    # A club with an elite first-choice core stays subject to elite
    # expectations after selling a reserve. Using only the current top-XI
    # average could lower the bar immediately after a damaging sale.
    rated=sorted((p[1] for players in roster.values()
                  for p in players),reverse=True)
    strongest_eight=(sum(rated[:8])/len(rated[:8]) - 1
                     if rated else 0)
    quality=max(squad_standard(roster),strongest_eight)
    eligible=getattr(squads,"secondary",{}).get(player_id,{})
    affected={slot,*eligible}
    reports=[]
    for lane in sorted(affected):
        before=effective_cover(squads,seller,lane)
        after=effective_cover(squads,seller,lane,exclude_player=player_id)
        n=STARTERS[lane]
        minimum=max(n,MIN_COVER[lane])
        old_floor=before[min(n-1,len(before)-1)][1] if before else None
        new_floor=after[min(n-1,len(after)-1)][1] if after else None
        # First two rotation places, not just the strongest starters.
        old_backup=[p[1] for p in before[n:n+2]]
        new_backup=[p[1] for p in after[n:n+2]]
        first_backup_drop=sum(
            max(0,old_backup[i]-(new_backup[i] if i<len(new_backup) else 0))
            for i in range(len(old_backup)))
        starter_drop=max(0,(old_floor or 0)-(new_floor or 0))
        short=len(after)<minimum
        reports.append({
            "lane":lane,"before_depth":len(before),"after_depth":len(after),
            "starter_rating_drop":starter_drop,
            "backup_quality_drop":first_backup_drop,
            "depth_shortage":short,
            "recruitment_needed":short or starter_drop>=4 or
                                first_backup_drop>=4,
        })
    seriousness=max((r["starter_rating_drop"]*2+
                     r["backup_quality_drop"]+
                     (15 if r["depth_shortage"] else 0)
                     for r in reports),default=0)
    # Strong clubs ought to retain *competition-quality* reserves instead of
    # preserving only their top two starters and replacing depth with 70s.
    # This only makes a routine sale harder; does not bar genuine exceptions.
    protected_rotation=quality>=82 and any(
        r["backup_quality_drop"]>=4 or r["starter_rating_drop"]>=4
        for r in reports)
    needs=any(r["recruitment_needed"] for r in reports)
    main=next(r for r in reports if r["lane"]==slot)
    return {
        "valid":True,"lane":slot,"rank":rank,
        "first_choice":rank<STARTERS[slot],
        "before_depth":main["before_depth"],
        "after_depth":main["after_depth"],
        "starter_rating_drop":main["starter_rating_drop"],
        "backup_quality_drop":main["backup_quality_drop"],
        "below_target_cover":main["depth_shortage"],
        "replacement_priority":("urgent" if any(r["depth_shortage"] for r in reports)
           else "improve_rotation" if protected_rotation
           else "improve_starter" if needs else "none"),
        "requires_recruitment":needs,
        "surplus_sale":not needs and rank>=STARTERS[slot],
        "protected_rotation":protected_rotation,
        "sporting_risk":seriousness,
        "affected_positions":reports,
        "source_standard_top11":round(quality,2),
        "reason":("Routine sale would materially weaken elite rotation"
            if protected_rotation else "Sale creates follow-up recruitment need"
            if needs else "Existing squad cover permits sale"),
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

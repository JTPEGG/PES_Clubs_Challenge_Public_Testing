"""Projected club recruitment plans for the PES pre-season transfer window.

All decisions use source-rated players in THIS career plus genuinely agreed
future transfers. They never infer PES results or change gameplay attributes.
The projected roster is rebuilt after each agreement, not cached at window start.
"""
from collections import defaultdict
import sqlite3

# User-verified alternative-position eligibility in this provisional 2026/27 dataset.
# These are NOT present in the FC27 primary-position source. Do not infer
# alternative positions from the broad DEF/MID/FWD group.
EXPLICIT_ALTERNATIVE_POSITIONS = {
    "england-2026-27-fc27": {
        "231936": {"CB": "User-confirmed Ben White centre-back cover, 19 Oct 2026"},
    },
}

class ProjectedSquads(defaultdict):
    """Original primary-position roster plus multi-position cover."""
    def __init__(self):
        super().__init__(lambda: defaultdict(list))
        self.alternative_positions = {}

def effective_cover(squads, club, lane, exclude_player=None):
    """Credible options at one position, counting each person once.

    An eligible alternative-position player counts as rotation cover only when
    enough other starters remain in their *primary* position. This avoids
    describing the same footballer as two simultaneous starters.
    """
    roster=squads.get(club,{})
    options={p[0]: p for p in roster.get(lane,())
             if p[0]!=exclude_player}
    evidence=getattr(squads,"alternative_positions",{})
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



def assign_available_players(squads, club, required, *, exclude_player=None):
    """Maximum simultaneous lineup assignment; no player fills two slots.

    required maps position -> number of simultaneous players. The assignment
    uses eligible positions, not invented position-specific OVR adjustments.
    """
    slots=[]
    for position,count in required.items():
        lane=lane_of(position)
        if lane is None or type(count) is not int or not 0<=count<=11:
            raise ValueError("Invalid requested lineup position or count")
        slots.extend([lane]*count)
    roster=squads.get(club,{})
    players={}
    evidence=getattr(squads,"alternative_positions",{})
    for origin,group in roster.items():
        for pid,ovr,pos in group:
            if pid==exclude_player:
                continue
            players[pid]=(ovr,{origin,*evidence.get(pid,{})},origin)
    candidates={}
    for index,lane in enumerate(slots):
        candidates[index]=sorted(
            (pid for pid,(ovr,playable,origin) in players.items()
             if lane in playable),
            key=lambda pid:(players[pid][2]!=lane,-players[pid][0],pid))
    matching={}
    def allocate(slot,visited):
        for pid in candidates[slot]:
            if pid in visited:continue
            visited.add(pid)
            if pid not in matching or allocate(matching[pid],visited):
                matching[pid]=slot
                return True
        return False
    for slot in sorted(range(len(slots)),key=lambda i:len(candidates[i])):
        allocate(slot,set())
    assignments=[{"position":slots[index],"player_id":pid}
                 for pid,index in sorted(matching.items(),
                   key=lambda pair:pair[1])]
    return {"required":len(slots),"filled":len(assignments),
            "assignments":assignments,
            "unfilled":len(slots)-len(assignments)}


def squad_standard(roster):
    """Rated standard of the best XI, without double-counting the same player."""
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
    "LM": "LM", "LMF": "LM", "RM": "RM", "RMF": "RM",
    "LW": "LW", "RW": "RW", "LWF": "LW", "RWF": "RW",
    "CF": "ST", "ST": "ST", "SS": "ST", "STRIKER": "ST",
}
FAMILY = {"GK":"GK", "CB":"DEF", "LB":"DEF", "RB":"DEF", "FB":"DEF",
          "DM":"MID", "CM":"MID", "AM":"MID", "LM":"MID", "RM":"MID",
          "LW":"FWD", "RW":"FWD", "ST":"FWD"}
STARTERS = {"GK":1,"CB":2,"LB":1,"RB":1,"FB":1,
            "DM":1,"CM":2,"AM":1,"LM":1,"RM":1,"LW":1,"RW":1,"ST":1}
# Conservative minimum viable positional coverage after a departure.
# A deficit cannot be cured with unrelated players from the same broad family.
MIN_COVER = {"GK":2,"CB":3,"LB":1,"RB":1,"FB":1,
             "DM":1,"CM":2,"AM":0,"LM":0,"RM":0,"LW":1,"RW":1,"ST":1}


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
    ids=EXPLICIT_ALTERNATIVE_POSITIONS.get(dataset,{})
    if ids:
        try:
            rows=conn.execute("""SELECT player_id,external_id
                FROM world_player_source_refs
                WHERE source_name='EAFC27'""").fetchall()
            squads.alternative_positions={
                int(pid):ids[str(ea_id)] for pid,ea_id in rows
                if str(ea_id) in ids}
        except sqlite3.OperationalError:
            # Minimal synthetic planner fixtures may omit source-ref tables.
            squads.alternative_positions={}
    # Many documented alternative positions are permitted per player.
    # This table supports user-approved imports without code changes.
    # An absent record means unknown, not automatically versatile.
    try:
        extra=conn.execute("""SELECT player_id,position,source_note
            FROM world_player_alternative_positions
            WHERE dataset_id=?""",(dataset,)).fetchall()
    except sqlite3.OperationalError:
        extra=()
    primary={pid:lane_of(pos) for pid,_owner,_ovr,pos in registrations}
    valid_players=set(primary)
    for pid,position,source_note in extra:
        lane=lane_of(position)
        if pid in valid_players and lane and lane!=primary[pid] and source_note:
            squads.alternative_positions.setdefault(pid,{})[lane]=source_note
    for roster in squads.values():
        for players in roster.values():
            players.sort(key=lambda x:(-x[1],x[0]))
    return squads


def recruitment_fit(squads, *, buyer, position, overall,
                    recent_senior_departure=False, starting_roles=None):
    """Evaluate actual starter upgrade and depth need, not third-best DEF/FWD.

    Lack of verified potential prevents labelling an inferior target as a
    wonderkid. Such targets can be recruited later with a licensed potential
    signal, but not by an ungrounded 'young and promising' guess.
    """
    if type(recent_senior_departure) is not bool:
        raise ValueError("Recent signed departure must be explicit")
    slot=lane_of(position)
    if not slot or not 1<=overall<=99:
        return {"eligible":False,"score":0,"reason":"Unknown position or rating"}
    roster=squads.get(buyer,{})
    peers=effective_cover(squads,buyer,slot)
    all_ratings=sorted((entry[1] for group in roster.values()
                        for entry in group),reverse=True)
    if not all_ratings:
        return {"eligible":False,"score":0,"reason":"No rated buyer squad"}
    if starting_roles is not None and (
            not isinstance(starting_roles,dict) or
            any(type(n) is not int or not 0<=n<=11
                for n in starting_roles.values())):
        raise ValueError("Invalid manager tactical roles")
    starter_n=(STARTERS[slot] if starting_roles is None
               else starting_roles.get(slot,0))
    # Do not treat specialist wide midfield and wing-forward as equivalent.
    # An unused tactical lane can still be developed for future seasons,
    # but it is not a *present XI* improvement.
    baseline=(peers[min(starter_n-1,len(peers)-1)][1]
              if peers and starter_n>0 else None)
    team_baseline=all_ratings[min(10,len(all_ratings)-1)]
    minimum=(max(MIN_COVER[slot],STARTERS[slot]) if starting_roles is None
             else starter_n+(1 if starter_n>0 else 0))
    thin=starter_n>0 and len(peers)<minimum
    # First-team upgrades require meaningful improvement to the actual
    # starter; an 83-rated attacker is not a first-team upgrade to a 90+ XI.
    improvement=(overall-baseline) if baseline is not None else 0
    # Missing a usable starter is an urgent need, not a demand to
    # obtain the replacement BEFORE selling the previous player.
    credible_depth=thin and overall>=team_baseline-8
    credible_upgrade=(baseline is not None and improvement>=3 and
                      overall>=team_baseline-3)
    # A club that has already agreed to sell an established player may
    # rationally buy a comparable senior replacement. Requiring a 3+ OVR
    # upgrade after a departure forces even elite clubs into youth-only
    # recruitment. This does NOT require a purchase before the sale.
    credible_replacement=(starter_n>0 and recent_senior_departure and
         overall>=team_baseline-5 and
         (baseline is None or overall>=baseline-4))
    if not (credible_depth or credible_upgrade or credible_replacement):
        return {"eligible":False,"score":0,"lane":slot,
                "reason":"Not a credible starter upgrade or necessary depth"}
    score=min(98,max(50,52+max(0,improvement)*5+
                     (20 if credible_depth else 0)+
                     (8 if credible_upgrade else 0)+
                     (23 if credible_replacement else 0)))
    return {"eligible":True,"score":score,"lane":slot,
            "upgrade":improvement,"depth_shortage":thin,
            "reason":("Required positional cover" if credible_depth else
                      "Senior squad-quality replacement after agreed departure"
                      if credible_replacement else
                      "Meaningful first-team positional upgrade"),
            "senior_replacement":credible_replacement}




def sale_profile(squads, *, seller, player_id, position, overall,
                 starting_roles=None):
    """Sporting cost of selling, considering genuine alternative positions.

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
    eligible=getattr(squads,"alternative_positions",{}).get(player_id,{})
    affected={slot,*eligible}
    reports=[]
    for lane in sorted(affected):
        before=effective_cover(squads,seller,lane)
        after=effective_cover(squads,seller,lane,exclude_player=player_id)
        used=(starting_roles is None or starting_roles.get(lane,0)>0)
        n=(STARTERS[lane] if starting_roles is None
           else starting_roles.get(lane,0))
        minimum=(max(n,MIN_COVER[lane]) if starting_roles is None
                 else n+1 if n else 0)
        old_floor=(before[min(n-1,len(before)-1)][1]
                   if before and n else None)
        new_floor=(after[min(n-1,len(after)-1)][1]
                   if after and n else None)
        # First two rotation places, not just the strongest starters.
        old_backup=[p[1] for p in before[n:n+2]]
        new_backup=[p[1] for p in after[n:n+2]]
        first_backup_drop=(sum(
            max(0,old_backup[i]-(new_backup[i] if i<len(new_backup) else 0))
            for i in range(len(old_backup))) if used else 0)
        starter_drop=(max(0,(old_floor or 0)-(new_floor or 0))
                      if used else 0)
        short=len(after)<minimum
        reports.append({
            "lane":lane,"before_depth":len(before),"after_depth":len(after),
            "starter_rating_drop":starter_drop,
            "backup_quality_drop":first_backup_drop,
            "depth_shortage":short,
            "recruitment_needed":short or starter_drop>=4 or
                                first_backup_drop>=4,
        })
    demands={lane:(max(STARTERS[lane],MIN_COVER[lane])
             if starting_roles is None else starting_roles.get(lane,0))
             for lane in affected
             if starting_roles is None or starting_roles.get(lane,0)>0}
    whole_before=assign_available_players(squads,seller,demands)
    whole_after=assign_available_players(squads,seller,demands,
                                         exclude_player=player_id)
    # Per-position lists overlap for multi-role players. This assignment
    # instead counts simultaneous cover: the same person cannot fulfil
    # centre-back AND defensive-midfield during one match.
    simultaneous_loss=max(0,whole_before["filled"]-whole_after["filled"])
    # A full tactical XI is a coupled assignment problem: two players
    # covering three potential positions are still only two people.
    # Compare the manager's whole preferred starting formation, rather
    # than only the departing footballer's primary role.
    if starting_roles is not None:
        match_before=assign_available_players(squads,seller,starting_roles)
        match_after=assign_available_players(
            squads,seller,starting_roles,exclude_player=player_id)
        formation_lineup_loss=max(0,match_before["filled"]-match_after["filled"])
    else:
        formation_lineup_loss=0
    seriousness=max((r["starter_rating_drop"]*2+
                     r["backup_quality_drop"]+
                     (15 if r["depth_shortage"] else 0)
                     for r in reports),default=0)+6*simultaneous_loss
    # Strong clubs ought to retain *competition-quality* reserves instead of
    # preserving only their top two starters and replacing depth with 70s.
    # This only makes a routine sale harder; does not bar genuine exceptions.
    protected_rotation=(formation_lineup_loss>0 or
        quality>=82 and (simultaneous_loss>0 or any(
        r["backup_quality_drop"]>=4 or r["starter_rating_drop"]>=4
        for r in reports)))
    needs=formation_lineup_loss>0 or simultaneous_loss>0 or any(
        r["recruitment_needed"] for r in reports)
    main=next(r for r in reports if r["lane"]==slot)
    return {
        "valid":True,"lane":slot,"rank":rank,
        "first_choice":rank<(STARTERS[slot] if starting_roles is None
                            else starting_roles.get(slot,0)),
        "before_depth":main["before_depth"],
        "after_depth":main["after_depth"],
        "starter_rating_drop":main["starter_rating_drop"],
        "backup_quality_drop":main["backup_quality_drop"],
        "below_target_cover":main["depth_shortage"],
        "replacement_priority":("urgent" if any(r["depth_shortage"] for r in reports)
           else "improve_rotation" if protected_rotation
           else "improve_starter" if needs else "none"),
        "requires_recruitment":needs,
        "surplus_sale":not needs and rank>=(
            STARTERS[slot] if starting_roles is None
            else starting_roles.get(slot,0)),
        "protected_rotation":protected_rotation,
        "sporting_risk":seriousness+formation_lineup_loss*35,
        "simultaneous_cover_loss":simultaneous_loss,
        "formation_lineup_loss":formation_lineup_loss,
        "tactically_required":(starting_roles is None or
                               starting_roles.get(slot,0)>0),
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

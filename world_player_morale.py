"""Deterministic fictional player motivation and future PES-season eligibility.

No user is asked to fabricate player wishes. Squad status, verified age when
available, and recorded blocked offers determine a player's dissatisfaction.
A transfer request is uncommon; refusal to play is rare, requires repeated
credible blocked exits, and excludes the player from the coming PES squad.
This is an explicit modelled simulation, not a claim about real players.
"""
import hashlib
from datetime import datetime
from world_preseason_window import window_snapshot, _utc

SCHEMA="""
CREATE TABLE IF NOT EXISTS world_career_player_morale(
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 window_id INTEGER NOT NULL REFERENCES world_career_preseason_windows(window_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 status TEXT NOT NULL CHECK(status IN ('transfer_requested','refusing_to_play')),
 reason TEXT NOT NULL,
 requested_at TEXT NOT NULL,
 refused_at TEXT,
 PRIMARY KEY(career_id,window_id,player_id)
);
CREATE INDEX IF NOT EXISTS world_career_player_morale_club
 ON world_career_player_morale(career_id,window_id,club_id,status);
"""


def initialise_player_morale(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def _probability(*parts):
    h=hashlib.sha256(("morale-v1:"+":".join(map(str,parts))).encode()).digest()
    return int.from_bytes(h[:4],"big")/4294967296.0


def is_unavailable(conn,*,career_id,window_id,player_id):
    try:
        return conn.execute("""SELECT 1 FROM world_career_player_morale
            WHERE career_id=? AND window_id=? AND player_id=?
              AND status='refusing_to_play'""",
            (career_id,window_id,player_id)).fetchone() is not None
    except __import__("sqlite3").OperationalError as exc:
        if "no such table" not in str(exc):raise
        # Older untimed career fixtures never initialise the live market.
        return False


def existing_morale(conn,*,career_id,window_id):
    rows=conn.execute("""SELECT m.player_id,m.club_id,m.status,m.reason,
        p.full_name,c.name FROM world_career_player_morale m
        JOIN world_players p ON p.player_id=m.player_id
        JOIN world_clubs c ON c.club_id=m.club_id
        WHERE m.career_id=? AND m.window_id=?""",
        (career_id,window_id)).fetchall()
    return [dict(player_id=r[0],club_id=r[1],status=r[2],
                 reason=r[3],player_name=r[4],club_name=r[5]) for r in rows]


def _player_role(conn,*,career_id,player_id,club_id,dataset,ratings):
    from world_ai_bidding import position_family
    explicit=conn.execute("""SELECT current_role FROM
        world_career_player_circumstances WHERE career_id=? AND player_id=?""",
        (career_id,player_id)).fetchone()
    if explicit:return explicit[0]
    group=ratings.get(player_id,(0,None))[1]
    family=position_family(group)
    family_peers=[(rating,pid) for pid,(rating,pos) in ratings.items()
        if position_family(pos)==family and
        conn.execute("""SELECT club_id FROM world_career_registrations
            WHERE career_id=? AND player_id=?""",
            (career_id,pid)).fetchone()[0]==club_id]
    if not family_peers:return "rotation"
    family_peers.sort(reverse=True)
    rank=next((i for i,(_,pid) in enumerate(family_peers) if pid==player_id),0)
    depth={"GK":1,"DEF":4,"MID":4,"FWD":2}.get(family,3)
    return ("regular_starter" if rank<depth else
            "rotation" if rank<depth*2 else "fringe")


def reconcile_player_morale(conn,*,career_id,now=None):
    """One deterministic iteration; status never rerolls on a reload.

    Triggers: non-playing status + either credible stalled moves OR a rare
    individual wish for starts. Refusal additionally requires >=2 genuine
    club-blocked valuable bids and late-window sustained disappointment.
    """
    t=_utc(now)
    snap=window_snapshot(conn,career_id=career_id,now=t)
    if snap["state"] not in ("open","deadline_reached"):
        return {"requested":0,"refusing":0}
    window_id=snap["window_id"]
    start=datetime.fromisoformat(snap["started_at"])
    elapsed=(t-start).total_seconds()
    if elapsed<600:return {"requested":0,"refusing":0}
    dataset,manager=conn.execute("""SELECT dataset_id,manager_club_id
        FROM world_career_saves WHERE career_id=?""",(career_id,)).fetchone()
    people=conn.execute("""SELECT r.player_id,r.club_id,p.full_name,p.birth_date,
        x.overall,p.primary_position
        FROM world_career_registrations r
        JOIN world_players p ON p.player_id=r.player_id
        JOIN world_dataset_ratings x ON x.player_id=r.player_id AND x.dataset_id=?
        WHERE r.career_id=? AND x.overall BETWEEN 1 AND 99""",
        (dataset,career_id)).fetchall()
    from world_ai_bidding import position_family
    from collections import defaultdict
    by_club=defaultdict(lambda:defaultdict(list))
    for pid,club,name,dob,overall,position in people:
        by_club[club][position_family(position)].append((overall,pid))
    for groups in by_club.values():
        for ranks in groups.values():ranks.sort(reverse=True)
    from world_careers import _player_reference
    from world_live_market import _message
    current_roles=dict(conn.execute("""SELECT player_id,current_role
        FROM world_career_player_circumstances
        WHERE career_id=?""",(career_id,)).fetchall())
    old_morale=dict(conn.execute("""SELECT player_id,status
        FROM world_career_player_morale WHERE career_id=? AND window_id=?""",
        (career_id,window_id)).fetchall())
    has_rejections={r[0] for r in conn.execute("""SELECT DISTINCT o.player_id
        FROM world_career_offers o
        JOIN world_career_preseason_window_offers wt ON wt.offer_id=o.offer_id
        WHERE wt.window_id=? AND o.career_id=? AND o.status='rejected'""",
        (window_id,career_id)).fetchall()}
    signed={r[0] for r in conn.execute("""SELECT DISTINCT player_id
        FROM world_career_offers WHERE career_id=? AND
        status IN ('agreed_future','completed')""",(career_id,)).fetchall()}
    requested=0
    refused=0
    resolved=0
    for pid,club,name,dob,overall,pos in people:
        if pid in signed:continue
        role=current_roles.get(pid)
        if role:
            pass
        else:
            ranks=by_club[club][position_family(pos)]
            rank=next((i for i,(_,person) in enumerate(ranks) if person==pid),0)
            starter={"GK":1,"DEF":4,"MID":4,"FWD":2}.get(position_family(pos),3)
            role=("regular_starter" if rank<starter else
                  "rotation" if rank<starter*2 else "fringe")
        if role not in ("fringe","rotation"):
            # A player's request is not an irreversible random event.
            # A genuine promotion to regular first-team status may resolve
            # their playing-time motivation; a blocked high-value exit
            # is a different concern and is not silently erased.
            if (old_morale.get(pid)=="transfer_requested" and
                    pid not in has_rejections):
                conn.execute("""DELETE FROM world_career_player_morale
                    WHERE career_id=? AND window_id=? AND player_id=?
                    AND status='transfer_requested'""",
                    (career_id,window_id,pid))
                resolved+=1
                if club==manager:
                    _message(conn,career_id=career_id,window_id=window_id,
                        key=f"player-request-resolved:{pid}",when=t,
                        headline=f"{name} withdraws transfer request",
                        detail="Regular first-team status has resolved the player's playing-time concern.")
            continue
        age=None
        if dob:
            try:
                born=datetime.fromisoformat(dob).date()
                age=start.date().year-born.year-(
                    (start.date().month,start.date().day)<
                    (born.month,born.day))
            except ValueError:pass
        if age is not None and not 19<=age<=37:continue
        requested_previously=pid in old_morale
        # Avoid thousands of valuations and offer lookups per market tick:
        # only genuinely rejected movers or independently motivated players
        # can reach the calculation.
        if pid not in has_rejections and not requested_previously:
            if role!="fringe" or elapsed<950 or (
                _probability(career_id,window_id,pid,"request")>=0.035):
                continue
        value,_=_player_reference(conn,dataset,pid)
        if not value or value<=0:continue
        rejected=conn.execute("""SELECT COUNT(DISTINCT o.offer_id)
            FROM world_career_offers o
            JOIN world_career_preseason_window_offers wt ON wt.offer_id=o.offer_id
            WHERE wt.window_id=? AND o.career_id=? AND o.player_id=?
                AND o.selling_club_id=? AND o.status='rejected'
                AND o.offered_fee>=?""",
            (window_id,career_id,pid,club,int(value*0.8))).fetchone()[0]
        previous=old_morale.get(pid)
        if previous=="refusing_to_play":continue
        if not previous:
            # A credible blocked exit strongly increases dissatisfaction.
            # A rarely occurring independent request covers other players
            # unhappy about a long period on the bench.
            likelihood=(0.60 if rejected>=1 else
                        0.035 if role=="fringe" and elapsed>=950 else 0)
            if _probability(career_id,window_id,pid,"request")>=likelihood:
                continue
            reason=("Reduced first-team opportunities and a blocked transfer."
                if rejected else "Player seeks more regular first-team football.")
            conn.execute("""INSERT OR IGNORE INTO world_career_player_morale
                (career_id,window_id,player_id,club_id,status,reason,requested_at)
                VALUES(?,?,?,?,'transfer_requested',?,?)""",
                (career_id,window_id,pid,club,reason,t.isoformat()))
            requested+=1
            old_morale[pid]="transfer_requested"
            if club==manager:
                _message(conn,career_id=career_id,window_id=window_id,
                    key=f"player-request:{pid}",when=t,
                    headline=f"{name} requests a transfer",
                    detail=reason)
        elif (elapsed>=1520 and rejected>=2 and
              _probability(career_id,window_id,pid,"strike")<0.09):
            # Refusal to play is never caused by the first rejected bid.
            # It is never assigned to a player with a fully signed exit.
            conn.execute("""UPDATE world_career_player_morale
                SET status='refusing_to_play',
                    reason='Repeated credible transfer bids blocked; player refuses to play.',
                    refused_at=?
                WHERE career_id=? AND window_id=? AND player_id=?
                  AND status='transfer_requested'""",
                (t.isoformat(),career_id,window_id,pid))
            refused+=1
            _message(conn,career_id=career_id,window_id=window_id,
                key=f"player-refuses:{pid}",when=t,
                headline=(f"{name} refuses to play" if club==manager
                    else "Player refuses to play after blocked move"),
                detail=(f"{name} at {club} is excluded from the coming PES-season squad. "
                        "Registration ownership remains on the ledger."))
    if requested or refused or resolved:conn.commit()
    return {"requested":requested,"refusing":refused,"resolved":resolved}

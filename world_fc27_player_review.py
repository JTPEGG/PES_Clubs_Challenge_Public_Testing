"""Replay-safe, explicitly separate transfer decisions from negotiated terms.

Both buying offers and free agents can have accepted *terms* while a player
considers his sporting choices. Only a later positive decision unlocks the
manager's final paperwork. Simulated rival free-agent bids are persisted
and have actual AI-club budgets/needs; none is silently a completed signing.
"""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
import hashlib
from world_fc27_free_agents import DATASET

SCHEMA="""
CREATE TABLE IF NOT EXISTS world_career_player_choices (
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 window_id INTEGER NOT NULL REFERENCES world_career_preseason_windows(window_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 kind TEXT NOT NULL CHECK(kind IN ('purchase','free_agent','sale')),
 source_id INTEGER NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('evaluating','accepted','declined')),
 due_at TEXT NOT NULL,reason TEXT NOT NULL,
 recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 decided_at TEXT,
 PRIMARY KEY(career_id,window_id,kind,source_id)
);
CREATE INDEX IF NOT EXISTS fc27_choices_due
 ON world_career_player_choices(career_id,window_id,status,due_at);
CREATE TABLE IF NOT EXISTS world_fc27_free_agent_rival_bids(
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 signing_id INTEGER NOT NULL REFERENCES world_fc27_free_agent_offers(signing_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 offered_wage_weekly INTEGER NOT NULL CHECK(offered_wage_weekly>=0),
 club_appeal INTEGER NOT NULL,
 reason TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(career_id,signing_id,club_id)
);
"""

def initialise_player_choices(conn):
    conn.executescript(SCHEMA)
    conn.commit()

def _stable(*parts):
    raw=":".join(map(str,("fc27-player-choices-v1",*parts))).encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8],"big")/2**64

def _now(now=None):
    if now is None:return datetime.now(timezone.utc)
    if isinstance(now,str):now=datetime.fromisoformat(now.replace("Z","+00:00"))
    return now if now.tzinfo else now.replace(tzinfo=timezone.utc)

def choice_for(conn,*,career_id,kind,source_id):
    from world_preseason_window import window_snapshot
    win=window_snapshot(conn,career_id=career_id)["window_id"]
    if win is None:return None
    row=conn.execute("""SELECT status,due_at,reason FROM world_career_player_choices
        WHERE career_id=? AND window_id=? AND kind=? AND source_id=?""",
        (career_id,win,kind,source_id)).fetchone()
    return dict(status=row[0],due_at=row[1],reason=row[2]) if row else None

def rival_bids(conn,*,career_id,signing_id):
    return [dict(club_id=r[0],name=r[1],weekly_wage=r[2],appeal=r[3])
       for r in conn.execute("""SELECT b.club_id,c.name,b.offered_wage_weekly,
              b.club_appeal FROM world_fc27_free_agent_rival_bids b
              JOIN world_clubs c ON c.club_id=b.club_id
              WHERE b.career_id=? AND b.signing_id=?
              ORDER BY b.offered_wage_weekly DESC,b.club_id""",
              (career_id,signing_id)).fetchall()]

def _free_rivals(conn,*,career_id,signing_id,player_id,required,overall,position,manager):
    from world_ai_bidding import position_family
    from world_fc27_ai_recruitment import read_fc27_profiles
    peer_family=position_family(position)
    # Genuine current squad strength and real career wages/budget constrain
    # every speculative AI offer. No faceless 'competitor pressure' counter.
    peers=conn.execute("""SELECT r.club_id,x.overall,p.primary_position
        FROM world_career_registrations r
        JOIN world_players p ON p.player_id=r.player_id
        JOIN world_dataset_ratings x ON x.dataset_id=? AND x.player_id=r.player_id
        WHERE r.career_id=?""",(DATASET,career_id)).fetchall()
    by_club={}
    for club,rating,pos in peers:
        if position_family(pos)==peer_family:
            by_club.setdefault(club,[]).append(rating)
    profiles=read_fc27_profiles(conn,dataset=DATASET)
    ledgers=dict((club,(budget,committed)) for club,budget,committed
      in conn.execute("""SELECT club_id,weekly_wage_budget,committed_wages
          FROM world_career_club_ledger WHERE career_id=?""",(career_id,)))
    manager_appeal=profiles.get(manager,{}).get("sporting_appeal",50)
    total=0
    for club,profile in profiles.items():
        if club==manager:continue
        squad=by_club.get(club)
        if not squad:continue
        appeal=profile["sporting_appeal"]
        max_rating=max(squad)
        # Source-rated player must actually be a useful sporting addition;
        # clubs with a stronger first choice can still need depth.
        upside=max(-8,min(15,overall-max_rating))
        if upside < -5 or appeal < 39:continue
        budget,spent=ledgers.get(club,(0,0))
        funds=budget-spent
        if funds<max(1000,required):continue
        if appeal<manager_appeal-33 and upside<2:continue
        desire=max(0,min(.060,.006+(upside+5)*.0025+
                       max(0,appeal-64)*.0005))
        if _stable(career_id,signing_id,club,"approach")>=desire:continue
        offer=int(round(max(required*.91,required*(.97+
                  min(.24,max(0,upside)*.023)+
                  min(.12,max(0,appeal-65)*.003))) /500)*500)
        if offer>funds:continue
        conn.execute("""INSERT OR IGNORE INTO world_fc27_free_agent_rival_bids
           (career_id,signing_id,club_id,offered_wage_weekly,club_appeal,reason)
           VALUES(?,?,?,?,?,'Rated positional need, budget and wage proposal')""",
           (career_id,signing_id,club,offer,appeal))
        total+=1
    return total

def queue_choice(conn,*,career_id,kind,source_id,player_id,now=None):
    from world_preseason_window import window_snapshot
    snap=window_snapshot(conn,career_id=career_id,now=now)
    if snap["state"]!="open":raise ValueError("The transfer window is not open")
    if kind not in ("purchase","free_agent","sale"):raise ValueError("Unrecognised choice type")
    existing=choice_for(conn,career_id=career_id,kind=kind,source_id=source_id)
    if existing and existing["status"] in ("accepted","declined"):
        return existing
    if existing:return existing
    t=_now(now)
    # Short bounded decision duration, distinct from the agent reply.
    # No player is made to wait for an artificial ten-minute review.
    seconds=25+int(_stable(career_id,kind,source_id,"consider")*44)
    deadline=_now(snap["deadline_at"])
    due=min(t+timedelta(seconds=seconds),deadline-timedelta(seconds=1))
    conn.execute("""INSERT OR IGNORE INTO world_career_player_choices
        (career_id,window_id,player_id,kind,source_id,status,due_at,reason)
        VALUES(?,?,?,?,?,'evaluating',?,
         'Player is comparing sporting opportunities and agreed contract terms')""",
        (career_id,snap["window_id"],player_id,kind,source_id,due.isoformat()))
    if kind=="free_agent":
        row=conn.execute("""SELECT f.buying_club_id,f.required_weekly_wage_gbp,
            x.overall,p.primary_position FROM world_fc27_free_agent_offers f
            JOIN world_career_saves c ON c.career_id=f.career_id
            JOIN world_dataset_ratings x ON x.dataset_id=c.dataset_id
               AND x.player_id=f.player_id
            JOIN world_players p ON p.player_id=f.player_id
            WHERE f.career_id=? AND f.signing_id=? AND f.player_id=?""",
            (career_id,source_id,player_id)).fetchone()
        if row:
            _free_rivals(conn,career_id=career_id,signing_id=source_id,
                player_id=player_id,manager=row[0],required=row[1],
                overall=row[2],position=row[3])
    from world_live_market import _message
    _message(conn,career_id=career_id,window_id=snap["window_id"],
        key=f"player-review-started:{kind}:{source_id}",
        headline="Player is considering your contract",
        detail="Terms were offered to the agent. The player is evaluating the proposal and any competing offers before a separate final decision.")
    conn.commit()
    return choice_for(conn,career_id=career_id,kind=kind,source_id=source_id)

def review_due_choices(conn,*,career_id,now=None):
    from world_preseason_window import window_snapshot
    from world_live_market import _message
    snap=window_snapshot(conn,career_id=career_id,now=now)
    if snap["state"]!="open":return 0
    clock=_now(now)
    rows=conn.execute("""SELECT player_id,kind,source_id FROM
        world_career_player_choices WHERE career_id=? AND window_id=?
          AND status='evaluating' AND due_at<=?
        ORDER BY due_at,source_id LIMIT 30""",
        (career_id,snap["window_id"],clock.isoformat())).fetchall()
    changes=0
    for pid,kind,identifier in rows:
        if kind=="sale":
            # Accepted wage deals, not open fee-only bids, are eligible.
            # Incomplete rival agent talks never hold the player hostage.
            contenders=conn.execute("""SELECT o.offer_id,o.buying_club_id,
                 t.proposed_wage_weekly,pc.prestige_score
                 FROM world_career_offers o
                 JOIN world_career_agent_terms t ON t.offer_id=o.offer_id
                 LEFT JOIN world_career_prestige_snapshots pc
                    ON pc.career_id=o.career_id AND pc.club_id=o.buying_club_id
                 WHERE o.career_id=? AND o.player_id=?
                   AND o.status='accepted_pending_contract'
                   AND t.status='accepted' AND t.proposed_wage_weekly IS NOT NULL
                 ORDER BY o.offer_id""",(career_id,pid)).fetchall()
            # A player must make an actual decision at the due checkpoint.
            # Pending fee-only bids do NOT stall a valid, agreed-wage deal.
            # If a buyer withdraws in the meantime, close that attempt;
            # never leave the player's choice indefinitely 'evaluating'.
            if not contenders:
                status="declined"
                reason="No active buying club has an accepted agent contract; this proposed move cannot proceed"
            else:
                ranked=[(float(appeal or 50)+min(20,wage/5000),
                    oid) for oid,club,wage,appeal in contenders]
                winner=max(ranked,key=lambda x:(x[0],-x[1]))[1]
                status="accepted" if identifier==winner else "declined"
                reason=("Player chooses this buying club after comparing "+
                        str(len(contenders))+" valid agreed-wage proposal(s)" if
                        status=="accepted" else
                        "Player prefers a competing club's agreed sporting and wage terms")
        elif kind=="purchase":
            from world_career_incoming import competing_player_choice
            choice=competing_player_choice(conn,career_id=career_id,
                                          offer_id=identifier)
            if choice["decision"]=="delayed":
                # Waiting for a real competing negotiation: do not falsely
                # refuse or accept. Re-evaluate promptly with a 30s cadence.
                conn.execute("""UPDATE world_career_player_choices
                    SET due_at=?,reason=? WHERE career_id=? AND window_id=?
                     AND kind=? AND source_id=? AND status='evaluating'""",
                    ((clock+timedelta(seconds=30)).isoformat(),choice["reason"],
                     career_id,snap["window_id"],kind,identifier))
                continue
            status="accepted" if choice["decision"]=="ready" else "declined"
            reason=choice["reason"]
        else:
            row=conn.execute("""SELECT f.status,f.buying_club_id,
                 f.proposed_weekly_wage_gbp,f.required_weekly_wage_gbp,
                 f.squad_role,p.full_name
                 FROM world_fc27_free_agent_offers f
                 JOIN world_players p ON p.player_id=f.player_id
                 WHERE f.career_id=? AND f.signing_id=?""",
                 (career_id,identifier)).fetchone()
            if not row or row[0]!="terms_accepted":
                continue
            from world_fc27_ai_recruitment import read_fc27_profiles
            manager_appeal=read_fc27_profiles(conn,dataset=DATASET,
                club_id=row[1]).get(row[1],{}).get("sporting_appeal",50)
            def utility(appeal,wage,role):
                return appeal*.38+min(2.3,wage/max(1,row[3]))*27+role
            role_bonus={"key_player":13,"regular_starter":8,
                "rotation":2,"fringe":-4}.get(row[4],0)
            own=utility(manager_appeal,row[2],role_bonus)
            rivals=rival_bids(conn,career_id=career_id,signing_id=identifier)
            rival_values=[(utility(r["appeal"],r["weekly_wage"],5),r)
                for r in rivals]
            winner=max(rival_values,key=lambda x:x[0]) if rival_values else None
            if winner and winner[0]>own+1.0:
                status="declined"
                reason=("Player preferred a competing club's financial and "
                        "sporting opportunity after considering the offers")
            else:
                status="accepted"
                reason=("Player wants to sign after comparing "+
                        str(len(rivals))+" credible AI-club offer(s)")
        if kind=="sale" and status=="declined":
            # An agent can agree wages for more than one club; the PLAYER
            # chooses one. The other unsigned offers must visibly end and
            # never remain as phantom pending transfers until the deadline.
            current=conn.execute("""SELECT status FROM world_career_offers
                WHERE career_id=? AND offer_id=?""",
                (career_id,identifier)).fetchone()
            if current and current[0]=="accepted_pending_contract":
                conn.execute("""UPDATE world_career_offers SET status='withdrawn'
                    WHERE career_id=? AND offer_id=?
                      AND status='accepted_pending_contract'""",
                    (career_id,identifier))
                conn.execute("""INSERT INTO world_career_offer_events
                    (offer_id,event_type,detail)
                    VALUES (?,'player_declined_sale',?)""",
                    (identifier,reason))
        conn.execute("""UPDATE world_career_player_choices
            SET status=?,reason=?,decided_at=? WHERE career_id=?
            AND window_id=? AND kind=? AND source_id=? AND status='evaluating'""",
            (status,reason,clock.isoformat(),career_id,
             snap["window_id"],kind,identifier))
        _message(conn,career_id=career_id,window_id=snap["window_id"],
            key=f"player-review-outcome:{kind}:{identifier}",
            offer_id=identifier if kind in ("purchase","sale") else None,
            headline=("Player accepts your contract" if status=="accepted"
                      else "Player declines your contract"),
            detail=reason+(". Open your Inbox to confirm the signing."
                   if status=="accepted" else ". No paperwork can be signed."),
            when=clock)
        changes+=1
    if rows:conn.commit()
    return changes

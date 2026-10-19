"""Manager's current and projected roster in the development transfer window.

The projected list includes fully signed inbound deals and hides fully
signed outbound deals. The original registrations are never mutated before
the authoritative deadline finaliser runs. Manager listing/role changes update
the existing player-interest inputs used by AI clubs.
"""
from world_preseason_window import window_snapshot
from world_careers import _player_reference
from world_player_decisions import PLAYER_CURRENT_ROLES

ROLES=("key_player","regular_starter","rotation","fringe")
OUTREACH_SCHEMA="""
CREATE TABLE IF NOT EXISTS world_career_squad_outreach(
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 window_id INTEGER NOT NULL REFERENCES world_career_preseason_windows(window_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(career_id,window_id,player_id)
);
"""

def initialise_squad_desk(conn):
    conn.executescript(OUTREACH_SCHEMA)
    conn.commit()


def squad_preview(conn,*,career_id):
    row=conn.execute("""SELECT dataset_id,manager_club_id FROM world_career_saves
        WHERE career_id=? AND state='sandbox'""",(career_id,)).fetchone()
    if not row:raise ValueError("Unknown development career")
    dataset,manager=row
    window=window_snapshot(conn,career_id=career_id)
    pending={}
    if window["state"]!="not_started":
        for offer in conn.execute("""SELECT player_id,selling_club_id,buying_club_id,
                status FROM world_career_offers o
            JOIN world_career_preseason_window_offers wo ON wo.offer_id=o.offer_id
            WHERE o.career_id=? AND wo.window_id=?
                AND o.status='agreed_future'""",
            (career_id,window["window_id"])).fetchall():
            player,seller,buyer,status=offer
            if seller==manager:pending[player]="selling"
            elif buyer==manager:pending[player]="buying"
    squads=conn.execute("""SELECT r.player_id,r.club_id,p.full_name,p.primary_position,
            x.overall,pc.current_role,pc.transfer_listed,
            lc.squad_role_estimate,lc.transfer_listed_estimate,
            cl.name AS club_name
        FROM world_career_registrations r
        JOIN world_players p ON p.player_id=r.player_id
        JOIN world_clubs cl ON cl.club_id=r.club_id
        JOIN world_dataset_ratings x ON x.dataset_id=? AND x.player_id=r.player_id
        LEFT JOIN world_career_player_circumstances pc
          ON pc.career_id=r.career_id AND pc.player_id=r.player_id
        LEFT JOIN world_career_live_player_context lc
          ON lc.career_id=r.career_id AND lc.player_id=r.player_id
            AND lc.window_id=?
        WHERE r.career_id=? AND
             (r.club_id=? OR r.player_id IN (
                SELECT o.player_id FROM world_career_offers o
                JOIN world_career_preseason_window_offers wo
                  ON wo.offer_id=o.offer_id
                WHERE o.career_id=? AND wo.window_id=?
                  AND o.buying_club_id=? AND o.status='agreed_future'
             ))
        ORDER BY x.overall DESC,p.full_name""",
        (dataset,window.get("window_id") or -1,career_id,manager,career_id,
         window.get("window_id") or -1,manager)).fetchall()
    from world_player_morale import existing_morale
    morale_rows=(existing_morale(conn,career_id=career_id,
                 window_id=window["window_id"])
                 if window["state"]!="not_started" else [])
    morale={r["player_id"]:r for r in morale_rows}
    results=[]
    sales=[]
    unavailable=[]
    for row in squads:
        player,club,name,pos,overall,role,listed,estimate_role,estimate_listed,club_name=row
        value,_=_player_reference(conn,dataset,player)
        move=pending.get(player)
        arrival=move=="buying"
        departure=move=="selling"
        data=dict(player_id=player,club_id=club,full_name=name,
                  position=pos,overall=overall,market_value=value,
                  role=role or estimate_role or "rotation",
                  listed=bool(listed if listed is not None else estimate_listed),
                  incoming=arrival,departing=departure,
                  from_club=club_name if arrival else None,
                  morale_status=(morale.get(player) or {}).get("status"),
                  morale_reason=(morale.get(player) or {}).get("reason"))
        if data["morale_status"]=="refusing_to_play":
            unavailable.append(data)
        elif departure:sales.append(data)
        else:results.append(data)
    return {"players":results,"departures":sales,"unavailable":unavailable,
            "manager_club_id":manager,"window_state":window["state"]}


def update_squad_player(conn,*,career_id,player_id,
                        role=None,listed=None,offer_to_clubs=False):
    window=window_snapshot(conn,career_id=career_id)
    if window["state"] not in ("not_started","open"):
        raise ValueError("Squad instructions cannot change after the deadline")
    club=conn.execute("""SELECT c.manager_club_id,c.dataset_id FROM world_career_saves c
        JOIN world_career_registrations r ON r.career_id=c.career_id
        WHERE c.career_id=? AND c.state='sandbox'
          AND r.club_id=c.manager_club_id AND r.player_id=?""",
        (career_id,player_id)).fetchone()
    if club is None:raise ValueError("Only your own currently registered players can be managed")
    if conn.execute("""SELECT 1 FROM world_career_offers
        WHERE career_id=? AND player_id=?
          AND status IN ('agreed_future','completed') LIMIT 1""",
        (career_id,player_id)).fetchone():
        raise ValueError("An already signed sale cannot be changed")
    if role is not None and role not in ROLES:
        raise ValueError("Select a recognised squad role")
    if listed is not None and type(listed) is not bool:
        raise ValueError("Transfer-listed status must be yes or no")
    if offer_to_clubs and window["state"]!="open":
        raise ValueError("You can approach clubs only during the active transfer window")
    if offer_to_clubs:
        initialise_squad_desk(conn)
        previously=conn.execute("""SELECT 1 FROM world_career_squad_outreach
            WHERE career_id=? AND window_id=? AND player_id=?""",
            (career_id,window["window_id"],player_id)).fetchone()
        if previously:
            raise ValueError("You already offered this player to clubs during this window")
    if role is None and listed is None and not offer_to_clubs:
        raise ValueError("Choose a squad instruction")
    data=conn.execute("""SELECT pc.current_wage_weekly,pc.current_role,
         pc.transfer_listed,pc.renewal_status FROM world_career_player_circumstances pc
        WHERE pc.career_id=? AND pc.player_id=?""",(career_id,player_id)).fetchone()
    info=conn.execute("""SELECT overall FROM world_dataset_ratings
        WHERE dataset_id=? AND player_id=?""",(club[1],player_id)).fetchone()
    if not info or info[0] is None:raise ValueError("Player has no rated career record")
    overall=int(info[0])
    wage=(data[0] if data else max(1000,min(350000,
        round(1000*2**((overall-55)/8)/500)*500)))
    new_role=role if role is not None else (data[1] if data else "rotation")
    new_listed=int(listed) if listed is not None else int(data[2]) if data else 0
    renewal=(data[3] if data else "renewal_offered")
    if offer_to_clubs and not new_listed:
        raise ValueError("Transfer-list this player before offering him to clubs")
    conn.execute("""INSERT INTO world_career_player_circumstances
        (career_id,player_id,current_wage_weekly,current_role,transfer_listed,
         renewal_status,source_kind) VALUES(?,?,?,?,?,?,'manager_squad_instruction')
        ON CONFLICT(career_id,player_id) DO UPDATE SET
         current_role=excluded.current_role,
         transfer_listed=excluded.transfer_listed,
         source_kind=excluded.source_kind,
         updated_at=CURRENT_TIMESTAMP""",
        (career_id,player_id,wage,new_role,new_listed,renewal))
    # Future AI interests must use the manager's current instructions rather
    # than the initial static seed estimate.
    conn.execute("""UPDATE world_career_live_player_context
        SET squad_role_estimate=?,transfer_listed_estimate=?,
            model_note='Manager squad instruction overrides initial model role/listing'
        WHERE career_id=? AND player_id=?""",
        (new_role,new_listed,career_id,player_id))
    if offer_to_clubs:
        cur=conn.execute("""INSERT OR IGNORE INTO world_career_squad_outreach
            (career_id,window_id,player_id) VALUES(?,?,?)""",
            (career_id,window["window_id"],player_id))
        if cur.rowcount==0:
            raise ValueError("You already offered this player to clubs during this window")
        from world_live_market import _message
        _message(conn,career_id=career_id,window_id=window["window_id"],
            key=f"outreach:{player_id}:{window['window_id']}",
            headline="Player offered to clubs",
            detail="Transfer-listed player circulated to AI recruitment desks. "
                   "Interest is not guaranteed, and the player must still agree any move.")
    conn.commit()
    return "Player offered to clubs." if offer_to_clubs else (
        "Squad status and availability updated. Future player decisions use these instructions."
    )

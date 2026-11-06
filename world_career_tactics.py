"""Persistent, career-scoped tactical lineup planner for the FC27 desk.

These selections are ONLY an editable visual plan. They do not modify PES
formation data, player contracts, transfers, registered club rosters or AI.
The authoritative squad preview controls who can be selected.
"""
from __future__ import annotations

import json

FORMATIONS={
    "4-4-2":[(50,91),(16,72),(39,74),(61,74),(84,72),
             (16,46),(39,48),(61,48),(84,46),(39,19),(61,19)],
    "4-3-3":[(50,91),(16,72),(39,74),(61,74),(84,72),
             (26,50),(50,54),(74,50),(18,20),(50,17),(82,20)],
    "4-2-3-1":[(50,91),(16,72),(39,74),(61,74),(84,72),
               (36,57),(64,57),(18,36),(50,35),(82,36),(50,15)],
    "3-5-2":[(50,91),(25,73),(50,75),(75,73),
             (10,50),(32,49),(50,57),(68,49),(90,50),(38,19),(62,19)],
}
DEFAULT_FORMATION="4-4-2"
BENCH_LIMIT=7
TACTICS_SCHEMA="""
CREATE TABLE IF NOT EXISTS world_career_tactics_layout(
  career_id TEXT PRIMARY KEY REFERENCES world_career_saves(career_id)
    ON DELETE CASCADE,
  formation TEXT NOT NULL,
  layout_json TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

def initialize_tactics(conn):
    conn.executescript(TACTICS_SCHEMA)
    conn.commit()

def _family(position):
    position=(position or "").upper()
    if position=="GK":return "GK"
    if position in ("CB","LB","RB","LWB","RWB"):return "DEF"
    if position in ("DMF","CMF","AMF","LMF","RMF","DM","CM","AM","LM","RM"):
        return "MID"
    return "FWD"

def _lineup_players(players,formation):
    """Rating-first draft XI, with position coverage, only for initial display."""
    selected=[]
    remaining=list(sorted(players,key=lambda p:(-int(p.get("overall") or 0),
                     p.get("full_name") or "")))
    slots={"4-4-2":(1,4,4,2),"4-3-3":(1,4,3,3),
           "4-2-3-1":(1,4,5,1),"3-5-2":(1,3,5,2)}[formation]
    for family,count in zip(("GK","DEF","MID","FWD"),slots):
        for _ in range(count):
            candidate=next((p for p in remaining
                 if _family(p.get("position"))==family),None)
            if candidate is None:break
            selected.append(candidate)
            remaining.remove(candidate)
    while len(selected)<min(11,len(players)):
        selected.append(remaining.pop(0))
    return selected,remaining

def prepare_tactics(conn,*,career_id,players):
    """Reconcile saved selections with today's real projected squad.

    Signed departures disappear and signed new arrivals become reserves;
    retired/invalid references cannot be resurrected by the saved JSON.
    """
    roster={int(p["player_id"]):p for p in players}
    ordered=sorted(players,key=lambda p:(-int(p.get("overall") or 0),
                                         p.get("full_name") or ""))
    row=conn.execute("""SELECT formation,layout_json
        FROM world_career_tactics_layout WHERE career_id=?""",
        (career_id,)).fetchone()
    if row:
        try:
            stored=json.loads(row["layout_json"])
        except (ValueError,TypeError):
            stored={}
        formation=row["formation"] if row["formation"] in FORMATIONS else DEFAULT_FORMATION
        used=set()
        xi=[]
        for entry in stored.get("xi",[]):
            if not isinstance(entry,dict):continue
            pid=entry.get("player_id")
            if type(pid) is not int or pid not in roster or pid in used:continue
            try:
                x,y=float(entry["x"]),float(entry["y"])
            except (ValueError,TypeError,KeyError):
                continue
            xi.append(dict(player_id=pid,x=max(7,min(93,x)),y=max(8,min(94,y))))
            used.add(pid)
            if len(xi)>=11:break
        bench=[]
        for pid in stored.get("bench",[]):
            if type(pid) is int and pid in roster and pid not in used:
                bench.append(pid);used.add(pid)
                if len(bench)>=BENCH_LIMIT:break
        reserves=[]
        for pid in stored.get("reserves",[]):
            if type(pid) is int and pid in roster and pid not in used:
                reserves.append(pid);used.add(pid)
        missing=[int(p["player_id"]) for p in ordered if int(p["player_id"]) not in used]
        while len(xi)<min(11,len(roster)) and missing:
            pid=missing.pop(0)
            x,y=FORMATIONS[formation][len(xi)]
            xi.append(dict(player_id=pid,x=x,y=y))
        while len(bench)<BENCH_LIMIT and missing:bench.append(missing.pop(0))
        reserves+=missing
        # Ensure initial XI has no unintended 12th player after inconsistent state.
        if len(xi)>11:xi=xi[:11]
    else:
        formation=DEFAULT_FORMATION
        starters,remaining=_lineup_players(ordered,formation)
        xi=[dict(player_id=int(p["player_id"]),
                 x=FORMATIONS[formation][i][0],y=FORMATIONS[formation][i][1])
            for i,p in enumerate(starters)]
        bench=[int(p["player_id"]) for p in remaining[:BENCH_LIMIT]]
        reserves=[int(p["player_id"]) for p in remaining[BENCH_LIMIT:]]
    return {"formation":formation,"xi":xi,"bench":bench,"reserves":reserves,
            "players":[{"player_id":int(p["player_id"]),"name":p["full_name"],
                         "position":p.get("position") or "—",
                         "overall":int(p.get("overall") or 0),
                         "incoming":bool(p.get("incoming",False))}
                       for p in ordered],"bench_limit":BENCH_LIMIT,
            "formations":FORMATIONS}

def save_tactics(conn,*,career_id,payload):
    """Validate against CURRENT projected squad, never browser-supplied roster."""
    from world_squad_desk import squad_preview
    if not isinstance(payload,dict):raise ValueError("Invalid tactical layout")
    formation=payload.get("formation")
    if formation not in FORMATIONS:raise ValueError("Select a supported formation")
    squad=squad_preview(conn,career_id=career_id)
    allowed={int(p["player_id"]) for p in squad["players"]}
    if not 11<=len(allowed):raise ValueError("At least 11 eligible players required")
    xi=payload.get("xi")
    bench=payload.get("bench")
    reserves=payload.get("reserves")
    if not isinstance(xi,list) or len(xi)!=11:
        raise ValueError("Your starting XI must contain exactly eleven players")
    if not isinstance(bench,list) or len(bench)>BENCH_LIMIT:
        raise ValueError("Only seven substitutes may be named")
    if not isinstance(reserves,list):raise ValueError("Invalid reserves")
    ids=[]
    normalised=[]
    for entry in xi:
        if not isinstance(entry,dict):raise ValueError("Invalid starting XI player")
        pid=entry.get("player_id")
        if type(pid) is not int:raise ValueError("Invalid player ID")
        try:
            x,y=float(entry["x"]),float(entry["y"])
        except (TypeError,ValueError,KeyError):
            raise ValueError("Invalid tactical location")
        if not 7<=x<=93 or not 8<=y<=94:
            raise ValueError("Player location is outside the pitch")
        ids.append(pid)
        normalised.append({"player_id":pid,"x":round(x,1),"y":round(y,1)})
    for group in (bench,reserves):
        if any(type(pid) is not int for pid in group):
            raise ValueError("Unknown player")
        ids.extend(group)
    if len(ids)!=len(set(ids)):
        raise ValueError("A player cannot occupy more than one squad slot")
    if set(ids)!=allowed:
        raise ValueError("Squad selection has changed; refresh and review the new signings")
    saved={"xi":normalised,"bench":bench,"reserves":reserves}
    conn.execute("""INSERT INTO world_career_tactics_layout
        (career_id,formation,layout_json) VALUES(?,?,?)
        ON CONFLICT(career_id) DO UPDATE SET
          formation=excluded.formation,
          layout_json=excluded.layout_json,updated_at=CURRENT_TIMESTAMP""",
        (career_id,formation,json.dumps(saved,separators=(",",":"))))
    conn.commit()
    return {"formation":formation,"xi":normalised,
            "bench":bench,"reserves":reserves}

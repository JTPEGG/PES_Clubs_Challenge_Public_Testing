"""Read-only Football Manager-style scouting for a saved development career.

Uses registered career squads, dataset attributes and source-backed dates.
Never guesses a contract expiry or individual PES attribute. Approximate
market values come from the existing labelled economy model.
"""
from datetime import date
from world_careers import _player_reference

SORT_COLUMNS=frozenset(('overall','age','market_value','pace','shooting','passing','dribbling','defending','physicality','years_left','full_name'))


GROUPS={"GK":"GK","DEF":"DEF","MID":"MID","FWD":"FWD"}
CATEGORIES=("pace","shooting","passing","dribbling","defending","physicality")


def scouting_attributes(conn, *, career_id):
    row=conn.execute("""SELECT d.season_id FROM world_career_saves c
        JOIN world_datasets d ON d.dataset_id=c.dataset_id
        WHERE c.career_id=?""",(career_id,)).fetchone()
    if not row:return []
    return [r[0] for r in conn.execute("""SELECT DISTINCT attribute_name
        FROM world_player_attributes WHERE effective_season=?
        ORDER BY attribute_name""",(row[0],)).fetchall()]


def scouting_search(conn, *, career_id, query="", position="", min_overall=None,
                    max_age=None, category="", min_category=None,
                    attribute="", min_attribute=None, contract="",
                    squad_only=False, limit=80, sort_by='overall', descending=True, shortlist_only=False):
    from world_ai_bidding import position_family
    save=conn.execute("""SELECT dataset_id,manager_club_id,pes_lock_date
        FROM world_career_saves WHERE career_id=? AND state='sandbox'""",
        (career_id,)).fetchone()
    if save is None:raise ValueError("Unknown development career")
    dataset,manager,asof=save
    season=conn.execute("SELECT season_id FROM world_datasets WHERE dataset_id=?",
                        (dataset,)).fetchone()[0]
    attr_names=scouting_attributes(conn,career_id=career_id)
    if attribute not in attr_names:attribute=""
    if category not in CATEGORIES:category=""
    if position not in GROUPS:position=""
    if contract not in ("","expiring","known","unknown"):contract=""
    min_overall= max(1,min(99,int(min_overall))) if min_overall is not None else None
    max_age=max(16,min(65,int(max_age))) if max_age is not None else None
    min_category=max(1,min(99,int(min_category))) if min_category is not None else None
    min_attribute=max(1,min(99,int(min_attribute))) if min_attribute is not None else None
    q=query.strip()[:70].lower()
    if sort_by not in SORT_COLUMNS:sort_by='overall'
    initialise_scouting(conn)
    saved_ids={r[0] for r in conn.execute('SELECT player_id FROM world_career_scout_shortlist WHERE career_id=?',(career_id,)).fetchall()}

    # Only actual source-backed current-club contracts are displayed as fact.
    # For no source contract, display "Unknown" rather than invented expiry.
    rows=conn.execute("""SELECT r.player_id,r.club_id,c.name club_name,
        p.full_name,p.birth_date,p.primary_position,
        x.overall,x.pace,x.shooting,x.passing,x.dribbling,x.defending,x.physicality,
        (SELECT wc.expires FROM world_contracts wc
         WHERE wc.player_id=r.player_id AND wc.club_id=r.club_id
           AND wc.expires IS NOT NULL AND wc.source_url IS NOT NULL
         ORDER BY wc.expires DESC LIMIT 1) expires,
        (SELECT a.value FROM world_player_attributes a
         WHERE a.player_id=r.player_id AND a.effective_season=?
           AND a.attribute_name=? LIMIT 1) detail_attribute
        FROM world_career_registrations r
        JOIN world_clubs c ON c.club_id=r.club_id
        JOIN world_players p ON p.player_id=r.player_id
        JOIN world_dataset_ratings x ON x.dataset_id=? AND x.player_id=r.player_id
        WHERE r.career_id=? AND x.overall BETWEEN 1 AND 99
          AND (?=0 OR r.club_id=?)
          AND (?='' OR lower(p.full_name) LIKE ?)
        ORDER BY x.overall DESC,p.full_name,r.player_id""",
        (season,attribute,dataset,career_id,int(bool(squad_only)),manager,
         q,"%"+q.replace("%","\\%").replace("_","\\_")+"%")).fetchall()
    # Individual scoring/filter choices do not mutate club or player records.
    out=[]
    anchor=date.fromisoformat(asof)
    for r in rows:
        d=dict(r)
        d["shortlisted"]=d["player_id"] in saved_ids
        if shortlist_only and not d["shortlisted"]:continue
        if position and position_family(d["primary_position"])!=position:
            continue
        if min_overall is not None and d["overall"]<min_overall:continue
        try:
            birth=date.fromisoformat(d["birth_date"]) if d["birth_date"] else None
            age=(anchor.year-birth.year-((anchor.month,anchor.day)<(birth.month,birth.day))) if birth else None
        except ValueError:
            age=None
        if max_age is not None and (age is None or age>max_age):continue
        d["age"]=age
        expiry=None
        try:
            expiry=date.fromisoformat(d["expires"]) if d["expires"] else None
        except ValueError:
            pass
        remaining=max(0,(expiry-anchor).days) if expiry else None
        d["years_left"]=round(remaining/365.25,1) if remaining is not None else None
        if contract=="known" and not expiry:continue
        if contract=="unknown" and expiry:continue
        if contract=="expiring" and (remaining is None or remaining>365):continue
        if category and min_category is not None and (
            d[category] is None or d[category]<min_category):continue
        if attribute and min_attribute is not None and (
            d["detail_attribute"] is None or d["detail_attribute"]<min_attribute):continue
        value,_=_player_reference(conn,dataset,d["player_id"])
        d["market_value"]=value
        d["owned"]=d["club_id"]==manager
        out.append(d)
    def sort_key(d):
        v=d.get(sort_by)
        # Unknown values always appear last, regardless of sort direction.
        if sort_by=="full_name":return (v is None,str(v or "").lower())
        return (v is None,-v if descending and v is not None else v if v is not None else 0)
    out.sort(key=sort_key)
    return out[:limit]


SHORTLIST_SCHEMA="""
CREATE TABLE IF NOT EXISTS world_career_scout_shortlist(
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 saved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(career_id,player_id)
);
"""


def initialise_scouting(conn):
    conn.executescript(SHORTLIST_SCHEMA)
    conn.commit()


def set_shortlisted(conn,*,career_id,player_id,save):
    player=conn.execute("""SELECT r.player_id FROM world_career_registrations r
        JOIN world_career_saves c ON c.career_id=r.career_id
        WHERE r.career_id=? AND r.player_id=? AND c.state='sandbox'""",
        (career_id,player_id)).fetchone()
    if player is None:raise ValueError("Player not found in this career")
    if save:
        conn.execute("""INSERT OR IGNORE INTO world_career_scout_shortlist
            (career_id,player_id) VALUES(?,?)""",(career_id,player_id))
    else:
        conn.execute("""DELETE FROM world_career_scout_shortlist
            WHERE career_id=? AND player_id=?""",(career_id,player_id))
    conn.commit()


def player_profile(conn,*,career_id,player_id):
    name=conn.execute("""SELECT p.full_name FROM world_players p
        JOIN world_career_registrations r ON r.player_id=p.player_id
        WHERE r.career_id=? AND p.player_id=?""",
        (career_id,player_id)).fetchone()
    if name is None:raise ValueError("Player not registered in this career")
    result=scouting_search(conn,career_id=career_id,limit=100,
                           query=name[0],sort_by="overall")
    info=next((row for row in result if row["player_id"]==player_id),None)
    if info is None:raise ValueError("Player does not have a source overall rating")
    ds=conn.execute("""SELECT d.season_id FROM world_datasets d
        JOIN world_career_saves c ON c.dataset_id=d.dataset_id
        WHERE c.career_id=?""",(career_id,)).fetchone()[0]
    info["attributes"]=[dict(name=r[0],value=r[1]) for r in conn.execute("""
        SELECT attribute_name,value FROM world_player_attributes
        WHERE effective_season=? AND player_id=? ORDER BY attribute_name""",
        (ds,player_id)).fetchall()]
    info["wage_guidance"]=max(1000,min(250000,
        round(1000*2**((info["overall"]-55)/8)/500)*500))
    return info


def recruitment_recommendations(conn, *, career_id, limit=8):
    """Explainable, conservative recruitment targets from real career ratings.

    Short contracts are only labelled when source-backed expiry is known.
    Budget fit and positional upgrades are signals, never guarantees that a
    seller or footballer will agree to the move.
    """
    from world_ai_bidding import position_family
    from world_careers import budget_remaining,wage_budget_breakdown
    career=conn.execute("""SELECT manager_club_id FROM world_career_saves
        WHERE career_id=? AND state='sandbox'""",(career_id,)).fetchone()
    if career is None:raise ValueError("Unknown development career")
    manager=career[0]
    funds=max(0,budget_remaining(conn,career_id,manager))
    wage=max(0,wage_budget_breakdown(conn,career_id,manager)["remaining"])
    squad=scouting_search(conn,career_id=career_id,squad_only=True,limit=200,
                          sort_by="overall")
    by_family={}
    for p in squad:
        family=position_family(p["primary_position"])
        if family:
            by_family.setdefault(family,[]).append(p["overall"])
    # Evaluate a finite, strong set from the dataset; show no recommendation
    # where affordability or rating evidence is insufficient.
    candidates=scouting_search(conn,career_id=career_id,limit=1000,
                               sort_by="overall")
    results=[]
    for p in candidates:
        if p["owned"] or not p["market_value"] or p["market_value"]>funds:
            continue
        family=position_family(p["primary_position"])
        ratings=by_family.get(family,[])
        if not ratings:continue
        baseline=sorted(ratings,reverse=True)[min(2,len(ratings)-1)]
        upgrade=p["overall"]-baseline
        if upgrade<2:continue
        expected=max(1000,min(250000,
            round(1000*2**((p["overall"]-55)/8)/500)*500))
        if expected>wage:continue
        reasons=[]
        if len(ratings)<3:reasons.append("Thin positional depth")
        if upgrade>=5:reasons.append(f"+{upgrade} OVR over positional third choice")
        else:reasons.append(f"+{upgrade} OVR over positional third choice")
        if p["years_left"] is not None and p["years_left"]<=1.0:
            reasons.append("Source-backed contract expiry within 12 months")
        if p["market_value"]<=funds*0.35:
            reasons.append("Indicative fee below 35% of available funds")
        if p["age"] is not None and p["age"]<=23:
            reasons.append("Young prospect")
        results.append({**p,"reasons":reasons,"wage_guidance":expected,
                        "upgrade":upgrade,
                        "score":upgrade*5+(12 if len(ratings)<3 else 0)+
                            (6 if p["years_left"] is not None and
                                 p["years_left"]<=1.0 else 0)+
                            (4 if p["market_value"]<=funds*0.35 else 0)})
    results.sort(key=lambda item:(-item["score"],-item["overall"],item["player_id"]))
    return results[:limit]

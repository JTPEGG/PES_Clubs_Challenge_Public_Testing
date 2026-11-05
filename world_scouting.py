"""Read-only Football Manager-style scouting for a saved development career.

Uses registered career squads, dataset attributes and source-backed dates.
Never guesses a contract expiry or individual PES attribute. Approximate
market values come from the existing labelled economy model.
"""
from datetime import date
from collections import defaultdict, OrderedDict
from threading import Lock
from time import monotonic
from world_careers import _player_reference, age_on
from world_valuation import model_value, fc27_game_reference_value

SORT_COLUMNS=frozenset(('overall','age','market_value','pace','shooting','passing','dribbling','defending','physicality','years_left','full_name'))


GROUPS={"GK":"GK","DEF":"DEF","MID":"MID","FWD":"FWD"}
CATEGORIES=("pace","shooting","passing","dribbling","defending","physicality")

# The source attribute aggregation scans half a million ratings. Cache its
# immutable base rows across filter changes, rather than scanning SQLite for
# every click. Limit retained careers/attributes so memory stays bounded.
_SCOUT_CACHE=OrderedDict()
_SCOUT_CACHE_LOCK=Lock()
_SCOUT_CACHE_TTL=90
_SCOUT_CACHE_LIMIT=4

def _cached_scout_rows(key):
    with _SCOUT_CACHE_LOCK:
        entry=_SCOUT_CACHE.get(key)
        if not entry:return None
        if monotonic()-entry[0]>_SCOUT_CACHE_TTL:
            del _SCOUT_CACHE[key]
            return None
        _SCOUT_CACHE.move_to_end(key)
        return entry[1]

def _remember_scout_rows(key,rows):
    with _SCOUT_CACHE_LOCK:
        _SCOUT_CACHE[key]=(monotonic(),rows)
        _SCOUT_CACHE.move_to_end(key)
        while len(_SCOUT_CACHE)>_SCOUT_CACHE_LIMIT:
            _SCOUT_CACHE.popitem(last=False)


def scouting_attributes(conn, *, career_id):
    row=conn.execute("""SELECT d.season_id FROM world_career_saves c
        JOIN world_datasets d ON d.dataset_id=c.dataset_id
        WHERE c.career_id=?""",(career_id,)).fetchone()
    if not row:return []
    source=conn.execute("""SELECT dataset_id FROM world_career_saves
        WHERE career_id=?""",(career_id,)).fetchone()
    if source and source[0]=="fc27-warehouse-659-mens-2026-27":
        return [r[0].removeprefix("PES2020V2:") for r in conn.execute(
            """SELECT DISTINCT attribute FROM world_dataset_extended_attributes
            WHERE dataset_id=? AND attribute LIKE 'PES2020V2:%'
            ORDER BY attribute""",(source[0],)).fetchall()]
    return [r[0] for r in conn.execute("""SELECT DISTINCT attribute_name
        FROM world_player_attributes WHERE effective_season=?
        ORDER BY attribute_name""",(row[0],)).fetchall()]


def scouting_search(conn, *, career_id, query="", position="", min_overall=None,
                    max_age=None, category="", min_category=None,
                    attribute="", min_attribute=None, contract="",
                    squad_only=False, limit=80, sort_by='overall', descending=True,
                    shortlist_only=False, offset=0, with_total=False,
                    max_market_value=None, interested_only=False):
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
    max_market_value=(max(0,int(max_market_value))
        if max_market_value is not None else None)
    interested_only=bool(interested_only)
    if sort_by not in SORT_COLUMNS:sort_by='overall'
    initialise_scouting(conn)
    saved_ids={r[0] for r in conn.execute('SELECT player_id FROM world_career_scout_shortlist WHERE career_id=?',(career_id,)).fetchall()}

    # The 659-club FC27 source stores all 29 converted PES ratings and
    # individual starting-game contracts in dataset-specific tables. The
    # original England-style columns and scraped world contracts are empty
    # for this warehouse. Never confuse a missing legacy field with no data.
    if dataset=="fc27-warehouse-659-mens-2026-27":
        # Clearly derived *game* six-category averages: these are not
        # additional independently sourced FC27 ratings. All components
        # come from the approved 29-attribute PES2020 V2 conversion.
        base_key=(career_id,attribute)
        rows=_cached_scout_rows(base_key)
        if rows is None:
            rows=conn.execute("""WITH fc27 AS (
          SELECT player_id,
          CAST(ROUND(AVG(CASE WHEN attribute IN (
            'PES2020V2:speed','PES2020V2:acceleration') THEN value END)) AS INT) pace,
          CAST(ROUND(AVG(CASE WHEN attribute IN (
            'PES2020V2:finishing','PES2020V2:kicking_power',
            'PES2020V2:offensive_awareness') THEN value END)) AS INT) shooting,
          CAST(ROUND(AVG(CASE WHEN attribute IN (
            'PES2020V2:low_pass','PES2020V2:lofted_pass') THEN value END)) AS INT) passing,
          CAST(ROUND(AVG(CASE WHEN attribute IN (
            'PES2020V2:ball_control','PES2020V2:dribbling',
            'PES2020V2:tight_possession') THEN value END)) AS INT) dribbling,
          CAST(ROUND(AVG(CASE WHEN attribute IN (
            'PES2020V2:defensive_awareness','PES2020V2:ball_winning',
            'PES2020V2:aggression') THEN value END)) AS INT) defending,
          CAST(ROUND(AVG(CASE WHEN attribute IN (
            'PES2020V2:physical_contact','PES2020V2:balance',
            'PES2020V2:stamina','PES2020V2:jump') THEN value END)) AS INT) physicality,
          MAX(CASE WHEN attribute=? THEN value END) detail_attribute
          FROM world_dataset_extended_attributes WHERE dataset_id=?
          GROUP BY player_id
        )
        SELECT r.player_id,r.club_id,c.name club_name,
          p.full_name,p.birth_date,p.primary_position,x.overall,
          a.pace,a.shooting,a.passing,a.dribbling,a.defending,a.physicality,
          cs.expires_on AS expires,cs.weekly_wage_gbp AS current_wage,
          a.detail_attribute
        FROM world_career_registrations r
        JOIN world_clubs c ON c.club_id=r.club_id
        JOIN world_players p ON p.player_id=r.player_id
        JOIN world_dataset_ratings x ON x.dataset_id=? AND x.player_id=r.player_id
        LEFT JOIN fc27 a ON a.player_id=r.player_id
        LEFT JOIN world_career_contract_snapshots cs
          ON cs.career_id=r.career_id AND cs.player_id=r.player_id
        WHERE r.career_id=? AND x.overall BETWEEN 1 AND 99
          AND (?=0 OR r.club_id=?)
          AND (?='' OR lower(p.full_name) LIKE ?)
        ORDER BY x.overall DESC,p.full_name,r.player_id""",
        ("PES2020V2:"+attribute if attribute else "",
         dataset,dataset,career_id,0,manager,"","%")).fetchall()
            _remember_scout_rows(base_key,rows)
    else:
        # Older datasets preserve their own documented source-backed fields.
        rows=conn.execute("""SELECT r.player_id,r.club_id,c.name club_name,
            p.full_name,p.birth_date,p.primary_position,
            x.overall,x.pace,x.shooting,x.passing,x.dribbling,x.defending,x.physicality,
            (SELECT wc.expires FROM world_contracts wc
             WHERE wc.player_id=r.player_id AND wc.club_id=r.club_id
               AND wc.expires IS NOT NULL AND wc.source_url IS NOT NULL
             ORDER BY wc.expires DESC LIMIT 1) expires,
            (SELECT a.value FROM world_player_attributes a
             WHERE a.player_id=r.player_id AND a.effective_season=?
               AND a.attribute_name=? LIMIT 1) detail_attribute,
            NULL AS current_wage
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
    # Market-value sorting and caps use the exact existing game model, but
    # evaluate wages in ONE bulk read rather than 17,593 reference SQL calls.
    require_values=(sort_by=="market_value" or max_market_value is not None)
    source_date=None
    source_wages={}
    if require_values:
        source_date=conn.execute("""SELECT source_date FROM world_datasets
            WHERE dataset_id=?""",(dataset,)).fetchone()[0]
        if dataset=="fc27-warehouse-659-mens-2026-27":
            source_wages=dict(conn.execute("""SELECT player_id,weekly_wage_gbp
                FROM world_dataset_contract_snapshots
                WHERE dataset_id=?""",(dataset,)).fetchall())

    # This is a provisional FC27 V2 *interest screen*, NOT a claim that
    # players consent to any fee, wage, or registration. Reuse the actual
    # player-choice decision function, source-rated club appeal and modelled
    # squad roles rather than a hard-coded club list (e.g. Haaland/Hull).
    interest_context=None
    if interested_only and dataset=="fc27-warehouse-659-mens-2026-27":
        from world_fc27_ai_recruitment import read_fc27_profiles
        from world_player_decisions import evaluate_player_choice_v2
        from world_ai_bidding import position_family
        profiles=read_fc27_profiles(conn,dataset=dataset)
        prestige=dict(conn.execute("""SELECT club_id,prestige_score
            FROM world_career_prestige_snapshots WHERE career_id=?""",
            (career_id,)).fetchall())
        changes={r[0]:r for r in conn.execute(
            """SELECT player_id,current_wage_weekly,current_role,
               transfer_listed,renewal_status
               FROM world_career_player_circumstances WHERE career_id=?""",
            (career_id,)).fetchall()}
        next_summer=conn.execute("""SELECT next_summer_date
            FROM world_career_saves WHERE career_id=?""",(career_id,)).fetchone()[0]
        ranks=defaultdict(int)
        goalie_ranks=defaultdict(int)
        roles={}
        for player in sorted(rows,key=lambda r:(r["club_id"],-r["overall"],r["player_id"])):
            club=player["club_id"]
            rank=ranks[club]
            ranks[club]+=1
            if position_family(player["primary_position"])=="GK":
                gk_rank=goalie_ranks[club]
                goalie_ranks[club]+=1
                role=("key_player" if gk_rank==0 and rank<3 else
                      "regular_starter" if gk_rank==0 else
                      "rotation" if gk_rank==1 else "fringe")
            else:
                role=("key_player" if rank<3 else "regular_starter"
                      if rank<11 else "rotation" if rank<18 else "fringe")
            roles[player["player_id"]]=role
        interest_context=(profiles,prestige,changes,roles,next_summer,
                          evaluate_player_choice_v2)

    out=[]
    anchor=date.fromisoformat(asof)
    for r in rows:
        d=dict(r)
        if q and q not in d["full_name"].lower():continue
        if squad_only and d["club_id"]!=manager:continue
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
        d["owned"]=d["club_id"]==manager
        if interested_only and not d["owned"] and interest_context is not None:
            profiles,prestige,changes,roles,next_summer,evaluate=interest_context
            seller=profiles.get(d["club_id"])
            buyer=profiles.get(manager)
            changed=changes.get(d["player_id"])
            current_role=changed[2] if changed else roles.get(d["player_id"],"unknown")
            listed=(bool(changed[3]) if changed else
                    current_role=="fringe" and bool(d["expires"])
                    and d["expires"]<=next_summer)
            renewal=(changed[4] if changed else
                     "not_offered" if listed else "renewal_offered")
            wage=(changed[1] if changed and changed[1] is not None
                  else d["current_wage"])
            if not buyer or not seller or d["age"] is None or wage is None:
                continue  # Not enough evidence to positively signal interest.
            choice=evaluate(
                buyer_tier=1,seller_tier=1,  # FC27 source tiers remain unknown.
                buyer_score=int(buyer["sporting_appeal"]),
                seller_score=int(seller["sporting_appeal"]),
                buyer_prestige=int(prestige.get(manager) or buyer["sporting_appeal"]),
                seller_prestige=int(prestige.get(d["club_id"]) or seller["sporting_appeal"]),
                overall=d["overall"],age=d["age"],current_wage=int(wage),
                current_role=current_role,transfer_listed=listed,
                renewal_status=renewal,offered_wage=None,
                role_promise="regular_starter",
                allow_unknown_europe_neutral=True)
            if not choice["can_negotiate"]:
                continue
        if require_values:
            baseline=model_value(d["overall"],age_on(d["birth_date"],source_date),
                                 d["primary_position"])
            if dataset=="fc27-warehouse-659-mens-2026-27" and baseline is not None:
                baseline=fc27_game_reference_value(
                    baseline=baseline,overall=d["overall"],
                    weekly_wage=source_wages.get(d["player_id"]))
            d["market_value"]=baseline
            if max_market_value is not None and (
                    baseline is None or baseline>max_market_value):
                continue
        else:
            d["market_value"]=None
        out.append(d)
    def sort_key(d):
        v=d.get(sort_by)
        # Unknown values always appear last, regardless of sort direction.
        if sort_by=="full_name":return (v is None,str(v or "").lower())
        return (v is None,-v if descending and v is not None else v if v is not None else 0)
    out.sort(key=sort_key)
    total=len(out)
    offset=max(0,int(offset))
    limit=max(1,int(limit))
    page=out[offset:offset+limit]
    if sort_by!="market_value":
        for d in page:
            d["market_value"]=_player_reference(conn,dataset,d["player_id"])[0]
    return (page,total) if with_total else page


SHORTLIST_SCHEMA="""
CREATE TABLE IF NOT EXISTS world_career_scout_shortlist(
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 saved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(career_id,player_id)
);
"""


def initialise_scouting(conn):
    # Avoid executescript's implicit transaction commit on every filter click.
    if conn.execute("""SELECT 1 FROM sqlite_master
        WHERE type='table' AND name='world_career_scout_shortlist'""").fetchone() is None:
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
    source=conn.execute("""SELECT dataset_id FROM world_career_saves
       WHERE career_id=?""",(career_id,)).fetchone()[0]
    if source=="fc27-warehouse-659-mens-2026-27":
        info["attributes"]=[dict(name=r[0].removeprefix("PES2020V2:"),value=r[1])
            for r in conn.execute("""SELECT attribute,value FROM
                world_dataset_extended_attributes WHERE dataset_id=?
                AND player_id=? AND attribute LIKE 'PES2020V2:%'
                ORDER BY attribute""",(source,player_id)).fetchall()]
        contract=conn.execute("""SELECT weekly_wage_gbp,expires_on,source_kind
            FROM world_career_contract_snapshots WHERE career_id=?
            AND player_id=?""",(career_id,player_id)).fetchone()
        if contract:
            info["source_game_wage"]=contract[0]
            info["contract_source"]=contract[2]
        else:
            info["source_game_wage"]=None
            info["contract_source"]=None
        info["wage_guidance"]=info["source_game_wage"]
    else:
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

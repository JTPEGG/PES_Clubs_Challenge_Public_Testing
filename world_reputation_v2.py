"""Versioned cross-division sporting appeal, without artificial league cliffs.

v1's immutable reputation rows are deliberately left untouched.
v2 uses a *shared* 0-100 squad-ability scale with a small division-context
adjustment and a tiny squad-strength rank adjustment. The latter is NOT a
league table or a prediction of promotion/relegation.

Institutional prestige remains unknown until sourced independently.
"""
import math
import sqlite3
from collections import defaultdict
from statistics import median

MODEL_VERSION = "rep-pyramid-v2"
TOP_PLAYERS = 16
MIN_RATED_PLAYERS = 8
# Explicit game-design *context* only. Small steps leave room for adjacent
# divisions to overlap: top Championship teams can exceed weak PL teams.
ENGLISH_DIVISION_CONTEXT = {"ENG1": 4, "ENG2": 0, "ENG3": -4, "ENG4": -8}

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_pyramid_league_strength (
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 model_version TEXT NOT NULL,
 competition_id TEXT NOT NULL REFERENCES world_competitions(competition_id),
 median_squad_average REAL,
 teams_rated INTEGER NOT NULL,
 teams_total INTEGER NOT NULL,
 context_adjustment INTEGER NOT NULL,
 league_prestige INTEGER,
 method TEXT NOT NULL,
 PRIMARY KEY (dataset_id,model_version,competition_id)
);
CREATE TABLE IF NOT EXISTS world_pyramid_club_appeal (
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 model_version TEXT NOT NULL,
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 competition_id TEXT NOT NULL REFERENCES world_competitions(competition_id),
 sporting_appeal INTEGER CHECK (sporting_appeal IS NULL OR sporting_appeal BETWEEN 0 AND 100),
 institutional_prestige INTEGER CHECK (institutional_prestige IS NULL OR institutional_prestige BETWEEN 0 AND 100),
 squad_average REAL,
 sample_players INTEGER NOT NULL,
 roster_players INTEGER NOT NULL,
 strength_component INTEGER,
 division_adjustment INTEGER NOT NULL,
 prospects_adjustment INTEGER NOT NULL,
 strength_rank INTEGER,
 competition_size INTEGER NOT NULL,
 prospects_label TEXT NOT NULL,
 confidence TEXT NOT NULL CHECK(confidence IN ('squad-proxy','limited-squad','unassessed')),
 source_label TEXT NOT NULL,
 source_date TEXT,
 PRIMARY KEY(dataset_id,model_version,club_id)
);
CREATE INDEX IF NOT EXISTS world_pyramid_club_comp
 ON world_pyramid_club_appeal(dataset_id,model_version,competition_id);
"""


def clamp(value,lo=0,hi=100):
    return min(hi,max(lo,value))


def common_strength(average):
    """One shared scale for all English divisions; NOT their actual prestige."""
    if average is None:
        return None
    return round(35+2.3*(average-60))


def rank_adjustment(rank, total):
    """Small, transparent proxy for prospects, never actual table standing."""
    if rank is None or total is None or total<4:
        return 0,"Not assessed"
    group=max(2,math.ceil(total*0.16))
    if rank<=group:
        return 1,"Strong upper-end squad (not a predicted finish)"
    if rank>total-group:
        return -1,"Weak lower-end squad (not a predicted finish)"
    return 0,"Middle-strength squad (not a predicted finish)"


def calculate_appeal(average, competition_id, *, rank=None, competition_size=None):
    """Return named score components to make every comparison auditable."""
    context=ENGLISH_DIVISION_CONTEXT.get(competition_id)
    if context is None:
        return {"sporting_appeal":None,"strength_component":None,
                "division_adjustment":0,"prospects_adjustment":0,
                "prospects_label":"League not configured"}
    if average is None:
        return {"sporting_appeal":None,"strength_component":None,
                "division_adjustment":context,"prospects_adjustment":0,
                "prospects_label":"Unassessed: insufficient player ratings"}
    strength=common_strength(average)
    prospects,label=rank_adjustment(rank,competition_size)
    return {"sporting_appeal":clamp(strength+context+prospects,10,99),
            "strength_component":strength,"division_adjustment":context,
            "prospects_adjustment":prospects,"prospects_label":label}


def initialize_pyramid(conn):
    """Immutable snapshots keyed by dataset and version, with safe partial import.

    As datasets are appended, old v1 and v2 rows for other seasons remain
    intact. A new algorithm must use a NEW version, not overwrite this one.
    """
    conn.executescript(SCHEMA)
    datasets=conn.execute("""SELECT dataset_id,source_label,source_date
                              FROM world_datasets""").fetchall()
    for dataset_id,source_label,source_date in datasets:
        entries=conn.execute("""SELECT e.club_id,e.competition_id,c.name FROM world_dataset_entries e
             JOIN world_clubs c ON c.club_id=e.club_id WHERE e.dataset_id=?""",
             (dataset_id,)).fetchall()
        if not entries:
            continue
        supported=[row for row in entries if row[1] in ENGLISH_DIVISION_CONTEXT]
        if not supported:
            continue
        already=conn.execute("""SELECT COUNT(*) FROM world_pyramid_club_appeal
            WHERE dataset_id=? AND model_version=?""",
            (dataset_id,MODEL_VERSION)).fetchone()[0]
        already_leagues=conn.execute("""SELECT COUNT(*) FROM world_pyramid_league_strength
            WHERE dataset_id=? AND model_version=?""",
            (dataset_id,MODEL_VERSION)).fetchone()[0]
        target_leagues={r[1] for r in supported}
        if already==len(supported) and already_leagues==len(target_leagues):
            continue

        roster_counts=dict(conn.execute("""SELECT club_id,COUNT(*)
            FROM world_dataset_rosters WHERE dataset_id=? GROUP BY club_id""",
            (dataset_id,)).fetchall())
        ratings=defaultdict(list)
        for club_id,overall in conn.execute("""SELECT r.club_id,x.overall
            FROM world_dataset_rosters r
            JOIN world_dataset_ratings x ON x.player_id=r.player_id
               AND x.dataset_id=r.dataset_id
            WHERE r.dataset_id=?""",(dataset_id,)):
            if type(overall) is int and 1<=overall<=99:
                ratings[club_id].append(overall)
        memberships=defaultdict(list)
        for club_id,comp,name in supported:
            memberships[comp].append((club_id,name))
        sample_averages={}
        for club_id,comp,name in supported:
            top=sorted(ratings.get(club_id,[]),reverse=True)[:TOP_PLAYERS]
            sample_averages[club_id]=(sum(top)/len(top)
                                      if len(top)>=MIN_RATED_PLAYERS else None)
        for comp,members in memberships.items():
            available=[(cid,name,sample_averages[cid])
                       for cid,name in members if sample_averages[cid] is not None]
            ranks={cid:i+1 for i,(cid,_,_) in enumerate(
                sorted(available,key=lambda x:(-x[2],x[1])))}
            typical=median([x[2] for x in available]) if available else None
            conn.execute("""INSERT OR IGNORE INTO world_pyramid_league_strength
                (dataset_id,model_version,competition_id,median_squad_average,
                 teams_rated,teams_total,context_adjustment,league_prestige,method)
                VALUES(?,?,?,?,?,?,?,NULL,?)""",
                (dataset_id,MODEL_VERSION,comp,round(typical,2) if typical is not None else None,
                 len(available),len(members),ENGLISH_DIVISION_CONTEXT[comp],
                 "Median of top-16 source OVR squad means; NOT institutional league prestige"))
            for club_id,name in members:
                average=sample_averages[club_id]
                rank=ranks.get(club_id)
                pieces=calculate_appeal(average,comp,rank=rank,
                    competition_size=len(members) if len(available)==len(members) else None)
                conn.execute("""INSERT OR IGNORE INTO world_pyramid_club_appeal
                    (dataset_id,model_version,club_id,competition_id,
                     sporting_appeal,institutional_prestige,squad_average,
                     sample_players,roster_players,strength_component,
                     division_adjustment,prospects_adjustment,strength_rank,
                     competition_size,prospects_label,confidence,source_label,source_date)
                    VALUES(?,?,?,?,?,NULL,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (dataset_id,MODEL_VERSION,club_id,comp,
                     pieces["sporting_appeal"],
                     round(average,2) if average is not None else None,
                     min(TOP_PLAYERS,len(ratings.get(club_id,[]))),
                     roster_counts.get(club_id,0),pieces["strength_component"],
                     pieces["division_adjustment"],pieces["prospects_adjustment"],
                     rank if len(available)==len(members) else None,
                     len(members),pieces["prospects_label"],
                     ("unassessed" if average is None else
                      "squad-proxy" if len(ratings.get(club_id,[]))>=TOP_PLAYERS else "limited-squad"),
                     source_label or "Not recorded",source_date))
    conn.commit()


def get_pyramid_appeal(conn,dataset_id,club_id):
    """No fallback to v1: unknown v2 values stay unknown."""
    try:
        row=conn.execute("""SELECT sporting_appeal,squad_average,confidence,prospects_label
            FROM world_pyramid_club_appeal WHERE dataset_id=?
            AND model_version=? AND club_id=?""",
            (dataset_id,MODEL_VERSION,club_id)).fetchone()
        if row is None:return None
        return {"score":row[0],"squad_average":row[1],
                "confidence":row[2],"prospects_label":row[3]}
    except sqlite3.OperationalError:
        return None


def assess_player_interest(*,buyer_tier,seller_tier,buyer_score,seller_score,
                           player_overall=None):
    """Gameplay sporting-barrier decision using *real overlap* between leagues.

    Cannot claim consent: this is a gate for approaching an agent, and a future
    player-response layer must still handle age, ambitions and competing bids.
    """
    if buyer_tier is None or seller_tier is None or buyer_score is None or seller_score is None:
        return {"decision":"review","can_negotiate":False,
                "reason":"Unassessed: comparable season-specific player and club data required"}
    gap=seller_score-buyer_score
    level_drop=buyer_tier-seller_tier
    # Truly large gaps remain hard refusals even at huge wages.
    if gap>=28 or (level_drop>=2 and gap>=18):
        return {"decision":"uninterested","can_negotiate":False,
                "reason":f"Large sporting-appeal decline ({gap:+d} points in seller's favour); wages cannot bypass this refusal"}
    if gap>=10 or (level_drop>=2 and gap>=5):
        return {"decision":"needs_assurances","can_negotiate":True,
                "reason":f"Sporting-appeal difference {gap:+d}; important/key-player role and greater financial terms are required"}
    if level_drop>=1 and gap>=6:
        return {"decision":"needs_assurances","can_negotiate":True,
                "reason":f"Move is down a division and sporting appeal is {gap} points lower; additional career assurances required"}
    if level_drop>=1 and gap>0:
        return {"decision":"open_to_talks","can_negotiate":True,
                "reason":f"Though a lower division, appeal is only {gap} points lower; promotion prospects and role still require evaluation"}
    if level_drop>=1 and gap<=0:
        return {"decision":"open_to_talks","can_negotiate":True,
                "reason":"Lower division has comparable or stronger squad-based appeal; no automatic divisional penalty"}
    return {"decision":"open_to_talks","can_negotiate":True,
            "reason":f"No severe sporting gap ({gap:+d} points in seller's favour); personal ambitions still unverified"}

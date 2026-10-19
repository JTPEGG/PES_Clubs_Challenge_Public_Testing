"""Source-conscious, career-isolated season-to-season reputation history.

This module NEVER infers match results, honours, actual table positions,
PES registrations, or financial changes. Season transitions require a complete
explicit set of attested club outcomes and a deliberate finalize call.

Base squad strength remains fixed until a separately sourced ratings update.
Direct promotion/relegation shifts are modest and result form is bounded.
Institutional prestige must be separately reviewed and sourced.
"""
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from urllib.parse import urlsplit

from world_reputation_v2 import (ENGLISH_DIVISION_CONTEXT, MODEL_VERSION as BASE_MODEL,
                                  initialize_pyramid)
from world_reputation_achievements import calculate_opportunity_bonuses

PROGRESSION_VERSION = "rep-career-progression-v2"
FINISH_ADJUSTMENTS = {"top": 2, "upper": 1, "middle": 0, "lower": -1, "bottom": -2}
PRESTIGE_CATEGORIES = ("honours", "european", "support", "infrastructure", "longevity")

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_reputation_prestige_evidence (
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 evidence_id TEXT NOT NULL,
 category TEXT NOT NULL CHECK(category IN
   ('honours','european','support','infrastructure','longevity')),
 factual_claim TEXT NOT NULL,
 source_url TEXT NOT NULL,
 published_date TEXT,
 review_state TEXT NOT NULL DEFAULT 'pending'
   CHECK(review_state IN ('pending','reviewed','rejected')),
 reviewed_by TEXT,
 PRIMARY KEY(dataset_id,club_id,evidence_id)
);
CREATE TABLE IF NOT EXISTS world_reputation_prestige_reviews (
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 prestige_score INTEGER NOT NULL CHECK(prestige_score BETWEEN 0 AND 100),
 reviewer TEXT NOT NULL,
 methodology_note TEXT NOT NULL,
 revision INTEGER NOT NULL DEFAULT 1,
 reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(dataset_id,club_id)
);
CREATE TABLE IF NOT EXISTS world_career_reputation_seasons (
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 season_index INTEGER NOT NULL CHECK(season_index>=0),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 competition_id TEXT NOT NULL REFERENCES world_competitions(competition_id),
 sporting_appeal INTEGER CHECK(sporting_appeal BETWEEN 0 AND 100),
 squad_anchor INTEGER,
 underlying_appeal INTEGER CHECK(underlying_appeal BETWEEN 0 AND 100),
 temporary_bonus INTEGER NOT NULL DEFAULT 0 CHECK(temporary_bonus BETWEEN 0 AND 8),
 cup_bonus INTEGER NOT NULL DEFAULT 0,
 continental_bonus INTEGER NOT NULL DEFAULT 0,
 continental_trophy_bonus INTEGER NOT NULL DEFAULT 0,
 bonus_overlap_reduction INTEGER NOT NULL DEFAULT 0,
 form_adjustment INTEGER NOT NULL CHECK(form_adjustment BETWEEN -3 AND 3),
 prestige_at_snapshot INTEGER CHECK(prestige_at_snapshot BETWEEN 0 AND 100),
 model_version TEXT NOT NULL,
 PRIMARY KEY(career_id,season_index,club_id)
);
CREATE TABLE IF NOT EXISTS world_career_reputation_runs (
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 season_index INTEGER NOT NULL CHECK(season_index>0),
 source_season TEXT NOT NULL,
 input_signature TEXT NOT NULL,
 submitted_by TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(career_id,season_index),
 UNIQUE(career_id,source_season)
);
CREATE TABLE IF NOT EXISTS world_career_reputation_outcomes (
 career_id TEXT NOT NULL,
 season_index INTEGER NOT NULL,
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 old_competition_id TEXT NOT NULL REFERENCES world_competitions(competition_id),
 next_competition_id TEXT NOT NULL REFERENCES world_competitions(competition_id),
 league_position INTEGER NOT NULL,
 league_size INTEGER NOT NULL,
 cup_won INTEGER NOT NULL CHECK(cup_won IN (0,1)),
 source_ref TEXT NOT NULL,
 previous_appeal INTEGER,
 current_appeal INTEGER,
 division_delta INTEGER NOT NULL,
 form_delta INTEGER NOT NULL,
 prestige_delta INTEGER NOT NULL DEFAULT 0 CHECK(prestige_delta BETWEEN -2 AND 2),
 domestic_cup TEXT NOT NULL DEFAULT 'none',
 continental_competition TEXT NOT NULL DEFAULT 'none',
 continental_trophy TEXT NOT NULL DEFAULT 'none',
 cup_source_ref TEXT,
 continental_source_ref TEXT,
 trophy_source_ref TEXT,
 temporary_bonus INTEGER NOT NULL DEFAULT 0,
 previous_temporary_bonus INTEGER NOT NULL DEFAULT 0,
 cup_bonus INTEGER NOT NULL DEFAULT 0,
 continental_bonus INTEGER NOT NULL DEFAULT 0,
 continental_trophy_bonus INTEGER NOT NULL DEFAULT 0,
 bonus_overlap_reduction INTEGER NOT NULL DEFAULT 0,
 underlying_appeal INTEGER,
 PRIMARY KEY(career_id,season_index,club_id),
 FOREIGN KEY(career_id,season_index) REFERENCES world_career_reputation_runs(career_id,season_index)
);
CREATE INDEX IF NOT EXISTS world_career_rep_history
 ON world_career_reputation_seasons(career_id,club_id,season_index);
"""


def initialize_progression(conn):
    """Idempotent additive migrations for already-existing development saves."""
    conn.executescript(SCHEMA)
    season_columns={
        "underlying_appeal":"INTEGER",
        "temporary_bonus":"INTEGER NOT NULL DEFAULT 0",
        "cup_bonus":"INTEGER NOT NULL DEFAULT 0",
        "continental_bonus":"INTEGER NOT NULL DEFAULT 0",
        "continental_trophy_bonus":"INTEGER NOT NULL DEFAULT 0",
        "bonus_overlap_reduction":"INTEGER NOT NULL DEFAULT 0",
    }
    outcome_columns={
        "prestige_delta":"INTEGER NOT NULL DEFAULT 0",
        "domestic_cup":"TEXT NOT NULL DEFAULT 'none'",
        "continental_competition":"TEXT NOT NULL DEFAULT 'none'",
        "continental_trophy":"TEXT NOT NULL DEFAULT 'none'",
        "cup_source_ref":"TEXT",
        "continental_source_ref":"TEXT",
        "trophy_source_ref":"TEXT",
        "temporary_bonus":"INTEGER NOT NULL DEFAULT 0",
        "previous_temporary_bonus":"INTEGER NOT NULL DEFAULT 0",
        "cup_bonus":"INTEGER NOT NULL DEFAULT 0",
        "continental_bonus":"INTEGER NOT NULL DEFAULT 0",
        "continental_trophy_bonus":"INTEGER NOT NULL DEFAULT 0",
        "bonus_overlap_reduction":"INTEGER NOT NULL DEFAULT 0",
        "underlying_appeal":"INTEGER",
    }
    for table,additions in (
        ("world_career_reputation_seasons",season_columns),
        ("world_career_reputation_outcomes",outcome_columns),
    ):
        columns={row[1] for row in conn.execute("PRAGMA table_info("+table+")")}
        for name,spec in additions.items():
            if name not in columns:
                conn.execute("ALTER TABLE "+table+" ADD COLUMN "+name+" "+spec)
    conn.commit()

def _as_dict(row):
    if hasattr(row, "keys"):
        return dict(row)
    raise ValueError("Expected sqlite3.Row; set row_factory before reading a snapshot")


def _clamp(value, low=10, high=99):
    return max(low, min(high, value))


def _source_reference(value):
    if not isinstance(value, str) or not 8<=len(value.strip())<=500:
        return False
    value=value.strip()
    if value.startswith("archive:"):
        return len(value)>len("archive:")+3
    parsed=urlsplit(value)
    return parsed.scheme in ("http","https") and bool(parsed.netloc)


def _finish_form(league_position, league_size, cup_won=False):
    if type(league_position) is not int or type(league_size) is not int:
        raise ValueError("An evidenced league position and competition size are required")
    if not 8<=league_size<=30 or not 1<=league_position<=league_size:
        raise ValueError("League finish is outside the competition's valid range")
    if type(cup_won) is not bool:
        raise ValueError("Cup result must be explicit true or false")
    fraction=(league_position-1)/(league_size-1)
    if fraction<=0.125:
        label,form="top",2
    elif fraction<=0.30:
        label,form="upper",1
    elif fraction>=0.875:
        label,form="bottom",-2
    elif fraction>=0.70:
        label,form="lower",-1
    else:
        label,form="middle",0
    return _clamp(form+int(cup_won),-3,3),label


def preview_progression(*,old_score,old_competition,next_competition,old_form,
                        league_position,league_size,cup_won=False,
                        domestic_cup="none",continental_competition="none",
                        continental_trophy="none",old_temporary_bonus=0,
                        old_underlying=None):
    """Pure NEXT-season projection: temporary opportunities expire and replace.

    The user explicitly selects continental participation. Finishing third or
    winning a cup never silently establishes eligibility across rule changes.
    """
    if old_competition not in ENGLISH_DIVISION_CONTEXT:
        raise ValueError("Unsupported source competition")
    if next_competition not in ENGLISH_DIVISION_CONTEXT:
        raise ValueError("Unsupported destination competition")
    if abs(int(next_competition[-1])-int(old_competition[-1]))>1:
        raise ValueError("More than one divisional move in a single season is unsupported")
    if old_score is not None and (type(old_score) is not int or not 0<=old_score<=100):
        raise ValueError("Existing sporting appeal must be 0-100 or unknown")
    if type(old_form) is not int or not -3<=old_form<=3:
        raise ValueError("Invalid previous form adjustment")
    if type(old_temporary_bonus) is not int or not 0<=old_temporary_bonus<=8:
        raise ValueError("Invalid prior temporary bonus")
    if old_underlying is not None and (type(old_underlying) is not int or
                                       not 0<=old_underlying<=100):
        raise ValueError("Underlying sporting appeal must be 0-100 or unknown")
    # Only the league finish contributes to persistent, bounded recent form;
    # a trophy gives its own one-season bonus, avoiding a second award.
    new_form,label=_finish_form(league_position,league_size,False)
    awards=calculate_opportunity_bonuses(
        domestic_cup=domestic_cup,
        continental_competition=continental_competition,
        continental_trophy=continental_trophy,
        legacy_cup_won=cup_won,
    )
    division_delta=(ENGLISH_DIVISION_CONTEXT[next_competition]-
                    ENGLISH_DIVISION_CONTEXT[old_competition])
    form_delta=new_form-old_form
    previous_core=(old_underlying if old_underlying is not None else
                   max(10,old_score-old_temporary_bonus) if old_score is not None else None)
    core=(None if previous_core is None else
          _clamp(previous_core+division_delta+form_delta))
    score=(None if core is None else
           _clamp(core+awards["temporary_bonus"]))
    return {
        "previous":old_score,"projected":score,"underlying_appeal":core,
        "division_delta":division_delta,"form_delta":form_delta,
        "old_form":old_form,"new_form":new_form,"finish_band":label,
        "previous_temporary_bonus":old_temporary_bonus,
        "old_underlying":previous_core,
        **awards,
        "source_is_hypothetical":True,
    }

def _career(conn,career_id):
    row=conn.execute("SELECT career_id,dataset_id FROM world_career_saves WHERE career_id=?",
                     (career_id,)).fetchone()
    if row is None:
        raise ValueError("Unknown development career")
    return row


def latest_season_index(conn,career_id):
    value=conn.execute("""SELECT MAX(season_index) FROM world_career_reputation_seasons
        WHERE career_id=?""",(career_id,)).fetchone()[0]
    return 0 if value is None else value


def current_career_appeal(conn,career_id,club_id):
    """Latest career-specific score including current-season temporary awards.

    Season zero is the immutable dataset estimate: no implied European
    participation, cup win or historical prestige without reviewed evidence.
    """
    row=conn.execute("""SELECT competition_id,sporting_appeal,form_adjustment,
           season_index,prestige_at_snapshot,underlying_appeal,temporary_bonus,
           cup_bonus,continental_bonus,continental_trophy_bonus
           FROM world_career_reputation_seasons
           WHERE career_id=? AND club_id=? ORDER BY season_index DESC LIMIT 1""",
           (career_id,club_id)).fetchone()
    if row:
        return dict(
            competition_id=row[0],score=row[1],form=row[2],
            season_index=row[3],prestige=row[4],
            underlying_appeal=row[5] if row[5] is not None else row[1],
            temporary_bonus=row[6],
            cup_bonus=row[7],continental_bonus=row[8],
            continental_trophy_bonus=row[9],
        )
    career=_career(conn,career_id)
    row=conn.execute("""SELECT competition_id,sporting_appeal,prospects_adjustment
        FROM world_pyramid_club_appeal
        WHERE dataset_id=? AND model_version=? AND club_id=?""",
        (career[1],BASE_MODEL,club_id)).fetchone()
    if row is None:
        return None
    prestige=conn.execute("""SELECT prestige_score FROM world_reputation_prestige_reviews
        WHERE dataset_id=? AND club_id=?""",(career[1],club_id)).fetchone()
    return {"competition_id":row[0],"score":row[1],"form":row[2],
            "season_index":0,"prestige":prestige[0] if prestige else None,
            "underlying_appeal":row[1],"temporary_bonus":0,
            "cup_bonus":0,"continental_bonus":0,"continental_trophy_bonus":0}

def add_prestige_evidence(conn,*,dataset_id,club_id,evidence_id,category,
                          factual_claim,source_url,published_date=None):
    """Capture a source citation for HUMAN review; never approve automatically."""
    from datetime import date
    if category not in PRESTIGE_CATEGORIES:
        raise ValueError("Unknown prestige-evidence category")
    if not isinstance(evidence_id,str) or not 3<=len(evidence_id)<=80:
        raise ValueError("A stable evidence identifier is required")
    if not isinstance(factual_claim,str) or len(factual_claim.strip())<15:
        raise ValueError("A clearly described sourced historical fact is required")
    if not isinstance(source_url,str):
        raise ValueError("A source URL is required")
    parsed=urlsplit(source_url)
    if parsed.scheme not in ("http","https") or not parsed.netloc:
        raise ValueError("Prestige source must be an external HTTP(S) URL")
    if published_date is not None:
        date.fromisoformat(published_date)
    membership=conn.execute("""SELECT 1 FROM world_dataset_entries
        WHERE dataset_id=? AND club_id=?""",(dataset_id,club_id)).fetchone()
    if membership is None:
        raise ValueError("Club not present in this season dataset")
    conn.execute("""INSERT INTO world_reputation_prestige_evidence
        (dataset_id,club_id,evidence_id,category,factual_claim,source_url,
         published_date,review_state)
        VALUES(?,?,?,?,?,?,?,'pending')""",
        (dataset_id,club_id,evidence_id,category,factual_claim.strip(),
         source_url,published_date))
    conn.commit()


def review_prestige_evidence(conn,*,dataset_id,club_id,evidence_id,
                             reviewer,approved):
    """Record a review decision, not an assertion that the URL was auto-verified."""
    if type(approved) is not bool:
        raise ValueError("Review decision must be explicit")
    if not isinstance(reviewer,str) or len(reviewer.strip())<3:
        raise ValueError("Reviewer identity is required")
    result=conn.execute("""UPDATE world_reputation_prestige_evidence
        SET review_state=?,reviewed_by=? WHERE dataset_id=? AND club_id=?
        AND evidence_id=? AND review_state='pending'""",
        ("reviewed" if approved else "rejected",reviewer.strip(),
         dataset_id,club_id,evidence_id))
    if result.rowcount!=1:
        conn.rollback()
        raise ValueError("Evidence not found or already reviewed")
    conn.commit()


def project_prestige(*,previous,old_competition,next_competition,
                     league_position,cup_won):
    """Intentionally slow reputation change only from an already-reviewed base.

    One relegation costs at most 1 prestige point. An evidenced top-flight title
    can contribute 2; a lower-tier title or cup success contributes 1 each,
    capped to ±2 per season. Unknown institutional prestige stays unknown.
    """
    if previous is None:
        return None,0
    if type(previous) is not int or not 0<=previous<=100:
        raise ValueError("Prior reviewed prestige score invalid")
    delta=0
    if league_position==1:
        delta+=2 if old_competition=="ENG1" else 1
    if cup_won:
        delta+=1
    if (int(next_competition[-1])>int(old_competition[-1])):
        delta-=1
    delta=max(-2,min(2,delta))
    return max(0,min(100,previous+delta)),delta


def verify_prestige(conn,*,dataset_id,club_id,prestige_score,reviewer,methodology_note):
    """Explicit reviewer sign-off; cannot create a score without sourced evidence."""
    if type(prestige_score) is not int or not 0<=prestige_score<=100:
        raise ValueError("Prestige rating must be an integer 0-100")
    if not isinstance(reviewer,str) or len(reviewer.strip())<3:
        raise ValueError("Named reviewer required")
    if not isinstance(methodology_note,str) or len(methodology_note.strip())<30:
        raise ValueError("A substantial, auditable scoring rationale is required")
    rows=conn.execute("""SELECT category,source_url FROM world_reputation_prestige_evidence
        WHERE dataset_id=? AND club_id=? AND review_state='reviewed'""",
        (dataset_id,club_id)).fetchall()
    if len(rows)<3 or len({r[0] for r in rows})<2 or len({r[1] for r in rows})<2:
        raise ValueError("At least three reviewed evidence items across two categories and two sources required")
    conn.execute("""INSERT INTO world_reputation_prestige_reviews
        (dataset_id,club_id,prestige_score,reviewer,methodology_note)
        VALUES(?,?,?,?,?) ON CONFLICT(dataset_id,club_id) DO UPDATE SET
        prestige_score=excluded.prestige_score, reviewer=excluded.reviewer,
        methodology_note=excluded.methodology_note,
        revision=world_reputation_prestige_reviews.revision+1,
        reviewed_at=CURRENT_TIMESTAMP""",
        (dataset_id,club_id,prestige_score,reviewer.strip(),methodology_note.strip()))
    conn.commit()


def _outcome_signature(outcomes):
    raw=json.dumps(outcomes,sort_keys=True,separators=(",",":"),ensure_ascii=True)
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


def finalize_career_season(conn,*,career_id,source_season,outcomes,submitted_by):
    """Atomic, complete-club season transition with explicit outcome references.

    Requires results for ALL clubs and internally consistent division memberships.
    Nothing runs automatically on a GET and no other career save is modified.
    User-supplied references are preserved, not claimed independently verified.
    """
    if not isinstance(source_season,str) or not re.fullmatch(r"\d{4}/\d{2}",source_season):
        raise ValueError("Season label must have the exact YYYY/YY format")
    if not isinstance(submitted_by,str) or len(submitted_by.strip())<3:
        raise ValueError("Explicit reviewer/submitter required")
    if not isinstance(outcomes,list) or not outcomes or any(not isinstance(x,dict) for x in outcomes):
        raise ValueError("Supply an explicit list of all club season outcomes")
    # Normalize and validate input before starting the write transaction.
    required={"club_id","next_competition_id","league_position","league_size","cup_won","source_ref"}
    options={"domestic_cup":"none","continental_competition":"none",
             "continental_trophy":"none","cup_source_ref":None,
             "continental_source_ref":None,"trophy_source_ref":None}
    normalized=[]
    for o in outcomes:
        if not required.issubset(o) or set(o)-required-set(options):
            raise ValueError("Every outcome must specify club, division, position, size, cup result and source")
        if type(o["club_id"]) is not int:
            raise ValueError("Club IDs must be integer references")
        if o["next_competition_id"] not in ENGLISH_DIVISION_CONTEXT:
            raise ValueError("Unsupported next-season division")
        if not _source_reference(o["source_ref"]):
            raise ValueError("Every club requires a source URL or explicit archive reference")
        _finish_form(o["league_position"],o["league_size"],o["cup_won"])
        n={**o}
        for key,default in options.items():
            n.setdefault(key,default)
        calculate_opportunity_bonuses(
            domestic_cup=n["domestic_cup"],
            continental_competition=n["continental_competition"],
            continental_trophy=n["continental_trophy"],
            legacy_cup_won=n["cup_won"])
        # Cup and European claims require their OWN evidence, not merely a
        # league-table URL. "None" means no asserted award.
        for claim,reference in (
            ("domestic_cup","cup_source_ref"),
            ("continental_competition","continental_source_ref"),
            ("continental_trophy","trophy_source_ref"),
        ):
            if n[claim]!="none" and not _source_reference(n[reference]):
                raise ValueError("Award or continental qualification requires a separate source: "+reference)
            if n[claim]=="none" and n[reference] is not None:
                raise ValueError("Unexpected source reference for an unclaimed award: "+reference)
        normalized.append({k:n[k] for k in sorted(required|set(options))})
    normalized.sort(key=lambda x:x["club_id"])
    if len({o["club_id"] for o in normalized})!=len(normalized):
        raise ValueError("Club included twice in season transition")
    signature=_outcome_signature(normalized)
    # Compatibility with completed v1 seasons whose signatures predated
    # named cup / continental opportunity fields.
    legacy_signature=_outcome_signature([
        {key:o[key] for key in sorted(required)} for o in normalized])
    _career(conn,career_id)
    # Replaying the *same sourced season* must never double-count reputation.
    # A changed replay is a conflict and needs explicit reconciliation.
    previous_run=conn.execute("""SELECT season_index,input_signature
         FROM world_career_reputation_runs
         WHERE career_id=? AND source_season=?""",
         (career_id,source_season)).fetchone()
    if previous_run:
        no_new_awards=all(
            o["domestic_cup"]=="none" and
            o["continental_competition"]=="none" and
            o["continental_trophy"]=="none"
            for o in normalized)
        if previous_run[1]==signature or (no_new_awards and previous_run[1]==legacy_signature):
            return previous_run[0]
        raise ValueError("This career season was already finalised with different results")
    career=_career(conn,career_id)
    start=conn.execute("SELECT season_id FROM world_datasets WHERE dataset_id=?",
                       (career[1],)).fetchone()
    if not start or not re.fullmatch(r"\d{4}/\d{2}",start[0]):
        raise ValueError("Career starting-season chronology is unavailable")
    next_season=latest_season_index(conn,career_id)+1
    year=int(start[0][:4])+next_season-1
    expected=f"{year}/{(year+1)%100:02d}"
    if source_season!=expected:
        raise ValueError(f"Result season {source_season} does not match career's next season {expected}")
    # Caller initializes progression+pyramid before attempting a transition.
    conn.execute("BEGIN IMMEDIATE")
    try:
        previous=conn.execute("""SELECT season_index FROM world_career_reputation_runs
            WHERE career_id=? ORDER BY season_index DESC LIMIT 1""",(career_id,)).fetchone()
        next_index=1 if previous is None else previous[0]+1
        prior=conn.execute("""SELECT club_id,competition_id,sporting_appeal,
            form_adjustment,prestige_at_snapshot,squad_anchor,
            underlying_appeal,temporary_bonus
            FROM world_career_reputation_seasons WHERE career_id=? AND season_index=?""",
            (career_id,next_index-1)).fetchall() if previous else []
        if not prior:
            dataset=_career(conn,career_id)[1]
            prior=conn.execute("""SELECT r.club_id,r.competition_id,r.sporting_appeal,
                r.prospects_adjustment AS form_adjustment,
                COALESCE(frozen.prestige_score,p.prestige_score) AS prestige,
                r.strength_component AS squad_anchor,
                r.sporting_appeal AS underlying_appeal,0 AS temporary_bonus
                FROM world_pyramid_club_appeal r
                LEFT JOIN world_reputation_prestige_reviews p
                 ON p.dataset_id=r.dataset_id AND p.club_id=r.club_id
                LEFT JOIN world_career_prestige_snapshots frozen
                 ON frozen.career_id=? AND frozen.dataset_id=r.dataset_id
                 AND frozen.club_id=r.club_id
                WHERE r.dataset_id=? AND r.model_version=?""",
                (career_id,dataset,BASE_MODEL)).fetchall()
        existing={r[0]:r for r in prior}
        if set(existing)!={o["club_id"] for o in normalized}:
            raise ValueError("Season requires results for every club in this career dataset")
        current_counts=Counter(r[1] for r in prior)
        future_counts=Counter(o["next_competition_id"] for o in normalized)
        if current_counts!=future_counts:
            raise ValueError("Promotion/relegation outcomes must preserve division sizes")
        # The complete 92-club English pyramid must also honour its actual
        # annual interchange slots, rather than arbitrarily swapping teams.
        full_english=(current_counts=={"ENG1":20,"ENG2":24,"ENG3":24,"ENG4":24})
        if full_english:
            expected={("ENG1","ENG2"):3,("ENG2","ENG3"):3,
                      ("ENG3","ENG4"):4}
            for (upper,lower),slots in expected.items():
                down=sum(1 for o in normalized
                    if existing[o["club_id"]][1]==upper
                    and o["next_competition_id"]==lower)
                up=sum(1 for o in normalized
                    if existing[o["club_id"]][1]==lower
                    and o["next_competition_id"]==upper)
                if down!=slots or up!=slots:
                    raise ValueError(
                        f"English pyramid requires {slots} promotions and relegations between {upper} and {lower}")
        placements=defaultdict(set)
        for o in normalized:
            old=existing[o["club_id"]]
            count=current_counts[old[1]]
            if o["league_size"]!=count:
                raise ValueError("League size must match the prior-season membership")
            if o["league_position"] in placements[old[1]]:
                raise ValueError("Duplicate final league position in a division")
            placements[old[1]].add(o["league_position"])
            if abs(int(o["next_competition_id"][-1])-int(old[1][-1]))>1:
                raise ValueError("A club cannot skip divisions in a single transition")
            if full_english:
                old_tier=int(old[1][-1])
                new_tier=int(o["next_competition_id"][-1])
                position=o["league_position"]
                if new_tier<old_tier and position>{2:6,3:6,4:7}.get(old_tier,0):
                    raise ValueError("Promotion must follow an eligible automatic/play-off position")
                if new_tier>old_tier and position<(
                    count-{1:3,2:3,3:4}.get(old_tier,0)+1):
                    raise ValueError("Relegation must follow a bottom-place finish")
        if previous is None:
            for old in prior:
                conn.execute("""INSERT INTO world_career_reputation_seasons
                    (career_id,season_index,club_id,competition_id,sporting_appeal,
                     form_adjustment,prestige_at_snapshot,model_version,squad_anchor,
                     underlying_appeal,temporary_bonus)
                    VALUES(?,0,?,?,?,?,?,?,?,?,?)""",
                    (career_id,old[0],old[1],old[2],old[3],old[4],
                     PROGRESSION_VERSION,old[5],old[6],0))
        conn.execute("""INSERT INTO world_career_reputation_runs
            (career_id,season_index,source_season,input_signature,submitted_by)
            VALUES (?,?,?,?,?)""",(career_id,next_index,source_season,signature,submitted_by.strip()))
        for o in normalized:
            old=existing[o["club_id"]]
            result=preview_progression(old_score=old[2],old_competition=old[1],
                next_competition=o["next_competition_id"],old_form=old[3],
                league_position=o["league_position"],league_size=o["league_size"],
                cup_won=o["cup_won"],domestic_cup=o["domestic_cup"],
                continental_competition=o["continental_competition"],
                continental_trophy=o["continental_trophy"],
                old_underlying=old[6],old_temporary_bonus=old[7])
            next_prestige,prestige_delta=project_prestige(
                previous=old[4],old_competition=old[1],
                next_competition=o["next_competition_id"],
                league_position=o["league_position"],
                cup_won=result["has_domestic_cup"] or o["continental_trophy"]!="none")
            conn.execute("""INSERT INTO world_career_reputation_seasons
                (career_id,season_index,club_id,competition_id,sporting_appeal,
                 form_adjustment,prestige_at_snapshot,model_version,squad_anchor,
                 underlying_appeal,temporary_bonus,cup_bonus,continental_bonus,
                 continental_trophy_bonus,bonus_overlap_reduction)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (career_id,next_index,o["club_id"],o["next_competition_id"],
                 result["projected"],result["new_form"],next_prestige,
                 PROGRESSION_VERSION,old[5],result["underlying_appeal"],
                 result["temporary_bonus"],result["cup_bonus"],
                 result["continental_bonus"],result["continental_trophy_bonus"],
                 result["overlap_cap"]))
            conn.execute("""INSERT INTO world_career_reputation_outcomes
                (career_id,season_index,club_id,old_competition_id,next_competition_id,
                 league_position,league_size,cup_won,source_ref,previous_appeal,
                 current_appeal,division_delta,form_delta,prestige_delta,
                 domestic_cup,continental_competition,continental_trophy,
                 cup_source_ref,continental_source_ref,trophy_source_ref,
                 temporary_bonus,previous_temporary_bonus,cup_bonus,continental_bonus,
                 continental_trophy_bonus,bonus_overlap_reduction,underlying_appeal)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (career_id,next_index,o["club_id"],old[1],o["next_competition_id"],
                 o["league_position"],o["league_size"],int(result["has_domestic_cup"]),
                 o["source_ref"],old[2],result["projected"],
                 result["division_delta"],result["form_delta"],prestige_delta,
                 o["domestic_cup"],o["continental_competition"],o["continental_trophy"],
                 o["cup_source_ref"],o["continental_source_ref"],o["trophy_source_ref"],
                 result["temporary_bonus"],result["previous_temporary_bonus"],
                 result["cup_bonus"],result["continental_bonus"],
                 result["continental_trophy_bonus"],result["overlap_cap"],
                 result["underlying_appeal"]))
        conn.commit()
        return next_index
    except Exception:
        conn.rollback()
        raise

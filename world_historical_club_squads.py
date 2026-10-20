"""Edition-isolated historical club/squad mapper for the completed PES2020 V2 data.

Read-only input: the SAME source and converted full-database artifacts. Builds a
standalone SQLite catalogue; never mutates live World/Career/Render databases.

Contract:
 - preserve all edition rows, including duplicate source IDs, using row ordinal
 - never join different FIFA years merely because IDs/names match
 - never guess country, league, budgets, club identities across source providers
 - free agents/unknown clubs are NOT silently assigned to a football club
 - loaned_from is retained as a fact, not equated with current club ownership
 - PES 25+4 estimates stay attached to the exact player source row
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import date
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import unicodedata
from zipfile import ZipFile

from scripts.export_fifa_pes_v2 import source_members, read_ed
from world_fifa_pes_converter_v2 import TARGETS

YEARS=tuple(y for y in range(2005,2028) if y!=2025)
ATTRS=tuple(TARGETS)
AUX=("weak_foot_usage","weak_foot_accuracy","form","injury_resistance")
UNKNOWN=frozenset(("","n/a","na","nan","none","null","unknown","-","--","not available"))
FREE_AGENT=frozenset(("freeagent","freeagents","unattached","withoutclub","no club"))
CLUB_COLS=("club_name","club","Club","ClubName","team_name","Team","TeamName")
CLUB_ID_COLS=("club_team_id","club_id","clubId","ClubID")
LEAGUE_COLS=("club_league_name","league_name","league","League","LeagueName")
LEAGUE_ID_COLS=("club_league_id","league_id","LeagueID")
LEAGUE_LEVEL_COLS=("league_level","league_rank")
LOAN_COLS=("club_loaned_from","loaned_from","loanedFrom")
SCHEMA="""
PRAGMA foreign_keys=ON;
CREATE TABLE editions(
 edition INTEGER PRIMARY KEY,
 season TEXT NOT NULL,
 provider TEXT NOT NULL,
 source_sha256 TEXT NOT NULL,
 source_player_rows INTEGER NOT NULL,
 imported_player_rows INTEGER NOT NULL,
 club_count INTEGER NOT NULL,
 assigned_squad_rows INTEGER NOT NULL,
 free_agent_rows INTEGER NOT NULL,
 unknown_club_rows INTEGER NOT NULL,
 missing_league_clubs INTEGER NOT NULL,
 conflicting_league_clubs INTEGER NOT NULL,
 source_roster_completeness TEXT NOT NULL DEFAULT 'not_verified',
 conversion_quality TEXT NOT NULL DEFAULT 'numeric_PES_estimates_only'
);
CREATE TABLE leagues(
 league_key TEXT PRIMARY KEY,
 edition INTEGER NOT NULL REFERENCES editions(edition),
 league_name TEXT NOT NULL,
 source_league_id TEXT,
 source_league_level TEXT,
 gender TEXT NOT NULL,
 verification_status TEXT NOT NULL DEFAULT 'source_label_only'
);
CREATE TABLE clubs(
 club_key TEXT PRIMARY KEY,
 edition INTEGER NOT NULL REFERENCES editions(edition),
 name TEXT NOT NULL,
 source_club_id TEXT,
 league_key TEXT REFERENCES leagues(league_key),
 league_status TEXT NOT NULL,
 league_conflicts INTEGER NOT NULL DEFAULT 0,
 squad_size INTEGER NOT NULL DEFAULT 0,
 source_provider TEXT NOT NULL,
 gender TEXT NOT NULL,
 identity_status TEXT NOT NULL DEFAULT 'edition_scoped_source'
);
CREATE TABLE players(
 player_key TEXT PRIMARY KEY,
 edition INTEGER NOT NULL REFERENCES editions(edition),
 source_row_number INTEGER NOT NULL,
 source_player_id TEXT NOT NULL,
 namespaced_source_player_key TEXT NOT NULL,
 player_name TEXT NOT NULL,
 date_of_birth TEXT,
 nationality TEXT,
 preferred_foot TEXT,
 height_cm TEXT,
 weight_kg TEXT,
 source_overall INTEGER,
 primary_position TEXT NOT NULL,
 alternative_positions TEXT NOT NULL,
 position_fit_indices TEXT NOT NULL,
 club_key TEXT REFERENCES clubs(club_key),
 assignment TEXT NOT NULL CHECK(assignment IN ('at_club','free_agent','club_unknown')),
 loaned_from TEXT,
 pes_abilities_json TEXT NOT NULL,
 pes_additional_json TEXT NOT NULL,
 source_provider TEXT NOT NULL,
 gender TEXT NOT NULL,
 UNIQUE(edition,source_row_number)
);
CREATE INDEX player_edition_club ON players(edition,club_key);
CREATE INDEX player_edition_name ON players(edition,player_name);
CREATE INDEX player_edition_source_id ON players(edition,source_player_id);
CREATE INDEX club_edition_name ON clubs(edition,name);
CREATE INDEX league_edition_name ON leagues(edition,league_name);
"""

def clean(value):
    raw=str(value or "").strip()
    return "" if raw.casefold() in UNKNOWN else raw

def first(row,cols):
    for col in cols:
        v=clean(row.get(col))
        if v:return v
    return ""

def norm(text):
    return "".join(c for c in unicodedata.normalize("NFKD",text).casefold()
                   if c.isascii() and c.isalnum())

def slug(text):
    # Hash of original exact label prevents Unicode transliteration collisions.
    label=norm(text)[:80] or "unlabelled"
    return label+"-"+hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]

def gender_group(row):
    raw=norm(first(row,("gender","Gender","sex","Sex")))
    if raw in ("women","female","womensfootball","womenssoccer","f"):
        return "women"
    if raw in ("men","male","mensfootball","menssoccer","m"):
        return "men"
    return "unspecified" if not raw else "source:"+raw

def source_club(row):
    return first(row,CLUB_COLS)

def club_ref(row,year):
    name=source_club(row)
    if not name or norm(name) in FREE_AGENT:
        return None
    sid=first(row,CLUB_ID_COLS)
    return f"c{year}:{gender_group(row)}:{slug(sid) if sid else slug(name)}"

def league_ref(row,year):
    name=first(row,LEAGUE_COLS)
    if not name:return None
    sid=first(row,LEAGUE_ID_COLS)
    return f"l{year}:{gender_group(row)}:{slug(sid) if sid else slug(name)}"

def season_label(year):
    start=year-1
    return f"{start}/{str(year)[-2:]}"

def get_manifests(source,converted):
    sm=[p for p in source.namelist() if p.endswith("/MANIFEST.json")]
    if len(sm)!=1:raise ValueError("Source manifest not unique")
    src=json.loads(source.read(sm[0]))
    out=json.loads(converted.read("PES2020_v2/MANIFEST.json"))
    expected=set(YEARS)
    if {int(x["edition"]) for x in src["downloads"]}!=expected:
        raise ValueError("Source archive must cover 22 editions excluding FC25")
    if {int(y) for y in out["per_edition"]}!=expected:
        raise ValueError("Rating archive must cover 22 editions excluding FC25")
    if out.get("converted_player_records")!=319389:
        raise ValueError("Unexpected full V2 data version; do not mix snapshots")
    if not out.get("source_original_bytes_preserved") or out.get("FC25")!="SOURCE_GAP_NOT_RESTORED":
        raise ValueError("Source preservation and FC25 safeguards failed")
    return src,out

def process_ed(conn,original,conversion,year,source_rec,pes_stats,source_file):
    raw_bytes=original.read(source_file)
    if hashlib.sha256(raw_bytes).hexdigest()!=source_rec["sha256"]:
        raise ValueError(f"{year}: source checksum mismatch")
    source_rows=read_ed(original,{year:source_file},year)
    filename=f"PES2020_v2/{year}_FIFA_to_PES2020_Complete.csv"
    with conversion.open(filename) as stream:
        rating_rows=list(csv.DictReader(io.TextIOWrapper(stream,encoding="utf-8",newline="")))
    if not (len(source_rows)==len(rating_rows)==source_rec["player_rows"]==pes_stats["converted_players"]):
        raise ValueError(f"{year}: conversion and source rows do not align")
    provider=source_rec["catalog_source"]
    players=[]
    clubs={}
    leagues={}
    duplicate_ids=Counter()
    club_league_seen=defaultdict(set)
    conflicting_names=defaultdict(set)
    club_sizes=Counter()
    assigned=free=unknown=0
    for ordinal,(src,pes) in enumerate(zip(source_rows,rating_rows),start=1):
        source_id=clean(pes["source_player_id"])
        if not source_id or not clean(pes["player_name"]):
            raise ValueError(f"{year} row {ordinal}: missing source identity")
        raw_player_id=first(src,("player_id","sofifa_id","ID"))
        if raw_player_id and raw_player_id!=source_id:
            raise ValueError(f"{year} row {ordinal}: source/player CSV ordering mismatch")
        raw_club=source_club(src)
        if raw_club!=clean(pes["source_club"]):
            raise ValueError(f"{year} row {ordinal}: source club/converted club mismatch")
        if int(pes["source_edition"])!=year or pes["source_provider"]!=provider:
            raise ValueError(f"{year} row {ordinal}: invalid source edition/provider")
        expected_namespaced=f"{year}:{provider}:{source_id}"
        if pes["namespaced_source_player_key"]!=expected_namespaced:
            raise ValueError(f"{year} row {ordinal}: source ID reference mismatch")
        # A source ID MAY be duplicated in an upstream dataset. Row ordinal
        # makes distinct registrations without inventing another original ID.
        duplicate_ids[source_id]+=1
        player_key=f"p{year}:{ordinal:06d}"
        club_key=club_ref(src,year)
        club_name=source_club(src)
        league_key=league_ref(src,year)
        if club_key:
            assigned+=1
            club_sizes[club_key]+=1
            source_club_id=first(src,CLUB_ID_COLS)
            if club_key not in clubs:
                clubs[club_key]=(club_name,source_club_id,gender_group(src))
            elif clubs[club_key]!=(club_name,source_club_id,gender_group(src)):
                conflicting_names[club_key].add(club_name)
            club_league_seen[club_key].add(league_key)
            if league_key:
                league=(first(src,LEAGUE_COLS),first(src,LEAGUE_ID_COLS),
                        first(src,LEAGUE_LEVEL_COLS),gender_group(src))
                if league_key in leagues and leagues[league_key]!=league:
                    raise ValueError(f"{year}: inconsistent league identity {league_key}")
                leagues[league_key]=league
            assignment="at_club"
        elif norm(club_name) in FREE_AGENT:
            free+=1
            assignment="free_agent"
        else:
            unknown+=1
            assignment="club_unknown"
        abilities={}
        for stat in ATTRS:
            v=int(pes[stat])
            if not 40<=v<=99:raise ValueError(f"{year}:{ordinal} invalid {stat}")
            abilities[stat]=v
        additional={}
        for stat,lo,hi in (("weak_foot_usage",1,4),
                           ("weak_foot_accuracy",1,4),
                           ("form",1,8),("injury_resistance",1,3)):
            v=int(pes[stat])
            if not lo<=v<=hi:raise ValueError(f"{year}:{ordinal} invalid {stat}")
            additional[stat]=v
        try: source_overall=int(float(pes["source_overall"]))
        except (ValueError,TypeError):source_overall=None
        players.append((player_key,year,ordinal,source_id,expected_namespaced,
            pes["player_name"],clean(pes["identity_dob"]) or None,
            clean(pes["source_nationality"]) or first(src,("nationality_name","Nationality")) or None,
            clean(pes["source_preferred_foot"]) or None,
            clean(pes["source_height_cm"]) or None,clean(pes["source_weight_kg"]) or None,
            source_overall,pes["primary_position"],pes["alternative_positions"],
            pes["position_fit_indices"],club_key,assignment,
            first(src,LOAN_COLS) or None,json.dumps(abilities,separators=(",",":")),
            json.dumps(additional,separators=(",",":")),provider,gender_group(src)))
    league_status={}
    for club_key,options in club_league_seen.items():
        # Unknown league on some records and known on others is not itself
        # contradictory; two distinct KNOWN leagues is a true conflict.
        actual={p for p in options if p}
        if len(actual)>1:
            league_status[club_key]=(None,"conflicting_source_leagues",len(actual))
        elif actual:
            league_status[club_key]=(next(iter(actual)),"source_league_name",0)
        else:
            league_status[club_key]=(None,"unknown_not_in_source",0)
    absent=sum(club_key is None for club_key,_,_ in league_status.values())
    conflicts=sum(bool(n) for _,_,n in league_status.values())
    conn.execute("""INSERT INTO editions
      (edition,season,provider,source_sha256,source_player_rows,imported_player_rows,
       club_count,assigned_squad_rows,free_agent_rows,unknown_club_rows,
       missing_league_clubs,conflicting_league_clubs)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",(
      year,season_label(year),provider,source_rec["sha256"],len(source_rows),
      len(players),len(clubs),assigned,free,unknown,absent,conflicts))
    for league_key,(name,sid,level,gender) in sorted(leagues.items()):
        conn.execute("""INSERT INTO leagues
          (league_key,edition,league_name,source_league_id,source_league_level,gender)
          VALUES (?,?,?,?,?,?)""",(league_key,year,name,sid or None,level or None,gender))
    for club_key,(name,sid,gender) in sorted(clubs.items()):
        lk,status,conflict=league_status[club_key]
        conn.execute("""INSERT INTO clubs
          (club_key,edition,name,source_club_id,league_key,league_status,
           league_conflicts,squad_size,source_provider,gender)
          VALUES (?,?,?,?,?,?,?,?,?,?)""",(
            club_key,year,name,sid or None,lk,status,conflict,
            club_sizes[club_key],provider,gender))
    conn.executemany("""INSERT INTO players
       (player_key,edition,source_row_number,source_player_id,
        namespaced_source_player_key,player_name,date_of_birth,nationality,
        preferred_foot,height_cm,weight_kg,source_overall,primary_position,
        alternative_positions,position_fit_indices,club_key,assignment,
        loaned_from,pes_abilities_json,pes_additional_json,source_provider,gender)
       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",players)
    result={
        "edition":year,"season":season_label(year),"source_provider":provider,
        "players":len(players),"clubs":len(clubs),
        "squad_player_rows":assigned,"free_agent_rows":free,"unknown_club_rows":unknown,
        "clubs_with_no_verified_league":absent,"clubs_with_conflicting_source_leagues":conflicts,
        "source_id_collisions":sum(v-1 for v in duplicate_ids.values() if v>1),
        "conflicting_club_names_for_same_club_id":len(conflicting_names),
        "source_roster_complete":False,
        "source_league_is_accepted_official_membership":False,
        "separate_mens_and_womens_clubs":True,
    }
    if assigned+free+unknown!=len(players):raise ValueError("Lost squad assignments")
    print(f"{year}: {len(players):,} players; {len(clubs):,} clubs; "
          f"{assigned:,} club assignments; {free:,} free; {unknown:,} unknown; "
          f"{absent} no league; {conflicts} league conflicts",flush=True)
    return result

def build(source_zip,ratings_zip,out_dir):
    out_dir=Path(out_dir)
    out_dir.mkdir(parents=True,exist_ok=True)
    target=out_dir/"PES_V2_22_EDITION_CLUB_SQUAD_MAP.sqlite"
    if target.exists():raise FileExistsError("Never overwrite an existing squad catalogue")
    with ZipFile(source_zip) as sources,ZipFile(ratings_zip) as converted:
        source_manifest,pes_manifest=get_manifests(sources,converted)
        members=source_members(sources)
        sr={int(r["edition"]):r for r in source_manifest["downloads"]}
        with sqlite3.connect(target) as conn:
            conn.executescript(SCHEMA)
            report={"status":"SOURCE_DERIVED_CLUB_SQUADS_READY_FOR_REVIEW",
              "edition_count":len(YEARS),"FC25_excluded":True,
              "ratings_source_players_expected":319389,
              "source_player_ids_not_guaranteed_unique":True,
              "gender_preserved_when_provided":True,
              "never_merge_womens_and_mens_club_squads":True,
              "data_converted_without_changing_career_or_live_rosters":True,
              "original_game_league_membership_not_verified":True,
              "season_start_date_not_assumed":True,
              "source_derived_club_map":{}}
            for year in YEARS:
                record=process_ed(conn,sources,converted,year,
                       sr[year],pes_manifest["per_edition"][str(year)],members[year])
                report["source_derived_club_map"][str(year)]=record
            total=conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
            if total!=319389:raise ValueError("Source player count mismatch after import")
            conn.commit()
            report["players"]=total
            report["clubs"]=conn.execute("SELECT COUNT(*) FROM clubs").fetchone()[0]
            report["leagues_with_known_source_name"]=conn.execute("SELECT COUNT(*) FROM leagues").fetchone()[0]
            report["players_with_club"]=conn.execute("SELECT COUNT(*) FROM players WHERE assignment='at_club'").fetchone()[0]
            report["free_agents"]=conn.execute("SELECT COUNT(*) FROM players WHERE assignment='free_agent'").fetchone()[0]
            report["unknown_club"]=conn.execute("SELECT COUNT(*) FROM players WHERE assignment='club_unknown'").fetchone()[0]
            report["duplicate_source_id_extras"]=sum(r["source_id_collisions"] for r in report["source_derived_club_map"].values())
            report["source_manifests_sha256"]={
                "selected_source":hashlib.sha256(Path(source_zip).read_bytes()).hexdigest(),
                "converted_ratings":hashlib.sha256(Path(ratings_zip).read_bytes()).hexdigest()}
            if sum(report[k] for k in ("players_with_club","free_agents","unknown_club"))!=total:
                raise ValueError("Player assignment parity failed")
            export_summary(conn,out_dir,report)
    return report

def export_summary(conn,out_dir,report):
    (out_dir/"CLUB_SQUAD_MAPPING_MANIFEST.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    # Useful small, inspectable club/competition mapping without a giant CSV.
    with (out_dir/"PES_V2_ALL_EDITION_CLUBS.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.writer(f)
        writer.writerow(("edition","season","club_key","club_name","source_club_id",
                         "league_name","league_status","squad_players","source_provider","gender"))
        for r in conn.execute("""SELECT c.edition,e.season,c.club_key,c.name,
                          c.source_club_id,l.league_name,c.league_status,c.squad_size,
                          c.source_provider,c.gender FROM clubs c
                          JOIN editions e ON e.edition=c.edition
                          LEFT JOIN leagues l ON l.league_key=c.league_key
                          ORDER BY c.edition,c.name"""):
            writer.writerow(r)
    (out_dir/"README.txt").write_text(
        "PES V2 HISTORICAL CLUB AND SQUAD DATABASE STARTER\n"
        "Choose a FIFA edition (2005–2027 excluding FC25); each edition has\n"
        "separate clubs, direct source squad records and 25+4 rating estimates.\n"
        "Leagues are populated ONLY where specifically given in source data.\n"
        "Men and women teams never share a club key when source gender exists.\n"\n        "Unknown club and unattached players are kept separately, not assigned\n"
        "to invented clubs. No automatic cross-year/source club identity merge.\n"
        "Original source IDs sometimes repeat; stable player_key uses edition\n"
        "and source row ordinal; raw ID and provider are retained unchanged.\n"
        "SQLite is a separate read-only starter catalogue, not a live career.\n"
        "Not an original-game-complete verified roster or a PES option file.\n",
        encoding="utf-8")

def available_editions(conn):
    return [dict(zip(("edition","season","players","clubs","assigned","free_agents",
                      "unknown_club","unmapped_league_clubs"),row))
            for row in conn.execute("""SELECT edition,season,imported_player_rows,
                 club_count,assigned_squad_rows,free_agent_rows,unknown_club_rows,
                 missing_league_clubs FROM editions ORDER BY edition""")]

def select_edition(conn,edition,*,limit=100):
    """Read-only career setup preview; never create or modify a saved career."""
    if edition not in YEARS:raise ValueError("Unknown FIFA edition or excluded FC25")
    summary=conn.execute("""SELECT season,imported_player_rows,club_count,
      assigned_squad_rows,free_agent_rows,unknown_club_rows FROM editions
      WHERE edition=?""",(edition,)).fetchone()
    if not summary:raise ValueError("Edition not built")
    clubs=conn.execute("""SELECT c.club_key,c.name,c.squad_size,
      l.league_name,c.league_status,c.gender FROM clubs c
      LEFT JOIN leagues l ON l.league_key=c.league_key
      WHERE c.edition=? ORDER BY c.squad_size DESC,c.name LIMIT ?""",(edition,limit)).fetchall()
    return {"edition":edition,"season":summary[0],"players":summary[1],
      "club_count":summary[2],"assigned":summary[3],"free_agents":summary[4],
      "unknown_club":summary[5],
      "club_preview":[{"club_key":r[0],"name":r[1],"squad_size":r[2],
         "league":r[3],"league_status":r[4],"gender":r[5]} for r in clubs]}

def club_squad(conn,edition,club_key):
    club=conn.execute("""SELECT c.name,l.league_name,c.squad_size,c.gender
          FROM clubs c LEFT JOIN leagues l ON l.league_key=c.league_key
          WHERE c.edition=? AND c.club_key=?""",(edition,club_key)).fetchone()
    if not club:raise ValueError("Club not found in selected edition")
    players=[dict(zip(("player_key","player_name","source_player_id","overall",
       "primary_position","nationality","birthdate","source_loan"),p))
       for p in conn.execute("""SELECT player_key,player_name,source_player_id,
            source_overall,primary_position,nationality,date_of_birth,loaned_from
            FROM players WHERE edition=? AND club_key=?
            ORDER BY source_overall DESC,player_name""",(edition,club_key))]
    if len(players)!=club[2]:raise ValueError("Squad count inconsistency")
    return {"edition":edition,"club_key":club_key,"club":club[0],
            "league":club[1],"squad_size":club[2],"gender":club[3],"players":players}

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--sources",required=True)
    p.add_argument("--ratings",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    print(json.dumps(build(a.sources,a.ratings,a.output),indent=2),flush=True)

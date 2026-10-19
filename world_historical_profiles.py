"""Rights-aware, source-ID-based enrichment for historical PES career datasets.

This does NOT extract Football Manager data. It accepts explicitly permitted,
independently obtained records and keeps source provenance. Unknown facts stay
NULL. The core world_import JSON snapshot must be installed first.
"""
from datetime import date
import json
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_dataset_data_rights(
 dataset_id TEXT PRIMARY KEY REFERENCES world_datasets(dataset_id),
 source_name TEXT NOT NULL,
 source_url TEXT,
 rights_basis TEXT NOT NULL CHECK(rights_basis IN
 ('licensed','open_data','original_research')),
 rights_note TEXT NOT NULL,
 imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS world_dataset_manager_profiles(
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 external_id TEXT NOT NULL,
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 full_name TEXT NOT NULL,
 nationality TEXT,
 preferred_formation TEXT,
 tactical_style TEXT,
 source_name TEXT NOT NULL,
 PRIMARY KEY(dataset_id,external_id)
);
CREATE TABLE IF NOT EXISTS world_dataset_contract_snapshots(
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 weekly_wage_gbp INTEGER CHECK(weekly_wage_gbp >= 0),
 expires_on TEXT,
 renewal_status TEXT NOT NULL DEFAULT 'unknown' CHECK(renewal_status IN
 ('unknown','open','unwilling','negotiating','agreed')),
 source_name TEXT NOT NULL,
 PRIMARY KEY(dataset_id,player_id)
);
CREATE TABLE IF NOT EXISTS world_dataset_transfer_history(
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 external_event_id TEXT NOT NULL,
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 from_club_id INTEGER REFERENCES world_clubs(club_id),
 to_club_id INTEGER REFERENCES world_clubs(club_id),
 date_effective TEXT NOT NULL,
 transfer_type TEXT NOT NULL CHECK(transfer_type IN ('permanent','loan','free')),
 fee_gbp INTEGER CHECK(fee_gbp >= 0),
 source_name TEXT NOT NULL,
 PRIMARY KEY(dataset_id,external_event_id)
);
CREATE TABLE IF NOT EXISTS world_dataset_extended_attributes(
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 attribute TEXT NOT NULL,
 value INTEGER NOT NULL CHECK(value BETWEEN 1 AND 200),
 source_name TEXT NOT NULL,
 PRIMARY KEY(dataset_id,player_id,attribute)
);
CREATE TABLE IF NOT EXISTS world_dataset_club_finances(
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 transfer_budget_gbp INTEGER NOT NULL CHECK(transfer_budget_gbp >= 0),
 weekly_wage_budget_gbp INTEGER NOT NULL CHECK(weekly_wage_budget_gbp >= 0),
 source_name TEXT NOT NULL,
 PRIMARY KEY(dataset_id,club_id)
);
"""

def initialize_historical_profiles(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def _date(v,label):
    try:
        if v is not None: date.fromisoformat(v)
    except (TypeError,ValueError):
        raise ValueError(label+" must be an ISO date or null")


def _money(v,label):
    if v is not None and (type(v) is not int or v<0):
        raise ValueError(label+" must be a nonnegative number of whole GBP")


def _lookup_club(conn, dataset, item, key):
    src=item.get(key+"_source","dataset-club:"+dataset)
    ext=item.get(key)
    if ext is None: return None
    row=conn.execute("""SELECT c.club_id FROM world_dataset_club_refs c
        JOIN world_dataset_entries e ON e.club_id=c.club_id
        WHERE c.source=? AND c.external_id=? AND e.dataset_id=?""",
        (src,str(ext),dataset)).fetchone()
    if row is None:raise ValueError("Unmatched source club: "+str(ext))
    return row[0]


def _lookup_player(conn, dataset, item):
    src=item.get("player_source","dataset-player:"+dataset)
    ext=item.get("player")
    row=conn.execute("""SELECT p.player_id FROM world_player_source_refs p
        JOIN world_dataset_rosters r ON r.player_id=p.player_id
        WHERE p.source_name=? AND p.external_id=? AND r.dataset_id=?""",
        (src,str(ext),dataset)).fetchone()
    if row is None:raise ValueError("Unmatched source player: "+str(ext))
    return row[0]


def import_enrichment(conn, payload):
    """Atomic optional managers/contracts/attributes/history/budget import.

    The caller must attest legitimate rights; this is provenance, not an
    independent legal verification. Existing snapshots are never overwritten.
    """
    if not isinstance(payload,dict):
        raise ValueError("Enrichment must be a JSON object")
    dataset=payload.get("dataset_id")
    source=payload.get("source_name")
    rights=payload.get("rights_basis")
    note=payload.get("rights_note")
    if not all(isinstance(x,str) and x.strip() for x in (dataset,source,note)):
        raise ValueError("dataset_id, source_name and rights_note are required")
    if rights not in ("licensed","open_data","original_research"):
        raise ValueError("Specify the documented permission/rights basis")
    for section in ("managers","contracts","transfers","attributes","club_finances"):
        if not isinstance(payload.get(section,[]),list):
            raise ValueError(section+" must be a list")
    initialize_historical_profiles(conn)
    from world_import import install_import_schema
    install_import_schema(conn)
    if not conn.execute("SELECT 1 FROM world_datasets WHERE dataset_id=?",(dataset,)).fetchone():
        raise ValueError("Import the core historical dataset first")
    if conn.execute("SELECT 1 FROM world_dataset_data_rights WHERE dataset_id=?",(dataset,)).fetchone():
        raise ValueError("This dataset already has an enrichment; create a new version")
    conn.commit()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("""INSERT INTO world_dataset_data_rights
            (dataset_id,source_name,source_url,rights_basis,rights_note)
            VALUES(?,?,?,?,?)""",(dataset,source,payload.get("source_url"),rights,note))
        seen_managers=set()
        for m in payload.get("managers",[]):
            mid=str(m["id"])
            if mid in seen_managers:raise ValueError("Duplicate manager source ID "+mid)
            seen_managers.add(mid)
            club=_lookup_club(conn,dataset,m,"club")
            if club is None or not str(m.get("name","")).strip():
                raise ValueError("Manager needs a mapped club and name")
            conn.execute("""INSERT INTO world_dataset_manager_profiles
                (dataset_id,external_id,club_id,full_name,nationality,
                 preferred_formation,tactical_style,source_name)
                 VALUES(?,?,?,?,?,?,?,?)""",
                (dataset,mid,club,m["name"],m.get("nationality"),
                 m.get("preferred_formation"),m.get("tactical_style"),source))
        for c in payload.get("contracts",[]):
            player=_lookup_player(conn,dataset,c)
            club=_lookup_club(conn,dataset,c,"club")
            if club is None:raise ValueError("Contract club required")
            actual=conn.execute("""SELECT 1 FROM world_dataset_rosters
                WHERE dataset_id=? AND player_id=? AND club_id=?""",
                (dataset,player,club)).fetchone()
            if not actual:raise ValueError("Contract club not player parent club")
            _date(c.get("expires_on"),"expires_on")
            wage=c.get("weekly_wage_gbp")
            _money(wage,"weekly_wage_gbp")
            status=c.get("renewal_status","unknown")
            if status not in ("unknown","open","unwilling","negotiating","agreed"):
                raise ValueError("Invalid renewal status")
            conn.execute("""INSERT INTO world_dataset_contract_snapshots
                (dataset_id,player_id,club_id,weekly_wage_gbp,expires_on,
                 renewal_status,source_name) VALUES(?,?,?,?,?,?,?)""",
                (dataset,player,club,wage,c.get("expires_on"),status,source))
        for t in payload.get("transfers",[]):
            player=_lookup_player(conn,dataset,t)
            src=_lookup_club(conn,dataset,t,"from_club")
            dest=_lookup_club(conn,dataset,t,"to_club")
            if src is None and dest is None: raise ValueError("Transfer needs a club")
            _date(t.get("date"),"transfer date")
            if t.get("date") is None:raise ValueError("Transfer date missing")
            kind=t.get("type","permanent")
            if kind not in ("permanent","loan","free"):
                raise ValueError("Invalid transfer type")
            fee=t.get("fee_gbp")
            _money(fee,"fee_gbp")
            conn.execute("""INSERT INTO world_dataset_transfer_history
                (dataset_id,external_event_id,player_id,from_club_id,to_club_id,
                 date_effective,transfer_type,fee_gbp,source_name)
                 VALUES(?,?,?,?,?,?,?,?,?)""",
                (dataset,str(t["id"]),player,src,dest,t["date"],kind,fee,source))
        for a in payload.get("attributes",[]):
            player=_lookup_player(conn,dataset,a)
            value=a.get("value")
            if type(value) is not int or not 1<=value<=200:
                raise ValueError("Attribute must be an integer from 1 to 200")
            name=a.get("attribute")
            if not isinstance(name,str) or not name.strip():
                raise ValueError("Attribute name required")
            conn.execute("""INSERT INTO world_dataset_extended_attributes
                (dataset_id,player_id,attribute,value,source_name)
                VALUES(?,?,?,?,?)""",(dataset,player,name,value,source))
        for f in payload.get("club_finances",[]):
            club=_lookup_club(conn,dataset,f,"club")
            if club is None:raise ValueError("Finance record club required")
            b=f.get("transfer_budget_gbp")
            w=f.get("weekly_wage_budget_gbp")
            _money(b,"transfer budget")
            _money(w,"wage budget")
            if b is None or w is None:raise ValueError("Finance record needs both budgets")
            conn.execute("""INSERT INTO world_dataset_club_finances
                (dataset_id,club_id,transfer_budget_gbp,weekly_wage_budget_gbp,source_name)
                VALUES(?,?,?,?,?)""",(dataset,club,b,w,source))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {k:len(payload.get(k,[])) for k in
            ("managers","contracts","transfers","attributes","club_finances")}


if __name__=="__main__":
    import sys
    if len(sys.argv)!=3:
        raise SystemExit("Usage: python world_historical_profiles.py ENRICHMENT.json SQLITE.db")
    with sqlite3.connect(sys.argv[2]) as db:
        db.execute("PRAGMA foreign_keys=ON")
        print(json.dumps(import_enrichment(db,json.load(open(sys.argv[1],encoding="utf-8"))),indent=2))

"""Versioned Football World JSON importer, isolated from existing careers.

Input requires explicit source-scoped player/club IDs. Preview validates without
mutating the database. Apply creates a NEW immutable dataset in one transaction.
For pre-existing identities, matching is by exact source reference, never name.
"""
import json
import re
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path

COLUMNS = ("pace", "shooting", "passing", "dribbling", "defending", "physicality")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$")
SEASON_RE = re.compile(r"^\d{4}/\d{2}$")


def validate_payload(obj):
    errors = []
    if not isinstance(obj, dict):
        return ["Payload must be a JSON object"]
    meta = obj.get("dataset", {})
    if not isinstance(meta, dict):
        return ["dataset must be an object"]
    dataset_id = meta.get("id")
    season = meta.get("season")
    if not isinstance(dataset_id, str) or not ID_RE.fullmatch(dataset_id):
        errors.append("dataset.id must be a unique slug (3-80 characters)")
    if not isinstance(season, str) or not SEASON_RE.fullmatch(season) or int(season[5:]) != (int(season[:4])+1)%100:
        errors.append("dataset.season must resemble 2004/05")
    if not isinstance(meta.get("title"), str) or not meta["title"].strip():
        errors.append("dataset.title is required")
    if not isinstance(meta.get("source"), str) or not meta["source"].strip():
        errors.append("dataset.source is required")
    try:
        date.fromisoformat(meta["source_date"])
    except (ValueError, KeyError, TypeError):
        errors.append("dataset.source_date must be YYYY-MM-DD")
    clubs = obj.get("clubs", [])
    players = obj.get("players", [])
    if not isinstance(clubs, list) or not isinstance(players, list):
        return errors + ["clubs and players must be arrays"]
    if not clubs:
        errors.append("At least one club required")
    club_keys, player_keys = set(), set()
    for i, club in enumerate(clubs):
        if not isinstance(club, dict):
            errors.append(f"clubs[{i}] not an object"); continue
        k = club.get("id")
        if not isinstance(k, str) or not ID_RE.fullmatch(k):
            errors.append(f"clubs[{i}].id invalid")
        elif k in club_keys:
            errors.append(f"Duplicate club id: {k}")
        club_keys.add(k)
        if not isinstance(club.get("name"), str) or not club["name"].strip():
            errors.append(f"clubs[{i}].name missing")
        if not isinstance(club.get("competition"), str) or not ID_RE.fullmatch(club["competition"]):
            errors.append(f"clubs[{i}].competition invalid")
    for i, player in enumerate(players):
        if not isinstance(player, dict):
            errors.append(f"players[{i}] not an object"); continue
        k = player.get("id")
        if not isinstance(k, str) or not ID_RE.fullmatch(k):
            errors.append(f"players[{i}].id invalid")
        elif k in player_keys:
            errors.append(f"Duplicate player id: {k}")
        player_keys.add(k)
        if player.get("club") not in club_keys:
            errors.append(f"players[{i}] references unknown club")
        if not isinstance(player.get("name"), str) or not player["name"].strip():
            errors.append(f"players[{i}].name missing")
        if player.get("birth_date") is not None:
            try:
                date.fromisoformat(player["birth_date"])
            except (ValueError, TypeError):
                errors.append(f"players[{i}].birth_date invalid")
        rating = player.get("rating")
        if rating is not None:
            if not isinstance(rating, dict):
                errors.append(f"players[{i}].rating must be object"); continue
            if not isinstance(rating.get("overall"), int) or isinstance(rating.get("overall"), bool) or not 1 <= rating["overall"] <= 99:
                errors.append(f"players[{i}].rating.overall invalid")
            for field in COLUMNS:
                value = rating.get(field)
                if value is not None and (not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 99):
                    errors.append(f"players[{i}].rating.{field} invalid")
    return errors


def preview(obj, conn=None):
    errors = validate_payload(obj)
    if conn is not None and not errors:
        if conn.execute("SELECT 1 FROM world_datasets WHERE dataset_id=?", (obj["dataset"]["id"],)).fetchone():
            errors.append("Dataset id already exists. Use a new version; existing snapshots cannot be overwritten.")
        leagues = {r[0] for r in conn.execute("SELECT competition_id FROM world_competitions")}
        for club in obj["clubs"]:
            if club["competition"] not in leagues:
                errors.append("Unknown competition: " + club["competition"])
    return {"valid": not errors, "errors": errors, "clubs": len(obj.get("clubs", [])) if isinstance(obj.get("clubs"),list) else 0,
            "players": len(obj.get("players", [])) if isinstance(obj.get("players"),list) else 0,
            "rated": sum(isinstance(p, dict) and isinstance(p.get("rating"),dict) for p in obj.get("players",[]) if isinstance(obj.get("players"),list))}


def apply(obj, conn):
    """Atomic new dataset creation. Caller should have initialized world schema."""
    outcome = preview(obj, conn)
    if not outcome["valid"]:
        raise ValueError("; ".join(outcome["errors"]))
    meta = obj["dataset"]
    club_source = "dataset-club:" + meta["id"]
    player_source = "dataset-player:" + meta["id"]
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT OR IGNORE INTO world_seasons(season_id,label) VALUES (?,?)", (meta["season"],meta["season"]))
        conn.execute("""INSERT INTO world_datasets(dataset_id,season_id,title,source_label,source_date,status,is_career_active)
            VALUES (?,?,?,?,?,'review',0)""", (meta["id"],meta["season"],meta["title"],meta["source"],meta["source_date"]))
        clubs = {}
        for c in obj["clubs"]:
            # Club identity requires external explicit IDs. Never merge on name by guessing.
            existing = conn.execute("SELECT club_id FROM world_dataset_club_refs WHERE source=? AND external_id=?",
                                    (c.get("identity_source",club_source),c["id"])).fetchone()
            if existing:
                cid=existing[0]
            else:
                # Historical club names can match shared identity when explicitly asserted.
                # Otherwise create a new entry; the source id remains the authoritative mapping.
                row=conn.execute("SELECT club_id FROM world_clubs WHERE name=?", (c["name"],)).fetchone()
                if row and c.get("reuse_name_identity",False):
                    cid=row[0]
                else:
                    name=c["name"]
                    if row:
                        name=f"{name} [{meta['id']}]"
                    cid=conn.execute("INSERT INTO world_clubs(name,nation) VALUES (?,?)",(name,c.get("nation","England"))).lastrowid
                conn.execute("INSERT INTO world_dataset_club_refs(source,external_id,club_id) VALUES (?,?,?)",
                             (c.get("identity_source",club_source),c["id"],cid))
            clubs[c["id"]]=cid
            conn.execute("""INSERT INTO world_dataset_entries(dataset_id,competition_id,club_id)
                        VALUES (?,?,?)""",(meta["id"],c["competition"],cid))
        for p in obj["players"]:
            source=p.get("identity_source",player_source)
            row=conn.execute("SELECT player_id FROM world_player_source_refs WHERE source_name=? AND external_id=?",(source,p["id"])).fetchone()
            if row:
                pid=row[0]
            else:
                pid=conn.execute("""INSERT INTO world_players(full_name,birth_date,nationality,primary_position,source_url)
                          VALUES (?,?,?,?,?)""",(p["name"],p.get("birth_date"),p.get("nationality"),p.get("position"),meta["source"])).lastrowid
                conn.execute("""INSERT INTO world_player_source_refs(player_id,source_name,external_id,source_url,identity_status)
                          VALUES (?,?,?,?,'provisional')""",(pid,source,p["id"],meta["source"]))
            conn.execute("""INSERT INTO world_dataset_rosters(dataset_id,player_id,club_id,evidence,verification_status)
                     VALUES (?,?,?,?,?)""",(meta["id"],pid,clubs[p["club"]],meta["source"],"provisional"))
            rating=p.get("rating")
            if rating:
                conn.execute("""INSERT INTO world_dataset_ratings(dataset_id,player_id,source_name,source_edition,source_date,
                         external_player_id,overall,pace,shooting,passing,dribbling,defending,physicality)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (meta["id"],pid,meta["source"],meta["season"],meta["source_date"],p["id"],
                          rating["overall"],*(rating.get(k) for k in COLUMNS)))
        conn.commit()
        return outcome
    except Exception:
        conn.rollback()
        raise


def install_import_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS world_dataset_club_refs(
        source TEXT NOT NULL, external_id TEXT NOT NULL,
        club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
        PRIMARY KEY(source,external_id))""")


if __name__ == "__main__":
    import sys
    from world_v2 import initialize_world
    from world_explorer import initialize_catalog
    if len(sys.argv) not in (3,4):
        raise SystemExit("Usage: python world_import.py INPUT.json SQLITE.db [--apply]")
    obj=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    with sqlite3.connect(sys.argv[2]) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        initialize_world(conn)
        initialize_catalog(conn)
        install_import_schema(conn)
        if len(sys.argv)==4 and sys.argv[3]=="--apply":
            result=apply(obj,conn)
        else:
            result=preview(obj,conn)
        print(json.dumps(result,indent=2))
        if not result["valid"]:sys.exit(2)

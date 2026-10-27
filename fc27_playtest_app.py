"""Dedicated authenticated FC27 manual-playtest app. No live/production routes.

Render boots ONLY the approved 659-club frozen world, not any existing
PES challenge save. Careers in this preview are disposable test scenarios.
"""
import os
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, redirect
from scripts.fc27_warehouse_world_bridge import DATASET
from world_career_play import create_play_blueprint

if os.getenv("FC27_PRESEASON_PLAYTEST_ENABLED") != "1":
    raise RuntimeError("Explicit FC27_PRESEASON_PLAYTEST_ENABLED=1 required")
if not os.getenv("WORLD_MARKET_ACCESS_KEY") or not os.getenv("WORLD_MARKET_COOKIE_SECRET"):
    raise RuntimeError("Refusing public preview without login and session keys")

db_path = Path(os.getenv("DATABASE_PATH", "")).resolve()
if not db_path.is_file():
    raise RuntimeError("FC27 frozen starter SQLite missing: run preview build before boot")

def source_coverage():
    with sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True) as conn:
        clubs=conn.execute(
            "SELECT COUNT(*) FROM world_dataset_entries WHERE dataset_id=?",
            (DATASET,)).fetchone()[0]
        players=conn.execute(
            "SELECT COUNT(*) FROM world_dataset_rosters WHERE dataset_id=?",
            (DATASET,)).fetchone()[0]
        leagues=conn.execute(
            "SELECT COUNT(DISTINCT competition_id) FROM world_dataset_entries WHERE dataset_id=?",
            (DATASET,)).fetchone()[0]
        metadata=conn.execute(
            "SELECT source_clubs,source_players,original_source_competitions "
            "FROM fc27_warehouse_import_audit WHERE dataset_id=?",
            (DATASET,)).fetchone()
    if (clubs, players, leagues)!=(659,17593,53) or metadata!=(659,17593,53):
        raise RuntimeError(f"FC27 source validation failed: {clubs,players,leagues,metadata}")
    return dict(clubs=clubs,players=players,competitions=leagues)

COVERAGE=source_coverage()
app=Flask("fc27_dedicated_manual_playtest")
app.register_blueprint(create_play_blueprint(db_path))

@app.get("/")
def root():
    return redirect("/world/play")

@app.get("/healthz")
def healthz():
    return jsonify(status="ready",dataset=DATASET,**COVERAGE)

# The full challenge app is intentionally not mounted; route legacy links back
# into the isolated Career Desk rather than 404ing or exposing production saves.
@app.get("/world/explore")
@app.get("/world/market")
@app.get("/world/careers")
@app.get("/world/reputations")
@app.get("/world/reputations/progression")
@app.get("/world/player-decisions")
def outside_preview():
    return redirect("/world/play")

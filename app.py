from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import sqlite3
import random
import math
import traceback
import time
import shutil
from collections import Counter
import os
from pathlib import Path
from datetime import datetime

try:
    import psycopg2
except ImportError:
    psycopg2 = None


APP_DIR = Path(__file__).parent
BUNDLED_DB_PATH = APP_DIR / "pes_manager_career_v1.db"
DEFAULT_RENDER_DISK_DIR = Path("/var/data")
SUPABASE_DATABASE_URL = os.environ.get("DATABASE_URL")
SUPABASE_SAVE_KEY = os.environ.get("SUPABASE_SAVE_KEY", "main")
SUPABASE_SYNC_TABLE = "pes_save_store"
SUPABASE_LOCAL_DB_PATH = Path(os.environ.get("SUPABASE_LOCAL_DB_PATH", "/tmp/pes_manager_career_v1.db"))


def using_supabase_sync():
    return bool(SUPABASE_DATABASE_URL)


def resolve_database_path():
    """Choose the live SQLite file path.

    With DATABASE_URL set, the app still runs on SQLite locally, but the DB file
    is restored from and synced back to Supabase Postgres. This avoids a risky
    full app rewrite while still surviving Render Free restarts.

    Priority:
    1. Supabase sync local working file in /tmp when DATABASE_URL exists.
    2. Explicit DATABASE_PATH.
    3. Render persistent disk mounted at /var/data.
    4. Bundled repo database as local/dev fallback.
    """
    if using_supabase_sync():
        return SUPABASE_LOCAL_DB_PATH

    env_path = os.environ.get("DATABASE_PATH")
    if env_path:
        return Path(env_path)

    if DEFAULT_RENDER_DISK_DIR.exists():
        return DEFAULT_RENDER_DISK_DIR / "pes_manager_career_v1.db"

    return BUNDLED_DB_PATH


DB_PATH = resolve_database_path()


def supabase_connection():
    if not SUPABASE_DATABASE_URL:
        return None

    if psycopg2 is None:
        raise RuntimeError("DATABASE_URL is set but psycopg2 is not installed.")

    return psycopg2.connect(SUPABASE_DATABASE_URL, sslmode="require")


def ensure_supabase_save_table():
    if not using_supabase_sync():
        return

    with supabase_connection() as pg:
        with pg.cursor() as cur:
            cur.execute(f'''
                CREATE TABLE IF NOT EXISTS {SUPABASE_SYNC_TABLE} (
                    save_key TEXT PRIMARY KEY,
                    db_bytes BYTEA NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            ''')


def upload_sqlite_save_to_supabase(reason="sync"):
    """Upload the live SQLite DB bytes to Supabase Postgres."""
    if not using_supabase_sync():
        return False

    if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        return False

    ensure_supabase_save_table()
    db_bytes = DB_PATH.read_bytes()

    with supabase_connection() as pg:
        with pg.cursor() as cur:
            cur.execute(
                f'''
                INSERT INTO {SUPABASE_SYNC_TABLE}(save_key, db_bytes, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (save_key)
                DO UPDATE SET db_bytes=EXCLUDED.db_bytes, updated_at=NOW()
                ''',
                (SUPABASE_SAVE_KEY, psycopg2.Binary(db_bytes)),
            )

    return True


def restore_sqlite_save_from_supabase():
    """Restore the latest SQLite DB bytes from Supabase if present."""
    if not using_supabase_sync():
        return False

    ensure_supabase_save_table()

    with supabase_connection() as pg:
        with pg.cursor() as cur:
            cur.execute(
                f"SELECT db_bytes FROM {SUPABASE_SYNC_TABLE} WHERE save_key=%s",
                (SUPABASE_SAVE_KEY,),
            )
            row = cur.fetchone()

    if not row:
        return False

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = bytes(row[0])
    tmp_path = DB_PATH.with_suffix(".restore.tmp")
    tmp_path.write_bytes(data)
    tmp_path.replace(DB_PATH)
    return True


def prepare_database_file():
    """Prepare the live SQLite file.

    Supabase mode:
    - first boot restores the DB from Supabase if one exists
    - if Supabase is empty, seed from the bundled starter DB and upload it once

    Non-Supabase mode:
    - keep the existing Render disk / bundled DB behaviour
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if using_supabase_sync():
        try:
            restored = restore_sqlite_save_from_supabase()
            if restored:
                return
        except Exception:
            traceback.print_exc()

        if BUNDLED_DB_PATH.exists():
            shutil.copy2(BUNDLED_DB_PATH, DB_PATH)

        try:
            upload_sqlite_save_to_supabase("initial-seed")
        except Exception:
            traceback.print_exc()

        return

    if DB_PATH.exists() and DB_PATH.stat().st_size > 0:
        return

    if DB_PATH != BUNDLED_DB_PATH and BUNDLED_DB_PATH.exists():
        shutil.copy2(BUNDLED_DB_PATH, DB_PATH)


prepare_database_file()

HUMAN_PLAYERS = ['Matt Kerry', 'James Pegg', 'Stupid Mole', 'Jake Brown', 'Jack Carnell', 'Tim Rees', 'Josh Stephenson']

# Remote crest URLs are used for convenience. If a file exists at
# static/logos/<slug>.png, the local file will be used instead.
TEAM_LOGO_URLS = {'Barnsley': "https://assets.footylogos.com/logos/barnsley/barnsley-logo-footylogos.svg", 'Birmingham City': "https://assets.footylogos.com/logos/birmingham-city/birmingham-city-logo-footylogos.svg", 'Blackburn Rovers': 'https://crests.football-data.org/59.png', 'Brentford': 'https://crests.football-data.org/402.png', 'Bristol City': 'https://crests.football-data.org/387.png', 'Cardiff City': 'https://crests.football-data.org/715.png', 'Charlton Athletic': "https://assets.footylogos.com/logos/charlton-athletic/charlton-athletic-logo-footylogos.svg", 'Derby County': 'https://crests.football-data.org/342.png', 'Fulham': 'https://crests.football-data.org/63.png', 'Huddersfield Town': 'https://crests.football-data.org/394.png', 'Hull City': 'https://crests.football-data.org/322.png', 'Leeds United': 'https://crests.football-data.org/341.png', 'Luton Town': 'https://crests.football-data.org/389.png', 'Middlesbrough': 'https://crests.football-data.org/343.png', 'Millwall': 'https://crests.football-data.org/384.png', 'Nottingham Forest': 'https://crests.football-data.org/351.png', 'Preston North End': 'https://crests.football-data.org/1081.png', 'QPR': 'https://crests.football-data.org/69.png', 'Reading': 'https://crests.football-data.org/355.png', 'Sheffield Wednesday': 'https://crests.football-data.org/345.png', 'Stoke City': 'https://crests.football-data.org/70.png', 'Swansea City': 'https://crests.football-data.org/72.png', 'West Bromwich Albion': 'https://crests.football-data.org/74.png', 'Wigan Athletic': 'https://crests.football-data.org/75.png', 'Preston': 'https://crests.football-data.org/1081.png', 'West Brom': 'https://crests.football-data.org/74.png', 'Nottm Forest': 'https://crests.football-data.org/351.png', 'Sheff Wed': 'https://crests.football-data.org/345.png', 'Burnley': 'https://crests.football-data.org/328.png', 'Coventry City': 'https://crests.football-data.org/1076.png', 'Norwich City': 'https://crests.football-data.org/68.png', 'Oxford United': 'https://crests.football-data.org/1082.png', 'Plymouth Argyle': 'https://crests.football-data.org/1138.png', 'Portsmouth': 'https://crests.football-data.org/325.png', 'Rotherham United': 'https://crests.football-data.org/385.png', 'Sheffield United': 'https://crests.football-data.org/356.png', 'Sunderland': 'https://crests.football-data.org/71.png', 'Watford': 'https://crests.football-data.org/346.png', 'Arsenal': 'https://crests.football-data.org/57.png', 'Aston Villa': 'https://crests.football-data.org/58.png', 'AFC Bournemouth': 'https://crests.football-data.org/1044.png', 'Brighton & Hove Albion': 'https://crests.football-data.org/397.png', 'Chelsea': 'https://crests.football-data.org/61.png', 'Crystal Palace': 'https://crests.football-data.org/354.png', 'Everton': 'https://crests.football-data.org/62.png', 'Leicester City': 'https://crests.football-data.org/338.png', 'Liverpool': 'https://crests.football-data.org/64.png', 'Manchester City': 'https://crests.football-data.org/65.png', 'Manchester United': 'https://crests.football-data.org/66.png', 'Newcastle United': 'https://crests.football-data.org/67.png', 'Southampton': 'https://crests.football-data.org/340.png', 'Tottenham Hotspur': 'https://crests.football-data.org/73.png', 'West Ham United': 'https://crests.football-data.org/563.png', 'Wolverhampton Wanderers': 'https://crests.football-data.org/76.png'}

PROBLEM_BADGE_REMOTE_PRIORITY = {'Barnsley', 'Birmingham City', 'Charlton Athletic'}

TEAM_LOGO_ALIASES = {'Preston': 'Preston North End', 'West Brom': 'West Bromwich Albion', 'Nottm Forest': 'Nottingham Forest', 'Sheff Wed': 'Sheffield Wednesday'}



# v18.66 additional 2020/21 Championship crest
TEAM_LOGO_URLS.setdefault("Wycombe Wanderers", "https://crests.football-data.org/1146.png")

DERBY_RESET_OPENING_STATS = [{'team_name': 'West Bromwich Albion', 'played': 38, 'won': 19, 'drawn': 14, 'lost': 5, 'goals_for': 64, 'goals_against': 37, 'goal_difference': 27, 'points': 71}, {'team_name': 'Leeds United', 'played': 38, 'won': 21, 'drawn': 8, 'lost': 9, 'goals_for': 56, 'goals_against': 32, 'goal_difference': 24, 'points': 71}, {'team_name': 'Fulham', 'played': 38, 'won': 18, 'drawn': 10, 'lost': 10, 'goals_for': 52, 'goals_against': 40, 'goal_difference': 12, 'points': 64}, {'team_name': 'Brentford', 'played': 38, 'won': 18, 'drawn': 9, 'lost': 11, 'goals_for': 66, 'goals_against': 33, 'goal_difference': 33, 'points': 63}, {'team_name': 'Nottingham Forest', 'played': 38, 'won': 16, 'drawn': 13, 'lost': 9, 'goals_for': 49, 'goals_against': 39, 'goal_difference': 10, 'points': 61}, {'team_name': 'Preston North End', 'played': 38, 'won': 16, 'drawn': 9, 'lost': 13, 'goals_for': 51, 'goals_against': 46, 'goal_difference': 5, 'points': 57}, {'team_name': 'Cardiff City', 'played': 38, 'won': 14, 'drawn': 15, 'lost': 9, 'goals_for': 54, 'goals_against': 50, 'goal_difference': 4, 'points': 57}, {'team_name': 'Blackburn Rovers', 'played': 38, 'won': 15, 'drawn': 11, 'lost': 12, 'goals_for': 55, 'goals_against': 46, 'goal_difference': 9, 'points': 56}, {'team_name': 'Swansea City', 'played': 38, 'won': 14, 'drawn': 14, 'lost': 10, 'goals_for': 49, 'goals_against': 45, 'goal_difference': 4, 'points': 56}, {'team_name': 'Bristol City', 'played': 38, 'won': 15, 'drawn': 10, 'lost': 13, 'goals_for': 52, 'goals_against': 56, 'goal_difference': -4, 'points': 55}, {'team_name': 'Millwall', 'played': 38, 'won': 13, 'drawn': 15, 'lost': 10, 'goals_for': 46, 'goals_against': 43, 'goal_difference': 3, 'points': 54}, {'team_name': 'Derby County', 'played': 38, 'won': 14, 'drawn': 12, 'lost': 12, 'goals_for': 52, 'goals_against': 51, 'goal_difference': 1, 'points': 54}, {'team_name': 'QPR', 'played': 38, 'won': 14, 'drawn': 8, 'lost': 16, 'goals_for': 58, 'goals_against': 63, 'goal_difference': -5, 'points': 50}, {'team_name': 'Reading', 'played': 38, 'won': 13, 'drawn': 10, 'lost': 15, 'goals_for': 47, 'goals_against': 43, 'goal_difference': 4, 'points': 49}, {'team_name': 'Sheffield Wednesday', 'played': 38, 'won': 13, 'drawn': 10, 'lost': 15, 'goals_for': 47, 'goals_against': 50, 'goal_difference': -3, 'points': 49}, {'team_name': 'Birmingham City', 'played': 38, 'won': 12, 'drawn': 12, 'lost': 14, 'goals_for': 48, 'goals_against': 57, 'goal_difference': -9, 'points': 48}, {'team_name': 'Wigan Athletic', 'played': 38, 'won': 11, 'drawn': 11, 'lost': 16, 'goals_for': 40, 'goals_against': 50, 'goal_difference': -10, 'points': 44}, {'team_name': 'Stoke City', 'played': 38, 'won': 12, 'drawn': 7, 'lost': 19, 'goals_for': 50, 'goals_against': 56, 'goal_difference': -6, 'points': 43}, {'team_name': 'Charlton Athletic', 'played': 38, 'won': 11, 'drawn': 9, 'lost': 18, 'goals_for': 45, 'goals_against': 54, 'goal_difference': -9, 'points': 42}, {'team_name': 'Huddersfield Town', 'played': 38, 'won': 11, 'drawn': 9, 'lost': 18, 'goals_for': 45, 'goals_against': 60, 'goal_difference': -15, 'points': 42}, {'team_name': 'Middlesbrough', 'played': 38, 'won': 9, 'drawn': 14, 'lost': 15, 'goals_for': 37, 'goals_against': 50, 'goal_difference': -13, 'points': 41}, {'team_name': 'Hull City', 'played': 38, 'won': 11, 'drawn': 8, 'lost': 19, 'goals_for': 49, 'goals_against': 64, 'goal_difference': -15, 'points': 41}, {'team_name': 'Barnsley', 'played': 38, 'won': 9, 'drawn': 10, 'lost': 19, 'goals_for': 43, 'goals_against': 62, 'goal_difference': -19, 'points': 37}, {'team_name': 'Luton Town', 'played': 38, 'won': 10, 'drawn': 6, 'lost': 22, 'goals_for': 44, 'goals_against': 72, 'goal_difference': -28, 'points': 36}]

DERBY_RESET_FIXTURES = [{'round': 39, 'match_no': 1, 'home_team': 'Derby County', 'away_team': 'Reading'}, {'round': 39, 'match_no': 2, 'home_team': 'Birmingham City', 'away_team': 'Swansea City'}, {'round': 39, 'match_no': 3, 'home_team': 'Blackburn Rovers', 'away_team': 'Wigan Athletic'}, {'round': 39, 'match_no': 4, 'home_team': 'Brentford', 'away_team': 'Middlesbrough'}, {'round': 39, 'match_no': 5, 'home_team': 'Bristol City', 'away_team': 'Sheffield Wednesday'}, {'round': 39, 'match_no': 6, 'home_team': 'Huddersfield Town', 'away_team': 'Nottingham Forest'}, {'round': 39, 'match_no': 7, 'home_team': 'Hull City', 'away_team': 'Fulham'}, {'round': 39, 'match_no': 8, 'home_team': 'Leeds United', 'away_team': 'Barnsley'}, {'round': 39, 'match_no': 9, 'home_team': 'Luton Town', 'away_team': 'West Bromwich Albion'}, {'round': 39, 'match_no': 10, 'home_team': 'Preston North End', 'away_team': 'Charlton Athletic'}, {'round': 39, 'match_no': 11, 'home_team': 'QPR', 'away_team': 'Millwall'}, {'round': 39, 'match_no': 12, 'home_team': 'Stoke City', 'away_team': 'Cardiff City'}, {'round': 40, 'match_no': 1, 'home_team': 'Preston North End', 'away_team': 'Derby County'}, {'round': 40, 'match_no': 2, 'home_team': 'Birmingham City', 'away_team': 'Middlesbrough'}, {'round': 40, 'match_no': 3, 'home_team': 'Brentford', 'away_team': 'Blackburn Rovers'}, {'round': 40, 'match_no': 4, 'home_team': 'Cardiff City', 'away_team': 'Nottingham Forest'}, {'round': 40, 'match_no': 5, 'home_team': 'Huddersfield Town', 'away_team': 'Wigan Athletic'}, {'round': 40, 'match_no': 6, 'home_team': 'Hull City', 'away_team': 'Sheffield Wednesday'}, {'round': 40, 'match_no': 7, 'home_team': 'Leeds United', 'away_team': 'Bristol City'}, {'round': 40, 'match_no': 8, 'home_team': 'Luton Town', 'away_team': 'QPR'}, {'round': 40, 'match_no': 9, 'home_team': 'Millwall', 'away_team': 'West Bromwich Albion'}, {'round': 40, 'match_no': 10, 'home_team': 'Reading', 'away_team': 'Barnsley'}, {'round': 40, 'match_no': 11, 'home_team': 'Stoke City', 'away_team': 'Charlton Athletic'}, {'round': 40, 'match_no': 12, 'home_team': 'Swansea City', 'away_team': 'Fulham'}, {'round': 41, 'match_no': 1, 'home_team': 'Derby County', 'away_team': 'Nottingham Forest'}, {'round': 41, 'match_no': 2, 'home_team': 'Birmingham City', 'away_team': 'Blackburn Rovers'}, {'round': 41, 'match_no': 3, 'home_team': 'Brentford', 'away_team': 'Charlton Athletic'}, {'round': 41, 'match_no': 4, 'home_team': 'Bristol City', 'away_team': 'QPR'}, {'round': 41, 'match_no': 5, 'home_team': 'Cardiff City', 'away_team': 'Wigan Athletic'}, {'round': 41, 'match_no': 6, 'home_team': 'Huddersfield Town', 'away_team': 'Fulham'}, {'round': 41, 'match_no': 7, 'home_team': 'Hull City', 'away_team': 'West Bromwich Albion'}, {'round': 41, 'match_no': 8, 'home_team': 'Leeds United', 'away_team': 'Middlesbrough'}, {'round': 41, 'match_no': 9, 'home_team': 'Luton Town', 'away_team': 'Barnsley'}, {'round': 41, 'match_no': 10, 'home_team': 'Reading', 'away_team': 'Millwall'}, {'round': 41, 'match_no': 11, 'home_team': 'Stoke City', 'away_team': 'Preston North End'}, {'round': 41, 'match_no': 12, 'home_team': 'Swansea City', 'away_team': 'Sheffield Wednesday'}, {'round': 42, 'match_no': 1, 'home_team': 'West Bromwich Albion', 'away_team': 'Derby County'}, {'round': 42, 'match_no': 2, 'home_team': 'Birmingham City', 'away_team': 'Charlton Athletic'}, {'round': 42, 'match_no': 3, 'home_team': 'Cardiff City', 'away_team': 'Brentford'}, {'round': 42, 'match_no': 4, 'home_team': 'Fulham', 'away_team': 'Blackburn Rovers'}, {'round': 42, 'match_no': 5, 'home_team': 'Huddersfield Town', 'away_team': 'Sheffield Wednesday'}, {'round': 42, 'match_no': 6, 'home_team': 'Hull City', 'away_team': 'QPR'}, {'round': 42, 'match_no': 7, 'home_team': 'Luton Town', 'away_team': 'Bristol City'}, {'round': 42, 'match_no': 8, 'home_team': 'Millwall', 'away_team': 'Barnsley'}, {'round': 42, 'match_no': 9, 'home_team': 'Nottingham Forest', 'away_team': 'Preston North End'}, {'round': 42, 'match_no': 10, 'home_team': 'Reading', 'away_team': 'Middlesbrough'}, {'round': 42, 'match_no': 11, 'home_team': 'Stoke City', 'away_team': 'Wigan Athletic'}, {'round': 42, 'match_no': 12, 'home_team': 'Swansea City', 'away_team': 'Leeds United'}, {'round': 43, 'match_no': 1, 'home_team': 'Derby County', 'away_team': 'Brentford'}, {'round': 43, 'match_no': 2, 'home_team': 'Birmingham City', 'away_team': 'Preston North End'}, {'round': 43, 'match_no': 3, 'home_team': 'Cardiff City', 'away_team': 'Sheffield Wednesday'}, {'round': 43, 'match_no': 4, 'home_team': 'Huddersfield Town', 'away_team': 'West Bromwich Albion'}, {'round': 43, 'match_no': 5, 'home_team': 'Hull City', 'away_team': 'Barnsley'}, {'round': 43, 'match_no': 6, 'home_team': 'Leeds United', 'away_team': 'Charlton Athletic'}, {'round': 43, 'match_no': 7, 'home_team': 'Luton Town', 'away_team': 'Middlesbrough'}, {'round': 43, 'match_no': 8, 'home_team': 'Millwall', 'away_team': 'Bristol City'}, {'round': 43, 'match_no': 9, 'home_team': 'Nottingham Forest', 'away_team': 'Wigan Athletic'}, {'round': 43, 'match_no': 10, 'home_team': 'Reading', 'away_team': 'Blackburn Rovers'}, {'round': 43, 'match_no': 11, 'home_team': 'Stoke City', 'away_team': 'Fulham'}, {'round': 43, 'match_no': 12, 'home_team': 'Swansea City', 'away_team': 'QPR'}, {'round': 44, 'match_no': 1, 'home_team': 'Cardiff City', 'away_team': 'Derby County'}, {'round': 44, 'match_no': 2, 'home_team': 'Birmingham City', 'away_team': 'Wigan Athletic'}, {'round': 44, 'match_no': 3, 'home_team': 'Brentford', 'away_team': 'Fulham'}, {'round': 44, 'match_no': 4, 'home_team': 'Huddersfield Town', 'away_team': 'QPR'}, {'round': 44, 'match_no': 5, 'home_team': 'Hull City', 'away_team': 'Bristol City'}, {'round': 44, 'match_no': 6, 'home_team': 'Leeds United', 'away_team': 'Nottingham Forest'}, {'round': 44, 'match_no': 7, 'home_team': 'Luton Town', 'away_team': 'Blackburn Rovers'}, {'round': 44, 'match_no': 8, 'home_team': 'Millwall', 'away_team': 'Middlesbrough'}, {'round': 44, 'match_no': 9, 'home_team': 'Preston North End', 'away_team': 'West Bromwich Albion'}, {'round': 44, 'match_no': 10, 'home_team': 'Reading', 'away_team': 'Charlton Athletic'}, {'round': 44, 'match_no': 11, 'home_team': 'Stoke City', 'away_team': 'Sheffield Wednesday'}, {'round': 44, 'match_no': 12, 'home_team': 'Swansea City', 'away_team': 'Barnsley'}, {'round': 45, 'match_no': 1, 'home_team': 'Derby County', 'away_team': 'Leeds United'}, {'round': 45, 'match_no': 2, 'home_team': 'Birmingham City', 'away_team': 'Brentford'}, {'round': 45, 'match_no': 3, 'home_team': 'Cardiff City', 'away_team': 'QPR'}, {'round': 45, 'match_no': 4, 'home_team': 'Fulham', 'away_team': 'Wigan Athletic'}, {'round': 45, 'match_no': 5, 'home_team': 'Huddersfield Town', 'away_team': 'Barnsley'}, {'round': 45, 'match_no': 6, 'home_team': 'Hull City', 'away_team': 'Middlesbrough'}, {'round': 45, 'match_no': 7, 'home_team': 'Luton Town', 'away_team': 'Charlton Athletic'}, {'round': 45, 'match_no': 8, 'home_team': 'Millwall', 'away_team': 'Blackburn Rovers'}, {'round': 45, 'match_no': 9, 'home_team': 'Nottingham Forest', 'away_team': 'Sheffield Wednesday'}, {'round': 45, 'match_no': 10, 'home_team': 'Reading', 'away_team': 'Preston North End'}, {'round': 45, 'match_no': 11, 'home_team': 'Stoke City', 'away_team': 'West Bromwich Albion'}, {'round': 45, 'match_no': 12, 'home_team': 'Swansea City', 'away_team': 'Bristol City'}, {'round': 46, 'match_no': 1, 'home_team': 'Birmingham City', 'away_team': 'Derby County'}, {'round': 46, 'match_no': 2, 'home_team': 'Blackburn Rovers', 'away_team': 'Middlesbrough'}, {'round': 46, 'match_no': 3, 'home_team': 'Brentford', 'away_team': 'West Bromwich Albion'}, {'round': 46, 'match_no': 4, 'home_team': 'Bristol City', 'away_team': 'Charlton Athletic'}, {'round': 46, 'match_no': 5, 'home_team': 'Huddersfield Town', 'away_team': 'Swansea City'}, {'round': 46, 'match_no': 6, 'home_team': 'Hull City', 'away_team': 'Cardiff City'}, {'round': 46, 'match_no': 7, 'home_team': 'Leeds United', 'away_team': 'Fulham'}, {'round': 46, 'match_no': 8, 'home_team': 'Luton Town', 'away_team': 'Nottingham Forest'}, {'round': 46, 'match_no': 9, 'home_team': 'Preston North End', 'away_team': 'Barnsley'}, {'round': 46, 'match_no': 10, 'home_team': 'QPR', 'away_team': 'Wigan Athletic'}, {'round': 46, 'match_no': 11, 'home_team': 'Sheffield Wednesday', 'away_team': 'Reading'}, {'round': 46, 'match_no': 12, 'home_team': 'Stoke City', 'away_team': 'Millwall'}]

DERBY_RESET_JOB_OFFERS = [('CH001', 'Blackburn Rovers', 'EFL Championship', '8th', 'Reach the play-offs', 'Medium', 'Available'), ('CH001', 'Bristol City', 'EFL Championship', '10th', 'Reach the play-offs', 'Medium', 'Available'), ('CH001', 'Millwall', 'EFL Championship', '11th', 'Late charge for the play-offs', 'Hard', 'Available'), ('CH001', 'Middlesbrough', 'EFL Championship', '21st', 'Avoid relegation', 'Survival Battle', 'Available'), ('CH001', 'Barnsley', 'EFL Championship', '23rd', 'Avoid relegation', 'Survival Battle', 'Available'), ('CH001', 'Luton Town', 'EFL Championship', '24th', 'Avoid relegation', 'Survival Battle', 'Available')]



PESMASTER_TEAM_RATINGS_2020 = {'AFC Bournemouth': {'overall': 77, 'defence': 77, 'midfield': 78, 'attack': 78, 'speed': 78, 'strength': 73, 'rating_source': 'PESMaster PES 2020', 'source_url': 'https://www.pesmaster.com/bournemouth-rb/pes-2020/team/4071/', 'pes_name': 'Bournemouth Rb', 'notes': 'PESMaster PES 2020 team rating.'}, 'Derby County': {'overall': 71, 'defence': 70, 'midfield': 72, 'attack': 72, 'speed': 72, 'strength': 74, 'rating_source': 'PESMaster PES 2020', 'source_url': 'https://www.pesmaster.com/derby-wb/pes-2020/team/383/', 'pes_name': 'Derby Wb'}, 'Blackburn Rovers': {'overall': 71, 'defence': 70, 'midfield': 71, 'attack': 71, 'speed': 72, 'strength': 72, 'rating_source': 'PESMaster PES 2020', 'source_url': 'https://www.pesmaster.com/blackburn-bw/pes-2020/team/176/', 'pes_name': 'Blackburn Bw'}, 'Leeds United': {'overall': 73, 'defence': 73, 'midfield': 72, 'attack': 73, 'speed': 75, 'strength': 70, 'rating_source': 'PESMaster PES 2020', 'source_url': 'https://www.pesmaster.com/leeds-w/pes-2020/team/104/', 'pes_name': 'Leeds W'}, 'Middlesbrough': {'overall': 72, 'defence': 74, 'midfield': 72, 'attack': 71, 'speed': 72, 'strength': 75, 'rating_source': 'PESMaster PES 2020', 'source_url': 'https://www.pesmaster.com/middlesbrough-rw/pes-2020/team/205/', 'pes_name': 'Middlesbrough Rw'}, 'Stoke City': {'overall': 72, 'defence': 72, 'midfield': 72, 'attack': 72, 'speed': 70, 'strength': 75, 'rating_source': 'PESMaster PES 2020', 'source_url': 'https://www.pesmaster.com/stoke-rw/pes-2020/team/395/', 'pes_name': 'Stoke Rw'}, 'West Brom': {'overall': 74, 'defence': 73, 'midfield': 75, 'attack': 74, 'speed': 73, 'strength': 74, 'rating_source': 'PESMaster PES 2020', 'source_url': 'https://www.pesmaster.com/west-bromwich-wb/pes-2020/team/399/', 'pes_name': 'West Bromwich Wb'}, 'Preston': {'overall': 71, 'defence': 72, 'midfield': 72, 'attack': 69, 'speed': 73, 'strength': 74, 'rating_source': 'PESMaster PES 2020', 'source_url': 'https://www.pesmaster.com/preston-wb/pes-2020/team/4192/', 'pes_name': 'Preston Wb'}, 'Hull City': {'overall': 69, 'defence': 69, 'midfield': 70, 'attack': 68, 'speed': 72, 'strength': 73, 'rating_source': 'PESMaster PES 2020', 'source_url': 'https://www.pesmaster.com/hull-ob/pes-2020/team/1589/', 'pes_name': 'Hull Ob'}, 'Watford': {'overall': 78, 'defence': 76, 'midfield': 79, 'attack': 78, 'speed': 76, 'strength': 75, 'rating_source': 'PESMaster PES 2020', 'source_url': 'https://www.pesmaster.com/watford-by/pes-2020/team/398/', 'pes_name': 'Watford By'}, 'Burnley': {'overall': 77, 'defence': 76, 'midfield': 76, 'attack': 77, 'speed': 72, 'strength': 75, 'rating_source': 'PESMaster PES 2020', 'source_url': 'https://www.pesmaster.com/burnley-rb/pes-2020/team/378/', 'pes_name': 'Burnley Rb'}, 'Norwich City': {'overall': 74, 'defence': 74, 'midfield': 74, 'attack': 77, 'speed': 74, 'strength': 73, 'rating_source': 'PESMaster PES 2020', 'source_url': 'https://www.pesmaster.com/norwich-yg/pes-2020/team/388/', 'pes_name': 'Norwich Yg'}, 'Bristol City': {'overall': 72, 'defence': 72, 'midfield': 70, 'attack': 72, 'speed': 73, 'strength': 71, 'rating_source': 'PESMaster PES 2020', 'source_url': 'https://www.pesmaster.com/bristol-r/pes-2020/team/1760/', 'pes_name': 'Bristol R', 'notes': 'PESMaster mapped team; detailed split cached for app use.'}, 'Cardiff City': {'overall': 73, 'defence': 72, 'midfield': 72, 'attack': 71, 'speed': 74, 'strength': 74, 'rating_source': 'PESMaster PES 2020', 'source_url': 'https://www.pesmaster.com/cardiff-b/pes-2020/team/379/', 'pes_name': 'Cardiff B', 'notes': 'PESMaster mapped team; detailed split cached for app use.'}, 'Luton Town': {'overall': 68, 'defence': 68, 'midfield': 68, 'attack': 68, 'speed': 71, 'strength': 70, 'rating_source': 'PESMaster PES 2020 / league-page overall', 'source_url': 'https://www.pesmaster.com/english-2nd-division/pes-2020/league/66/', 'pes_name': 'Luton Wo', 'notes': 'Overall from PESMaster English 2nd Division list; balanced split used where page detail was not cached.'}, 'Millwall': {'overall': 70, 'defence': 70, 'midfield': 70, 'attack': 70, 'speed': 70, 'strength': 72, 'rating_source': 'PESMaster PES 2020 / league-page overall', 'source_url': 'https://www.pesmaster.com/english-2nd-division/pes-2020/league/66/', 'pes_name': 'Millwall Bw', 'notes': 'Overall from PESMaster English 2nd Division list; balanced split used where page detail was not cached.'}, 'QPR': {'overall': 69, 'defence': 68, 'midfield': 69, 'attack': 69, 'speed': 72, 'strength': 70, 'rating_source': 'PESMaster PES 2020 / league-page overall', 'source_url': 'https://www.pesmaster.com/english-2nd-division/pes-2020/league/66/', 'pes_name': 'Queens Park BW', 'notes': 'Overall from PESMaster English 2nd Division list; balanced split used where page detail was not cached.'}, 'Swansea City': {'overall': 71, 'defence': 71, 'midfield': 72, 'attack': 70, 'speed': 73, 'strength': 71, 'rating_source': 'PESMaster PES 2020 / league-page overall', 'source_url': 'https://www.pesmaster.com/english-2nd-division/pes-2020/league/66/', 'pes_name': 'Swansea W', 'notes': 'Overall from PESMaster English 2nd Division list; balanced split used where page detail was not cached.'}, 'Sheffield United': {'overall': 75, 'defence': 75, 'midfield': 75, 'attack': 75, 'speed': 74, 'strength': 75, 'rating_source': 'PESMaster PES 2020 / mapped team', 'source_url': 'https://www.pesmaster.com/sheffield-rb/pes-2020/team/4194/', 'pes_name': 'Sheffield Rb', 'notes': 'Mapped PES 2020 team; balanced split used where page detail was not cached.'}, 'Coventry City': {'overall': 76, 'defence': 76, 'midfield': 76, 'attack': 76, 'speed': 73, 'strength': 73, 'rating_source': 'Challenge fallback', 'source_url': '', 'pes_name': '', 'notes': 'Not in PES 2020 English 2nd Division. Kept calibrated challenge rating.'}, 'Sunderland': {'overall': 75, 'defence': 75, 'midfield': 75, 'attack': 75, 'speed': 73, 'strength': 73, 'rating_source': 'Challenge fallback', 'source_url': '', 'pes_name': '', 'notes': 'Not in PES 2020 English 2nd Division. Kept calibrated challenge rating.'}, 'Plymouth Argyle': {'overall': 64, 'defence': 64, 'midfield': 64, 'attack': 64, 'speed': 67, 'strength': 66, 'rating_source': 'Challenge fallback', 'source_url': '', 'pes_name': '', 'notes': 'Not in PES 2020 English 2nd Division. Kept calibrated challenge rating.'}, 'Oxford United': {'overall': 63, 'defence': 63, 'midfield': 63, 'attack': 63, 'speed': 67, 'strength': 66, 'rating_source': 'Challenge fallback', 'source_url': '', 'pes_name': '', 'notes': 'Not in PES 2020 English 2nd Division. Kept calibrated challenge rating.'}, 'Portsmouth': {'overall': 62, 'defence': 62, 'midfield': 62, 'attack': 62, 'speed': 67, 'strength': 66, 'rating_source': 'Challenge fallback', 'source_url': '', 'pes_name': '', 'notes': 'Not in PES 2020 English 2nd Division. Kept calibrated challenge rating.'}, 'Rotherham United': {'overall': 58, 'defence': 58, 'midfield': 58, 'attack': 58, 'speed': 64, 'strength': 64, 'rating_source': 'Challenge fallback', 'source_url': '', 'pes_name': '', 'notes': 'Not in PES 2020 English 2nd Division. Kept calibrated challenge rating.'}}


# PES 2020 verified Middlesbrough squad revision: all 24 active league teams.
# Overrides older PES 2021 entries and previously approximated stat splits.
PESMASTER_TEAM_RATINGS_2020.update({
    "AFC Bournemouth": {"overall": 77, "defence": 77, "midfield": 78, "attack": 78, "speed": 78, "strength": 73, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/bournemouth-rb/pes-2020/team/4071/", "pes_name": "AFC Bournemouth", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Barnsley": {"overall": 67, "defence": 66, "midfield": 68, "attack": 67, "speed": 73, "strength": 72, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/barnsley-r/pes-2020/team/1588/", "pes_name": "Barnsley", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Birmingham City": {"overall": 71, "defence": 71, "midfield": 72, "attack": 72, "speed": 74, "strength": 74, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/birmingham-b/pes-2020/team/201/", "pes_name": "Birmingham City", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Blackburn Rovers": {"overall": 71, "defence": 70, "midfield": 71, "attack": 71, "speed": 72, "strength": 72, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/blackburn-bw/pes-2020/team/176/", "pes_name": "Blackburn Rovers", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Bristol City": {"overall": 72, "defence": 73, "midfield": 71, "attack": 72, "speed": 76, "strength": 73, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/bristol-r/pes-2020/team/1760/", "pes_name": "Bristol City", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Cardiff City": {"overall": 73, "defence": 74, "midfield": 73, "attack": 71, "speed": 74, "strength": 76, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/cardiff-b/pes-2020/team/379/", "pes_name": "Cardiff City", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Charlton Athletic": {"overall": 68, "defence": 68, "midfield": 68, "attack": 69, "speed": 71, "strength": 73, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/charlton-rw/pes-2020/team/203/", "pes_name": "Charlton Athletic", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Derby County": {"overall": 71, "defence": 70, "midfield": 72, "attack": 72, "speed": 72, "strength": 74, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/derby-wb/pes-2020/team/383/", "pes_name": "Derby County", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Fulham": {"overall": 75, "defence": 75, "midfield": 75, "attack": 77, "speed": 75, "strength": 75, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/fulham-w/pes-2020/team/178/", "pes_name": "Fulham", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Huddersfield Town": {"overall": 72, "defence": 71, "midfield": 71, "attack": 73, "speed": 72, "strength": 73, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/huddersfield-bw/pes-2020/team/2610/", "pes_name": "Huddersfield Town", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Hull City": {"overall": 69, "defence": 69, "midfield": 70, "attack": 68, "speed": 72, "strength": 73, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/hull-ob/pes-2020/team/1589/", "pes_name": "Hull City", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Luton Town": {"overall": 68, "defence": 68, "midfield": 68, "attack": 70, "speed": 73, "strength": 72, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/luton-wo/pes-2020/team/4363/", "pes_name": "Luton Town", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Middlesbrough": {"overall": 72, "defence": 74, "midfield": 72, "attack": 71, "speed": 72, "strength": 75, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/middlesbrough-rw/pes-2020/team/205/", "pes_name": "Middlesbrough", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Millwall": {"overall": 70, "defence": 70, "midfield": 69, "attack": 69, "speed": 72, "strength": 74, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/millwall-bw/pes-2020/team/387/", "pes_name": "Millwall", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Nottingham Forest": {"overall": 73, "defence": 72, "midfield": 73, "attack": 74, "speed": 74, "strength": 74, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/nottingham-rw/pes-2020/team/389/", "pes_name": "Nottingham Forest", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Preston North End": {"overall": 71, "defence": 72, "midfield": 72, "attack": 69, "speed": 73, "strength": 74, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/preston-wb/pes-2020/team/4192/", "pes_name": "Preston North End", "notes": "Verified PESMaster PES 2020 team ratings."},
    "QPR": {"overall": 69, "defence": 69, "midfield": 68, "attack": 73, "speed": 73, "strength": 71, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/queens-park-bw/pes-2020/team/1327/", "pes_name": "QPR", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Reading": {"overall": 72, "defence": 71, "midfield": 72, "attack": 72, "speed": 77, "strength": 73, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/reading-bw/pes-2020/team/391/", "pes_name": "Reading", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Sheffield Wednesday": {"overall": 72, "defence": 72, "midfield": 73, "attack": 72, "speed": 75, "strength": 73, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/sheffield-bw/pes-2020/team/394/", "pes_name": "Sheffield Wednesday", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Stoke City": {"overall": 72, "defence": 72, "midfield": 72, "attack": 72, "speed": 70, "strength": 75, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/stoke-rw/pes-2020/team/395/", "pes_name": "Stoke City", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Swansea City": {"overall": 71, "defence": 71, "midfield": 71, "attack": 73, "speed": 74, "strength": 70, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/swansea-w/pes-2020/team/1909/", "pes_name": "Swansea City", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Watford": {"overall": 78, "defence": 76, "midfield": 79, "attack": 78, "speed": 76, "strength": 75, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/watford-by/pes-2020/team/398/", "pes_name": "Watford", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Wigan Athletic": {"overall": 70, "defence": 71, "midfield": 69, "attack": 70, "speed": 74, "strength": 73, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/wigan-bw/pes-2020/team/400/", "pes_name": "Wigan Athletic", "notes": "Verified PESMaster PES 2020 team ratings."},
    "Norwich City": {"overall": 74, "defence": 74, "midfield": 74, "attack": 77, "speed": 74, "strength": 73, "rating_source": "PESMaster PES 2020", "source_url": "https://www.pesmaster.com/norwich-yg/pes-2020/team/388/", "pes_name": "Norwich City", "notes": "Verified PESMaster PES 2020 team ratings."},
})


app = Flask(__name__)
from challenge_archive_admin import create_archive_blueprint
app.register_blueprint(create_archive_blueprint(DB_PATH))

# PES 2.0: isolated, read-only football world prototype.
from world_v2 import create_world_blueprint
app.register_blueprint(create_world_blueprint(DB_PATH))

from world_explorer import create_explorer_blueprint
app.register_blueprint(create_explorer_blueprint(DB_PATH))

from world_finance import create_finance_blueprint
app.register_blueprint(create_finance_blueprint(DB_PATH))

from world_market import create_market_blueprint
app.register_blueprint(create_market_blueprint(DB_PATH))

from world_careers_ui import create_careers_blueprint
app.register_blueprint(create_careers_blueprint(DB_PATH))

from world_career_play import create_play_blueprint
app.register_blueprint(create_play_blueprint(DB_PATH))

from world_reputation import create_reputation_blueprint
app.register_blueprint(create_reputation_blueprint(DB_PATH))

from world_reputation_v2_ui import create_pyramid_blueprint
app.register_blueprint(create_pyramid_blueprint(DB_PATH))

from world_reputation_progression_ui import create_progression_blueprint
app.register_blueprint(create_progression_blueprint(DB_PATH))

from world_prestige_calibration_ui import create_calibration_blueprint
app.register_blueprint(create_calibration_blueprint(DB_PATH))

from world_prestige_full_ui import create_full_prestige_blueprint
app.register_blueprint(create_full_prestige_blueprint(DB_PATH))

from world_player_decisions_ui import create_player_decisions_blueprint
app.register_blueprint(create_player_decisions_blueprint(DB_PATH))

from world_transfer_negotiations_ui import create_transfer_negotiations_blueprint
app.register_blueprint(create_transfer_negotiations_blueprint(DB_PATH))

# Transfer and career integration regressions run in
# .github/workflows/player-decisions.yml on every development main push.
# Do NOT rerun 195+ integration tests whenever a Render web worker boots:
# free-instance restarts made the live service repeatedly crash or time out.
# This change does not touch stored career data or the production app.


@app.after_request
def sync_sqlite_save_after_request(response):
    """Persist the SQLite save to Supabase after successful app requests."""
    if using_supabase_sync():
        path = request.path or ""
        should_skip = (
            path.startswith("/static/")
            or path.startswith("/favicon")
            or path.startswith("/admin/storage")
            or path.startswith("/admin/challenge-archive")
        )

        # Career-desk GET/HEAD/OPTIONS only display saved data. Do not
        # upload the entire SQLite file on each page view or redirect;
        # that can stall a free Render worker and make navigation appear
        # to loop. Genuine POST writes still sync, including new careers,
        # seller circumstances, offer decisions and player agreements.
        # The autonomous market may process a due AI event or reconcile the
        # hard deadline on a real page GET. Such requests are WRITE events,
        # explicitly marked by the career route; sync those to Supabase.
        # Ordinary page refreshes remain read-only and never upload a save.
        live_market_changed=bool(request.environ.get("career_live_market_dirty"))
        career_read_only = (
            path.startswith("/world/play") and
            request.method in ("GET","HEAD","OPTIONS") and
            not live_market_changed
        )
        if not should_skip and not career_read_only and response.status_code < 500:
            try:
                upload_sqlite_save_to_supabase("after-request")
            except Exception:
                traceback.print_exc()

    return response
app.secret_key = "change-this-secret-key"


def ensure_app_schema(conn):

    conn.execute("""
        CREATE TABLE IF NOT EXISTS playoff_matches (
            playoff_id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenge_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            leg INTEGER NOT NULL DEFAULT 1,
            match_no INTEGER NOT NULL DEFAULT 1,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            home_goals INTEGER,
            away_goals INTEGER,
            played INTEGER NOT NULL DEFAULT 0,
            neutral INTEGER NOT NULL DEFAULT 0,
            winner_team TEXT,
            source TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(player_match_events)").fetchall()}
    if "yellow_cards" not in cols:
        conn.execute("ALTER TABLE player_match_events ADD COLUMN yellow_cards INTEGER NOT NULL DEFAULT 0")
    if "red_cards" not in cols:
        conn.execute("ALTER TABLE player_match_events ADD COLUMN red_cards INTEGER NOT NULL DEFAULT 0")
    if "rating" not in cols:
        conn.execute("ALTER TABLE player_match_events ADD COLUMN rating REAL")
    seed_default_job_offers(conn)
    seed_extra_job_offers(conn)
    conn.commit()


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    ensure_app_schema(conn)

    # v18.70: repair any pre-existing Supabase/live CH002 that still has the
    # old 2020/21 club set. New deployments restore the live save from
    # Supabase before serving requests, so updating only the bundled DB is not
    # enough. This migration is deliberately limited to an unplayed CH002.
    repair = globals().get("repair_middlesbrough_career_season_2_if_needed")
    if repair is not None:
        repair(conn)

    # Refresh only rating data if a restored live save has old PES 2021 values.
    # This is safe after matches have been played: no fixtures or results change.
    if globals().get("apply_team_rating_sources") is not None:
        ensure_team_rating_sources_table(conn)
        ratings_outdated = any(
            (stored is None or stored["overall"] != entry["overall"]
             or stored["defence"] != entry["defence"]
             or stored["attack"] != entry["attack"]
             or stored["rating_source"] != "PESMaster PES 2020")
            for team, entry in PESMASTER_TEAM_RATINGS_2020.items()
            if team in {row[0] for row in MIDDLESBROUGH_2021_OPENING}
            for stored in [conn.execute(
                "SELECT overall, defence, attack, rating_source FROM team_rating_sources WHERE team_name=?",
                (team,),
            ).fetchone()]
        )
        if ratings_outdated:
            with conn:
                apply_team_rating_sources(conn)

    return conn


def slugify_team(team_name):
    return (
        team_name.lower()
        .replace("&", "and")
        .replace(".", "")
        .replace("'", "")
        .replace(" ", "-")
    )


def logo_for_team(team_name):
    slug = slugify_team(team_name)

    if team_name in PROBLEM_BADGE_REMOTE_PRIORITY and team_name in TEAM_LOGO_URLS:
        return TEAM_LOGO_URLS.get(team_name)

    for ext in ("png", "svg", "webp", "jpg", "jpeg"):
        local_path = APP_DIR / "static" / "logos" / f"{slug}.{ext}"
        if local_path.exists():
            return f"/static/logos/{slug}.{ext}"

    if team_name in TEAM_LOGO_URLS:
        return TEAM_LOGO_URLS.get(team_name)

    alias = TEAM_LOGO_ALIASES.get(team_name)
    if alias:
        return TEAM_LOGO_URLS.get(alias)

    return None


def result_logo_for_team(team_name):
    """Use the corrected problem-club logo mapping on Results/Around pages."""
    if team_name in {"Charlton Athletic", "Birmingham City", "Barnsley"}:
        return TEAM_LOGO_URLS.get(team_name) or logo_for_team(team_name)
    return logo_for_team(team_name)



def active_challenge(conn):
    return conn.execute("SELECT * FROM challenges WHERE status='Active' LIMIT 1").fetchone()


def validation(conn):
    rows = conn.execute("SELECT check_name, status, notes FROM validation_report").fetchall()
    status = "VALID" if rows and all(r["status"] == "PASS" for r in rows) else "INVALID"
    return status, rows


def league_table(conn, challenge_id):
    return conn.execute("""
        SELECT position, team_name, played, won, drawn, lost, goals_for, goals_against, goal_difference, points
        FROM league_table
        WHERE challenge_id=?
        ORDER BY position
    """, (challenge_id,)).fetchall()


def human_dashboard_totals(conn, challenge_id=None, club=None):
    """Aggregate human player stats for the Stats page and Career page.

    For a specific challenge + club, this deliberately includes:
    - normal managed fixtures from fixtures
    - managed play-off fixtures stored as synthetic negative fixture IDs

    Play-off player events are written with fixture_id = -playoff_id, so they need
    to be treated as part of the same challenge instead of being ignored as
    non-standard fixtures.
    """
    ensure_player_match_event_role_columns(conn)

    params = []
    event_filter = ""

    if challenge_id and club:
        event_filter = """
           AND (
                EXISTS (
                    SELECT 1
                    FROM fixtures f
                    WHERE f.challenge_id = pme.challenge_id
                      AND f.fixture_id = pme.fixture_id
                      AND (f.home_team = ? OR f.away_team = ?)
                )
                OR EXISTS (
                    SELECT 1
                    FROM playoff_matches pm
                    WHERE pm.challenge_id = pme.challenge_id
                      AND -pm.playoff_id = pme.fixture_id
                      AND (pm.home_team = ? OR pm.away_team = ?)
                )
           )
        """
        params.extend([challenge_id, club, club, club, club])
        challenge_filter = "AND pme.challenge_id = ?"
    elif challenge_id:
        challenge_filter = "AND pme.challenge_id = ?"
        params.append(challenge_id)
    else:
        challenge_filter = ""

    return conn.execute(f"""
        SELECT
            hp.player_name,
            COALESCE(SUM(pme.appearance), 0) AS appearances,
            COALESCE(SUM(pme.started), 0) AS starts,
            COALESCE(SUM(pme.substitute), 0) AS sub_apps,
            COALESCE(SUM(pme.goals), 0) AS goals,
            COALESCE(SUM(pme.assists), 0) AS assists,
            CASE
                WHEN COUNT(CASE WHEN pme.rating IS NOT NULL AND pme.rating > 0 THEN 1 END) = 0 THEN NULL
                ELSE ROUND(AVG(CASE WHEN pme.rating IS NOT NULL AND pme.rating > 0 THEN pme.rating END), 1)
            END AS average_rating,
            COALESCE(SUM(pme.yellow_cards), 0) AS yellow_cards,
            COALESCE(SUM(pme.red_cards), 0) AS red_cards
        FROM human_players hp
        LEFT JOIN player_match_events pme
            ON pme.player_name = hp.player_name
           {challenge_filter}
           {event_filter}
        GROUP BY hp.player_name
        ORDER BY goals DESC, assists DESC, appearances DESC, hp.player_name
    """, params).fetchall()


def stats_source_summary(conn, challenge):
    """Small Stats-page context summary showing regular/play-off coverage."""
    challenge_id = challenge["challenge_id"]
    club = challenge["club_or_nation"]

    regular_row = conn.execute("""
        SELECT COUNT(*) AS c
        FROM fixtures
        WHERE challenge_id=?
          AND played=1
          AND (home_team=? OR away_team=?)
    """, (challenge_id, club, club)).fetchone()

    playoff_row = conn.execute("""
        SELECT COUNT(*) AS c
        FROM playoff_matches
        WHERE challenge_id=?
          AND played=1
          AND (home_team=? OR away_team=?)
    """, (challenge_id, club, club)).fetchone()

    return {
        "regular_matches": regular_row["c"] if regular_row else 0,
        "playoff_matches": playoff_row["c"] if playoff_row else 0,
    }



def manager_record(conn, challenge_id):
    return conn.execute("""
        SELECT challenge_id, club_or_nation, matches, wins, draws, losses,
               CAST(ROUND(100.0 * wins / NULLIF(matches, 0), 0) AS INTEGER) AS win_percentage
        FROM manager_record
        WHERE challenge_id=?
    """, (challenge_id,)).fetchone()


def playoff_managed_record(conn, challenge_id, club):
    """Return W-D-L for managed play-off matches involving the club."""
    rows = conn.execute("""
        SELECT *
        FROM playoff_matches
        WHERE challenge_id=?
          AND played=1
          AND (home_team=? OR away_team=?)
        ORDER BY stage, match_no, leg, playoff_id
    """, (challenge_id, club, club)).fetchall()

    wins = draws = losses = 0

    for row in rows:
        home_goals = row["home_goals"] or 0
        away_goals = row["away_goals"] or 0
        winner = playoff_match_winner(row)

        if winner:
            if winner == club:
                wins += 1
            else:
                losses += 1
        elif home_goals == away_goals:
            draws += 1
        else:
            club_home = row["home_team"] == club
            club_goals = home_goals if club_home else away_goals
            opp_goals = away_goals if club_home else home_goals
            if club_goals > opp_goals:
                wins += 1
            else:
                losses += 1

    matches = wins + draws + losses
    win_percentage = int(round(100.0 * wins / matches)) if matches else 0

    return {
        "matches": matches,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "win_percentage": win_percentage,
    }


def combined_manager_record(conn, challenge):
    """Regular run-in record plus managed play-off record."""
    regular = manager_record(conn, challenge["challenge_id"])
    playoff = playoff_managed_record(conn, challenge["challenge_id"], challenge["club_or_nation"])

    regular_matches = regular["matches"] or 0 if regular else 0
    regular_wins = regular["wins"] or 0 if regular else 0
    regular_draws = regular["draws"] or 0 if regular else 0
    regular_losses = regular["losses"] or 0 if regular else 0

    wins = regular_wins + playoff["wins"]
    draws = regular_draws + playoff["draws"]
    losses = regular_losses + playoff["losses"]
    matches = regular_matches + playoff["matches"]
    win_percentage = int(round(100.0 * wins / matches)) if matches else 0

    return {
        "challenge_id": challenge["challenge_id"],
        "club_or_nation": challenge["club_or_nation"],
        "matches": matches,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "win_percentage": win_percentage,
        "regular_matches": regular_matches,
        "playoff_matches": playoff["matches"],
    }



def latest_board(conn, challenge_id, fallback):
    row = conn.execute("""
        SELECT board_confidence, assessment
        FROM board_log
        WHERE challenge_id=?
        ORDER BY round DESC, log_id DESC
        LIMIT 1
    """, (challenge_id,)).fetchone()
    if row:
        return row["board_confidence"], row["assessment"]
    return fallback, "Starting board confidence."


def next_fixture(conn, challenge_id, club):
    return conn.execute("""
        SELECT *
        FROM fixtures
        WHERE challenge_id=?
          AND played=0
          AND (home_team=? OR away_team=?)
        ORDER BY round, match_no
        LIMIT 1
    """, (challenge_id, club, club)).fetchone()


def round_fixtures(conn, challenge_id, round_no):
    return conn.execute("""
        SELECT *
        FROM fixtures
        WHERE challenge_id=? AND round=?
        ORDER BY match_no
    """, (challenge_id, round_no)).fetchall()


def latest_round_summary(conn, challenge_id):
    latest = conn.execute("""
        SELECT MAX(round) AS latest_round
        FROM fixtures
        WHERE challenge_id=? AND played=1
    """, (challenge_id,)).fetchone()["latest_round"]

    if latest is None:
        return None, []

    rows = conn.execute("""
        SELECT match_no, home_team, away_team, home_goals, away_goals, source, notes
        FROM fixtures
        WHERE challenge_id=? AND round=?
        ORDER BY match_no
    """, (challenge_id, latest)).fetchall()

    return latest, rows


def clamp(value, low, high):
    return max(low, min(high, value))


def poisson_goal_sample(expected_goals):
    """Small local Poisson sampler so the app does not need numpy."""
    expected_goals = clamp(expected_goals, 0.05, 4.5)
    limit = math.exp(-expected_goals)
    k = 0
    product = 1.0

    while product > limit:
        k += 1
        product *= random.random()

    return k - 1


def team_strength_profile(conn, team_name):
    row = conn.execute("""
        SELECT team_name, hidden_strength, attack, defence, home_advantage
        FROM teams
        WHERE team_name=?
    """, (team_name,)).fetchone()

    if row:
        hidden = row["hidden_strength"] or 70
        return {
            "team_name": row["team_name"],
            "hidden_strength": hidden,
            "attack": row["attack"] or hidden,
            "defence": row["defence"] or hidden,
            "home_advantage": row["home_advantage"] if row["home_advantage"] is not None else 3,
        }

    return {
        "team_name": team_name,
        "hidden_strength": 70,
        "attack": 70,
        "defence": 70,
        "home_advantage": 3,
    }


def current_team_table_context(conn, challenge_id, team_name):
    table = league_table(conn, challenge_id)
    for row in table:
        if row["team_name"] == team_name:
            return {
                "position": row["position"],
                "points": row["points"],
                "goal_difference": row["goal_difference"],
            }

    return {"position": 12, "points": 50, "goal_difference": 0}



def team_rating(conn, team_name):
    try:
        row = conn.execute("""
            SELECT overall
            FROM team_rating_sources
            WHERE team_name=?
            LIMIT 1
        """, (team_name,)).fetchone()
        if row and row["overall"] is not None:
            return int(row["overall"])
    except sqlite3.Error:
        pass
    return None


def expected_goals_for_team(attacking_profile, defending_profile, attacking_context, defending_context, is_home):
    attack = attacking_profile["attack"]
    opponent_defence = defending_profile["defence"]

    # Championship-style base scoring rate.
    xg = 1.18 if is_home else 1.03

    # Attack v defence matchup.
    xg += (attack - opponent_defence) * 0.018

    # Overall quality still matters slightly.
    xg += (attacking_profile["hidden_strength"] - defending_profile["hidden_strength"]) * 0.008

    # Home advantage from team profile.
    if is_home:
        xg += attacking_profile["home_advantage"] * 0.035

    # Live table context.
    attacking_position = attacking_context["position"] or 12
    defending_position = defending_context["position"] or 12

    xg += (13 - attacking_position) * 0.012
    xg -= (13 - defending_position) * 0.006

    # Goal difference acts as a season-strength proxy.
    xg += clamp(attacking_context["goal_difference"], -30, 30) * 0.006
    xg -= clamp(defending_context["goal_difference"], -30, 30) * 0.003

    return clamp(xg, 0.25, 2.75)


def simulate_scoreline(conn, challenge_id, home_team, away_team):
    home_profile = team_strength_profile(conn, home_team)
    away_profile = team_strength_profile(conn, away_team)
    home_context = current_team_table_context(conn, challenge_id, home_team)
    away_context = current_team_table_context(conn, challenge_id, away_team)

    home_xg = expected_goals_for_team(home_profile, away_profile, home_context, away_context, True)
    away_xg = expected_goals_for_team(away_profile, home_profile, away_context, home_context, False)

    home_goals = poisson_goal_sample(home_xg)
    away_goals = poisson_goal_sample(away_xg)

    # Keep the game believable. Freak results can still happen, but less often.
    if home_goals + away_goals >= 7 and random.random() < 0.70:
        if home_goals > away_goals:
            home_goals -= 1
        elif away_goals > home_goals:
            away_goals -= 1
        else:
            home_goals -= 1

    return max(0, min(home_goals, 5)), max(0, min(away_goals, 5))


def default_sim_scores(conn, fixtures, managed_match_no, managed_hg, managed_ag):
    """Generate the full round's scoreline.

    The managed PES result is kept exactly as entered.
    All other fixtures use the v16.7 simulation engine.
    """
    out = {}

    challenge_id = fixtures[0]["challenge_id"] if fixtures else None

    for f in fixtures:
        match_no = int(f["match_no"])

        if match_no == managed_match_no:
            out[match_no] = (managed_hg, managed_ag)
            continue

        out[match_no] = simulate_scoreline(
            conn,
            challenge_id,
            f["home_team"],
            f["away_team"],
        )

    return out





def calibrated_board_confidence(board_conf, current_position=None, target_position=None, games_remaining=0, playoff_info=None):
    """Final display calibration for board confidence.

    - Inside play-off places before the season ends: max 80%.
    - Inside automatic promotion places before the season ends: max 90%.
    - Play-offs reached / campaign underway: 85%.
    - Promotion achieved: 100%.
    """
    board_conf = int(board_conf or 0)

    if playoff_info:
        if playoff_info.get("promoted"):
            return 100
        if playoff_info.get("qualified") and not playoff_info.get("finished"):
            return 85
        if playoff_info.get("qualified") and playoff_info.get("finished") and not playoff_info.get("promoted"):
            return min(board_conf, 85)

    return board_confidence_display_value(
        board_conf,
        current_position,
        target_position,
        games_remaining,
    )


def board_confidence_display_value(board_conf, current_position=None, target_position=None, games_remaining=0):
    """Display confidence without claiming 100% before the objective is secured.

    Promotion/play-off final victory can legitimately show 100%.
    """
    board_conf = int(board_conf or 0)
    games_remaining = int(games_remaining or 0)

    if games_remaining > 0 and target_position is not None and current_position is not None:
        current_position = int(current_position)
        target_position = int(target_position)

        if current_position <= 2:
            return min(board_conf, 90)

        if current_position <= target_position:
            return min(board_conf, 80)

    return max(0, min(100, board_conf))


def board_after_result(previous, result, position, target_position, gap_to_target=0, games_remaining=0):
    delta = 8 if result == "W" else 1 if result == "D" else -8

    if position <= target_position:
        delta += 4
    elif position <= target_position + 2:
        delta += 1
    else:
        delta -= 2

    confidence = max(0, min(100, previous + delta))

    gap_to_target = int(gap_to_target or 0)
    games_remaining = int(games_remaining or 0)
    max_points_available = games_remaining * 3

    if games_remaining == 0:
        if position <= 2:
            assessment = "Objective exceeded — automatic promotion secured."
            confidence = 100
        elif position <= target_position:
            assessment = "Objective achieved — play-offs secured. The board are pleased, but promotion is still there to be won."
            confidence = 85
        else:
            assessment = "Objective missed — the final target was not reached."
            confidence = min(confidence, 50)
        return confidence, assessment

    if position <= target_position:
        # Inside the target places is strong, but not finished until the regular season is complete.
        if position <= 2:
            confidence = min(confidence, 90)
            if games_remaining == 1:
                assessment = "Outstanding — inside the automatic promotion places with one game to go, but the job is not done yet."
            else:
                assessment = "Outstanding — currently inside the automatic promotion places, but promotion still needs securing."
        else:
            confidence = min(confidence, 80)
            if games_remaining == 1:
                assessment = "Very positive — inside the play-off places with one game to go, but the job is not done yet."
            else:
                assessment = "Very positive — currently inside the play-off places, but the objective still needs securing."
        return confidence, assessment

    if gap_to_target > max_points_available:
        confidence = min(confidence, 45)
        assessment = (
            f"Critical — objective is now mathematically impossible. "
            f"The team are {gap_to_target} points off the target with {games_remaining} game(s) left "
            f"and only {max_points_available} point(s) still available."
        )
        return confidence, assessment

    if gap_to_target == max_points_available:
        confidence = min(confidence, 58)
        assessment = (
            f"High pressure — objective is only just mathematically alive. "
            f"The team need a perfect finish and help elsewhere."
        )
        return confidence, assessment

    if gap_to_target > 0 and games_remaining <= 2:
        confidence = min(confidence, 65)
        assessment = (
            f"Concerned — objective is still possible, but the margin for error is almost gone. "
            f"Gap to target: {gap_to_target} point(s), games left: {games_remaining}."
        )
        return confidence, assessment

    if confidence >= 85:
        assessment = "Excellent — board fully behind the run."
    elif confidence >= 70:
        assessment = "Positive — objective remains alive, but the table still needs movement."
    elif confidence >= 55:
        assessment = "Mixed — pressure building but challenge still alive."
    elif confidence >= 40:
        assessment = "Concerned — results need to improve quickly."
    else:
        assessment = "Critical — objective at serious risk."

    return confidence, assessment


def progress_board_context(conn, challenge, current_position, current_points, record, games_remaining, gap_to_target=0):
    """Context-aware live board view used before the final verdict.

    It reuses the same ingredients as the final verdict: manager output,
    movement from the starting point, target gap, remaining games and relative
    squad strength. This keeps the live verdict aligned with the final screen.
    """
    ctx = final_performance_context(conn, challenge, current_position, current_points, record)
    target = int(challenge["target_position"] or 6)
    games_remaining = int(games_remaining or 0)
    gap_to_target = int(gap_to_target or 0)
    max_points_available = games_remaining * 3

    objective_alive = True
    if gap_to_target > max_points_available:
        objective_alive = False

    in_target = current_position is not None and int(current_position) <= target

    if ctx["played"] == 0:
        status = "No matches posted"
        message = (
            f"The {challenge['club_or_nation']} challenge has not started on the pitch yet. "
            f"We will judge the run-in against the objective, the squad baseline and the table context once results are posted."
        )
    elif in_target:
        if current_position is not None and int(current_position) <= 2 and ("play" in (challenge["objective"] or "").lower() or target == 6):
            status = "Ahead of brief"
            message = (
                f"Excellent — {challenge['club_or_nation']} are currently inside the automatic-promotion places. "
                f"The record is {ctx['wins']}W {ctx['draws']}D {ctx['losses']}L at {ctx['ppg']} points per game. "
                "The job is not finished yet, but the manager has put the club ahead of the original brief."
            )
        else:
            status = "In target places"
            message = (
                f"Very positive — {challenge['club_or_nation']} are currently inside the target places. "
                f"The record is {ctx['wins']}W {ctx['draws']}D {ctx['losses']}L at {ctx['ppg']} points per game. "
                "The objective still needs securing, but the controllables are being handled well."
            )
    elif not objective_alive:
        if ctx["ppg"] >= 2.0 and ctx["rating_rank"] is not None and ctx["rating_rank"] > target:
            status = "Strong effort, table escaped"
            message = (
                f"The objective is now mathematically out of reach, but the assessment is not simply poor performance. "
                f"The record is {ctx['wins']}W {ctx['draws']}D {ctx['losses']}L at {ctx['ppg']} points per game, "
                f"from a squad ranked around {ordinal_position(ctx['rating_rank'])} for strength. "
                "The manager delivered a strong chase; the field above did not open the door."
            )
        elif ctx["ppg"] >= 1.75:
            status = "Objective slipped away"
            message = (
                f"The objective is mathematically out of reach. The run-in has still been competitive "
                f"({ctx['wins']}W {ctx['draws']}D {ctx['losses']}L, {ctx['ppg']} PPG), "
                "but not enough to overturn the table."
            )
        else:
            status = "Objective impossible"
            message = (
                f"Critical — the objective is mathematically impossible. "
                f"The team are {gap_to_target} point(s) off the target with {games_remaining} game(s) left."
            )
    elif gap_to_target == max_points_available and gap_to_target > 0:
        status = "No margin for error"
        message = (
            f"High pressure — the objective is only just mathematically alive. "
            f"A perfect finish is needed, plus help elsewhere. Current record: "
            f"{ctx['wins']}W {ctx['draws']}D {ctx['losses']}L at {ctx['ppg']} PPG."
        )
    elif gap_to_target > 0 and games_remaining <= 2:
        if ctx["ppg"] >= 2.0:
            status = "Strong chase"
            message = (
                f"Positive performance, but the table still needs movement. "
                f"The record is {ctx['wins']}W {ctx['draws']}D {ctx['losses']}L at {ctx['ppg']} PPG, "
                f"yet the club remain {gap_to_target} point(s) off the target with {games_remaining} game(s) left. "
                "This is a strong showing, but other results now matter."
            )
        else:
            status = "Pressure building"
            message = (
                f"Concerned — the objective is still possible, but the margin for error is almost gone. "
                f"Gap to target: {gap_to_target} point(s), games left: {games_remaining}. "
                f"Current record: {ctx['wins']}W {ctx['draws']}D {ctx['losses']}L."
            )
    elif gap_to_target > 0:
        if ctx["ppg"] >= 2.25:
            status = "Strong run-in"
            message = (
                f"Positive — the objective remains alive and the performance level is strong. "
                f"The record is {ctx['wins']}W {ctx['draws']}D {ctx['losses']}L at {ctx['ppg']} PPG. "
                f"The club are {gap_to_target} point(s) off the target, so the table still needs movement, "
                "but the manager is doing enough to keep pressure on the teams above."
            )
        elif ctx["ppg"] >= 1.75:
            status = "Competitive chase"
            message = (
                f"Mixed but competitive — the objective remains alive. "
                f"The record is {ctx['wins']}W {ctx['draws']}D {ctx['losses']}L at {ctx['ppg']} PPG, "
                f"with a {gap_to_target}-point gap still to close."
            )
        else:
            status = "Needs improvement"
            message = (
                f"Concerned — the objective remains alive, but the run-in needs to improve. "
                f"The current record is {ctx['wins']}W {ctx['draws']}D {ctx['losses']}L."
            )
    else:
        status = "In progress"
        message = (
            f"Challenge in progress. Current record: {ctx['wins']}W {ctx['draws']}D {ctx['losses']}L "
            f"at {ctx['ppg']} PPG."
        )

    return {
        "context": ctx,
        "status": status,
        "message": message,
        "objective_alive": objective_alive,
        "in_target": in_target,
        "gap_to_target": gap_to_target,
        "max_points_available": max_points_available,
    }


def contextual_progress_board_confidence(conn, challenge, current_position, current_points, record, base_confidence, gap_to_target=0, games_remaining=0):
    """Live board percentage using context, not just raw target status."""
    base_confidence = int(base_confidence or 0)
    target = int(challenge["target_position"] or 6)
    games_remaining = int(games_remaining or 0)
    gap_to_target = int(gap_to_target or 0)
    max_points_available = games_remaining * 3

    status = playoff_status(conn, challenge)
    if status.get("promoted"):
        return 100
    if status.get("qualified") and not status.get("finished"):
        return 85

    ctx = final_performance_context(conn, challenge, current_position, current_points, record)

    # A brand-new challenge should begin from a genuinely neutral board position.
    # Do not punish or reward the manager for the inherited table before a ball is kicked.
    if ctx["played"] == 0:
        return 50

    if current_position is None:
        return max(0, min(100, base_confidence))

    current_position = int(current_position)

    if games_remaining == 0:
        return final_board_confidence(conn, challenge, current_position, current_points, record, base_confidence)

    if current_position <= 2 and ("play" in (challenge["objective"] or "").lower() or target == 6):
        score = 78
    elif current_position <= target:
        score = 70
    else:
        score = 48

    if ctx["ppg"] >= 2.4:
        score += 16
    elif ctx["ppg"] >= 2.25:
        score += 14
    elif ctx["ppg"] >= 2.0:
        score += 10
    elif ctx["ppg"] >= 1.75:
        score += 6
    elif ctx["ppg"] >= 1.5:
        score += 2
    elif ctx["ppg"] < 1.0 and ctx["played"]:
        score -= 10

    if ctx["win_rate"] >= 75:
        score += 5
    elif ctx["win_rate"] >= 60:
        score += 3

    if ctx["movement"] is not None and ctx["movement"] > 0:
        score += min(8, ctx["movement"] * 2)
    elif ctx["movement"] is not None and ctx["movement"] < 0:
        score -= min(8, abs(ctx["movement"]) * 2)

    if current_position > target:
        if gap_to_target > max_points_available:
            score = min(score, 54 if ctx["ppg"] >= 2.0 else 42)
        elif gap_to_target == max_points_available and gap_to_target > 0:
            score = min(score, 60)
        elif games_remaining <= 2:
            score = min(score, 70 if ctx["ppg"] >= 2.0 else 62)
        elif gap_to_target <= 3 and ctx["ppg"] >= 2.0:
            score = max(score, 66)

    rating_rank = ctx["rating_rank"]
    if rating_rank is not None:
        if rating_rank <= max(2, target - 3) and current_position > target:
            score -= 10
        elif rating_rank <= target and current_position > target:
            score -= 4
        elif rating_rank > target:
            score += min(8, (rating_rank - target) * 2)

    if current_position <= 2:
        score = min(score, 90)
    elif current_position <= target:
        score = min(score, 80)
    else:
        score = min(score, 74)

    return max(0, min(100, int(round(score))))


def contextual_progress_board_update(conn, challenge, current_position, current_points, record, base_confidence, base_assessment, gap_to_target=0, games_remaining=0):
    progress = progress_board_context(
        conn,
        challenge,
        current_position,
        current_points,
        record,
        games_remaining,
        gap_to_target,
    )
    confidence = contextual_progress_board_confidence(
        conn,
        challenge,
        current_position,
        current_points,
        record,
        base_confidence,
        gap_to_target,
        games_remaining,
    )
    return confidence, progress["message"], progress


def contextual_board_after_result(conn, challenge, previous, result, position, current_points, gap_to_target=0, games_remaining=0):
    """Board log after each result, with the same contextual logic used on dashboards."""
    basic_confidence, basic_assessment = board_after_result(
        previous,
        result,
        position,
        challenge["target_position"],
        gap_to_target,
        games_remaining,
    )

    record = combined_manager_record(conn, challenge)
    confidence, assessment, _ = contextual_progress_board_update(
        conn,
        challenge,
        position,
        current_points,
        record,
        basic_confidence,
        basic_assessment,
        gap_to_target,
        games_remaining,
    )

    return confidence, assessment


def challenge_title(challenge):
    club = challenge["club_or_nation"]
    objective = challenge["objective"]

    if "play" in (objective or "").lower():
        return f"Can Jake Brown guide {club} to the play-offs?"

    return f"Can Jake Brown guide {club} to {objective.lower()}?"


def team_initials(team_name):
    stop_words = {"fc", "afc", "the", "united", "city", "county", "rovers", "town"}
    words = [w for w in team_name.replace("-", " ").split() if w.lower() not in stop_words]
    if not words:
        words = team_name.split()
    initials = "".join(w[0].upper() for w in words[:3])
    return initials[:3]


def derby_context(table, challenge):
    club = challenge["club_or_nation"]
    target_position = int(challenge["target_position"])

    club_row = next((r for r in table if r["team_name"] == club), None)
    target_row = next((r for r in table if int(r["position"]) == target_position), None)

    current_position = club_row["position"] if club_row else None
    points = club_row["points"] if club_row else None

    if club_row and target_row and int(club_row["position"]) > target_position:
        gap = max(0, int(target_row["points"]) - int(club_row["points"]))
    else:
        gap = 0

    return current_position, points, gap


def games_remaining(conn, challenge_id, club):
    return conn.execute("""
        SELECT COUNT(*) AS remaining
        FROM fixtures
        WHERE challenge_id=?
          AND played=0
          AND (home_team=? OR away_team=?)
    """, (challenge_id, club, club)).fetchone()["remaining"]





def ensure_default_human_players(conn):
    """Ensure current human player roster exists."""
    try:
        conn.execute("""
            INSERT OR IGNORE INTO human_players(player_name)
            VALUES ('Tim Rees')
        """)
    except sqlite3.Error:
        pass



def ensure_team_rating_sources_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_rating_sources (
            team_name TEXT PRIMARY KEY,
            rating_source TEXT,
            source_url TEXT,
            pes_name TEXT,
            overall INTEGER,
            defence INTEGER,
            midfield INTEGER,
            attack INTEGER,
            speed INTEGER,
            strength INTEGER,
            notes TEXT
        )
    """)


def apply_team_rating_sources(conn):
    """Apply cached PESMaster/challenge ratings to the simulation teams table."""
    ensure_team_rating_sources_table(conn)

    for team_name, rating in PESMASTER_TEAM_RATINGS_2020.items():
        conn.execute("""
            INSERT OR IGNORE INTO teams(team_name, hidden_strength, attack, defence, home_advantage)
            VALUES (?, ?, ?, ?, 3)
        """, (
            team_name,
            rating["overall"],
            rating["attack"],
            rating["defence"],
        ))

        conn.execute("""
            UPDATE teams
            SET hidden_strength=?, attack=?, defence=?
            WHERE team_name=?
        """, (
            rating["overall"],
            rating["attack"],
            rating["defence"],
            team_name,
        ))

        conn.execute("""
            INSERT INTO team_rating_sources(
                team_name, rating_source, source_url, pes_name, overall, defence,
                midfield, attack, speed, strength, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(team_name) DO UPDATE SET
                rating_source=excluded.rating_source,
                source_url=excluded.source_url,
                pes_name=excluded.pes_name,
                overall=excluded.overall,
                defence=excluded.defence,
                midfield=excluded.midfield,
                attack=excluded.attack,
                speed=excluded.speed,
                strength=excluded.strength,
                notes=excluded.notes
        """, (
            team_name,
            rating.get("rating_source", ""),
            rating.get("source_url", ""),
            rating.get("pes_name", ""),
            rating["overall"],
            rating["defence"],
            rating["midfield"],
            rating["attack"],
            rating["speed"],
            rating["strength"],
            rating.get("notes", ""),
        ))




def ensure_player_match_event_role_columns(conn):
    """Ensure player_match_events can distinguish starts from substitute appearances."""
    try:
        cols = [row["name"] for row in conn.execute("PRAGMA table_info(player_match_events)").fetchall()]
        if "started" not in cols:
            conn.execute("ALTER TABLE player_match_events ADD COLUMN started INTEGER DEFAULT 0")
        if "substitute" not in cols:
            conn.execute("ALTER TABLE player_match_events ADD COLUMN substitute INTEGER DEFAULT 0")
        conn.execute("""
            UPDATE player_match_events
            SET started=CASE
                    WHEN COALESCE(appearance,0)=1 AND COALESCE(started,0)=0 AND COALESCE(substitute,0)=0 THEN 1
                    ELSE COALESCE(started,0)
                END,
                substitute=COALESCE(substitute,0)
        """)
    except sqlite3.Error:
        pass


def ensure_player_roster_schema(conn):
    """Keep historical player records while allowing admins to deactivate players."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(human_players)").fetchall()}
    if "active" not in columns:
        conn.execute("ALTER TABLE human_players ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
    for name in CURRENT_HUMAN_PLAYERS:
        conn.execute("INSERT OR IGNORE INTO human_players(player_name) VALUES (?)", (name,))
    conn.commit()


def active_human_players(conn):
    ensure_player_roster_schema(conn)
    rows = conn.execute(
        "SELECT player_name FROM human_players WHERE active = 1 ORDER BY rowid"
    ).fetchall()
    return [row["player_name"] for row in rows]


@app.route("/admin/human-players", methods=["GET", "POST"])
def admin_human_players():
    conn = connect()
    ensure_player_roster_schema(conn)
    if request.method == "POST":
        operation = request.form.get("operation", "")
        name = " ".join(request.form.get("player_name", "").split()).strip()
        if operation == "add":
            if not name or len(name) > 100:
                flash("Enter a valid player name (up to 100 characters).")
            elif any(c in name for c in "<>"):
                flash("Player names cannot contain angle brackets.")
            else:
                existing = conn.execute(
                    "SELECT player_name FROM human_players WHERE lower(player_name) = lower(?)",
                    (name,),
                ).fetchone()
                if existing:
                    conn.execute("UPDATE human_players SET active = 1 WHERE player_name = ?", (existing["player_name"],))
                    conn.commit()
                    flash(f"{existing['player_name']} is active again.")
                else:
                    conn.execute("INSERT INTO human_players(player_name, active) VALUES (?, 1)", (name,))
                    conn.commit()
                    flash(f"{name} added to the active roster.")
        elif operation in ("activate", "deactivate"):
            existing = conn.execute("SELECT player_name FROM human_players WHERE player_name = ?", (name,)).fetchone()
            if existing:
                if operation == "deactivate" and len(active_human_players(conn)) <= 1:
                    flash("At least one player must remain active.")
                else:
                    conn.execute("UPDATE human_players SET active = ? WHERE player_name = ?",
                                 (1 if operation == "activate" else 0, name))
                    conn.commit()
                    flash(f"{name} {'activated' if operation == 'activate' else 'deactivated'}. Previous stats are preserved.")
        conn.close()
        return redirect(url_for("admin_human_players"))
    players = conn.execute(
        "SELECT player_name, active FROM human_players ORDER BY active DESC, player_name COLLATE NOCASE"
    ).fetchall()
    conn.close()
    return render_template("admin_human_players.html", players=players)


def ensure_current_human_players(conn):
    ensure_player_roster_schema(conn)



CURRENT_HUMAN_PLAYERS = ['Matt Kerry', 'James Pegg', 'Stupid Mole', 'Jake Brown', 'Jack Carnell', 'Tim Rees', 'Josh Stephenson']






# v18.70 Middlesbrough Career Season 2 — live CH002 table repair + PES 2020 ratings
MIDDLESBROUGH_2021_OPENING = [('Norwich City', 38, 25, 8, 5, 56, 27, 29, 83), ('Watford', 38, 22, 9, 7, 55, 26, 29, 75), ('Swansea City', 38, 21, 9, 8, 47, 29, 18, 72), ('Fulham', 38, 20, 11, 7, 66, 39, 27, 71), ('Barnsley', 38, 19, 7, 12, 49, 42, 7, 64), ('AFC Bournemouth', 38, 17, 11, 10, 57, 38, 19, 62), ('Reading', 38, 18, 8, 12, 52, 41, 11, 62), ('Cardiff City', 38, 16, 10, 12, 55, 37, 18, 58), ('Middlesbrough', 38, 16, 8, 14, 46, 39, 7, 56), ('Millwall', 38, 12, 16, 10, 38, 36, 2, 52), ('Stoke City', 38, 13, 13, 12, 42, 42, 0, 52), ('Luton Town', 38, 14, 9, 15, 31, 41, -10, 51), ('QPR', 38, 13, 11, 14, 40, 46, -6, 50), ('Bristol City', 38, 15, 4, 19, 39, 50, -11, 49), ('Blackburn Rovers', 38, 12, 10, 16, 50, 42, 8, 46), ('Preston North End', 38, 13, 5, 20, 39, 49, -10, 44), ('Nottingham Forest', 38, 10, 12, 16, 30, 38, -8, 42), ('Huddersfield Town', 38, 11, 9, 18, 42, 54, -12, 42), ('Charlton Athletic', 38, 10, 12, 16, 33, 48, -15, 42), ('Derby County', 38, 10, 10, 18, 27, 42, -15, 40), ('Wigan Athletic', 38, 11, 6, 21, 41, 50, -9, 39), ('Birmingham City', 38, 9, 11, 18, 28, 50, -22, 38), ('Sheffield Wednesday', 38, 10, 8, 20, 28, 49, -21, 32), ('Hull City', 38, 6, 9, 23, 25, 61, -36, 27)]

MIDDLESBROUGH_2021_FIXTURES = [(39, 1, 'Watford', 'Sheffield Wednesday'), (39, 2, 'AFC Bournemouth', 'Middlesbrough'), (39, 3, 'Bristol City', 'Stoke City'), (39, 4, 'Cardiff City', 'Nottingham Forest'), (39, 5, 'Derby County', 'Luton Town'), (39, 6, 'Millwall', 'Wigan Athletic'), (39, 7, 'Preston North End', 'Norwich City'), (39, 8, 'QPR', 'Charlton Athletic'), (39, 9, 'Hull City', 'Blackburn Rovers'), (39, 10, 'Barnsley', 'Reading'), (39, 11, 'Birmingham City', 'Swansea City'), (39, 12, 'Huddersfield Town', 'Fulham'), (40, 1, 'Middlesbrough', 'Watford'), (40, 2, 'Blackburn Rovers', 'AFC Bournemouth'), (40, 3, 'Charlton Athletic', 'Bristol City'), (40, 4, 'Luton Town', 'Barnsley'), (40, 5, 'Nottingham Forest', 'QPR'), (40, 6, 'Reading', 'Derby County'), (40, 7, 'Wigan Athletic', 'Hull City'), (40, 8, 'Stoke City', 'Millwall'), (40, 9, 'Swansea City', 'Preston North End'), (40, 10, 'Sheffield Wednesday', 'Cardiff City'), (40, 11, 'Fulham', 'Birmingham City'), (40, 12, 'Norwich City', 'Huddersfield Town'), (41, 1, 'Watford', 'Reading'), (41, 2, 'Millwall', 'Swansea City'), (41, 3, 'AFC Bournemouth', 'Charlton Athletic'), (41, 4, 'Barnsley', 'Middlesbrough'), (41, 5, 'Birmingham City', 'Stoke City'), (41, 6, 'Bristol City', 'Nottingham Forest'), (41, 7, 'Cardiff City', 'Blackburn Rovers'), (41, 8, 'Derby County', 'Norwich City'), (41, 9, 'Huddersfield Town', 'Wigan Athletic'), (41, 10, 'Preston North End', 'Fulham'), (41, 11, 'QPR', 'Sheffield Wednesday'), (41, 12, 'Hull City', 'Luton Town'), (42, 1, 'Blackburn Rovers', 'Derby County'), (42, 2, 'Reading', 'Cardiff City'), (42, 3, 'Fulham', 'Millwall'), (42, 4, 'Luton Town', 'Watford'), (42, 5, 'Middlesbrough', 'QPR'), (42, 6, 'Nottingham Forest', 'Huddersfield Town'), (42, 7, 'Sheffield Wednesday', 'Bristol City'), (42, 8, 'Stoke City', 'Preston North End'), (42, 9, 'Swansea City', 'Hull City'), (42, 10, 'Norwich City', 'AFC Bournemouth'), (42, 11, 'Wigan Athletic', 'Birmingham City'), (42, 12, 'Charlton Athletic', 'Barnsley'), (43, 1, 'Fulham', 'Cardiff City'), (43, 2, 'Norwich City', 'Watford'), (43, 3, 'Preston North End', 'Derby County'), (43, 4, 'Sheffield Wednesday', 'Blackburn Rovers'), (43, 5, 'Swansea City', 'QPR'), (43, 6, 'Millwall', 'AFC Bournemouth'), (43, 7, 'Wigan Athletic', 'Middlesbrough'), (43, 8, 'Hull City', 'Bristol City'), (43, 9, 'Stoke City', 'Charlton Athletic'), (43, 10, 'Birmingham City', 'Nottingham Forest'), (43, 11, 'Huddersfield Town', 'Barnsley'), (43, 12, 'Luton Town', 'Reading'), (44, 1, 'AFC Bournemouth', 'Fulham'), (44, 2, 'Barnsley', 'Wigan Athletic'), (44, 3, 'Blackburn Rovers', 'Huddersfield Town'), (44, 4, 'Cardiff City', 'Hull City'), (44, 5, 'Charlton Athletic', 'Preston North End'), (44, 6, 'Derby County', 'Birmingham City'), (44, 7, 'Middlesbrough', 'Sheffield Wednesday'), (44, 8, 'Nottingham Forest', 'Stoke City'), (44, 9, 'QPR', 'Norwich City'), (44, 10, 'Watford', 'Millwall'), (44, 11, 'Reading', 'Swansea City'), (44, 12, 'Bristol City', 'Luton Town'), (45, 1, 'Sheffield Wednesday', 'Nottingham Forest'), (45, 2, 'Norwich City', 'Reading'), (45, 3, 'Preston North End', 'Barnsley'), (45, 4, 'Wigan Athletic', 'Blackburn Rovers'), (45, 5, 'Stoke City', 'QPR'), (45, 6, 'Swansea City', 'Derby County'), (45, 7, 'Hull City', 'AFC Bournemouth'), (45, 8, 'Birmingham City', 'Cardiff City'), (45, 9, 'Fulham', 'Watford'), (45, 10, 'Huddersfield Town', 'Charlton Athletic'), (45, 11, 'Luton Town', 'Middlesbrough'), (45, 12, 'Millwall', 'Bristol City'), (46, 1, 'AFC Bournemouth', 'Stoke City'), (46, 2, 'Barnsley', 'Norwich City'), (46, 3, 'Blackburn Rovers', 'Birmingham City'), (46, 4, 'Bristol City', 'Fulham'), (46, 5, 'Cardiff City', 'Wigan Athletic'), (46, 6, 'Charlton Athletic', 'Millwall'), (46, 7, 'Derby County', 'Sheffield Wednesday'), (46, 8, 'Middlesbrough', 'Hull City'), (46, 9, 'Nottingham Forest', 'Preston North End'), (46, 10, 'QPR', 'Luton Town'), (46, 11, 'Reading', 'Huddersfield Town'), (46, 12, 'Watford', 'Swansea City')]

MIDDLESBROUGH_2021_MANAGED_FIXTURES = [(39, 'AFC Bournemouth', 'Middlesbrough'), (40, 'Middlesbrough', 'Watford'), (41, 'Barnsley', 'Middlesbrough'), (42, 'Middlesbrough', 'QPR'), (43, 'Wigan Athletic', 'Middlesbrough'), (44, 'Middlesbrough', 'Sheffield Wednesday'), (45, 'Luton Town', 'Middlesbrough'), (46, 'Middlesbrough', 'Hull City')]


def repair_middlesbrough_career_season_2_if_needed(conn):
    """Repair a stale, unplayed CH002 after restoring an older live/Supabase save.

    v18.67 created Middlesbrough from the real 2020/21 Championship club list.
    Career Season 2 instead keeps the PES 2020 Championship club pool, removes
    Leeds/West Brom/Brentford after promotion, and brings down Bournemouth,
    Watford and Norwich. Never rewrite CH002 once a result has been played.
    """
    challenge = conn.execute("""
        SELECT *
        FROM challenges
        WHERE challenge_id='CH002'
          AND club_or_nation='Middlesbrough'
        LIMIT 1
    """).fetchone()

    if not challenge:
        return False

    played = conn.execute("""
        SELECT COUNT(*) AS n
        FROM fixtures
        WHERE challenge_id='CH002' AND played=1
    """).fetchone()["n"]

    if int(played or 0) > 0:
        return False

    expected_teams = {row[0] for row in MIDDLESBROUGH_2021_OPENING}
    current_rows = conn.execute("""
        SELECT team_name
        FROM opening_stats
        WHERE challenge_id='CH002'
    """).fetchall()
    current_teams = {row["team_name"] for row in current_rows}

    fixture_rows = conn.execute("""
        SELECT home_team, away_team
        FROM fixtures
        WHERE challenge_id='CH002'
    """).fetchall()
    fixture_teams = {
        team
        for row in fixture_rows
        for team in (row["home_team"], row["away_team"])
    }

    stale = (
        len(current_rows) != 24
        or current_teams != expected_teams
        or len(fixture_rows) != 96
        or fixture_teams != expected_teams
    )

    if not stale:
        # Ratings still need to be safe on a restored pre-v18.69 database.
        with conn:
            apply_team_rating_sources(conn)
        return False

    with conn:
        # CH002 has no played results, so it is safe to rebuild the opening
        # table and run-in while leaving completed Derby CH001 untouched.
        conn.execute("DELETE FROM player_match_events WHERE challenge_id='CH002'")
        conn.execute("DELETE FROM computer_goal_events WHERE challenge_id='CH002'")
        conn.execute("DELETE FROM playoff_matches WHERE challenge_id='CH002'")
        conn.execute("DELETE FROM fixtures WHERE challenge_id='CH002'")
        conn.execute("DELETE FROM opening_stats WHERE challenge_id='CH002'")
        conn.execute("DELETE FROM board_log WHERE challenge_id='CH002'")

        conn.execute("""
            UPDATE challenges
            SET competition='EFL Championship',
                objective='Reach the Play-Offs',
                status='Active',
                start_round=38,
                final_round=46,
                opening_position=9,
                opening_points=56,
                target_position=6,
                board_confidence_start=50
            WHERE challenge_id='CH002'
        """)

        ensure_teams_exist(conn, sorted(expected_teams))
        apply_team_rating_sources(conn)

        conn.executemany("""
            INSERT INTO opening_stats(
                challenge_id, team_name, played, won, drawn, lost,
                goals_for, goals_against, goal_difference, points
            )
            VALUES ('CH002', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, MIDDLESBROUGH_2021_OPENING)

        conn.executemany("""
            INSERT INTO fixtures(
                challenge_id, round, match_no, home_team, away_team,
                home_goals, away_goals, played, locked, source, notes
            )
            VALUES ('CH002', ?, ?, ?, ?, NULL, NULL, 0, 0, 'Pending',
                    'Career Season 2 custom Championship schedule — PES 2020 club pool')
        """, MIDDLESBROUGH_2021_FIXTURES)

        conn.execute("""
            INSERT INTO board_log(
                challenge_id, round, board_confidence, assessment, created_at
            )
            VALUES ('CH002', 38, 50, ?, datetime('now'))
        """, (
            "Middlesbrough begin 9th on 56 points, six points outside the play-offs "
            "with eight matches remaining. Leeds United, West Bromwich Albion and "
            "Brentford have gone up; AFC Bournemouth, Watford and Norwich City have "
            "come down. Reach the top six.",
        ))

    return True


def create_middlesbrough_2021_challenge(conn):
    """Create Middlesbrough Career Season 2 using the PES 2020-compatible Championship continuity."""
    active = active_challenge(conn)
    if active:
        if (
            active["club_or_nation"] == "Middlesbrough"
            and int(active["opening_points"] or 0) == 56
            and int(active["opening_position"] or 0) == 9
        ):
            return active["challenge_id"], False
        raise ValueError(
            f"{active['club_or_nation']} is still an active challenge. "
            "Complete and lock it before starting Middlesbrough."
        )

    completed = completed_challenge_count(conn)
    if completed < 1:
        raise ValueError(
            "A completed challenge is required before starting this follow-on job."
        )

    existing = conn.execute("""
        SELECT *
        FROM challenges
        WHERE club_or_nation='Middlesbrough'
          AND opening_position=9
          AND opening_points=56
          AND start_round=38
          AND final_round=46
        ORDER BY challenge_id DESC
        LIMIT 1
    """).fetchone()

    if existing:
        if existing["status"] == "Active":
            return existing["challenge_id"], False
        raise ValueError(
            f"This Middlesbrough Career Season 2 challenge already exists as {existing['challenge_id']} "
            f"with status {existing['status']}. It has not been overwritten."
        )

    new_id = next_challenge_id(conn)
    teams = [row[0] for row in MIDDLESBROUGH_2021_OPENING]

    with conn:
        ensure_manager_exists(conn)
        ensure_current_human_players(conn)
        ensure_teams_exist(conn, teams)

        # All clubs in this custom league exist in PES 2020, so standard PES 2020 ratings are used.

        cleanup_challenge_everywhere(conn, new_id)

        conn.execute("""
            INSERT INTO challenges(
                challenge_id, manager_id, club_or_nation, competition, objective,
                status, start_round, final_round, opening_position, opening_points,
                target_position, board_confidence_start, created_at
            )
            VALUES (?, 'JB001', 'Middlesbrough', 'EFL Championship',
                    'Reach the Play-Offs', 'Active', 38, 46, 9, 56, 6, 50, datetime('now'))
        """, (new_id,))

        conn.executemany("""
            INSERT INTO opening_stats(
                challenge_id, team_name, played, won, drawn, lost,
                goals_for, goals_against, goal_difference, points
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (new_id, team, played, won, drawn, lost, gf, ga, gd, pts)
            for team, played, won, drawn, lost, gf, ga, gd, pts in MIDDLESBROUGH_2021_OPENING
        ])

        conn.executemany("""
            INSERT INTO fixtures(
                challenge_id, round, match_no, home_team, away_team,
                home_goals, away_goals, played, locked, source, notes
            )
            VALUES (?, ?, ?, ?, ?, NULL, NULL, 0, 0, 'Pending', 'Career Season 2 custom Championship schedule — PES 2020 club pool')
        """, [
            (new_id, round_no, match_no, home_team, away_team)
            for round_no, match_no, home_team, away_team in MIDDLESBROUGH_2021_FIXTURES
        ])

        conn.execute("""
            INSERT INTO board_log(
                challenge_id, round, board_confidence, assessment, created_at
            )
            VALUES (?, 38, 50, ?, datetime('now'))
        """, (
            new_id,
            "We saw the impact you made during Derby's run-in. "
            "Middlesbrough begin 9th on 56 points, six points outside the play-offs "
            "with eight matches remaining. Leeds United, West Bromwich Albion and Brentford have gone up; "
            "AFC Bournemouth, Watford and Norwich City have come down. Prove that Derby was no fluke and get us into the top six.",
        ))

    return new_id, True


def reset_derby_challenge_data(conn):
    """Reset the live database to a clean Derby County CH001 run-in."""
    with conn:
        for table in ["player_match_events", "computer_goal_events", "playoff_matches", "fixtures", "opening_stats", "board_log"]:
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM challenges")
        conn.execute("DELETE FROM job_offers")
        conn.execute("DELETE FROM teams")

        conn.execute("""
            INSERT OR IGNORE INTO managers(manager_id, manager_name)
            VALUES ('JB001', 'Jake Brown')
        """)

        ensure_current_human_players(conn)

        conn.execute("""
            INSERT OR IGNORE INTO human_players(player_name)
            VALUES ('Tim Rees')
        """)

        team_names = {row["team_name"] for row in DERBY_RESET_OPENING_STATS}
        for row in DERBY_RESET_FIXTURES:
            team_names.add(row["home_team"])
            team_names.add(row["away_team"])

        for team in sorted(team_names):
            conn.execute("""
                INSERT OR IGNORE INTO teams(team_name, hidden_strength, attack, defence, home_advantage)
                VALUES (?, 70, 70, 70, 3)
            """, (team,))

        conn.execute("""
            INSERT INTO challenges(
                challenge_id, manager_id, club_or_nation, competition, objective,
                status, start_round, final_round, opening_position, opening_points,
                target_position, board_confidence_start, created_at
            )
            VALUES ('CH001', 'JB001', 'Derby County', 'EFL Championship',
                    'Reach the Play-Offs', 'Active', 38, 46, 12, 54, 6, 65, datetime('now'))
        """)

        conn.executemany("""
            INSERT INTO opening_stats(
                challenge_id, team_name, played, won, drawn, lost,
                goals_for, goals_against, goal_difference, points
            )
            VALUES ('CH001', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                row["team_name"], row["played"], row["won"], row["drawn"], row["lost"],
                row["goals_for"], row["goals_against"], row["goal_difference"], row["points"]
            )
            for row in DERBY_RESET_OPENING_STATS
        ])

        conn.executemany("""
            INSERT INTO fixtures(
                challenge_id, round, match_no, home_team, away_team,
                home_goals, away_goals, played, locked, source, notes
            )
            VALUES ('CH001', ?, ?, ?, ?, NULL, NULL, 0, 0, NULL, NULL)
        """, [
            (
                row["round"],
                row["match_no"],
                row["home_team"],
                row["away_team"],
            )
            for row in DERBY_RESET_FIXTURES
        ])

        conn.execute("""
            INSERT INTO board_log(challenge_id, round, board_confidence, assessment, created_at)
            VALUES ('CH001', 38, 65,
                    'Derby challenge started. Derby begin 12th on 54 points, three points outside the play-offs.',
                    datetime('now'))
        """)

        conn.executemany("""
            INSERT INTO job_offers(
                generated_after_challenge_id, club_or_nation, competition,
                current_position, objective, difficulty, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, DERBY_RESET_JOB_OFFERS)


def derby_managed_fixtures(conn, challenge_id="CH001"):
    return conn.execute("""
        SELECT *
        FROM fixtures
        WHERE challenge_id=?
          AND (home_team='Derby County' OR away_team='Derby County')
        ORDER BY round, match_no
    """, (challenge_id,)).fetchall()


def derby_fixture_opponent(row):
    return row["away_team"] if row["home_team"] == "Derby County" else row["home_team"]



def derby_reset_opponents():
    opponents = []
    for row in DERBY_RESET_FIXTURES:
        if row["home_team"] == "Derby County":
            opponents.append(row["away_team"])
        elif row["away_team"] == "Derby County":
            opponents.append(row["home_team"])
    return sorted(set(opponents))


def validate_derby_fixture_slots(slots):
    expected = derby_reset_opponents()
    selected = [slot["opponent"] for slot in slots]

    duplicates = sorted({team for team in selected if selected.count(team) > 1})
    missing = sorted(set(expected) - set(selected))
    unexpected = sorted(set(selected) - set(expected))

    errors = []

    if duplicates:
        errors.append("Duplicate opponent selected: " + ", ".join(duplicates))

    if missing:
        errors.append("Missing opponent: " + ", ".join(missing))

    if unexpected:
        errors.append("Unexpected opponent: " + ", ".join(unexpected))

    if len(selected) != len(expected):
        errors.append(f"Expected {len(expected)} Derby fixtures, got {len(selected)}.")

    return errors


def apply_derby_fixture_order(conn, challenge_id, slots):
    """Update Derby's managed fixture order/venue to match the PES custom league order.

    This intentionally updates the Derby managed fixture rows only. Around-the-grounds
    fixtures remain as the app's simulated background schedule.
    """
    existing = derby_managed_fixtures(conn, challenge_id)

    if len(existing) != len(slots):
        raise ValueError("Could not update fixture order because the Derby fixture count does not match the supplied slots.")

    with conn:
        for idx, slot in enumerate(slots):
            row = existing[idx]
            round_no = 39 + idx
            venue = slot["venue"]
            opponent = slot["opponent"]

            if venue == "H":
                home_team = "Derby County"
                away_team = opponent
            else:
                home_team = opponent
                away_team = "Derby County"

            conn.execute("""
                UPDATE fixtures
                SET round=?, home_team=?, away_team=?, home_goals=NULL, away_goals=NULL,
                    played=0, locked=0, source=NULL, notes=NULL
                WHERE fixture_id=?
            """, (round_no, home_team, away_team, row["fixture_id"]))

        conn.execute("""
            DELETE FROM player_match_events
            WHERE challenge_id=? AND fixture_id IN (
                SELECT fixture_id FROM fixtures
                WHERE challenge_id=?
                  AND (home_team='Derby County' OR away_team='Derby County')
            )
        """, (challenge_id, challenge_id))

        conn.execute("""
            DELETE FROM computer_goal_events
            WHERE challenge_id=? AND fixture_id IN (
                SELECT fixture_id FROM fixtures
                WHERE challenge_id=?
                  AND (home_team='Derby County' OR away_team='Derby County')
            )
        """, (challenge_id, challenge_id))


def seed_default_job_offers(conn):
    try:
        existing = conn.execute("SELECT COUNT(*) AS c FROM job_offers").fetchone()["c"]
    except sqlite3.Error:
        return

    if existing:
        return

    offers = [
        ("CH001", "Blackburn Rovers", "EFL Championship", "11th", "Reach the play-offs", "Medium", "Available"),
        ("CH001", "Sunderland", "EFL Championship", "8th", "Reach the play-offs", "Medium", "Available"),
        ("CH001", "Watford", "EFL Championship", "12th", "Late charge for the play-offs", "Hard", "Available"),
        ("CH001", "Canada", "International", "N/A", "Prepare for a major tournament", "Reputation Builder", "Scenario Needed"),
    ]

    conn.executemany("""
        INSERT INTO job_offers(
            generated_after_challenge_id, club_or_nation, competition,
            current_position, objective, difficulty, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, offers)


def seed_extra_job_offers(conn):
    """Add competition-specific job offers to existing live saves without duplicating them."""
    try:
        conn.execute("SELECT 1 FROM job_offers LIMIT 1")
    except sqlite3.Error:
        return

    offers = [
        ("ANY", "Manchester United", "Premier League", "5th", "Qualify for the Champions League", "High Pressure", "Available"),
        ("ANY", "Arsenal", "Premier League", "10th", "Qualify for Europe", "Hard", "Available"),
        ("ANY", "Tottenham Hotspur", "Premier League", "8th", "Qualify for Europe", "Medium-Hard", "Available"),
        ("ANY", "Everton", "Premier League", "12th", "Finish in the top half", "Medium", "Available"),
        ("ANY", "Aston Villa", "Premier League", "19th", "Avoid relegation", "Survival Battle", "Available"),
        ("ANY", "West Ham United", "Premier League", "17th", "Avoid relegation", "Survival Battle", "Available"),
    ]

    for generated_after, club, competition, current_position, objective, difficulty, status in offers:
        exists = conn.execute("""
            SELECT COUNT(*) AS c
            FROM job_offers
            WHERE club_or_nation=? AND competition=? AND objective=?
        """, (club, competition, objective)).fetchone()["c"]

        if not exists:
            conn.execute("""
                INSERT INTO job_offers(
                    generated_after_challenge_id, club_or_nation, competition,
                    current_position, objective, difficulty, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (generated_after, club, competition, current_position, objective, difficulty, status))


def next_challenge_id(conn):
    rows = conn.execute("SELECT challenge_id FROM challenges").fetchall()
    highest = 0

    for row in rows:
        raw = row["challenge_id"] or ""
        if raw.upper().startswith("CH"):
            try:
                highest = max(highest, int(raw[2:]))
            except ValueError:
                pass

    return f"CH{highest + 1:03d}"


def infer_target_position(objective):
    text = (objective or "").lower()

    if "automatic" in text or "promotion" in text and "play" not in text:
        return 2
    if "play" in text or "top 6" in text:
        return 6
    if "avoid relegation" in text or "survival" in text:
        return 21
    if "mid" in text:
        return 12

    return 6


def infer_target_position_for_competition(objective, competition):
    text = (objective or "").lower()
    comp_slug = slugify_text(competition)

    if "title" in text or "win the league" in text:
        return 1
    if "champions league" in text or "top 4" in text:
        return 4
    if "europe" in text or "europa" in text or "top 7" in text:
        return 7
    if "top half" in text or "top 10" in text:
        return 10
    if "avoid relegation" in text or "survival" in text:
        if comp_slug in {"premier-league", "english-premier-league", "epl", "pl", "la-liga", "serie-a", "bundesliga", "ligue-1"}:
            return 17
        return 21

    return infer_target_position(objective)


def career_player_totals(conn):
    ensure_player_match_event_role_columns(conn)
    return conn.execute("""
        SELECT
            hp.player_name,
            COALESCE(SUM(pme.appearance), 0) AS appearances,
            COALESCE(SUM(pme.started), 0) AS starts,
            COALESCE(SUM(pme.substitute), 0) AS sub_apps,
            COALESCE(SUM(pme.goals), 0) AS goals,
            COALESCE(SUM(pme.assists), 0) AS assists,
            CASE
                WHEN COUNT(CASE WHEN pme.rating IS NOT NULL AND pme.rating > 0 THEN 1 END) = 0 THEN NULL
                ELSE ROUND(AVG(CASE WHEN pme.rating IS NOT NULL AND pme.rating > 0 THEN pme.rating END), 1)
            END AS average_rating,
            COALESCE(SUM(pme.yellow_cards), 0) AS yellow_cards,
            COALESCE(SUM(pme.red_cards), 0) AS red_cards
        FROM human_players hp
        LEFT JOIN player_match_events pme
            ON pme.player_name = hp.player_name
        GROUP BY hp.player_name
        ORDER BY goals DESC, assists DESC, hp.player_name
    """).fetchall()



def managed_match_summary(conn, challenge_id, club):
    """Return manager W-D-L and goals for/against for the managed club.

    Includes posted regular-season fixtures. If play-off matches exist in this
    build/live DB, played managed-club play-off matches are included as well.
    """
    summary = {
        "matches": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "win_percentage": 0,
        "gf": 0,
        "ga": 0,
        "gd": 0,
    }

    def add_match(gf, ga):
        summary["matches"] += 1
        summary["gf"] += gf
        summary["ga"] += ga
        if gf > ga:
            summary["wins"] += 1
        elif gf == ga:
            summary["draws"] += 1
        else:
            summary["losses"] += 1

    rows = conn.execute("""
        SELECT home_team, away_team, home_goals, away_goals
        FROM fixtures
        WHERE challenge_id=?
          AND played=1
          AND (home_team=? OR away_team=?)
    """, (challenge_id, club, club)).fetchall()

    for row in rows:
        if row["home_team"] == club:
            add_match(row["home_goals"] or 0, row["away_goals"] or 0)
        else:
            add_match(row["away_goals"] or 0, row["home_goals"] or 0)

    # Play-off table was introduced in v18. Older saves may not have it yet.
    try:
        playoff_rows = conn.execute("""
            SELECT home_team, away_team, home_goals, away_goals
            FROM playoff_matches
            WHERE challenge_id=?
              AND played=1
              AND (home_team=? OR away_team=?)
        """, (challenge_id, club, club)).fetchall()

        for row in playoff_rows:
            if row["home_team"] == club:
                add_match(row["home_goals"] or 0, row["away_goals"] or 0)
            else:
                add_match(row["away_goals"] or 0, row["home_goals"] or 0)
    except sqlite3.Error:
        pass

    summary["gd"] = summary["gf"] - summary["ga"]
    summary["win_percentage"] = int(round(100.0 * summary["wins"] / summary["matches"])) if summary["matches"] else 0
    return summary


def challenge_cards(conn):
    challenges = conn.execute("""
        SELECT *
        FROM challenges
        ORDER BY challenge_id
    """).fetchall()

    cards = []

    for ch in challenges:
        record = combined_manager_record(conn, ch)
        managed_summary = managed_match_summary(conn, ch["challenge_id"], ch["club_or_nation"])
        table = league_table(conn, ch["challenge_id"])
        current_position, current_points, gap = derby_context(table, ch)
        board_conf, board_assessment = latest_board(
            conn,
            ch["challenge_id"],
            ch["board_confidence_start"],
        )
        remaining = games_remaining(conn, ch["challenge_id"], ch["club_or_nation"])
        playoff_info = playoff_status(conn, ch)

        if ch["status"] == "Completed":
            # Archived cards should show the final contextual board verdict, not
            # the raw last regular-season log entry. This keeps Career aligned
            # with the archived challenge page (e.g. Derby's 78% final rating).
            board_conf = final_board_confidence(
                conn, ch, current_position, current_points, record, board_conf
            )
        else:
            # Active cards use the same contextual calculation as Home/Manager.
            board_conf, board_assessment, _ = contextual_progress_board_update(
                conn,
                ch,
                current_position,
                current_points,
                record,
                board_conf,
                board_assessment,
                gap,
                remaining,
            )

        board_conf = calibrated_board_confidence(
            board_conf,
            current_position,
            ch["target_position"],
            remaining,
            playoff_info,
        )

        cards.append({
            "challenge": ch,
            "record": record,
            "managed_summary": managed_summary,
            "position": current_position,
            "points": current_points,
            "gap": gap,
            "board_conf": board_conf,
            "board_assessment": board_assessment,
            "remaining": remaining,
        })

    return cards



def ensure_manager_exists(conn):
    """Make sure the Jake Brown manager reference exists before creating any challenge."""
    conn.execute("""
        INSERT OR IGNORE INTO managers(manager_id, manager_name)
        VALUES ('JB001', 'Jake Brown')
    """)


def ensure_team_exists(conn, team_name):
    if not team_name:
        return

    conn.execute("""
        INSERT OR IGNORE INTO teams(
            team_name, hidden_strength, attack, defence, home_advantage
        )
        VALUES (?, 70, 70, 70, 3)
    """, (team_name,))


def ensure_teams_exist(conn, team_names):
    for team in sorted({t for t in team_names if t}):
        ensure_team_exists(conn, team)


def cleanup_challenge_everywhere(conn, challenge_id):
    """Delete a partial challenge and any known/detected child rows before retrying.

    Some live saves may have stricter foreign keys than the original bundled DB.
    This removes rows from known challenge tables and also discovers tables that
    reference challenges(challenge_id).
    """
    known_tables = [
        "player_match_events",
        "computer_goal_events",
        "fixtures",
        "opening_stats",
        "board_log",
    ]

    for table in known_tables:
        try:
            cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            if "challenge_id" in cols:
                conn.execute(f"DELETE FROM {table} WHERE challenge_id=?", (challenge_id,))
        except sqlite3.Error:
            pass

    try:
        tables = [
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if row[0] != "challenges"
        ]

        for table in tables:
            try:
                fks = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
                for fk in fks:
                    # columns: id, seq, table, from, to, on_update, on_delete, match
                    if fk[2] == "challenges" and fk[4] == "challenge_id":
                        conn.execute(f"DELETE FROM {table} WHERE {fk[3]}=?", (challenge_id,))
            except sqlite3.Error:
                pass
    except sqlite3.Error:
        pass

    conn.execute("DELETE FROM challenges WHERE challenge_id=?", (challenge_id,))


def foreign_key_problem_summary(conn):
    try:
        rows = conn.execute("PRAGMA foreign_key_check").fetchall()
        if not rows:
            return "No foreign-key detail was returned by SQLite."
        details = []
        for row in rows[:5]:
            details.append(f"table={row[0]}, rowid={row[1]}, parent={row[2]}")
        return "; ".join(details)
    except sqlite3.Error:
        return "SQLite did not return foreign-key detail."


PREMIER_LEAGUE_1920_OPENING = [
    ("Liverpool", 30, 27, 2, 1, 64, 21, 43, 83),
    ("Manchester City", 30, 20, 3, 7, 76, 31, 45, 63),
    ("Leicester City", 30, 16, 6, 8, 59, 29, 30, 54),
    ("Chelsea", 30, 15, 6, 9, 53, 40, 13, 51),
    ("Manchester United", 30, 12, 10, 8, 45, 31, 14, 46),
    ("Wolverhampton Wanderers", 30, 11, 13, 6, 43, 34, 9, 46),
    ("Sheffield United", 30, 11, 11, 8, 30, 28, 2, 44),
    ("Tottenham Hotspur", 30, 11, 9, 10, 48, 41, 7, 42),
    ("Crystal Palace", 30, 11, 9, 10, 28, 32, -4, 42),
    ("Arsenal", 30, 9, 13, 8, 41, 41, 0, 40),
    ("Burnley", 30, 11, 6, 13, 34, 45, -11, 39),
    ("Everton", 30, 10, 8, 12, 37, 46, -9, 38),
    ("Newcastle United", 30, 10, 8, 12, 28, 41, -13, 38),
    ("Southampton", 30, 11, 4, 15, 38, 52, -14, 37),
    ("Brighton & Hove Albion", 30, 7, 11, 12, 34, 41, -7, 32),
    ("Watford", 30, 6, 10, 14, 28, 45, -17, 28),
    ("West Ham United", 30, 7, 6, 17, 35, 54, -19, 27),
    ("AFC Bournemouth", 30, 7, 6, 17, 29, 49, -20, 27),
    ("Aston Villa", 30, 7, 5, 18, 36, 59, -23, 26),
    ("Norwich City", 30, 5, 6, 19, 25, 55, -30, 21),
]

PREMIER_LEAGUE_1920_FIXTURES = [
    (31, 1, "Leicester City", "Brighton & Hove Albion"),
    (31, 2, "Tottenham Hotspur", "West Ham United"),
    (31, 3, "Manchester United", "Sheffield United"),
    (31, 4, "Newcastle United", "Aston Villa"),
    (31, 5, "Norwich City", "Everton"),
    (31, 6, "Wolverhampton Wanderers", "AFC Bournemouth"),
    (31, 7, "Liverpool", "Crystal Palace"),
    (31, 8, "Burnley", "Watford"),
    (31, 9, "Southampton", "Arsenal"),
    (31, 10, "Chelsea", "Manchester City"),
    (32, 1, "Aston Villa", "Wolverhampton Wanderers"),
    (32, 2, "Watford", "Southampton"),
    (32, 3, "Crystal Palace", "Burnley"),
    (32, 4, "Brighton & Hove Albion", "Manchester United"),
    (32, 5, "Everton", "Leicester City"),
    (32, 6, "AFC Bournemouth", "Newcastle United"),
    (32, 7, "Arsenal", "Norwich City"),
    (32, 8, "West Ham United", "Chelsea"),
    (32, 9, "Sheffield United", "Tottenham Hotspur"),
    (32, 10, "Manchester City", "Liverpool"),
    (33, 1, "Norwich City", "Brighton & Hove Albion"),
    (33, 2, "Leicester City", "Crystal Palace"),
    (33, 3, "Manchester United", "AFC Bournemouth"),
    (33, 4, "Wolverhampton Wanderers", "Arsenal"),
    (33, 5, "Chelsea", "Watford"),
    (33, 6, "Burnley", "Sheffield United"),
    (33, 7, "Newcastle United", "West Ham United"),
    (33, 8, "Liverpool", "Aston Villa"),
    (33, 9, "Southampton", "Manchester City"),
    (33, 10, "Tottenham Hotspur", "Everton"),
    (34, 1, "Crystal Palace", "Chelsea"),
    (34, 2, "Arsenal", "Leicester City"),
    (34, 3, "Manchester City", "Newcastle United"),
    (34, 4, "Sheffield United", "Wolverhampton Wanderers"),
    (34, 5, "Everton", "Southampton"),
    (34, 6, "AFC Bournemouth", "Tottenham Hotspur"),
    (34, 7, "Aston Villa", "Manchester United"),
    (34, 8, "West Ham United", "Burnley"),
    (34, 9, "Watford", "Norwich City"),
    (34, 10, "Brighton & Hove Albion", "Liverpool"),
    (35, 1, "Norwich City", "West Ham United"),
    (35, 2, "Watford", "Newcastle United"),
    (35, 3, "Liverpool", "Burnley"),
    (35, 4, "Sheffield United", "Chelsea"),
    (35, 5, "Brighton & Hove Albion", "Manchester City"),
    (35, 6, "Wolverhampton Wanderers", "Everton"),
    (35, 7, "Aston Villa", "Crystal Palace"),
    (35, 8, "Tottenham Hotspur", "Arsenal"),
    (35, 9, "AFC Bournemouth", "Leicester City"),
    (35, 10, "Manchester United", "Southampton"),
    (36, 1, "Chelsea", "Norwich City"),
    (36, 2, "Burnley", "Wolverhampton Wanderers"),
    (36, 3, "Manchester City", "AFC Bournemouth"),
    (36, 4, "Arsenal", "Liverpool"),
    (36, 5, "Everton", "Aston Villa"),
    (36, 6, "Leicester City", "Sheffield United"),
    (36, 7, "Crystal Palace", "Manchester United"),
    (36, 8, "Southampton", "Brighton & Hove Albion"),
    (36, 9, "West Ham United", "Watford"),
    (36, 10, "Newcastle United", "Tottenham Hotspur"),
    (37, 1, "Norwich City", "Burnley"),
    (37, 2, "AFC Bournemouth", "Southampton"),
    (37, 3, "Tottenham Hotspur", "Leicester City"),
    (37, 4, "Brighton & Hove Albion", "Newcastle United"),
    (37, 5, "Sheffield United", "Everton"),
    (37, 6, "Wolverhampton Wanderers", "Crystal Palace"),
    (37, 7, "Watford", "Manchester City"),
    (37, 8, "Aston Villa", "Arsenal"),
    (37, 9, "Manchester United", "West Ham United"),
    (37, 10, "Liverpool", "Chelsea"),
    (38, 1, "Arsenal", "Watford"),
    (38, 2, "Burnley", "Brighton & Hove Albion"),
    (38, 3, "Chelsea", "Wolverhampton Wanderers"),
    (38, 4, "Crystal Palace", "Tottenham Hotspur"),
    (38, 5, "Everton", "AFC Bournemouth"),
    (38, 6, "Leicester City", "Manchester United"),
    (38, 7, "Manchester City", "Norwich City"),
    (38, 8, "Newcastle United", "Liverpool"),
    (38, 9, "Southampton", "Sheffield United"),
    (38, 10, "West Ham United", "Aston Villa"),
]

PREMIER_LEAGUE_1920_STRENGTHS = {
    "Liverpool": 95,
    "Manchester City": 92,
    "Leicester City": 84,
    "Chelsea": 83,
    "Manchester United": 82,
    "Wolverhampton Wanderers": 81,
    "Tottenham Hotspur": 81,
    "Arsenal": 80,
    "Sheffield United": 77,
    "Everton": 76,
    "Burnley": 73,
    "Crystal Palace": 73,
    "Southampton": 73,
    "Newcastle United": 72,
    "West Ham United": 68,
    "Brighton & Hove Albion": 67,
    "Watford": 67,
    "AFC Bournemouth": 66,
    "Aston Villa": 65,
    "Norwich City": 62,
}


def static_competition_template(competition):
    slug = slugify_text(competition)
    if slug in {"premier-league", "english-premier-league", "epl", "pl"}:
        return {
            "competition": "Premier League",
            "season_label": "2019/20",
            "start_round": 30,
            "final_round": 38,
            "opening": PREMIER_LEAGUE_1920_OPENING,
            "fixtures": PREMIER_LEAGUE_1920_FIXTURES,
            "strengths": PREMIER_LEAGUE_1920_STRENGTHS,
            "board_start": 50,
            "board_intro": "Premier League 2019/20 run-in started. The board expects the target to be attacked immediately.",
        }
    return None


def create_static_competition_challenge_from_offer(conn, offer, template):
    club = offer["club_or_nation"]
    opening_lookup = {row[0]: row for row in template["opening"]}

    if club not in opening_lookup:
        raise ValueError(f"{club} is not in the {template['competition']} {template['season_label']} template.")

    new_id = next_challenge_id(conn)
    target_position = infer_target_position_for_competition(offer["objective"], template["competition"])
    opening_position = parse_position_value(offer["current_position"], None)
    if opening_position is None:
        # Calculate from the template table if the offer text is not numeric.
        sorted_rows = sorted(template["opening"], key=lambda r: (r[8], r[7], r[5]), reverse=True)
        opening_position = next((idx + 1 for idx, row in enumerate(sorted_rows) if row[0] == club), None)

    opening = opening_lookup[club]
    all_teams = [row[0] for row in template["opening"]]
    all_teams += [row[2] for row in template["fixtures"]]
    all_teams += [row[3] for row in template["fixtures"]]

    try:
        with conn:
            ensure_manager_exists(conn)
            ensure_teams_exist(conn, all_teams)

            for team, strength in template["strengths"].items():
                conn.execute("""
                    UPDATE teams
                    SET hidden_strength=?, attack=?, defence=?, home_advantage=3
                    WHERE team_name=?
                """, (strength, strength, strength, team))

            cleanup_challenge_everywhere(conn, new_id)

            conn.execute("""
                UPDATE challenges
                SET status='Completed'
                WHERE status='Active'
            """)

            conn.execute("""
                INSERT INTO challenges(
                    challenge_id, manager_id, club_or_nation, competition, objective,
                    status, start_round, final_round, opening_position, opening_points,
                    target_position, board_confidence_start, created_at
                )
                VALUES (?, 'JB001', ?, ?, ?, 'Active', ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                new_id,
                club,
                template["competition"],
                offer["objective"],
                template["start_round"],
                template["final_round"],
                opening_position,
                opening[8],
                target_position,
                template["board_start"],
            ))

            conn.executemany("""
                INSERT INTO opening_stats(
                    challenge_id, team_name, played, won, drawn, lost,
                    goals_for, goals_against, goal_difference, points
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (new_id, team, played, won, drawn, lost, gf, ga, gd, points)
                for team, played, won, drawn, lost, gf, ga, gd, points in template["opening"]
            ])

            conn.executemany("""
                INSERT INTO fixtures(
                    challenge_id, round, match_no, home_team, away_team,
                    home_goals, away_goals, played, locked, source, notes
                )
                VALUES (?, ?, ?, ?, ?, NULL, NULL, 0, 0, 'Pending', NULL)
            """, [
                (new_id, round_no, match_no, home_team, away_team)
                for round_no, match_no, home_team, away_team in template["fixtures"]
            ])

            conn.execute("""
                INSERT INTO board_log(challenge_id, round, board_confidence, assessment, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, (new_id, template["start_round"], template["board_start"], template["board_intro"]))

            conn.execute("""
                UPDATE job_offers
                SET status='Accepted'
                WHERE offer_id=?
            """, (offer["offer_id"],))

    except sqlite3.IntegrityError as exc:
        detail = foreign_key_problem_summary(conn)
        raise sqlite3.Error(
            f"Could not create the new {template['competition']} challenge because the database rejected duplicate or invalid data: {exc}. Detail: {detail}"
        )

    return new_id


def clone_championship_challenge_from_offer(conn, offer):
    club = offer["club_or_nation"]

    if not club:
        raise ValueError("This job offer is missing a club or nation name.")

    static_template = static_competition_template(offer["competition"])
    if static_template:
        return create_static_competition_challenge_from_offer(conn, offer, static_template)

    source_challenge_id = source_challenge_for_new_job(conn)
    if not source_challenge_id:
        raise ValueError("No completed source challenge exists to clone fixtures from.")

    opening = conn.execute("""
        SELECT *
        FROM opening_stats
        WHERE challenge_id=? AND team_name=?
    """, (source_challenge_id, club)).fetchone()

    if not opening:
        raise ValueError("The selected club is not present in the source league table.")

    new_id = next_challenge_id(conn)
    target_position = infer_target_position_for_competition(offer["objective"], offer["competition"])
    opening_position = parse_position_value(offer["current_position"], opening["played"])

    source_opening_rows = conn.execute("""
        SELECT team_name, played, won, drawn, lost, goals_for, goals_against, goal_difference, points
        FROM opening_stats
        WHERE challenge_id=?
    """, (source_challenge_id,)).fetchall()

    if not source_opening_rows:
        raise ValueError("The source challenge has no opening table to clone.")

    source_fixtures = conn.execute("""
        SELECT round, match_no, home_team, away_team
        FROM fixtures
        WHERE challenge_id=?
        ORDER BY round, match_no
    """, (source_challenge_id,)).fetchall()

    if not source_fixtures:
        raise ValueError("The source challenge has no fixtures to clone.")

    all_teams = [row["team_name"] for row in source_opening_rows]
    all_teams += [row["home_team"] for row in source_fixtures]
    all_teams += [row["away_team"] for row in source_fixtures]
    all_teams.append(club)

    try:
        with conn:
            ensure_manager_exists(conn)
            ensure_teams_exist(conn, all_teams)
            cleanup_challenge_everywhere(conn, new_id)

            conn.execute("""
                UPDATE challenges
                SET status='Completed'
                WHERE status='Active'
            """)

            conn.execute("""
                INSERT INTO challenges(
                    challenge_id, manager_id, club_or_nation, competition, objective,
                    status, start_round, final_round, opening_position, opening_points,
                    target_position, board_confidence_start, created_at
                )
                VALUES (?, 'JB001', ?, ?, ?, 'Active', 38, 46, ?, ?, ?, 50, datetime('now'))
            """, (
                new_id,
                club,
                offer["competition"],
                offer["objective"],
                opening_position,
                opening["points"],
                target_position,
            ))

            conn.executemany("""
                INSERT INTO opening_stats(
                    challenge_id, team_name, played, won, drawn, lost,
                    goals_for, goals_against, goal_difference, points
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    new_id,
                    row["team_name"],
                    row["played"],
                    row["won"],
                    row["drawn"],
                    row["lost"],
                    row["goals_for"],
                    row["goals_against"],
                    row["goal_difference"],
                    row["points"],
                )
                for row in source_opening_rows
            ])

            conn.executemany("""
                INSERT INTO fixtures(
                    challenge_id, round, match_no, home_team, away_team,
                    home_goals, away_goals, played, locked, source, notes
                )
                VALUES (?, ?, ?, ?, ?, NULL, NULL, 0, 0, 'Pending', NULL)
            """, [
                (
                    new_id,
                    row["round"],
                    row["match_no"],
                    row["home_team"],
                    row["away_team"],
                )
                for row in source_fixtures
            ])

            conn.execute("""
                INSERT INTO board_log(challenge_id, round, board_confidence, assessment, created_at)
                VALUES (?, 38, 50, 'New challenge started. The board starts neutral and will judge the run-in on results.', datetime('now'))
            """, (new_id,))

            conn.execute("""
                UPDATE job_offers
                SET status='Accepted'
                WHERE offer_id=?
            """, (offer["offer_id"],))

    except sqlite3.IntegrityError as exc:
        detail = foreign_key_problem_summary(conn)
        raise sqlite3.Error(
            f"Could not create the new challenge because the database rejected duplicate or invalid data: {exc}. Detail: {detail}"
        )

    return new_id


def slugify_text(value):
    return (
        (value or "")
        .lower()
        .replace("&", "and")
        .replace(".", "")
        .replace("'", "")
        .replace("/", "-")
        .replace(" ", "-")
    )



def competition_display_name(competition):
    value = (competition or "").strip()
    slug = slugify_text(value)
    display_names = {
        "championship": "EFL Championship",
        "efl-championship": "EFL Championship",
        "english-championship": "EFL Championship",
        "sky-bet-championship": "EFL Championship",
        "skybet-championship": "EFL Championship",
        "premier-league": "Premier League",
        "english-premier-league": "Premier League",
        "epl": "Premier League",
        "pl": "Premier League",
        "league-one": "EFL League One",
        "efl-league-one": "EFL League One",
        "sky-bet-league-one": "EFL League One",
        "league-two": "EFL League Two",
        "efl-league-two": "EFL League Two",
        "sky-bet-league-two": "EFL League Two",
        "champions-league": "UEFA Champions League",
        "uefa-champions-league": "UEFA Champions League",
        "ucl": "UEFA Champions League",
        "europa-league": "UEFA Europa League",
        "uefa-europa-league": "UEFA Europa League",
        "uel": "UEFA Europa League",
        "conference-league": "UEFA Conference League",
        "uefa-conference-league": "UEFA Conference League",
        "uecl": "UEFA Conference League",
        "la-liga": "La Liga",
        "laliga": "La Liga",
        "la-liga-2": "La Liga 2",
        "laliga-2": "La Liga 2",
        "serie-a": "Serie A",
        "serie-b": "Serie B",
        "bundesliga": "Bundesliga",
        "2-bundesliga": "2. Bundesliga",
        "second-bundesliga": "2. Bundesliga",
        "ligue-1": "Ligue 1",
        "ligue-2": "Ligue 2",
        "canada": "Canada",
        "world-cup": "FIFA World Cup",
        "fifa-world-cup": "FIFA World Cup",
    }
    return display_names.get(slug, value or "Competition")


def competition_logo_aliases():
    return {
        "championship": "efl-championship",
        "efl-championship": "efl-championship",
        "english-championship": "efl-championship",
        "sky-bet-championship": "efl-championship",
        "skybet-championship": "efl-championship",
        "premier-league": "english-premier-league",
        "english-premier-league": "english-premier-league",
        "epl": "english-premier-league",
        "pl": "english-premier-league",
        "league-one": "efl-league-one",
        "efl-league-one": "efl-league-one",
        "sky-bet-league-one": "efl-league-one",
        "league-two": "efl-league-two",
        "efl-league-two": "efl-league-two",
        "sky-bet-league-two": "efl-league-two",
        "champions-league": "uefa-champions-league",
        "uefa-champions-league": "uefa-champions-league",
        "ucl": "uefa-champions-league",
        "europa-league": "uefa-europa-league",
        "uefa-europa-league": "uefa-europa-league",
        "uel": "uefa-europa-league",
        "conference-league": "uefa-conference-league",
        "uefa-conference-league": "uefa-conference-league",
        "uecl": "uefa-conference-league",
        "la-liga": "la-liga",
        "laliga": "la-liga",
        "la-liga-2": "la-liga-2",
        "laliga-2": "la-liga-2",
        "serie-a": "serie-a",
        "serie-b": "serie-b",
        "bundesliga": "bundesliga",
        "2-bundesliga": "2-bundesliga",
        "second-bundesliga": "2-bundesliga",
        "ligue-1": "ligue-1",
        "ligue-2": "ligue-2",
        "fifa-world-cup": "fifa-world-cup-2026",
        "world-cup": "fifa-world-cup-2026",
    }


def competition_logo_sources():
    # Remote fallbacks from football-logos.cc. Local files in static/competition_logos
    # with matching slugs take priority, so hard-copy backups can be added later.
    return {
        "efl-championship": "https://assets.football-logos.cc/logos/england/1500x1500/efl-championship.c50fa46f.png",
        "english-premier-league": "https://assets.football-logos.cc/logos/england/1500x1500/english-premier-league.6b5b73f0.png",
        "efl-league-one": "https://assets.football-logos.cc/logos/england/1500x1500/efl-league-one.59c51464.png",
        "efl-league-two": "https://assets.football-logos.cc/logos/england/1500x1500/efl-league-two.3afec297.png",
        "uefa-champions-league": "https://assets.football-logos.cc/logos/tournaments/1500x1500/uefa-champions-league.47d48d4e.png",
        "uefa-europa-league": "https://assets.football-logos.cc/logos/tournaments/1500x1500/uefa-europa-league.a5dfd022.png",
        "uefa-conference-league": "https://assets.football-logos.cc/logos/tournaments/1500x1500/uefa-conference-league.7fce1e15.png",
        "la-liga": "https://assets.football-logos.cc/logos/spain/1500x1500/la-liga.07ed875e.png",
        "serie-a": "https://assets.football-logos.cc/logos/italy/1500x1500/serie-a.0e7a37ed.png",
        "bundesliga": "https://assets.football-logos.cc/logos/germany/1500x1500/bundesliga.77719ba2.png",
        "ligue-1": "https://assets.football-logos.cc/logos/france/1500x1500/ligue-1.0cc44ebd.png",
    }


def competition_logo_for(competition):
    slug = slugify_text(competition)
    slug = competition_logo_aliases().get(slug, slug)

    # Hard-copy local backups can be added here. This intentionally avoids the
    # older placeholder in static/competitions/efl-championship.svg.
    for ext in ("png", "svg", "webp", "jpg", "jpeg"):
        local_path = APP_DIR / "static" / "competition_logos" / f"{slug}.{ext}"
        if local_path.exists():
            return f"/static/competition_logos/{slug}.{ext}"

    return competition_logo_sources().get(slug)


def short_player_name(name):
    value = (name or "").strip()
    if not value:
        return ""
    parts = value.split()
    if len(parts) >= 2:
        return parts[-1]
    return value


def make_backup_filename(prefix="pro_clubs_save"):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}.db"



def safe_fixture_dict(row):
    return dict(row) if row is not None else None


def safe_player_event_dict(row):
    data = dict(row)
    data.setdefault("yellow_cards", None)
    data.setdefault("red_cards", None)
    data.setdefault("rating", None)
    return data


def managed_results(conn, challenge_id, club):
    fixtures = conn.execute("""
        SELECT *
        FROM fixtures
        WHERE challenge_id=?
          AND played=1
          AND (home_team=? OR away_team=?)
        ORDER BY round DESC, match_no DESC
    """, (challenge_id, club, club)).fetchall()

    results = []

    for fixture in fixtures:
        player_events = conn.execute("""
            SELECT
                player_name,
                goals,
                assists,
                appearance,
                started,
                substitute,
                yellow_cards,
                red_cards,
                rating,
                notes
            FROM player_match_events
            WHERE challenge_id=? AND fixture_id=?
            ORDER BY goals DESC, assists DESC, yellow_cards DESC, red_cards DESC, player_name
        """, (challenge_id, fixture["fixture_id"])).fetchall()

        computer_goals_row = conn.execute("""
            SELECT COALESCE(SUM(goals), 0) AS goals
            FROM computer_goal_events
            WHERE challenge_id=? AND fixture_id=?
        """, (challenge_id, fixture["fixture_id"])).fetchone()

        results.append({
            "fixture": safe_fixture_dict(fixture),
            "player_events": [safe_player_event_dict(e) for e in player_events],
            "computer_goals": computer_goals_row["goals"] if computer_goals_row else 0,
        })

    return results


def upcoming_managed_fixtures(conn, challenge_id, club):
    return [
        safe_fixture_dict(row)
        for row in conn.execute("""
            SELECT *
            FROM fixtures
            WHERE challenge_id=?
              AND played=0
              AND (home_team=? OR away_team=?)
            ORDER BY round, match_no
        """, (challenge_id, club, club)).fetchall()
    ]


def all_played_rounds(conn, challenge_id):
    rounds = conn.execute("""
        SELECT DISTINCT round
        FROM fixtures
        WHERE challenge_id=?
          AND played=1
        ORDER BY round DESC
    """, (challenge_id,)).fetchall()

    groups = []

    for round_row in rounds:
        fixtures = conn.execute("""
            SELECT *
            FROM fixtures
            WHERE challenge_id=?
              AND round=?
              AND played=1
            ORDER BY match_no
        """, (challenge_id, round_row["round"])).fetchall()

        groups.append({
            "round": round_row["round"],
            "fixtures": [safe_fixture_dict(f) for f in fixtures],
        })

    return groups


def challenge_progress_verdict(conn, challenge, current_position, current_points, completed_count, games_remaining, record, board_assessment, gap=None):
    club = challenge["club_or_nation"]
    target = int(challenge["target_position"] or 6)
    objective = challenge["objective"]
    opening_position = challenge["opening_position"]
    opening_points = challenge["opening_points"]

    if completed_count == 0:
        rating = challenge_team_rating_context(conn, challenge)
        baseline = ""
        if rating["rating_rank"] is not None:
            baseline = f" Squad baseline: around {ordinal_position(rating['rating_rank'])} strongest in the field."
        return (
            f"Progress update only — the {club} challenge has not started on the pitch. "
            f"We asked Jake to {objective.lower()}. "
            f"{club} start {ordinal_position(opening_position)} on {opening_points} points with {games_remaining} games to play."
            f"{baseline} The final verdict will judge the outcome and the controllables together."
        )

    progress = progress_board_context(
        conn,
        challenge,
        current_position,
        current_points,
        record,
        games_remaining,
        gap,
    )
    ctx = progress["context"]

    movement_text = ""
    if ctx["opening_position"] is not None and current_position is not None:
        if ctx["movement"] and ctx["movement"] > 0:
            movement_text = f" Jake has moved the side from {ordinal_position(ctx['opening_position'])} to {ordinal_position(current_position)}."
        elif ctx["movement"] and ctx["movement"] < 0:
            movement_text = f" Jake has moved the side from {ordinal_position(ctx['opening_position'])} to {ordinal_position(current_position)}."
        else:
            movement_text = f" The side remain {ordinal_position(current_position)}."

    points_text = f" Points gained under the manager: {ctx['points_gained']}." if ctx["points_gained"] is not None else ""
    target_text = ""
    if current_position is not None:
        if int(current_position) <= target:
            target_text = f" Current position: {ordinal_position(current_position)}, inside the target of {ordinal_position(target)}."
        elif gap is not None:
            target_text = f" Current position: {ordinal_position(current_position)}, {int(gap or 0)} point(s) off the target."

    return (
        f"Progress update only — this is not the final verdict yet. "
        f"{club} have played {completed_count} run-in game(s), with {games_remaining} still to play. "
        f"{progress['message']}"
        f"{movement_text}{points_text} {target_text}"
    )

def completed_managed_fixtures_count(conn, challenge_id, club):
    return conn.execute("""
        SELECT COUNT(*) AS c
        FROM fixtures
        WHERE challenge_id=?
          AND played=1
          AND (home_team=? OR away_team=?)
    """, (challenge_id, club, club)).fetchone()["c"]



def regular_season_finished(conn, challenge):
    return games_remaining(conn, challenge["challenge_id"], challenge["club_or_nation"]) == 0


def playoff_seed_table(conn, challenge_id):
    return list(league_table(conn, challenge_id))[:6]


def is_playoff_position(position):
    return position is not None and 3 <= int(position) <= 6


def get_playoff_matches(conn, challenge_id):
    return conn.execute("""
        SELECT *
        FROM playoff_matches
        WHERE challenge_id=?
        ORDER BY
            CASE stage
                WHEN 'Semi-Final' THEN 1
                WHEN 'Final' THEN 2
                ELSE 3
            END,
            match_no,
            leg,
            playoff_id
    """, (challenge_id,)).fetchall()



def playoff_matches_with_events(conn, challenge_id):
    """Return play-off matches with tracked Derby player events attached.

    Play-off match player events are stored against synthetic fixture_id = -playoff_id.
    App-simulated non-human ties do not have individual scorers available.
    """
    rows = get_playoff_matches(conn, challenge_id)
    enriched = []

    for row in rows:
        item = dict(row)
        synthetic_fixture_id = -int(row["playoff_id"])

        player_events = conn.execute("""
            SELECT
                player_name,
                goals,
                assists,
                appearance,
                started,
                substitute,
                yellow_cards,
                red_cards,
                rating,
                notes
            FROM player_match_events
            WHERE challenge_id=? AND fixture_id=?
            ORDER BY goals DESC, assists DESC, player_name
        """, (challenge_id, synthetic_fixture_id)).fetchall()

        computer_goals_row = conn.execute("""
            SELECT COALESCE(SUM(goals), 0) AS goals
            FROM computer_goal_events
            WHERE challenge_id=? AND fixture_id=?
        """, (challenge_id, synthetic_fixture_id)).fetchone()

        item["player_events"] = [safe_player_event_dict(e) for e in player_events]
        item["computer_goals"] = computer_goals_row["goals"] if computer_goals_row else 0
        enriched.append(item)

    return enriched


def playoff_matches_generated(conn, challenge_id):
    row = conn.execute("""
        SELECT COUNT(*) AS c
        FROM playoff_matches
        WHERE challenge_id=?
    """, (challenge_id,)).fetchone()
    return row["c"] > 0


def generate_playoff_fixtures(conn, challenge):
    """Generate Championship play-off semi-final fixtures from final league table.

    3rd plays 6th; 4th plays 5th.
    Leg 1: lower seed at home.
    Leg 2: higher seed at home.
    """
    table = playoff_seed_table(conn, challenge["challenge_id"])
    if len(table) < 6:
        raise ValueError("Cannot generate play-offs because the top six is unavailable.")

    seeds = {row["position"]: row["team_name"] for row in table}

    required = [3, 4, 5, 6]
    missing = [seed for seed in required if seed not in seeds]
    if missing:
        raise ValueError("Cannot generate play-offs because one or more play-off seeds are missing.")

    if playoff_matches_generated(conn, challenge["challenge_id"]):
        return 0

    fixtures = [
        ("Semi-Final", 1, 1, seeds[6], seeds[3], 0),
        ("Semi-Final", 2, 1, seeds[3], seeds[6], 0),
        ("Semi-Final", 1, 2, seeds[5], seeds[4], 0),
        ("Semi-Final", 2, 2, seeds[4], seeds[5], 0),
    ]

    with conn:
        for stage, leg, match_no, home, away, neutral in fixtures:
            conn.execute("""
                INSERT INTO playoff_matches(
                    challenge_id, stage, leg, match_no, home_team, away_team,
                    played, neutral, source, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, NULL, NULL)
            """, (
                challenge["challenge_id"],
                stage,
                leg,
                match_no,
                home,
                away,
                neutral,
            ))

    return len(fixtures)


def playoff_tie_rows(conn, challenge_id, match_no):
    return conn.execute("""
        SELECT *
        FROM playoff_matches
        WHERE challenge_id=?
          AND stage='Semi-Final'
          AND match_no=?
        ORDER BY leg
    """, (challenge_id, match_no)).fetchall()


def playoff_tie_winner(conn, challenge_id, match_no):
    rows = playoff_tie_rows(conn, challenge_id, match_no)
    if len(rows) < 2 or any(not row["played"] for row in rows):
        return None

    teams = sorted({rows[0]["home_team"], rows[0]["away_team"]})
    totals = {team: 0 for team in teams}

    for row in rows:
        totals[row["home_team"]] += row["home_goals"] or 0
        totals[row["away_team"]] += row["away_goals"] or 0

    if totals[teams[0]] > totals[teams[1]]:
        return teams[0]
    if totals[teams[1]] > totals[teams[0]]:
        return teams[1]

    # Aggregate tie: use the explicitly selected penalty/extra-time winner on leg 2.
    return rows[-1]["winner_team"]


def playoff_final_row(conn, challenge_id):
    return conn.execute("""
        SELECT *
        FROM playoff_matches
        WHERE challenge_id=?
          AND stage='Final'
        ORDER BY playoff_id DESC
        LIMIT 1
    """, (challenge_id,)).fetchone()


def playoff_match_winner(row):
    if not row or not row["played"]:
        return None

    if (row["home_goals"] or 0) > (row["away_goals"] or 0):
        return row["home_team"]
    if (row["away_goals"] or 0) > (row["home_goals"] or 0):
        return row["away_team"]

    return row["winner_team"]


def maybe_generate_playoff_final(conn, challenge_id):
    if playoff_final_row(conn, challenge_id):
        return None

    winner_a = playoff_tie_winner(conn, challenge_id, 1)
    winner_b = playoff_tie_winner(conn, challenge_id, 2)

    if not winner_a or not winner_b:
        return None

    with conn:
        conn.execute("""
            INSERT INTO playoff_matches(
                challenge_id, stage, leg, match_no, home_team, away_team,
                played, neutral, source, notes
            )
            VALUES (?, 'Final', 1, 1, ?, ?, 0, 1, NULL, 'Neutral venue')
        """, (challenge_id, winner_a, winner_b))

    return (winner_a, winner_b)


def playoff_qualified(conn, challenge):
    if not regular_season_finished(conn, challenge):
        return False

    table = league_table(conn, challenge["challenge_id"])
    row = final_position_row(table, challenge["club_or_nation"])
    position = row["position"] if row else None
    return is_playoff_position(position)



def next_managed_playoff_match(conn, challenge):
    """Return the next unplayed play-off match involving the managed club."""
    rows = get_playoff_matches(conn, challenge["challenge_id"])
    club = challenge["club_or_nation"]

    for row in rows:
        if row["played"]:
            continue
        if row["home_team"] == club or row["away_team"] == club:
            return row

    return None


def simulate_unmanaged_playoff_matches(conn, challenge, stage=None, leg=None):
    """Auto-fill matching unplayed play-off matches that do not involve the managed club.

    The key behaviour is deliberately synchronised with Derby's progress:
    - after Derby semi-final leg 1, simulate only the other semi-final leg 1
    - after Derby semi-final leg 2, simulate only the other semi-final leg 2
    - final is generated only after both semi-finals are complete

    If stage/leg are omitted, no bulk simulation is performed. This prevents the
    other semi-final being fully played immediately when fixtures are generated.
    """
    if stage is None:
        return 0

    club = challenge["club_or_nation"]
    rows = get_playoff_matches(conn, challenge["challenge_id"])

    simulated = 0
    with conn:
        for row in rows:
            if row["played"]:
                continue
            if row["home_team"] == club or row["away_team"] == club:
                continue
            if row["stage"] != stage:
                continue
            if leg is not None and row["leg"] != leg:
                continue

            home_goals, away_goals = simulate_scoreline(
                conn,
                challenge["challenge_id"],
                row["home_team"],
                row["away_team"],
            )

            winner_team = None

            if row["stage"] == "Final" and home_goals == away_goals:
                home_rating = team_rating(conn, row["home_team"]) or 70
                away_rating = team_rating(conn, row["away_team"]) or 70
                winner_team = row["home_team"] if home_rating >= away_rating else row["away_team"]

            if row["stage"] == "Semi-Final" and row["leg"] == 2:
                existing = playoff_tie_rows(conn, row["challenge_id"], row["match_no"])
                if len(existing) == 2:
                    leg1 = existing[0]
                    totals = {
                        row["home_team"]: home_goals,
                        row["away_team"]: away_goals,
                    }
                    totals[leg1["home_team"]] = totals.get(leg1["home_team"], 0) + (leg1["home_goals"] or 0)
                    totals[leg1["away_team"]] = totals.get(leg1["away_team"], 0) + (leg1["away_goals"] or 0)
                    teams = list(totals.keys())
                    if len(teams) == 2 and totals[teams[0]] == totals[teams[1]]:
                        home_rating = team_rating(conn, row["home_team"]) or 70
                        away_rating = team_rating(conn, row["away_team"]) or 70
                        winner_team = row["home_team"] if home_rating >= away_rating else row["away_team"]

            conn.execute("""
                UPDATE playoff_matches
                SET home_goals=?, away_goals=?, played=1, winner_team=?, source='App Simulation', notes='Simulated other play-off tie'
                WHERE playoff_id=?
            """, (home_goals, away_goals, winner_team, row["playoff_id"]))

            simulated += 1

    if simulated:
        maybe_generate_playoff_final(conn, challenge["challenge_id"])

    return simulated


def playoff_status(conn, challenge):
    table = league_table(conn, challenge["challenge_id"])
    row = final_position_row(table, challenge["club_or_nation"])
    position = row["position"] if row else None
    club = challenge["club_or_nation"]

    status = {
        "regular_finished": regular_season_finished(conn, challenge),
        "league_position": position,
        "qualified": False,
        "generated": playoff_matches_generated(conn, challenge["challenge_id"]),
        "finished": False,
        "promoted": False,
        "exit_stage": None,
        "message": "",
        "needs_playoffs": False,
    }

    if not status["regular_finished"]:
        status["message"] = "Regular season still in progress."
        return status

    if position is not None and position <= 2:
        status["finished"] = True
        status["promoted"] = True
        status["message"] = "Automatic promotion secured."
        return status

    if not is_playoff_position(position):
        status["finished"] = True
        status["message"] = "Play-offs missed."
        return status

    status["qualified"] = True
    status["needs_playoffs"] = True

    if not status["generated"]:
        status["message"] = f"The board congratulates {club} on reaching the play-offs and wishes Jake well for the promotion campaign."
        return status

    semi_rows = get_playoff_matches(conn, challenge["challenge_id"])
    derby_semi_rows = [
        row for row in semi_rows
        if row["stage"] == "Semi-Final" and (row["home_team"] == club or row["away_team"] == club)
    ]

    if derby_semi_rows and all(row["played"] for row in derby_semi_rows):
        derby_match_no = derby_semi_rows[0]["match_no"]
        semi_winner = playoff_tie_winner(conn, challenge["challenge_id"], derby_match_no)
        if semi_winner and semi_winner != club:
            status["finished"] = True
            status["promoted"] = False
            status["exit_stage"] = "Semi-Final"
            status["message"] = f"{club} reached the play-offs but were knocked out in the semi-final."
            return status

    final = playoff_final_row(conn, challenge["challenge_id"])
    if final and final["played"]:
        winner = playoff_match_winner(final)
        status["finished"] = True
        status["promoted"] = winner == club
        status["exit_stage"] = "Final"
        status["message"] = (
            f"{club} won the play-off final and earned promotion."
            if status["promoted"]
            else f"{club} reached the play-off final but missed promotion."
        )
        return status

    status["message"] = "The board wishes Jake well in the play-off campaign. Promotion is now within reach."
    return status


def playoff_run_finished(conn, challenge):
    status = playoff_status(conn, challenge)
    return status["finished"]


def playoff_final_verdict(conn, challenge, final_position, final_points, record, board_conf):
    status = playoff_status(conn, challenge)
    club = challenge["club_or_nation"]

    if status["qualified"]:
        if status["promoted"]:
            return (
                f"Objective exceeded. {club} reached the play-offs and finished the job by winning promotion. "
                "The board wanted a top-six finish; Jake turned it into a promotion campaign."
            )
        if status["exit_stage"] == "Final":
            return (
                f"Objective achieved, but with Wembley heartbreak. {club} reached the play-offs and got all the way to the final, "
                "but promotion slipped away at the last hurdle. The board target was met, even if the ending hurts."
            )
        if status["exit_stage"] == "Semi-Final":
            return (
                f"Objective achieved, but the promotion push ended in the semi-final. {club} got into the play-offs, "
                "which met the board brief, but could not convert the opportunity into promotion."
            )

    return final_board_verdict(conn, challenge, final_position, final_points, record, board_conf)


def challenge_is_complete(conn, challenge):
    return playoff_run_finished(conn, challenge)


def final_position_row(table, club):
    for row in table:
        if row["team_name"] == club:
            return row
    return None


def player_leaders(conn, challenge_id):
    scorers = conn.execute("""
        SELECT player_name, COALESCE(SUM(goals), 0) AS total
        FROM player_match_events
        WHERE challenge_id=?
        GROUP BY player_name
        HAVING total > 0
        ORDER BY total DESC, player_name
    """, (challenge_id,)).fetchall()

    assisters = conn.execute("""
        SELECT player_name, COALESCE(SUM(assists), 0) AS total
        FROM player_match_events
        WHERE challenge_id=?
        GROUP BY player_name
        HAVING total > 0
        ORDER BY total DESC, player_name
    """, (challenge_id,)).fetchall()

    return scorers, assisters



def ordinal_position(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return "-"

    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")

    return f"{n}{suffix}"


def challenge_team_rating_context(conn, challenge):
    """Compare the managed club's ability against the rest of the challenge field."""
    club = challenge["club_or_nation"]
    challenge_id = challenge["challenge_id"]

    rows = conn.execute("""
        SELECT
            o.team_name,
            COALESCE(t.hidden_strength, t.attack, t.defence, 70) AS rating
        FROM opening_stats o
        LEFT JOIN teams t ON t.team_name = o.team_name
        WHERE o.challenge_id=?
    """, (challenge_id,)).fetchall()

    if not rows:
        return {
            "team_rating": None,
            "rating_rank": None,
            "field_size": None,
            "relative_label": "Unknown squad baseline",
        }

    ranked = sorted(
        [{"team_name": r["team_name"], "rating": int(r["rating"] or 70)} for r in rows],
        key=lambda x: x["rating"],
        reverse=True,
    )

    team_rating = None
    rating_rank = None
    for index, row in enumerate(ranked, start=1):
        if row["team_name"] == club:
            team_rating = row["rating"]
            rating_rank = index
            break

    field_size = len(ranked)

    if rating_rank is None:
        relative_label = "Unknown squad baseline"
    elif rating_rank <= 3:
        relative_label = "One of the strongest squads in the field"
    elif rating_rank <= 6:
        relative_label = "Play-off calibre squad on paper"
    elif rating_rank <= 12:
        relative_label = "Competitive but not dominant squad"
    else:
        relative_label = "Outside-favourite squad profile"

    return {
        "team_rating": team_rating,
        "rating_rank": rating_rank,
        "field_size": field_size,
        "relative_label": relative_label,
    }


def final_performance_context(conn, challenge, final_position, final_points, record):
    """Build the evidence used by the final board assessment."""
    target = int(challenge["target_position"] or 6)
    opening_position = challenge["opening_position"]
    opening_points = challenge["opening_points"]

    wins = int(record["wins"] or 0)
    draws = int(record["draws"] or 0)
    losses = int(record["losses"] or 0)
    played = wins + draws + losses
    points_under_manager = wins * 3 + draws
    ppg = round(points_under_manager / played, 2) if played else 0
    win_rate = int(round(100.0 * wins / played)) if played else 0

    movement = None
    if opening_position is not None and final_position is not None:
        movement = int(opening_position) - int(final_position)

    points_gained = None
    if opening_points is not None and final_points is not None:
        points_gained = int(final_points) - int(opening_points)

    table = league_table(conn, challenge["challenge_id"])
    target_row = next((r for r in table if int(r["position"]) == target), None)
    target_points = int(target_row["points"]) if target_row else None

    missed_by_points = None
    if final_position is not None and final_points is not None and target_points is not None and int(final_position) > target:
        missed_by_points = max(0, target_points - int(final_points))

    rating_context = challenge_team_rating_context(conn, challenge)
    rating_rank = rating_context["rating_rank"]

    objective_met = final_position is not None and int(final_position) <= target
    final_position_gap = int(final_position) - target if final_position is not None else None

    if final_position is None:
        objective_label = "Outcome pending"
        objective_note = "Final league position is unavailable."
    elif objective_met:
        objective_label = "Objective achieved"
        objective_note = f"Finished {ordinal_position(final_position)} against a target of {ordinal_position(target)}."
    elif final_position_gap == 1:
        objective_label = "Missed by one place"
        objective_note = (
            f"Finished {ordinal_position(final_position)} against a target of {ordinal_position(target)}"
            + (f", {missed_by_points} point(s) short." if missed_by_points is not None else ".")
        )
    else:
        objective_label = "Objective missed"
        objective_note = (
            f"Finished {ordinal_position(final_position)} against a target of {ordinal_position(target)}"
            + (f", {missed_by_points} point(s) short." if missed_by_points is not None else ".")
        )

    if played == 0:
        manager_label = "No posted record"
        manager_note = "No managed matches were posted."
    elif ppg >= 2.25 and win_rate >= 70:
        manager_label = "Excellent run-in"
        manager_note = f"{wins}W {draws}D {losses}L, {ppg} points per game and {win_rate}% win rate."
    elif ppg >= 2.0:
        manager_label = "Strong run-in"
        manager_note = f"{wins}W {draws}D {losses}L, {ppg} points per game."
    elif ppg >= 1.5:
        manager_label = "Competitive run-in"
        manager_note = f"{wins}W {draws}D {losses}L, {ppg} points per game."
    else:
        manager_label = "Underwhelming run-in"
        manager_note = f"{wins}W {draws}D {losses}L, {ppg} points per game."

    if rating_rank is not None:
        if rating_rank <= max(2, target - 3):
            difficulty_label = "High expectation squad"
            difficulty_note = (
                f"{challenge['club_or_nation']} ranked around {ordinal_position(rating_rank)} for squad strength, "
                "so the board expected the objective to be controlled."
            )
        elif rating_rank <= target:
            difficulty_label = "Target-level squad"
            difficulty_note = (
                f"{challenge['club_or_nation']} ranked around {ordinal_position(rating_rank)} for squad strength, "
                "so missing the target carries more responsibility."
            )
        else:
            difficulty_label = "Demanding chase"
            difficulty_note = (
                f"{challenge['club_or_nation']} ranked around {ordinal_position(rating_rank)} for squad strength, "
                f"so reaching {ordinal_position(target)} required overperformance."
            )
    else:
        difficulty_label = "Context limited"
        difficulty_note = "Squad-strength context is unavailable."

    if not objective_met and played and ppg >= 2.0 and final_position_gap is not None and final_position_gap <= 2:
        control_label = "Strong controllables"
        control_note = (
            "The objective was missed, but the manager delivered the kind of points return normally expected to move the table. "
            "This points more to the strength of the field and other results not dropping than to poor performance."
        )
    elif not objective_met and rating_rank is not None and rating_rank <= target and ppg < 2.0:
        control_label = "Below expectation"
        control_note = "The squad profile suggested the target was realistic, and the run-in did not produce enough sustained pressure."
    elif objective_met:
        control_label = "Job delivered"
        control_note = "The target was secured on the pitch."
    else:
        control_label = "Mixed controllables"
        control_note = "There were positives, but the run-in did not produce enough to overcome the table position."

    return {
        "target": target,
        "opening_position": opening_position,
        "opening_points": opening_points,
        "final_position": final_position,
        "final_points": final_points,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "played": played,
        "points_under_manager": points_under_manager,
        "ppg": ppg,
        "win_rate": win_rate,
        "movement": movement,
        "points_gained": points_gained,
        "target_points": target_points,
        "missed_by_points": missed_by_points,
        "final_position_gap": final_position_gap,
        "objective_met": objective_met,
        "rating_rank": rating_rank,
        "field_size": rating_context["field_size"],
        "team_rating": rating_context["team_rating"],
        "relative_label": rating_context["relative_label"],
        "objective_label": objective_label,
        "objective_note": objective_note,
        "manager_label": manager_label,
        "manager_note": manager_note,
        "difficulty_label": difficulty_label,
        "difficulty_note": difficulty_note,
        "control_label": control_label,
        "control_note": control_note,
    }


def final_board_confidence(conn, challenge, final_position, final_points, record, current_board_conf):
    """Final board confidence based on objective outcome and performance context.

    This deliberately avoids treating every missed objective as the same.
    A favourite missing a target is punished heavily; an underdog/mid-table side
    producing an excellent run and narrowly missing gets credit for the controllables.
    """
    status = playoff_status(conn, challenge)
    if status["qualified"]:
        if status["promoted"]:
            return 100
        if status["exit_stage"] in {"Final", "Semi-Final"}:
            return 85

    ctx = final_performance_context(conn, challenge, final_position, final_points, record)
    target = ctx["target"]

    if final_position is None:
        return max(0, min(100, int(current_board_conf or 0)))

    final_position = int(final_position)

    if final_position <= 2 and ("play" in (challenge["objective"] or "").lower() or target == 6):
        return 95

    if final_position <= target:
        return 85

    score = 38

    # Manager output.
    if ctx["ppg"] >= 2.4:
        score += 24
    elif ctx["ppg"] >= 2.25:
        score += 22
    elif ctx["ppg"] >= 2.0:
        score += 18
    elif ctx["ppg"] >= 1.75:
        score += 12
    elif ctx["ppg"] >= 1.5:
        score += 6
    elif ctx["ppg"] < 1.0 and ctx["played"]:
        score -= 8

    if ctx["win_rate"] >= 75:
        score += 8
    elif ctx["win_rate"] >= 60:
        score += 5
    elif ctx["win_rate"] < 35 and ctx["played"]:
        score -= 6

    # Table movement and points added from the starting position.
    if ctx["movement"] is not None:
        if ctx["movement"] > 0:
            score += min(10, ctx["movement"] * 2)
        elif ctx["movement"] < 0:
            score -= min(10, abs(ctx["movement"]) * 2)

    if ctx["points_gained"] is not None:
        if ctx["points_gained"] >= 18:
            score += 8
        elif ctx["points_gained"] >= 14:
            score += 6
        elif ctx["points_gained"] >= 10:
            score += 3

    # How narrowly the target was missed.
    gap_pos = ctx["final_position_gap"]
    gap_pts = ctx["missed_by_points"]

    if gap_pos == 1:
        score += 8
    elif gap_pos == 2:
        score += 4
    elif gap_pos is not None and gap_pos >= 5:
        score -= 8

    if gap_pts is not None:
        if gap_pts <= 1:
            score += 8
        elif gap_pts <= 3:
            score += 5
        elif gap_pts <= 6:
            score += 2

    # Relative squad strength / challenge difficulty.
    rating_rank = ctx["rating_rank"]
    if rating_rank is not None:
        if rating_rank <= max(2, target - 3):
            score -= 14
        elif rating_rank <= target:
            score -= 6
        else:
            score += min(10, (rating_rank - target) * 2)

    if ctx["opening_position"] is not None and int(ctx["opening_position"]) > target:
        score += min(8, int(ctx["opening_position"]) - target)

    # Missed objective caps/floors.
    if rating_rank is not None and rating_rank <= max(2, target - 3):
        score = min(score, 58)
    elif ctx["ppg"] >= 2.0 and gap_pos is not None and gap_pos <= 2 and (gap_pts is None or gap_pts <= 3):
        score = max(score, 72)
        score = min(score, 78)
    elif ctx["ppg"] >= 1.75 and gap_pos is not None and gap_pos <= 4:
        score = min(score, 68)
    else:
        score = min(score, 60)

    return max(0, min(100, int(round(score))))


def final_board_verdict(conn, challenge, final_position, final_points, record, board_conf):
    target = int(challenge["target_position"] or 6)
    objective = (challenge["objective"] or "").lower()
    ctx = final_performance_context(conn, challenge, final_position, final_points, record)

    wins = ctx["wins"]
    draws = ctx["draws"]
    losses = ctx["losses"]
    ppg = ctx["ppg"]

    if final_position is None:
        return "We cannot issue a final verdict because the final league position is unavailable."

    movement_text = ""
    if ctx["opening_position"] is not None:
        if ctx["movement"] and ctx["movement"] > 0:
            movement_text = f"Jake improved the side from {ordinal_position(ctx['opening_position'])} to {ordinal_position(final_position)}"
        elif ctx["movement"] and ctx["movement"] < 0:
            movement_text = f"Jake took the side from {ordinal_position(ctx['opening_position'])} to {ordinal_position(final_position)}"
        else:
            movement_text = f"Jake finished where he started, in {ordinal_position(final_position)}"

    points_text = f"adding {ctx['points_gained']} points" if ctx["points_gained"] is not None else ""
    record_text = f"with a record of {wins}W {draws}D {losses}L ({ppg} points per game)" if ctx["played"] else ""

    facts = ". ".join([part for part in [movement_text, points_text, record_text] if part])
    if facts:
        facts += "."

    is_playoff_objective = "play" in objective or target == 6

    if is_playoff_objective:
        if int(final_position) <= 2:
            return (
                "Outstanding. We asked for the play-offs and Jake delivered an automatic-promotion finish. "
                f"{facts} This is comfortably beyond expectation and significantly strengthens his reputation."
            )

        if int(final_position) <= 6:
            return (
                "Objective achieved. We asked for a play-off place and Jake got the club over the line. "
                f"{facts} The target was met when it mattered."
            )

        if int(final_position) <= 10:
            strong_narrow_miss = (
                ctx["ppg"] >= 2.0
                and ctx["final_position_gap"] is not None
                and ctx["final_position_gap"] <= 2
            )

            if strong_narrow_miss:
                return (
                    "Objective missed, but the performance deserves respect. We are disappointed that the play-offs were not reached, "
                    "but this was not a poor run-in or a collapse. "
                    f"{facts} Given the starting position, the squad baseline and the points return delivered, "
                    "this looks more like a strong managerial showing that was not quite enough in a competitive field. "
                    "Verdict: the objective was missed, but Jake handled the controllables well and leaves with credit."
                )

            if ctx["rating_rank"] is not None and ctx["rating_rank"] <= target:
                return (
                    "Objective missed. We expected this squad to be capable of reaching the play-offs, so the final position is frustrating. "
                    f"{facts} There were positives, but the target was within the squad's realistic range and it was not delivered."
                )

            return (
                "Objective missed, but not a collapse. We are frustrated that the play-offs were not reached, "
                "but the run-in still showed improvement and competitiveness. "
                f"{facts} Verdict: a respectable audition, but short of a successful challenge."
            )

        return (
            "Objective failed. We asked for a play-off push, but the team finished too far away from the target. "
            f"{facts} There may have been individual positives, but the final outcome falls short of the brief."
        )

    if "avoid relegation" in objective or "survival" in objective or target >= 20:
        if int(final_position) <= 12:
            return (
                "Objective exceeded. We asked for survival and Jake delivered comfort rather than chaos. "
                f"{facts} This is a strong stabilisation job."
            )
        if int(final_position) <= 21:
            return (
                "Objective achieved. Survival was the brief and survival was delivered. "
                f"{facts} It may not have been glamorous, but the job was done."
            )
        return (
            "Objective failed. The club needed survival and Jake could not keep them out of the relegation zone. "
            f"{facts} We would view this as a damaging outcome."
        )

    if "promotion" in objective or target <= 2:
        if int(final_position) == 1:
            return (
                "Objective exceeded. Jake did not just deliver promotion — he finished top. "
                f"{facts} This is a major reputation boost."
            )
        if int(final_position) <= target:
            return (
                "Objective achieved. The promotion target was met. "
                f"{facts} We view this as a successful challenge."
            )

        if ctx["rating_rank"] is not None and ctx["rating_rank"] <= target:
            return (
                "Objective failed. The promotion target was missed with a squad expected to compete at that level. "
                f"{facts} The performance does not fully excuse the outcome."
            )

        return (
            "Objective failed, but context matters. The promotion target was missed, but the run-in and squad baseline are part of the assessment. "
            f"{facts} We recognise the performance level, even though the final objective was not delivered."
        )

    if int(final_position) < target:
        return (
            f"Objective exceeded. We set a target of {ordinal_position(target)} and Jake finished {ordinal_position(final_position)}. "
            f"{facts} This is above expectation."
        )

    if int(final_position) == target:
        return (
            f"Objective achieved. Jake finished exactly on the target of {ordinal_position(target)}. "
            f"{facts} The brief was met."
        )

    return (
        f"Objective failed. The target was {ordinal_position(target)} and Jake finished {ordinal_position(final_position)}. "
        f"{facts} The final assessment accounts for performance level, squad strength and the size of the miss."
    )


def available_job_offers(conn):
    try:
        return conn.execute("""
            SELECT *
            FROM job_offers
            WHERE status IN ('Available', 'Scenario Needed')
            ORDER BY
                CASE status
                    WHEN 'Available' THEN 1
                    WHEN 'Scenario Needed' THEN 2
                    ELSE 3
                END,
                offer_id
        """).fetchall()
    except sqlite3.Error:
        return []


def current_challenge(conn):
    challenge = active_challenge(conn)
    if challenge:
        return challenge

    return conn.execute("""
        SELECT *
        FROM challenges
        ORDER BY
            CASE status
                WHEN 'Active' THEN 1
                WHEN 'Completed' THEN 2
                ELSE 3
            END,
            challenge_id DESC
        LIMIT 1
    """).fetchone()



def objective_outcome(challenge, position):
    if position is None:
        return {
            "status": "Pending",
            "class_name": "pending",
            "headline": "Challenge outcome pending",
            "message": "Final position is not available yet.",
        }

    objective = (challenge["objective"] or "").lower()
    target = challenge["target_position"] or 6

    if "play" in objective or target == 6:
        if position <= 2:
            return {
                "status": "Objective Exceeded",
                "class_name": "exceeded",
                "headline": "Objective exceeded",
                "message": "Automatic promotion was achieved despite the board only asking for the play-offs.",
            }
        if position <= 6:
            return {
                "status": "Objective Met",
                "class_name": "met",
                "headline": "Objective met",
                "message": "The play-off place was secured. The board brief was delivered.",
            }
        if position <= 10:
            return {
                "status": "Objective Failed",
                "class_name": "failed",
                "headline": "Objective missed, but the run-in was competitive",
                "message": "The play-offs were missed, but the final run-in still showed progress rather than a collapse.",
            }
        return {
            "status": "Objective Failed",
            "class_name": "failed",
            "headline": "Objective failed",
            "message": "The play-off push fell short and the final position was too far away from the target.",
        }

    if "avoid relegation" in objective or "survival" in objective or target >= 20:
        if position <= 12:
            return {
                "status": "Objective Exceeded",
                "class_name": "exceeded",
                "headline": "Objective exceeded",
                "message": "Survival was delivered comfortably, well beyond the board's minimum expectation.",
            }
        if position <= 21:
            return {
                "status": "Objective Met",
                "class_name": "met",
                "headline": "Objective met",
                "message": "Survival was secured. The board brief was delivered.",
            }
        return {
            "status": "Objective Failed",
            "class_name": "failed",
            "headline": "Objective failed",
            "message": "The team finished in the relegation zone.",
        }

    if "promotion" in objective or target <= 2:
        if position == 1:
            return {
                "status": "Objective Exceeded",
                "class_name": "exceeded",
                "headline": "Objective exceeded",
                "message": "The club finished top and exceeded the promotion brief.",
            }
        if position <= target:
            return {
                "status": "Objective Met",
                "class_name": "met",
                "headline": "Objective met",
                "message": "The promotion objective was achieved.",
            }
        return {
            "status": "Objective Failed",
            "class_name": "failed",
            "headline": "Objective failed",
            "message": "The promotion target was missed.",
        }

    if position < target:
        return {
            "status": "Objective Exceeded",
            "class_name": "exceeded",
            "headline": "Objective exceeded",
            "message": f"Finished above the target position of {target}.",
        }
    if position == target:
        return {
            "status": "Objective Met",
            "class_name": "met",
            "headline": "Objective met",
            "message": f"Finished on the target position of {target}.",
        }
    return {
        "status": "Objective Failed",
        "class_name": "failed",
        "headline": "Objective failed",
        "message": f"Finished below the target position of {target}.",
    }

def home_completion_status(challenge, current_position, current_points, games_remaining, board_assessment, gap_to_target=0):
    gap_to_target = int(gap_to_target or 0)
    games_remaining = int(games_remaining or 0)
    max_points_available = games_remaining * 3

    if games_remaining > 0:
        if current_position is not None and current_position <= (challenge["target_position"] or 6):
            message = "Currently inside the target places, but the job is not done yet. Keep the run going until the season is finished."
            return {
                "is_complete": False,
                "status": "In Target Places",
                "class_name": "in-progress",
                "headline": "Objective within reach",
                "message": message,
                "board_message": message,
            }

        if gap_to_target > max_points_available:
            message = (
                f"Objective is mathematically impossible. The team are {gap_to_target} points off the target "
                f"with {games_remaining} game(s) left and only {max_points_available} point(s) available."
            )
            return {
                "is_complete": False,
                "status": "Objective Impossible",
                "class_name": "failed",
                "headline": "Objective impossible",
                "message": message,
                "board_message": message,
            }

        if gap_to_target == max_points_available and gap_to_target > 0:
            message = "Objective is only just mathematically alive. A perfect finish is required, plus help elsewhere."
            return {
                "is_complete": False,
                "status": "High Pressure",
                "class_name": "at-risk",
                "headline": "No margin for error",
                "message": message,
                "board_message": message,
            }

        return {
            "is_complete": False,
            "status": "In Progress",
            "class_name": "in-progress",
            "headline": "Challenge in progress",
            "message": board_assessment,
            "board_message": board_assessment,
        }

    outcome = objective_outcome(challenge, current_position)
    final_bits = []
    if current_position is not None:
        final_bits.append(f"Final position: {current_position}")
    if current_points is not None:
        final_bits.append(f"Final points: {current_points}")

    final_suffix = " · ".join(final_bits)
    final_message = outcome["message"]
    if final_suffix:
        final_message = f"{final_message} {final_suffix}."

    return {
        "is_complete": True,
        "status": outcome["status"],
        "class_name": outcome["class_name"],
        "headline": outcome["headline"],
        "message": final_message,
        "board_message": final_message,
    }

def parse_position_value(value, fallback=None):
    if value is None:
        return fallback
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return int(digits) if digits else fallback


def source_challenge_for_new_job(conn):
    """Use the most recent completed challenge as the scenario source.
    Fall back to the first challenge if status data is unusual.
    """
    row = conn.execute("""
        SELECT challenge_id
        FROM challenges
        WHERE status='Completed'
        ORDER BY challenge_id DESC
        LIMIT 1
    """).fetchone()
    if row:
        return row["challenge_id"]

    row = conn.execute("""
        SELECT challenge_id
        FROM challenges
        ORDER BY challenge_id
        LIMIT 1
    """).fetchone()
    return row["challenge_id"] if row else None


def completed_challenge_count(conn):
    return conn.execute("""
        SELECT COUNT(*) AS c
        FROM challenges
        WHERE status='Completed'
    """).fetchone()["c"]


def reset_partial_challenge(conn, challenge_id):
    """Remove a partially-created challenge before retrying new challenge creation."""
    cleanup_challenge_everywhere(conn, challenge_id)


@app.context_processor
def inject_helpers():
    return {
        "team_initials": team_initials,
        "logo_for_team": logo_for_team,
        "result_logo_for_team": result_logo_for_team,
        "competition_logo_for": competition_logo_for,
        "competition_display_name": competition_display_name,
        "short_player_name": short_player_name,
    }



@app.context_processor
def inject_challenge_nav_state():
    """Expose lightweight challenge state to the layout.

    Table/Matches/Results are live-challenge navigation.
    Stats stays available until the challenge is explicitly marked Completed,
    so final run-in numbers can still be reviewed before locking the save.
    """
    if request.blueprint == 'challenge_archive_admin':
        # Archive rendering must not run connect() schema/season migrations.
        return {}
    complete_ready = False
    nav_active_challenge = False
    nav_has_completed_challenge = False
    nav_has_challenge = False
    nav_challenge_locked = False
    conn = None

    try:
        conn = connect()
        active = active_challenge(conn)
        nav_active_challenge = active is not None
        nav_has_completed_challenge = completed_challenge_count(conn) > 0

        challenge = current_challenge(conn)
        nav_has_challenge = challenge is not None

        if challenge:
            nav_challenge_locked = challenge["status"] == "Completed"
            complete_ready = challenge_complete_ready(conn, challenge) and not nav_challenge_locked
    except Exception:
        traceback.print_exc()
        complete_ready = False
        nav_active_challenge = False
        nav_has_completed_challenge = False
        nav_has_challenge = False
        nav_challenge_locked = False
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass

    return dict(
        complete_ready=complete_ready,
        nav_active_challenge=nav_active_challenge,
        nav_has_completed_challenge=nav_has_completed_challenge,
        nav_has_challenge=nav_has_challenge,
        nav_challenge_locked=nav_challenge_locked,
    )


@app.route("/")
def dashboard():
    conn = connect()
    challenge = current_challenge(conn)

    if not challenge:

        conn.close()

        flash("No challenge found yet.")

        return redirect(url_for("career"))
    archive_mode = challenge["status"] != "Active"
    table = league_table(conn, challenge["challenge_id"])
    players = human_dashboard_totals(conn, challenge["challenge_id"], challenge["club_or_nation"])
    regular_record = manager_record(conn, challenge["challenge_id"])
    record = combined_manager_record(conn, challenge)
    board_conf, board_assessment = latest_board(
        conn, challenge["challenge_id"], challenge["board_confidence_start"]
    )
    nxt = None if archive_mode else next_fixture(conn, challenge["challenge_id"], challenge["club_or_nation"])
    latest_round, latest_scores = latest_round_summary(conn, challenge["challenge_id"])
    current_position, current_points, gap = derby_context(table, challenge)
    remaining = games_remaining(conn, challenge["challenge_id"], challenge["club_or_nation"])
    playoff_info = playoff_status(conn, challenge)
    complete_ready = challenge_complete_ready(conn, challenge)
    board_conf, board_assessment, progress_context = contextual_progress_board_update(
        conn,
        challenge,
        current_position,
        current_points,
        record,
        board_conf,
        board_assessment,
        gap,
        remaining,
    )
    board_conf = calibrated_board_confidence(
        board_conf,
        current_position,
        challenge["target_position"],
        remaining,
        playoff_info if "playoff_info" in locals() else None,
    )
    home_status = home_completion_status(
        challenge,
        current_position,
        current_points,
        remaining,
        board_assessment,
        gap,
    )
    if playoff_info["qualified"] and not playoff_info["finished"]:
        home_status = {
            "is_complete": False,
            "status": "Play-Offs Qualified",
            "class_name": "met",
            "headline": "Play-off campaign active",
            "message": playoff_info["message"],
            "board_message": playoff_info["message"],
        }
    conn.close()

    return render_template(
        "dashboard.html",
        challenge=challenge,
        challenge_title=challenge_title(challenge),
        table=table,
        players=players,
        record=record,
        board_conf=board_conf,
        board_assessment=home_status["board_message"],
        home_status=home_status,
        playoff_info=playoff_info,
        complete_ready=complete_ready,
        archive_mode=archive_mode,
        next_fixture=nxt,
        latest_round=latest_round,
        latest_scores=latest_scores,
        current_position=current_position,
        current_points=current_points,
        gap=gap,
        games_remaining=remaining,
        progress_context=progress_context,
    )


@app.route("/post", methods=["GET", "POST"])
def post_match():
    conn = connect()
    ensure_player_match_event_role_columns(conn)
    ensure_current_human_players(conn)
    challenge = current_challenge(conn)

    if not challenge:

        conn.close()

        flash("No challenge found yet.")

        return redirect(url_for("career"))
    if challenge["status"] == "Completed" and request.method == "POST":
        conn.close()
        flash("This challenge is completed, so new results cannot be posted.")
        return redirect(url_for("matches_page") if "matches_page" in globals() else url_for("dashboard"))
    club = challenge["club_or_nation"]
    nxt = next_fixture(conn, challenge["challenge_id"], club)

    if not nxt:
        conn.close()
        flash("No remaining managed fixture.")
        return redirect(url_for("dashboard"))

    fixtures = round_fixtures(conn, challenge["challenge_id"], nxt["round"])
    integrity_issues = fixture_round_integrity_issues(conn, challenge["challenge_id"])
    if integrity_issues:
        conn.close()
        flash("Fixture errors detected: a club appears twice or is missing from a matchday. Repair fixtures before posting.")
        return redirect(url_for("fixture_integrity_admin"))

    if request.method == "POST":
        managed_hg = int(request.form.get("managed_hg", 0))
        managed_ag = int(request.form.get("managed_ag", 0))
        notes = request.form.get("notes", "")

        player_stats = {}
        for p in active_human_players(conn):
            key = p.replace(" ", "_").lower()
            appearance_role = request.form.get(f"{key}_appearance", "start")
            appearance = 1 if appearance_role in ("start", "sub") else 0
            started = 1 if appearance_role == "start" else 0
            substitute = 1 if appearance_role == "sub" else 0
            goals = int(request.form.get(f"{key}_goals", 0))
            assists = int(request.form.get(f"{key}_assists", 0))
            yellow_cards = int(request.form.get(f"{key}_yellow_cards", 0))
            red_cards = int(request.form.get(f"{key}_red_cards", 0))
            rating_raw = request.form.get(f"{key}_rating", "").strip()
            rating = float(rating_raw) if rating_raw else None

            player_stats[p] = {
                "appearance": appearance,
                "started": started,
                "substitute": substitute,
                "goals": goals,
                "assists": assists,
                "yellow_cards": yellow_cards,
                "red_cards": red_cards,
                "rating": rating,
            }

        computer_goals = int(request.form.get("computer_goals", 0))

        team_goals = managed_hg if nxt["home_team"] == club else managed_ag
        human_goals = sum(v["goals"] for v in player_stats.values())
        human_assists = sum(v["assists"] for v in player_stats.values())

        if human_goals + computer_goals != team_goals:
            flash(f"Invalid: human goals + computer goals must equal {club} goals ({team_goals}).")
            conn.close()
            return redirect(url_for("post_match"))

        if human_assists > team_goals:
            flash("Invalid: assists cannot exceed managed team goals.")
            conn.close()
            return redirect(url_for("post_match"))

        for player, stats in player_stats.items():
            if stats["appearance"] == 0:
                if stats["goals"] or stats["assists"] or stats["yellow_cards"] or stats["red_cards"] or stats["rating"]:
                    flash(f"Invalid: {player} has match events but appearance is 0.")
                    conn.close()
                    return redirect(url_for("post_match"))

        scores = default_sim_scores(conn, fixtures, int(nxt["match_no"]), managed_hg, managed_ag)

        with conn:
            for f in fixtures:
                match_no = int(f["match_no"])
                hg, ag = scores[match_no]
                source = "PES Result" if match_no == int(nxt["match_no"]) else "Simulated"
                row_notes = notes if source == "PES Result" else f"Round {nxt['round']} simulated"

                conn.execute("""
                    UPDATE fixtures
                    SET home_goals=?, away_goals=?, played=1, locked=1, source=?, notes=?
                    WHERE fixture_id=?
                """, (hg, ag, source, row_notes, f["fixture_id"]))

            conn.execute("DELETE FROM player_match_events WHERE fixture_id=?", (nxt["fixture_id"],))
            conn.execute("DELETE FROM computer_goal_events WHERE fixture_id=?", (nxt["fixture_id"],))

            for p, stats in player_stats.items():
                if (
                    stats["appearance"]
                    or stats["goals"]
                    or stats["assists"]
                    or stats["yellow_cards"]
                    or stats["red_cards"]
                    or stats["rating"]
                ):
                    conn.execute("""
                        INSERT INTO player_match_events(
                            challenge_id, round, fixture_id, player_name,
                            goals, assists, appearance, started, substitute, notes, yellow_cards, red_cards, rating
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        challenge["challenge_id"],
                        nxt["round"],
                        nxt["fixture_id"],
                        p,
                        stats["goals"],
                        stats["assists"],
                        stats["appearance"],
                        stats["started"],
                        stats["substitute"],
                        notes,
                        stats["yellow_cards"],
                        stats["red_cards"],
                        stats["rating"],
                    ))

            if computer_goals:
                conn.execute("""
                    INSERT INTO computer_goal_events(challenge_id, round, fixture_id, goals, notes)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    challenge["challenge_id"],
                    nxt["round"],
                    nxt["fixture_id"],
                    computer_goals,
                    "Computer-controlled player goal(s)",
                ))

            if nxt["home_team"] == club:
                result = "W" if managed_hg > managed_ag else "D" if managed_hg == managed_ag else "L"
            else:
                result = "W" if managed_ag > managed_hg else "D" if managed_hg == managed_ag else "L"

            table_now = league_table(conn, challenge["challenge_id"])
            pos, _, gap_to_target = derby_context(table_now, challenge)
            remaining_after = games_remaining(conn, challenge["challenge_id"], club)

            prev_board, _ = latest_board(conn, challenge["challenge_id"], challenge["board_confidence_start"])
            current_row = final_position_row(table_now, club)
            current_points_after = current_row["points"] if current_row else None

            new_board, assessment = contextual_board_after_result(
                conn,
                challenge,
                prev_board,
                result,
                pos,
                current_points_after,
                gap_to_target,
                remaining_after,
            )

            conn.execute("""
                INSERT INTO board_log(challenge_id, round, board_confidence, assessment, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, (challenge["challenge_id"], nxt["round"], new_board, assessment))

        conn.close()
        flash("Matchday posted. Around the Grounds were simulated automatically.")
        return redirect(url_for("dashboard"))

    roster = active_human_players(conn)
    conn.close()

    return render_template(
        "post.html",
        challenge=challenge,
        next_fixture=nxt,
        players=roster,
    )


@app.route("/history")
def history():
    conn = connect()
    challenge = active_challenge(conn)
    rounds = conn.execute("""
        SELECT DISTINCT round
        FROM fixtures
        WHERE challenge_id=? AND played=1
        ORDER BY round
    """, (challenge["challenge_id"],)).fetchall()

    selected = request.args.get("round")
    if selected is None and rounds:
        selected = rounds[-1]["round"]

    fixtures = []
    if selected:
        fixtures = conn.execute("""
            SELECT match_no, home_team, away_team, home_goals, away_goals, source, notes
            FROM fixtures
            WHERE challenge_id=? AND round=?
            ORDER BY match_no
        """, (challenge["challenge_id"], selected)).fetchall()

    conn.close()
    return render_template(
        "history.html",
        rounds=rounds,
        selected=str(selected) if selected else None,
        fixtures=fixtures,
    )


@app.route("/career")
def career():
    conn = connect()
    cards = challenge_cards(conn)
    players = career_player_totals(conn)
    active = active_challenge(conn)
    conn.close()

    return render_template(
        "career.html",
        cards=cards,
        players=players,
        active=active,
    )


@app.route("/challenge/<challenge_id>")
def challenge_archive(challenge_id):
    conn = connect()
    challenge = conn.execute(
        "SELECT * FROM challenges WHERE challenge_id=?",
        (challenge_id,),
    ).fetchone()

    if not challenge:
        conn.close()
        flash("Challenge not found.")
        return redirect(url_for("career"))

    archive_mode = challenge["status"] != "Active"
    table = league_table(conn, challenge["challenge_id"])
    players = human_dashboard_totals(conn, challenge["challenge_id"], challenge["club_or_nation"])
    record = combined_manager_record(conn, challenge)

    board_conf, board_assessment = latest_board(
        conn,
        challenge["challenge_id"],
        challenge["board_confidence_start"],
    )

    nxt = None if archive_mode else next_fixture(
        conn,
        challenge["challenge_id"],
        challenge["club_or_nation"],
    )

    latest_round, latest_scores = latest_round_summary(conn, challenge["challenge_id"])
    current_position, current_points, gap = derby_context(table, challenge)
    remaining = games_remaining(conn, challenge["challenge_id"], challenge["club_or_nation"])
    playoff_info = playoff_status(conn, challenge)
    complete_ready = challenge_complete_ready(conn, challenge) and not archive_mode

    # Use exactly the same contextual calculation as the live dashboard
    # and Manager page so archived/direct challenge URLs cannot show a stale
    # board percentage from board_log.
    board_conf, board_assessment, progress_context = contextual_progress_board_update(
        conn,
        challenge,
        current_position,
        current_points,
        record,
        board_conf,
        board_assessment,
        gap,
        remaining,
    )

    board_conf = calibrated_board_confidence(
        board_conf,
        current_position,
        challenge["target_position"],
        remaining,
        playoff_info,
    )

    home_status = home_completion_status(
        challenge,
        current_position,
        current_points,
        remaining,
        board_assessment,
        gap,
    )

    if playoff_info["qualified"] and not playoff_info["finished"]:
        home_status = {
            "is_complete": False,
            "status": "Play-Offs Qualified",
            "class_name": "met",
            "headline": "Play-off campaign active",
            "message": playoff_info["message"],
            "board_message": playoff_info["message"],
        }

    conn.close()

    return render_template(
        "dashboard.html",
        challenge=challenge,
        challenge_title=challenge_title(challenge),
        table=table,
        players=players,
        record=record,
        board_conf=board_conf,
        board_assessment=home_status["board_message"],
        home_status=home_status,
        playoff_info=playoff_info,
        complete_ready=complete_ready,
        next_fixture=nxt,
        latest_round=latest_round,
        latest_scores=latest_scores,
        current_position=current_position,
        current_points=current_points,
        gap=gap,
        games_remaining=remaining,
        archive_mode=archive_mode,
        progress_context=progress_context,
    )


@app.route("/jobs")
def jobs():
    conn = connect()

    try:
        active = active_challenge(conn)
        completed_count = completed_challenge_count(conn)
        fk_issues = foreign_key_problem_summary(conn)
        jobs_locked = active is not None or completed_count == 0

        offers = []
        if not jobs_locked:
            offers = conn.execute("""
                SELECT *
                FROM job_offers
                ORDER BY
                    CASE status
                        WHEN 'Available' THEN 1
                        WHEN 'Scenario Needed' THEN 2
                        WHEN 'Accepted' THEN 3
                        ELSE 4
                    END,
                    offer_id
            """).fetchall()

        return render_template(
            "jobs.html",
            active=active,
            offers=offers,
            jobs_locked=jobs_locked,
            completed_count=completed_count,
            fk_issues=fk_issues,
        )
    except Exception as exc:
        traceback.print_exc()
        return render_template(
            "jobs_error.html",
            error=str(exc),
        ), 500
    finally:
        conn.close()


@app.route("/jobs/accept/<int:offer_id>", methods=["POST"])
def accept_job_offer(offer_id):
    conn = connect()

    active = active_challenge(conn)
    if active is not None:
        conn.close()
        flash("Jobs unlock once the current challenge is completed.")
        return redirect(url_for("jobs"))

    if completed_challenge_count(conn) == 0:
        conn.close()
        flash("Complete the current challenge before starting a new one.")
        return redirect(url_for("jobs"))

    offer = conn.execute(
        "SELECT * FROM job_offers WHERE offer_id=?",
        (offer_id,),
    ).fetchone()

    if not offer:
        conn.close()
        flash("Job offer not found.")
        return redirect(url_for("jobs"))

    if offer["status"] != "Available":
        conn.close()
        flash("This job is not currently available to auto-start.")
        return redirect(url_for("jobs"))

    try:
        new_id = clone_championship_challenge_from_offer(conn, offer)
    except ValueError as exc:
        conn.rollback()
        conn.close()
        flash(str(exc))
        return redirect(url_for("jobs"))
    except sqlite3.Error as exc:
        conn.rollback()
        conn.close()
        flash(f"Database error while starting the new challenge: {exc}")
        return redirect(url_for("jobs"))
    except Exception:
        traceback.print_exc()
        conn.rollback()
        conn.close()
        flash("Unexpected error while starting the new challenge. The save has not been changed.")
        return redirect(url_for("jobs"))

    conn.close()
    flash(f"{new_id} created and set as the active challenge.")
    return redirect(url_for("dashboard"))


@app.route("/table")
def league_table_page():
    conn = connect()
    challenge = current_challenge(conn)

    if not challenge:

        conn.close()

        flash("No challenge found yet.")

        return redirect(url_for("career"))
    table = league_table(conn, challenge["challenge_id"])
    current_position, current_points, gap = derby_context(table, challenge)
    remaining = games_remaining(conn, challenge["challenge_id"], challenge["club_or_nation"])
    latest_round, latest_scores = latest_round_summary(conn, challenge["challenge_id"])
    conn.close()

    return render_template(
        "league_table.html",
        challenge=challenge,
        table=table,
        current_position=current_position,
        current_points=current_points,
        gap=gap,
        games_remaining=remaining,
        latest_round=latest_round,
        latest_scores=latest_scores,
    )


@app.route("/around")
@app.route("/results")
def around_the_grounds_page():
    conn = connect()
    challenge = current_challenge(conn)

    if not challenge:

        conn.close()

        flash("No challenge found yet.")

        return redirect(url_for("career"))
    rounds = all_played_rounds(conn, challenge["challenge_id"])
    conn.close()

    return render_template(
        "around.html",
        challenge=challenge,
        rounds=rounds,
    )


@app.route("/manager")
def manager_dashboard_page():
    conn = connect()
    challenge = current_challenge(conn)

    if not challenge:

        conn.close()

        flash("No challenge found yet.")

        return redirect(url_for("career"))
    table = league_table(conn, challenge["challenge_id"])
    record = manager_record(conn, challenge["challenge_id"])
    board_conf, board_assessment = latest_board(
        conn,
        challenge["challenge_id"],
        challenge["board_confidence_start"],
    )
    current_position, current_points, gap = derby_context(table, challenge)
    remaining = games_remaining(conn, challenge["challenge_id"], challenge["club_or_nation"])
    playoff_info = playoff_status(conn, challenge)
    board_conf, board_assessment, progress_context = contextual_progress_board_update(
        conn,
        challenge,
        current_position,
        current_points,
        record,
        board_conf,
        board_assessment,
        gap,
        remaining,
    )
    board_conf = calibrated_board_confidence(
        board_conf,
        current_position,
        challenge["target_position"],
        remaining,
        playoff_info,
    )
    manager_status = home_completion_status(challenge, current_position, current_points, remaining, board_assessment, gap)
    board_assessment = manager_status["board_message"]
    nxt = next_fixture(conn, challenge["challenge_id"], challenge["club_or_nation"])
    conn.close()

    return render_template(
        "manager.html",
        challenge=challenge,
        record=record,
        board_conf=board_conf,
        board_assessment=board_assessment,
        current_position=current_position,
        current_points=current_points,
        gap=gap,
        games_remaining=remaining,
        next_fixture=nxt,
        progress_context=progress_context,
    )


@app.route("/players")
def player_stats_page():
    conn = connect()
    challenge = current_challenge(conn)

    if not challenge:

        conn.close()

        flash("No challenge found yet.")

        return redirect(url_for("career"))
    # Only the Stats page filters by roster status. Career/history totals retain all players.
    # ?show_inactive=1 exposes archived players without changing saved events.
    show_inactive = request.args.get("show_inactive") == "1"
    all_players = human_dashboard_totals(conn, challenge["challenge_id"])
    active_names = set(active_human_players(conn))
    players = all_players if show_inactive else [
        player for player in all_players if player["player_name"] in active_names
    ]

    stats_summary = {
        "apps": sum((p["appearances"] or 0) for p in players),
        "starts": sum((p["starts"] or 0) if "starts" in p.keys() else (p["appearances"] or 0) for p in players),
        "sub_apps": sum((p["sub_apps"] or 0) if "sub_apps" in p.keys() else 0 for p in players),
        "goals": sum((p["goals"] or 0) for p in players),
        "assists": sum((p["assists"] or 0) for p in players),
        "yellow_cards": sum((p["yellow_cards"] or 0) for p in players),
        "red_cards": sum((p["red_cards"] or 0) for p in players),
    }

    stats_source = stats_source_summary(conn, challenge)

    conn.close()

    return render_template(
        "players.html",
        body_class="stats-page",
        challenge=challenge,
        players=players,
        stats_summary=stats_summary,
        stats_source=stats_source,
        show_inactive=show_inactive,
    )


@app.route("/matches")
def matches_page():
    conn = connect()
    challenge = current_challenge(conn)

    if not challenge:

        conn.close()

        flash("No challenge found yet.")

        return redirect(url_for("career"))
    results = managed_results(conn, challenge["challenge_id"], challenge["club_or_nation"])
    upcoming = upcoming_managed_fixtures(conn, challenge["challenge_id"], challenge["club_or_nation"])
    conn.close()

    return render_template(
        "matches.html",
        challenge=challenge,
        results=results,
        upcoming=upcoming,
    )





@app.route("/admin/start-middlesbrough", methods=["GET", "POST"])
def start_middlesbrough_2021():
    conn = connect()
    active = active_challenge(conn)
    existing = conn.execute("""
        SELECT *
        FROM challenges
        WHERE club_or_nation='Middlesbrough'
          AND opening_position=9
          AND opening_points=56
          AND start_round=38
          AND final_round=46
        ORDER BY challenge_id DESC
        LIMIT 1
    """).fetchone()

    if request.method == "POST":
        try:
            challenge_id, created = create_middlesbrough_2021_challenge(conn)
        except ValueError as exc:
            conn.close()
            flash(str(exc))
            return redirect(url_for("start_middlesbrough_2021"))
        except sqlite3.Error as exc:
            conn.close()
            flash(f"Could not create Middlesbrough challenge: {exc}")
            return redirect(url_for("start_middlesbrough_2021"))

        conn.close()
        if created:
            flash(
                f"{challenge_id} started: Middlesbrough Career Season 2, 9th on 56 points, "
                "six points off the play-offs with eight games remaining."
            )
        else:
            flash(f"{challenge_id} is already the active Middlesbrough challenge.")
        return redirect(url_for("dashboard"))

    completed_count = completed_challenge_count(conn)
    conn.close()

    return render_template(
        "admin_start_middlesbrough.html",
        active=active,
        existing=existing,
        completed_count=completed_count,
        opening_position=9,
        opening_points=56,
        target_position=6,
        target_points=62,
        points_from_target=6,
        managed_fixtures=MIDDLESBROUGH_2021_MANAGED_FIXTURES,
    )


@app.route("/admin/reset-derby", methods=["GET", "POST"])
def reset_derby():
    if request.method == "POST":
        conn = connect()
        reset_derby_challenge_data(conn)
        conn.close()
        flash("Derby challenge reset. CH001 is active again with no posted results.")
        return redirect(url_for("dashboard"))

    return render_template(
        "reset_derby.html",
        opening_stats=DERBY_RESET_OPENING_STATS,
        fixtures=DERBY_RESET_FIXTURES,
    )


def managed_fixture_order(conn, challenge_id, club):
    return conn.execute("""
        SELECT * FROM fixtures
        WHERE challenge_id=? AND (home_team=? OR away_team=?)
        ORDER BY round, match_no
    """, (challenge_id, club, club)).fetchall()


def fixture_order_opponent(row, club):
    return row["away_team"] if row["home_team"] == club else row["home_team"]


def fixture_round_integrity_issues(conn, challenge_id):
    """Each round must contain every starting club exactly once."""
    names = {r["team_name"] for r in conn.execute(
        "SELECT team_name FROM opening_stats WHERE challenge_id=?", (challenge_id,)
    ).fetchall()}
    issues = []
    if not names or len(names) % 2:
        return [{"round": None, "missing": [], "duplicated": [], "reason": "Invalid competition club list"}]
    round_rows = conn.execute(
        "SELECT DISTINCT round FROM fixtures WHERE challenge_id=? ORDER BY round",
        (challenge_id,),
    ).fetchall()
    for entry in round_rows:
        round_no = entry["round"]
        fixtures = round_fixtures(conn, challenge_id, round_no)
        count = Counter(name for f in fixtures for name in (f["home_team"], f["away_team"]))
        missing = sorted(names - count.keys())
        duplicated = sorted(name for name, amount in count.items() if amount > 1)
        unknown = sorted(count.keys() - names)
        if missing or duplicated or unknown or len(fixtures) * 2 != len(names):
            issues.append({
                "round": round_no, "missing": missing,
                "duplicated": duplicated, "unknown": unknown,
                "fixtures": fixtures,
                "reason": "A matchday must contain every club exactly once",
            })
    return issues


def middlesbrough_fixture_repair_plan(conn, challenge):
    """Plan only one-for-one non-managed swaps; never rewrite played PES games."""
    if challenge is None or challenge["challenge_id"] != "CH002" or challenge["club_or_nation"] != "Middlesbrough":
        return [], "The repair is limited to the Middlesbrough CH002 challenge."

    challenge_id = challenge["challenge_id"]
    rounds = conn.execute(
        "SELECT DISTINCT round FROM fixtures WHERE challenge_id=? ORDER BY round",
        (challenge_id,),
    ).fetchall()
    expected_rounds = list(range(39, 47))
    if [r["round"] for r in rounds] != expected_rounds:
        return [], "Unexpected rounds: no changes made."

    issues = fixture_round_integrity_issues(conn, challenge_id)
    if not issues:
        return [], None
    if len(issues) != len(expected_rounds) or [r["round"] for r in issues] != expected_rounds:
        return [], "The fixture issues do not match the known eight-round pattern. Nothing was changed."

    # This one-time repair must run immediately after the first real match.
    played = conn.execute(
        "SELECT round, home_team, away_team, source, home_goals, away_goals FROM fixtures "
        "WHERE challenge_id=? AND played=1 ORDER BY round, match_no", (challenge_id,),
    ).fetchall()
    if len(played) != 12 or any(r["round"] != 39 for r in played):
        return [], "The save has changed since the export. Export a new archive before repairing."

    managed = [r for r in played if "Middlesbrough" in (r["home_team"], r["away_team"])]
    if (len(managed) != 1 or managed[0]["home_team"] != "Middlesbrough"
            or managed[0]["away_team"] != "Wigan Athletic" or managed[0]["home_goals"] != 2
            or managed[0]["away_goals"] != 0 or managed[0]["source"] != "PES Result"):
        return [], "The recorded Middlesbrough result differs from the verified export. Nothing was changed."

    plan = []
    for issue in issues:
        missing, duplicate = issue["missing"], issue["duplicated"]
        if issue["unknown"] or len(missing) != 1 or len(duplicate) != 1:
            return [], "One or more rounds have unexpected fixture errors."
        repeated = duplicate[0]
        fixtures = issue["fixtures"]
        managed_rows = [r for r in fixtures if "Middlesbrough" in (r["home_team"], r["away_team"])]
        if len(managed_rows) != 1 or repeated not in (managed_rows[0]["home_team"], managed_rows[0]["away_team"]):
            return [], "A round is missing its managed fixture or has an unexpected duplicate."

        candidates = [f for f in fixtures
                      if f["fixture_id"] != managed_rows[0]["fixture_id"]
                      and repeated in (f["home_team"], f["away_team"])]
        if len(candidates) != 1:
            return [], "Could not uniquely identify a non-managed fixture to correct."
        row = candidates[0]
        if row["round"] == 39:
            if row["played"] != 1 or row["source"] != "Simulated":
                return [], "The completed fixture is not a simulation; manual review required."
        elif row["played"]:
            return [], "A future fixture has already been played. No changes made."

        home = missing[0] if row["home_team"] == repeated else row["home_team"]
        away = missing[0] if row["away_team"] == repeated else row["away_team"]
        plan.append({
            "round": row["round"], "fixture_id": row["fixture_id"],
            "old_home": row["home_team"], "old_away": row["away_team"],
            "home": home, "away": away, "played": bool(row["played"]),
        })
    return plan, None


@app.route("/admin/fixture-integrity", methods=["GET", "POST"])
def fixture_integrity_admin():
    conn = connect()
    challenge = active_challenge(conn)
    plan, problem = middlesbrough_fixture_repair_plan(conn, challenge)
    issues = fixture_round_integrity_issues(conn, challenge["challenge_id"]) if challenge else []
    if request.method == "POST":
        if problem or not plan or request.form.get("confirm") != "REPAIR FIXTURES":
            conn.close()
            flash(problem or "Repair not confirmed. No changes made.")
            return redirect(url_for("fixture_integrity_admin"))
        if request.form.get("challenge_id") != challenge["challenge_id"]:
            conn.close()
            flash("The active challenge has changed. No changes made.")
            return redirect(url_for("fixture_integrity_admin"))
        try:
            # Save a pre-repair database copy before any fixture is modified.
            backup_dir = DB_PATH.parent / "fixture_repair_backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(DB_PATH, backup_dir / make_backup_filename("pre_fixture_repair"))
            with conn:
                for change in plan:
                    conn.execute(
                        "UPDATE fixtures SET home_team=?, away_team=? "
                        "WHERE challenge_id=? AND fixture_id=?",
                        (change["home"], change["away"], challenge["challenge_id"], change["fixture_id"]),
                    )
                    if change["played"]:
                        # Never assign a score simulated for Wigan to Bournemouth:
                        # rerun just this computer fixture; PES 2-0 stays untouched.
                        conn.execute(
                            "UPDATE fixtures SET played=0, home_goals=NULL, away_goals=NULL "
                            "WHERE challenge_id=? AND fixture_id=?",
                            (challenge["challenge_id"], change["fixture_id"]),
                        )
                        hg, ag = simulate_scoreline(conn, challenge["challenge_id"], change["home"], change["away"])
                        conn.execute(
                            "UPDATE fixtures SET played=1, home_goals=?, away_goals=?, "
                            "notes=? WHERE challenge_id=? AND fixture_id=?",
                            (hg, ag, "Round 39 simulation rerun after opponent correction",
                             challenge["challenge_id"], change["fixture_id"]),
                        )

                if fixture_round_integrity_issues(conn, challenge["challenge_id"]):
                    raise ValueError("Fixture validation failed. Rolled back all changes.")

                # Update the latest board assessment to reflect the corrected table.
                original_board = conn.execute(
                    "SELECT board_confidence FROM board_log "
                    "WHERE challenge_id=? AND round<39 ORDER BY round DESC, log_id DESC LIMIT 1",
                    (challenge["challenge_id"],),
                ).fetchone()
                previous_conf = (original_board["board_confidence"] if original_board
                                 else challenge["board_confidence_start"])
                table_now = league_table(conn, challenge["challenge_id"])
                position, _, gap_to_target = derby_context(table_now, challenge)
                remaining_after = games_remaining(conn, challenge["challenge_id"], challenge["club_or_nation"])
                current_row = final_position_row(table_now, challenge["club_or_nation"])
                points = current_row["points"] if current_row else None
                new_conf, assessment = contextual_board_after_result(
                    conn, challenge, previous_conf, "W", position, points,
                    gap_to_target, remaining_after,
                )
                conn.execute(
                    "UPDATE board_log SET board_confidence=?, assessment=? "
                    "WHERE challenge_id=? AND round=39",
                    (new_conf, assessment, challenge["challenge_id"]),
                )
        except Exception as exc:
            conn.close()
            flash(f"Fixture repair was cancelled: {exc}")
            return redirect(url_for("fixture_integrity_admin"))
        conn.close()
        flash("All eight rounds repaired. Middlesbrough 2-0 Wigan and player statistics are preserved.")
        return redirect(url_for("fixture_integrity_admin"))

    conn.close()
    return render_template(
        "admin_fixture_integrity.html", challenge=challenge, issues=issues,
        plan=plan, problem=problem,
    )


@app.route("/admin/fixture-order", methods=["GET", "POST"])
def fixture_order():
    conn = connect()
    challenge = active_challenge(conn)
    if not challenge:
        conn.close()
        flash("Fixture order can only be edited for an active challenge.")
        return redirect(url_for("career"))

    challenge_id = challenge["challenge_id"]
    club = challenge["club_or_nation"]
    managed = managed_fixture_order(conn, challenge_id, club)
    if not managed:
        conn.close()
        flash(f"No {club} fixtures found to edit.")
        return redirect(url_for("matches_page"))

    opponents = [fixture_order_opponent(row, club) for row in managed]
    expected = set(opponents)
    duplicates = sorted({team for team in opponents if opponents.count(team) > 1})

    if request.method == "POST":
        if request.form.get("challenge_id", "") != challenge_id:
            conn.close()
            flash("The active challenge changed. Reload the fixture editor before saving.")
            return redirect(url_for("fixture_order"))

        if any(row["played"] for row in managed):
            conn.close()
            flash(f"Fixture order cannot be changed after {club} results have been posted.")
            return redirect(url_for("fixture_order"))

        slots = []
        for idx in range(len(managed)):
            opponent = request.form.get(f"opponent_{idx}", "").strip()
            venue = request.form.get(f"venue_{idx}", "").strip().upper()
            if not opponent or venue not in {"H", "A"}:
                conn.close()
                flash("Every fixture needs a valid opponent and Home/Away selection.")
                return redirect(url_for("fixture_order"))
            slots.append((opponent, venue))

        selected = [opponent for opponent, _ in slots]
        if (duplicates or len(expected) != len(managed)
                or set(selected) != expected or len(set(selected)) != len(selected)):
            conn.close()
            flash("Fixture order not saved. Each original opponent must appear exactly once.")
            return redirect(url_for("fixture_order"))

        # Preserve full-round integrity when an opponent is moved into a new slot.
        # A move must swap the displaced opponent into the other fixture of that round.
        current_issues = fixture_round_integrity_issues(conn, challenge_id)
        if current_issues:
            conn.close()
            flash("Cannot reorder fixtures until existing duplicate/missing clubs are corrected.")
            return redirect(url_for("fixture_integrity_admin"))

        updates = []
        for row, (opponent, venue) in zip(managed, slots):
            original = fixture_order_opponent(row, club)
            home, away = (club, opponent) if venue == "H" else (opponent, club)
            updates.append((row["fixture_id"], home, away))
            if opponent != original:
                others = [
                    f for f in round_fixtures(conn, challenge_id, row["round"])
                    if f["fixture_id"] != row["fixture_id"]
                    and opponent in (f["home_team"], f["away_team"])
                    and club not in (f["home_team"], f["away_team"])
                ]
                if len(others) != 1 or others[0]["played"]:
                    conn.close()
                    flash(f"Cannot safely swap {opponent} in MD{row['round']}. No fixtures were changed.")
                    return redirect(url_for("fixture_order"))
                other = others[0]
                other_home = original if other["home_team"] == opponent else other["home_team"]
                other_away = original if other["away_team"] == opponent else other["away_team"]
                updates.append((other["fixture_id"], other_home, other_away))

        try:
            with conn:
                for fixture_id, home, away in updates:
                    conn.execute("""
                        UPDATE fixtures SET home_team=?, away_team=?
                        WHERE fixture_id=? AND challenge_id=? AND played=0
                    """, (home, away, fixture_id, challenge_id))
                if fixture_round_integrity_issues(conn, challenge_id):
                    raise ValueError("Fixture order would create repeated or missing clubs.")
        except (ValueError, sqlite3.Error) as exc:
            conn.close()
            flash(f"Fixture order not saved: {exc}")
            return redirect(url_for("fixture_order"))
        conn.close()
        flash(f"{club} fixture order updated; every club still plays exactly once per round.")
        return redirect(url_for("matches_page"))

    conn.close()
    return render_template(
        "fixture_order.html", challenge=challenge, fixtures=managed,
        opponents=sorted(expected), duplicate_opponents=duplicates,
        missing_opponents=[],
    )


@app.route("/admin/human-players/apply", methods=["POST", "GET"])
def apply_human_players_admin():
    conn = connect()
    with conn:
        ensure_current_human_players(conn)
    conn.close()

    flash("Human player roster updated. Tim Rees is now available for result posting.")
    return redirect(url_for("post_match"))



@app.route("/admin/team-ratings")
def team_ratings_admin():
    conn = connect()
    ensure_team_rating_sources_table(conn)

    ratings = conn.execute("""
        SELECT
            t.team_name,
            t.hidden_strength,
            t.attack,
            t.defence,
            r.rating_source,
            r.source_url,
            r.pes_name,
            r.overall,
            r.midfield,
            r.speed,
            r.strength,
            r.notes
        FROM teams t
        LEFT JOIN team_rating_sources r ON r.team_name=t.team_name
        ORDER BY t.team_name
    """).fetchall()

    conn.close()

    return render_template(
        "team_ratings.html",
        ratings=ratings,
    )


@app.route("/admin/team-ratings/apply", methods=["POST"])
def apply_team_ratings_admin():
    conn = connect()
    with conn:
        apply_team_rating_sources(conn)
    conn.close()

    flash("PESMaster/challenge ratings applied to the simulation teams table.")
    return redirect(url_for("team_ratings_admin"))



@app.route("/admin/backup")
def admin_backup():
    return render_template("backup.html", db_path=str(DB_PATH))


@app.route("/export-save")
def export_save():
    if not DB_PATH.exists():
        flash("No database file found to export.")
        return redirect(url_for("admin_backup"))

    return send_file(
        DB_PATH,
        as_attachment=True,
        download_name=make_backup_filename(),
        mimetype="application/octet-stream",
    )


@app.route("/import-save", methods=["GET", "POST"])
def import_save():
    if request.method == "GET":
        return render_template("import_save.html", db_path=str(DB_PATH))

    uploaded = request.files.get("save_file")
    if not uploaded or not uploaded.filename:
        flash("Choose a .db save file to import.")
        return redirect(url_for("import_save"))

    if not uploaded.filename.lower().endswith(".db"):
        flash("Import cancelled. Please upload a .db SQLite save file.")
        return redirect(url_for("import_save"))

    backup_dir = APP_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)

    if DB_PATH.exists():
        safety_backup = backup_dir / make_backup_filename("pre_import_backup")
        shutil.copy2(DB_PATH, safety_backup)

    temp_path = backup_dir / make_backup_filename("uploaded_save")
    uploaded.save(temp_path)

    try:
        test_conn = sqlite3.connect(temp_path)
        required_tables = {"challenges", "fixtures", "opening_stats", "player_match_events"}
        found_tables = {
            row[0]
            for row in test_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        test_conn.close()

        missing = required_tables - found_tables
        if missing:
            temp_path.unlink(missing_ok=True)
            flash("Import cancelled. Save file is missing required tables.")
            return redirect(url_for("import_save"))

        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(temp_path, DB_PATH)
        flash("Save imported successfully. The live database has been restored.")
        return redirect(url_for("dashboard"))
    except Exception as exc:
        flash(f"Import failed: {exc}")
        return redirect(url_for("import_save"))


@app.route("/playoffs")
def playoffs_page():
    conn = connect()
    challenge = current_challenge(conn)

    if not challenge:
        conn.close()
        flash("No challenge found.")
        return redirect(url_for("dashboard"))

    table = league_table(conn, challenge["challenge_id"])
    status = playoff_status(conn, challenge)
    matches = playoff_matches_with_events(conn, challenge["challenge_id"])
    next_match = next_managed_playoff_match(conn, challenge)
    final = playoff_final_row(conn, challenge["challenge_id"])
    conn.close()

    return render_template(
        "playoffs.html",
        body_class="playoffs-page",
        challenge=challenge,
        table=table,
        status=status,
        matches=matches,
        next_match=next_match,
        final=final,
    )


@app.route("/playoffs/generate", methods=["POST"])
def generate_playoffs_route():
    conn = connect()
    challenge = active_challenge(conn) or current_challenge(conn)

    if not challenge:
        conn.close()
        flash("No challenge found.")
        return redirect(url_for("dashboard"))

    status = playoff_status(conn, challenge)
    if not status["qualified"]:
        conn.close()
        flash(f"Play-offs can only be generated once the regular season is complete and {challenge['club_or_nation']} finish 3rd-6th.")
        return redirect(url_for("playoffs_page"))

    try:
        created = generate_playoff_fixtures(conn, challenge)
        if created:
            flash(f"Play-off semi-final fixtures generated. The other semi-final will progress after each {challenge['club_or_nation']} leg is posted.")
        else:
            flash("Play-off fixtures already exist.")
    except ValueError as exc:
        flash(str(exc))

    conn.close()
    return redirect(url_for("playoffs_page"))


@app.route("/playoffs/post/<int:playoff_id>", methods=["GET", "POST"])
def post_playoff_match(playoff_id):
    conn = connect()
    ensure_player_match_event_role_columns(conn)
    ensure_current_human_players(conn)

    match = conn.execute("""
        SELECT *
        FROM playoff_matches
        WHERE playoff_id=?
    """, (playoff_id,)).fetchone()

    if not match:
        conn.close()
        flash("Play-off match not found.")
        return redirect(url_for("playoffs_page"))

    challenge = conn.execute("""
        SELECT *
        FROM challenges
        WHERE challenge_id=?
    """, (match["challenge_id"],)).fetchone()

    if not challenge:
        conn.close()
        flash("Challenge not found.")
        return redirect(url_for("dashboard"))

    club = challenge["club_or_nation"]
    managed_involved = match["home_team"] == club or match["away_team"] == club

    if request.method == "POST":
        # Score is the final score after extra time, so all open-play/extra-time
        # goals and assists are recorded normally. winner_team is only used when
        # the tie is still level and a penalty winner is required.
        home_goals = int(request.form.get("home_goals", 0))
        away_goals = int(request.form.get("away_goals", 0))
        winner_team = request.form.get("winner_team", "").strip() or None
        notes = request.form.get("notes", "")

        possible_winners = {match["home_team"], match["away_team"]}
        if winner_team and winner_team not in possible_winners:
            conn.close()
            flash("Selected winner is not part of this play-off match.")
            return redirect(url_for("post_playoff_match", playoff_id=playoff_id))

        # If a leg-2 aggregate tie or final tie is unresolved, require a winner.
        if match["stage"] == "Final" and home_goals == away_goals and not winner_team:
            conn.close()
            flash("Final is level after extra time. Select the penalty winner.")
            return redirect(url_for("post_playoff_match", playoff_id=playoff_id))

        if match["stage"] == "Semi-Final" and match["leg"] == 2:
            rows = playoff_tie_rows(conn, match["challenge_id"], match["match_no"])
            if len(rows) == 2:
                totals = {
                    match["home_team"]: home_goals,
                    match["away_team"]: away_goals,
                }
                leg1 = rows[0]
                totals[leg1["home_team"]] = totals.get(leg1["home_team"], 0) + (leg1["home_goals"] or 0)
                totals[leg1["away_team"]] = totals.get(leg1["away_team"], 0) + (leg1["away_goals"] or 0)
                teams = list(totals.keys())
                if len(teams) == 2 and totals[teams[0]] == totals[teams[1]] and not winner_team:
                    conn.close()
                    flash("The semi-final is level on aggregate after extra time. Select the penalty winner.")
                    return redirect(url_for("post_playoff_match", playoff_id=playoff_id))

        player_stats = {}
        computer_goals = int(request.form.get("computer_goals", 0)) if managed_involved else 0

        if managed_involved:
            for player in active_human_players(conn):
                key = player.replace(" ", "_").lower()
                appearance_role = request.form.get(f"{key}_appearance", "start")
                appearance = 1 if appearance_role in ("start", "sub") else 0
                started = 1 if appearance_role == "start" else 0
                substitute = 1 if appearance_role == "sub" else 0
                goals = int(request.form.get(f"{key}_goals", 0))
                assists = int(request.form.get(f"{key}_assists", 0))
                yellow_cards = int(request.form.get(f"{key}_yellow_cards", 0))
                red_cards = int(request.form.get(f"{key}_red_cards", 0))
                rating_raw = request.form.get(f"{key}_rating", "").strip()
                rating = float(rating_raw) if rating_raw else None

                player_stats[player] = {
                    "appearance": appearance,
                    "started": started,
                    "substitute": substitute,
                    "goals": goals,
                    "assists": assists,
                    "yellow_cards": yellow_cards,
                    "red_cards": red_cards,
                    "rating": rating,
                }

            team_goals = home_goals if match["home_team"] == club else away_goals
            human_goals = sum(v["goals"] for v in player_stats.values())
            human_assists = sum(v["assists"] for v in player_stats.values())

            if human_goals + computer_goals != team_goals:
                conn.close()
                flash(f"Invalid: human goals + computer goals must equal {club} goals ({team_goals}).")
                return redirect(url_for("post_playoff_match", playoff_id=playoff_id))

            if human_assists > team_goals:
                conn.close()
                flash("Invalid: assists cannot exceed managed team goals.")
                return redirect(url_for("post_playoff_match", playoff_id=playoff_id))

            for player, stats in player_stats.items():
                if stats["appearance"] == 0 and (
                    stats["goals"] or stats["assists"] or stats["yellow_cards"] or stats["red_cards"] or stats["rating"]
                ):
                    conn.close()
                    flash(f"Invalid: {player} has match events but did not play.")
                    return redirect(url_for("post_playoff_match", playoff_id=playoff_id))

        synthetic_fixture_id = -int(playoff_id)

        with conn:
            conn.execute("""
                UPDATE playoff_matches
                SET home_goals=?, away_goals=?, played=1, winner_team=?, source='PES Result', notes=?
                WHERE playoff_id=?
            """, (home_goals, away_goals, winner_team, notes, playoff_id))

            conn.execute("DELETE FROM player_match_events WHERE fixture_id=?", (synthetic_fixture_id,))
            conn.execute("DELETE FROM computer_goal_events WHERE fixture_id=?", (synthetic_fixture_id,))

            if managed_involved:
                for player, stats in player_stats.items():
                    if (
                        stats["appearance"]
                        or stats["goals"]
                        or stats["assists"]
                        or stats["yellow_cards"]
                        or stats["red_cards"]
                        or stats["rating"]
                    ):
                        conn.execute("""
                            INSERT INTO player_match_events(
                                challenge_id, round, fixture_id, player_name,
                                goals, assists, appearance, started, substitute, notes, yellow_cards, red_cards, rating
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            challenge["challenge_id"],
                            47 if match["stage"] == "Semi-Final" and match["leg"] == 1 else 48 if match["stage"] == "Semi-Final" else 49,
                            synthetic_fixture_id,
                            player,
                            stats["goals"],
                            stats["assists"],
                            stats["appearance"],
                            stats["started"],
                            stats["substitute"],
                            notes,
                            stats["yellow_cards"],
                            stats["red_cards"],
                            stats["rating"],
                        ))

                if computer_goals:
                    conn.execute("""
                        INSERT INTO computer_goal_events(challenge_id, round, fixture_id, goals, notes)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        challenge["challenge_id"],
                        47 if match["stage"] == "Semi-Final" and match["leg"] == 1 else 48 if match["stage"] == "Semi-Final" else 49,
                        synthetic_fixture_id,
                        computer_goals,
                        "Computer-controlled player goal(s)",
                    ))

            maybe_generate_playoff_final(conn, match["challenge_id"])
            simulate_unmanaged_playoff_matches(conn, challenge, stage=match["stage"], leg=match["leg"])
            maybe_generate_playoff_final(conn, match["challenge_id"])

            status = playoff_status(conn, challenge)
            if status["finished"]:
                board_conf, _ = latest_board(
                    conn,
                    challenge["challenge_id"],
                    challenge["board_confidence_start"],
                )
                verdict = playoff_final_verdict(conn, challenge, None, None, manager_record(conn, challenge["challenge_id"]), board_conf)
                conn.execute("""
                    INSERT INTO board_log(challenge_id, round, board_confidence, assessment, created_at)
                    VALUES (?, 49, ?, ?, datetime('now'))
                """, (
                    challenge["challenge_id"],
                    100 if status["promoted"] else 78,
                    verdict,
                ))

        conn.close()
        flash("Play-off result posted.")
        return redirect(url_for("playoffs_page"))

    roster = active_human_players(conn)
    conn.close()

    return render_template(
        "playoff_post.html",
        body_class="playoffs-page",
        challenge=challenge,
        match=match,
        players=roster,
        managed_involved=managed_involved,
    )



def challenge_complete_ready(conn, challenge):
    """Return True when the challenge complete page is a live next action."""
    if not challenge:
        return False

    playoff_info = playoff_status(conn, challenge)

    # If play-offs have started/are required, completion should wait until the play-off run is finished.
    if playoff_info and playoff_info.get("qualified"):
        return bool(playoff_info.get("finished"))

    # Otherwise the regular season must be finished.
    return regular_season_finished(conn, challenge)


@app.route("/challenge-complete")
def challenge_complete():
    conn = connect()
    challenge = current_challenge(conn)

    if not challenge:
        conn.close()
        flash("No challenge found.")
        return redirect(url_for("dashboard"))

    table = league_table(conn, challenge["challenge_id"])
    final_row = final_position_row(table, challenge["club_or_nation"])
    regular_record = manager_record(conn, challenge["challenge_id"])
    record = combined_manager_record(conn, challenge)
    players = human_dashboard_totals(conn, challenge["challenge_id"])
    players = sorted(
        players,
        key=lambda p: (p["average_rating"] is not None, p["average_rating"] or 0),
        reverse=True,
    )
    board_conf, board_assessment = latest_board(
        conn,
        challenge["challenge_id"],
        challenge["board_confidence_start"],
    )
    remaining = games_remaining(conn, challenge["challenge_id"], challenge["club_or_nation"])
    playoff_info = playoff_status(conn, challenge)
    complete = playoff_info["finished"]
    regular_completed_count = completed_managed_fixtures_count(
        conn,
        challenge["challenge_id"],
        challenge["club_or_nation"],
    )
    playoff_completed_count = record.get("playoff_matches", 0) if isinstance(record, dict) else 0
    completed_count = regular_completed_count + playoff_completed_count
    scorers, assisters = player_leaders(conn, challenge["challenge_id"])
    offers = available_job_offers(conn) if complete else []

    final_position = final_row["position"] if final_row else None
    final_points = final_row["points"] if final_row else None
    current_position, current_points, gap = derby_context(table, challenge)
    performance_context = final_performance_context(conn, challenge, final_position, final_points, record)
    board_conf = calibrated_board_confidence(
        board_conf,
        current_position,
        challenge["target_position"],
        remaining,
        playoff_info if "playoff_info" in locals() else None,
    )

    if complete:
        board_conf = final_board_confidence(conn, challenge, final_position, final_points, record, board_conf)
        verdict = playoff_final_verdict(conn, challenge, final_position, final_points, record, board_conf)
        verdict_label = "Board verdict"
        verdict_heading = "Final Board Verdict"
    elif playoff_info["qualified"]:
        verdict = playoff_info["message"]
        verdict_label = "Play-off update"
        verdict_heading = "Play-Off Campaign"
    else:
        verdict = challenge_progress_verdict(
            conn,
            challenge,
            current_position,
            current_points,
            completed_count,
            remaining,
            record,
            board_assessment,
            gap,
        )
        verdict_label = "Progress update"
        verdict_heading = "Board Progress Check"

    conn.close()

    return render_template(
        "challenge_complete.html",
        body_class="challenge-complete-page",
        challenge=challenge,
        final_row=final_row,
        record=record,
        players=players,
        board_conf=board_conf,
        board_assessment=board_assessment,
        games_remaining=remaining,
        completed_count=completed_count,
        regular_completed_count=regular_completed_count,
        playoff_completed_count=playoff_completed_count,
        complete=complete,
        scorers=scorers,
        assisters=assisters,
        offers=offers,
        verdict=verdict,
        verdict_label=verdict_label,
        verdict_heading=verdict_heading,
        current_position=current_position,
        current_points=current_points,
        playoff_info=playoff_info,
        performance_context=performance_context,
    )


@app.route("/challenge-complete/confirm", methods=["POST"])
def confirm_challenge_complete():
    conn = connect()
    challenge = active_challenge(conn)

    if not challenge:
        latest = current_challenge(conn) if "current_challenge" in globals() else None
        conn.close()
        if latest and latest["status"] == "Completed":
            flash("Challenge is already completed.")
            return redirect(url_for("challenge_complete"))
        flash("No active challenge found.")
        return redirect(url_for("challenge_complete"))

    if not challenge_is_complete(conn, challenge):
        conn.close()
        flash("Challenge cannot be completed until all managed fixtures have been posted.")
        return redirect(url_for("challenge_complete"))

    table = league_table(conn, challenge["challenge_id"])
    final_row = final_position_row(table, challenge["club_or_nation"])
    regular_record = manager_record(conn, challenge["challenge_id"])
    record = combined_manager_record(conn, challenge)
    board_conf, _ = latest_board(
        conn,
        challenge["challenge_id"],
        challenge["board_confidence_start"],
    )

    final_position = final_row["position"] if final_row else None
    final_points = final_row["points"] if final_row else None
    board_conf = final_board_confidence(conn, challenge, final_position, final_points, record, board_conf)
    verdict = playoff_final_verdict(conn, challenge, final_position, final_points, record, board_conf)

    with conn:
        conn.execute("""
            UPDATE challenges
            SET status='Completed'
            WHERE challenge_id=?
        """, (challenge["challenge_id"],))

        conn.execute("""
            INSERT INTO board_log(challenge_id, round, board_confidence, assessment, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, (
            challenge["challenge_id"],
            challenge["final_round"],
            board_conf,
            verdict,
        ))

    conn.close()
    flash("Challenge completed.")
    return redirect(url_for("challenge_complete"))


@app.route("/admin/job-debug")
def job_debug():
    conn = connect()
    challenges = conn.execute("""
        SELECT challenge_id, club_or_nation, competition, objective, status,
               opening_position, opening_points, target_position
        FROM challenges
        ORDER BY challenge_id
    """).fetchall()
    offers = conn.execute("""
        SELECT *
        FROM job_offers
        ORDER BY offer_id
    """).fetchall()
    teams = conn.execute("""
        SELECT team_name
        FROM teams
        ORDER BY team_name
    """).fetchall()
    completed_count = completed_challenge_count(conn)
    fk_issues = foreign_key_problem_summary(conn)
    conn.close()

    return render_template(
        "job_debug.html",
        challenges=challenges,
        offers=offers,
        teams=teams,
        completed_count=completed_count,
    )




# v18.46 admin result correction tools
def admin_event_state(conn, challenge_id, fixture_id):
    """Return existing human/computer events for an editable result."""
    ensure_player_match_event_role_columns(conn)

    rows = conn.execute("""
        SELECT
            player_name,
            goals,
            assists,
            appearance,
            started,
            substitute,
            yellow_cards,
            red_cards,
            rating,
            notes
        FROM player_match_events
        WHERE challenge_id=? AND fixture_id=?
    """, (challenge_id, fixture_id)).fetchall()

    event_map = {}
    for row in rows:
        event_map[row["player_name"]] = {
            "appearance": row["appearance"] or 0,
            "started": row["started"] or 0,
            "substitute": row["substitute"] or 0,
            "goals": row["goals"] or 0,
            "assists": row["assists"] or 0,
            "yellow_cards": row["yellow_cards"] or 0,
            "red_cards": row["red_cards"] or 0,
            "rating": row["rating"],
            "notes": row["notes"] or "",
        }

    computer_row = conn.execute("""
        SELECT COALESCE(SUM(goals), 0) AS goals
        FROM computer_goal_events
        WHERE challenge_id=? AND fixture_id=?
    """, (challenge_id, fixture_id)).fetchone()

    return {
        "events": event_map,
        "computer_goals": computer_row["goals"] if computer_row else 0,
    }


def editable_match_players(conn, challenge_id, fixture_id):
    """Show active players plus everyone with recorded events in this match.

    Inactive players with historical events must remain editable so a correction
    cannot silently delete their goals, assists, appearances, cards or ratings.
    """
    players = active_human_players(conn)
    recorded = conn.execute(
        """SELECT DISTINCT player_name FROM player_match_events
           WHERE challenge_id=? AND fixture_id=? ORDER BY player_name COLLATE NOCASE""",
        (challenge_id, fixture_id),
    ).fetchall()
    for row in recorded:
        if row["player_name"] not in players:
            players.append(row["player_name"])
    return players


def admin_parse_player_stats_from_form(conn, challenge_id, fixture_id):
    player_stats = {}

    for player in editable_match_players(conn, challenge_id, fixture_id):
        key = player.replace(" ", "_").lower()
        appearance_role = request.form.get(f"{key}_appearance", "none")
        appearance = 1 if appearance_role in ("start", "sub") else 0
        started = 1 if appearance_role == "start" else 0
        substitute = 1 if appearance_role == "sub" else 0
        goals = int(request.form.get(f"{key}_goals", 0) or 0)
        assists = int(request.form.get(f"{key}_assists", 0) or 0)
        yellow_cards = int(request.form.get(f"{key}_yellow_cards", 0) or 0)
        red_cards = int(request.form.get(f"{key}_red_cards", 0) or 0)
        rating_raw = request.form.get(f"{key}_rating", "").strip()
        rating = float(rating_raw) if rating_raw else None

        player_stats[player] = {
            "appearance": appearance,
            "started": started,
            "substitute": substitute,
            "goals": goals,
            "assists": assists,
            "yellow_cards": yellow_cards,
            "red_cards": red_cards,
            "rating": rating,
        }

    return player_stats


def admin_validate_result_correction(match, challenge, player_stats, computer_goals, home_goals, away_goals):
    club = challenge["club_or_nation"]
    team_goals = home_goals if match["home_team"] == club else away_goals
    human_goals = sum(v["goals"] for v in player_stats.values())
    human_assists = sum(v["assists"] for v in player_stats.values())

    if human_goals + computer_goals != team_goals:
        return f"Invalid: human goals + computer goals must equal {club} goals ({team_goals})."

    if human_assists > team_goals:
        return "Invalid: assists cannot exceed managed team goals."

    for player, stats in player_stats.items():
        if stats["appearance"] == 0 and (
            stats["goals"] or stats["assists"] or stats["yellow_cards"] or stats["red_cards"] or stats["rating"]
        ):
            return f"Invalid: {player} has match events but did not play."

    return None


def admin_save_player_events(conn, challenge_id, round_no, fixture_id, player_stats, computer_goals, notes):
    conn.execute("DELETE FROM player_match_events WHERE challenge_id=? AND fixture_id=?", (challenge_id, fixture_id))
    conn.execute("DELETE FROM computer_goal_events WHERE challenge_id=? AND fixture_id=?", (challenge_id, fixture_id))

    for player, stats in player_stats.items():
        if (
            stats["appearance"]
            or stats["goals"]
            or stats["assists"]
            or stats["yellow_cards"]
            or stats["red_cards"]
            or stats["rating"]
        ):
            conn.execute("""
                INSERT INTO player_match_events(
                    challenge_id, round, fixture_id, player_name,
                    goals, assists, appearance, started, substitute, notes, yellow_cards, red_cards, rating
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                challenge_id,
                round_no,
                fixture_id,
                player,
                stats["goals"],
                stats["assists"],
                stats["appearance"],
                stats["started"],
                stats["substitute"],
                notes,
                stats["yellow_cards"],
                stats["red_cards"],
                stats["rating"],
            ))

    if computer_goals:
        conn.execute("""
            INSERT INTO computer_goal_events(challenge_id, round, fixture_id, goals, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (
            challenge_id,
            round_no,
            fixture_id,
            computer_goals,
            "Computer-controlled player goal(s)",
        ))



@app.route("/admin/complete-debug")
def admin_complete_debug():
    conn = connect()
    challenge = current_challenge(conn)

    if not challenge:
        conn.close()
        return "No challenge found", 404

    playoff_info = playoff_status(conn, challenge)
    ready = challenge_complete_ready(conn, challenge)
    remaining = games_remaining(conn, challenge["challenge_id"], challenge["club_or_nation"])
    conn.close()

    return render_template(
        "admin_complete_debug.html",
        challenge=challenge,
        playoff_info=playoff_info,
        complete_ready=ready,
        games_remaining=remaining,
    )


@app.route("/admin/storage")
def admin_storage_status():
    """Show where the live SQLite save is being written and synced."""
    db_exists = DB_PATH.exists()
    db_size = DB_PATH.stat().st_size if db_exists else 0
    db_modified = datetime.fromtimestamp(DB_PATH.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S") if db_exists else None
    using_env_path = bool(os.environ.get("DATABASE_PATH"))
    using_render_disk = str(DB_PATH).startswith(str(DEFAULT_RENDER_DISK_DIR))
    using_supabase = using_supabase_sync()

    supabase_ok = False
    supabase_updated_at = None
    supabase_error = None
    supabase_size = None

    if using_supabase:
        try:
            ensure_supabase_save_table()
            with supabase_connection() as pg:
                with pg.cursor() as cur:
                    cur.execute(
                        f"SELECT updated_at, octet_length(db_bytes) FROM {SUPABASE_SYNC_TABLE} WHERE save_key=%s",
                        (SUPABASE_SAVE_KEY,),
                    )
                    row = cur.fetchone()
                    if row:
                        supabase_ok = True
                        supabase_updated_at = row[0]
                        supabase_size = row[1]
        except Exception as exc:
            supabase_error = str(exc)

    return render_template(
        "admin_storage.html",
        db_path=str(DB_PATH),
        bundled_db_path=str(BUNDLED_DB_PATH),
        render_disk_path=str(DEFAULT_RENDER_DISK_DIR),
        db_exists=db_exists,
        db_size=db_size,
        db_modified=db_modified,
        using_env_path=using_env_path,
        using_render_disk=using_render_disk,
        using_supabase=using_supabase,
        supabase_ok=supabase_ok,
        supabase_updated_at=supabase_updated_at,
        supabase_size=supabase_size,
        supabase_error=supabase_error,
        supabase_save_key=SUPABASE_SAVE_KEY,
    )



@app.route("/admin/edit-results")
def admin_edit_results():
    conn = connect()
    challenge = current_challenge(conn)

    if not challenge:
        conn.close()
        flash("No challenge found.")
        return redirect(url_for("dashboard"))

    club = challenge["club_or_nation"]

    regular_results = conn.execute("""
        SELECT *
        FROM fixtures
        WHERE challenge_id=?
          AND played=1
          AND (home_team=? OR away_team=?)
        ORDER BY round DESC, match_no DESC
    """, (challenge["challenge_id"], club, club)).fetchall()

    playoff_results = conn.execute("""
        SELECT *
        FROM playoff_matches
        WHERE challenge_id=?
          AND played=1
          AND (home_team=? OR away_team=?)
        ORDER BY
            CASE stage
                WHEN 'Final' THEN 2
                WHEN 'Semi-Final' THEN 1
                ELSE 0
            END DESC,
            match_no DESC,
            leg DESC,
            playoff_id DESC
    """, (challenge["challenge_id"], club, club)).fetchall()

    conn.close()

    return render_template(
        "admin_edit_results.html",
        challenge=challenge,
        regular_results=regular_results,
        playoff_results=playoff_results,
    )


@app.route("/admin/edit-results/regular/<int:fixture_id>", methods=["GET", "POST"])
def admin_edit_regular_result(fixture_id):
    conn = connect()
    ensure_player_match_event_role_columns(conn)
    ensure_current_human_players(conn)
    challenge = current_challenge(conn)

    if not challenge:
        conn.close()
        flash("No challenge found.")
        return redirect(url_for("admin_edit_results"))

    club = challenge["club_or_nation"]
    match = conn.execute("""
        SELECT *
        FROM fixtures
        WHERE fixture_id=?
          AND challenge_id=?
          AND played=1
          AND (home_team=? OR away_team=?)
        LIMIT 1
    """, (fixture_id, challenge["challenge_id"], club, club)).fetchone()

    if not match:
        conn.close()
        flash("Posted regular result not found.")
        return redirect(url_for("admin_edit_results"))

    if request.method == "POST":
        home_goals = int(request.form.get("home_goals", 0) or 0)
        away_goals = int(request.form.get("away_goals", 0) or 0)
        computer_goals = int(request.form.get("computer_goals", 0) or 0)
        notes = request.form.get("notes", "").strip()

        player_stats = admin_parse_player_stats_from_form(conn, challenge["challenge_id"], fixture_id)
        error = admin_validate_result_correction(match, challenge, player_stats, computer_goals, home_goals, away_goals)
        if error:
            conn.close()
            flash(error)
            return redirect(url_for("admin_edit_regular_result", fixture_id=fixture_id))

        with conn:
            conn.execute("""
                UPDATE fixtures
                SET home_goals=?, away_goals=?, played=1, locked=1, source='PES Result', notes=?
                WHERE fixture_id=?
            """, (home_goals, away_goals, notes, fixture_id))

            admin_save_player_events(
                conn,
                challenge["challenge_id"],
                match["round"],
                fixture_id,
                player_stats,
                computer_goals,
                notes,
            )

        conn.close()
        flash("Regular result corrected.")
        return redirect(url_for("admin_edit_results"))

    event_state = admin_event_state(conn, challenge["challenge_id"], fixture_id)
    roster = editable_match_players(conn, challenge["challenge_id"], fixture_id)
    conn.close()

    return render_template(
        "admin_edit_result_form.html",
        challenge=challenge,
        match=match,
        result_type="regular",
        players=roster,
        event_map=event_state["events"],
        computer_goals=event_state["computer_goals"],
        action_label="Save corrected result",
        back_url=url_for("admin_edit_results"),
    )


@app.route("/admin/edit-results/playoff/<int:playoff_id>", methods=["GET", "POST"])
def admin_edit_playoff_result(playoff_id):
    conn = connect()
    ensure_player_match_event_role_columns(conn)
    ensure_current_human_players(conn)
    challenge = current_challenge(conn)

    if not challenge:
        conn.close()
        flash("No challenge found.")
        return redirect(url_for("admin_edit_results"))

    club = challenge["club_or_nation"]
    match = conn.execute("""
        SELECT *
        FROM playoff_matches
        WHERE playoff_id=?
          AND challenge_id=?
          AND played=1
          AND (home_team=? OR away_team=?)
        LIMIT 1
    """, (playoff_id, challenge["challenge_id"], club, club)).fetchone()

    if not match:
        conn.close()
        flash("Posted play-off result not found.")
        return redirect(url_for("admin_edit_results"))

    synthetic_fixture_id = -int(playoff_id)

    if request.method == "POST":
        home_goals = int(request.form.get("home_goals", 0) or 0)
        away_goals = int(request.form.get("away_goals", 0) or 0)
        computer_goals = int(request.form.get("computer_goals", 0) or 0)
        notes = request.form.get("notes", "").strip()
        winner_team = request.form.get("winner_team", "").strip() or None

        if winner_team and winner_team not in {match["home_team"], match["away_team"]}:
            conn.close()
            flash("Selected winner is not part of this play-off match.")
            return redirect(url_for("admin_edit_playoff_result", playoff_id=playoff_id))

        player_stats = admin_parse_player_stats_from_form(conn, challenge["challenge_id"], synthetic_fixture_id)
        error = admin_validate_result_correction(match, challenge, player_stats, computer_goals, home_goals, away_goals)
        if error:
            conn.close()
            flash(error)
            return redirect(url_for("admin_edit_playoff_result", playoff_id=playoff_id))

        round_no = 47 if match["stage"] == "Semi-Final" and match["leg"] == 1 else 48 if match["stage"] == "Semi-Final" else 49

        with conn:
            conn.execute("""
                UPDATE playoff_matches
                SET home_goals=?, away_goals=?, played=1, winner_team=?, source='PES Result', notes=?
                WHERE playoff_id=?
            """, (home_goals, away_goals, winner_team, notes, playoff_id))

            admin_save_player_events(
                conn,
                challenge["challenge_id"],
                round_no,
                synthetic_fixture_id,
                player_stats,
                computer_goals,
                notes,
            )

        conn.close()
        flash("Play-off result corrected.")
        return redirect(url_for("admin_edit_results"))

    event_state = admin_event_state(conn, challenge["challenge_id"], synthetic_fixture_id)
    roster = editable_match_players(conn, challenge["challenge_id"], synthetic_fixture_id)
    conn.close()

    return render_template(
        "admin_edit_result_form.html",
        challenge=challenge,
        match=match,
        result_type="playoff",
        players=roster,
        event_map=event_state["events"],
        computer_goals=event_state["computer_goals"],
        action_label="Save corrected play-off result",
        back_url=url_for("admin_edit_results"),
    )



@app.route("/validation")
def validation_page():
    conn = connect()
    status, rows = validation(conn)
    conn.close()
    return render_template("validation.html", validation_status=status, validation_rows=rows)


if __name__ == "__main__":
    app.run(debug=True)

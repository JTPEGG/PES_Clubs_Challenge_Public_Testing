"""Read-only PES 2.0 football world scaffold.

Uses namespaced tables in the development application's existing SQLite save.
No source player ratings, contracts or match results are fabricated.
"""
import sqlite3
import re
import unicodedata
from datetime import datetime
from flask import Blueprint, abort, render_template_string
from world_2026_27_clubs import LEAGUE_MEMBERS, validate_memberships
from world_2026_27_players import PLAYER_SEED, SOURCE_URL as PLAYER_SOURCE_URL
from world_fc27_english import FC27_PLAYERS, SOURCE_URL as FC_SOURCE_URL, SNAPSHOT_DATE as FC_SNAPSHOT
from world_quality import audit_seed_sources, audit_database

SEASON = "2026/27"
PL_SOURCE = "https://www.premierleague.com/en/news/4365156"
PL_CLUBS = (
    "AFC Bournemouth", "Arsenal", "Aston Villa", "Brentford",
    "Brighton & Hove Albion", "Chelsea", "Coventry City",
    "Crystal Palace", "Everton", "Fulham", "Hull City",
    "Ipswich Town", "Leeds United", "Liverpool", "Manchester City",
    "Manchester United", "Newcastle United", "Nottingham Forest",
    "Sunderland", "Tottenham Hotspur",
)
COMPETITIONS = (
    ("ENG1", "Premier League", 1, 20),
    ("ENG2", "Championship", 2, 24),
    ("ENG3", "League One", 3, 24),
    ("ENG4", "League Two", 4, 24),
)
# International competitions are catalogued, not populated with invented
# 2026/27 clubs or players. Historical imports may vary in league size.
INTERNATIONAL_COMPETITIONS = (
    ("ITA1", "Serie A", "Italy", 20),
    ("ESP1", "La Liga", "Spain", 20),
    ("GER1", "Bundesliga", "Germany", 18),
    ("FRA1", "Ligue 1", "France", 18),
    ("POR1", "Primeira Liga", "Portugal", 18),
    ("SCO1", "Scottish Premiership", "Scotland", 12),
)


def ensure_international_competitions(conn):
    """Add league definitions without asserting any historical memberships."""
    for cid,name,country,size in INTERNATIONAL_COMPETITIONS:
        conn.execute("""INSERT OR IGNORE INTO world_competitions
            (competition_id,name,country,tier,expected_clubs)
            VALUES(?,?,?,1,?)""",(cid,name,country,size))
    conn.commit()

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS world_seasons(
 season_id TEXT PRIMARY KEY, label TEXT NOT NULL, start_date TEXT,
 registration_lock TEXT, status TEXT NOT NULL DEFAULT 'setup'
);
CREATE TABLE IF NOT EXISTS world_competitions(
 competition_id TEXT PRIMARY KEY, name TEXT NOT NULL, country TEXT NOT NULL,
 tier INTEGER, expected_clubs INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS world_clubs(
 club_id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, nation TEXT NOT NULL DEFAULT 'England',
 reputation INTEGER, finances_source TEXT, pes_team_id TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS world_entries(
 season_id TEXT NOT NULL REFERENCES world_seasons(season_id),
 competition_id TEXT NOT NULL REFERENCES world_competitions(competition_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 source_url TEXT, status TEXT NOT NULL DEFAULT 'verified',
 PRIMARY KEY(season_id,club_id)
);
CREATE TABLE IF NOT EXISTS world_players(
 player_id INTEGER PRIMARY KEY, full_name TEXT NOT NULL, birth_date TEXT,
 nationality TEXT, primary_position TEXT, source_url TEXT
);
CREATE TABLE IF NOT EXISTS world_contracts(
 contract_id INTEGER PRIMARY KEY, player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 starts TEXT, expires TEXT, wage_amount INTEGER, currency TEXT,
 source_url TEXT, UNIQUE(player_id, club_id, starts)
);
CREATE TABLE IF NOT EXISTS world_player_source_refs(
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 source_name TEXT NOT NULL, external_id TEXT NOT NULL, source_url TEXT NOT NULL,
 identity_status TEXT NOT NULL DEFAULT 'provisional',
 PRIMARY KEY(source_name,external_id), UNIQUE(player_id,source_name)
);
CREATE TABLE IF NOT EXISTS world_player_alternative_positions(
 dataset_id TEXT NOT NULL,
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 position TEXT NOT NULL,
 source_note TEXT NOT NULL,
 PRIMARY KEY(dataset_id,player_id,position)
);
CREATE TABLE IF NOT EXISTS world_rosters(
 season_id TEXT NOT NULL REFERENCES world_seasons(season_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 registration_source TEXT NOT NULL, verification_status TEXT NOT NULL DEFAULT 'provisional',
 PRIMARY KEY(season_id,player_id)
);
CREATE TABLE IF NOT EXISTS world_pes_player_map(
 player_id INTEGER PRIMARY KEY REFERENCES world_players(player_id),
 pes_player_id TEXT NOT NULL UNIQUE, file_version TEXT NOT NULL, verified_at TEXT
);
CREATE TABLE IF NOT EXISTS world_player_attributes(
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 effective_season TEXT NOT NULL REFERENCES world_seasons(season_id),
 attribute_name TEXT NOT NULL, value INTEGER NOT NULL CHECK(value BETWEEN 1 AND 99),
 source_url TEXT, PRIMARY KEY(player_id,effective_season,attribute_name)
);
CREATE TABLE IF NOT EXISTS world_fixtures(
 fixture_id INTEGER PRIMARY KEY, season_id TEXT NOT NULL REFERENCES world_seasons(season_id),
 competition_id TEXT NOT NULL REFERENCES world_competitions(competition_id),
 round_no INTEGER NOT NULL, home_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 away_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 home_goals INTEGER, away_goals INTEGER, played INTEGER NOT NULL DEFAULT 0,
 CHECK(home_id <> away_id), UNIQUE(season_id,competition_id,round_no,home_id)
);
CREATE TABLE IF NOT EXISTS world_player_match_events(
 fixture_id INTEGER NOT NULL REFERENCES world_fixtures(fixture_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 minutes INTEGER, goals INTEGER NOT NULL DEFAULT 0, assists INTEGER NOT NULL DEFAULT 0,
 yellows INTEGER NOT NULL DEFAULT 0, reds INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(fixture_id,player_id)
);
CREATE TABLE IF NOT EXISTS world_external_ratings(
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 source_name TEXT NOT NULL, edition TEXT NOT NULL, snapshot_date TEXT NOT NULL,
 external_player_id TEXT NOT NULL,
 overall INTEGER NOT NULL CHECK(overall BETWEEN 1 AND 99),
 pace INTEGER, shooting INTEGER, passing INTEGER, dribbling INTEGER,
 defending INTEGER, physicality INTEGER,
 PRIMARY KEY(player_id,source_name,edition),
 UNIQUE(source_name,edition,external_player_id)
);
CREATE TABLE IF NOT EXISTS world_transfers(
 transfer_id INTEGER PRIMARY KEY, player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 from_club_id INTEGER REFERENCES world_clubs(club_id),
 to_club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 agreement_date TEXT NOT NULL, effective_date TEXT NOT NULL,
 fee_amount INTEGER, currency TEXT, status TEXT NOT NULL,
 CHECK(from_club_id IS NULL OR from_club_id <> to_club_id)
);
"""

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{title}} | PES Clubs Challenge 2.0</title>
<style>
:root{color-scheme:dark}body{margin:0;background:#111a25;color:#eaf1f8;font-family:system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1000px;margin:auto;padding:30px 20px 70px}
a{color:#a9d3fc;text-decoration:none}a:hover{text-decoration:underline}
header{background:#1b2939;border-bottom:1px solid #33465a;padding:18px 22px}
h1{font-size:2rem;margin:0 0 10px}h2{font-size:1.15rem}
.muted{color:#a6b5c5}.small{font-size:.87rem}.pill{display:inline-block;padding:4px 10px;border:1px solid #41576c;border-radius:20px;font-size:.8rem;color:#b7d7f5}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:15px;margin-top:24px}
.card{display:block;background:#1c2b3b;border:1px solid #35485b;border-radius:10px;padding:19px}
.card:hover{border-color:#83b5e5;text-decoration:none}.stat{font-size:1.8rem;font-weight:700}
table{width:100%;border-collapse:collapse;background:#1c2b3b;border-radius:8px;overflow:hidden}
td,th{padding:13px 15px;border-bottom:1px solid #334356;text-align:left}th{font-size:.82rem;color:#aab8c7}
.notice{background:#26374a;border-left:3px solid #81b6e5;padding:14px 18px;border-radius:4px;margin:20px 0}
</style></head><body>
<header><a href="/world"><b>PES CLUBS CHALLENGE 2.0</b></a> · <a href="/world/explore">Squad Explorer</a> · <a href="/">Original challenge</a></header>
<main><p class="muted small">Development sandbox · 2026/27 · Read only</p>
<h1>{{title}}</h1><p class="muted">{{subtitle}}</p>
{% if kind == 'index' %}
<div class="notice">All four 2026/27 divisions have FC27 reference ratings. Squad memberships are provisional, not registered/verified lineups. Some EA and FPL sources disagree. <a href="/world/quality">View the data-quality audit</a>.</div>
<div class="grid">{% for c in competitions %}
<a class="card" href="{{url_for('world_v2.competition',cid=c['competition_id'])}}">
<span class="pill">Tier {{c['tier']}}</span><h2>{{c['name']}}</h2>
<div class="stat">{{c['actual']}} / {{c['expected_clubs']}}</div><div class="muted small">verified clubs imported</div></a>
{% endfor %}</div>
{% elif kind == 'competition' %}
<p><a href="/world">← All leagues</a></p>
<div class="notice">{{clubs|length}} of {{expected}} league clubs loaded. Player roster assignments are source snapshots, not confirmed registrations. <a href="/world/quality">Review quality issues</a>.</div>
{% if clubs %}<table><tr><th>Club</th><th>Squad records</th></tr>
{% for c in clubs %}<tr><td><a href="{{url_for('world_v2.club',club_id=c['club_id'])}}">{{c['name']}}</a></td><td>{{c['players']}}</td></tr>{% endfor %}</table>
{% else %}<div class="card">No verified clubs are currently available.</div>{% endif %}
{% elif kind == 'club' %}
<p><a href="{{url_for('world_v2.competition',cid=competition_id)}}">← {{competition_name}}</a></p>
<div class="grid"><div class="card"><div class="muted small">Season</div><div class="stat">2026/27</div></div>
<div class="card"><div class="muted small">Player records loaded</div><div class="stat">{{players|length}}</div></div></div>
<h2>Squad</h2>{% if players %}<table><tr><th>Player</th><th>Position</th><th>FC 27 OVR</th><th>Source status</th></tr>
{% for p in players %}<tr><td>{{p['full_name']}}</td><td>{{p['primary_position'] or '—'}}</td><td>{{p['overall'] if p['overall'] is not none else '—'}}</td><td>{{p['verification_status']}}</td></tr>{% endfor %}</table>
{% else %}<div class="notice">Player records for this club have not been imported. No invented ratings or wages.</div>{% endif %}
{% elif kind == 'quality' %}
<p><a href="/world">← Football World</a></p>
<div class="notice">Candidate mismatches are NOT verified transfer movements. Identical or abbreviated names can refer to different footballers. This audit does not edit player records.</div>
<div class="grid">
<div class="card"><div class="muted small">Unique player records in database</div><div class="stat">{{quality['players']}}</div></div>
<div class="card"><div class="muted small">EA FC27 ratings</div><div class="stat">{{quality['ea_rated']}}</div></div>
<div class="card"><div class="muted small">Provisional squad assignments</div><div class="stat">{{quality['provisional_rosters']}}</div></div>
<div class="card"><div class="muted small">PES IDs verified</div><div class="stat">{{quality['pes_id_matches']}}</div></div>
</div>
<h2>Database checks</h2>
<table><tr><th>Check</th><th>Count</th></tr>
<tr><td>EA source references</td><td>{{quality['ea_source_refs']}}</td></tr>
<tr><td>FPL source references</td><td>{{quality['fpl_source_refs']}}</td></tr>
<tr><td>EA ID duplicates</td><td>{{quality['duplicate_ea_ids']}}</td></tr>
<tr><td>Repeated season registrations</td><td>{{quality['duplicate_season_registrations']}}</td></tr>
<tr><td>Players with no squad registration</td><td>{{quality['unassigned_players']}}</td></tr>
<tr><td>EA players without squad entry</td><td>{{quality['fc27_without_roster']}}</td></tr>
<tr><td>Contracts with verified terms</td><td>{{quality['contracts']}}</td></tr></table>
<h2>Cross-source club/identity review candidates ({{audit['possible_conflicts']|length}})</h2>
<p class="muted small">Found using a unique normalized display/common/surname match across the two source extracts. These are warnings needing independent confirmation.</p>
<table><tr><th>FPL entry</th><th>EA entry</th></tr>
{% for c in audit['possible_conflicts'] %}
<tr><td>{{c['fpl_name']}}<div class="muted small">{{c['fpl_club']}} · ID {{c['fpl_id']}}</div></td>
<td>{{c['ea_name']}}<div class="muted small">{{c['ea_club']}} · ID {{c['ea_id']}}</div></td></tr>
{% endfor %}
</table>
{% endif %}
<p class="muted small" style="margin-top:35px">Prototype — existing result posting, careers and live fixtures remain unchanged.</p>
</main></body></html>"""


def _normal_name(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _seed_fc27(conn):
    existing = conn.execute(
        "SELECT COUNT(*) FROM world_player_source_refs WHERE source_name='EAFC27'"
    ).fetchone()[0]
    if existing == len(FC27_PLAYERS):
        return
    if existing:
        raise ValueError("Partial FC27 seed detected: manual reconciliation required")

    # Link legacy FPL short-name records only on a unique club/name match.
    # Ambiguous names are never automatically merged.
    fpl = conn.execute("""SELECT p.player_id,p.full_name,r.club_id
        FROM world_players p JOIN world_rosters r ON r.player_id=p.player_id
        JOIN world_player_source_refs s ON s.player_id=p.player_id
        WHERE s.source_name='FPL' AND r.season_id=?""", (SEASON,)).fetchall()
    keys = {}
    for player_id, short_name, club_id in fpl:
        keys.setdefault((club_id, _normal_name(short_name)), []).append(player_id)
    # Resolve all clubs once instead of joining entries for every player.
    known_clubs = {(row[1], row[2]): row[0] for row in conn.execute(
        """SELECT c.club_id,c.name,e.competition_id FROM world_clubs c
           JOIN world_entries e ON e.club_id=c.club_id
           WHERE e.season_id=?""", (SEASON,)).fetchall()}
    claimed = set()
    for rec in FC27_PLAYERS:
        (external_id, name, first, last, common, position, club_name, league_code,
         overall, pace, shooting, passing, dribbling, defending, physicality,
         birthdate, nationality) = rec
        club_id = known_clubs.get((club_name, league_code))
        if club_id is None:
            raise ValueError(f"Unknown FC27 English league membership: {club_name} ({league_code})")
        candidates = set()
        for label in (name, common, last, (first[:1] + "." + last) if first else ""):
            if label:
                candidates.update(keys.get((club_id, _normal_name(label)), []))
        candidates.difference_update(claimed)
        player_id = next(iter(candidates)) if len(candidates) == 1 else None
        try:
            birth_iso = datetime.strptime(birthdate, "%d-%m-%Y").date().isoformat() if birthdate else None
        except ValueError:
            birth_iso = None
        if player_id is None:
            player_id = conn.execute(
                """INSERT INTO world_players(full_name,birth_date,nationality,
                   primary_position,source_url) VALUES (?,?,?,?,?)""",
                (name,birth_iso,nationality,position,FC_SOURCE_URL),
            ).lastrowid
        else:
            claimed.add(player_id)
            conn.execute("""UPDATE world_players SET full_name=?,birth_date=?,
                nationality=?,primary_position=?,source_url=? WHERE player_id=?""",
                (name,birth_iso,nationality,position,FC_SOURCE_URL,player_id))
            conn.execute("""UPDATE world_rosters SET verification_status='source-matched',
                registration_source='FPL + EA FC27'
                WHERE season_id=? AND club_id=? AND player_id=?""",
                (SEASON,club_id,player_id))
        conn.execute("""INSERT INTO world_player_source_refs
            (player_id,source_name,external_id,source_url,identity_status)
            VALUES (?,?,?,?,?)""",
            (player_id,"EAFC27",str(external_id),FC_SOURCE_URL,"source-matched"))
        conn.execute("""INSERT OR IGNORE INTO world_rosters
            (season_id,club_id,player_id,registration_source,verification_status)
            VALUES (?,?,?,?,?)""",
            (SEASON,club_id,player_id,"EA FC27 ratings snapshot","source-matched"))
        conn.execute("""INSERT INTO world_external_ratings
            (player_id,source_name,edition,snapshot_date,external_player_id,
             overall,pace,shooting,passing,dribbling,defending,physicality)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (player_id,"EA FC 27","fc27",FC_SNAPSHOT,str(external_id),
             overall,pace,shooting,passing,dribbling,defending,physicality))


def initialize_world(conn):
    # Fast path: prevent re-importing 3,000 source references on every request.
    existing_tables = conn.execute("""SELECT name FROM sqlite_master
        WHERE type='table' AND name IN ('world_player_source_refs','world_entries',
                                       'world_external_ratings')""").fetchall()
    if len(existing_tables) == 3:
        ensure_international_competitions(conn)
        refs = dict(conn.execute("""SELECT source_name,COUNT(*)
            FROM world_player_source_refs WHERE source_name IN ('FPL','EAFC27')
            GROUP BY source_name""").fetchall())
        entries = conn.execute("SELECT COUNT(*) FROM world_entries WHERE season_id=?", (SEASON,)).fetchone()[0]
        ratings = conn.execute("""SELECT COUNT(*) FROM world_external_ratings
            WHERE source_name='EA FC 27' AND edition='fc27'""").fetchone()[0]
        if (refs.get('FPL') == len(PLAYER_SEED)
                and refs.get('EAFC27') == len(FC27_PLAYERS)
                and entries == 92 and ratings == len(FC27_PLAYERS)):
            return
    conn.executescript(SCHEMA)
    conn.execute("INSERT OR IGNORE INTO world_seasons(season_id,label) VALUES (?,?)", (SEASON, SEASON))
    ensure_international_competitions(conn)
    for cid, name, tier, n in COMPETITIONS:
        conn.execute(
            "INSERT OR IGNORE INTO world_competitions(competition_id,name,country,tier,expected_clubs) VALUES (?,?,?,?,?)",
            (cid, name, "England", tier, n),
        )
    errors = validate_memberships()
    if errors:
        raise ValueError("2026/27 league seed invalid: " + "; ".join(errors))
    for cid, (source_url, clubs) in LEAGUE_MEMBERS.items():
        for name in clubs:
            conn.execute("INSERT OR IGNORE INTO world_clubs(name) VALUES (?)", (name,))
            club_id = conn.execute("SELECT club_id FROM world_clubs WHERE name=?", (name,)).fetchone()[0]
            current = conn.execute(
                "SELECT competition_id FROM world_entries WHERE season_id=? AND club_id=?",
                (SEASON, club_id),
            ).fetchone()
            if current and current[0] != cid:
                raise ValueError(f"Conflicting 2026/27 membership for {name}")
            conn.execute(
                "INSERT OR IGNORE INTO world_entries(season_id,competition_id,club_id,source_url,status) VALUES (?,?,?,?,?)",
                (SEASON, cid, club_id, source_url, "verified"),
            )
    counts = dict(conn.execute(
        "SELECT competition_id, COUNT(*) FROM world_entries WHERE season_id=? GROUP BY competition_id",
        (SEASON,)
    ).fetchall())
    for cid, _name, _tier, expected in COMPETITIONS:
        if counts.get(cid, 0) != expected:
            raise ValueError(f"{cid}: expected {expected} clubs, database contains {counts.get(cid, 0)}")
    # Keep existing FPL identifiers and fill them only when first seeded.
    fpl_count = conn.execute(
        "SELECT COUNT(*) FROM world_player_source_refs WHERE source_name='FPL'"
    ).fetchone()[0]
    if fpl_count not in (0, len(PLAYER_SEED)):
        raise ValueError("Partial FPL seed detected: manual reconciliation required")
    if fpl_count == 0:
        for external_id, display_name, position, club_name in PLAYER_SEED:
            club = conn.execute("SELECT club_id FROM world_clubs WHERE name=?", (club_name,)).fetchone()
            if club is None:
                raise ValueError(f"Unknown source player club {club_name}")
            existing = conn.execute("""SELECT player_id FROM world_player_source_refs
                WHERE source_name='FPL' AND external_id=?""", (external_id,)).fetchone()
            if existing:
                player_id = existing[0]
            else:
                cur = conn.execute(
                    "INSERT INTO world_players(full_name,primary_position,source_url) VALUES (?,?,?)",
                    (display_name, position, PLAYER_SOURCE_URL))
                player_id = cur.lastrowid
                conn.execute("""INSERT INTO world_player_source_refs
                    (player_id,source_name,external_id,source_url,identity_status)
                    VALUES (?,?,?,?,?)""",
                    (player_id, "FPL", external_id, PLAYER_SOURCE_URL, "provisional"))
            conn.execute("""INSERT OR IGNORE INTO world_rosters
                (season_id,club_id,player_id,registration_source,verification_status)
                VALUES (?,?,?,?,?)""",
                (SEASON, club[0], player_id, "FPL-derived season dataset", "provisional"))
    _seed_fc27(conn)
    conn.commit()


def create_world_blueprint(db_path):
    bp = Blueprint("world_v2", __name__)
    def connect():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        initialize_world(conn)
        return conn

    @bp.get("/world")
    def index():
        with connect() as db:
            items = db.execute("""SELECT c.*, COUNT(e.club_id) AS actual
                FROM world_competitions c LEFT JOIN world_entries e
                  ON e.competition_id=c.competition_id AND e.season_id=?
                WHERE c.country='England'
                GROUP BY c.competition_id ORDER BY c.tier""", (SEASON,)).fetchall()
            return render_template_string(PAGE, kind="index", title="Football World",
                subtitle="Explore the foundation of the persistent 2026/27 season",
                competitions=items)

    @bp.get("/world/quality")
    def quality():
        with connect() as db:
            return render_template_string(PAGE, kind="quality",
                title="Player database quality",
                subtitle="Source comparison, identity conflicts and registration-readiness checks",
                quality=audit_database(db), audit=audit_seed_sources())

    @bp.get("/world/league/<cid>")
    def competition(cid):
        with connect() as db:
            league = db.execute("SELECT * FROM world_competitions WHERE competition_id=?", (cid,)).fetchone()
            if not league:
                abort(404)
            clubs = db.execute("""SELECT c.club_id,c.name, COUNT(DISTINCT x.player_id) AS players
                FROM world_entries e JOIN world_clubs c ON c.club_id=e.club_id
                LEFT JOIN world_rosters co ON co.club_id=c.club_id AND co.season_id=?
                LEFT JOIN world_external_ratings x ON x.player_id=co.player_id
                  AND x.source_name='EA FC 27' AND x.edition='fc27'
                WHERE e.season_id=? AND e.competition_id=?
                GROUP BY c.club_id ORDER BY c.name""", (SEASON, SEASON, cid)).fetchall()
            return render_template_string(PAGE, kind="competition", title=league["name"],
                subtitle="Verified league membership", clubs=clubs,
                expected=league["expected_clubs"], season=SEASON)

    @bp.get("/world/club/<int:club_id>")
    def club(club_id):
        with connect() as db:
            team = db.execute("""SELECT c.name,e.competition_id,w.name AS competition_name
                FROM world_clubs c JOIN world_entries e ON c.club_id=e.club_id
                JOIN world_competitions w ON w.competition_id=e.competition_id
                WHERE c.club_id=? AND e.season_id=?""", (club_id, SEASON)).fetchone()
            if not team:
                abort(404)
            players = db.execute("""SELECT p.player_id,p.full_name,p.primary_position,
                       r.verification_status,x.overall
                FROM world_rosters r JOIN world_players p ON p.player_id=r.player_id
                LEFT JOIN world_external_ratings x ON x.player_id=p.player_id
                  AND x.source_name='EA FC 27' AND x.edition='fc27'
                WHERE r.club_id=? AND r.season_id=?
                ORDER BY x.overall DESC,p.full_name""", (club_id, SEASON)).fetchall()
            return render_template_string(PAGE, kind="club", title=team["name"],
                subtitle="Club profile and verified squad records",
                competition_id=team["competition_id"], competition_name=team["competition_name"],
                players=players)
    return bp

"""Season-aware read-only squad explorer for PES Challenge 2.0.

All queries are scoped to a selected, immutable season dataset. A browsing
selection NEVER changes the active career save or edits player registrations.
Future season imports create separate dataset rows and season-specific data.
"""
from datetime import date
import sqlite3
from flask import Blueprint, abort, render_template_string, request, url_for
from world_valuation import model_value, display_gbp, MODEL_VERSION

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_datasets (
 dataset_id TEXT PRIMARY KEY,
 season_id TEXT NOT NULL REFERENCES world_seasons(season_id),
 title TEXT NOT NULL,
 source_label TEXT NOT NULL,
 source_date TEXT,
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','review','published','archived')),
 is_career_active INTEGER NOT NULL DEFAULT 0 CHECK(is_career_active IN (0,1)),
 created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS world_only_one_active_dataset
ON world_datasets(is_career_active) WHERE is_career_active=1;
CREATE TABLE IF NOT EXISTS world_dataset_entries (
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 competition_id TEXT NOT NULL REFERENCES world_competitions(competition_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 PRIMARY KEY(dataset_id,club_id)
);
CREATE TABLE IF NOT EXISTS world_dataset_rosters (
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 evidence TEXT NOT NULL DEFAULT 'source snapshot',
 verification_status TEXT NOT NULL DEFAULT 'provisional',
 PRIMARY KEY(dataset_id,player_id)
);
CREATE TABLE IF NOT EXISTS world_dataset_ratings (
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 source_name TEXT NOT NULL, source_edition TEXT NOT NULL,
 source_date TEXT, external_player_id TEXT,
 overall INTEGER CHECK(overall BETWEEN 1 AND 99),
 pace INTEGER, shooting INTEGER, passing INTEGER, dribbling INTEGER,
 defending INTEGER, physicality INTEGER,
 PRIMARY KEY(dataset_id,player_id)
);
CREATE INDEX IF NOT EXISTS world_dataset_rosters_by_club
ON world_dataset_rosters(dataset_id,club_id);
"""

CSS = """body{margin:0;background:#111a25;color:#eaf1f8;font:15px system-ui,-apple-system,Segoe UI,sans-serif}
header{padding:17px 25px;background:#1c2a3a;border-bottom:1px solid #39485b}
main{max-width:1120px;margin:auto;padding:28px 18px 70px}
a{color:#a9d3fc;text-decoration:none}a:hover{text-decoration:underline}
h1{font-size:2rem;margin:7px 0}h2{font-size:1.25rem}
.muted{color:#aab9c8}.small{font-size:.85rem}
.pill{border:1px solid #435a70;padding:4px 9px;border-radius:18px}
.note{background:#25374a;border-left:3px solid #83bce7;padding:14px 18px;margin:20px 0;border-radius:4px}
.box{background:#1b2b3c;border:1px solid #354c63;border-radius:10px;padding:17px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:14px}
table{border-collapse:collapse;width:100%;background:#1b2b3c;border-radius:8px;overflow:hidden}
th,td{text-align:left;padding:11px 12px;border-bottom:1px solid #35485b}
th{font-size:.85rem;color:#bfd1df}
form{display:flex;gap:10px;flex-wrap:wrap;align-items:end;margin:18px 0}
select,input,button{background:#263b50;color:#edf5fd;border:1px solid #526980;padding:9px 11px;border-radius:6px}
button{cursor:pointer;background:#305d80}
table td.num,table th.num{text-align:right}
.bar{height:8px;background:#394c60;border-radius:6px;overflow:hidden;flex:1}
.fill{background:#6bb8a5;height:100%}
.stat{font-size:1.8rem;font-weight:700}
"""

TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{title}} · Football World</title><style>""" + CSS + """</style></head><body>
<header><a href="/world"><b>PES CLUBS CHALLENGE</b></a> · <a href="{{url_for('world_explorer.index',dataset=dataset['dataset_id'])}}">Squad Explorer</a> · <a href="/world/finances?dataset={{dataset['dataset_id']}}">Club finances</a> · <a href="/world/reputations?dataset={{dataset['dataset_id']}}">Reputation audit</a> · <a href="/">Existing challenge</a></header>
<main><p class="small muted">Development environment · Historical dataset explorer · Read only</p>
<h1>{{title}}</h1>
<div class="note"><b>Selected dataset:</b> {{dataset['title']}} · {{dataset['source_label']}} · {{dataset['status']}}.
Selecting a season here does not switch or overwrite an active career. FC ratings are references, not PES attributes, contracts, potential or transfer values.</div>
<form method="get" action="{{url_for('world_explorer.index')}}">
<label for="dataset">Browse season dataset</label>
<select id="dataset" name="dataset">{% for d in datasets %}
<option value="{{d['dataset_id']}}" {% if d['dataset_id']==dataset['dataset_id'] %}selected{% endif %}>{{d['title']}} ({{d['status']}})</option>
{% endfor %}</select><button type="submit">View dataset</button></form>
{% if mode == 'index' %}
<div class="grid">{% for l in leagues %}<a class="box" href="{{url_for('world_explorer.league',cid=l['competition_id'],dataset=dataset['dataset_id'])}}">
<p class="muted small">English division {{l['tier']}}</p><h2>{{l['name']}}</h2>
<div class="stat">{{l['clubs']}}</div><p class="muted small">clubs in selected dataset</p></a>{% endfor %}</div>
{% elif mode == 'league' %}
<p><a href="{{url_for('world_explorer.index',dataset=dataset['dataset_id'])}}">← Divisions</a></p>
<table><tr><th>Club</th><th class="num">Player records</th></tr>
{% for c in clubs %}<tr><td><a href="{{url_for('world_explorer.club',club_id=c['club_id'],dataset=dataset['dataset_id'])}}">{{c['name']}}</a></td><td class="num">{{c['roster_size']}}</td></tr>{% endfor %}</table>
{% elif mode == 'club' %}
<p><a href="{{url_for('world_explorer.league',cid=team['competition_id'],dataset=dataset['dataset_id'])}}">← {{team['competition_name']}}</a> · <a href="/world/finances/club/{{club_id}}?dataset={{dataset['dataset_id']}}">Club finances and contracts →</a></p>
<div class="grid"><div class="box"><div class="muted small">Squad records</div><div class="stat">{{total}}</div></div>
<div class="box"><div class="muted small">Rating reference</div><div class="stat">Source dataset</div></div></div>
<form method="get">
<input type="hidden" name="dataset" value="{{dataset['dataset_id']}}">
<label for="position">Position</label><select id="position" name="position"><option value="">All positions</option>
{% for p in positions %}<option value="{{p}}" {% if p==selected_position %}selected{% endif %}>{{p}}</option>{% endfor %}</select>
<label for="sort">Sort</label><select id="sort" name="sort">
{% for val,label in sorts %}<option value="{{val}}" {% if val==selected_sort %}selected{% endif %}>{{label}}</option>{% endfor %}</select>
<label for="q">Search</label><input id="q" name="q" value="{{q}}" placeholder="Player name"><button type="submit">Apply</button></form>
<table><tr><th>Player</th><th>Position</th><th class="num">Age at dataset date</th><th class="num">Source OVR</th><th class="num">Model value</th><th>Status</th></tr>
{% for p in players %}<tr><td><a href="{{url_for('world_explorer.player',player_id=p['player_id'],dataset=dataset['dataset_id'])}}">{{p['full_name']}}</a></td>
<td>{{p['primary_position'] or '—'}}</td><td class="num">{{p['age'] if p['age'] is not none else '—'}}</td>
<td class="num">{{p['overall'] if p['overall'] is not none else '—'}}</td><td class="num">{{p['value_label']}}</td><td>{{p['verification_status']}}</td></tr>{% endfor %}</table>
{% if not players %}<p class="muted">No players match these filters.</p>{% endif %}
{% elif mode == 'player' %}
<p><a href="{{url_for('world_explorer.club',club_id=player['club_id'],dataset=dataset['dataset_id'])}}">← {{player['club_name']}} squad</a></p>
<div class="grid">
<div class="box"><div class="muted small">Club · {{dataset['title']}}</div><h2>{{player['club_name']}}</h2><p>{{player['primary_position'] or 'Unknown'}} · {{player['nationality'] or 'Nationality unavailable'}}</p>
<p class="muted">Age at dataset date: {{player['age'] if player['age'] is not none else 'unknown'}}</p></div>
<div class="box"><div class="muted small">Source overall rating</div><div class="stat">{{player['overall'] if player['overall'] is not none else '—'}}</div><p class="small muted">Rating source: {{player['source_name'] or 'Unavailable'}} · PES rating not yet mapped</p></div>
</div>
<div class="box" style="margin-top:14px"><div class="muted small">Prototype in-game transfer valuation · {{model_version}}</div><div class="stat">{{player['value_label']}}</div><p class="muted small">Fictional model, not a real transfer fee, verified market value, offer, salary or prediction of potential.</p></div>
<h2>Imported reference attributes</h2>
<div class="box">{% for key,label,value in attrs %}
<div style="display:flex;align-items:center;gap:14px;margin:12px 0">
<span style="width:95px">{{label}}</span><div class="bar"><div class="fill" style="width:{{value if value is not none else 0}}%"></div></div><b style="min-width:28px;text-align:right">{{value if value is not none else '—'}}</b></div>{% endfor %}</div>
<h2>Data provenance</h2><div class="box">
<p>Squad assignment: {{player['evidence']}} · {{player['verification_status']}}</p>
<p>EA reference ID: {{player['external_player_id'] or 'Unavailable'}}</p>
<p>Reference edition: {{player['edition'] or 'Unavailable'}} · snapshot {{player['snapshot_date'] or 'Unknown'}}</p>
<p><a href="{{player['source_url']}}" target="_blank" rel="noopener noreferrer">Reference dataset ↗</a></p>
<p class="muted">Potential, salary, contract, transfer value and PES player ID are not yet independently verified.</p></div>
{% endif %}
</main></body></html>"""


def initialize_catalog(conn):
    conn.executescript(SCHEMA)
    conn.execute("""INSERT OR IGNORE INTO world_datasets
        (dataset_id, season_id, title, source_label, source_date, status, is_career_active)
        VALUES ('england-2026-27-fc27','2026/27','England 2026/27','EA FC 27 + FPL snapshots','2026-09-12','review',0)""")
    key = "england-2026-27-fc27"
    # Materialize once. Future imports have their own dataset_id and are never
    # merged into this or into career data by a browsing request.
    exists = conn.execute("SELECT COUNT(*) FROM world_dataset_entries WHERE dataset_id=?", (key,)).fetchone()[0]
    if not exists:
        conn.execute("""INSERT INTO world_dataset_entries(dataset_id,competition_id,club_id)
            SELECT ?,competition_id,club_id FROM world_entries WHERE season_id='2026/27'""", (key,))
        conn.execute("""INSERT INTO world_dataset_rosters(dataset_id,player_id,club_id,evidence,verification_status)
            SELECT ?,player_id,club_id,registration_source,verification_status
            FROM world_rosters WHERE season_id='2026/27'""", (key,))
    ratings_present = conn.execute(
        "SELECT COUNT(*) FROM world_dataset_ratings WHERE dataset_id=?", (key,)).fetchone()[0]
    if not ratings_present:
        conn.execute("""INSERT INTO world_dataset_ratings
            (dataset_id,player_id,source_name,source_edition,source_date,external_player_id,
             overall,pace,shooting,passing,dribbling,defending,physicality)
            SELECT ?,x.player_id,x.source_name,x.edition,x.snapshot_date,x.external_player_id,
                   x.overall,x.pace,x.shooting,x.passing,x.dribbling,x.defending,x.physicality
            FROM world_external_ratings x
            JOIN world_dataset_rosters r ON r.player_id=x.player_id AND r.dataset_id=?
            WHERE x.source_name='EA FC 27' AND x.edition='fc27'""", (key,key))
    conn.commit()


def get_dataset(conn, value):
    if value:
        dataset = conn.execute("SELECT * FROM world_datasets WHERE dataset_id=?", (value,)).fetchone()
        if dataset is None:
            abort(404)
    else:
        dataset = conn.execute("SELECT * FROM world_datasets WHERE dataset_id='england-2026-27-fc27'").fetchone()
    if dataset is None:
        abort(404)
    return dataset


def age_on(birth_date, when):
    if not birth_date or not when:
        return None
    try:
        birthday = date.fromisoformat(birth_date)
        reference = date.fromisoformat(when)
        return reference.year-birthday.year-((reference.month,reference.day)<(birthday.month,birthday.day))
    except ValueError:
        return None


def create_explorer_blueprint(db_path):
    bp = Blueprint("world_explorer", __name__)
    def connect():
        # Reuse the legacy 2026/27 seed once, then browse immutable snapshots.
        from world_v2 import initialize_world
        db = sqlite3.connect(str(db_path))
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        initialize_world(db)
        initialize_catalog(db)
        return db

    def view(db, dataset, mode, title, **kwargs):
        options = db.execute("SELECT * FROM world_datasets ORDER BY season_id DESC,dataset_id").fetchall()
        return render_template_string(TEMPLATE, dataset=dataset, datasets=options,
                                      mode=mode, title=title, **kwargs)

    @bp.get("/world/explore")
    def index():
        with connect() as db:
            dataset=get_dataset(db,request.args.get("dataset"))
            leagues=db.execute("""SELECT c.competition_id,c.name,c.tier,COUNT(e.club_id) clubs
              FROM world_competitions c JOIN world_dataset_entries e
              ON e.competition_id=c.competition_id AND e.dataset_id=?
              GROUP BY c.competition_id ORDER BY c.tier""",(dataset["dataset_id"],)).fetchall()
            return view(db,dataset,"index","Football World · Squad Explorer",leagues=leagues)

    @bp.get("/world/explore/league/<cid>")
    def league(cid):
        with connect() as db:
            dataset=get_dataset(db,request.args.get("dataset"))
            comp=db.execute("SELECT * FROM world_competitions WHERE competition_id=?",(cid,)).fetchone()
            if comp is None:
                abort(404)
            clubs=db.execute("""SELECT c.club_id,c.name,COUNT(r.player_id) roster_size
              FROM world_dataset_entries e JOIN world_clubs c ON c.club_id=e.club_id
              LEFT JOIN world_dataset_rosters r ON r.dataset_id=e.dataset_id AND r.club_id=c.club_id
              WHERE e.dataset_id=? AND e.competition_id=?
              GROUP BY c.club_id ORDER BY c.name""",(dataset["dataset_id"],cid)).fetchall()
            return view(db,dataset,"league",comp["name"],clubs=clubs)

    @bp.get("/world/explore/club/<int:club_id>")
    def club(club_id):
        with connect() as db:
            dataset=get_dataset(db,request.args.get("dataset"))
            team=db.execute("""SELECT c.name,e.competition_id,w.name competition_name
              FROM world_dataset_entries e JOIN world_clubs c ON c.club_id=e.club_id
              JOIN world_competitions w ON w.competition_id=e.competition_id
              WHERE e.dataset_id=? AND e.club_id=?""",(dataset["dataset_id"],club_id)).fetchone()
            if team is None:
                abort(404)
            positions=[x[0] for x in db.execute("""SELECT DISTINCT p.primary_position
              FROM world_dataset_rosters r JOIN world_players p ON p.player_id=r.player_id
              WHERE r.dataset_id=? AND r.club_id=? AND p.primary_position IS NOT NULL
              ORDER BY p.primary_position""",(dataset["dataset_id"],club_id)).fetchall()]
            chosen=request.args.get("position","")
            if chosen not in positions:
                chosen=""
            q=request.args.get("q","").strip()[:80]
            selected_sort=request.args.get("sort","rating")
            sorts=[("rating","Overall (highest)"),("name","Player name"),("age_young","Age (youngest)"),("age_old","Age (oldest)")]
            if selected_sort not in dict(sorts):
                selected_sort="rating"
            rows=db.execute("""SELECT p.player_id,p.full_name,p.birth_date,p.primary_position,
                r.verification_status,x.overall
                FROM world_dataset_rosters r JOIN world_players p ON p.player_id=r.player_id
                LEFT JOIN world_dataset_ratings x ON x.player_id=p.player_id
                   AND x.dataset_id=r.dataset_id
                WHERE r.dataset_id=? AND r.club_id=? AND (?='' OR p.primary_position=?)
                  AND (?='' OR p.full_name LIKE '%'||?||'%')
            """,(dataset["dataset_id"],club_id,chosen,chosen,q,q)).fetchall()
            players=[]
            for p in rows:
                age=age_on(p["birth_date"],dataset["source_date"])
                players.append(dict(p,age=age,value_label=display_gbp(model_value(p["overall"],age,p["primary_position"]))))
            if selected_sort=="name":
                players.sort(key=lambda p:p["full_name"].casefold())
            elif selected_sort=="age_young":
                players.sort(key=lambda p:(p["age"] is None,p["age"] if p["age"] is not None else 0,p["full_name"]))
            elif selected_sort=="age_old":
                players.sort(key=lambda p:(p["age"] is None,-p["age"] if p["age"] is not None else 0,p["full_name"]))
            else:
                players.sort(key=lambda p:(p["overall"] is None,-p["overall"] if p["overall"] is not None else 0,p["full_name"]))
            return view(db,dataset,"club",team["name"],team=team,club_id=club_id,players=players,
                total=db.execute("SELECT COUNT(*) FROM world_dataset_rosters WHERE dataset_id=? AND club_id=?",
                    (dataset["dataset_id"],club_id)).fetchone()[0],
                positions=positions,selected_position=chosen,selected_sort=selected_sort,sorts=sorts,q=q)

    @bp.get("/world/explore/player/<int:player_id>")
    def player(player_id):
        with connect() as db:
            dataset=get_dataset(db,request.args.get("dataset"))
            p=db.execute("""SELECT p.*,r.club_id,c.name club_name,r.evidence,r.verification_status,
                 x.overall,x.pace,x.shooting,x.passing,x.dribbling,x.defending,x.physicality,
                 x.external_player_id,x.source_name,x.source_edition AS edition,x.source_date AS snapshot_date,
                 COALESCE(p.source_url,'https://github.com/LakshmiKanth11/EA_FC_ANALYSIS') source_url
                 FROM world_dataset_rosters r
                 JOIN world_players p ON p.player_id=r.player_id
                 JOIN world_clubs c ON c.club_id=r.club_id
                 LEFT JOIN world_dataset_ratings x ON x.player_id=p.player_id
                     AND x.dataset_id=r.dataset_id
                 WHERE r.dataset_id=? AND r.player_id=?""",(dataset["dataset_id"],player_id)).fetchone()
            if p is None:
                abort(404)
            age=age_on(p["birth_date"],dataset["source_date"])
            person=dict(p,age=age,value_label=display_gbp(model_value(p["overall"],age,p["primary_position"])))
            attrs=[(k,label,p[k]) for k,label in
                   [("pace","Pace"),("shooting","Shooting"),("passing","Passing"),
                    ("dribbling","Dribbling"),("defending","Defending"),("physicality","Physicality")]]
            return view(db,dataset,"player",p["full_name"],player=person,attrs=attrs,model_version=MODEL_VERSION)
    return bp

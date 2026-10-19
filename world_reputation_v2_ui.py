"""Read-only audit and cross-pyramid comparison screens for v2 reputation."""
import sqlite3
from flask import Blueprint, abort, render_template_string, request
from world_explorer import initialize_catalog, get_dataset
from world_reputation_v2 import MODEL_VERSION, initialize_pyramid

CSS="""body{margin:0;background:#111a25;color:#edf5ff;font:15px system-ui,-apple-system,Segoe UI,sans-serif}
header{background:#1c2c3b;border-bottom:1px solid #3d5367;padding:17px 23px}
main{max-width:1180px;margin:26px auto;padding:0 20px 65px}h1{margin:5px 0}h2{margin-top:27px}
a{color:#a8d5ff;text-decoration:none}a:hover{text-decoration:underline}.muted{color:#b6c6d6}
.notice{padding:16px;background:#24384b;border-left:3px solid #89b9e5;margin:22px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(195px,1fr));gap:12px}
.card{padding:17px;background:#1c2d3f;border:1px solid #40586c;border-radius:8px}
.score{font-size:2rem;font-weight:750}.sub{font-size:.85rem;color:#acbece}
table{width:100%;border-collapse:collapse;margin:16px 0}
td,th{padding:11px 10px;border-bottom:1px solid #394e62;text-align:left}th{color:#b6cddd;font-size:.85rem}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
button,select{padding:9px;background:#263b50;color:#edf4fc;border:1px solid #547089;border-radius:5px}
form{margin:19px 0;display:flex;gap:11px;flex-wrap:wrap;align-items:center}
footer{color:#a9b9c9;margin-top:30px;font-size:.85rem}
"""
PAGE="""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{title}} · Reputation Audit</title><style>"""+CSS+"""</style></head>
<body><header><a href="/world/explore">← Squad Explorer</a> ·
<a href="/world/play">Transfer Desk</a> ·
<a href="/world/reputations/jobs?dataset={{dataset['dataset_id']}}">Job Eligibility</a> ·
<a href="/world/reputations/progression?dataset={{dataset['dataset_id']}}">Season Preview</a> ·
<a href="/world/reputations/prestige?dataset={{dataset['dataset_id']}}">Prestige Evidence</a> ·
<a href="/world/reputations/legacy?dataset={{dataset['dataset_id']}}">Old model (v1)</a></header>
<main><h1>{{title}}</h1><p class="muted">Season dataset: {{dataset['title']}} · {{version}}</p>
<div class="notice"><b>Simulation model, not verified real-world reputation.</b>
The revised scale uses top-16 squad ability on one shared rating scale across all English
divisions, with modest division context and a small league-relative squad-strength indicator.
Historical club prestige, actual league position and individual player intentions remain unknown.
The labels below are <b>not</b> forecasts of promotion or relegation.</div>
{% if mode=='overview' %}
<form method="get"><label for="dataset">Starting season</label><select id="dataset" name="dataset">
{% for d in datasets %}<option value="{{d['dataset_id']}}" {% if d['dataset_id']==dataset['dataset_id'] %}selected{% endif %}>{{d['title']}}</option>{% endfor %}</select>
<label for="league">Division</label><select id="league" name="league"><option value="">All four</option>
{% for l in leagues %}<option value="{{l['competition_id']}}" {% if selected_league==l['competition_id'] %}selected{% endif %}>{{l['name']}}</option>{% endfor %}</select>
<button>Browse</button></form>
<div class="grid">{% for l in leagues %}
<div class="card"><b>{{l['name']}}</b><p class="sub">{{l['teams_rated']}}/{{l['teams_total']}} clubs with usable source ratings</p>
<div class="score">{{'%.1f'|format(l['median_squad_average']) if l['median_squad_average'] is not none else '—'}}</div>
<div class="sub">Median top-16 OVR · Context adjustment {{'%+d'|format(l['context_adjustment'])}}</div></div>
{% endfor %}</div>
<h2>Compare across divisions</h2>
<p><a href="/world/reputations/compare?dataset={{dataset['dataset_id']}}&a=Hull+City&b=West+Ham+United">
Hull City vs West Ham United</a> ·
<a href="/world/reputations/compare?dataset={{dataset['dataset_id']}}&a=Leicester+City&b=Bolton+Wanderers">
Leicester City vs Bolton Wanderers</a> ·
<a href="/world/reputations/compare?dataset={{dataset['dataset_id']}}&a=Burton+Albion&b=Salford+City">
Burton Albion vs Salford City</a></p>
<h2>Club sporting appeal · 0–100</h2>
<table><tr><th>Club</th><th>Division</th><th class="num">Sporting appeal</th>
<th class="num">Top-16 OVR</th><th class="num">Relative squad rank</th><th>Squad strength indicator</th><th>Source quality</th></tr>
{% for c in clubs %}<tr>
<td><a href="/world/reputations/v2/club/{{c['club_id']}}?dataset={{dataset['dataset_id']}}">{{c['name']}}</a></td>
<td>{{c['competition_name']}}</td>
<td class="num"><b>{{c['sporting_appeal'] if c['sporting_appeal'] is not none else 'Unknown'}}</b></td>
<td class="num">{{'%.2f'|format(c['squad_average']) if c['squad_average'] is not none else '—'}}</td>
<td class="num">{{c['strength_rank'] if c['strength_rank'] is not none else '—'}} / {{c['competition_size']}}</td>
<td>{{c['prospects_label']}}</td><td>{{c['confidence']}}</td>
</tr>{% endfor %}</table>
{% elif mode=='club' %}
<p><a href="/world/reputations?dataset={{dataset['dataset_id']}}">← All 92 clubs</a></p>
<div class="grid">
<div class="card"><div class="sub">Sporting appeal</div><div class="score">{{club['sporting_appeal'] if club['sporting_appeal'] is not none else 'Unknown'}}</div></div>
<div class="card"><div class="sub">Top 16 source overall average</div><div class="score">{{'%.2f'|format(club['squad_average']) if club['squad_average'] is not none else '—'}}</div></div>
<div class="card"><div class="sub">Relative squad strength</div><div class="score">{{club['strength_rank'] if club['strength_rank'] is not none else '—'}} / {{club['competition_size']}}</div></div>
<div class="card"><div class="sub">Institutional prestige</div><div class="score">Unknown</div></div></div>
<h2>Score explanation</h2>
<p><b>Shared top-16 squad rating scale:</b> {{club['strength_component'] if club['strength_component'] is not none else 'Unknown'}}<br>
<b>Division context:</b> {{'%+d'|format(club['division_adjustment'])}}<br>
<b>Relative squad-strength indicator:</b> {{'%+d'|format(club['prospects_adjustment'])}}<br>
<b>Modelled sporting appeal:</b> {{club['sporting_appeal'] if club['sporting_appeal'] is not none else 'Not assessed'}} / 100</p>
<p><b>Strength indicator:</b> {{club['prospects_label']}}</p>
<div class="notice">Ranking is by source squad ratings <b>within the division</b>, not by points, form, betting odds or actual league position. A promoted club may have a lower institutional prestige despite a competitive squad.
The above is a starting estimate and will not silently rewrite an existing career.</div>
<p class="muted">Source: {{club['source_label']}} · snapshot {{club['source_date'] or 'unknown'}}.
{% if membership_url %}<a href="{{membership_url}}" target="_blank" rel="noopener noreferrer">Division source</a>.{% endif %}
{% if ratings_url %}<a href="{{ratings_url}}" target="_blank" rel="noopener noreferrer">Rating source</a>.{% endif %}</p>
{% elif mode=='compare' %}
<p><a href="/world/reputations?dataset={{dataset['dataset_id']}}">← All clubs</a></p>
<form method="get"><input type="hidden" name="dataset" value="{{dataset['dataset_id']}}">
<label for="a">First club</label><select name="a" id="a">{% for c in choices %}
<option value="{{c['name']}}" {% if c['name']==first['name'] %}selected{% endif %}>{{c['name']}}</option>{% endfor %}</select>
<label for="b">Second club</label><select name="b" id="b">{% for c in choices %}
<option value="{{c['name']}}" {% if c['name']==second['name'] %}selected{% endif %}>{{c['name']}}</option>{% endfor %}</select>
<button>Compare</button></form>
<div class="grid">{% for c in comparison %}
<div class="card"><h2>{{c['name']}}</h2><p class="muted">{{c['competition_name']}}</p>
<div class="score">{{c['sporting_appeal'] if c['sporting_appeal'] is not none else 'Unknown'}} <span class="sub">/100</span></div>
<p>Source squad mean: {{'%.2f'|format(c['squad_average']) if c['squad_average'] is not none else '—'}}</p>
<p>Division context: {{'%+d'|format(c['division_adjustment'])}}</p>
<p>Relative squad indicator: {{'%+d'|format(c['prospects_adjustment'])}}</p>
<p class="sub">{{c['prospects_label']}}</p></div>
{% endfor %}</div>
<h2>What the gap means</h2>
{% if difference is not none %}
<p><b>{{gap}} points</b> between the two clubs on the provisional sporting-appeal scale.
This reflects squad strength and a small division context—not the probability of a transfer.
The stronger number is not guaranteed to attract every player.</p>
{% else %}<p>At least one club lacks usable source ratings. No comparison is asserted.</p>{% endif %}
<p class="muted">The career engine also considers an individual player's current club, role promises,
and provisional agent demands. Historic prestige remains unassessed.</p>
{% endif %}
<footer>Version {{version}} · All scores are transparent game-design estimates.
Original v1 scores remain retained for comparison.
No club finance, career result, contract or PES registration is changed by browsing.</footer>
</main></body></html>"""


def create_pyramid_blueprint(db_path):
    bp=Blueprint("world_pyramid",__name__)

    def connect():
        from world_v2 import initialize_world
        db=sqlite3.connect(str(db_path))
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        initialize_world(db)
        initialize_catalog(db)
        initialize_pyramid(db)
        return db

    def ctx(db,ds,mode,title,**kwargs):
        return render_template_string(PAGE,title=title,version=MODEL_VERSION,
            dataset=ds,mode=mode,**kwargs)

    @bp.get("/world/reputations")
    def index():
        with connect() as db:
            ds=get_dataset(db,request.args.get("dataset"))
            options=db.execute("SELECT dataset_id,title FROM world_datasets ORDER BY season_id DESC").fetchall()
            leagues=db.execute("""SELECT s.*,c.name FROM world_pyramid_league_strength s
                JOIN world_competitions c ON c.competition_id=s.competition_id
                WHERE s.dataset_id=? AND s.model_version=? ORDER BY c.tier""",
                (ds["dataset_id"],MODEL_VERSION)).fetchall()
            selected=request.args.get("league","")
            if selected not in [c["competition_id"] for c in leagues]:selected=""
            clubs=db.execute("""SELECT r.*,c.name,w.name AS competition_name
                FROM world_pyramid_club_appeal r
                JOIN world_clubs c ON c.club_id=r.club_id
                JOIN world_competitions w ON w.competition_id=r.competition_id
                WHERE r.dataset_id=? AND r.model_version=?
                AND (?='' OR r.competition_id=?)
                ORDER BY r.sporting_appeal IS NULL,r.sporting_appeal DESC,c.name""",
                (ds["dataset_id"],MODEL_VERSION,selected,selected)).fetchall()
            return ctx(db,ds,"overview","Club & League Reputation Audit",
                datasets=options,leagues=leagues,selected_league=selected,clubs=clubs)

    @bp.get("/world/reputations/v2/club/<int:club_id>")
    def club(club_id):
        with connect() as db:
            ds=get_dataset(db,request.args.get("dataset"))
            row=db.execute("""SELECT r.*,c.name,w.name AS competition_name
                FROM world_pyramid_club_appeal r
                JOIN world_clubs c ON c.club_id=r.club_id
                JOIN world_competitions w ON w.competition_id=r.competition_id
                WHERE r.dataset_id=? AND r.model_version=? AND r.club_id=?""",
                (ds["dataset_id"],MODEL_VERSION,club_id)).fetchone()
            if not row:abort(404)
            membership=db.execute("""SELECT source_url FROM world_entries
                WHERE season_id=? AND club_id=?""",(ds["season_id"],club_id)).fetchone()
            ratings_url=None
            if ds["dataset_id"]=="england-2026-27-fc27":
                from world_fc27_english import SOURCE_URL
                ratings_url=SOURCE_URL
            return ctx(db,ds,"club",row["name"]+" · Reputation Breakdown",
                club=row,membership_url=membership[0] if membership else None,
                ratings_url=ratings_url)

    @bp.get("/world/reputations/compare")
    def compare():
        with connect() as db:
            ds=get_dataset(db,request.args.get("dataset"))
            choices=db.execute("""SELECT c.name,r.*
                FROM world_pyramid_club_appeal r
                JOIN world_clubs c ON c.club_id=r.club_id
                WHERE r.dataset_id=? AND r.model_version=? ORDER BY c.name""",
                (ds["dataset_id"],MODEL_VERSION)).fetchall()
            if not choices:abort(404)
            mapping={row["name"]:row for row in choices}
            a=request.args.get("a","Arsenal")
            b=request.args.get("b","Hull City")
            first=mapping.get(a,choices[0])
            second=mapping.get(b,choices[-1])
            records=[]
            for c in (first,second):
                league=db.execute("SELECT name FROM world_competitions WHERE competition_id=?",
                    (c["competition_id"],)).fetchone()
                records.append(dict(c,competition_name=league[0] if league else "Unknown"))
            diff=(records[0]["sporting_appeal"]-records[1]["sporting_appeal"]
                if all(c["sporting_appeal"] is not None for c in records) else None)
            return ctx(db,ds,"compare","Cross-Division Club Comparison",
                choices=choices,first=first,second=second,comparison=records,
                difference=diff,gap=abs(diff) if diff is not None else None)
    return bp

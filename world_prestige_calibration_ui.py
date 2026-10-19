"""Read-only editorial calibration for a documented 15-club prestige sample.

No score is written to approved reviews and no transfer/job logic consumes
a proposed number. The user can inspect/review source evidence before signoff.
"""
import sqlite3
from flask import Blueprint,abort,render_template_string,request

from world_explorer import get_dataset,initialize_catalog
from world_reputation_v2 import MODEL_VERSION as SPORT_MODEL,initialize_pyramid
from world_reputation_progression import initialize_progression
from world_prestige_calibration import (
    VERSION,DATASET_ID,CLUBS,DIMENSIONS,STADIUM_SOURCE,
    score_club,domestic_points,stadium_points,
)

STYLE="""body{margin:0;background:#101b28;color:#eef4fb;font:15px system-ui,-apple-system,Segoe UI,sans-serif}
header{background:#1c2c40;padding:17px 24px;border-bottom:1px solid #3b5065}
a{color:#a2d4ff;text-decoration:none}a:hover{text-decoration:underline}
main{margin:22px auto;max-width:1170px;padding:0 18px 60px}
h1{margin:4px 0 10px}h2{margin:26px 0 10px}
.small{font-size:.85rem}.muted{color:#b0c1d3}.num{text-align:right;font-variant-numeric:tabular-nums}
.notice{padding:16px 18px;border-left:3px solid #8cc7ef;background:#233a52;margin:19px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.card{border:1px solid #3b546a;background:#192d41;border-radius:9px;padding:16px}
.big{font-size:2rem;font-weight:730;letter-spacing:-.02em}
label{font-size:.87rem;color:#becee0}select,button{padding:8px 10px;border:1px solid #567089;background:#254158;color:white;border-radius:4px}
table{width:100%;border-collapse:collapse;margin:12px 0 24px}td,th{border-bottom:1px solid #344b61;padding:10px 9px;text-align:left;vertical-align:top}
th{color:#bed0e0;font-size:.86rem}td.num,th.num{text-align:right}
.bar{height:9px;background:#33495d;border-radius:20px;overflow:hidden;margin-top:7px}
.bar span{height:100%;display:block;background:#83bde7}
.value{font-weight:700}.prose{line-height:1.55}
footer{margin-top:25px;color:#aabbd0;font-size:.85rem}
"""
PAGE="""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{title}} · PES Clubs Challenge</title><style>"""+STYLE+"""</style></head>
<body><header><a href="/world/reputations">← Sporting appeal</a> ·
<a href="/world/reputations/prestige">Prestige evidence</a> ·
<a href="/world/reputations/prestige/calibration">Original 15</a> ·
<a href="/world/reputations/prestige/all">All 92 clubs</a> ·
<a href="/world/play">Development transfer desk</a></header><main>
<h1>{{title}}</h1>
<p class="muted">Historical prestige calibration · {{version}} · selected dataset: {{dataset['title']}}</p>
<div class="notice"><b>Review-only draft — not approved club prestige.</b>
The facts and source links below support the historical narrative; the
numerical scoring weights and editorial components are proposed <b>gameplay decisions</b>,
not facts endorsed by those publishers.
No calibration score currently affects transfers, agent responses, job opportunities,
existing saves or PES registrations. Sporting appeal remains a separate measure.</div>
{% if mode=='list' %}
{% if no_data %}
<p>No calibrated prestige sample exists for this starting-season dataset.
A new historical review is needed; 2026/27 prestige must not be copied into a different year.</p>
{% else %}
<div class="grid">
<div class="card"><div class="muted">Clubs included</div><div class="big">{{rows|length}} / 92</div></div>
<div class="card"><div class="muted">English divisions covered</div><div class="big">4</div></div>
<div class="card"><div class="muted">Individually approved scores</div><div class="big">{{approved_count}}</div></div>
<div class="card"><div class="muted">Pending gameplay sign-off</div><div class="big">{{pending_count}}</div></div></div>
<h2>How this first calibration works</h2>
<p class="prose">The rebalanced rubric gives greater weight to long-term league
standing and continuity, while major domestic honours remain limited to
<b>top-flight championships, FA Cups and League Cups</b>.
Lower-division titles and promotions can inform the <b>history narrative</b>
but do not receive separate trophy points.
Stadium capacity is a rough <b>infrastructure-scale proxy</b>, not attendance
or direct evidence of fanbase size.
European heritage, historical standing and club identity are editorial
assessments that still require review.</p>
<p class="muted small">Version 2 adjusts the five category weights without
changing the original underlying European and historical editorial judgements.
Consequently, clubs like Hull can gain history weight without an ad hoc manual
increase to their own rating.</p>
<div class="grid">{% for key,dimension in dimensions.items() %}
<div class="card"><div class="muted">{{dimension[0]}}</div>
<div class="big">{{dimension[1]}} <span class="small muted">maximum</span></div>
</div>{% endfor %}</div>
<h2>Compare proposed historical prestige with current sporting appeal</h2>
<form method="get"><input type="hidden" name="dataset" value="{{dataset['dataset_id']}}">
<label for="league">Division</label>
<select id="league" name="league"><option value="">All four divisions</option>
{% for code,label in league_names.items() %}
<option value="{{code}}" {% if selected_league==code %}selected{% endif %}>{{label}}</option>
{% endfor %}</select><button type="submit">Apply</button></form>
<table><thead><tr><th>Club</th><th>2026/27 division</th>
<th class="num">Proposed prestige</th><th class="num">Current sporting appeal</th>
<th class="num">Domestic</th><th class="num">Europe</th><th class="num">History</th>
<th class="num">Scale</th><th class="num">Identity</th><th>Review status</th>
</tr></thead><tbody>{% for c in rows %}
<tr><td><a href="/world/reputations/prestige/calibration/{{c['club_id']}}?dataset={{dataset['dataset_id']}}">{{c['name']}}</a></td>
<td>{{c['league_name']}}</td>
<td class="num value">{{c['score']}}</td>
<td class="num">{{c['sporting_appeal'] if c['sporting_appeal'] is not none else 'Unknown'}}</td>
<td class="num">{{c['domestic']}}</td><td class="num">{{c['europe']}}</td>
<td class="num">{{c['longevity']}}</td><td class="num">{{c['scale']}}</td>
<td class="num">{{c['identity']}}</td>
<td>{{'Approved separately' if c['approved_score'] is not none else 'Proposed only'}}</td>
</tr>{% endfor %}</tbody></table>
<p class="muted small">Scores shown above are provisional proposals even when an
independently reviewed rating exists; detail screens show that reviewed rating
separately. No missing evidence is interpreted as proof of zero achievements.</p>
{% endif %}
{% elif mode=='detail' %}
<p><a href="/world/reputations/prestige/calibration?dataset={{dataset['dataset_id']}}">← All 15 calibration clubs</a>
 · <a href="/world/reputations/v2/club/{{club['club_id']}}?dataset={{dataset['dataset_id']}}">Current sporting-appeal breakdown</a></p>
<div class="grid">
<div class="card"><div class="muted">Proposed historical prestige</div><div class="big">{{club['score']}} / 100</div></div>
<div class="card"><div class="muted">Starting sporting appeal</div>
<div class="big">{{club['sporting_appeal'] if club['sporting_appeal'] is not none else 'Unknown'}}</div></div>
<div class="card"><div class="muted">League in current dataset</div><div class="big" style="font-size:1.3rem">{{club['league_name']}}</div></div>
<div class="card"><div class="muted">Approved institutional prestige</div>
<div class="big">{{club['approved_score'] if club['approved_score'] is not none else 'Not yet'}}</div></div></div>
<h2>What the proposal is trying to capture</h2>
<p class="prose">{{club['heritage']}}</p>
<p class="prose"><b>Calibration judgement:</b> {{club['rationale']}}</p>
<h2>Detailed 100-point decomposition</h2>
{% for key,dimension in dimensions.items() %}
<div class="card" style="margin:9px 0"><div style="display:flex;justify-content:space-between;gap:14px">
<b>{{dimension[0]}}</b><span class="value">{{club[key]}} / {{dimension[1]}}</span></div>
<div class="bar"><span style="width:{{(club[key] / dimension[1] * 100)|round(2)}}%"></span></div></div>
{% endfor %}
<h2>Reproducible inputs and outstanding judgement</h2>
<table><tr><th>Input</th><th>Used in this proposal</th></tr>
<tr><td>Top-flight league titles</td><td>{{club['league_titles']}}</td></tr>
<tr><td>FA Cup wins</td><td>{{club['fa_cups']}}</td></tr>
<tr><td>League Cup wins</td><td>{{club['league_cups']}}</td></tr>
<tr><td>Home venue capacity proxy</td><td>{{'{:,}'.format(club['stadium'])}}</td></tr>
<tr><td>Historical continuity</td><td>Original editorial input {{club['raw_longevity']}} / 20,
weighted to {{club['longevity']}} / 35 · <b>requires reviewer agreement</b></td></tr>
<tr><td>European profile</td><td>Original editorial input {{club['raw_europe']}} / 20,
weighted to {{club['europe']}} / 15 · <b>requires reviewer agreement</b></td></tr>
<tr><td>Cultural footprint</td><td>Editorial {{club['identity']}} / 10 · <b>requires reviewer agreement</b></td></tr>
</table>
<p class="muted small">Proposed domestic silverware score:
{{club['domestic']}} / 25, calculated exclusively from top-flight championships,
FA Cups and League Cups, with logarithmic
diminishing returns. Stadium scale:
{{club['scale']}} / 15 based on a broad capacity bracket.
The selected venue figures are approximate reference capacities and may change.</p>
<h2>Source evidence to inspect</h2>
<table><thead><tr><th>Category</th><th>What the reference supports</th><th>Source</th></tr></thead>
<tbody>{% for category,label,url,claim in club['sources'] %}
<tr><td>{{category}}</td><td>{{claim}}</td>
<td><a href="{{url}}" target="_blank" rel="noopener noreferrer">{{label}} ↗</a></td></tr>
{% endfor %}
<tr><td>infrastructure</td><td>Approximate ground capacity used for the scale component.</td>
<td><a href="{{club['stadium_url']}}" target="_blank" rel="noopener noreferrer">Stadium capacity reference ↗</a></td></tr>
</tbody></table>
<div class="notice">Next step is a <b>human sign-off of the rubric</b>, including
rechecking any disputed honours or capacity references. Only then should a
reviewer explicitly approve an institutional prestige score through the
existing evidence-gated process. This page never does that automatically.</div>
{% endif %}
<footer>Calibration model {{version}} is independent of
career results, temporary cup/European participation bonuses, and future player
or managerial decisions until reviewed and connected.</footer>
</main></body></html>"""

LEAGUE_NAMES={
    "ENG1":"Premier League",
    "ENG2":"Championship",
    "ENG3":"League One",
    "ENG4":"League Two",
}
# Source listing for capacity where general guide does not contain an entry.
STADIUM_OVERRIDES={
    "Wrexham":"https://footballgroundguide.com/leagues/conference/conference-premier/wrexham-afc-racecourse-ground.html",
    "AFC Wimbledon":"https://footballgroundguide.com/leagues/england/league-one/plough-lane-afc-wimbledon.html",
    "Grimsby Town":"https://footballgroundguide.com/leagues/england/league-two/blundell-park-grimsby-town.html",
    "York City":"https://footballgroundguide.com/leagues/york-city-stadium.html",
    "Salford City":"https://footballgroundguide.com/leagues/england/league-two/salford-city-moor-lane.html",
}


def create_calibration_blueprint(db_path):
    bp=Blueprint("world_prestige_calibration",__name__)

    def connect():
        from world_v2 import initialize_world
        db=sqlite3.connect(str(db_path))
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        initialize_world(db)
        initialize_catalog(db)
        initialize_pyramid(db)
        initialize_progression(db)
        return db

    def build_rows(db, dataset_id):
        actual=db.execute("""SELECT c.club_id,c.name,e.competition_id,
            s.sporting_appeal,p.prestige_score
            FROM world_dataset_entries e
            JOIN world_clubs c ON c.club_id=e.club_id
            LEFT JOIN world_pyramid_club_appeal s
              ON s.dataset_id=e.dataset_id AND s.model_version=?
             AND s.club_id=e.club_id
            LEFT JOIN world_reputation_prestige_reviews p
              ON p.dataset_id=e.dataset_id AND p.club_id=e.club_id
            WHERE e.dataset_id=?""",(SPORT_MODEL,dataset_id)).fetchall()
        lookups={r["name"]:r for r in actual}
        out=[]
        for c in CLUBS:
            member=lookups.get(c["name"])
            if not member:
                continue
            if member["competition_id"]!=c["league"]:
                raise ValueError("Calibration club membership changed; do not copy old-season ratings")
            scored=score_club(c)
            out.append(dict(c,**scored,raw_europe=c["europe"],raw_longevity=c["longevity"],
                club_id=member["club_id"],
                sporting_appeal=member["sporting_appeal"],
                approved_score=member["prestige_score"],
                league_name=LEAGUE_NAMES[c["league"]],
                stadium_url=STADIUM_OVERRIDES.get(c["name"],STADIUM_SOURCE)))
        return out

    def view(db,dataset,title,mode,**kwargs):
        return render_template_string(
            PAGE,title=title,dataset=dataset,mode=mode,version=VERSION,
            dimensions=DIMENSIONS,league_names=LEAGUE_NAMES,**kwargs)

    @bp.get("/world/reputations/prestige/calibration")
    def index():
        with connect() as db:
            dataset=get_dataset(db,request.args.get("dataset"))
            if dataset["dataset_id"]!=DATASET_ID:
                return view(db,dataset,"Historical Prestige Calibration",mode="list",
                            rows=[],no_data=True,selected_league="",
                            approved_count=0,pending_count=0)
            rows=build_rows(db,DATASET_ID)
            selected_league=request.args.get("league","")
            if selected_league not in LEAGUE_NAMES:selected_league=""
            filtered=[c for c in rows if not selected_league or c["league"]==selected_league]
            filtered.sort(key=lambda c:(int(c["league"][-1]),-c["score"],c["name"]))
            return view(db,dataset,"15-club Prestige Calibration",mode="list",
                no_data=False,rows=filtered,selected_league=selected_league,
                approved_count=sum(c["approved_score"] is not None for c in rows),
                pending_count=sum(c["approved_score"] is None for c in rows))

    @bp.get("/world/reputations/prestige/calibration/<int:club_id>")
    def detail(club_id):
        with connect() as db:
            dataset=get_dataset(db,request.args.get("dataset"))
            if dataset["dataset_id"]!=DATASET_ID:abort(404)
            row=next((c for c in build_rows(db,DATASET_ID) if c["club_id"]==club_id),None)
            if row is None:abort(404)
            return view(db,dataset,row["name"]+" · Prestige Calibration",mode="detail",club=row)

    return bp

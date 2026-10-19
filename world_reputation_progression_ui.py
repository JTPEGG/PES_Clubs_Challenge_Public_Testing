"""Read-only preview and evidenced-career audit for reputation progression.

The scenario lab is intentionally GET-only: it MUST NOT approve fabricated
results or persist speculative career updates.
"""
import os
import sqlite3
from flask import Blueprint,abort,redirect,render_template_string,request
from itsdangerous import URLSafeTimedSerializer,BadSignature,SignatureExpired

from world_explorer import initialize_catalog,get_dataset
from world_reputation_v2 import MODEL_VERSION,initialize_pyramid
from world_reputation_progression import (
    PROGRESSION_VERSION,initialize_progression,preview_progression,
    current_career_appeal,latest_season_index
)

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{title}} · PES Clubs Challenge Development</title>
<style>
body{margin:0;background:#111a25;color:#eef5fb;font:15px system-ui,-apple-system,Segoe UI,sans-serif}
header{padding:17px 23px;background:#1c2c3b;border-bottom:1px solid #3d5367}
main{max-width:1100px;margin:25px auto;padding:0 20px 65px}
a{color:#a8d5ff;text-decoration:none}a:hover{text-decoration:underline}
h1{margin:5px 0}h2{margin:26px 0 12px}.muted{color:#b5c6d5}
.notice{background:#253a50;border-left:3px solid #82b9e7;padding:16px;margin:18px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:13px}
.card{background:#1e3042;border:1px solid #405a72;padding:16px;border-radius:9px}
.metric{font-size:1.8rem;font-weight:750}
table{width:100%;border-collapse:collapse}th,td{padding:11px;border-bottom:1px solid #384c60;text-align:left}
th{font-size:.85rem;color:#bed0e0}
select,input,button{background:#293d52;color:#eef5fb;padding:9px 10px;border:1px solid #5d7589;border-radius:5px}
button{cursor:pointer;background:#2d5d80}form{display:flex;flex-wrap:wrap;align-items:end;gap:10px;margin:18px 0}
label{display:block;font-size:.87rem;color:#c2d0dc;margin:0 0 5px}
footer{font-size:.85rem;color:#a3b7c8;margin-top:35px}
</style></head><body><header>
<a href="/world/reputations">← Reputation Audit</a> ·
<a href="/world/reputations/progression">Season Preview</a> ·
<a href="/world/reputations/prestige">Prestige Evidence</a> ·
<a href="/world/reputations/prestige/calibration">15-club calibration</a> ·
<a href="/world/reputations/prestige/all">All 92 prestige proposals</a> ·
<a href="/world/play">Career Desk</a></header><main>
<h1>{{title}}</h1>
<p class="muted">Development sandbox · {{model_version}} · no changes to active PES squad registrations</p>
{% if mode=='preview' %}
<div class="notice"><b>Hypothetical scenario only.</b> Select a club and an imagined
season finish to see how promotion, relegation and performance could affect
sporting appeal. The preview never records those results or changes a career.
Institutional prestige is not guessed from squad quality. Champions League qualification
is explicitly selected here rather than inferred from third place, because
qualification allocations can vary by season.</div>
<p><a href="/world/reputations/progression?position=3&continental=champions_league">
Try Hull finishing third and qualifying for the Champions League →</a></p>
<form method="get"><div><label for="dataset">Starting-season dataset</label>
<select id="dataset" name="dataset">{% for d in datasets %}
<option value="{{d['dataset_id']}}" {% if d['dataset_id']==dataset['dataset_id'] %}selected{% endif %}>{{d['title']}}</option>
{% endfor %}</select></div>
<div><label for="club">Club</label><select id="club" name="club">
{% for c in clubs %}<option value="{{c['club_id']}}" {% if c['club_id']==selected_club %}selected{% endif %}>{{c['name']}}</option>{% endfor %}</select></div>
<div><label for="destination">Division next season</label><select id="destination" name="destination">
{% for c in competitions %}<option value="{{c['competition_id']}}" {% if c['competition_id']==next_comp %}selected{% endif %}>{{c['name']}}</option>{% endfor %}</select></div>
<div><label for="position">Hypothetical league finish</label>
<input id="position" name="position" type="number" value="{{finish}}" min="1" max="30" required style="width:80px"></div>
<div><label for="domestic_cup">Domestic cup achievement</label>
<select id="domestic_cup" name="domestic_cup">
{% for value,label in domestic_cup_choices %}
<option value="{{value}}" {% if value==domestic_cup %}selected{% endif %}>{{label}}</option>
{% endfor %}</select></div>
<div><label for="continental">European competition next season</label>
<select id="continental" name="continental">
{% for value,label in european_choices %}
<option value="{{value}}" {% if value==continental %}selected{% endif %}>{{label}}</option>
{% endfor %}</select></div>
<div><label for="continental_trophy">European trophy won</label>
<select id="continental_trophy" name="continental_trophy">
{% for value,label in european_choices %}
<option value="{{value}}" {% if value==continental_trophy %}selected{% endif %}>{{label}}</option>
{% endfor %}</select></div>
<button>Preview season change</button></form>
{% if error %}<div class="notice">{{error}}</div>{% endif %}
{% if selected and result %}
<h2>{{selected['name']}} — simulated outcome</h2>
<div class="grid">
<div class="card"><div class="muted">Starting sporting appeal</div>
<div class="metric">{{result['previous'] if result['previous'] is not none else 'Unknown'}}</div></div>
<div class="card"><div class="muted">Division adjustment</div><div class="metric">{{'%+d'|format(result['division_delta'])}}</div></div>
<div class="card"><div class="muted">League-form adjustment</div><div class="metric">{{'%+d'|format(result['form_delta'])}}</div></div>
<div class="card"><div class="muted">Projected appeal including opportunities</div>
<div class="metric">{{result['projected'] if result['projected'] is not none else 'Unknown'}}</div></div></div>
<h2>Next-season sporting opportunities</h2>
<div class="grid">
<div class="card"><div class="muted">Domestic cup victory</div><div class="metric">+{{result['cup_bonus']}}</div></div>
<div class="card"><div class="muted">European participation</div><div class="metric">+{{result['continental_bonus']}}</div></div>
<div class="card"><div class="muted">European trophy</div><div class="metric">+{{result['continental_trophy_bonus']}}</div></div>
<div class="card"><div class="muted">Effective temporary bonus (cap +8)</div>
<div class="metric">+{{result['temporary_bonus']}}</div>
{% if result['overlap_cap'] %}<div class="muted">−{{result['overlap_cap']}} overlap cap applied</div>{% endif %}</div>
</div>
<p class="muted">From {{selected['competition_name']}} to {{next_comp_name}}.
Finishing position {{finish}} of {{selected['competition_size']}} in the old division.
Form band: {{result['finish_band']}}. Existing source squad ratings are held constant
in this preview because no future-season player dataset has been supplied.</p>
<div class="notice">The <b>{{'%+d'|format(result['division_delta'])}}</b> divisional change
is distinct from the <b>{{'%+d'|format(result['form_delta'])}}</b> bounded form change.
New cup and European bonuses are temporary. They expire before the next season's
bonuses are calculated, rather than compounding every year.
Any European financial benefits must be handled separately by a sourced finance
model; this screen does not invent extra money. Long-term prestige is
unchanged here and remains unassessed until sourced.</div>
{% endif %}
{% elif mode=='prestige' %}
<p><a href="/world/reputations/prestige/calibration?dataset={{dataset['dataset_id']}}">Open the 15-club source-linked prestige calibration →</a></p>
<div class="notice"><b>Historical club prestige is currently unassessed unless
an attributed review has been completed.</b> We require at least three
reviewed evidence items across two different categories and sources,
followed by an explicit rating review. It will never be populated from
EA squad strength or assumed from the current division.</div>
<form method="get"><label for="dataset">Dataset</label><select name="dataset" id="dataset">
{% for d in datasets %}<option value="{{d['dataset_id']}}" {% if d['dataset_id']==dataset['dataset_id'] %}selected{% endif %}>{{d['title']}}</option>{% endfor %}</select>
<button>View</button></form>
<div class="grid"><div class="card"><div class="muted">Clubs in snapshot</div><div class="metric">{{clubs|length}}</div></div>
<div class="card"><div class="muted">Prestige ratings with approved evidence</div><div class="metric">{{rated}}</div></div>
<div class="card"><div class="muted">Evidence items reviewed</div><div class="metric">{{reviewed_items}}</div></div></div>
<h2>Evidence coverage</h2>
<table><tr><th>Club</th><th>Division</th><th>Reviewed sources</th><th>Evidence pending</th><th>Institutional prestige</th></tr>
{% for c in clubs %}<tr><td>{{c['name']}}</td><td>{{c['competition_name']}}</td>
<td>{{c['reviewed_count']}}</td><td>{{c['pending_count']}}</td>
<td>{{c['prestige_score'] if c['prestige_score'] is not none else 'Not assessed'}}</td></tr>{% endfor %}</table>
{% elif mode=='career' %}
<p><a href="/world/play/career/{{career['career_id']}}">← Career transfer desk</a></p>
<div class="notice"><b>Only recorded, operator-attested season results alter a career's
reputation timeline.</b> No challenge results are inferred or generated by
opening this page. Archived source references are preserved, but not
independently verified solely because an operator supplies one.</div>
<form method="get"><div><label for="club">Club to inspect</label>
<select id="club" name="club">{% for c in clubs %}
<option value="{{c['club_id']}}" {% if c['club_id']==selected_club %}selected{% endif %}>{{c['name']}}</option>
{% endfor %}</select></div><button>Show history</button></form>
<h2>{{selected_name}} — season history</h2>
<div class="grid"><div class="card"><div class="muted">Recorded transitions</div>
<div class="metric">{{number_transitions}}</div></div>
<div class="card"><div class="muted">Current sporting appeal</div>
<div class="metric">{{current['score'] if current and current['score'] is not none else 'Unknown'}}</div></div>
<div class="card"><div class="muted">Temporary cup / Europe boost</div>
<div class="metric">+{{current['temporary_bonus'] if current else 0}}</div></div>
<div class="card"><div class="muted">Historical prestige</div>
<div class="metric">{{current['prestige'] if current and current['prestige'] is not none else 'Unknown'}}</div></div>
<div class="card"><div class="muted">Current division</div><div class="metric">{{current_division}}</div></div></div>
{% if history %}
<table><tr><th>Season step</th><th>Sporting appeal</th><th>Division</th><th>Form</th><th>Sporting delta</th><th>Temporary cup / Europe</th><th>Institutional prestige</th><th>Source</th></tr>
{% for h in history %}<tr><td>{{h['season_index']}}</td><td>{{h['sporting_appeal'] if h['sporting_appeal'] is not none else 'Unknown'}}</td>
<td>{{h['competition_name']}}</td><td>{{'%+d'|format(h['form_adjustment'])}}</td>
<td>{{'%+d'|format(h['division_delta'] if h['division_delta'] is not none else 0)}} division, {{'%+d'|format(h['form_delta'] if h['form_delta'] is not none else 0)}} form</td>
<td>+{{h['temporary_bonus']}}
{% if h['domestic_cup'] and h['domestic_cup']!='none' %}<div class="muted">Cup: {{h['domestic_cup']|replace('_',' ')}} +{{h['cup_bonus']}}</div>{% endif %}
{% if h['continental_competition'] and h['continental_competition']!='none' %}<div class="muted">Europe: {{h['continental_competition']|replace('_',' ')}} +{{h['continental_bonus']}}</div>{% endif %}
{% if h['continental_trophy'] and h['continental_trophy']!='none' %}<div class="muted">European trophy: {{h['continental_trophy']|replace('_',' ')}} +{{h['continental_trophy_bonus']}}</div>{% endif %}
{% if h['bonus_overlap_reduction'] %}<div class="muted">Overlap cap −{{h['bonus_overlap_reduction']}}</div>{% endif %}
</td>
<td>{{h['prestige_at_snapshot'] if h['prestige_at_snapshot'] is not none else 'Unknown'}}
{% if h['prestige_at_snapshot'] is not none and h['prestige_delta'] %}({{'%+d'|format(h['prestige_delta'])}}){% endif %}</td>
<td>{{h['source_ref'] if h['source_ref'] else 'Initial source snapshot'}}</td></tr>{% endfor %}</table>
{% else %}
<p class="muted">No season has been finalised for this career yet. The current value is the immutable starting-dataset estimate, not a generated season result.</p>
{% endif %}
{% endif %}
<footer>Progression updates are separate to the original PES save, club financial ledgers,
transfer agreements, and active registrations. No speculative data is committed by these screens.</footer>
</main></body></html>"""


def create_progression_blueprint(db_path):
    bp=Blueprint("world_progression",__name__)
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

    def allowed():
        secret=os.getenv("WORLD_MARKET_COOKIE_SECRET","")
        if not secret:return False
        try:
            v=URLSafeTimedSerializer(secret,salt="pes-world-play-v1").loads(
                request.cookies.get("world_play_access",""),max_age=8*60*60)
            return v=="market-admin"
        except (BadSignature,SignatureExpired):
            return False

    @bp.get("/world/reputations/progression")
    def scenario():
        with connect() as db:
            dataset=get_dataset(db,request.args.get("dataset"))
            datasets=db.execute("SELECT dataset_id,title FROM world_datasets ORDER BY season_id DESC").fetchall()
            clubs=db.execute("""SELECT c.club_id,c.name,w.name competition_name,w.competition_id,
                 w.expected_clubs AS competition_size,r.sporting_appeal,r.prospects_adjustment
                 FROM world_pyramid_club_appeal r JOIN world_clubs c ON c.club_id=r.club_id
                 JOIN world_competitions w ON w.competition_id=r.competition_id
                 WHERE r.dataset_id=? AND r.model_version=? ORDER BY c.name""",
                 (dataset["dataset_id"],MODEL_VERSION)).fetchall()
            club_by_id={c["club_id"]:c for c in clubs}
            default=next((c["club_id"] for c in clubs if c["name"]=="Hull City"),
                         clubs[0]["club_id"] if clubs else None)
            try:
                club_id=int(request.args.get("club",default))
            except (ValueError,TypeError):abort(400)
            selected=club_by_id.get(club_id)
            if selected is None:abort(404)
            comps=db.execute("""SELECT competition_id,name,expected_clubs
                   FROM world_competitions WHERE competition_id IN ('ENG1','ENG2','ENG3','ENG4')
                   ORDER BY tier""").fetchall()
            next_comp=request.args.get("destination",selected["competition_id"])
            if next_comp not in {x["competition_id"] for x in comps}:abort(400)
            comp_name=next(c["name"] for c in comps if c["competition_id"]==next_comp)
            try:
                finish=int(request.args.get("position",selected["competition_size"]))
            except (ValueError,TypeError):abort(400)
            from world_reputation_achievements import (
                DOMESTIC_CUPS,EUROPEAN_ACCESS
            )
            cup=request.args.get("cup","no")=="yes"  # legacy untyped link
            domestic_cup=request.args.get("domestic_cup","none")
            continental=request.args.get("continental","none")
            continental_trophy=request.args.get("continental_trophy","none")
            domestic_cup_choices=[
                ("none","None"),("fa_cup","FA Cup (+3)"),
                ("league_cup","League Cup (+2)"),
            ]
            european_choices=[
                ("none","None"),("champions_league","Champions League"),
                ("europa_league","Europa League"),("conference_league","Conference League"),
            ]
            error=None
            result=None
            try:
                result=preview_progression(old_score=selected["sporting_appeal"],
                    old_competition=selected["competition_id"],next_competition=next_comp,
                    old_form=selected["prospects_adjustment"],
                    league_position=finish,league_size=selected["competition_size"],cup_won=cup,
                    domestic_cup=domestic_cup,
                    continental_competition=continental,
                    continental_trophy=continental_trophy)
            except ValueError as exc:
                error=str(exc)
            return render_template_string(PAGE,title="Season Reputation Preview",
                mode="preview",model_version=PROGRESSION_VERSION,dataset=dataset,datasets=datasets,
                clubs=clubs,competitions=comps,selected=selected,selected_club=club_id,
                finish=finish,cup=cup,next_comp=next_comp,next_comp_name=comp_name,
                domestic_cup=domestic_cup,continental=continental,
                continental_trophy=continental_trophy,
                domestic_cup_choices=domestic_cup_choices,european_choices=european_choices,
                result=result,error=error)

    @bp.get("/world/reputations/prestige")
    def evidence():
        with connect() as db:
            ds=get_dataset(db,request.args.get("dataset"))
            datasets=db.execute("SELECT dataset_id,title FROM world_datasets ORDER BY season_id DESC").fetchall()
            clubs=db.execute("""SELECT c.club_id,c.name,w.name competition_name,
                p.prestige_score,
                (SELECT COUNT(*) FROM world_reputation_prestige_evidence e
                 WHERE e.dataset_id=r.dataset_id AND e.club_id=r.club_id
                 AND e.review_state='reviewed') reviewed_count,
                (SELECT COUNT(*) FROM world_reputation_prestige_evidence e
                 WHERE e.dataset_id=r.dataset_id AND e.club_id=r.club_id
                 AND e.review_state='pending') pending_count
                FROM world_pyramid_club_appeal r JOIN world_clubs c ON c.club_id=r.club_id
                JOIN world_competitions w ON w.competition_id=r.competition_id
                LEFT JOIN world_reputation_prestige_reviews p
                 ON p.dataset_id=r.dataset_id AND p.club_id=r.club_id
                WHERE r.dataset_id=? AND r.model_version=?
                ORDER BY w.tier,c.name""",(ds["dataset_id"],MODEL_VERSION)).fetchall()
            return render_template_string(PAGE,title="Institutional Prestige Evidence",
                mode="prestige",model_version=PROGRESSION_VERSION,dataset=ds,datasets=datasets,
                clubs=clubs,rated=sum(c["prestige_score"] is not None for c in clubs),
                reviewed_items=sum(c["reviewed_count"] for c in clubs))

    @bp.get("/world/reputations/career/<career_id>")
    def career(career_id):
        if not allowed():return redirect("/world/play")
        with connect() as db:
            from world_careers import initialize_career_engine
            initialize_career_engine(db)
            career=db.execute("""SELECT * FROM world_career_saves
                 WHERE career_id=? AND state='sandbox'""",(career_id,)).fetchone()
            if career is None:abort(404)
            clubs=db.execute("""SELECT c.club_id,c.name FROM world_dataset_entries e
                JOIN world_clubs c ON c.club_id=e.club_id
                WHERE e.dataset_id=? ORDER BY c.name""",(career["dataset_id"],)).fetchall()
            ids={c["club_id"]:c["name"] for c in clubs}
            try:
                club_id=int(request.args.get("club",career["manager_club_id"]))
            except (ValueError,TypeError):abort(400)
            if club_id not in ids:abort(404)
            current=current_career_appeal(db,career_id,club_id)
            history=db.execute("""SELECT h.season_index,h.sporting_appeal,h.form_adjustment,
                   h.prestige_at_snapshot,h.temporary_bonus,h.cup_bonus,
                   h.continental_bonus,h.continental_trophy_bonus,
                   h.bonus_overlap_reduction,w.name competition_name,o.division_delta,
                   o.form_delta,o.prestige_delta,o.source_ref,
                   o.domestic_cup,o.continental_competition,o.continental_trophy
                FROM world_career_reputation_seasons h
                JOIN world_competitions w ON w.competition_id=h.competition_id
                LEFT JOIN world_career_reputation_outcomes o
                 ON o.career_id=h.career_id AND o.season_index=h.season_index
                 AND o.club_id=h.club_id
                WHERE h.career_id=? AND h.club_id=?
                ORDER BY h.season_index""",(career_id,club_id)).fetchall()
            division=db.execute("""SELECT name FROM world_competitions WHERE competition_id=?""",
                (current["competition_id"],)).fetchone() if current else None
            return render_template_string(PAGE,title=career["title"]+" · Reputation History",
                mode="career",model_version=PROGRESSION_VERSION,dataset=career,career=career,
                clubs=clubs,selected_club=club_id,selected_name=ids[club_id],
                current=current,current_division=division[0] if division else "Not assessed",
                history=history,number_transitions=latest_season_index(db,career_id))
    return bp

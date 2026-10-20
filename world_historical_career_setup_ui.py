"""Read-only historical season and club picker; never creates a live career.

The historical catalogue contains 22 seasons, but first live-mode candidates
must have their source leagues, player crosswalk and verified finance inputs
imported as their own immutable dataset. GET requests cannot start transfers.
"""
from flask import Blueprint,abort,render_template_string,request
import sqlite3,re
from world_historical_career_import import SUPPORTED,season

EDITION_CHOICES=tuple(y for y in range(2005,2028) if y!=2025)
TEMPLATE="""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Historical careers · PES Clubs Challenge</title>
<style>body{background:#111a25;color:#eaf1f8;font:15px system-ui,sans-serif;margin:0}
header{background:#1d2a38;padding:19px 26px}main{max-width:1100px;margin:32px auto;padding:0 20px}
a{color:#90c8fe}.muted{color:#aab9c8}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:12px}
.card{border:1px solid #3b4f64;background:#1a2a3c;border-radius:12px;padding:16px}
small,.small{font-size:12px;color:#acb9c8}h1{margin-bottom:6px}h2{font-size:16px}
.pill{font-size:12px;padding:4px 9px;border-radius:15px;border:1px solid #62768a}
table{width:100%;border-collapse:collapse}td,th{padding:11px;text-align:left;border-bottom:1px solid #344759}
input,select{background:#223b54;color:white;border-radius:6px;padding:9px}
</style></head><body><header><a href="/world/careers">PES CHALLENGE · CAREER DESK</a> / Historical seasons</header>
<main><h1>Choose a historical starting season</h1>
<p class="muted">Men's football · PC and PlayStation · Source snapshots and game-estimated finances.
Selecting a season does not create or overwrite a save.</p>
<div class="grid">{% for item in seasons %}
<div class="card"><h2>{{item.label}}</h2>
{% if item.installed %}<span class="pill">Sandbox dataset ready</span>
<p><a href="/world/historical-setup?edition={{item.edition}}">Browse clubs and finances →</a></p>
{% elif item.edition in eligible %}<span class="pill">Database built · import pending</span>
{% else %}<span class="pill">Requires league mapping</span>{% endif %}
</div>{% endfor %}</div>
{% if selected %}<h2>{{selected.label}} — available clubs</h2>
{% if clubs %}<p class="muted">Loaded {{clubs|length}} source clubs. Starting transfer and wage budgets are game estimates.</p>
<table><tr><th>Club</th><th>Source league</th><th>Players</th><th>Existing loans</th><th>Transfer budget</th><th>Weekly wage ceiling</th></tr>
{% for c in clubs %}<tr><td><b>{{c.name}}</b></td><td>{{c.league}}</td>
<td>{{c.players}}</td><td>{{c.loans}}</td>
<td>£{{'{:,.0f}'.format(c.transfer_budget)}}</td>
<td>£{{'{:,.0f}'.format(c.wage_budget)}}</td></tr>{% endfor %}</table>
<p><a href="/world/explore?dataset={{selected.dataset}}">Explore full player squads →</a></p>
{% else %}<div class="card"><p>Historical world not yet imported into this app database.</p>
<p class="small">The completed source package remains in the isolated GitHub test artifacts. No production careers were changed.</p></div>{% endif %}
{% endif %}
<p class="small">Read-only manager-club preview. Launch controls remain disabled until production integration and permission checks pass.</p>
</main></body></html>"""

def _display(name):
    return re.sub(r"\s+\[\d{4}:[a-f0-9]{8}\]$","",name)

def read_historical_setup(conn,selected_year=None):
    names={row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    imported={}
    if {"world_dataset_pes_v2_metadata","world_datasets"}<=names:
        imported=dict(conn.execute("""SELECT edition,dataset_id FROM
            world_dataset_pes_v2_metadata"""))
    seasons=[{"edition":y,"label":season(y),"installed":y in imported}
             for y in EDITION_CHOICES]
    if selected_year is None:return seasons,None,[]
    if selected_year not in EDITION_CHOICES:raise ValueError("Unsupported edition")
    selected={"edition":selected_year,"label":season(selected_year),
              "dataset":imported.get(selected_year)}
    if selected_year not in imported:return seasons,selected,[]
    required={"world_dataset_entries","world_clubs","world_competitions",
       "world_dataset_rosters","world_dataset_initial_loans",
       "world_dataset_club_finances"}
    if not required<=names:raise ValueError("Incomplete installed historical dataset")
    ds=imported[selected_year]
    clubs=[]
    for cid,name,league,transfer,wage,players,loans in conn.execute("""
      SELECT cl.club_id,cl.name,comp.name,b.transfer_budget_gbp,
      b.weekly_wage_budget_gbp,
      (SELECT COUNT(*) FROM world_dataset_rosters r
        WHERE r.dataset_id=e.dataset_id AND r.club_id=cl.club_id),
      (SELECT COUNT(*) FROM world_dataset_initial_loans l
        WHERE l.dataset_id=e.dataset_id AND l.borrower_club_id=cl.club_id)
      FROM world_dataset_entries e JOIN world_clubs cl ON cl.club_id=e.club_id
      JOIN world_competitions comp ON comp.competition_id=e.competition_id
      JOIN world_dataset_club_finances b ON b.dataset_id=e.dataset_id
      AND b.club_id=e.club_id
      WHERE e.dataset_id=? ORDER BY comp.name,cl.name""",(ds,)):
        clubs.append(dict(id=cid,name=_display(name),league=league,players=players,
                          loans=loans,transfer_budget=transfer,wage_budget=wage))
    return seasons,selected,clubs

def create_historical_setup_blueprint(db_path):
    bp=Blueprint("historical_career_setup",__name__)
    @bp.get("/world/historical-setup")
    def picker():
        year=request.args.get("edition",type=int)
        if "edition" in request.args and year not in EDITION_CHOICES:abort(404)
        with sqlite3.connect(str(db_path)) as db:
            seasons,selected,clubs=read_historical_setup(db,year)
        return render_template_string(TEMPLATE,seasons=seasons,selected=selected,
                                      clubs=clubs,eligible=SUPPORTED)
    return bp

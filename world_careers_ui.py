"""Read-only dashboard for versioned career-market sandboxes."""
import sqlite3
import os
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import Blueprint,abort,render_template_string,request,redirect
from world_careers import initialize_career_engine,budget_remaining,ai_interest
from world_explorer import initialize_catalog
from world_valuation import display_gbp

PAGE="""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Career transfer negotiations</title><style>
body{margin:0;background:#111a25;color:#edf3f9;font:15px system-ui}
header{padding:16px 24px;background:#1a2b3c}main{max-width:1050px;margin:28px auto;padding:0 20px 70px}
a{color:#a9d2fa;text-decoration:none}.muted{color:#b8c5d2}.notice{background:#263d52;border-left:3px solid #8ebbe7;padding:15px;margin:18px 0}
.card{background:#203144;padding:16px;border:1px solid #364e65;border-radius:8px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}
table{width:100%;border-collapse:collapse}td,th{padding:12px;text-align:left;border-bottom:1px solid #3c4e61}
</style></head><body><header><a href="/world/market">← Market preview</a> · <a href="/world/explore">Squad Explorer</a></header><main>
<h1>Career transfer negotiations</h1>
<div class="notice">Sandbox career records only. This dashboard is read-only; career creation and transactions require a separate developer-only operation.
All budgets are fictional economy-model outputs, not verified financial statements.
Agreed future transfers do not move PES-locked players midseason.</div>
{% if not careers %}<div class="card"><h2>No separate career sandboxes yet</h2><p>Create one through the development engine's controlled CLI or tests.
The original Clubs Challenge is unaffected.</p></div>{% else %}
<h2>Available sandbox careers</h2><div class="grid">
{% for c in careers %}<a class="card" href="/world/careers?career={{c['career_id']}}"><b>{{c['title']}}</b>
<p class="muted">{{c['career_id']}} · {{c['economy_version']}}</p></a>{% endfor %}</div>
{% if current %}
<h2>{{current['title']}}</h2>
<p class="muted">Dataset {{current['dataset_id']}} · Economy {{current['economy_version']}} · PES squad lock {{current['pes_lock_date']}} · Next registration {{current['next_summer_date']}}</p>
<div class="grid"><div class="card"><b>{{total}}</b><p class="muted">Negotiations on record</p></div>
<div class="card"><b>{{display_budget}}</b><p class="muted">Manager club available transfer funds</p></div>
<div class="card"><b>{{agreed}}</b><p class="muted">Agreed future transfers</p></div></div>
<h2>Negotiation history</h2>
<table><tr><th>Player</th><th>Buyer</th><th>Seller</th><th>Offer</th><th>Status</th><th>Registration</th></tr>
{% for o in offers %}<tr><td>{{o['player_name']}}</td><td>{{o['buyer_name']}}</td>
<td>{{o['seller_name']}}</td><td>{{o['fee_label']}}</td><td>{{o['status']}}</td>
<td>{{o['effective_date'] or 'Not agreed'}}</td></tr>{% endfor %}</table>
{% endif %}{% endif %}
</main></body></html>"""


def create_careers_blueprint(db_path):
    bp=Blueprint("world_careers_ui",__name__)
    @bp.get("/world/careers")
    def index():
        secret=os.getenv("WORLD_MARKET_COOKIE_SECRET","")
        if not secret:
            return redirect("/world/play")
        signer=URLSafeTimedSerializer(secret,salt="pes-world-play-v1")
        try:
            if signer.loads(request.cookies.get("world_play_access",""),max_age=8*60*60)!="market-admin":
                return redirect("/world/play")
        except (BadSignature,SignatureExpired):
            return redirect("/world/play")
        # No mutations: migrations/seeding are performed by the developer CLI,
        # the manager never exposes a public POST operation.
        with sqlite3.connect(str(db_path)) as db:
            db.row_factory=sqlite3.Row
            try:
                careers=db.execute("SELECT * FROM world_career_saves WHERE state='sandbox' ORDER BY created_at DESC").fetchall()
            except sqlite3.OperationalError:
                careers=[]
            selected=request.args.get("career")
            current=None
            if selected:
                current=next((c for c in careers if c["career_id"]==selected),None)
                if current is None:abort(404)
            elif careers:
                current=careers[0]
            offers=[]
            remaining=None
            agreed=0
            if current:
                rows=db.execute("""SELECT o.*,p.full_name player_name,b.name buyer_name,s.name seller_name
                    FROM world_career_offers o
                    JOIN world_players p ON p.player_id=o.player_id
                    JOIN world_clubs b ON b.club_id=o.buying_club_id
                    JOIN world_clubs s ON s.club_id=o.selling_club_id
                    WHERE o.career_id=? ORDER BY o.offer_id DESC""",(current["career_id"],)).fetchall()
                offers=[dict(x,fee_label=display_gbp(x["offered_fee"])) for x in rows]
                agreed=sum(o["status"]=="agreed_future" for o in offers)
                if current["manager_club_id"] is not None:
                    remaining=budget_remaining(db,current["career_id"],current["manager_club_id"])
            return render_template_string(PAGE,careers=careers,current=current,offers=offers,
                total=len(offers),agreed=agreed,display_budget=display_gbp(remaining))
    return bp

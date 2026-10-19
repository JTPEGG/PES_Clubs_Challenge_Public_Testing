"""Isolated club-budget scenarios and transfer negotiation sandbox.

Public pages only PREVIEW. No POST endpoints mutate live career data.
Persisted scenarios/offers require an explicit developer CLI call on a
separate development database. No source budget is invented as a fact.
"""
from datetime import date
import math
import sqlite3
from flask import Blueprint, abort, render_template_string, request
from world_explorer import initialize_catalog, get_dataset
from world_valuation import model_value, display_gbp

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_market_scenarios(
 scenario_id TEXT PRIMARY KEY,
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 title TEXT NOT NULL, assumptions_version TEXT NOT NULL,
 currency TEXT NOT NULL DEFAULT 'GBP',
 created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','locked')),
 pes_lock_date TEXT, next_summer_date TEXT,
 CHECK(next_summer_date IS NULL OR pes_lock_date IS NULL OR next_summer_date > pes_lock_date)
);
CREATE TABLE IF NOT EXISTS world_market_scenario_clubs(
 scenario_id TEXT NOT NULL REFERENCES world_market_scenarios(scenario_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 transfer_budget INTEGER NOT NULL CHECK(transfer_budget>=0),
 wage_budget_weekly INTEGER NOT NULL CHECK(wage_budget_weekly>=0),
 PRIMARY KEY(scenario_id,club_id)
);
CREATE TABLE IF NOT EXISTS world_market_offers(
 offer_id INTEGER PRIMARY KEY,
 scenario_id TEXT NOT NULL REFERENCES world_market_scenarios(scenario_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 from_club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 to_club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 fee_amount INTEGER NOT NULL CHECK(fee_amount>=0),
 agreement_date TEXT NOT NULL, effective_date TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('proposed','countered','rejected','agreed_future','cancelled')),
 counter_amount INTEGER, valuation_model TEXT NOT NULL,
 CHECK(from_club_id<>to_club_id)
);
"""


def initialize_market(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def tier_budget(tier, scale=1.0):
    """Explicit FICTIONAL scenario base, not accounts or reported expenditure."""
    bases={1:(45_000_000,2_300_000),2:(8_000_000,440_000),
           3:(1_300_000,110_000),4:(450_000,52_000)}
    if tier not in bases or not 0.25<=scale<=3:
        raise ValueError("Invalid tier or scenario scale")
    amount,wages=bases[tier]
    return int(round(amount*scale/25_000)*25_000),int(round(wages*scale/1000)*1000)


def offer_result(offer, reference, budget, relationship="neutral"):
    """Deterministic preview, never commits transfers or finances."""
    if not isinstance(offer,int) or offer<0:
        raise ValueError("Offer must be a nonnegative whole number of GBP")
    if budget is None or budget<0:
        return {"status":"blocked","reason":"Buyer has no configured transfer budget"}
    if offer>budget:
        return {"status":"blocked","reason":"Offer exceeds buyer's budget"}
    if reference is None:
        return {"status":"review","reason":"Player valuation unavailable"}
    # A seller's asking-price threshold is NOT the player's intrinsic value.
    pressure={"neutral":1.25,"rival":1.65,"selling":0.98}
    if relationship not in pressure:
        raise ValueError("Unknown club relationship")
    asking=int(math.ceil(reference*pressure[relationship]/100_000)*100_000)
    if offer>=asking:
        return {"status":"acceptable_for_discussion","asking":asking,
                "reason":"Meets this scenario's asking-price threshold; wage/contract negotiation still required"}
    if offer>=asking*.75:
        return {"status":"counteroffer","asking":asking,
                "reason":"Seller would counter at the scenario asking price"}
    return {"status":"rejected","asking":asking,
            "reason":"Below the scenario seller threshold"}


def allowed_effective_date(agreement, proposed, pes_lock, next_summer, *, active_pes=True):
    """Deals after PES squad lock remain future deals even if agreed in winter."""
    dates=(agreement,proposed,pes_lock,next_summer)
    if not all(isinstance(d,date) for d in dates):
        raise TypeError("Registration dates must be real dates")
    if next_summer<=pes_lock or proposed<agreement:
        raise ValueError("Invalid transfer season dates")
    if active_pes and proposed>=pes_lock:
        return max(proposed,next_summer)
    return proposed


STYLE="""body{margin:0;background:#111a25;color:#edf3f9;font:15px system-ui}
header{padding:18px 25px;background:#1a2939}main{max-width:1100px;margin:auto;padding:30px 20px}
a{color:#a7d1fb;text-decoration:none}a:hover{text-decoration:underline}
.card{background:#1f3043;border:1px solid #394f66;padding:18px;border-radius:10px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:13px}
.notice{background:#273a4d;padding:16px;border-left:3px solid #8fc5ee;margin:20px 0}
label{display:block;margin:8px 0 3px}select,input,button{padding:9px;border:1px solid #526780;border-radius:6px;
background:#253c51;color:#eef6ff}button{cursor:pointer}small,.muted{color:#acbfd0}
table{width:100%;border-collapse:collapse;margin-top:12px}td,th{padding:12px;text-align:left;border-bottom:1px solid #39495a}
"""
PAGE="""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Transfer market sandbox</title><style>"""+STYLE+"""</style></head><body>
<header><a href="/world/explore">← Squad Explorer</a> · <a href="/world/finances">Finances</a> · <a href="/world/careers">Career offers</a></header>
<main><h1>Transfer market sandbox</h1>
<p class="muted">Selected dataset: {{dataset['title']}}. Nothing on this page submits an offer or changes a save.</p>
<div class="notice">All budgets below are FICTIONAL scenario assumptions. They are not sourced club financial statements.
Transfer proposals are previews only, with no player-registration changes. Contracts, wages and the PS4 file remain unaltered.</div>
<h2>Financial scenario setup</h2>
<form method="get"><input type="hidden" name="dataset" value="{{dataset['dataset_id']}}">
<label for="scale">Financial scale</label><select id="scale" name="scale">
{% for v,label in scales %}<option value="{{v}}" {% if v==scale %}selected{% endif %}>{{label}}</option>{% endfor %}</select>
<label for="club">Explore buying club</label><select name="club" id="club">
{% for c in clubs %}<option value="{{c['club_id']}}" {% if c['club_id']==club_id %}selected{% endif %}>{{c['name']}}</option>{% endfor %}</select>
<label for="player">Transfer target</label><select name="player" id="player">
{% for p in targets %}<option value="{{p['player_id']}}" {% if p['player_id']==player_id %}selected{% endif %}>{{p['full_name']}} — {{p['club_name']}}</option>{% endfor %}</select>
<label for="fee">Proposed fee (£)</label><input type="number" min="0" step="100000" name="fee" id="fee" value="{{fee}}">
<label for="relationship">Seller stance</label><select name="relationship">
{% for v,label in relationships %}<option value="{{v}}" {% if v==relationship %}selected{% endif %}>{{label}}</option>{% endfor %}</select>
<button type="submit">Preview offer</button></form>
<div class="grid">
<div class="card"><small>Buyer budget · simulated</small><h2>{{budget_label}}</h2></div>
<div class="card"><small>Weekly wage limit · simulated</small><h2>{{wage_label}}</h2></div>
<div class="card"><small>Target base value · model</small><h2>{{reference_label}}</h2></div>
</div>
<h2>Offer assessment</h2>
<div class="card"><h2>{{decision['status']}}</h2><p>{{decision['reason']}}</p>
{% if decision.get('asking') is not none %}<p>Scenario seller threshold: <b>{{asking_label}}</b></p>{% endif %}
</div>
<div class="notice"><b>PES season lock:</b> Once an active PES League Mode competition is created, any move that affects its squads must wait until the next summer registration/import.
Agreeing a January deal does not alter the playable league midseason.</div>
<p><a href="/world/quality">Player database review</a> · <a href="/world/explore">Return to clubs</a></p>
</main></body></html>"""


def create_market_blueprint(db_path):
    bp=Blueprint("world_market",__name__)
    def connect():
        from world_v2 import initialize_world
        db=sqlite3.connect(str(db_path))
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        initialize_world(db)
        initialize_catalog(db)
        initialize_market(db)
        return db

    @bp.get("/world/market")
    def index():
        with connect() as db:
            ds=get_dataset(db,request.args.get("dataset"))
            clubs=db.execute("""SELECT c.club_id,c.name,w.tier FROM world_dataset_entries e
                JOIN world_clubs c ON c.club_id=e.club_id
                JOIN world_competitions w ON w.competition_id=e.competition_id
                WHERE e.dataset_id=? ORDER BY c.name""",(ds["dataset_id"],)).fetchall()
            if not clubs:abort(404)
            try:club_id=int(request.args.get("club",clubs[0]["club_id"]))
            except (ValueError,TypeError):club_id=clubs[0]["club_id"]
            club=next((c for c in clubs if c["club_id"]==club_id),clubs[0])
            scale_options=[("0.5","Conservative · 0.5×"),("1","Baseline · 1×"),("1.5","Generous · 1.5×")]
            scale=request.args.get("scale","1")
            if scale not in dict(scale_options):scale="1"
            budget,wages=tier_budget(club["tier"],float(scale))
            targets=db.execute("""SELECT p.player_id,p.full_name,c.name club_name,p.birth_date,
                p.primary_position,x.overall FROM world_dataset_rosters r
                JOIN world_players p ON p.player_id=r.player_id
                JOIN world_clubs c ON c.club_id=r.club_id
                LEFT JOIN world_dataset_ratings x ON x.player_id=r.player_id AND x.dataset_id=r.dataset_id
                WHERE r.dataset_id=? AND r.club_id<>?
                ORDER BY x.overall DESC,p.full_name LIMIT 250""",(ds["dataset_id"],club["club_id"])).fetchall()
            if not targets:abort(404)
            try:player_id=int(request.args.get("player",targets[0]["player_id"]))
            except (ValueError,TypeError):player_id=targets[0]["player_id"]
            target=next((p for p in targets if p["player_id"]==player_id),targets[0])
            from world_explorer import age_on
            ref=model_value(target["overall"],age_on(target["birth_date"],ds["source_date"]),target["primary_position"])
            fee_raw=request.args.get("fee","")
            try:fee=int(fee_raw) if fee_raw else (ref if ref is not None else 0)
            except ValueError:fee=0
            relationship=request.args.get("relationship","neutral")
            relationships=[("neutral","Normal seller"),("rival","Direct rival"),("selling","Transfer-listed")]
            if relationship not in dict(relationships):relationship="neutral"
            decision=offer_result(fee,ref,budget,relationship)
            return render_template_string(PAGE,dataset=ds,clubs=clubs,club_id=club["club_id"],
                player_id=target["player_id"],targets=targets,
                scale=scale,scales=scale_options,fee=fee,
                relationship=relationship,relationships=relationships,
                budget_label=display_gbp(budget),wage_label=display_gbp(wages),
                reference_label=display_gbp(ref),decision=decision,
                asking_label=display_gbp(decision.get("asking")))
    return bp

"""Dataset-specific financial and contract foundations for PES Challenge 2.0.

Never infer actual club budgets, wages, contract expiries or clauses from
ratings. All values require explicit provenance and remain isolated per dataset.
This module is read-only; later career saves will maintain their own ledgers.
"""
import sqlite3
from datetime import date
from flask import Blueprint, abort, request, render_template_string
from world_explorer import initialize_catalog, get_dataset
from world_valuation import display_gbp

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_dataset_club_finances (
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 currency TEXT NOT NULL DEFAULT 'GBP',
 transfer_budget INTEGER CHECK (transfer_budget IS NULL OR transfer_budget >= 0),
 wage_budget_weekly INTEGER CHECK (wage_budget_weekly IS NULL OR wage_budget_weekly >= 0),
 wage_spend_weekly INTEGER CHECK (wage_spend_weekly IS NULL OR wage_spend_weekly >= 0),
 available_cash INTEGER,
 debt INTEGER CHECK (debt IS NULL OR debt >= 0),
 financial_status TEXT NOT NULL DEFAULT 'unverified',
 source_url TEXT, notes TEXT,
 PRIMARY KEY(dataset_id,club_id),
 CHECK(financial_status IN ('unverified','source-backed','simulation-assumption'))
);
CREATE TABLE IF NOT EXISTS world_dataset_player_contracts (
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 start_date TEXT, end_date TEXT,
 wage_weekly INTEGER CHECK(wage_weekly IS NULL OR wage_weekly >= 0),
 currency TEXT NOT NULL DEFAULT 'GBP',
 release_clause INTEGER CHECK(release_clause IS NULL OR release_clause >= 0),
 squad_role TEXT, contract_status TEXT NOT NULL DEFAULT 'unverified',
 source_url TEXT, notes TEXT,
 PRIMARY KEY(dataset_id,player_id),
 CHECK(contract_status IN ('unverified','source-backed','simulation-assumption'))
);
CREATE TABLE IF NOT EXISTS world_finance_scenario_assumptions (
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 scenario_id TEXT NOT NULL,
 model_version TEXT NOT NULL,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 notes TEXT,
 PRIMARY KEY(dataset_id,scenario_id)
);
"""

STYLE = """body{font:15px system-ui;background:#111a25;color:#edf3fa;margin:0}
header{background:#1e2e40;padding:17px 22px;border-bottom:1px solid #415267}
main{max-width:1050px;margin:28px auto;padding:0 20px 60px}a{color:#acd3fa;text-decoration:none}
a:hover{text-decoration:underline}.dim{color:#aebdcc}.banner{border-left:3px solid #89badb;
background:#25394b;padding:15px;margin:20px 0}
table{width:100%;border-collapse:collapse;background:#1c2b3d}
td,th{padding:12px;border-bottom:1px solid #39495e;text-align:left}
th{font-size:.85rem;color:#b9c9d7}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.card{padding:18px;background:#1c2b3d;border:1px solid #42546a;border-radius:8px}
.stat{font-size:1.5rem;font-weight:bold}h1{margin-bottom:5px}
select,button{padding:9px;background:#283d50;color:white;border:1px solid #53697d;border-radius:5px}
"""
PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{title}} | Football World</title><style>""" + STYLE + """</style></head><body>
<header><a href="/world/explore">← Squad Explorer</a> · <a href="/world">Football World</a> · <a href="/world/market?dataset={{dataset['dataset_id']}}">Transfer market sandbox</a></header>
<main><h1>{{title}}</h1><p class="dim">Financial and contractual readiness · {{dataset['title']}}</p>
<div class="banner">These are dataset-specific financial records, not a live club bank account.
Unverified figures are shown as unknown, never filled with invented numbers.
Browsing datasets does not change active career finances.</div>
{% if mode == 'overview' %}
<form method="get"><label for="dataset">Select dataset </label><select id="dataset" name="dataset">
{% for d in datasets %}<option value="{{d['dataset_id']}}" {% if d['dataset_id']==dataset['dataset_id'] %}selected{% endif %}>{{d['title']}}</option>{% endfor %}</select>
<button type="submit">Browse</button></form>
<div class="grid">
<div class="card"><div class="dim">Clubs in dataset</div><div class="stat">{{summary['clubs']}}</div></div>
<div class="card"><div class="dim">Financial records with evidence</div><div class="stat">{{summary['source_clubs']}}</div></div>
<div class="card"><div class="dim">Simulated assumptions</div><div class="stat">{{summary['scenario_clubs']}}</div></div>
<div class="card"><div class="dim">Player contracts with evidence</div><div class="stat">{{summary['source_contracts']}}</div></div>
</div>
<h2>Club finances</h2>
<table><tr><th>Club</th><th>Transfer budget</th><th>Wage budget/week</th><th>Evidence</th></tr>
{% for c in clubs %}<tr><td><a href="{{url_for('world_finance.club',club_id=c['club_id'],dataset=dataset['dataset_id'])}}">{{c['name']}}</a></td>
<td>{{c['transfer_display']}}</td><td>{{c['wage_display']}}</td><td>{{c['financial_status'] or 'Not recorded'}}</td></tr>{% endfor %}</table>
{% elif mode == 'club' %}
<p><a href="{{url_for('world_finance.index',dataset=dataset['dataset_id'])}}">← All club finances</a></p>
<div class="grid">
<div class="card"><div class="dim">Transfer budget</div><div class="stat">{{finance['transfer_display']}}</div></div>
<div class="card"><div class="dim">Weekly wage budget</div><div class="stat">{{finance['wage_display']}}</div></div>
<div class="card"><div class="dim">Weekly wage spend</div><div class="stat">{{finance['spend_display']}}</div></div>
<div class="card"><div class="dim">Available cash</div><div class="stat">{{finance['cash_display']}}</div></div></div>
<p class="dim">Finance status: {{finance['financial_status']}}{% if finance['source_url'] %} · <a href="{{finance['source_url']}}">Source ↗</a>{% endif %}</p>
<h2>Player contracts ({{contracts|length}} roster entries)</h2>
<table><tr><th>Player</th><th>Expiry</th><th>Weekly wage</th><th>Role</th><th>Evidence</th></tr>
{% for p in contracts %}<tr><td><a href="/world/explore/player/{{p['player_id']}}?dataset={{dataset['dataset_id']}}">{{p['full_name']}}</a></td>
<td>{{p['end_date'] or 'Unknown'}}</td><td>{{p['wage_display']}}</td><td>{{p['squad_role'] or 'Unknown'}}</td>
<td>{{p['contract_status'] or 'Not recorded'}}</td></tr>{% endfor %}</table>
{% endif %}
<p class="dim">No transactions, wages, player registrations or career records are changed on this screen.</p>
</main></body></html>"""


def initialize_finance(conn):
    conn.executescript(SCHEMA)
    # Intentionally no fabricated baseline finance or contracts.
    conn.commit()


def financial_status(conn, dataset_id):
    row = conn.execute("""SELECT
      (SELECT COUNT(*) FROM world_dataset_entries WHERE dataset_id=?) clubs,
      (SELECT COUNT(*) FROM world_dataset_club_finances WHERE dataset_id=? AND financial_status='source-backed') source_clubs,
      (SELECT COUNT(*) FROM world_dataset_club_finances WHERE dataset_id=? AND financial_status='simulation-assumption') scenario_clubs,
      (SELECT COUNT(*) FROM world_dataset_player_contracts WHERE dataset_id=? AND contract_status='source-backed') source_contracts
    """, (dataset_id,)*4).fetchone()
    return dict(zip(("clubs","source_clubs","scenario_clubs","source_contracts"), row))


def create_finance_blueprint(db_path):
    bp = Blueprint("world_finance", __name__)
    def connect():
        from world_v2 import initialize_world
        db = sqlite3.connect(str(db_path))
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        initialize_world(db)
        initialize_catalog(db)
        initialize_finance(db)
        return db

    @bp.get("/world/finances")
    def index():
        with connect() as db:
            dataset = get_dataset(db, request.args.get("dataset"))
            clubs = db.execute("""SELECT c.club_id,c.name,f.transfer_budget,f.wage_budget_weekly,
              f.currency,f.financial_status FROM world_dataset_entries e
              JOIN world_clubs c ON c.club_id=e.club_id
              LEFT JOIN world_dataset_club_finances f
              ON f.dataset_id=e.dataset_id AND f.club_id=e.club_id
              WHERE e.dataset_id=? ORDER BY c.name""", (dataset["dataset_id"],)).fetchall()
            result=[]
            for c in clubs:
                cur=c["currency"] or "GBP"
                result.append(dict(c,transfer_display=display_gbp(c["transfer_budget"]) if cur=="GBP" else "Unknown",
                    wage_display=display_gbp(c["wage_budget_weekly"]) if cur=="GBP" else "Unknown"))
            return render_template_string(PAGE,mode="overview",title="Club finances",
                dataset=dataset, datasets=db.execute("SELECT * FROM world_datasets ORDER BY season_id DESC").fetchall(),
                summary=financial_status(db,dataset["dataset_id"]),clubs=result)

    @bp.get("/world/finances/club/<int:club_id>")
    def club(club_id):
        with connect() as db:
            dataset = get_dataset(db, request.args.get("dataset"))
            team=db.execute("""SELECT c.name FROM world_dataset_entries e
                JOIN world_clubs c ON c.club_id=e.club_id
                WHERE e.dataset_id=? AND e.club_id=?""",(dataset["dataset_id"],club_id)).fetchone()
            if not team:abort(404)
            row=db.execute("""SELECT * FROM world_dataset_club_finances
                WHERE dataset_id=? AND club_id=?""",(dataset["dataset_id"],club_id)).fetchone()
            fin=dict(row) if row else {"currency":"GBP","transfer_budget":None,"wage_budget_weekly":None,
                   "wage_spend_weekly":None,"available_cash":None,"financial_status":"Not recorded","source_url":None}
            fin.update(transfer_display=display_gbp(fin["transfer_budget"]) if fin["currency"]=="GBP" else "Unknown",
                wage_display=display_gbp(fin["wage_budget_weekly"]) if fin["currency"]=="GBP" else "Unknown",
                spend_display=display_gbp(fin["wage_spend_weekly"]) if fin["currency"]=="GBP" else "Unknown",
                cash_display=display_gbp(fin["available_cash"]) if fin["currency"]=="GBP" else "Unknown")
            people=db.execute("""SELECT p.player_id,p.full_name,ct.end_date,ct.wage_weekly,
                   ct.currency,ct.squad_role,ct.contract_status
                FROM world_dataset_rosters r
                JOIN world_players p ON p.player_id=r.player_id
                LEFT JOIN world_dataset_player_contracts ct
                   ON ct.dataset_id=r.dataset_id AND ct.player_id=r.player_id
                WHERE r.dataset_id=? AND r.club_id=?
                ORDER BY p.full_name""",(dataset["dataset_id"],club_id)).fetchall()
            contracts=[dict(p,wage_display=display_gbp(p["wage_weekly"]) if p["currency"] in (None,"GBP") else "Unknown") for p in people]
            return render_template_string(PAGE,mode="club",title=team["name"]+" · Finances",
                dataset=dataset,finance=fin,contracts=contracts)
    return bp

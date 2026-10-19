"""Versioned, auditable reputation groundwork for PES Clubs Challenge 2.0.

Every league anchor is an EXPLICIT fictional assumption, NOT a real-world
league ranking. All team adjustments are reproducible from the selected
dataset's provisional EA-style source ratings. Historical institutional
prestige and league position remain UNKNOWN until independently evidenced.
No write to production challenge, existing career ledgers or club master.
"""
import sqlite3
from collections import defaultdict
from flask import Blueprint, abort, render_template_string, request
from world_explorer import get_dataset, initialize_catalog

MODEL_VERSION = "rep-prototype-v1"
# Gameplay starting points, deliberately not asserted as historical facts.
LEAGUE_ANCHORS = {
    "ENG1": (86, 77),
    "ENG2": (67, 70),
    "ENG3": (49, 65),
    "ENG4": (35, 62),
}
SQUAD_SAMPLE = 16
MAX_SQUAD_ADJUSTMENT = 10

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_league_reputation_snapshots (
    dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
    competition_id TEXT NOT NULL REFERENCES world_competitions(competition_id),
    score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100),
    source_type TEXT NOT NULL DEFAULT 'simulation-assumption',
    model_version TEXT NOT NULL,
    justification TEXT NOT NULL,
    PRIMARY KEY(dataset_id,competition_id)
);
CREATE TABLE IF NOT EXISTS world_club_reputation_snapshots (
    dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
    club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
    competition_id TEXT NOT NULL,
    working_appeal INTEGER NOT NULL CHECK(working_appeal BETWEEN 0 AND 100),
    institutional_prestige INTEGER CHECK(institutional_prestige BETWEEN 0 AND 100),
    league_anchor INTEGER NOT NULL,
    top_squad_average REAL,
    squad_adjustment INTEGER NOT NULL,
    rated_players INTEGER NOT NULL,
    confidence TEXT NOT NULL CHECK(confidence IN ('source-proxy','limited-source','tier-only')),
    source_label TEXT NOT NULL,
    source_date TEXT,
    model_version TEXT NOT NULL,
    PRIMARY KEY(dataset_id,club_id)
);
CREATE TABLE IF NOT EXISTS world_career_reputation_events (
    career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
    event_id TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('manager','club','league')),
    club_id INTEGER REFERENCES world_clubs(club_id),
    competition_id TEXT REFERENCES world_competitions(competition_id),
    event_type TEXT NOT NULL,
    event_date TEXT NOT NULL,
    evidenced_source TEXT NOT NULL,
    reputation_delta INTEGER NOT NULL CHECK(reputation_delta BETWEEN -15 AND 15),
    PRIMARY KEY(career_id,event_id)
);
"""

def _clamp(value, low, high):
    return max(low,min(high,value))

def derive_club_appeal(competition_id, overalls):
    """All values are simulation outputs; not a historic/prestige rating.

    Returns score, top-16 rounded squad average, signed adjustment, confidence.
    """
    baseline = LEAGUE_ANCHORS.get(competition_id)
    if baseline is None:
        return None
    league_anchor,expected_ovr=baseline
    valid=sorted((v for v in overalls if type(v) is int and 1<=v<=99), reverse=True)
    if not valid:
        return league_anchor,None,0,"tier-only"
    sampled=valid[:SQUAD_SAMPLE]
    average=sum(sampled)/len(sampled)
    adjustment=_clamp(round((average-expected_ovr)*0.85),-MAX_SQUAD_ADJUSTMENT,MAX_SQUAD_ADJUSTMENT)
    confidence="source-proxy" if len(sampled)==SQUAD_SAMPLE else "limited-source"
    return _clamp(league_anchor+adjustment,0,100),round(average,2),adjustment,confidence


def initialize_reputations(conn):
    """Snapshot existing dataset entries once. Never change old version records."""
    conn.executescript(SCHEMA)
    datasets=conn.execute("SELECT dataset_id,source_label,source_date FROM world_datasets").fetchall()
    for dataset_id,src,source_date in datasets:
        entries=conn.execute("""SELECT e.club_id,e.competition_id FROM world_dataset_entries e
            WHERE e.dataset_id=?""",(dataset_id,)).fetchall()
        if not entries:
            continue
        snapshot_count=conn.execute("""SELECT COUNT(*) FROM world_club_reputation_snapshots
            WHERE dataset_id=?""",(dataset_id,)).fetchone()[0]
        league_count=conn.execute("""SELECT COUNT(*) FROM world_league_reputation_snapshots
            WHERE dataset_id=?""",(dataset_id,)).fetchone()[0]
        supported={code for _,code in entries if code in LEAGUE_ANCHORS}
        supported_count=sum(code in LEAGUE_ANCHORS for _,code in entries)
        # Browser navigation should never recalculate thousands of players once
        # the immutable dataset version is fully snapshotted.
        if snapshot_count==supported_count and league_count==len(supported):
            continue
        ratings=defaultdict(list)
        for club_id,overall in conn.execute("""SELECT r.club_id,x.overall
            FROM world_dataset_rosters r
            JOIN world_dataset_ratings x ON x.dataset_id=r.dataset_id AND x.player_id=r.player_id
            WHERE r.dataset_id=?""",(dataset_id,)).fetchall():
            ratings[club_id].append(overall)
        for club_id,code in entries:
            if code not in LEAGUE_ANCHORS:
                continue  # Future foreign leagues need separately approved baselines.
            baseline,benchmark=LEAGUE_ANCHORS[code]
            conn.execute("""INSERT OR IGNORE INTO world_league_reputation_snapshots
                (dataset_id,competition_id,score,source_type,model_version,justification)
                VALUES (?, ?, ?, 'simulation-assumption', ?, ?)""",
                (dataset_id,code,baseline,MODEL_VERSION,
                 f"Provisional game-world league anchor {baseline}/100; no verified international ranking."))
            result=derive_club_appeal(code,ratings.get(club_id,[]))
            score,average,adjustment,confidence=result
            conn.execute("""INSERT OR IGNORE INTO world_club_reputation_snapshots
                (dataset_id,club_id,competition_id,working_appeal,institutional_prestige,
                 league_anchor,top_squad_average,squad_adjustment,rated_players,
                 confidence,source_label,source_date,model_version)
                VALUES (?,?,?,?,NULL,?,?,?,?,?,?,?,?)""",
                (dataset_id,club_id,code,score,baseline,average,adjustment,
                 len(ratings.get(club_id,[])),confidence,src or "Unspecified source",
                 source_date,MODEL_VERSION))
    conn.commit()


def assess_player_move(*, buyer_tier, seller_tier, buyer_appeal=None,
                       seller_appeal=None, player_overall=None):
    """Conservative *simulation decision*, not actual player consent.

    Hard blocking 2+ tier drops prevents unlimited wage exploit; uncertain
    cases remain conditional until playing-time and ambition data exist.
    """
    if buyer_tier is None or seller_tier is None:
        return {"decision":"review","reason":"Cannot establish sporting level for both clubs",
                "can_negotiate":False}
    gap=buyer_tier-seller_tier
    if gap>=2:
        return {"decision":"uninterested","reason":"Two or more divisions lower: the player declines talks in this prototype; wages cannot bypass this barrier",
                "can_negotiate":False}
    if gap==1:
        return {"decision":"needs_assurances","reason":"One-division drop: require clear playing-time and career assurances in a future stage",
                "can_negotiate":True}
    if buyer_appeal is not None and seller_appeal is not None:
        diff=buyer_appeal-seller_appeal
        if diff<=-12:
            return {"decision":"needs_assurances","reason":"Substantial drop in modelled sporting appeal; salary alone does not establish consent",
                    "can_negotiate":True}
    if gap<0:
        return {"decision":"open_to_talks","reason":"Higher division makes talks plausible, subject to role, personality and finances",
                "can_negotiate":True}
    return {"decision":"open_to_talks","reason":"No severe divisional obstacle identified; real player intent remains unverified",
            "can_negotiate":True}


def manager_reputation_from_results(results, *, starting=25):
    """Reputation can change only from explicitly logged career outcomes.

    Accepts result objects with event and source; missing information is not
    inferred. These game mechanics are provisional, NOT external career data.
    """
    increments={"promotion":8,"championship_title":5,"top_flight_title":14,
                "cup_win":6,"objective_met":3,"objective_exceeded":5,
                "objective_failed":-3,"relegation":-8,"sacking":-6,
                "international_trophy":12}
    if results is None:
        return None
    score=starting
    for record in results:
        if not isinstance(record,dict) or not record.get("source"):
            raise ValueError("Every result must have an auditable source")
        kind=record.get("event")
        if kind not in increments:
            raise ValueError("Unknown managerial result: "+str(kind))
        score+=increments[kind]
    return _clamp(score,0,100)


def assess_manager_application(*, manager_reputation, club_appeal, league_tier,
                               top_division_experience=False):
    """No invented interview invitations: outputs an evaluation, never a job offer."""
    if manager_reputation is None or club_appeal is None or league_tier is None:
        return {"status":"unassessed","reason":"Manager results or club dataset missing","threshold":None}
    # Club requirements are intentionally harder at the top; values are
    # game design controls, subject to calibration, NOT actual HR policy.
    baseline={1:66,2:47,3:34,4:24}.get(league_tier)
    if baseline is None:
        return {"status":"unassessed","reason":"Unknown division","threshold":None}
    threshold=_clamp(baseline+round((club_appeal-LEAGUE_ANCHORS.get("ENG"+str(league_tier),(club_appeal,))[0])*.45),15,90)
    if league_tier==1 and manager_reputation<75 and not top_division_experience:
        return {"status":"unlikely","reason":"Top-flight experience or an exceptional managerial record is required by this prototype","threshold":max(threshold,75)}
    if manager_reputation<threshold:
        return {"status":"unlikely","reason":"Manager reputation below this club's game-world hiring requirement","threshold":threshold}
    return {"status":"eligible_for_review","reason":"May apply or be considered, but no appointment or interview is guaranteed","threshold":threshold}


def assess_manager_application_v2(*,manager_reputation,sporting_appeal,league_tier,
                                   top_division_experience=False):
    """Read-only hiring benchmark on the shared, continuous appeal scale."""
    if manager_reputation is None or sporting_appeal is None or league_tier is None:
        return {"status":"unassessed","threshold":None,
                "reason":"Missing verified manager results or squad source data"}
    minimum={1:61,2:43,3:31,4:22}.get(league_tier)
    if minimum is None:
        return {"status":"unassessed","threshold":None,
                "reason":"Unsupported league"}
    threshold=_clamp(max(minimum,round(sporting_appeal*.87)),20,95)
    if league_tier==1 and sporting_appeal>=85 and not top_division_experience:
        threshold=max(threshold,83)
    if manager_reputation<threshold:
        return {"status":"unlikely","threshold":threshold,
                "reason":"Below this club's proposed game-world hiring threshold"}
    return {"status":"eligible_for_review","threshold":threshold,
            "reason":"Application may be reviewed; interview or appointment not guaranteed"}


PAGE="""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{title}} · Reputation Audit</title>
<style>
body{margin:0;background:#111a25;color:#ecf3fb;font:15px system-ui,-apple-system,sans-serif}
header{background:#213449;border-bottom:1px solid #47566c;padding:18px 25px}
main{max-width:1120px;margin:28px auto;padding:0 20px 65px}
a{color:#a8d4fd;text-decoration:none}a:hover{text-decoration:underline}
h1{margin-bottom:8px}.muted{color:#adbecb}.note{background:#263b50;border-left:3px solid #8dc5ec;padding:15px;margin:18px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(185px,1fr));gap:12px}
.card{padding:17px;background:#1b2c3e;border:1px solid #3d5367;border-radius:8px}
.stat{font-size:1.65rem;font-weight:700}
table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #354b62;text-align:left;padding:11px}
th{font-size:.83rem;color:#c5d4e1}td.num{text-align:right;font-variant-numeric:tabular-nums}
form{margin:19px 0}select,button{padding:8px;background:#2c4155;color:white;border:1px solid #586e81}
footer{font-size:.86rem;color:#aebecb;margin-top:30px}
</style></head><body><header>
<a href="/world/explore">← Squad Explorer</a> · <a href="/world/finances">Finances</a> ·
<a href="/world/play">Transfer Desk</a> · <a href="/world/reputations">Updated pyramid model (v2)</a></header><main>
<h1>{{title}}</h1>
<p class="muted">Selected dataset: {{dataset['title']}} · {{model_version}}</p>
<div class="note"><b>Important:</b> these are <b>provisional gameplay scores</b>, not verified club prestige,
official rankings or independently sourced historical reputations. League scores are explicit assumptions;
squad adjustments use EA reference ratings with provisional registration data.
Institutional prestige, real league standing and actual player interest are not yet rated.</div>
{% if mode=='index' %}
<form method="get"><label for="dataset">Starting season: </label><select id="dataset" name="dataset">
{% for d in datasets %}<option value="{{d['dataset_id']}}" {% if d['dataset_id']==dataset['dataset_id'] %}selected{% endif %}>{{d['title']}}</option>{% endfor %}</select>
<label for="league">League: </label><select id="league" name="league">
<option value="">All leagues</option>
{% for l in leagues %}<option value="{{l['competition_id']}}" {% if chosen==l['competition_id'] %}selected{% endif %}>{{l['name']}}</option>{% endfor %}</select>
<button>Apply</button></form>
<div class="grid">
<div class="card"><div class="muted">Clubs with provisional ratings</div><div class="stat">{{summary['count']}}</div></div>
<div class="card"><div class="muted">Squad-supported models</div><div class="stat">{{summary['source_proxy']}}</div></div>
<div class="card"><div class="muted">Prestige assessed</div><div class="stat">0</div></div>
<div class="card"><div class="muted">Historical results incorporated</div><div class="stat">No</div></div>
</div>
<h2>League starting assumptions</h2>
<div class="grid">{% for l in leagues %}<div class="card"><b>{{l['name']}}</b>
<div class="stat">{{l['score']}} / 100</div>
<div class="muted">Tier {{l['tier']}} · simulated starting anchor</div></div>{% endfor %}</div>
<h2>Club reputation audit</h2>
<p><a href="/world/reputations/jobs?dataset={{dataset['dataset_id']}}">Explore hypothetical manager job eligibility →</a></p>
<table><tr><th>Club</th><th>League</th><th>Working appeal</th><th>League baseline</th><th>Squad adjustment</th><th>EA rated players</th><th>Data strength</th></tr>
{% for c in clubs %}<tr>
<td><a href="/world/reputations/club/{{c['club_id']}}?dataset={{dataset['dataset_id']}}">{{c['name']}}</a></td>
<td>{{c['competition_name']}}</td><td class="num"><b>{{c['working_appeal']}}</b></td><td class="num">{{c['league_anchor']}}</td>
<td class="num">{{'%+d'|format(c['squad_adjustment'])}}</td><td class="num">{{c['rated_players']}}</td><td>{{c['confidence']}}</td>
</tr>{% endfor %}</table>
{% elif mode=='jobs' %}
<p><a href="/world/reputations?dataset={{dataset['dataset_id']}}">← Club reputation audit</a></p>
<h2>Explore career job eligibility</h2>
<div class="note">Enter a <b>hypothetical</b> manager-reputation rating to test our
hiring requirements. This is not your recorded PES career rating.
No job offers are generated by this screen, and no application is submitted.</div>
<form method="get"><input type="hidden" name="dataset" value="{{dataset['dataset_id']}}">
<label for="manager">Hypothetical manager reputation (0–100): </label>
<input id="manager" name="manager" type="number" min="0" max="100"
 value="{{manager_input}}" placeholder="Enter a rating">
<label for="experience">Top-flight managerial experience: </label>
<select name="experience" id="experience">
<option value="no" {% if not topflight %}selected{% endif %}>No</option>
<option value="yes" {% if topflight %}selected{% endif %}>Yes</option>
</select> <button>Evaluate clubs</button></form>
<table><tr><th>Club</th><th>Division</th><th>Working club appeal</th><th>Hiring threshold</th><th>Eligibility</th></tr>
{% for c in jobs %}<tr>
<td><a href="/world/reputations/club/{{c['club_id']}}?dataset={{dataset['dataset_id']}}">{{c['name']}}</a></td>
<td>{{c['competition_name']}}</td><td class="num">{{c['working_appeal']}}</td>
<td class="num">{{c['threshold'] if c['threshold'] is not none else '—'}}</td>
<td>{{c['status']|replace('_',' ')}}<small class="muted"> — {{c['reason']}}</small></td>
</tr>{% endfor %}</table>
{% elif mode=='club' %}
<p><a href="/world/reputations?dataset={{dataset['dataset_id']}}">← All clubs</a></p>
<div class="grid">
<div class="card"><div class="muted">Working sporting appeal</div><div class="stat">{{club['working_appeal']}} / 100</div></div>
<div class="card"><div class="muted">League starting score</div><div class="stat">{{club['league_anchor']}}</div></div>
<div class="card"><div class="muted">EA squad adjustment</div><div class="stat">{{'%+d'|format(club['squad_adjustment'])}}</div></div>
<div class="card"><div class="muted">Historical institutional prestige</div><div class="stat">Unknown</div></div>
</div>
<h2>How this club's provisional score was calculated</h2>
<p>League: <b>{{club['competition_name']}}</b> · dataset: {{dataset['title']}}</p>
<p>Starting point: <b>{{club['league_anchor']}}</b>.</p>
<p>Top 16 available squad rating average:
<b>{{club['top_squad_average'] if club['top_squad_average'] is not none else 'Unavailable'}}</b>
from {{club['rated_players']}} rated source players.
Adjustment: <b>{{'%+d'|format(club['squad_adjustment'])}}</b>.</p>
<p>Resulting provisional sporting appeal: <b>{{club['working_appeal']}} / 100</b>.</p>
<div class="note">EA ability data supports only a <b>squad-strength proxy</b>.
It cannot by itself establish historical achievements, club prestige, financial standing,
facilities, supporter base or future prospects. The provisional roster may contain source conflicts.</div>
<p class="muted">Data: {{club['source_label']}} · snapshot {{club['source_date'] or 'Unknown'}} · {{club['confidence']}}.</p>
<p class="muted">{% if club['membership_source_url'] %}<a href="{{club['membership_source_url']}}" target="_blank" rel="noopener noreferrer">League membership source ↗</a>{% else %}No separate membership URL recorded for this snapshot{% endif %}
{% if rating_source_url %} · <a href="{{rating_source_url}}" target="_blank" rel="noopener noreferrer">EA reference rating source ↗</a>{% endif %}</p>
<h2>Job-market prototype</h2>
<p>Minimum manager reputation: <b>{{job['threshold'] if job['threshold'] is not none else 'Not assessed'}}</b>
{% if job['threshold'] is not none %}/100{% endif %}.
This is an eligibility guideline only; no job is offered, and no manager's results have been invented.</p>
{% endif %}
<footer>Reputation model {{model_version}}. Club and league ratings remain independent for each season dataset.
Career performance updates require logged results and are never fabricated. No existing career saves are modified.</footer>
</main></body></html>"""


def create_reputation_blueprint(db_path):
    bp=Blueprint("world_reputation",__name__)
    def connect():
        from world_v2 import initialize_world
        db=sqlite3.connect(str(db_path))
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        initialize_world(db)
        initialize_catalog(db)
        initialize_reputations(db)
        return db

    @bp.get("/world/reputations/legacy")
    def index():
        with connect() as db:
            ds=get_dataset(db,request.args.get("dataset"))
            datasets=db.execute("SELECT * FROM world_datasets ORDER BY season_id DESC,dataset_id").fetchall()
            leagues=db.execute("""SELECT c.competition_id,c.name,c.tier,r.score FROM world_league_reputation_snapshots r
                JOIN world_competitions c ON c.competition_id=r.competition_id
                WHERE r.dataset_id=? ORDER BY c.tier""",(ds["dataset_id"],)).fetchall()
            chosen=request.args.get("league","")
            if chosen not in {l["competition_id"] for l in leagues}:chosen=""
            clubs=db.execute("""SELECT r.*,c.name,comp.name competition_name
                FROM world_club_reputation_snapshots r
                JOIN world_clubs c ON c.club_id=r.club_id
                JOIN world_competitions comp ON comp.competition_id=r.competition_id
                WHERE r.dataset_id=? AND (?='' OR r.competition_id=?)
                ORDER BY r.working_appeal DESC,c.name""",(ds["dataset_id"],chosen,chosen)).fetchall()
            n=db.execute("""SELECT COUNT(*),SUM(CASE WHEN confidence='source-proxy' THEN 1 ELSE 0 END)
                FROM world_club_reputation_snapshots WHERE dataset_id=?""",(ds["dataset_id"],)).fetchone()
            return render_template_string(PAGE,title="Club & League Reputation Audit",mode="index",
                dataset=ds,datasets=datasets,chosen=chosen,leagues=leagues,clubs=clubs,
                model_version=MODEL_VERSION,summary={"count":n[0],"source_proxy":n[1] or 0})

    @bp.get("/world/reputations/club/<int:club_id>")
    def club(club_id):
        with connect() as db:
            ds=get_dataset(db,request.args.get("dataset"))
            row=db.execute("""SELECT r.*,c.name,comp.name competition_name,comp.tier,
                  membership.source_url AS membership_source_url
                FROM world_club_reputation_snapshots r JOIN world_clubs c ON c.club_id=r.club_id
                JOIN world_competitions comp ON comp.competition_id=r.competition_id
                LEFT JOIN world_entries membership ON membership.season_id=?
                  AND membership.club_id=r.club_id
                WHERE r.dataset_id=? AND r.club_id=?""",
                (ds["season_id"],ds["dataset_id"],club_id)).fetchone()
            if row is None:abort(404)
            job=assess_manager_application(manager_reputation=0,
                club_appeal=row["working_appeal"],league_tier=row["tier"])
            rating_source_url=None
            if ds["dataset_id"]=="england-2026-27-fc27":
                from world_fc27_english import SOURCE_URL
                rating_source_url=SOURCE_URL
            return render_template_string(PAGE,title=row["name"]+" · Reputation Audit",
                mode="club",dataset=ds,model_version=MODEL_VERSION,club=row,job=job,
                rating_source_url=rating_source_url)
    @bp.get("/world/reputations/jobs")
    def jobs():
        with connect() as db:
            ds=get_dataset(db,request.args.get("dataset"))
            raw=request.args.get("manager","").strip()
            if raw:
                try:
                    candidate=int(raw)
                except ValueError:
                    abort(400,"Manager reputation must be an integer from 0 to 100")
                if not 0<=candidate<=100:abort(400,"Manager reputation out of range")
            else:
                candidate=None
            topflight=request.args.get("experience","no")=="yes"
            from world_reputation_v2 import initialize_pyramid, MODEL_VERSION as PYRAMID_VERSION
            initialize_pyramid(db)
            rows=db.execute("""SELECT r.club_id,r.sporting_appeal,c.name,comp.name competition_name,
                comp.tier FROM world_pyramid_club_appeal r
                JOIN world_clubs c ON c.club_id=r.club_id
                JOIN world_competitions comp ON comp.competition_id=r.competition_id
                WHERE r.dataset_id=? AND r.model_version=? ORDER BY comp.tier,c.name""",
                (ds["dataset_id"],PYRAMID_VERSION)).fetchall()
            results=[]
            for c in rows:
                outcome=assess_manager_application_v2(manager_reputation=candidate,
                    sporting_appeal=c["sporting_appeal"],league_tier=c["tier"],
                    top_division_experience=topflight)
                results.append(dict(c,working_appeal=c["sporting_appeal"],**outcome))
            return render_template_string(PAGE,title="Job Eligibility Lab",
                mode="jobs",dataset=ds,model_version=PYRAMID_VERSION,jobs=results,
                manager_input=raw,topflight=topflight)

    return bp

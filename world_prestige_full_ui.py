"""Read-only four-division full prestige draft, with detailed evidence and flags.

There is NO approval write path. Existing active careers, approvals, transfer
interest, player registrations and production environment remain untouched.
"""
import csv
import io
import sqlite3

from flask import Blueprint,Response,abort,request,render_template_string
from world_explorer import initialize_catalog,get_dataset
from world_reputation_v2 import initialize_pyramid,MODEL_VERSION as SPORT_MODEL
from world_reputation_progression import initialize_progression
from world_prestige_full import (
    ALL_92,DATASET_ID,FULL_VERSION,DIMENSIONS,CAPACITY_SOURCE,
    HISTORY_SOURCE,FA_SOURCE,LEAGUE_CUP_SOURCE,
    score_club,review_flags,
)

LEAGUES={"ENG1":"Premier League","ENG2":"Championship",
         "ENG3":"League One","ENG4":"League Two"}
CSS="""body{margin:0;background:#111a27;color:#e7f2fd;font:15px system-ui,-apple-system,Segoe UI,Arial,sans-serif}
header{background:#192c40;border-bottom:1px solid #355069;padding:18px 20px}
main{max-width:1300px;margin:25px auto;padding:0 18px 60px}
a{color:#99caff;text-decoration:none}a:hover{text-decoration:underline}
h1{font-size:1.75rem;margin:8px 0}h2{font-size:1.3rem;margin:28px 0 12px}
p{line-height:1.48}.muted{color:#adbed1}.small{font-size:.86rem}
.notice{padding:14px 18px;border-left:3px solid #96bdec;background:#233b54;margin:15px 0}
.warning{border-left-color:#eeb873}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(185px,1fr));gap:12px}
.card{background:#1b3045;border:1px solid #3c566e;border-radius:8px;padding:16px}
.big{font-weight:700;font-size:1.85rem;font-variant-numeric:tabular-nums}
.num{text-align:right;font-variant-numeric:tabular-nums}
table{border-collapse:collapse;width:100%;margin:14px 0 25px}
td,th{padding:10px 11px;border-bottom:1px solid #354c61;text-align:left;vertical-align:top}
th{color:#c6d7e8;font-weight:650;font-size:.83rem}td.num,th.num{text-align:right}
tbody tr:hover{background:#1c3147}
.tag{display:inline-block;border:1px solid #556d83;color:#c6dcf0;padding:2px 8px;border-radius:14px;font-size:.73rem;white-space:nowrap}
input,select,button{padding:9px;background:#263e53;border:1px solid #536d84;color:#f0f6fc;border-radius:5px}
form{display:flex;align-items:end;gap:10px;flex-wrap:wrap;margin:17px 0}
form label{display:block;color:#bed1df;font-size:.85rem}
.pill{padding:6px 10px;border-radius:8px;background:#324a60}
.bar{height:8px;background:#3d5164;border-radius:20px;overflow:hidden;margin-top:5px}
.fill{height:100%;background:#78b9e3}
ul{padding-left:19px}li{padding:4px 0}
footer{color:#93a8ba;font-size:.83rem;margin-top:40px}
"""
PAGE="""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{title}} · PES Clubs Challenge Development</title><style>"""+CSS+"""</style></head>
<body><header><a href="/world/reputations">← Sporting appeal</a> ·
<a href="/world/reputations/prestige/calibration">Original 15-club calibration</a> ·
<a href="/world/reputations/prestige">Prestige evidence</a> ·
<a href="/world/play">Development career desk</a></header><main>
<h1>{{title}}</h1>
<p class="muted">2026/27 development · {{version}} · separate from sporting appeal</p>
<div class="notice warning"><b>92 provisional gameplay proposals — not 92 verified historical scores.</b>
All 92 clubs have a calculable draft score and traceable review references;
the 77 new proposals have major-honour counts and three editorial bands
requiring individual source verification.
No score is approved automatically or used for player transfers, agent
decisions or managerial applications. A source link is a place to check a fact,
not proof that every draft input has already been checked.</div>
{% if mode=='list' %}
<div class="grid">
<div class="card"><div class="muted">English clubs covered</div><div class="big">{{all_rows|length}} / 92</div></div>
<div class="card"><div class="muted">Previous calibration clubs retained</div><div class="big">{{original_count}}</div></div>
<div class="card"><div class="muted">New draft proposals</div><div class="big">{{new_count}}</div></div>
<div class="card"><div class="muted">Independently approved records</div><div class="big">{{approved_count}}</div></div>
</div>
<h2>Agreed 100-point rubric</h2>
<div class="grid">{% for name,part in dimensions.items() %}
<div class="card"><div class="muted">{{part[0]}}</div><div class="big">{{part[1]}}</div></div>
{% endfor %}</div>
<p class="small muted">Domestic means <b>top-flight championship, FA Cup and League Cup</b> only;
second/third/fourth-tier league titles do not count as major domestic honours.
Stadium capacity is a transparent infrastructure proxy, not attendance.
Identity, history and Europe are editorial bands that need independent review.</p>
<h2>Review the four divisions</h2>
<p><a href="/world/reputations/prestige/all.csv">Download full 92-club audit CSV ↗</a>
 · the CSV includes source links, all five components, sporting appeal and source-review status.</p>
<form method="get">
<div><label for="league">League</label><select id="league" name="league">
<option value="">All 92</option>
{% for key,value in leagues.items() %}
<option value="{{key}}" {% if selected_league==key %}selected{% endif %}>{{value}}</option>
{% endfor %}</select></div>
<div><label for="sort">Order by</label><select id="sort" name="sort">
<option value="prestige" {% if selected_sort=='prestige' %}selected{% endif %}>Prestige: highest first</option>
<option value="sporting" {% if selected_sort=='sporting' %}selected{% endif %}>Sporting appeal: highest first</option>
<option value="name" {% if selected_sort=='name' %}selected{% endif %}>Club name</option>
<option value="gap" {% if selected_sort=='gap' %}selected{% endif %}>Largest prestige/sporting difference</option>
</select></div>
<div><label for="attention">Review focus</label><select id="attention" name="attention">
<option value="all" {% if selected_attention=='all' %}selected{% endif %}>All clubs</option>
<option value="flags" {% if selected_attention=='flags' %}selected{% endif %}>Comparison flags only</option>
<option value="new" {% if selected_attention=='new' %}selected{% endif %}>New 77 requiring source review</option>
</select></div><button type="submit">Apply</button></form>
{% if groups %}
{% for group in groups %}
<h2>{{group['name']}} ({{group['total']}} {% if selected_attention=='all' %}clubs{% else %}shown{% endif %})</h2>
<table><thead><tr>
<th>Club</th><th class="num">Prestige draft</th><th class="num">Sporting</th>
<th class="num">Domestic</th><th class="num">Europe</th><th class="num">History</th>
<th class="num">Ground</th><th class="num">Identity</th><th>Evidence status / outliers</th>
</tr></thead><tbody>
{% for c in group['rows'] %}
<tr>
<td><a href="/world/reputations/prestige/all/{{c['club_id']}}">{{c['name']}}</a></td>
<td class="num"><b>{{c['score']}}</b></td>
<td class="num">{{c['sporting'] if c['sporting'] is not none else '—'}}</td>
<td class="num">{{c['domestic']}}</td><td class="num">{{c['europe']}}</td>
<td class="num">{{c['longevity']}}</td><td class="num">{{c['scale']}}</td>
<td class="num">{{c['identity']}}</td>
<td><span class="tag">{{'Original 15, review' if c['source_status']=='original_15_review_only' else 'New proposal, unverified'}}</span>
{% if c['comparative_flags'] %}
<p class="small muted">{{c['comparative_flags']|join(' · ')}}</p>{% endif %}
</td></tr>
{% endfor %}
</tbody></table>
{% endfor %}
{% else %}
<p>No clubs match that review filter.</p>
{% endif %}
<p class="notice">A large gap between sporting appeal and institutional
prestige is <b>not automatically a scoring error</b>. It may be realistic
for a well-performing newer club or a former giant in a lower division.
The flags only prompt review, never change a score.</p>
{% elif mode=='detail' %}
<p><a href="/world/reputations/prestige/all?league={{club['league']}}">← {{league_name}} comparison</a>
 · <a href="/world/reputations/v2/club/{{club['club_id']}}">Starting sporting appeal breakdown</a></p>
<div class="grid">
<div class="card"><div class="muted">Proposed historical prestige</div><div class="big">{{club['score']}} / 100</div></div>
<div class="card"><div class="muted">Starting sporting appeal</div>
<div class="big">{{club['sporting'] if club['sporting'] is not none else 'Unknown'}}</div></div>
<div class="card"><div class="muted">Starting division</div><div class="big" style="font-size:1.2rem">{{league_name}}</div></div>
<div class="card"><div class="muted">Approved institutional prestige</div>
<div class="big">{{club['approved_score'] if club['approved_score'] is not none else 'Not approved'}}</div></div></div>
<h2>How this rating was calculated</h2>
{% for key,part in dimensions.items() %}
<div class="card" style="margin:9px 0">
<div style="display:flex;justify-content:space-between">
<strong>{{part[0]}}</strong><strong>{{club[key]}} / {{part[1]}}</strong></div>
<div class="bar"><div class="fill" style="width:{{club[key]/part[1]*100}}%"></div></div>
</div>
{% endfor %}
<h2>Provisional input records</h2>
<table><tr><th>Input</th><th>Value or editorial basis</th></tr>
<tr><td>Top-flight league championship titles</td><td>{{club['league_titles']}}</td></tr>
<tr><td>FA Cup victories</td><td>{{club['fa_cups']}}</td></tr>
<tr><td>League Cup victories</td><td>{{club['league_cups']}}</td></tr>
<tr><td>Ground capacity</td><td>{{'{:,}'.format(club['stadium'])}} · coarse size proxy</td></tr>
<tr><td>Continental pedigree</td><td>Initial editorial assessment {{club['raw_europe']}} / 20,
weighted to {{club['europe']}} / 15</td></tr>
<tr><td>Historical continuity and standing</td><td>Initial editorial assessment {{club['raw_longevity']}} / 20,
weighted to {{club['longevity']}} / 35</td></tr>
<tr><td>Club identity</td><td>Initial editorial assessment {{club['identity']}} / 10</td></tr>
<tr><td>Input confidence</td><td>{{'Previously reviewed calibration sample, still unapproved' if club['source_status']=='original_15_review_only' else 'New draft; honour totals and editorial bands need direct source review'}}</td></tr>
</table>
<p>{{club['heritage']}}</p>
<div class="notice warning"><b>Manual checks needed before approval:</b>
{% if club['source_status']=='proposed_counts_pending_review' %}
This club is from the new 77-club tranche. Its trophy counts and subjective
assessment require independent confirmation from the linked archives.
{% else %}This club belongs to the original 15-club calibration. The
original editorial assessments are preserved, without automatic approval.{% endif %}
</div>
{% if club['comparative_flags'] %}
<h2>Comparative outlier checks</h2><ul>
{% for issue in club['comparative_flags'] %}<li>{{issue}}</li>{% endfor %}
</ul>{% endif %}
<h2>Source and review links</h2>
<ul>
<li><a href="{{club['historical_source']}}" target="_blank" rel="noopener noreferrer">Football Club History Database</a>
 — seasonal league and club-history reference index</li>
<li><a href="{{capacity_source}}" target="_blank" rel="noopener noreferrer">Stadium-capacity directory</a>
 — check capacity and permitted restrictions</li>
<li><a href="{{fa_source}}" target="_blank" rel="noopener noreferrer">The FA historic results</a>
 — validate FA Cup total</li>
<li><a href="{{league_cup_source}}" target="_blank" rel="noopener noreferrer">League Cup winners by year</a>
 — validate League Cup total</li>
<li><a href="{{club['research_url']}}" target="_blank" rel="noopener noreferrer">Search this club's historical records</a>
 — research aid, not a verified citation</li>
{% for category,label,url,claim in club['sources'] %}
{% if club['source_status']=='original_15_review_only' %}
<li><a href="{{url}}" target="_blank" rel="noopener noreferrer">{{label}}</a>
 — {{claim}}</li>
{% endif %}
{% endfor %}
</ul>
{% endif %}
<footer>No writes to approved reputation, career saves, transfer agents or original PES challenges.
PES squad strength and historical prestige remain independent variables.</footer>
</main></body></html>"""


def create_full_prestige_blueprint(db_path):
    bp=Blueprint("world_prestige_full",__name__)

    def connect():
        from world_v2 import initialize_world
        conn=sqlite3.connect(str(db_path))
        conn.row_factory=sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        initialize_world(conn)
        initialize_catalog(conn)
        initialize_pyramid(conn)
        initialize_progression(conn)
        return conn

    def rows_with_career_sources(conn):
        dataset=get_dataset(conn,DATASET_ID)
        rows=conn.execute("""SELECT c.club_id,c.name,e.competition_id,
            a.sporting_appeal,r.prestige_score
            FROM world_dataset_entries e JOIN world_clubs c ON c.club_id=e.club_id
            LEFT JOIN world_pyramid_club_appeal a
              ON a.dataset_id=e.dataset_id AND a.club_id=e.club_id
              AND a.model_version=?
            LEFT JOIN world_reputation_prestige_reviews r
              ON r.dataset_id=e.dataset_id AND r.club_id=e.club_id
            WHERE e.dataset_id=?""",(SPORT_MODEL,DATASET_ID)).fetchall()
        by_name={r["name"]:r for r in rows}
        out=[]
        for c in ALL_92:
            member=by_name.get(c["name"])
            if member is None or member["competition_id"]!=c["league"]:
                raise RuntimeError("2026/27 club has mismatched database membership: "+c["name"])
            calculated=score_club(c)
            flag=review_flags(c,score=calculated["score"],
                              sporting_appeal=member["sporting_appeal"])
            comparative=tuple(f for f in flag if not f.startswith("Honours counts"))
            out.append(dict(c,**calculated,
                club_id=member["club_id"],
                sporting=member["sporting_appeal"],
                approved_score=member["prestige_score"],
                raw_europe=c["europe"],
                raw_longevity=c["longevity"],
                comparative_flags=comparative))
        return dataset,out

    def render(mode,title,**kwargs):
        return render_template_string(
            PAGE,mode=mode,title=title,version=FULL_VERSION,leagues=LEAGUES,
            dimensions=DIMENSIONS,capacity_source=CAPACITY_SOURCE,
            fa_source=FA_SOURCE,league_cup_source=LEAGUE_CUP_SOURCE,
            **kwargs)

    @bp.get("/world/reputations/prestige/all")
    def list_all():
        with connect() as conn:
            ds,items=rows_with_career_sources(conn)
            league=request.args.get("league","")
            if league not in LEAGUES:league=""
            sort=request.args.get("sort","prestige")
            if sort not in ("prestige","sporting","gap","name"):sort="prestige"
            attention=request.args.get("attention","all")
            if attention not in ("all","flags","new"):attention="all"
            groups=[]
            for division,label in LEAGUES.items():
                if league and division!=league:continue
                rows=[c for c in items if c["league"]==division]
                if attention=="flags":rows=[c for c in rows if c["comparative_flags"]]
                if attention=="new":rows=[c for c in rows
                                          if c["source_status"]=="proposed_counts_pending_review"]
                if sort=="name":rows.sort(key=lambda c:c["name"])
                elif sort=="sporting":
                    rows.sort(key=lambda c:(c["sporting"] is None,
                                             -(c["sporting"] or 0),c["name"]))
                elif sort=="gap":
                    rows.sort(key=lambda c:(c["sporting"] is None,
                        -abs((c["sporting"] or 0)-c["score"]),c["name"]))
                else:rows.sort(key=lambda c:(-c["score"],c["name"]))
                if rows:groups.append(dict(id=division,name=label,rows=rows,total=len(rows)))
            return render("list","92-club Historical Prestige Review",
                dataset=ds,groups=groups,all_rows=items,selected_league=league,
                selected_sort=sort,selected_attention=attention,
                original_count=sum(c["source_status"]=="original_15_review_only" for c in items),
                new_count=sum(c["source_status"]=="proposed_counts_pending_review" for c in items),
                approved_count=sum(c["approved_score"] is not None for c in items))

    @bp.get("/world/reputations/prestige/all.csv")
    def export_csv():
        """The complete transparent proposal, not a verified prestige database."""
        with connect() as conn:
            _dataset,items=rows_with_career_sources(conn)
            output=io.StringIO()
            writer=csv.writer(output)
            writer.writerow((
                "club","2026_27_division","proposed_prestige","sporting_appeal",
                "major_domestic_honours_points","european_points",
                "historical_standing_points","stadium_scale_points","identity_points",
                "top_division_titles","fa_cup_titles","league_cup_titles",
                "stadium_capacity","source_status","comparative_review_flags",
                "historical_record_reference","stadium_reference",
                "fa_cup_history_reference","league_cup_history_reference",
                "club_specific_research_search"))
            for item in items:
                writer.writerow((
                    item["name"],LEAGUES[item["league"]],item["score"],
                    item["sporting"],item["domestic"],item["europe"],
                    item["longevity"],item["scale"],item["identity"],
                    item["league_titles"],item["fa_cups"],item["league_cups"],
                    item["stadium"],item["source_status"],
                    "; ".join(item["comparative_flags"]),
                    item["historical_source"],CAPACITY_SOURCE,FA_SOURCE,
                    LEAGUE_CUP_SOURCE,item["research_url"]))
            return Response(
                output.getvalue(),mimetype="text/csv; charset=utf-8",
                headers={"Content-Disposition":
                         'attachment; filename="pes_prestige_92_review.csv"',
                         "Cache-Control":"no-store"})

    @bp.get("/world/reputations/prestige/all/<int:club_id>")
    def detail(club_id):
        with connect() as conn:
            ds,items=rows_with_career_sources(conn)
            item=next((c for c in items if c["club_id"]==club_id),None)
            if item is None:abort(404)
            return render("detail",item["name"]+" · Prestige Audit",
                          dataset=ds,club=item,league_name=LEAGUES[item["league"]])

    return bp

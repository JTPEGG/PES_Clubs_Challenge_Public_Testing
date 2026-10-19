"""GET-only scenario laboratory for versioned fictional player preferences.

Shows actual source club sporting ratings and provisional historical prestige,
but all player ages, overall ratings, wage terms and negotiations are
hypothetical. No career ID, signing, offer or contract is created.
"""
import sqlite3
from flask import Blueprint,abort,render_template_string,request

from world_v2 import initialize_world
from world_explorer import initialize_catalog
from world_reputation_v2 import initialize_pyramid,MODEL_VERSION as SPORT_MODEL
from world_prestige_full import ALL_92,DATASET_ID,FULL_VERSION,score_club
from world_selling_club import (evaluate_selling_club, SELLER_POLICY_VERSION,
    SQUAD_ROLES, ROLE_LABELS as SELLER_ROLE_LABELS,
    FINANCIAL_STATES, REPLACEMENT_STATES, SELLER_STANCES)

from world_player_decisions import (
    DECISION_V2_VERSION,ROLES,SELECTABLE_ROLES,ROLE_LABELS,canonical_role,
    PLAYER_CURRENT_ROLES,RENEWAL_STATES,EUROPE_LABELS,
    evaluate_player_choice_v2,agent_minimum_wage_v2,
    contract_length_consideration,
)

PAGE="""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Player Decision Laboratory · PES Clubs Challenge</title>
<style>
body{margin:0;background:#111c29;color:#f2f7fd;font:15px system-ui,-apple-system,Segoe UI,Arial}
header{padding:18px 25px;background:#1b2f43}main{max-width:1100px;margin:22px auto 55px;padding:0 20px}
a{color:#abd8fc}h1{font-size:1.8rem}.muted{color:#b6c5d5}
.notice{background:#23394c;border-left:3px solid #96c2e8;padding:15px 18px;margin:16px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}
.card{padding:16px;background:#1c3044;border:1px solid #415b73;border-radius:9px}
.strong{font-size:1.65rem;font-weight:700}form{display:flex;flex-wrap:wrap;gap:12px;align-items:end}
.field{flex:1;min-width:178px}label{display:block;margin-bottom:6px;font-size:.84rem;color:#c4d4e3}
input,select,button{padding:10px 11px;background:#29445b;color:#f6fbff;border:1px solid #698099;border-radius:6px;max-width:100%;box-sizing:border-box}
button{cursor:pointer;background:#315d83}h2{margin-top:25px}
li{padding:5px 0}footer{margin-top:32px;color:#9bb0c3}
</style></head><body>
<header><a href="/world/play">← Career desk</a> ·
<a href="/world/reputations/prestige/all">Club prestige audit</a> ·
<a href="/world/reputations/progression">Sporting appeal preview</a> ·
<a href="/world/selling-club">Selling club laboratory</a></header>
<main><h1>Player &amp; Agent Decision Laboratory</h1>
<p class="muted">{{decision_version}} · {{prestige_version}}</p>
<div class="notice"><b>Hypothetical gameplay scenario, not a real player statement.</b>
The clubs' sporting scores use the 2026/27 EA-reference snapshot and their
historical prestige comes from the provisional, unapproved 92-club draft.
The player, age, current wage, current club squad status, transfer listing,
renewal status, continental qualification and proposed contract are
<b>explicit fictional assumptions</b>,
not verified real-player information.
This page is read-only and cannot offer a player a contract or change
a registered PES squad.</div>
<form method="get">
<div class="field"><label for="buyer">Interested club</label>
<select id="buyer" name="buyer">{% for club in clubs %}
<option value="{{club['club_id']}}" {% if club['club_id']==buyer['club_id'] %}selected{% endif %}>{{club['name']}}</option>
{% endfor %}</select></div>
<div class="field"><label for="seller">Player's current club</label>
<select id="seller" name="seller">{% for club in clubs %}
<option value="{{club['club_id']}}" {% if club['club_id']==seller['club_id'] %}selected{% endif %}>{{club['name']}}</option>
{% endfor %}</select></div>
<div class="field"><label for="age">Fictional player age</label>
<input type="number" id="age" name="age" min="17" max="40" value="{{age}}" required></div>
<div class="field"><label for="overall">EA-style overall (hypothetical)</label>
<input type="number" id="overall" name="overall" min="45" max="95" value="{{overall}}" required></div>
<div class="field"><label for="current_wage">Current weekly wage (£)</label>
<input type="number" id="current_wage" name="current_wage" min="0" max="1000000" step="500" value="{{current_wage if current_wage is not none else ''}}" placeholder="Unknown — enter if known"></div>
<div class="field"><label for="current_role">Status at current club</label>
<select id="current_role" name="current_role">
<option value="unknown" {% if current_role=='unknown' %}selected{% endif %}>Unknown — needs review</option>
<option value="key_player" {% if current_role=='key_player' %}selected{% endif %}>Key Player</option>
<option value="regular_starter" {% if current_role=='regular_starter' %}selected{% endif %}>Regular Starter</option>
<option value="rotation" {% if current_role=='rotation' %}selected{% endif %}>Rotation Player</option>
<option value="fringe" {% if current_role=='fringe' %}selected{% endif %}>Fringe Player</option>
</select></div>
<div class="field"><label for="listed">Transfer-listed by current club?</label>
<select id="listed" name="listed">
<option value="no" {% if listed=='no' %}selected{% endif %}>No</option>
<option value="yes" {% if listed=='yes' %}selected{% endif %}>Yes</option>
<option value="unknown" {% if listed=='unknown' %}selected{% endif %}>Unknown — needs review</option>
</select></div>
<div class="field"><label for="renewal">Contract / renewal prospects</label>
<select id="renewal" name="renewal">
<option value="renewal_offered" {% if renewal=='renewal_offered' %}selected{% endif %}>Renewal available / expected to stay (scenario assumption)</option>
<option value="not_offered" {% if renewal=='not_offered' %}selected{% endif %}>Not being offered a renewal</option>
<option value="unknown" {% if renewal=='unknown' %}selected{% endif %}>Unknown — needs review</option>
</select></div>
<div class="field"><label for="seller_europe">European football at current club</label>
<select id="seller_europe" name="seller_europe">
{% for code,label in europe_labels.items() %}
<option value="{{code}}" {% if code==seller_europe %}selected{% endif %}>{{label}}</option>
{% endfor %}</select></div>
<div class="field"><label for="buyer_europe">European football at interested club</label>
<select id="buyer_europe" name="buyer_europe">
{% for code,label in europe_labels.items() %}
<option value="{{code}}" {% if code==buyer_europe %}selected{% endif %}>{{label}}</option>
{% endfor %}</select></div>
<div class="field"><label for="role">Promised squad role</label>
<select id="role" name="role">{% for role in roles %}
<option value="{{role}}" {% if role==selected_role %}selected{% endif %}>{{role_labels[role]}}</option>
{% endfor %}</select></div>
<div class="field"><label for="wage">Offered weekly wage (£)</label>
<input type="number" id="wage" name="wage" min="0" max="500000" value="{{wage if wage is not none else ''}}" step="500" placeholder="Not yet offered"></div>
<div class="field"><label for="years">Contract duration</label>
<select id="years" name="years">{% for value in [1,2,3,4,5] %}
<option value="{{value}}" {% if value==years %}selected{% endif %}>{{value}} year{{'s' if value!=1 else ''}}</option>
{% endfor %}</select></div>
<div class="field"><label for="rival">Simulated rival pressure</label>
<select id="rival" name="rival">
<option value="0" {% if rival==0 %}selected{% endif %}>None</option>
<option value="18" {% if rival==18 %}selected{% endif %}>Moderate (hypothetical)</option>
<option value="32" {% if rival==32 %}selected{% endif %}>Strong (hypothetical)</option>
</select></div>
<button type="submit">Evaluate scenario</button></form>
{% if error %}<p class="notice">{{error}}</p>{% else %}
<h2>Club comparison</h2>
<div class="grid">
<div class="card"><div class="muted">Interested club — {{buyer['name']}}</div>
<div class="strong">{{buyer['sporting'] if buyer['sporting'] is not none else 'Unknown'}}</div>
<div class="muted">Sporting appeal</div>
<div class="strong">{{buyer['prestige']}}</div><div class="muted">Proposed historical prestige</div>
<div class="muted">European football (scenario): {{europe_labels[buyer_europe]}}</div>
</div>
<div class="card"><div class="muted">Current club — {{seller['name']}}</div>
<div class="strong">{{seller['sporting'] if seller['sporting'] is not none else 'Unknown'}}</div>
<div class="muted">Sporting appeal</div>
<div class="strong">{{seller['prestige']}}</div><div class="muted">Proposed historical prestige</div>
<div class="muted">European football (scenario): {{europe_labels[seller_europe]}}</div>
</div>
<div class="card"><div class="muted">Player career stage</div>
<div class="strong">{{result['player_phase']|capitalize if result['player_phase'] else 'Unassessed'}}</div>
<div class="muted">Fictional {{age}}-year-old, OVR {{overall}}</div></div>
</div>
<h2>Player decision</h2>
<div class="card"><div class="strong">
{% if result['decision']=='uninterested' %}Not Interested
{% elif result['decision']=='needs_assurances' and result['issue']=='wage' %}Higher Wages Required
{% elif result['decision']=='needs_assurances' and result['issue']=='role' %}Squad Role Guarantee Required
{% elif result['decision']=='needs_assurances' and result['issue']=='wage_and_role' %}Higher Wages and Role Guarantee Required
{% else %}{{result['decision']|replace('_',' ')|title}}{% endif %}</div>
<p>{{result['reason']}}</p><p class="muted">Current wage: {% if current_wage is not none %}£{{"{:,}".format(current_wage)}}{% else %}Unknown{% endif %} per week.
Current club role: {{role_labels[current_role] if current_role in role_labels else 'Unknown'}}.
Transfer-listed: {{listed}}. Contract renewal: {{renewal|replace('_',' ')}}.
Current European competition: {{europe_labels[seller_europe]}}.
Interested club's European competition: {{europe_labels[buyer_europe]}}.</p>
<div class="muted">Minimum promised squad role:
{{role_labels[result['required_role']] if result['required_role'] in role_labels else result['required_role']|replace('_',' ')|title}}
{% if result['role_satisfied'] is sameas true %}
 · <b>Role requirement already met</b>
{% elif result['role_satisfied'] is sameas false %}
 · <b>Role guarantee still needed</b>{% endif %}</div></div>
<h2>Agent negotiation preview</h2>
<div class="grid">
<div class="card"><div class="muted">Current salary benchmark (scenario)</div>
<div class="strong">{% if current_wage is not none %}£{{'{:,}'.format(current_wage)}}{% else %}Unknown{% endif %}</div></div>
<div class="card"><div class="muted">Adjusted agent wage demand</div>
<div class="strong">{% if demand is not none %}£{{'{:,}'.format(demand)}}{% else %}No negotiations{% endif %}</div></div>
<div class="card"><div class="muted">Offered salary</div><div class="strong">{% if wage is not none %}£{{'{:,}'.format(wage)}}{% else %}Not offered{% endif %}</div></div>
<div class="card"><div class="muted">Simulated negotiation signal</div>
<div class="strong">{{agent_signal}}</div></div>
</div>
{% if contract_warning %}<p class="muted">{{contract_warning}} — agent adds a soft wage premium in a new career.</p>{% endif %}
<div class="notice">A £15k offer to a £150k/week regular is not a plausible
reason to leave a stronger club. A contract opportunity to remain matters,
especially for elite players aged 24–31. Missing out on Champions League
football matters too. Transfer-listing or confirmed non-renewal can change
the situation, but no amount of money bypasses a severe
sporting refusal. Rival pressure is a laboratory assumption here;
development careers only count actual recorded sandbox offers.</div>
{% endif %}
<footer>No player birth records, club histories, PES lineups, career negotiations
or contracts are changed by this GET-only laboratory.</footer>
</main></body></html>"""



SELLER_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Selling Club Laboratory · PES Clubs Challenge</title>
<style>
body{margin:0;background:#111c29;color:#eef6ff;font:15px system-ui,sans-serif}
header{padding:18px;background:#1b2f43}a{color:#abd8fc}
main{max-width:1100px;margin:24px auto;padding:0 20px 45px}
.notice,.card{padding:16px;background:#1c3044;border:1px solid #415b73;border-radius:9px;margin:14px 0}
form{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:14px}
label{display:block;font-size:.85rem;color:#c4d4e3;margin-bottom:7px}
input,select,button{width:100%;box-sizing:border-box;padding:11px;border-radius:6px;background:#29445b;color:white;border:1px solid #698099}
button{cursor:pointer;background:#315d83}.big{font-size:1.6rem;font-weight:700}
.muted{color:#b6c5d5}
</style></head><body><header>
<a href="/world/player-decisions">← Player &amp; Agent Laboratory</a> ·
<a href="/world/play">Career desk</a></header>
<main><h1>Selling Club Decision Laboratory</h1>
<p class="muted">{{version}} · GET-only fictional scenarios</p>
<div class="notice">All contract terms, valuations, transfer-list status, finances,
replacement prospects and player wishes start <b>unknown</b>.
No real player contract or transfer valuation is looked up or invented.
This exercise does not record offers, alter a save, move a player, or create a contract.
The selling club's approval is independent of the player's sporting choice.</div>
<form method="get">
<div><label>Current club (label only)</label><select name="club">
{% for name in clubs %}<option value="{{name}}" {% if name==club %}selected{% endif %}>{{name}}</option>{% endfor %}
</select></div>
<div><label>Player age (optional)</label><input name="age" type="number" min="16" max="45" value="{{age if age is not none else ''}}" placeholder="Unknown"></div>
<div><label>Scenario market value (£)</label><input name="market_value" type="number" min="0" step="50000" value="{{market_value if market_value is not none else ''}}" placeholder="Unknown"></div>
<div><label>Offered transfer fee (£)</label><input name="offer_fee" type="number" min="0" step="50000" value="{{offer_fee if offer_fee is not none else ''}}" placeholder="No offer yet"></div>
<div><label>Years left on existing contract</label><select name="contract_years">
<option value="unknown">Unknown</option>
{% for n in range(0,7) %}<option value="{{n}}" {% if contract_years==n %}selected{% endif %}>{{n}}</option>{% endfor %}</select></div>
<div><label>Current squad role</label><select name="squad_role">
<option value="unknown">Unknown</option>
{% for code in roles %}<option value="{{code}}" {% if squad_role==code %}selected{% endif %}>{{role_labels[code]}}</option>{% endfor %}</select></div>
<div><label>Transfer listed?</label><select name="transfer_listed">
<option value="unknown">Unknown</option>
<option value="yes" {% if transfer_listed is sameas true %}selected{% endif %}>Yes</option>
<option value="no" {% if transfer_listed is sameas false %}selected{% endif %}>No</option>
</select></div>
<div><label>Player requesting departure?</label><select name="player_wants_exit">
<option value="unknown">Unknown</option>
<option value="yes" {% if player_wants_exit is sameas true %}selected{% endif %}>Yes</option>
<option value="no" {% if player_wants_exit is sameas false %}selected{% endif %}>No</option>
</select></div>
<div><label>Selling club finances</label><select name="financial_state">
<option value="unknown">Unknown</option>
<option value="stable" {% if financial_state=='stable' %}selected{% endif %}>Stable</option>
<option value="cash_needed" {% if financial_state=='cash_needed' %}selected{% endif %}>Needs transfer proceeds</option>
<option value="distressed" {% if financial_state=='distressed' %}selected{% endif %}>Financial distress</option>
</select></div>
<div><label>Replacement availability</label><select name="replacement">
<option value="unknown">Unknown</option>
<option value="available" {% if replacement=='available' %}selected{% endif %}>Suitable replacement available</option>
<option value="difficult" {% if replacement=='difficult' %}selected{% endif %}>Difficult to replace</option>
</select></div>
<div><label>Selling club intentions</label><select name="seller_stance">
<option value="unknown">Unknown</option>
<option value="retain" {% if seller_stance=='retain' %}selected{% endif %}>Actively retain</option>
<option value="neutral" {% if seller_stance=='neutral' %}selected{% endif %}>Consider offers</option>
<option value="sell" {% if seller_stance=='sell' %}selected{% endif %}>Willing to sell</option>
</select></div>
<div><button type="submit">Evaluate selling club</button></div>
</form>
<div class="card">
<div class="muted">{{club}} · Selling club stance</div>
<div class="big">{{result['decision']|capitalize}}</div>
<p>{{result['reason']}}</p>
<p>Scenario asking price:
<strong>{% if result['asking_price'] is none %}Not determined{% else %}£{{'{:,}'.format(result['asking_price'])}}{% endif %}</strong></p>
{% if result['fee_shortfall'] is not none %}<p>Bid shortfall: £{{'{:,}'.format(result['fee_shortfall'])}}</p>{% endif %}
</div>
<div class="notice">A simulated club acceptance is not a completed deal:
the player, agent and registration rules must also agree.
All monetary amounts here are hypothetical scenario values.</div>
</main></body></html>"""

def create_player_decisions_blueprint(db_path):
    bp=Blueprint("world_player_decisions",__name__)
    def connect():
        conn=sqlite3.connect(str(db_path))
        conn.row_factory=sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        initialize_world(conn)
        initialize_catalog(conn)
        initialize_pyramid(conn)
        return conn

    @bp.get("/world/player-decisions")
    def lab():
        with connect() as conn:
            from world_explorer import get_dataset
            get_dataset(conn,DATASET_ID)
            teams=conn.execute("""SELECT c.club_id,c.name,comp.tier,r.sporting_appeal
                FROM world_dataset_entries e
                JOIN world_clubs c ON c.club_id=e.club_id
                JOIN world_competitions comp ON comp.competition_id=e.competition_id
                LEFT JOIN world_pyramid_club_appeal r
                    ON r.club_id=e.club_id AND r.dataset_id=e.dataset_id
                    AND r.model_version=?
                WHERE e.dataset_id=? ORDER BY c.name""",(SPORT_MODEL,DATASET_ID)).fetchall()
            scores={p["name"]:score_club(p)["score"] for p in ALL_92}
            clubs=[dict(club_id=x["club_id"],name=x["name"],tier=x["tier"],
                        sporting=x["sporting_appeal"],prestige=scores[x["name"]])
                   for x in teams]
            by_id={str(x["club_id"]):x for x in clubs}
            defaults={x["name"]:x for x in clubs}
            buyer=by_id.get(request.args.get("buyer",""),defaults["Nottingham Forest"])
            seller=by_id.get(request.args.get("seller",""),defaults["Arsenal"])
            try:
                age=int(request.args.get("age",27))
                overall=int(request.args.get("overall",90))
                current_wage=(int(request.args["current_wage"]) if request.args.get("current_wage","").strip() else None)
                current_role=request.args.get("current_role","unknown")
                listed=request.args.get("listed","unknown")
                renewal=request.args.get("renewal","unknown")
                buyer_europe=request.args.get("buyer_europe","unknown")
                seller_europe=request.args.get("seller_europe","unknown")
                wage=(int(request.args["wage"]) if request.args.get("wage","").strip() else None)
                years=int(request.args.get("years",3))
                rival=int(request.args.get("rival",0))
                role=request.args.get("role","unspecified")
                if not (17<=age<=40 and 45<=overall<=95 and (wage is None or 0<=wage<=500_000)
                        and (current_wage is None or 0<=current_wage<=1_000_000) and
                        years in (1,2,3,4,5) and rival in (0,18,32)
                        and role in ROLES and current_role in PLAYER_CURRENT_ROLES
                        and listed in ("no","yes","unknown") and renewal in RENEWAL_STATES
                        and buyer_europe in EUROPE_LABELS and seller_europe in EUROPE_LABELS):
                    raise ValueError("Scenario selections outside supported bounds")
            except ValueError as exc:
                abort(400,description=str(exc))
            result=evaluate_player_choice_v2(
                buyer_tier=buyer["tier"],seller_tier=seller["tier"],
                buyer_score=buyer["sporting"],seller_score=seller["sporting"],
                buyer_prestige=buyer["prestige"],seller_prestige=seller["prestige"],
                overall=overall,age=age,role_promise=role,
                current_wage=current_wage,
                current_role=current_role,transfer_listed=(
                    None if listed=="unknown" else listed=="yes"),
                renewal_status=renewal,offered_wage=wage,
                buyer_europe=buyer_europe,seller_europe=seller_europe,
                competitor_pressure=rival)
            demand=agent_minimum_wage_v2(choice=result)
            contract_warning=contract_length_consideration(
                phase=result.get("player_phase"),years=years) if result.get("player_phase") else None
            if contract_warning and demand is not None:
                demand=max(demand,round(demand*1.10/500)*500)
                # Keep the agent demand, player decision and displayed shortfall
                # consistent when contract duration raises the minimum.
                if result["decision"] in ("open_to_talks","needs_assurances"):
                    result={**result, "minimum_wage":demand,
                            "wage_shortfall":max(0,demand-wage) if wage is not None else None}
                    if wage is not None and wage<demand and result["decision"]=="open_to_talks":
                        result={**result,"decision":"needs_assurances","issue":"wage",
                                "reason":result["reason"]+f" Contract duration raises the agent wage requirement to £{demand:,}/week."}
            if not result["can_negotiate"]:
                agent_signal="Refusal / review"
            elif result["decision"]=="needs_assurances":
                agent_signal={
                    "wage":"Higher wage offer needed",
                    "role":"Squad role promise needed",
                    "wage_and_role":"Salary and role guarantee needed",
                }.get(result.get("issue"),"Terms require review")
            elif demand is not None and wage is not None and wage>=demand:
                agent_signal="Terms acceptable"
            else:
                agent_signal="Counteroffer likely"
            return render_template_string(
                PAGE,decision_version=DECISION_V2_VERSION,prestige_version=FULL_VERSION,
                clubs=clubs,buyer=buyer,seller=seller,age=age,overall=overall,
                current_wage=current_wage,current_role=current_role,listed=listed,
                renewal=renewal,buyer_europe=buyer_europe,seller_europe=seller_europe,
                europe_labels=EUROPE_LABELS,selected_role=role,
                roles=SELECTABLE_ROLES,role_labels=ROLE_LABELS,
                wage=wage,years=years,rival=rival,
                result=result,demand=demand,agent_signal=agent_signal,
                contract_warning=contract_warning,error=None)

    @bp.get("/world/selling-club")
    def selling_club_lab():
        def optional_int(name):
            value=request.args.get(name,"").strip()
            return None if value in ("","unknown") else int(value)
        def optional_bool(name):
            value=request.args.get(name,"unknown")
            if value not in ("unknown","yes","no"):
                raise ValueError("Expected unknown, yes or no: "+name)
            return None if value=="unknown" else value=="yes"
        try:
            names=sorted(p["name"] for p in ALL_92)
            club=request.args.get("club","Arsenal")
            if club not in names:
                abort(400,description="Unknown scenario club")
            market_value=optional_int("market_value")
            offer_fee=optional_int("offer_fee")
            contract_years=optional_int("contract_years")
            age=optional_int("age")
            squad_role=request.args.get("squad_role","unknown")
            transfer_listed=optional_bool("transfer_listed")
            player_wants_exit=optional_bool("player_wants_exit")
            financial_state=request.args.get("financial_state","unknown")
            replacement=request.args.get("replacement","unknown")
            seller_stance=request.args.get("seller_stance","unknown")
            result=evaluate_selling_club(
                market_value=market_value,offer_fee=offer_fee,
                contract_years=contract_years,age=age,
                squad_role=squad_role,transfer_listed=transfer_listed,
                player_wants_exit=player_wants_exit,financial_state=financial_state,
                replacement=replacement,seller_stance=seller_stance)
        except ValueError as exc:
            abort(400,description=str(exc))
        return render_template_string(
            SELLER_PAGE,version=SELLER_POLICY_VERSION,clubs=names,club=club,
            result=result,age=age,market_value=market_value,offer_fee=offer_fee,
            contract_years=contract_years,squad_role=squad_role,roles=SQUAD_ROLES,
            role_labels=SELLER_ROLE_LABELS,transfer_listed=transfer_listed,
            player_wants_exit=player_wants_exit,financial_state=financial_state,
            replacement=replacement,seller_stance=seller_stance)
    return bp

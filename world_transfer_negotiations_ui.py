"""Read-only three-party negotiation lab using the development world snapshot.

No POST routes and no completed deals. Every player and contract fact is an
explicit fictional scenario input; blank means unknown, never a derived fact.
"""
import sqlite3
from flask import Blueprint, abort, render_template_string, request

from world_v2 import initialize_world
from world_explorer import initialize_catalog, get_dataset
from world_reputation_v2 import initialize_pyramid, MODEL_VERSION as SPORT_MODEL
from world_prestige_full import ALL_92, DATASET_ID, FULL_VERSION, score_club
from world_transfer_negotiations import (
    evaluate_transfer_negotiation, NEGOTIATION_VERSION
)
from world_player_decisions import ROLE_LABELS, SELECTABLE_ROLES, EUROPE_LABELS
from world_selling_club import FINANCIAL_STATES, REPLACEMENT_STATES, SELLER_STANCES
from world_transfer_board import (FINANCIAL_OBJECTIVES, AMBITION_LEVELS,
    OWNERSHIP_PRIORITIES, MANAGER_TRUST_LEVELS)


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Transfer Negotiation Laboratory · Clubs Challenge 2.0</title>
<style>
body{margin:0;background:#111c29;color:#f0f6fc;font:15px system-ui,Arial,sans-serif;line-height:1.5}
header{background:#1b2f43;padding:16px 22px}a{color:#abd8fc}
main{max-width:1160px;margin:22px auto 50px;padding:0 20px}
h1{margin-bottom:5px}h2{margin-top:27px}
small,.muted{color:#bbc9d7}.note{background:#23394c;border-left:3px solid #8eb7d7;padding:12px 15px;margin:15px 0}
fieldset{border:1px solid #40596e;border-radius:8px;margin:14px 0;padding:17px}
legend{font-weight:700;padding:0 9px}
.fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:12px}
label{display:block;font-size:.87rem;color:#c7d7e5;margin-bottom:5px}
input,select,button{background:#29445b;color:white;border:1px solid #698099;border-radius:6px;
padding:10px 11px;width:100%;box-sizing:border-box}
button{background:#315d83;cursor:pointer;max-width:280px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(235px,1fr));gap:13px}
.card{background:#1c3044;border:1px solid #415b73;padding:16px;border-radius:8px}
.big{font-size:1.45rem;font-weight:700}
p{margin:9px 0}
</style></head><body>
<header><a href="/world/play">Career desk</a> ·
<a href="/world/player-decisions">Player laboratory</a> ·
<a href="/world/selling-club">Selling-club laboratory</a></header>
<main>
<h1>Transfer Negotiation & Board Oversight</h1>
<p class="muted">{{version}} · Sporting model {{sport_model}} · Provisional prestige {{prestige_version}}</p>
<div class="note"><b>Development sandbox — fictional inputs only.</b>
This GET-only laboratory doesn't record a bid, sign a player, register a transfer,
change wages, alter squad membership, or spend a transfer budget.
Club sporting ratings and proposed historical prestige are separate values from
the world snapshot. Every other value is a user-selected hypothetical assumption;
missing information stays unknown.</div>
<form method="get">
<fieldset><legend>1. Clubs and player</legend><div class="fields">
<div><label>Buying club</label><select name="buyer">
{% for club in clubs %}<option value="{{club.club_id}}" {% if buyer.club_id==club.club_id %}selected{% endif %}>{{club.name}}</option>{% endfor %}
</select></div>
<div><label>Selling club</label><select name="seller">
{% for club in clubs %}<option value="{{club.club_id}}" {% if seller.club_id==club.club_id %}selected{% endif %}>{{club.name}}</option>{% endfor %}
</select></div>
<div><label>Fictional player age</label><input type="number" name="age" min="17" max="40" value="{{age if age is not none else ''}}" placeholder="Unknown"></div>
<div><label>Fictional overall rating</label><input type="number" name="overall" min="45" max="99" value="{{overall if overall is not none else ''}}" placeholder="Unknown"></div>
<div><label>Current weekly wage (£)</label><input type="number" name="current_wage" min="0" max="1000000" step="500" value="{{current_wage if current_wage is not none else ''}}" placeholder="Unknown"></div>
<div><label>Current squad role</label><select name="current_role">
<option value="unknown">Unknown</option>
{% for r in current_roles %}<option value="{{r}}" {% if current_role==r %}selected{% endif %}>{{role_labels[r]}}</option>{% endfor %}
</select></div>
<div><label>Transfer listed?</label><select name="listed">
<option value="unknown">Unknown</option>
<option value="yes" {% if listed=='yes' %}selected{% endif %}>Yes</option>
<option value="no" {% if listed=='no' %}selected{% endif %}>No</option>
</select></div>
<div><label>Renewal prospects</label><select name="renewal">
<option value="unknown">Unknown</option>
<option value="renewal_offered" {% if renewal=='renewal_offered' %}selected{% endif %}>Renewal offered / expected</option>
<option value="not_offered" {% if renewal=='not_offered' %}selected{% endif %}>No renewal offered</option>
</select></div>
<div><label>Selling club European football</label><select name="seller_europe">
{% for code,label in europe_labels.items() %}<option value="{{code}}" {% if seller_europe==code %}selected{% endif %}>{{label}}</option>{% endfor %}
</select></div>
<div><label>Buying club European football</label><select name="buyer_europe">
{% for code,label in europe_labels.items() %}<option value="{{code}}" {% if buyer_europe==code %}selected{% endif %}>{{label}}</option>{% endfor %}
</select></div>
</div></fieldset>
<fieldset><legend>2. Selling club</legend><div class="fields">
<div><label>Scenario market value (£)</label><input type="number" name="market_value" min="0" max="1000000000" step="50000" value="{{market_value if market_value is not none else ''}}" placeholder="Unknown"></div>
<div><label>Offered transfer fee (£)</label><input type="number" name="offer_fee" min="0" max="1000000000" step="50000" value="{{offer_fee if offer_fee is not none else ''}}" placeholder="No bid yet"></div>
<div><label>Years remaining on current contract</label><select name="contract_years">
<option value="unknown">Unknown</option>
{% for y in range(0,7) %}<option value="{{y}}" {% if contract_years==y %}selected{% endif %}>{{y}}</option>{% endfor %}
</select></div>
<div><label>Player has requested exit?</label><select name="player_wants_exit">
<option value="unknown">Unknown</option>
<option value="yes" {% if player_wants_exit=='yes' %}selected{% endif %}>Yes</option>
<option value="no" {% if player_wants_exit=='no' %}selected{% endif %}>No</option>
</select></div>
<div><label>Financial circumstances</label><select name="financial_state">
<option value="unknown">Unknown</option>
<option value="stable" {% if financial_state=='stable' %}selected{% endif %}>Stable</option>
<option value="cash_needed" {% if financial_state=='cash_needed' %}selected{% endif %}>Needs proceeds</option>
<option value="distressed" {% if financial_state=='distressed' %}selected{% endif %}>Distressed</option>
</select></div>
<div><label>Replacement prospects</label><select name="replacement">
<option value="unknown">Unknown</option>
<option value="available" {% if replacement=='available' %}selected{% endif %}>Replacement available</option>
<option value="difficult" {% if replacement=='difficult' %}selected{% endif %}>Difficult</option>
</select></div>
<div><label>Selling club stance</label><select name="seller_stance">
<option value="unknown">Unknown</option>
<option value="retain" {% if seller_stance=='retain' %}selected{% endif %}>Wants to retain</option>
<option value="neutral" {% if seller_stance=='neutral' %}selected{% endif %}>Considers offers</option>
<option value="sell" {% if seller_stance=='sell' %}selected{% endif %}>Wants to sell</option>
</select></div>
</div></fieldset>
<fieldset><legend>3. Agent and proposed personal terms</legend><div class="fields">
<div><label>Promised squad role</label><select name="role">
{% for r in proposed_roles %}<option value="{{r}}" {% if role==r %}selected{% endif %}>{{role_labels[r]}}</option>{% endfor %}
</select></div>
<div><label>Offered weekly wage (£)</label><input type="number" name="offered_wage" min="0" max="1000000" step="500" value="{{offered_wage if offered_wage is not none else ''}}" placeholder="Not offered"></div>
<div><label>Proposed contract term (years)</label><select name="proposed_years">
<option value="unknown">Unknown</option>
{% for y in range(1,6) %}<option value="{{y}}" {% if proposed_years==y %}selected{% endif %}>{{y}}</option>{% endfor %}
</select></div>
</div></fieldset>
<fieldset><legend>4. Buying club affordability</legend>
<p class="muted">Enter the remaining, uncommitted scenario funds. Unknown inputs remain unknown. Zero must be entered explicitly.</p>
<div class="fields">
<div><label>Remaining transfer budget (£)</label><input type="number" name="transfer_budget" min="0" step="50000" value="{{transfer_budget if transfer_budget is not none else ''}}" placeholder="Unknown"></div>
<div><label>Weekly wage headroom (£/week)</label><input type="number" name="wage_headroom" min="0" step="500" value="{{wage_headroom if wage_headroom is not none else ''}}" placeholder="Unknown"></div>
<div><label>Signing-on fee (£)</label><input type="number" name="signing_on_fee" min="0" step="10000" value="{{signing_on_fee if signing_on_fee is not none else ''}}" placeholder="Unknown (enter 0 if none)"></div>
<div><label>Agent fee (£)</label><input type="number" name="agent_fee" min="0" step="10000" value="{{agent_fee if agent_fee is not none else ''}}" placeholder="Unknown (enter 0 if none)"></div>
<div><label>Other upfront fees (£)</label><input type="number" name="other_upfront_fees" min="0" step="10000" value="{{other_upfront_fees if other_upfront_fees is not none else ''}}" placeholder="Unknown (enter 0 if none)"></div>
</div></fieldset>
<fieldset><legend>5. Board oversight — exceptional sales and buying vetoes</legend>
<p class="muted">These are explicit fictional board policies, not information about real clubs.
Enable a board decision and enter its thresholds; otherwise the board does not intervene.</p>
<div class="fields">
<div><label>Selling board exceptional-sale rule</label><select name="seller_board_enabled">
<option value="no" {% if seller_board_enabled=='no' %}selected{% endif %}>Off</option>
<option value="yes" {% if seller_board_enabled=='yes' %}selected{% endif %}>On — board can direct sale</option></select></div>
<div><label>Selling board minimum offer (% of scenario market value)</label>
<input type="number" name="seller_board_pct" min="0" max="1000" step="5" value="{{seller_board_pct if seller_board_pct is not none else ''}}" placeholder="Unknown — e.g. 200"></div>
<div><label>Buying board value-for-money rule</label><select name="buyer_board_enabled">
<option value="no" {% if buyer_board_enabled=='no' %}selected{% endif %}>Off</option>
<option value="yes" {% if buyer_board_enabled=='yes' %}selected{% endif %}>On — board can veto</option></select></div>
<div><label>Buying board maximum fee (% of scenario market value)</label>
<input type="number" name="buyer_board_fee_pct" min="0" max="1000" step="5" value="{{buyer_board_fee_pct if buyer_board_fee_pct is not none else ''}}" placeholder="Unknown — e.g. 150"></div>
<div><label>Buying board maximum weekly wage allocation (% of headroom)</label>
<input type="number" name="buyer_board_wage_pct" min="0" max="1000" step="5" value="{{buyer_board_wage_pct if buyer_board_wage_pct is not none else ''}}" placeholder="Unknown — e.g. 60"></div>
</div>
<p class="muted">Optional board culture: choose all four factors for each enabled board. Blank/unknown factors block a culture-based board ruling rather than inventing a personality. Leaving culture modelling off preserves the manual board thresholds.</p>
<div class="fields">
<div><label>Selling board culture</label><select name="seller_context_on"><option value="no" {% if seller_context_on=='no' %}selected{% endif %}>Not modelled</option><option value="yes" {% if seller_context_on=='yes' %}selected{% endif %}>Use explicit board context</option></select></div>
<div><label>Selling board financial objective</label><select name="seller_financial"><option value="unknown">Unknown</option>{% for code in financial_options %}<option value="{{code}}" {% if seller_financial==code %}selected{% endif %}>{{code|replace('_',' ')|title}}</option>{% endfor %}</select></div>
<div><label>Selling club ambition</label><select name="seller_ambition"><option value="unknown">Unknown</option>{% for code in ambition_options %}<option value="{{code}}" {% if seller_ambition==code %}selected{% endif %}>{{code|title}}</option>{% endfor %}</select></div>
<div><label>Selling ownership priority</label><select name="seller_ownership"><option value="unknown">Unknown</option>{% for code in ownership_options %}<option value="{{code}}" {% if seller_ownership==code %}selected{% endif %}>{{code|replace('_',' ')|title}}</option>{% endfor %}</select></div>
<div><label>Selling board confidence in manager</label><select name="seller_trust"><option value="unknown">Unknown</option>{% for code in trust_options %}<option value="{{code}}" {% if seller_trust==code %}selected{% endif %}>{{code|title}}</option>{% endfor %}</select></div>
<div><label>Buying board culture</label><select name="buyer_context_on"><option value="no" {% if buyer_context_on=='no' %}selected{% endif %}>Not modelled</option><option value="yes" {% if buyer_context_on=='yes' %}selected{% endif %}>Use explicit board context</option></select></div>
<div><label>Buying board financial objective</label><select name="buyer_financial"><option value="unknown">Unknown</option>{% for code in financial_options %}<option value="{{code}}" {% if buyer_financial==code %}selected{% endif %}>{{code|replace('_',' ')|title}}</option>{% endfor %}</select></div>
<div><label>Buying club ambition</label><select name="buyer_ambition"><option value="unknown">Unknown</option>{% for code in ambition_options %}<option value="{{code}}" {% if buyer_ambition==code %}selected{% endif %}>{{code|title}}</option>{% endfor %}</select></div>
<div><label>Buying ownership priority</label><select name="buyer_ownership"><option value="unknown">Unknown</option>{% for code in ownership_options %}<option value="{{code}}" {% if buyer_ownership==code %}selected{% endif %}>{{code|replace('_',' ')|title}}</option>{% endfor %}</select></div>
<div><label>Buying board confidence in manager</label><select name="buyer_trust"><option value="unknown">Unknown</option>{% for code in trust_options %}<option value="{{code}}" {% if buyer_trust==code %}selected{% endif %}>{{code|title}}</option>{% endfor %}</select></div>
</div></fieldset>
<button type="submit">Evaluate transfer</button>
</form>
<h2>Simulation outcome</h2>
<div class="card"><div class="muted">{{seller.name}} → {{buyer.name}}</div>
<div class="big">{{result.outcome|replace('_',' ')|title}}</div>
<p>{{result.next_step}}</p></div>
<h2>Independent decisions</h2><div class="grid">
<div class="card"><b>Player</b>
<div class="big">{{result.player.decision|replace('_',' ')|title}}</div>
<p>{{result.player.reason}}</p>
<p class="muted">Sporting gap: {{result.player.sporting_gap if result.player.sporting_gap is defined else 'Unknown'}} ·
Historical prestige gap: {{result.player.prestige_gap if result.player.prestige_gap is defined else 'Unknown'}}</p>
<p class="muted">Minimum squad role: {{role_labels.get(result.player.required_role, result.player.required_role)}}</p>
</div>
<div class="card"><b>Selling club</b>
<div class="big">{{result.selling_club.decision|capitalize}}</div>
<p>{{result.selling_club.reason}}</p>
<p class="muted">Scenario asking price:
{% if result.selling_club.asking_price is not none %}£{{'{:,}'.format(result.selling_club.asking_price)}}{% else %}Not determined{% endif %}</p>
{% if result.selling_club.fee_shortfall is not none %}
<p class="muted">Fee shortfall: £{{'{:,}'.format(result.selling_club.fee_shortfall)}}</p>{% endif %}
</div>
<div class="card"><b>Buying club finances</b>
<div class="big">{{result.buyer_affordability.decision|capitalize}}</div>
<p>{{result.buyer_affordability.reason}}</p>
<p class="muted">Upfront transfer commitment:
{% if result.buyer_affordability.total_upfront_commitment is not none %}£{{'{:,}'.format(result.buyer_affordability.total_upfront_commitment)}}{% else %}Unknown{% endif %}</p>
<p class="muted">Remaining transfer budget:
{% if result.buyer_affordability.remaining_transfer_budget is not none %}£{{'{:,}'.format(result.buyer_affordability.remaining_transfer_budget)}}{% else %}Unknown{% endif %}</p>
<p class="muted">Remaining weekly wage headroom:
{% if result.buyer_affordability.remaining_weekly_wage_headroom is not none %}£{{'{:,}'.format(result.buyer_affordability.remaining_weekly_wage_headroom)}}{% else %}Unknown{% endif %}</p>
<p class="muted">Total contract salary commitment (52 weeks/year):
{% if result.buyer_affordability.total_contract_wages is not none %}£{{'{:,}'.format(result.buyer_affordability.total_contract_wages)}}{% else %}Unknown{% endif %}</p>
{% if result.buyer_affordability.transfer_shortfall %}<p>Transfer funds shortfall: £{{'{:,}'.format(result.buyer_affordability.transfer_shortfall)}}</p>{% endif %}
{% if result.buyer_affordability.weekly_wage_shortfall %}<p>Weekly wage shortfall: £{{'{:,}'.format(result.buyer_affordability.weekly_wage_shortfall)}}</p>{% endif %}
</div>
<div class="card"><b>Agent</b>
<div class="big">{{result.agent.status|replace('_',' ')|title}}</div>
<p>{{result.agent.reason}}</p>
<p class="muted">Simulated minimum weekly pay:
{% if result.agent.minimum_weekly_wage is not none %}£{{'{:,}'.format(result.agent.minimum_weekly_wage)}}{% else %}Undetermined{% endif %}</p>
{% if result.agent.wage_shortfall is not none %}
<p class="muted">Weekly pay shortfall: £{{'{:,}'.format(result.agent.wage_shortfall)}}</p>{% endif %}
{% if result.agent.contract_warning %}<p class="muted">{{result.agent.contract_warning}}</p>{% endif %}
</div></div>
<h2>Board decisions</h2><div class="grid">
<div class="card"><b>Selling club board</b>
<div class="big">{{result.selling_board.decision|replace('_',' ')|title}}</div>
<p>{{result.selling_board.reason}}</p>
{% if result.selling_board.required_offer is not none %}
<p class="muted">Exceptional-offer threshold: £{{'{:,}'.format(result.selling_board.required_offer)}}</p>{% endif %}
<p class="muted">Board threshold adjustment: {{result.selling_board.threshold_adjustment_pct if result.selling_board.threshold_adjustment_pct is not none else "Unassessed"}} percentage points</p>
<p class="muted">Manager/seller decision: {{result.selling_club.decision|capitalize}}
· Effective selling-club decision: {{result.effective_selling_club.decision|capitalize}}</p>
</div>
<div class="card"><b>Buying club board</b>
<div class="big">{{result.buying_board.decision|replace('_',' ')|title}}</div>
<p>{{result.buying_board.reason}}</p><p class="muted">Board threshold adjustment: {{result.buying_board.threshold_adjustment_pct if result.buying_board.threshold_adjustment_pct is not none else "Unassessed"}} percentage points</p>
{% if result.buying_board.maximum_fee is not none %}
<p class="muted">Maximum approved fee: £{{'{:,}'.format(result.buying_board.maximum_fee)}}</p>{% endif %}
{% if result.buying_board.maximum_weekly_wage is not none %}
<p class="muted">Maximum weekly wage allocation: £{{'{:,}'.format(result.buying_board.maximum_weekly_wage)}}</p>{% endif %}
</div></div>
<div class="note">Even a <b>Provisional Agreement</b> is NOT a completed transfer:
the simulation does not verify legal registration, real club budgets, an actual
player's wishes, transfer-window eligibility, or a real accepted contract.</div>
</main></body></html>"""


def create_transfer_negotiations_blueprint(db_path):
    bp = Blueprint("world_transfer_negotiations", __name__)

    @bp.get("/world/transfer-negotiations")
    def lab():
        def optional_int(key):
            value = request.args.get(key, "").strip()
            return None if value in ("", "unknown") else int(value)

        def optional_bool(key):
            value = request.args.get(key, "unknown")
            if value not in ("yes", "no", "unknown"):
                raise ValueError(key + " must be yes, no or unknown")
            return None if value == "unknown" else value == "yes"

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            initialize_world(conn)
            initialize_catalog(conn)
            initialize_pyramid(conn)
            get_dataset(conn, DATASET_ID)
            rows = conn.execute(
                """SELECT c.club_id, c.name, comp.tier, r.sporting_appeal
                   FROM world_dataset_entries e
                   JOIN world_clubs c ON c.club_id=e.club_id
                   JOIN world_competitions comp ON comp.competition_id=e.competition_id
                   LEFT JOIN world_pyramid_club_appeal r
                     ON r.club_id=e.club_id AND r.dataset_id=e.dataset_id
                      AND r.model_version=?
                   WHERE e.dataset_id=? ORDER BY c.name""",
                (SPORT_MODEL, DATASET_ID),
            ).fetchall()
        finally:
            conn.close()

        prestige = {p["name"]: score_club(p)["score"] for p in ALL_92}
        clubs = [dict(club_id=x["club_id"], name=x["name"], tier=x["tier"],
                      sporting=x["sporting_appeal"], prestige=prestige.get(x["name"]))
                 for x in rows]
        by_id = {str(c["club_id"]):c for c in clubs}
        by_name = {c["name"]:c for c in clubs}
        buyer = by_id.get(request.args.get("buyer", ""),by_name.get("Nottingham Forest"))
        seller = by_id.get(request.args.get("seller", ""),by_name.get("Arsenal"))
        if buyer is None or seller is None:
            abort(503,description="World snapshot unavailable")
        if buyer["club_id"] == seller["club_id"]:
            abort(400,description="Buying and selling clubs must differ")
        try:
            age = optional_int("age")
            overall = optional_int("overall")
            current_wage = optional_int("current_wage")
            offered_wage = optional_int("offered_wage")
            market_value = optional_int("market_value")
            offer_fee = optional_int("offer_fee")
            contract_years = optional_int("contract_years")
            proposed_years = optional_int("proposed_years")
            transfer_budget = optional_int("transfer_budget")
            wage_headroom = optional_int("wage_headroom")
            signing_on_fee = optional_int("signing_on_fee")
            agent_fee = optional_int("agent_fee")
            other_upfront_fees = optional_int("other_upfront_fees")
            seller_board_pct = optional_int("seller_board_pct")
            buyer_board_fee_pct = optional_int("buyer_board_fee_pct")
            buyer_board_wage_pct = optional_int("buyer_board_wage_pct")
            seller_board_enabled = request.args.get("seller_board_enabled","no")
            buyer_board_enabled = request.args.get("buyer_board_enabled","no")
            if seller_board_enabled not in ("yes","no") or buyer_board_enabled not in ("yes","no"):
                raise ValueError("Board options must be yes or no")
            seller_context_on = request.args.get("seller_context_on","no")
            buyer_context_on = request.args.get("buyer_context_on","no")
            if seller_context_on not in ("yes","no") or buyer_context_on not in ("yes","no"):
                raise ValueError("Culture toggles must be yes or no")
            seller_financial = request.args.get("seller_financial","unknown")
            seller_ambition = request.args.get("seller_ambition","unknown")
            seller_ownership = request.args.get("seller_ownership","unknown")
            seller_trust = request.args.get("seller_trust","unknown")
            buyer_financial = request.args.get("buyer_financial","unknown")
            buyer_ambition = request.args.get("buyer_ambition","unknown")
            buyer_ownership = request.args.get("buyer_ownership","unknown")
            buyer_trust = request.args.get("buyer_trust","unknown")
            selling_context = dict(financial_objective=seller_financial,
                ambition=seller_ambition,ownership_priority=seller_ownership,
                manager_trust=seller_trust) if seller_context_on=="yes" else None
            buying_context = dict(financial_objective=buyer_financial,
                ambition=buyer_ambition,ownership_priority=buyer_ownership,
                manager_trust=buyer_trust) if buyer_context_on=="yes" else None
            role = request.args.get("role","unspecified")
            current_role = request.args.get("current_role","unknown")
            listed = request.args.get("listed","unknown")
            renewal = request.args.get("renewal","unknown")
            buyer_europe = request.args.get("buyer_europe","unknown")
            seller_europe = request.args.get("seller_europe","unknown")
            player_wants_exit = request.args.get("player_wants_exit","unknown")
            financial_state = request.args.get("financial_state","unknown")
            replacement = request.args.get("replacement","unknown")
            seller_stance = request.args.get("seller_stance","unknown")
            result = evaluate_transfer_negotiation(
                player=dict(
                    buyer_tier=buyer["tier"],seller_tier=seller["tier"],
                    buyer_score=buyer["sporting"],seller_score=seller["sporting"],
                    buyer_prestige=buyer["prestige"],seller_prestige=seller["prestige"],
                    overall=overall,age=age,
                    current_wage=current_wage,current_role=current_role,
                    transfer_listed=optional_bool("listed"),
                    renewal_status=renewal,offered_wage=offered_wage,
                    role_promise=role,buyer_europe=buyer_europe,
                    seller_europe=seller_europe,
                ),
                seller=dict(market_value=market_value,offer_fee=offer_fee,
                    contract_years=contract_years,squad_role=current_role,
                    transfer_listed=optional_bool("listed"),
                    player_wants_exit=optional_bool("player_wants_exit"),
                    financial_state=financial_state,replacement=replacement,
                    seller_stance=seller_stance,age=age),
                proposed_contract_years=proposed_years,
                buyer_finances=dict(transfer_budget=transfer_budget,
                    wage_headroom=wage_headroom,signing_on_fee=signing_on_fee,
                    agent_fee=agent_fee,other_upfront_fees=other_upfront_fees),
                seller_board=dict(intervene=seller_board_enabled=="yes",
                    approval_multiple_pct=seller_board_pct,
                    context=selling_context),
                buyer_board=dict(intervene=buyer_board_enabled=="yes",
                    max_fee_pct=buyer_board_fee_pct,
                    max_headroom_use_pct=buyer_board_wage_pct,
                    context=buying_context),
            )
        except (ValueError, TypeError) as exc:
            abort(400,description=str(exc))
        return render_template_string(
            PAGE,version=NEGOTIATION_VERSION,sport_model=SPORT_MODEL,
            prestige_version=FULL_VERSION,
            clubs=clubs,buyer=buyer,seller=seller,result=result,
            age=age,overall=overall,current_wage=current_wage,
            offered_wage=offered_wage,market_value=market_value,
            offer_fee=offer_fee,contract_years=contract_years,
            proposed_years=proposed_years,role=role,
            transfer_budget=transfer_budget,wage_headroom=wage_headroom,
            signing_on_fee=signing_on_fee,agent_fee=agent_fee,
            other_upfront_fees=other_upfront_fees,
            seller_board_enabled=seller_board_enabled,
            buyer_board_enabled=buyer_board_enabled,
            seller_board_pct=seller_board_pct,
            buyer_board_fee_pct=buyer_board_fee_pct,
            buyer_board_wage_pct=buyer_board_wage_pct,
            seller_context_on=seller_context_on,buyer_context_on=buyer_context_on,
            seller_financial=seller_financial,seller_ambition=seller_ambition,
            seller_ownership=seller_ownership,seller_trust=seller_trust,
            buyer_financial=buyer_financial,buyer_ambition=buyer_ambition,
            buyer_ownership=buyer_ownership,buyer_trust=buyer_trust,
            financial_options=FINANCIAL_OBJECTIVES[1:],
            ambition_options=AMBITION_LEVELS[1:],
            ownership_options=OWNERSHIP_PRIORITIES[1:],
            trust_options=MANAGER_TRUST_LEVELS[1:],
            current_role=current_role,listed=listed,renewal=renewal,
            buyer_europe=buyer_europe,seller_europe=seller_europe,
            player_wants_exit=player_wants_exit,financial_state=financial_state,
            replacement=replacement,seller_stance=seller_stance,
            current_roles=tuple(r for r in SELECTABLE_ROLES if r!="unspecified"),
            proposed_roles=SELECTABLE_ROLES,
            role_labels=ROLE_LABELS,europe_labels=EUROPE_LABELS,
        )
    return bp

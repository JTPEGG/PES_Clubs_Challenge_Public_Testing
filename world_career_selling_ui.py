"""Authenticated career selling-club settings screen (template only).

Authentication and CSRF write checks live in the existing career desk blueprint.
"""
SELLING_CAREER_PAGE = """<!doctype html><html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Selling Clubs &amp; Board Decisions · PES Challenge</title>
<style>
body{background:#111a25;color:#edf5ff;font:15px system-ui,sans-serif;line-height:1.5;margin:0}
header{padding:15px 24px;background:#1e3044}a{color:#a8d1fc}
main{max-width:1020px;margin:25px auto;padding:0 20px 70px}
section{padding:16px;background:#1c3145;border:1px solid #405a73;border-radius:8px;margin:18px 0}
h1{margin-bottom:5px}h2{margin-top:25px}.muted{color:#c1d0df}
.fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:14px}
label{display:block;color:#d0dfea;margin:7px 0 5px}
input,select,button{box-sizing:border-box;width:100%;padding:10px;border:1px solid #647b91;
background:#2a4760;color:white;border-radius:6px}
button{cursor:pointer;background:#315d83}
strong{color:#f4f8fd}small{color:#bdcddd}
details{padding:8px;background:#223c54;border-radius:6px}
</style></head><body><header>
<a href="/world/play/career/{{career_id}}">← Back to Career Desk</a> ·
<a href="/world/play/career/{{career_id}}/management">Club management</a>
</header>
<main><h1>Selling Clubs &amp; Board Intervention</h1>
<p class="muted">{{career_name}} · {{career_id}}</p>
{% if error %}<section><strong>Could not save settings:</strong> {{error}}</section>{% endif %}
<section>
<b>Development career only.</b> All market values, contract circumstances, selling intentions
and board preferences below are explicit fictional assumptions unless independently sourced.
The player's permission and agent terms are separate. No screen here moves a player,
accepts a real contract or changes PES registration.
</section>
<section><h2>Selling engine</h2>
{% if enabled %}
<p><strong>Active for new offers.</strong> The engine uses the saved circumstances for each target.
Missing facts pause the negotiation for review, rather than automatically making a player available.</p>
{% else %}
<p><strong>Legacy seller decisions still in force.</strong> Opt in to the enhanced selling-club
engine for new bids. Earlier offers and their terms remain unchanged.</p>
<form method="post" action="/world/play/career/{{career_id}}/selling/enable">
<input type="hidden" name="csrf" value="{{csrf}}">
<label>Activation note</label>
<input name="source_note" required maxlength="300" placeholder="Enable fictional selling-club decision rules for new offers">
<p><button type="submit">Enable enhanced selling-club decisions</button></p>
</form>
{% endif %}</section>
<section><h2>Choose a player</h2>
<form method="get" action="/world/play/career/{{career_id}}/selling">
<label>Current squad or prospective signing</label>
<select name="player_id" required>
{% for player in players %}
<option value="{{player.player_id}}" {% if player.player_id==selected_id %}selected{% endif %}>
{{player.full_name}} — {{player.club_name}} ({{player.player_id}})
</option>{% endfor %}
</select>
<p><button type="submit">View seller circumstances</button></p>
</form>
{% if player %}
<p><strong>{{player.full_name}}</strong> · Current seller: {{player.club_name}}.
{% if player.club_id==manager_club_id %}<strong>Your own club</strong> — your board's
confidence score will determine its willingness to overrule you.{% endif %}</p>
{% endif %}
</section>
{% if player %}
<section><h2>Seller circumstances — {{player.full_name}}</h2>
{% if existing %}
<p><strong>Scenario locked.</strong> Values cannot silently change once recorded.
This makes decisions reproducible and protects outstanding offer histories.</p>
<div class="fields">
<p>Market value: {% if existing.market_value is not none %}£{{'{:,}'.format(existing.market_value)}}{% else %}Unknown{% endif %}</p>
<p>Contract years: {{existing.contract_years if existing.contract_years is not none else 'Unknown'}}</p>
<p>Current role: {{existing.squad_role|replace('_',' ')|title}}</p>
<p>Transfer listed: {{'Unknown' if existing.transfer_listed is none else ('Yes' if existing.transfer_listed else 'No')}}</p>
<p>Player wants exit: {{'Unknown' if existing.player_wants_exit is none else ('Yes' if existing.player_wants_exit else 'No')}}</p>
<p>Finances: {{existing.financial_state|replace('_',' ')|title}}</p>
<p>Replacement: {{existing.replacement|replace('_',' ')|title}}</p>
<p>Manager's seller stance: {{existing.seller_stance|title}}</p>
<p>Board intervention: {{'Enabled' if existing.board_enabled else 'Disabled'}}</p>
<p>Exceptional-offer threshold: {{existing.exceptional_offer_pct if existing.exceptional_offer_pct is not none else 'Unknown'}}%</p>
<p>Source note: {{existing.source_note}}</p>
</div>
{% else %}
<form method="post" action="/world/play/career/{{career_id}}/selling/circumstances">
<input type="hidden" name="csrf" value="{{csrf}}">
<input type="hidden" name="player_id" value="{{player.player_id}}">
<div class="fields">
<div><label>Fictional market valuation (£)</label>
<input type="number" id="market_value" name="market_value" min="0" max="1000000000" step="1" inputmode="numeric"
 value="{{model_valuation if model_valuation is not none else ''}}"
 placeholder="Unknown" aria-describedby="market_value_help">
<small id="market_value_help">Any whole-pound amount is valid; the calculated valuation is not necessarily a multiple of £50,000.</small>
<small>Pre-filled from the game's source-rated valuation model, where available.
It is not a confirmed real-world transfer valuation; you may revise it.</small></div>
<div><label>Contract years remaining</label><select name="contract_years">
<option value="unknown">Unknown</option>{% for years in range(7) %}
<option value="{{years}}">{{years}}</option>{% endfor %}</select></div>
<div><label>Current squad role</label><select name="squad_role">
<option value="unknown">Unknown</option>
{% for role in roles %}<option value="{{role}}">{{role|replace('_',' ')|title}}</option>{% endfor %}
</select></div>
<div><label>Transfer-listed?</label><select name="transfer_listed">
<option value="unknown">Unknown</option><option value="yes">Yes</option><option value="no">No</option></select></div>
<div><label>Player has asked to leave?</label><select name="player_wants_exit">
<option value="unknown">Unknown</option><option value="yes">Yes</option><option value="no">No</option></select></div>
<div><label>Seller financial position</label><select name="financial_state">
{% for code in financial_options %}<option value="{{code}}">{{code|replace('_',' ')|title}}</option>{% endfor %}</select></div>
<div><label>Replacement difficulty</label><select name="replacement">
{% for code in replacement_options %}<option value="{{code}}">{{code|replace('_',' ')|title}}</option>{% endfor %}</select></div>
<div><label>Selling manager preference</label><select name="seller_stance">
{% for code in seller_stances %}<option value="{{code}}">{{code|title}}</option>{% endfor %}</select></div>
<div><label>Exceptional-offer board override</label><select name="board_enabled">
<option value="no">Disabled</option><option value="yes">Enabled</option></select></div>
<div><label>Board exceptional offer threshold (% of valuation)</label>
<input type="number" name="exceptional_offer_pct" min="0" max="1000" step="1" inputmode="numeric"
placeholder="Unknown — e.g. 200"></div>
<div><label>Board financial objective</label><select name="financial_objective">
{% for code in board_financial_options %}<option value="{{code}}">{{code|replace('_',' ')|title}}</option>{% endfor %}</select></div>
<div><label>Club ambition</label><select name="ambition">
{% for code in ambition_options %}<option value="{{code}}">{{code|title}}</option>{% endfor %}</select></div>
<div><label>Ownership priority</label><select name="ownership_priority">
{% for code in ownership_options %}<option value="{{code}}">{{code|replace('_',' ')|title}}</option>{% endfor %}</select></div>
<div><label>Seller manager trust (AI clubs only)</label><select name="assumed_manager_trust">
{% for code in trust_options %}<option value="{{code}}">{{code|title}}</option>{% endfor %}</select>
<small>Your own club uses saved board confidence automatically.</small></div>
<div><label>Evidence / fictional scenario note</label>
<input name="source_note" maxlength="350" required placeholder="Record the source of these assumptions"></div>
</div><p><button type="submit">Lock seller circumstances</button></p>
</form>
{% endif %}
</section>
{% if enabled and existing %}
<section><h2>Preview a buying club's bid</h2>
<p>Fee approval is independent of whether the player will agree to leave.</p>
<form method="get" action="/world/play/career/{{career_id}}/selling">
<input name="player_id" type="hidden" value="{{player.player_id}}">
<label>Offer (£)</label><input type="number" name="offer_fee" min="0" max="1000000000"
step="1" inputmode="numeric" value="{{offer_fee if offer_fee is not none else ''}}" required>
<p><button type="submit">Check seller and board response</button></p>
</form>
{% if preview %}
<p><strong>Seller decision:</strong> {{preview.decision|replace('_',' ')|title}}</p>
<p><strong>Board:</strong> {{preview.board_decision|replace('_',' ')|title}}</p>
<p>{{preview.reason}}</p>
{% if preview.asking_price is defined and preview.asking_price is not none %}
<p>Scenario asking price: £{{'{:,}'.format(preview.asking_price)}}</p>{% endif %}
{% if preview.board_decision=='direct_sale' %}
<p><strong>Board directs a fee agreement against the selling manager's preference.
No player contract or registration changes.</strong></p>{% endif %}
{% endif %}</section>
{% endif %}
{% endif %}
</main></body></html>"""

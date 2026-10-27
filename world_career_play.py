"""Password-gated PLAYABLE development career negotiation interface.

The access passphrase is supplied through a Render environment variable, never
stored in source. Signed browser cookie and per-form CSRF token protect writes.
No endpoint completes an actual PES registration or alters production saves.
"""
import hmac
import json
import os
import secrets
import sqlite3
from datetime import date
from functools import wraps
from flask import Blueprint, abort, make_response, redirect, render_template_string, request, url_for
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from world_explorer import initialize_catalog
from world_market import initialize_market
from world_careers import (
    initialize_career_engine, start_sandbox, propose_offer, review_pending_seller_offer, _player_reference, accept_counter,
    settle_future_deal, withdraw_offer, reject_incoming_offer, budget_remaining, ai_interest, simulate_ai_bids, negotiate_agent, agent_terms, wage_budget_breakdown, confirm_future_agreement, player_move_interest,
    career_player_policy,player_circumstances,set_player_circumstances,
    offer_europe_context
)
from world_valuation import display_gbp
from world_career_board_policy import (initialize_career_board_policy,
    configure_policy,get_policy,career_board_decision)
from world_career_selling import (initialize_career_selling,selling_enabled,
    enable_career_selling,get_seller_assumptions,record_seller_assumptions,
    evaluate_career_seller_bid,offer_decision)
from world_selling_club import SQUAD_ROLES,FINANCIAL_STATES,REPLACEMENT_STATES,SELLER_STANCES
from world_transfer_board import (FINANCIAL_OBJECTIVES,AMBITION_LEVELS,
    OWNERSHIP_PRIORITIES,MANAGER_TRUST_LEVELS)
from world_career_selling_ui import SELLING_CAREER_PAGE
from world_career_incoming import (
    initialize_incoming_approaches,incoming_approach,advance_incoming_approach,
    finalise_incoming_approach,
)
from world_career_transfer_protocol import (
    initialize_transfer_protocol,transfer_protocol_enabled,
    enable_transfer_protocol,stage_description,offer_uses_five_stages,
)
from world_board_objectives import objective_band
from world_career_strength import strength_baseline
from world_career_resources import resource_capacity,expectation_with_resources
from world_career_objectives import (initialize_board_objectives,lock_objective,
    lock_auto_strength_objective,review_season,objective_history)
from world_career_management import (
 initialize_career_management,career_management_snapshot,
 set_initial_confidence,record_board_event,record_contract,
 EVENTS as BOARD_EVENTS,ROLES as CONTRACT_ROLES
)
from world_player_decisions import ROLE_LABELS
from world_player_decisions import DECISION_VERSION,DECISION_V2_VERSION,LEGACY_VERSION
from world_preseason_window import window_snapshot
from world_live_market import (
    initialise_live_market,start_live_market,process_live_market,
    spectator_token,manager_respond,market_messages,mark_market_read,
)
from world_scouting import scouting_search,scouting_attributes,CATEGORIES,SORT_COLUMNS,set_shortlisted,player_profile,recruitment_recommendations
from world_live_buying import (
    submit_buy_offer,act_on_buy_offer,manager_targets,
)
from world_squad_desk import squad_preview,update_squad_player
from world_season_setup import checklist as season_checklist,change_step as season_change_step

HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{title}} | Career Transfer Desk</title>
<style>body{background:#111a25;color:#eef5fb;font:15px system-ui;margin:0}
header{padding:16px 24px;background:#203043}main{max-width:1040px;margin:25px auto;padding:0 20px 75px}
a{color:#a8d1fc}.muted{color:#adbfce}.warn{background:#293d50;border-left:3px solid #8fc5f5;padding:13px;margin:16px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(225px,1fr));gap:12px}
.card{padding:17px;background:#1d2e40;border:1px solid #415a70;border-radius:9px}
table{border-collapse:collapse;width:100%;margin:20px 0}td,th{padding:11px;text-align:left;border-bottom:1px solid #394d60}
input,select,button{font:inherit;padding:8px 10px;background:#273c50;color:white;border:1px solid #5b748b;border-radius:6px}
button{cursor:pointer;background:#285b83}button:disabled{opacity:.5}label{display:block;margin:10px 0 3px}
form{margin:12px 0}.inline{display:inline}.danger{background:#613940}
</style></head><body>
<header><a href="/world/explore">Football World</a> · <a href="/world/market">Market preview</a> · <a href="/world/careers">Career history</a> · <a href="/world/reputations">Reputation audit</a> · <a href="/world/reputations/progression">Season preview</a></header>
<main><h1>{{title}}</h1>
<div class="warn"><b>Development sandbox only.</b> These are fictional finance assumptions and source-snapshot squads.
All deals are subject to the PES league summer registration lock. This screen cannot update the original challenge.
{% if career %} Economy model: {{career['economy_version']}}. {% endif %}</div>
{% if error %}<div class="warn" role="alert">{{error}}</div>{% endif %}
{% if not authenticated %}
<form method="post" action="/world/play/login"><label for="password">Development access passphrase</label>
<input type="password" id="password" name="password" required autofocus><button type="submit">Unlock career desk</button></form>
{% elif mode == 'index' %}
{% if access_required %}<form method="post" action="/world/play/logout"><input type="hidden" name="csrf" value="{{csrf}}"><button>Sign out</button></form>{% endif %}
{% if careers %}<h2>Your available development sandboxes</h2><div class="grid">
{% for c in careers %}<div class="card"><b>{{c['title']}}</b><p class="muted">{{c['economy_version']}} · {{c['dataset_id']}}</p>
<a href="/world/play/career/{{c['career_id']}}/market">Open manager's inbox →</a></div>{% endfor %}</div>{% endif %}
<h2>Create new development career</h2>
<p class="muted">Enhanced selling-club decisions are <b>enabled by default</b> for new careers. Unknown player contracts and selling-club circumstances must still be recorded before bids can progress.</p>
<form method="get" action="/world/play">
<label for="browse_dataset">Select starting dataset</label><select name="dataset" id="browse_dataset">{% for d in datasets %}
<option value="{{d['dataset_id']}}" {% if d['dataset_id']==selected_dataset %}selected{% endif %}>{{d['title']}}</option>{% endfor %}</select>
<button>Choose dataset</button></form>
<form method="post" action="/world/play/create">
<input type="hidden" name="csrf" value="{{csrf}}">
<label>Career identifier</label><input name="career_id" required placeholder="my-test-career" pattern="[A-Za-z0-9_-]+">
<label>Career name</label><input name="title" maxlength="80" required placeholder="2026/27 career sandbox">
<input type="hidden" name="dataset_id" value="{{selected_dataset}}"><p class="muted">Starting snapshot: {{selected_dataset}}</p>
<label>Manager's club</label><select name="manager_club_id">{% for c in clubs %}<option value="{{c['club_id']}}">{{c['name']|club_display}}</option>{% endfor %}</select>
<p class="muted">The club list belongs to your selected dataset. Historical teams only appear after an independent historical season has been imported.</p>
<label>Player and agent decision model</label>
<select name="player_decision_version">
<option value="player-decisions-v2" {% if selected_dataset=='england-2026-27-fc27' %}selected{% endif %} {% if selected_dataset!='england-2026-27-fc27' %}disabled{% endif %}>Player decisions v2 — current wages, squad role, transfer listing, contract status and club appeal</option>
<option value="player-decisions-v1">Player decisions v1 (old model — for comparison)</option>
<option value="legacy-sporting-v2" {% if selected_dataset!='england-2026-27-fc27' %}selected{% endif %}>Legacy sporting-appeal only</option>
</select>
<p class="muted">The new model freezes the <b>provisional 92-club historical prestige draft</b> in this new career.
It is a gameplay calibration, not a verified real-world player preference. Existing careers keep their original model;
later global prestige edits do not rewrite your career's saved inputs.</p>
<p><a href="/world/player-decisions">Test hypothetical player decisions without creating a career →</a></p>
<label>Economy model</label><select name="economy_version"><option value="prototype-v1">Prototype v1 (fictional, subject to rebalance)</option></select>
<label>Financial scale</label><select name="scale"><option value="0.5">Conservative 0.5×</option><option value="1" selected>Baseline 1×</option><option value="1.5">Generous 1.5×</option></select>
<label>PES season squad lock</label><input type="date" name="pes_lock_date" value="2026-08-01" required>
<label>Next summer registration date</label><input type="date" name="next_summer_date" value="2027-07-01" required>
<p><button>Create separate career</button></p></form>
{% elif mode == 'career' %}
<p><a href="/world/play">← My development careers</a> ·
<a href="/world/reputations/career/{{career['career_id']}}">Career reputation history →</a> ·
<a href="/world/player-decisions">Player-decision scenario lab →</a> ·
<a href="/world/play/career/{{career['career_id']}}/management">Career finance, contracts &amp; board confidence →</a> ·
<a href="/world/play/career/{{career['career_id']}}/selling">Selling clubs and board overrides →</a></p>
<div class="warn"><b>Player/agent rules:</b> {{decision_policy['version']}}.
{% if decision_policy['version']=='player-decisions-v2' %}
This career stores a fixed provisional prestige calibration and now requires
<b>explicit current wage, current squad role, transfer listing and renewal circumstances</b>
for each player before agent talks, plus the continental competition
at each club. Those are user-entered <b>fictional sandbox assumptions</b>
until independently sourced, not inferred real salaries or transfer requests.
An elite Arsenal regular will not downgrade merely for a nominal wage offer.
{% elif decision_policy['version']=='player-decisions-v1' %}
This existing career retains its frozen proposal prestige snapshot and earlier prestige/age model.
Its player circumstances are not silently changed to v2.
{% else %}This older career retains its earlier sporting-only algorithm.{% endif %}
</div>
<div class="grid"><div class="card"><span class="muted">Available transfer budget</span><h2>{{remaining_label}}</h2></div>
<div class="card"><span class="muted">Total weekly wage budget</span><h2>{{wage_total_label}}</h2></div>
<div class="card"><span class="muted">Committed weekly wages</span><h2>{{wage_committed_label}}</h2></div>
<div class="card"><span class="muted">Reserved for future deals</span><h2>{{wage_reserved_label}}</h2></div>
<div class="card"><span class="muted">Remaining weekly wage budget</span><h2>{{wage_remaining_label}}</h2></div>
<div class="card"><span class="muted">Season lock</span><h2>{{career['pes_lock_date']}}</h2></div>
<div class="card"><span class="muted">Next registration</span><h2>{{career['next_summer_date']}}</h2></div></div>
<p class="muted"><b>Simulation wage capacity only:</b> Existing squad wages have not yet been imported or modelled.
The committed figure is the career ledger, not the real current payroll. Agreed future deals reserve wages immediately.
Actual available headroom may be lower once existing contracts are included.</p>
<h2>Transfer process — five stages</h2>
<div class="card">
<p><b>1.</b> Submit offer → <b>2.</b> Selling club responds →
<b>3.</b> Player consideration and contract negotiations →
<b>4.</b> Player/agent accept or refuse →
<b>5.</b> Human manager confirms or backs out, with a final board-exception review.</p>
{% if transfer_protocol_on %}
<p><b>Five-stage protocol active.</b> Financial affordability limits the offer.
Configured board policies apply their exceptional veto when you confirm, not
before the player has considered the contract. Signed future agreements remain
binding but PES registration changes only in a later season.</p>
{% else %}
<p class="muted">This career still has its previous transfer policy:
configured boards may decline a proposed bid before player negotiations.
Existing offers and agreements keep the transfer rules under which they were created.</p>
<form method="post" action="/world/play/career/{{career['career_id']}}/protocol/enable">
<input type="hidden" name="csrf" value="{{csrf}}">
<label>Activation record</label>
<input name="activation_note" required
value="Explicit fictional career five-stage transfer process">
<button>Enable five-stage transfer protocol for new negotiations</button>
</form>
{% endif %}
</div>
<h2 id="transfer-offers">Make a transfer offer</h2>
<p>Find any registered player by name, including players outside the previous top-300 list.</p>
<form method="get" action="/world/play/career/{{career['career_id']}}#transfer-offers">
<label>Search the entire career player database</label>
<input type="search" name="player_search" value="{{player_search}}"
  placeholder="e.g. Wood or Maguire" maxlength="80" aria-label="Player name">
<button type="submit">Find player</button>
</form>
{% if player_search %}
<p class="muted">{{targets|length}} matching targets shown for "{{player_search}}".
{% if not targets %}Try another name or check whether the player is already in your squad.{% endif %}</p>
{% else %}
<p class="muted">Showing the highest-rated 150 players. Search to find anyone else.</p>
{% endif %}
{% if notice and notice_scope=='offer' %}<div class="warn" role="status">{{notice}}</div>{% endif %}
{% if error and (notice_scope=='offer' or not notice_scope) %}<div class="warn" role="alert"><b>Offer could not proceed:</b> {{error}}</div>{% endif %}
<form method="post" action="{{url_for('world_play.offer',career_id=career['career_id'])}}">
<input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="request_key" value="{{request_key}}">
<input type="hidden" name="player_search" value="{{player_search}}">
<label>Target player (source data; not a confirmed registration)</label>
<select name="player_id" required {% if not targets %}disabled{% endif %}>
{% for t in targets %}<option value="{{t['player_id']}}">{{t['full_name']}} — {{t['club_name']|club_display}} · OVR {{t['overall'] if t['overall'] is not none else '?'}}</option>{% endfor %}
</select>
<label>Buying club</label><select name="buying_club_id"><option value="{{career['manager_club_id']}}">{{manager_name|club_display}}</option></select>
<label>Offer fee (£)</label><input type="number" name="offered_fee" min="0" step="100000" value="1000000" required>
<label>Agreement date</label><input type="date" name="agreement_date" value="{{today}}" required>
<label>Seller's negotiating stance</label><select name="seller_stance">
<option value="neutral">Normal seller</option><option value="rival">Direct rival</option><option value="selling">Transfer-listed</option></select>
<p><button {% if not targets %}disabled{% endif %}>Send offer</button></p></form>
<div class="warn"><b>Selling-club decision rules:</b>
{% if seller_policy_on %}
Enhanced selling-club decisions are active. Supply explicit seller circumstances in
<a href="/world/play/career/{{career['career_id']}}/selling">Selling clubs &amp; boards</a>
before submitting a bid. An unknown selling position will block the offer.
Existing offers retain their frozen terms.
{% else %}
Legacy seller response is still active for this career.
You can <a href="/world/play/career/{{career['career_id']}}/selling">opt into the new
seller and board decision system</a> without changing historical offers.
{% endif %}</div>
<h2 id="ai-rivals">Simulate competing-club bids</h2>
{% if notice and notice_scope=='ai' %}<div class="warn" role="status">{{notice}}</div>{% endif %}
{% if error and notice_scope=='ai' %}<div class="warn" role="alert">{{error}}</div>{% endif %}
<div class="card"><p>AI buyers value a player differently according to rated squad needs, financial resources, seller circumstances and credible rival interest. A rejected club can return with a higher offer at most twice, but pending or accepted offers remain open.</p><p>Run an optional AI-rival bidding round for one target. Opponent budgets are reserved if an offer is created.
This is an explicit sandbox simulation, not a claim that real clubs have placed bids.</p>
<form method="post" action="/world/play/career/{{career['career_id']}}/ai">
<input type="hidden" name="csrf" value="{{csrf}}">
<label>Target player</label><select name="player_id">{% for t in targets %}<option value="{{t['player_id']}}">{{t['full_name']}} — {{t['club_name']|club_display}}</option>{% endfor %}</select>
<button>Simulate rival interest (up to 2 AI offers)</button>
</form></div>
<h2 id="ai-inbound">Simulate incoming offers for your own players</h2>
{% if notice and notice_scope=='ai_inbound' %}<div class="warn" role="status">{{notice}}</div>{% endif %}
{% if error and notice_scope=='ai_inbound' %}<div class="warn" role="alert">{{error}}</div>{% endif %}
<div class="card">
<p>Offers are club-specific and competitive demand raises valuations. Rejected bids may prompt a higher second or third offer when the buyer still has both budget and sporting interest; repeated simulations alone do not reset existing agreements.</p>
<p>Run an optional fictional round of buying-club interest in a member of your own squad.
If the enhanced seller engine is on, you must first record that player's
<a href="/world/play/career/{{career['career_id']}}/selling">seller circumstances</a>.
A board-directed fee agreement can overrule your wish to keep the player,
but it does not register a transfer or establish the player's consent.</p>
<form method="post" action="/world/play/career/{{career['career_id']}}/ai-inbound">
<input type="hidden" name="csrf" value="{{csrf}}">
<label>Player in your squad</label>
<select name="player_id">
{% for p in home_players %}<option value="{{p['player_id']}}">{{p['full_name']}}</option>
{% endfor %}</select>
<p><button {% if not home_players %}disabled{% endif %}>Simulate incoming bids</button></p>
</form></div>
<h2 id="negotiations">Negotiations</h2>
{% if notice and notice_scope in ['seller_review','offer'] %}<div class="warn" role="status">{{notice}}</div>{% endif %}
{% if error and notice_scope=='seller_review' %}<div class="warn" role="alert">{{error}}</div>{% endif %}
<table><tr><th>Player</th><th>Buying club</th><th>Selling club</th><th>Offered fee</th><th>Stage</th><th>Next steps</th></tr>
{% for o in offers %}<tr><td>{{o['full_name']}}</td><td><b>{{o['buyer_name']|club_display}}</b>{% if o['buying_club_id']==career['manager_club_id'] %} <small>(Your club)</small>{% else %} <small>(AI rival)</small>{% endif %}</td><td>{{o['seller_name']|club_display}}</td><td>{{o['fee_label']}}</td><td>{{o['stage_label']}}
{% if o['demanded_fee'] is not none %}<p class="muted">Counter: {{o['counter_label']}}</p>{% endif %}
{% if o['ai_bid'] %}
<p class="muted"><b>AI bid round {{o['ai_bid']['round']}} of 3:</b>
{{o['ai_bid']['reason']}}</p>
<p class="muted">Eligible rivals: {{o['ai_bid']['eligible_competing_clubs']}} ·
Market demand premium: +{{o['ai_bid']['demand_premium_pct']}}% ·
Buyer need: {{o['ai_bid']['buyer_need_score']}}/100.
{% if o['ai_bid']['last_offer'] is not none %}
Raised from £{{'{:,}'.format(o['ai_bid']['last_offer'])}} after a rejection.
{% endif %}</p>
{% endif %}
{% if o['seller_review'] %}
<p class="muted"><b>Seller:</b> {{o['seller_review']['effective_decision']|title}}
· <b>Board:</b> {{o['seller_review']['board_decision']|replace('_',' ')|title}}.</p>
<p class="muted">{{o['seller_review']['seller_reason']}}</p>
{% if o['seller_review']['board_decision']=='direct_sale' %}
<p class="warn">Selling board directed a fee agreement despite the manager's preference.
The player has NOT agreed to leave and no registration has changed.</p>{% endif %}
{% endif %}
{% if o['status']=='proposed' and not o['seller_review'] and seller_policy_on %}
<div class="warn"><b>Offer recorded — awaiting selling club information.</b>
This bid is not accepted or rejected yet. The selling club's contract, squad role,
transfer-listing and financial position are still needed.
<a href="/world/play/career/{{career['career_id']}}/selling?player_id={{o['player_id']}}">Record {{o['full_name']}}'s selling-club circumstances</a>.
</div>
{% endif %}
{% if o['effective_date'] %}<p class="muted">Summer registration: {{o['effective_date']}}</p>{% endif %}
{% if o['status']=='accepted_pending_contract' %}<p class="muted">Player fit: <b>{{o['interest_signal']}}</b> — {{o['interest_reason']}}</p>
{% if o['interest_phase'] %}<p class="muted">Career stage: {{o['interest_phase']}} · Required role:
{{role_labels[o['interest_required_role']] if o['interest_required_role'] in role_labels else o['interest_required_role']|replace('_',' ')}} · Provisional prestige: buyer
{{o['interest_buyer_prestige']}}, seller {{o['interest_seller_prestige']}}.
{% if o['interest_competitor_pressure'] %}Simulated rival pressure: {{o['interest_competitor_pressure']}}.{% endif %}</p>{% endif %}
{% endif %}</td><td>
{% if o['status']=='proposed' and not o['seller_review'] and seller_policy_on %}
<form method="post" action="/world/play/career/{{career['career_id']}}/seller/review">
<input type="hidden" name="csrf" value="{{csrf}}">
<input type="hidden" name="offer_id" value="{{o['offer_id']}}">
<button>Get selling club response</button>
</form>
<p class="muted">First record the missing seller facts using the link beside the offer.</p>
{% endif %}
{% if o['selling_club_id']==career['manager_club_id']
      and o['buying_club_id']!=career['manager_club_id'] %}
<div class="card">
<p><b>Incoming AI offer — independent player and agent decisions</b></p>
{% if o['incoming'] %}
<p class="muted"><b>{{o['incoming']['status']|replace('_',' ')|title}}</b>:
{{o['incoming']['decision_reason']}}</p>
{% if o['incoming']['offered_wage_weekly'] is not none %}
<p class="muted">AI offered £{{'{:,}'.format(o['incoming']['offered_wage_weekly'])}}/week
{% if o['incoming']['agent_requested_weekly'] is not none %}
· Agent requested £{{'{:,}'.format(o['incoming']['agent_requested_weekly'])}}/week{% endif %}
· {{o['incoming']['role_promise']|replace('_',' ')|title}} role</p>{% endif %}
{% else %}
<p class="muted">Club fee agreed only. Player interest, salary, squad role and
European football circumstances still need assessment.</p>
{% endif %}
{% if decision_policy['version']=='player-decisions-v2'
      and o['status']=='accepted_pending_contract' and not o['agent_status'] %}
<form method="post" action="/world/play/career/{{career['career_id']}}/incoming/circumstances">
<input type="hidden" name="csrf" value="{{csrf}}">
<input type="hidden" name="offer_id" value="{{o['offer_id']}}">
<label>Current wage at your club (£/week, sourced or fictional assumption)</label>
<input type="number" name="current_wage_weekly" min="0" max="1000000" required
value="{{o['context']['current_wage_weekly'] if o['context'] else
  (o['known_contract']['wage_weekly'] if o['known_contract'] and o['known_contract']['wage_weekly'] is not none else '')}}">
<label>Current squad status</label>
{% set cur_role=o['context']['current_role'] if o['context'] else
 (o['known_contract']['squad_role'] if o['known_contract'] and o['known_contract']['squad_role'] else '') %}
<select name="current_role" required>
<option value="">Select verified or explicitly assumed role</option>
{% for code in ['key_player','regular_starter','rotation','fringe'] %}
<option value="{{code}}" {% if code==cur_role %}selected{% endif %}>{{code|replace('_',' ')|title}}</option>
{% endfor %}</select>
<label>Transfer-listed?</label>
{% set listed=o['context']['transfer_listed'] if o['context'] else
 (o['seller_info']['transfer_listed'] if o['seller_info'] else none) %}
<select name="transfer_listed" required>
<option value="">Unknown — please decide</option>
<option value="yes" {% if listed==1 %}selected{% endif %}>Yes</option>
<option value="no" {% if listed==0 %}selected{% endif %}>No</option>
</select>
<label>Renewal situation at your club</label><select name="renewal_status">
<option value="unknown">Unknown — blocks decision</option>
<option value="renewal_offered" {% if o['context'] and o['context']['renewal_status']=='renewal_offered' %}selected{% endif %}>Renewal offered / current club wants to keep</option>
<option value="not_offered" {% if o['context'] and o['context']['renewal_status']=='not_offered' %}selected{% endif %}>No renewal offered</option>
</select>
<label>Buying club's European competition</label><select name="buyer_europe">
{% for code in ['unknown','none','conference_league','europa_league','champions_league'] %}
<option value="{{code}}" {% if o['europe_context'] and o['europe_context']['buyer_europe']==code %}selected{% endif %}>{{code|replace('_',' ')|title}}</option>{% endfor %}
</select>
<label>Your club's European competition</label><select name="seller_europe">
{% for code in ['unknown','none','conference_league','europa_league','champions_league'] %}
<option value="{{code}}" {% if o['europe_context'] and o['europe_context']['seller_europe']==code %}selected{% endif %}>{{code|replace('_',' ')|title}}</option>{% endfor %}
</select>
<button>Record player circumstances (fictional scenario unless sourced)</button>
</form>
{% endif %}
{% if o['status']=='accepted_pending_contract' %}
{% if o['incoming'] and o['incoming']['status']=='terms_accepted' %}
<div class="warn"><b>Stage 4 complete: player and agent accepted.</b>
This is NOT a transfer yet. You must explicitly authorise a binding
future-dated agreement; the board may still veto by exception.</div>
{% if transfer_protocol_on %}
<form method="post" action="/world/play/career/{{career['career_id']}}/incoming/finalise">
<input type="hidden" name="csrf" value="{{csrf}}">
<input type="hidden" name="offer_id" value="{{o['offer_id']}}">
<button>Stage 5 — confirm incoming sale (subject to board veto)</button>
</form>
{% else %}<p>Enable the five-stage protocol above to authorise the final sale.</p>{% endif %}
{% elif not o['incoming'] or o['incoming']['status'] not in ['player_refused','role_refused','wage_limit'] %}
<form method="post" action="/world/play/career/{{career['career_id']}}/incoming/advance">
<input type="hidden" name="csrf" value="{{csrf}}">
<input type="hidden" name="offer_id" value="{{o['offer_id']}}">
<button>{% if o['incoming'] and o['incoming']['status']=='agent_counter' %}
Stage 3 — continue AI agent negotiation
{% else %}Stage 3 — assess player interest and contract terms{% endif %}</button>
</form>
{% endif %}
<form method="post" action="/world/play/career/{{career['career_id']}}/incoming/cancel">
<input type="hidden" name="csrf" value="{{csrf}}">
<input type="hidden" name="offer_id" value="{{o['offer_id']}}">
<button class="danger">Reject this AI offer — a higher bid may follow</button>
</form>
{% endif %}
<p class="muted">The player's decision may veto a board-approved sale. A fee
agreement is not personal consent. No real club contracts are inferred.</p>
</div>
{% endif %}
{% if decision_policy['version']=='player-decisions-v2'
      and o['buying_club_id']==career['manager_club_id']
      and o['status']=='accepted_pending_contract' %}
<div class="card">
<p><b>Current player's circumstances (manual sandbox assumption)</b></p>
{% if o['context'] %}
<p class="muted">Current salary: {{o['context_wage_label']}}/week ·
Current role: {{role_labels[o['context']['current_role']] if o['context']['current_role'] in role_labels else o['context']['current_role']|replace('_',' ')}} ·
Transfer-listed: {{'yes' if o['context']['transfer_listed'] else 'no'}} ·
Renewal: {{o['context']['renewal_status']|replace('_',' ')}}.
{% if o['europe_context'] %}<br/>Current club Europe: {{o['europe_context']['seller_europe']|replace('_',' ')}} ·
Interested club Europe: {{o['europe_context']['buyer_europe']|replace('_',' ')}}.
{% else %}Continental participation at both clubs is unknown.{% endif %}
These are <b>not verified real-world terms</b>.</p>
{% else %}
<p class="muted">Current wage, present squad status, transfer listing and renewal
are unknown. Continental competition at both clubs must also be supplied.
Enter explicit scenario assumptions before player interest can be assessed;
the game will not assume an elite regular wants to leave.</p>
{% endif %}
{% if not o['agent_status'] %}
<form method="post" action="/world/play/career/{{career['career_id']}}/circumstances">
<input type="hidden" name="csrf" value="{{csrf}}">
<input type="hidden" name="offer_id" value="{{o['offer_id']}}">
<label>Current weekly wage at selling club (£)</label>
<input type="number" name="current_wage_weekly" min="0" max="1000000" step="500"
 value="{{o['context']['current_wage_weekly'] if o['context'] else ''}}"
 placeholder="Known or explicitly assumed wage" required>
<label>Current squad status at selling club</label>
<select name="current_role">
<option value="key_player" {% if o['context'] and o['context']['current_role']=='key_player' %}selected{% endif %}>Key Player</option>
<option value="regular_starter" {% if o['context'] and o['context']['current_role'] in ('regular_starter','important') %}selected{% endif %}>Regular Starter</option>
<option value="rotation" {% if o['context'] and o['context']['current_role']=='rotation' %}selected{% endif %}>Rotation Player</option>
<option value="fringe" {% if o['context'] and o['context']['current_role']=='fringe' %}selected{% endif %}>Fringe Player</option>
</select>
<label>Is the player transfer listed?</label>
<select name="transfer_listed">
<option value="no" {% if not o['context'] or not o['context']['transfer_listed'] %}selected{% endif %}>No</option>
<option value="yes" {% if o['context'] and o['context']['transfer_listed'] %}selected{% endif %}>Yes</option>
</select>
<label>Current club's contract renewal situation</label>
<select name="renewal_status">
<option value="unknown" {% if not o['context'] or o['context']['renewal_status']=='unknown' %}selected{% endif %}>Unknown — cannot assume release</option>
<option value="renewal_offered" {% if o['context'] and o['context']['renewal_status']=='renewal_offered' %}selected{% endif %}>Renewal offered / current club wants to keep him</option>
<option value="not_offered" {% if o['context'] and o['context']['renewal_status']=='not_offered' %}selected{% endif %}>No renewal being offered</option>
</select>
<label>European participation at player's current club</label>
<select name="seller_europe">
{% for code,label in europe_labels.items() %}
<option value="{{code}}" {% if (o['europe_context']['seller_europe'] if o['europe_context'] else 'unknown')==code %}selected{% endif %}>{{label}}</option>
{% endfor %}</select>
<label>European participation at interested club</label>
<select name="buyer_europe">
{% for code,label in europe_labels.items() %}
<option value="{{code}}" {% if (o['europe_context']['buyer_europe'] if o['europe_context'] else 'unknown')==code %}selected{% endif %}>{{label}}</option>
{% endfor %}</select>
<p class="muted">Choose the specific current/next-season competition, or keep it
unknown. A club's Champions League participation is not inferred from
its history, stadium or current league position. These statuses are
manager-supplied sandbox assumptions until results are sourced.</p>
<button type="submit">Record player and club context for this sandbox</button>
</form>
{% else %}
<p class="muted">Player assumptions are locked once agent talks begin.</p>
{% endif %}
</div>
{% endif %}
{% if o['buying_club_id']==career['manager_club_id'] and o['status']=='countered' %}
<form class="inline" method="post" action="/world/play/career/{{career['career_id']}}/accept">
<input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="offer_id" value="{{o['offer_id']}}">
<button>Accept counter</button></form>{% endif %}
{% if o['buying_club_id']==career['manager_club_id'] and o['status']=='accepted_pending_contract' and o['agent_status']=='accepted' %}
<div class="card"><p><b>Agent has accepted the proposed personal terms.</b> No transfer agreement has been confirmed yet.</p>
<p class="muted">The sporting-interest indicator is provisional and is not proof of player consent.</p>
<form method="post" action="/world/play/career/{{career['career_id']}}/confirm">
<input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="offer_id" value="{{o['offer_id']}}">
<label>Agreement date</label><input type="date" name="agreement_date" value="{{today}}" required>
<button>{% if o['offer_five_stage'] %}
Stage 5 — confirm signing (subject to board exception veto)
{% else %}Confirm future transfer agreement{% endif %}</button></form></div>
{% elif o['buying_club_id']==career['manager_club_id'] and o['status']=='accepted_pending_contract' and not o['interest_can_negotiate'] %}
<p class="muted">The player is not prepared to discuss this move, or their circumstances have not
been established. Review the player's wage, present squad role and contract
situation above; a large salary cannot override a serious sporting or career obstacle.</p>
{% elif o['buying_club_id']==career['manager_club_id'] and o['status']=='accepted_pending_contract' %}
<form method="post" action="/world/play/career/{{career['career_id']}}/agree">
<input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="offer_id" value="{{o['offer_id']}}">
{% if o['agent_demand'] is not none %}<p class="muted">Agent's fictional wage request: <b>{{o['agent_demand_label']}} per week</b>
{% if o['agent_status']=='countered' %} · Counteroffer requested{% endif %}</p>{% endif %}
<label>Weekly wage offer (£)</label>
<input type="number" name="weekly_wage" data-budget-wage min="0" value="10000" required
 data-wage-offer data-remaining="{{wage_remaining_raw}}">
<p class="muted">Weekly headroom before this offer: <b>{{wage_remaining_label}}</b>.
<span data-wage-preview>Headroom if £10k/week is accepted: {{wage_default_preview}}</span>
</p>
<label>Proposed squad role</label><select name="role_promise">
<option value="unspecified">No guaranteed role</option>
<option value="key_player">Key Player</option>
<option value="regular_starter">Regular Starter</option>
<option value="rotation">Rotation Player</option>
<option value="fringe">Fringe Player</option></select>
{% if o['interest_decision']=='needs_assurances' %}<p class="muted">
The minimum possible promise is {{role_labels[o['interest_required_role']] if o['interest_required_role'] in role_labels else o['interest_required_role']|replace('_',' ')}}.
{% if o['interest_issue']=='wage' %}The squad-role condition is already met; salary terms still need improvement.
{% elif o['interest_issue']=='wage_and_role' %}Salary and squad-role assurances both need attention.
{% else %}Agent wage demands may increase because of sporting, historical-prestige or rival-offer concerns.{% endif %}</p>{% endif %}
<label>Contract duration</label><select name="contract_years"><option value="1">1 year</option><option value="2">2 years</option><option value="3" selected>3 years</option><option value="4">4 years</option><option value="5">5 years</option></select>
<label>Agreement date</label><input type="date" name="agreement_date" value="{{today}}" required>
<button>Send offer to player's agent</button></form>{% endif %}
{% if o['buying_club_id']==career['manager_club_id'] and
    (o['status'] in ('proposed','countered','accepted_pending_contract')
     or (not o['offer_five_stage'] and o['status']=='agreed_future')) %}
<form method="post" action="/world/play/career/{{career['career_id']}}/withdraw">
<input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="offer_id" value="{{o['offer_id']}}">
<button class="danger">Withdraw</button></form>{% endif %}
</td></tr>{% endfor %}</table>
{% if not offers %}<p class="muted">No negotiations created yet.</p>{% endif %}
<p class="muted">AI bids are generated only on request; there is no automatic background transfer activity.</p>
{% endif %}
<script>
document.querySelectorAll('[data-wage-offer]').forEach(function(input) {
  const label=input.parentElement.querySelector('[data-wage-preview]');
  const capacity=Number(input.dataset.remaining);
  function update() {
    const offered=Number(input.value);
    if (!Number.isFinite(offered) || offered<0) {
      label.textContent='Enter a valid weekly wage.';
      return;
    }
    const remaining=capacity-offered;
    label.textContent='Headroom if accepted: '+new Intl.NumberFormat('en-GB',{
      style:'currency',currency:'GBP',maximumFractionDigits:0
    }).format(remaining)+' per week'+(remaining<0?' — exceeds available budget':'');
    label.style.color=remaining<0?'#ffb6b6':'';
  }
  input.addEventListener('input',update);
  update();
});
</script>
</main></body></html>"""



def format_market_gbp(value):
    """Readable transfer money; keep integer pounds in persistent ledgers."""
    amount=int(value or 0)
    sign="-" if amount<0 else ""
    absolute=abs(amount)
    if absolute>=1_000_000:
        return f"{sign}£{absolute/1_000_000:,.2f}m"
    if absolute>=1_000:
        return f"{sign}£{absolute/1_000:,.0f}k"
    return f"{sign}£{absolute:,}"

LIVE_MARKET_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>{{title}} | Pre-season transfer window</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}
body{margin:0;background:#101a27;color:#ecf5ff;font:15px/1.55 system-ui,-apple-system,sans-serif}
header{padding:16px 22px;background:#1b3044}main{max-width:1060px;margin:20px auto;padding:0 17px 75px}
a{color:#b8dbff}h1{font-size:27px;margin:8px 0 6px}h2{margin:32px 0 12px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(285px,1fr));gap:14px}
.card{background:#1d3044;border:1px solid #3c5c78;border-radius:12px;padding:18px;margin:12px 0}
.muted{color:#bed0e1}.label{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#b3d1e8;font-weight:700}
.clock{font-variant-numeric:tabular-nums;font-size:clamp(42px,8vw,70px);font-weight:800;line-height:1.1;margin:10px 0}
button,input{font:inherit;border-radius:7px;border:1px solid #7593ac;background:#29465e;color:white;padding:10px}
button{background:#3276a7;cursor:pointer;font-weight:600}
button:disabled{opacity:.45;cursor:not-allowed}.danger{background:#81414b}
.actions{display:flex;align-items:end;gap:8px;flex-wrap:wrap;margin-top:12px}
form{display:inline-flex;align-items:end;gap:7px;flex-wrap:wrap}
input[type=number]{width:145px}label{display:inline-block;font-size:12px;color:#ccdceb}
.offer{border-left:3px solid #6dbbec;padding-left:15px}
.rail{display:flex;gap:14px;flex-wrap:wrap;margin:14px 0}
.pill{background:#253d52;padding:5px 11px;border-radius:30px;font-size:13px}
.count{color:#78d4b1;font-size:20px;font-weight:700}.alert{border-left:3px solid #f0a85d;padding-left:12px}
.time-note{font-size:12px;color:#b1c5d6}.feed .card{padding:12px 16px}
small{color:#b4cadb}form.inline{display:inline-flex}
.budget-track{height:13px;border-radius:8px;background:#3b4e61;overflow:hidden;margin:7px 0}
.budget-fill{height:100%;background:#63cca0;transition:width .18s}
.budget-fill.warning{background:#f0a85d}
.preview-text{font-size:13px;color:#c5dcf0}
.scout-filters{display:flex;gap:10px;flex-wrap:wrap;align-items:end}
.scout-table{overflow-x:auto;max-height:500px;overflow-y:auto}
.scout-table table{width:100%;border-collapse:collapse;font-size:13px;white-space:nowrap}
.scout-table th,.scout-table td{padding:8px;border-bottom:1px solid #40566b;text-align:left}
.scout-table th{position:sticky;top:0;background:#20364c}
.scout-table tr.owned{background:#233c49}

</style></head><body class="desk-ui" data-window-state="{{snap.state}}" data-spectator="{{'true' if spectator else 'false'}}"
 data-incoming-offers="{{offers|length}}" data-unread="{{unread}}"
 data-signed="{{signed}}" data-saved="{{shortlist|length}}"
 data-fee-remaining="{{funds}}" data-fee-total="{{budget_total}}"
 data-wage-remaining="{{wage_headroom}}" data-wage-total="{{wage_total}}">
<header class="desk-topbar">
 <a href="/world/play" class="desk-brand">
  <span class="desk-logo" aria-hidden="true">PES</span>
  <span><strong>Clubs Challenge</strong><small>Career transfer centre · Development</small></span>
 </a>
 <div class="desk-header-right">
  <span class="desk-header-tag"><strong>{{manager_name|club_display}}</strong> · Summer window</span>
  <span class="desk-live-status {{'closed' if snap.state!='open' else ''}}">
   {{'Live market' if snap.state=='open' else 'Window closed' if snap.state=='closed' else 'Pre-season'}}
  </span>
  <span class="desk-header-clock">
   <small>Deadline</small>
   <strong id="desk-header-clock" data-deadline="{{snap.deadline_at or ''}}">--:--</strong>
  </span>
 </div>
</header>
<main class="desk-shell">
{% if not spectator %}
<aside class="desk-sidebar">
 <div class="desk-nav-label">Manager workspace</div>
 <nav aria-label="Transfer Desk sections">
  <a class="desk-tab" href="#dashboard" data-desk-tab="dashboard"><span class="desk-nav-icon" aria-hidden="true">⌂</span><span class="desk-nav-text">Overview</span></a>
  <a class="desk-tab" href="#inbox" data-desk-tab="inbox"><span class="desk-nav-icon" aria-hidden="true">✉</span><span class="desk-nav-text">Inbox</span>{% if unread %}<span class="desk-nav-count">{{unread}}</span>{% endif %}</a>
  <a class="desk-tab" href="#transfers" data-desk-tab="transfers"><span class="desk-nav-icon" aria-hidden="true">⇄</span><span class="desk-nav-text">Transfers</span></a>
  <a class="desk-tab" href="#squad" data-desk-tab="squad"><span class="desk-nav-icon" aria-hidden="true">♟</span><span class="desk-nav-text">Squad</span></a>
  <a class="desk-tab" href="#scouting" data-desk-tab="scouting"><span class="desk-nav-icon" aria-hidden="true">⌕</span><span class="desk-nav-text">Scouting</span></a>
  <a class="desk-tab" href="#shortlist" data-desk-tab="shortlist"><span class="desk-nav-icon" aria-hidden="true">☆</span><span class="desk-nav-text">Shortlist</span><span class="desk-nav-count">{{shortlist|length}}</span></a>
  <a class="desk-tab" href="#finances" data-desk-tab="finances"><span class="desk-nav-icon" aria-hidden="true">£</span><span class="desk-nav-text">Finances</span></a>
  {% if snap.state=='closed' %}
  <a class="desk-tab" href="#season-setup" data-desk-tab="season-setup"><span class="desk-nav-icon" aria-hidden="true">✓</span><span class="desk-nav-text">Season setup</span></a>
  {% endif %}
  <a class="desk-tab" href="#news" data-desk-tab="news"><span class="desk-nav-icon" aria-hidden="true">☷</span><span class="desk-nav-text">Market news</span></a>
 </nav>
 <div class="desk-sidebar-foot">
  <p>Pre-season transfer window</p>
  <a href="/world/play">← All development careers</a>
 </div>
</aside>
{% endif %}
<div class="desk-workspace">
 <div class="desk-intro">
  <div>
   <div class="desk-section-kicker" id="desk-current-view">Manager overview</div>
   <h1>{{title}}</h1>
   <p class="muted">{{manager_name|club_display}} · {{'30-minute window active' if snap.state=='open' else 'Transfer window closed' if snap.state=='closed' else 'Pre-season planning'}}{% if spectator %} · Read only · Spectator{% endif %}</p>
  </div>
 </div>
 {% if not spectator %}
 <nav class="desk-mobile-tabs" aria-label="Transfer Desk mobile sections">
  <a class="desk-tab" href="#dashboard" data-desk-tab="dashboard"><span class="desk-nav-icon">⌂</span> Overview</a>
  <a class="desk-tab" href="#inbox" data-desk-tab="inbox"><span class="desk-nav-icon">✉</span> Inbox</a>
  <a class="desk-tab" href="#transfers" data-desk-tab="transfers"><span class="desk-nav-icon">⇄</span> Transfers</a>
  <a class="desk-tab" href="#squad" data-desk-tab="squad"><span class="desk-nav-icon">♟</span> Squad</a>
  <a class="desk-tab" href="#scouting" data-desk-tab="scouting"><span class="desk-nav-icon">⌕</span> Scouting</a>
  <a class="desk-tab" href="#shortlist" data-desk-tab="shortlist"><span class="desk-nav-icon">☆</span> Shortlist</a>
  <a class="desk-tab" href="#finances" data-desk-tab="finances"><span class="desk-nav-icon">£</span> Finances</a>
  {% if snap.state=='closed' %}
  <a class="desk-tab" href="#season-setup" data-desk-tab="season-setup"><span class="desk-nav-icon">✓</span> Season setup</a>
  {% endif %}
  <a class="desk-tab" href="#news" data-desk-tab="news"><span class="desk-nav-icon">☷</span> News</a>
 </nav>
 {% endif %}
 {% if error %}<div class="desk-global-message alert" role="alert">{{error}}</div>{% endif %}
 {% if notice %}<div class="desk-global-message" role="status">{{notice}}</div>{% endif %}
 {% if snap.state=='closed' %}
 <div class="desk-global-message" role="status"><strong>The 30-minute window has closed.</strong>
 <a href="#transfers" data-desk-tab="transfers">View transfer summary</a>
 · <a href="#season-setup" data-desk-tab="season-setup">Proceed to season setup</a>.
 Only signed deals have registered in this career ledger.</div>
 {% endif %}
 {% if purchases|selectattr('status','equalto','rejected')|list|length %}
 <div class="desk-global-message alert" role="alert">
 <strong>Transfer bid rejected.</strong>
 One or more selling clubs have declined your offers.
 <a href="#inbox" data-desk-tab="inbox">Review rejected bids in the Inbox</a>.
 </div>
 {% endif %}
 <div id="desk-view-host"></div>
 <div id="desk-screen-source">
{% if not spectator %}
<h2 id="squad">Current squad &amp; live signings</h2>
<div class="card">

<div class="scout-table desk-squad-table"><table data-desk-table="squad"><thead>
<tr><th>Player</th><th>Position</th><th data-sort-type="number">OVR</th><th data-sort-type="number">Market value</th>
<th>Squad status</th><th>Transfer list / availability</th></tr></thead><tbody>
{% for p in squad.players %}
<tr>
<td><strong>{{p.full_name}}</strong>
{% if p.incoming %}<span class="pill">Agreed signing</span>{% endif %}
{% if p.morale_status=='transfer_requested' %}
<span class="pill" title="{{p.morale_reason}}">Transfer request</span>{% endif %}</td>
<td>{{p.position or '—'}}</td><td data-sort-value="{{p.overall}}">{{p.overall}}</td>
<td data-sort-value="{{p.market_value or 0}}">{{money(p.market_value) if p.market_value is not none else '—'}}</td>
<td>
{% if not p.incoming and snap.state in ('not_started','open') %}
<form method="post" action="/world/play/career/{{career_id}}/market/squad/decision">
<input type="hidden" name="csrf" value="{{csrf}}">
<input type="hidden" name="player_id" value="{{p.player_id}}">
<select name="role" aria-label="Squad role for {{p.full_name}}">
<option value="key_player" {% if p.role=='key_player' %}selected{% endif %}>Key Player</option>
<option value="regular_starter" {% if p.role=='regular_starter' %}selected{% endif %}>Regular Starter</option>
<option value="rotation" {% if p.role=='rotation' %}selected{% endif %}>Rotation</option>
<option value="fringe" {% if p.role=='fringe' %}selected{% endif %}>Backup / Fringe</option>
</select>
<label><input type="checkbox" name="listed" value="1" {% if p.listed %}checked{% endif %}>
 Transfer listed</label>
<button name="action" value="update">Update</button>
{% if snap.state=='open' %}
<button name="action" value="offer" title="Circulate this player to interested AI clubs during remaining market moments">Offer to clubs</button>
{% endif %}
</form>
{% else %}
{{p.role|replace('_',' ')|title}}
{% endif %}
</td>
<td>{{'Listed' if p.listed else 'Not listed'}}
{% if p.incoming %} · Joining at deadline{% endif %}</td>
</tr>
{% endfor %}
</tbody></table></div>
{% if squad.departures %}
<h3>Agreed departures</h3>
<p class="muted">{% for p in squad.departures %}{{p.full_name}}{% if not loop.last %} · {% endif %}{% endfor %}</p>
{% endif %}
{% if squad.unavailable %}
<h3>Unavailable for the PES season</h3>
<div class="desk-unavailable-list">{% for p in squad.unavailable %}
<div><strong>{{p.full_name}}</strong> <span class="pill">Refusing to play</span></div>
{% endfor %}</div>
{% endif %}

</div>
{% endif %}
<h2 id="overview-anchor" hidden>Overview</h2>
{% if snap.state=='not_started' %}
<div class="card"><h2>Your 30-minute transfer window is ready</h2>
<p><a href="/world/play/career/{{career_id}}/market/shortlist">Open saved shortlist</a> — scouting targets can be reviewed before starting the clock.</p>
<p>As soon as the manager starts, the 30-minute real-world clock runs continuously.
AI clubs will assess squad needs automatically and eligible offers will arrive in the inbox.
Your completed transfers register together at the deadline; unfinished negotiations expire.</p>
<p><b>Important:</b> the clock cannot be paused or restarted if you close your browser.
No mid-season transfers. This does not edit the Xbox PES game file.</p>
{% if not spectator %}
<form method="post" action="/world/play/career/{{career_id}}/market/start">
<input type="hidden" name="csrf" value="{{csrf}}">
<input type="hidden" name="confirm" value="start-30-minute-window">
<button>Start 30-minute transfer window</button></form>
{% endif %}</div>
{% if not spectator %}
<div class="card" data-desk-prestart-shortlist>
 <h2>Saved transfer shortlist</h2>
 {% if shortlist %}
 <div class="scout-table"><table data-desk-table="scouting"><thead><tr><th>Player</th><th>Club</th><th>Position</th><th>OVR</th><th>Indicative value</th></tr></thead><tbody>
 {% for p in shortlist %}
 <tr><td><a href="/world/play/career/{{career_id}}/market/player/{{p.player_id}}">{{p.full_name}}</a></td>
 <td>{{p.club_name|club_display}}</td><td>{{p.primary_position or '—'}}</td><td>{{p.overall}}</td>
 <td>{{money(p.market_value) if p.market_value is not none else '—'}}</td></tr>
 {% endfor %}</tbody></table></div>
 {% else %}
 <p class="muted">No players saved yet. Your career shortlist is ready to use once you start scouting.</p>
 {% endif %}
 <p><a href="/world/play/career/{{career_id}}/market/shortlist">Open full shortlist</a></p>
</div>
{% endif %}
{% else %}
<div class="grid">
 <div class="card"><div class="label">{{'Deadline reached' if snap.state!='open' else 'Time remaining'}}</div>
  <div id="window-clock" class="clock" data-deadline="{{snap.deadline_at}}">--:--</div>
  <div class="time-note">One server-controlled deadline · Reloading never restarts it.</div>
 </div>
 <div class="card"><div class="label">Transfer window</div>
  <h2 style="margin:8px 0">{{'Closed — squads locked' if snap.state=='closed'
       else 'Deadline processing' if snap.state=='deadline_reached'
       else 'Open for business'}}</h2>
  <div class="rail"><span class="pill">📩 <b>{{unread}}</b> unread</span>
  <span class="pill">🤝 <b>{{offers|length}}</b> received bids</span>
  <span class="pill">✅ <b>{{signed}}</b> agreed deals</span></div>
  <div class="budget-panel" id="budget-panel"
       data-fee-remaining="{{funds}}" data-fee-total="{{budget_total}}"
       data-wage-remaining="{{wage_headroom}}" data-wage-total="{{wage_total}}">
    <div>Transfer budget · <b id="fee-current">{{money(funds)}}</b> available</div>
    <div class="budget-track"><div class="budget-fill" id="fee-bar" style="width:{{(100*funds/[budget_total,1]|max)|round(1)}}%"></div></div>
    <div class="preview-text" id="fee-preview">Adjust your bid to preview the remaining balance.</div>
    <div style="margin-top:14px">Weekly wage budget · <b id="wage-current">{{money(wage_headroom)}}</b> available</div>
    <div class="budget-track"><div class="budget-fill" id="wage-bar" style="width:{{(100*wage_headroom/[wage_total,1]|max)|round(1)}}%"></div></div>
    <div class="preview-text" id="wage-preview">Enter contract wages to preview remaining headroom.</div>
    <p class="time-note">Indicative only. Open offers and signed deals are already reserved in the balances shown.</p>
  </div>

 </div>
</div>
{% if not spectator and watch_url and snap.state=='open' %}
<div class="card desk-spectator-share">
  <h3>Share the live transfer window</h3>
  <p class="muted">Other players can follow the market without seeing or changing your manager decisions.</p>
  <div class="desk-share-controls">
    <a href="{{watch_url}}" target="_blank" rel="noopener noreferrer">Open read-only spectator view</a>
    <input id="spectator-share-url" type="text" value="{{watch_url}}" readonly
      aria-label="Read-only spectator link" onclick="this.select()">
    <button type="button" onclick="navigator.clipboard.writeText(document.getElementById('spectator-share-url').value)">Copy link</button>
  </div>
</div>
{% endif %}
{% if not spectator %}
<h2 id="recruitment">Shortlist</h2>
<div class="card">
<p class="muted">Your saved targets are available throughout the window. Browse players in Scouting and save them from their profile.</p>
<h3 id="shortlist">My transfer shortlist</h3>
{% if shortlist %}
<div class="scout-table"><table><thead><tr><th>Player</th><th>Club</th><th>Position</th><th>Overall</th><th>Value</th></tr></thead>
<tbody>{% for p in shortlist %}
<tr><td><a href="/world/play/career/{{career_id}}/market/player/{{p.player_id}}">{{p.full_name}}</a></td>
<td>{{p.club_name|club_display}}</td><td>{{p.primary_position}}</td><td>{{p.overall}}</td>
<td>{{money(p.market_value) if p.market_value is not none else '—'}}</td></tr>
{% endfor %}</tbody></table></div>
{% else %}<p class="muted">No shortlisted players yet.</p>{% endif %}
</div>
<h2 id="scouting">Scouting &amp; squad values</h2>
<div class="card">

<form class="scout-filters" method="get" action="/world/play/career/{{career_id}}/market#scouting">
<label>Name<br><input name="scout_query" value="{{scout_query}}" placeholder="Search players"></label>
<label>Position<br><select name="scout_position">
<option value="">All positions</option>
{% for role in ['GK','DEF','MID','FWD'] %}<option value="{{role}}" {% if scout_position==role %}selected{% endif %}>{{role}}</option>{% endfor %}
</select></label>
<label>Min OVR<br><input name="scout_min_overall" type="number" min="1" max="99" value="{{scout_min_overall}}" style="width:80px"></label>
<label>Max age<br><input name="scout_max_age" type="number" min="16" max="65" value="{{scout_max_age}}" style="width:80px"></label>
<label>Category<br><select name="scout_category"><option value="">Any</option>
{% for cat in scout_categories %}<option value="{{cat}}" {% if scout_category==cat %}selected{% endif %}>{{cat|title}}</option>{% endfor %}</select></label>
<label>Min category<br><input type="number" name="scout_min_category" min="1" max="99" value="{{scout_min_category}}" style="width:80px"></label>
<label>Specific attribute<br><select name="scout_attribute"><option value="">Any</option>
{% for attr in scout_attributes %}<option value="{{attr}}" {% if scout_attribute==attr %}selected{% endif %}>{{attr|replace('_',' ')|title}}</option>{% endfor %}</select></label>
<label>Min attribute<br><input type="number" name="scout_min_attribute" min="1" max="99" value="{{scout_min_attribute}}" style="width:80px"></label>
<label>Contract<br><select name="scout_contract">
<option value="">All</option><option value="expiring" {% if scout_contract=='expiring' %}selected{% endif %}>Within 12 months</option>
<option value="known" {% if scout_contract=='known' %}selected{% endif %}>Verified expiry</option>
<option value="unknown" {% if scout_contract=='unknown' %}selected{% endif %}>Unknown</option>
</select></label>
<label><input type="checkbox" name="scout_squad" value="1" {% if scout_squad %}checked{% endif %}> My squad only</label>
<label>Sort by<br><select name="scout_sort">
{% for key in ['overall','age','market_value','pace','shooting','passing','dribbling','defending','physicality','years_left','full_name'] %}
<option value="{{key}}" {% if scout_sort==key %}selected{% endif %}>{{key|replace('_',' ')|title}}</option>{% endfor %}
</select></label>
<label>Order<br><select name="scout_order"><option value="desc" {% if scout_order=='desc' %}selected{% endif %}>Highest first</option>
<option value="asc" {% if scout_order=='asc' %}selected{% endif %}>Lowest first</option></select></label>
<label><input type="checkbox" name="scout_shortlist" value="1" {% if scout_shortlist %}checked{% endif %}> Shortlist only</label>
<button>Apply filters</button>
</form>
<div class="scout-table"><table>
<thead><tr><th>Player</th><th>Club</th><th>Pos</th><th>OVR</th><th>Age</th><th>Value</th>
<th>Contract</th><th>Years left</th><th>Pace</th><th>Shoot</th><th>Pass</th>
<th>Dribble</th><th>Defend</th><th>Physical</th>
{% if scout_attribute %}<th>{{scout_attribute|replace('_',' ')|title}}</th>{% endif %}</tr></thead>
<tbody>{% for p in scout_results %}
<tr class="{{'owned' if p.owned else ''}}">
<td><a href="/world/play/career/{{career_id}}/market/player/{{p.player_id}}">{{p.full_name}}</a>{% if p.shortlisted %} ★{% endif %}</td><td>{{p.club_name|club_display}}</td><td>{{p.primary_position or '—'}}</td>
<td><b>{{p.overall}}</b></td><td>{{p.age if p.age is not none else '—'}}</td>
<td>{{money(p.market_value) if p.market_value is not none else '—'}}</td>
<td>{{p.expires or 'Unknown'}}</td><td>{{p.years_left if p.years_left is not none else '—'}}</td>
<td>{{p.pace if p.pace is not none else '—'}}</td>
<td>{{p.shooting if p.shooting is not none else '—'}}</td>
<td>{{p.passing if p.passing is not none else '—'}}</td>
<td>{{p.dribbling if p.dribbling is not none else '—'}}</td>
<td>{{p.defending if p.defending is not none else '—'}}</td>
<td>{{p.physicality if p.physicality is not none else '—'}}</td>
{% if scout_attribute %}<td>{{p.detail_attribute if p.detail_attribute is not none else '—'}}</td>{% endif %}
</tr>{% endfor %}</tbody></table></div>
<p class="time-note">{{scout_results|length}} players</p>
</div>
{% endif %}
{% if snap.state!='not_started' %}
<h2 id="transfer-centre">Transfer Centre</h2>
<div class="desk-transfer-split">
 <section class="card desk-transfer-section">
  <h3><span class="desk-direction in" aria-label="Incoming transfers">↙</span>
   Incoming <span class="desk-section-count">{{purchases|length}}</span></h3>
  <div class="scout-table"><table data-desk-table="incoming">
  <thead><tr><th>Player</th><th>From</th><th data-sort-type="number">Fee</th><th>Status</th></tr></thead>
  <tbody>{% for o in purchases %}
  <tr><td><a href="/world/play/career/{{career_id}}/market/player/{{o.player_id}}">{{o.player_name}}</a></td>
   <td>{{o.seller_name|club_display}}</td><td data-sort-value="{{o.offered_fee}}">{{money(o.offered_fee)}}</td>
   <td><a href="#inbox">{{o.status_label}}</a></td></tr>
  {% endfor %}</tbody></table></div>
  {% if not purchases %}<p class="muted">No incoming bids</p>{% endif %}
 </section>
 <section class="card desk-transfer-section">
  <h3><span class="desk-direction out" aria-label="Outgoing transfers">↗</span>
   Outgoing <span class="desk-section-count">{{offers|length}}</span></h3>
  <div class="scout-table"><table data-desk-table="outgoing">
  <thead><tr><th>Player</th><th>To</th><th data-sort-type="number">Fee</th><th>Status</th></tr></thead>
  <tbody>{% for o in offers %}
  <tr><td>{{o.player_name}}</td><td>{{o.buyer_name|club_display}}</td>
   <td data-sort-value="{{o.offered_fee}}">{{money(o.offered_fee)}}</td>
   <td><a href="#inbox">{{o.status_label}}</a></td></tr>
  {% endfor %}</tbody></table></div>
  {% if not offers %}<p class="muted">No outgoing bids</p>{% endif %}
 </section>
</div>
<h2 id="purchases">Outgoing bids — negotiations</h2>
{% if purchases %}
<div class="grid">{% for o in purchases %}
<div class="card offer">
<div class="label">Buying from {{o.seller_name|club_display}} · {{o.status_label}}</div>
<h3 style="margin:6px 0"><a href="/world/play/career/{{career_id}}/market/player/{{o.player_id}}" class="desk-player-profile">{{o.player_name}}</a></h3>
<div class="count">{{money(o.offered_fee)}}</div>
{% if o.demanded_fee is not none %}
<p class="muted">Seller's counter: {{money(o.demanded_fee)}}</p>{% endif %}
{% if o.agent_demand is not none and o.status=='accepted_pending_contract' %}
<p class="agent-opening-quote">Agent opening request: <strong>{{money(o.agent_demand)}}/week</strong></p>{% endif %}
{% if o.agent_status=='accepted' %}
<p class="muted">Player and agent have agreed personal terms.</p>{% endif %}
{% if not spectator and snap.state=='open' %}
<div class="actions">
{% if o.status=='countered' %}
<form method="post" action="/world/play/career/{{career_id}}/market/buy/decision">
<input type="hidden" name="csrf" value="{{csrf}}">
<input type="hidden" name="offer_id" value="{{o.offer_id}}">
<button name="decision" value="accept_counter">Accept seller's counter</button>
</form>
<form method="post" action="/world/play/career/{{career_id}}/market/buy/decision">
<input type="hidden" name="csrf" value="{{csrf}}">
<input type="hidden" name="offer_id" value="{{o.offer_id}}">
<label>Revised offer (£)<br><input type="number" name="negotiated_fee"
 min="{{o.offered_fee+1}}" max="{{o.demanded_fee-1}}"
 value="{{((o.offered_fee+o.demanded_fee)//2)}}" required></label>
<button name="decision" value="negotiate_counter">Negotiate fee</button>
</form>
{% elif o.status=='accepted_pending_contract' and o.agent_status=='accepted' %}
<form method="post" action="/world/play/career/{{career_id}}/market/buy/decision">
<input type="hidden" name="csrf" value="{{csrf}}">
<input type="hidden" name="offer_id" value="{{o.offer_id}}">
<button name="decision" value="sign">Sign transfer</button></form>
{% elif o.status=='accepted_pending_contract' and o.agent_demand is none %}
<form method="post" action="/world/play/career/{{career_id}}/market/buy/decision">
<input type="hidden" name="csrf" value="{{csrf}}">
<input type="hidden" name="offer_id" value="{{o.offer_id}}">
<button name="decision" value="request_agent">Request agent's opening wage</button>
</form>
{% elif o.status=='accepted_pending_contract' %}
<form method="post" action="/world/play/career/{{career_id}}/market/buy/decision">
<input type="hidden" name="csrf" value="{{csrf}}">
<input type="hidden" name="offer_id" value="{{o.offer_id}}">
<label>Weekly wage (£)<br><input type="number" name="weekly_wage" min="0"
max="1000000" step="1" value="{{o.agent_demand}}" required></label>
<label>Contract<br><select name="contract_years">
<option value="3" selected>3 years</option><option value="4">4 years</option>
<option value="2">2 years</option><option value="5">5 years</option>
<option value="1">1 year</option></select></label>
<label>Squad role<br><select name="role_promise">
<option value="regular_starter">Regular Starter</option>
<option value="key_player">Key Player</option>
<option value="rotation">Rotation</option>
<option value="fringe">Fringe</option></select></label>
<button name="decision" value="terms">Offer player terms</button>
</form>
{% endif %}
{% if o.status in ('rejected','withdrawn') %}
<form method="post" class="desk-rebid-form" action="/world/play/career/{{career_id}}/market/buy/rebid">
<input type="hidden" name="csrf" value="{{csrf}}">
<input type="hidden" name="offer_id" value="{{o.offer_id}}">
<label>New offer (£)<input name="offered_fee" type="number" min="{{o.offered_fee+1}}" step="1"
 value="{{(o.offered_fee*110//100)+1}}" required></label>
<button type="submit">Make new offer</button>
</form>
{% endif %}
{% if o.status in ('proposed','countered','accepted_pending_contract') %}
<form method="post" action="/world/play/career/{{career_id}}/market/buy/decision">
<input type="hidden" name="csrf" value="{{csrf}}">
<input type="hidden" name="offer_id" value="{{o.offer_id}}">
<button name="decision" value="withdraw" class="danger">Withdraw bid</button></form>
{% endif %}
</div>{% endif %}
</div>{% endfor %}</div>
{% else %}<div class="card"><p>No active approaches. Find players in Scouting.</p></div>{% endif %}
{% endif %}
<h2 id="inbox">Manager's Inbox</h2>
{% if not spectator and unread>0 %}
<form method="post" action="/world/play/career/{{career_id}}/market/read">
<input type="hidden" name="csrf" value="{{csrf}}">
<button>Mark inbox news as read</button>
</form>{% endif %}
{% if offers %}
<div class="grid">{% for o in offers %}
<div class="card offer" data-desk-player="{{o.player_id}}" data-desk-player-name="{{o.player_name}}"
 data-desk-status="{{o.status}}" data-desk-agent="{{o.player_status or ''}}"
 data-desk-buyer="{{o.buyer_name|club_display}}">
 <div class="label">{{o.buyer_name|club_display}} · {{o.status_label}}</div>
 <h3 style="margin:6px 0"><button type="button" class="desk-player-quickfilter"
 data-desk-filter-player="{{o.player_name}}" title="Filter offers for {{o.player_name}}">{{o.player_name}}</button></h3>
 <div class="count">{{money(o.offered_fee)}}</div>
 {% if o.market_value is not none and o.market_value>0 %}
 <p class="muted" style="margin:5px 0">Indicative market value: <b>{{money(o.market_value)}}</b></p>
 <p class="muted" style="margin:5px 0">
 Bid versus valuation:
 <b>{{'+' if o.value_difference>=0 else '−'}}{{money(o.value_difference|abs)}}</b>
 (<b>{{'+' if o.value_difference_pct>=0 else '−'}}{{'%.1f'|format(o.value_difference_pct|abs)}}%</b>)
 {{'above' if o.value_difference>=0 else 'below'}} the modelled value.
 </p>
 {% else %}<p class="muted">Indicative market value unavailable.</p>{% endif %}
 {% if o.demanded_fee is not none %}
 <p class="muted">Your counter: {{money(o.demanded_fee)}}</p>{% endif %}
 {% if o.competing_offers and o.status=='accepted_pending_contract' %}
 <p class="alert"><b>{{o.competing_offers}} competing agreed-fee offer(s).</b>
 Player and agent must reconsider before any signature; the deal may be delayed.</p>{% endif %}
 {% if o.player_status %}<p class="muted">Player/agent: {{o.player_status|replace('_',' ')|title}}</p>
 {% if o.player_reason %}<small>{{o.player_reason}}</small>{% endif %}{% endif %}
 {% if not spectator and snap.state=='open' %}
 <div class="actions">
 {% if o.status=='proposed' %}
 <form method="post" action="/world/play/career/{{career_id}}/market/decision">
 <input type="hidden" name="csrf" value="{{csrf}}">
 <input type="hidden" name="offer_id" value="{{o.offer_id}}">
 <button name="decision" value="accept">Accept fee</button>
 <button name="decision" value="reject" class="danger">Reject</button>
 </form>
 <form method="post" action="/world/play/career/{{career_id}}/market/decision">
 <input type="hidden" name="csrf" value="{{csrf}}">
 <input type="hidden" name="offer_id" value="{{o.offer_id}}">
 <label>Asking fee (£)<br><input type="number" name="counter_fee"
 value="{{(o.offered_fee*11//10) if o.offered_fee>=10 else (o.offered_fee+1)}}"
 min="{{o.offered_fee+1}}" max="{{[o.offered_fee*2,1000000000]|min}}"
 step="1" required></label>
 <button name="decision" value="counter">Counter</button></form>
 {% elif o.status=='accepted_pending_contract' and o.player_status=='terms_accepted' %}
 <div class="buyer-decision" style="width:100%">
 {% if o.confirmation %}
 <p class="time-note" style="margin:7px 0">
 <b>{{o.buyer_name|club_display}} needs your decision in
 <span class="buyer-decision-clock" data-deadline="{{o.confirmation.deadline_at}}">--:--</span></b>.
 The buying club can withdraw when this timer expires.</p>
 {% if o.confirmation.extension_requested %}
 <p class="muted">{{'Extra time granted (one request used)' if o.confirmation.extension_granted
                  else 'Extra time refused — original deadline remains (one request used)'}}.</p>
 {% endif %}
 {% else %}
 <p class="time-note">The buyer's finalisation timer will start when accepted agent terms are recorded.</p>
 {% endif %}
 <form method="post" action="/world/play/career/{{career_id}}/market/decision">
 <input type="hidden" name="csrf" value="{{csrf}}">
 <input type="hidden" name="offer_id" value="{{o.offer_id}}">
 <button name="decision" value="finalise">Finalise transfer</button>
 {% if o.confirmation and not o.confirmation.extension_requested and o.confirmation.deadline_at!=snap.deadline_at %}
 <button name="decision" value="delay" type="submit">Request more time (+2 min)</button>
 {% endif %}
 </form></div>
 {% endif %}
 {% if o.status in ('proposed','countered','accepted_pending_contract') %}
 <form method="post" action="/world/play/career/{{career_id}}/market/decision">
 <input type="hidden" name="csrf" value="{{csrf}}">
 <input type="hidden" name="offer_id" value="{{o.offer_id}}">
 <button name="decision" value="cancel" class="danger">Cancel transfer</button></form>
 {% endif %}
 </div>{% endif %}
</div>{% endfor %}</div>
{% else %}<div class="card"><p>No offers have arrived yet. The world is evaluating its squads;
a quiet market is possible. No transfers will be invented to fill the inbox.</p></div>{% endif %}
{% if snap.state=='closed' %}
<h2 id="window-summary">Final transfer window report</h2>
<div class="card desk-post-window-next">
<strong>Transfer window complete</strong>
<a href="#season-setup" data-desk-tab="season-setup">Continue to season setup →</a>
</div>
<div class="card">

<div class="rail">
<span class="pill">Arrivals: <b>{{summary.arrivals}}</b></span>
<span class="pill">Departures: <b>{{summary.departures}}</b></span>
<span class="pill">Fees spent: <b>{{money(summary.spent)}}</b></span>
<span class="pill">Fees received: <b>{{money(summary.received)}}</b></span>
<span class="pill">Net spend: <b>{{money(summary.spent-summary.received)}}</b></span>
</div>
<p>Remaining transfer budget: <b>{{money(funds)}}</b>
 · Remaining modelled weekly wage budget: <b>{{money(wage_headroom)}}</b></p>
{% if summary.deals %}
<table><thead><tr><th>Movement</th><th>Player</th><th>Club</th><th>Fee</th><th>Weekly wage</th></tr></thead>
<tbody>{% for deal in summary.deals %}
<tr><td>{{deal.direction}}</td><td>{{deal.player}}</td>
<td>{{deal.other_club|club_display}}</td><td>{{money(deal.fee)}}</td>
<td>{{money(deal.wage)}}</td></tr>
{% endfor %}</tbody></table>
{% else %}<p>No transfers registered before the deadline.</p>{% endif %}
<h3>Transfers between other clubs: {{summary.world_deals|length}}</h3>
{% if summary.world_deals %}
<div class="scout-table desk-market-table">
<table data-desk-table="world-deals"><thead><tr><th>Player</th><th>From</th><th>To</th><th data-sort-type="number">Fee</th></tr></thead>
<tbody>{% for deal in summary.world_deals %}
<tr><td>{{deal.player}}</td><td>{{deal.seller}}</td>
<td>{{deal.buyer}}</td><td data-sort-value="{{deal.fee}}">{{money(deal.fee)}}</td></tr>
{% endfor %}</tbody></table></div>
{% else %}<p class="muted">No AI-to-AI transfers registered during this window.</p>{% endif %}
{% if season_exclusions %}
<h3>PES-season exclusions · Refused to play</h3>
<div class="scout-table"><table data-desk-table="unavailable">
<thead><tr><th>Player</th><th>Club</th><th>Eligibility</th></tr></thead>
<tbody>{% for person in season_exclusions %}
<tr><td>{{person.player_name}}</td><td>{{person.club_name|club_display}}</td>
<td>Unavailable for the coming season</td></tr>
{% endfor %}</tbody></table></div>
{% endif %}
<p class="muted">{{summary.rejected}} rejected offers;
{{summary.expired}} negotiations expired at the deadline;
{{summary.other_withdrawn}} other withdrawn negotiations.
Rejected and expired offers are not transfers.</p>

</div>
<h2 id="season-setup">Season setup</h2>
<div class="card desk-setup-card">
{% if season_tasks.completed %}
<h3 class="desk-setup-done">Ready for the new season</h3>
{% else %}
<p><strong>Prepare your PES squads</strong> <span class="muted">· {{season_tasks.steps.values()|select|list|length}} of 3 complete</span></p>
{% endif %}
{% for step,label in [
('review','Review the final transfer report'),
('apply_pes','Apply confirmed moves in PES'),
('verify_squads','Check both squads match the report')
] %}
<form class="desk-setup-step" method="post" action="/world/play/career/{{career_id}}/market/season/step">
<input type="hidden" name="csrf" value="{{csrf}}">
<input type="hidden" name="step" value="{{step}}">
<input type="hidden" name="done" value="{{'0' if season_tasks.steps.get(step) else '1'}}">
<button type="submit" aria-label="{{'Mark incomplete' if season_tasks.steps.get(step) else 'Mark complete'}}: {{label}}">
<span class="desk-setup-check" aria-hidden="true">{{'✓' if season_tasks.steps.get(step) else '○'}}</span>
<span>{{label}}</span></button>
</form>
{% endfor %}
{% if season_exclusions %}
<h3>Remove from eligible PES squads</h3>
<div class="scout-table"><table><thead><tr><th>Player</th><th>Club</th></tr></thead>
<tbody>{% for person in season_exclusions %}
<tr><td>{{person.player_name}}</td><td>{{person.club_name|club_display}}</td></tr>
{% endfor %}</tbody></table></div>
{% endif %}
{% if summary.deals %}
<h3>Moves to apply</h3>
<div class="scout-table"><table><thead><tr><th>Action</th><th>Player</th><th>Club</th></tr></thead><tbody>
{% for deal in summary.deals %}
<tr><td>{{'Add to squad' if deal.direction=='In' else 'Remove from squad'}}</td>
<td>{{deal.player}}</td><td>{{deal.other_club|club_display}}</td></tr>
{% endfor %}</tbody></table></div>
{% else %}<p class="muted">No changes to your squad this window.</p>{% endif %}
{% if season_tasks.completed %}
<p class="muted">Your PES setup has been marked complete. The app's career registrations are already final.</p>
{% endif %}
<p><a href="#window-summary" data-desk-tab="transfers">View final transfer report</a></p>
</div>
{% endif %}
<h2>Market news</h2>
{% if messages %}
<div class="feed">
{% for m in messages %}
<div class="card"><b>{{m.headline}}</b>
<p style="margin:5px 0">{{m.detail}}</p>
<small>{{m.created_at}} UTC{% if m.is_read==0 %} · New{% endif %}</small>
</div>{% endfor %}</div>
{% else %}<div class="card">No news yet.</div>{% endif %}
<p class="desk-provenance">Career market values, wages and player preferences are simulated.</p>
{% endif %}
 </div>
</div>
</main>
<script>
(function(){
 const panel=document.getElementById('budget-panel');
 if(panel){
   const money=(v)=>{const sign=v<0?'-':'';v=Math.abs(v);
     return sign+'£'+(v>=1e6?(v/1e6).toFixed(2)+'m':v>=1e3?
       Math.round(v/1e3)+'k':Math.round(v).toLocaleString('en-GB'));};
   const feeBase=Number(panel.dataset.feeRemaining), wageBase=Number(panel.dataset.wageRemaining);
   const feeTotal=Math.max(1,Number(panel.dataset.feeTotal));
   const wageTotal=Math.max(1,Number(panel.dataset.wageTotal));
   function repaint(selector,base,total,currentId,barId,previewId,label){
     const inp=document.querySelector(selector), entered=inp?Math.max(0,Number(inp.value)||0):0;
     const left=base-entered;
     document.getElementById(currentId).textContent=money(base);
     const bar=document.getElementById(barId);
     bar.style.width=Math.max(0,Math.min(100,100*left/total))+'%';
     bar.classList.toggle('warning',left<0 || left/total<.2);
     const desc=document.getElementById(previewId);
     desc.textContent=inp&&inp.value?('After proposed '+label+': '+money(left)+
       (left<0?' — exceeds available budget':'')):
       ('Available '+label+': '+money(base));
   }
   function updateBudgets(){
     repaint('[data-budget-fee]',feeBase,feeTotal,'fee-current','fee-bar','fee-preview','transfer funds');
     repaint('[data-budget-wage]',wageBase,wageTotal,'wage-current','wage-bar','wage-preview','weekly wage headroom');
   }
   document.querySelectorAll('[data-budget-fee],[data-budget-wage]').forEach(
     inp=>inp.addEventListener('input',updateBudgets));
   updateBudgets();
 }
 const decisionClocks=document.querySelectorAll('.buyer-decision-clock');
 if(decisionClocks.length){
   function tickDecisionClocks(){
     decisionClocks.forEach(function(el){
       const deadline=Date.parse(el.dataset.deadline);
       const remaining=Math.max(0,Math.ceil((deadline-Date.now())/1000));
       const minutes=String(Math.floor(remaining/60)).padStart(2,'0');
       const seconds=String(remaining%60).padStart(2,'0');
       el.textContent=minutes+':'+seconds+(remaining===0?' — time expired':'');
     });
   }
   tickDecisionClocks();setInterval(tickDecisionClocks,1000);
 }
 const clock=document.getElementById('window-clock');
 if(clock){
  const deadline=Date.parse(clock.dataset.deadline);
  function update(){
    const remaining=Math.max(0,Math.ceil((deadline-Date.now())/1000));
    const minutes=String(Math.floor(remaining/60)).padStart(2,'0');
    const seconds=String(remaining%60).padStart(2,'0');
    clock.textContent=minutes+':'+seconds;
  }
  update();setInterval(update,1000);
  if(document.body.dataset.windowState==='open'){
   setInterval(function(){
     const active=document.activeElement;
     if(active && active.matches('input,textarea,select'))return;
     location.reload();
   },15000);
  }
 }
})();
</script></body></html>"""

# Keep the transfer engine and all existing forms server-rendered.
# The presentation layer moves these elements between client-side tabs.
from world_career_ui import DASHBOARD_CSS,DASHBOARD_JS
LIVE_MARKET_PAGE = LIVE_MARKET_PAGE.replace(
    "</style></head>",DASHBOARD_CSS+"</style></head>"
).replace("</script></body></html>",DASHBOARD_JS+"</script></body></html>")

SCOUT_PLAYER_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{{player.full_name}} | Scout report</title>
<style>body{background:#101a27;color:#ecf5ff;font:15px/1.5 system-ui;margin:0}
main{max-width:880px;margin:25px auto;padding:0 20px}a{color:#b8dbff}
.card{background:#1d3044;border:1px solid #3c5c78;border-radius:12px;padding:18px;margin:15px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.muted{color:#bed0e1}b{font-size:18px}button{background:#3276a7;border:0;border-radius:7px;padding:10px 16px;color:white;cursor:pointer}
table{width:100%;border-collapse:collapse}td{padding:8px;border-bottom:1px solid #3c5c78}</style></head><body><main>
<a href="/world/play/career/{{career_id}}/market#recruitment">← Recruitment centre &amp; shortlist</a>
<h1>{{player.full_name}}</h1><p class="muted">{{player.club_name|club_display}} · {{player.primary_position or 'Unknown position'}} ·
Age {{player.age if player.age is not none else 'unknown'}}</p>
<div class="grid">
<div class="card">Overall<br><b>{{player.overall}}</b></div>
<div class="card">Indicative market value<br><b>{{money(player.market_value) if player.market_value is not none else 'Unknown'}}</b></div>
<div class="card">Estimated weekly wage expectation<br><b>{{money(player.wage_guidance)}}/week</b></div>
<div class="card">Contract expires<br><b>{{player.expires or 'Unknown'}}</b>
<p class="muted">Years remaining: {{player.years_left if player.years_left is not none else 'Unknown'}}</p></div>
</div>
<p class="muted">Transfer valuation and wage expectation are fictional game-model estimates, not actual demands.
Contract dates appear only where sourced.</p>
<form method="post" action="/world/play/career/{{career_id}}/market/shortlist">
<input type="hidden" name="csrf" value="{{csrf}}">
<input type="hidden" name="player_id" value="{{player.player_id}}">
<button name="action" value="{{'remove' if player.shortlisted else 'save'}}">
{{'Remove from shortlist' if player.shortlisted else 'Add to shortlist'}}</button></form>
{% if not player.owned %}
<h2>Approach to buy</h2>
<div class="card">
{% if market_open %}
<p class="muted">Bid directly for this player. The selling club, player and agent make their own decisions. The indicative value is not a guaranteed asking price.</p>
<form method="post" action="/world/play/career/{{career_id}}/market/buy" id="scout-buy">
<input type="hidden" name="csrf" value="{{csrf}}">
<input type="hidden" name="request_key" value="{{request_key}}">
<input type="hidden" name="player_id" value="{{player.player_id}}">
<label for="scout-fee">Your proposed transfer fee (£)</label>
<input id="scout-fee" name="offered_fee" type="number" min="1" max="1000000000" step="1"
value="{{player.market_value if player.market_value is not none else ''}}" required>
<p id="scout-budget-preview">Available transfer budget: {{money(funds)}}</p>
<button type="submit">Submit transfer offer</button>
</form>
<script>
(function(){
 const input=document.getElementById('scout-fee');
 const label=document.getElementById('scout-budget-preview');
 const funds={{funds}};
 function fmt(v){const sign=v<0?'-':'';v=Math.abs(v);
   return sign+'£'+(v>=1e6?(v/1e6).toFixed(2)+'m':v>=1e3?Math.round(v/1e3)+'k':Math.round(v));}
 function refresh(){const fee=Math.max(0,Number(input.value)||0);
   const remaining=funds-fee;
   label.textContent='After this proposed bid: '+fmt(remaining)+
     (remaining<0?' — exceeds your remaining budget':'');}
 input.addEventListener('input',refresh);refresh();
})();
</script>
{% else %}<p class="muted">The 30-minute market must be open before you can make a transfer offer. You can still shortlist the player.</p>{% endif %}
</div>
{% endif %}
<h2>Category ratings</h2><div class="grid">
{% for field in ['pace','shooting','passing','dribbling','defending','physicality'] %}
<div class="card">{{field|title}}<br><b>{{player[field] if player[field] is not none else '—'}}</b></div>
{% endfor %}</div>
<h2>Individual attributes</h2><div class="card">
{% if player.attributes %}<table>{% for item in player.attributes %}
<tr><td>{{item.name|replace('_',' ')|title}}</td><td><b>{{item.value}}</b></td></tr>
{% endfor %}</table>{% else %}<p class="muted">No source-backed individual attributes currently available.</p>{% endif %}
</div></main></body></html>"""

CAREER_MANAGEMENT_PAGE = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Career Management</title><style>
body{background:#111a25;color:#e9f4ff;font:15px system-ui;margin:0;line-height:1.5}
header{padding:16px 24px;background:#203043}main{max-width:1020px;margin:25px auto;padding:0 20px 80px}
a{color:#a8d1fc}.muted{color:#b8c9db}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}
.card{background:#1d3044;border:1px solid #456074;border-radius:9px;padding:16px;margin:15px 0}
input,select,button{padding:10px;width:100%;box-sizing:border-box;background:#29445b;color:white;border:1px solid #698099;border-radius:6px}
button{cursor:pointer;background:#315d83}label{display:block;color:#c5d7e4;margin:8px 0 5px}h2{margin-top:27px}
table{width:100%;border-collapse:collapse}td,th{padding:10px;text-align:left;border-bottom:1px solid #405267}
</style></head><body><header><a href="/world/play/career/{{career_id}}">← Career desk</a></header>
<main><h1>Career Management</h1><p class="muted">{{club_name|club_display}} · {{career_id}}</p>
<div class="card">Development career only. Existing career-budget assumptions are reused.
Unknown wages and contract expiries stay unknown. No PES registration or transfer is changed.</div>
<div class="grid">
<div class="card"><b>Remaining transfer funds</b><h2>£{{'{:,}'.format(snapshot.finances.available_transfer_budget)}}</h2></div>
<div class="card"><b>Weekly wage headroom</b><h2>£{{'{:,}'.format(snapshot.finances.weekly_wages.remaining)}}</h2></div>
<div class="card"><b>Board confidence</b><h2>{{snapshot.board.manager_confidence if snapshot.board.manager_confidence is not none else "Unknown"}}</h2>
<p class="muted">{{snapshot.board.confidence_source}}</p></div></div>
<h2>Buying board — transfer policy</h2>
<div class="card">
<p>Your saved manager confidence automatically influences board approval once this
policy is configured. Fee approval happens before submitting or accepting a bid;
wage/contract approval happens before confirming a future deal. Existing saves
with no policy retain the old sandbox behaviour.</p>
{% if buying_policy %}<p><b>Board policy active:</b> maximum fee {{buying_policy.max_fee_pct}}%
of the scenario valuation, maximum new weekly wages {{buying_policy.max_headroom_use_pct}}%
of available weekly wage headroom.</p>
<p class="muted">Financial priority: {{buying_policy.financial_objective}},
ambition: {{buying_policy.ambition}}, ownership: {{buying_policy.ownership_priority}}.
Board confidence changes can alter these ceilings automatically.</p>
{% else %}
<form method="post" action="/world/play/career/{{career_id}}/management/buying-board">
<input type="hidden" name="csrf" value="{{csrf}}">
<div class="grid">
<div><label>Maximum fee (% of fictional model valuation)</label>
<input name="max_fee_pct" type="number" min="0" max="1000" placeholder="e.g. 180" required></div>
<div><label>Maximum share of available weekly wages (%)</label>
<input name="max_headroom_use_pct" type="number" min="0" max="1000" placeholder="e.g. 70" required></div>
<div><label>Financial priority</label><select name="financial_objective">
<option value="growth">Growth</option><option value="balanced" selected>Balanced</option>
<option value="cost_control">Cost control</option><option value="cash_generation">Cash generation</option>
</select></div>
<div><label>Ambition</label><select name="ambition">
<option value="survival">Survival</option><option value="consolidation" selected>Consolidation</option>
<option value="promotion">Promotion</option><option value="continental">Continental football</option>
</select></div>
<div><label>Ownership priority</label><select name="ownership_priority">
<option value="sporting">Sporting success</option><option value="balanced" selected>Balanced</option>
<option value="return_on_investment">Investment returns</option>
</select></div>
<div><label>Policy assumptions note</label>
<input name="source_note" required placeholder="Fictional career ownership policy"></div>
</div><button>Lock buying board policy</button></form>
{% endif %}
<p class="muted">No policy or manager-confidence score is inferred from the real club.
Contract and transfer decisions remain subject to player and agent consent.</p>
</div>
<h2>Pre-season board expectations — based on squad strength</h2>
<div class="card">
<p><b>Objective baseline calculated from the actual career dataset.</b>
Each club is ranked by its mean rating across the best 16 rated players, with
a minimum of eight rated players for every club. This is a <b>relative squad-strength
ranking</b>, not a guaranteed finishing position or a historical season result.</p>
{% if strength_baseline.available %}
<p><b>{{club_name|club_display}}: {{strength_baseline.rank}} of {{strength_baseline.league_size}}</b>
— suggested objective range {{strength_baseline.band[0]}}–{{strength_baseline.band[1]}}.
{% if strength_baseline.expected_relegation is not none %}
Expected relegation risk based on squad rank:
{{"yes" if strength_baseline.expected_relegation else "no"}}.{% endif %}</p>
<p class="muted">Source: {{strength_baseline.dataset_id}} ·
{{strength_baseline.source_date}} · {{strength_baseline.underlying_strength_version}}.
{{strength_baseline.note}}</p>
<div class="card">
<p><b>Financial capability and ambition matter too.</b> The displayed £ amounts
are from the game's provisional career economy, not real club financial accounts.
The board can give you an explicit improvement mandate; this stretches
expectations even if you choose not to recruit. A manager meeting the targets
without spending isn't punished for good management.</p>
<p>Career transfer funds available: <b>£{{'{:,}'.format(resource_capacity.unreserved)}}</b>
· Division median transfer budget:
<b>£{{'{:,}'.format(resource_capacity.median_peer_budget)}}</b>.</p>
<p class="muted">{{resource_capacity.note}}</p>
<form method="post" action="/world/play/career/{{career_id}}/management/objective/auto">
<input type="hidden" name="csrf" value="{{csrf}}">
<div class="grid">
<div><label>Season to lock</label>
<input name="season_key" maxlength="32" required placeholder="2026-27"></div>
<div><label>Board ambition</label><select name="ambition">
<option value="survival">Survival</option>
<option value="consolidation" selected>Consolidation</option>
{% if strength_baseline.competition_id!='ENG1' %}
<option value="promotion">Challenge for promotion</option>{% endif %}
{% if strength_baseline.competition_id=='ENG1' %}
<option value="continental">Challenge for European places</option>{% endif %}
</select></div>
<div><label>Recruitment investment mandate</label><select name="investment_mandate">
<option value="none">None — no spending expected</option>
<option value="optional">Optional — spend only if value found</option>
<option value="expected">Expected — improve with resources</option>
<option value="required">Required — board has funded improvements</option>
</select></div>
<div><label>Board allocation for squad improvement (£)</label>
<input name="investment_pool" type="number" min="0"
max="{{resource_capacity.unreserved}}" step="100000" value="0" required></div>
</div><label>Board decision and evidence</label>
<input name="commitment_note" required value="Explicit fictional pre-season ambition and spending mandate">
<p><button type="submit">Lock squad strength + financial expectations</button></p>
</form>
<p class="muted">The target can rise by up to four places versus squad-only expectations.
If a required allocation is substantially unused and results fall short,
board confidence faces an additional small penalty. Money spent on ineffective
players doesn't automatically count as success.</p>
</div>
<details><summary>See complete relative league squad ranking</summary>
<table><tr><th>Strength rank</th><th>Club</th><th>Top-rated squad mean</th><th>Rated players</th></tr>
{% for team in strength_baseline.clubs %}
<tr><td>{{team.rank}}</td><td>{{team.name|club_display}}{% if team.club_id==strength_baseline.club_id %} (you){% endif %}</td>
<td>{{team.strength}}</td><td>{{team.sample_players}}</td></tr>{% endfor %}
</table></details>
{% else %}
<p><b>Automatically calculated expectations unavailable.</b>
{{strength_baseline.reason}}</p>
{% if strength_baseline.missing_clubs %}
<p class="muted">Missing enough sourced ratings for:
{{strength_baseline.missing_clubs|join(", ")}}</p>{% endif %}
{% endif %}
</div>
<details><summary>Optional manual objectives for unsupported or exceptional circumstances</summary>
<div class="card"><p><b>Manual scenario overrides are labelled as assumptions</b>,
and cannot be recorded as an automated squad-strength result. Use only when
you can explain an exceptional change in circumstances.</p>
<form method="post" action="/world/play/career/{{career_id}}/management/objective">
<input type="hidden" name="csrf" value="{{csrf}}">
<div class="grid">
<div><label>Season key</label><input name="season_key" maxlength="32" required placeholder="2026-27"></div>
<div><label>Assumed expected finish (rank)</label><input type="number" name="expected_rank" min="1" max="30" required></div>
<div><label>Division size</label><input type="number" name="league_size" min="10" max="30" required value="{{strength_baseline.league_size}}"></div>
<div><label>Relegation expected?</label><select name="expected_relegation">
<option value="unknown">Unknown</option><option value="yes">Yes</option><option value="no">No</option></select></div>
<div><label>Scenario reason/evidence</label><input name="source_note" required placeholder="Squad sold several starters after snapshot"></div>
</div><input type="hidden" name="strength_source" value="user_sandbox_assumption">
<button>Lock explicitly assumed alternative objective</button></form></div>
</details>
<h2>Confirmed season review</h2>
<div class="card"><p>Use only a completed, verified career season. This applies a single
expectation-relative confidence adjustment and cannot be repeated or edited silently.
Promotion/relegation is treated contextually, not as a separate +20/−22 award.</p>
<form method="post" action="/world/play/career/{{career_id}}/management/review">
<input type="hidden" name="csrf" value="{{csrf}}">
<div class="grid">
<div><label>Locked season key</label><select name="season_key">
{% for o in objective_history %}{% if o.actual_rank is none %}<option value="{{o.season_key}}">{{o.season_key}} (expected {{o.expected_rank}})</option>{% endif %}{% endfor %}
</select></div>
<div><label>Verified final league position</label><input type="number" name="actual_rank" min="1" max="30" required></div>
<div><label>Promoted?</label><select name="promoted"><option value="no">No</option><option value="yes">Yes</option></select></div>
<div><label>Relegated?</label><select name="relegated"><option value="no">No</option><option value="yes">Yes</option></select></div>
<div><label>Cup result relative to expectations</label><select name="cup_result">
<option value="not_assessed">Not assessed</option><option value="expected">As expected</option>
<option value="above">Above expectations</option><option value="below">Below expectations</option></select></div>
<div><label>Confirmed result/evidence note</label><input name="result_note" required placeholder="Final table / archived season record"></div>
</div><button>Apply completed-season review</button></form></div>
<h2>Locked objectives and historical reviews</h2><div class="card"><table>
<tr><th>Season</th><th>Strength</th><th>Board target</th><th>Actual</th>
<th>Investment mandate</th><th>Confidence</th></tr>
{% for o in objective_history %}<tr><td>{{o.season_key}}</td>
<td>{{o.strength_rank if o.strength_rank is not none else 'Manual'}}</td>
<td>{{o.expected_rank}} / {{o.league_size}}
{% if o.ambition %}<small>{{o.ambition|replace('_',' ')|title}}</small>{% endif %}</td>
<td>{{o.actual_rank if o.actual_rank is not none else "Awaiting results"}}</td>
<td>{% if o.investment_pool is not none %}
{{o.investment_mandate|title}} · £{{'{:,}'.format(o.investment_pool)}}
{% if o.reported_investment is not none %}<small>Confirmed spent: £{{'{:,}'.format(o.reported_investment)}}</small>{% endif %}
{% else %}Not assessed{% endif %}</td>
<td>{{o.confidence_delta if o.confidence_delta is not none else "—"}}
{% if o.resource_confidence_delta %}<small>(including {{o.resource_confidence_delta}} unused funds)</small>{% endif %}</td></tr>
{% else %}<tr><td colspan="6">No objectives locked yet.</td></tr>{% endfor %}
</table></div>
<h2>Recorded player contracts</h2><div class="card"><table><tr><th>Player</th><th>Wage/week</th><th>Expires</th><th>Role</th><th>Provenance</th></tr>
{% for c in snapshot.contracts %}<tr><td>{{c.player_id}}</td>
<td>{% if c.wage_weekly is not none %}£{{'{:,}'.format(c.wage_weekly)}}{% else %}Unknown{% endif %}</td>
<td>{{c.end_date or "Unknown"}}</td><td>{{c.squad_role or "Unknown"}}</td><td>{{c.source_kind}}</td></tr>
{% else %}<tr><td colspan="5">No player contracts recorded.</td></tr>{% endfor %}
</table></div>
<h2>Establish initial board confidence</h2><div class="card">
<p>Enter an explicit scenario starting point once. Subsequent changes require confirmed career events.</p>
<form method="post" action="/world/play/career/{{career_id}}/management/confidence">
<input type="hidden" name="csrf" value="{{csrf}}"><label>Manager confidence (0–100)</label>
<input name="value" type="number" min="0" max="100" required><button>Set starting confidence</button></form></div>
<h2>Record confirmed career event</h2><div class="card">
<form method="post" action="/world/play/career/{{career_id}}/management/event">
<input type="hidden" name="csrf" value="{{csrf}}">
<div class="grid"><div><label>Unique event key</label><input name="event_key" required placeholder="season-1-promotion"></div>
<div><label>Event</label><select name="event_type">{% for event in board_events %}
<option value="{{event}}">{{event|replace('_',' ')|title}}</option>{% endfor %}</select></div>
<div><label>Actual event date</label><input type="date" name="event_date" required></div>
<div><label>Confirmation/evidence</label><input name="source_note" required placeholder="Verified in career results"></div></div>
<button>Record confirmed event</button></form></div>
<h2>Record current player contract</h2><div class="card">
<p>Only currently registered players are available. Blank means unknown. Existing records cannot be overwritten.</p>
<form method="post" action="/world/play/career/{{career_id}}/management/contract">
<input type="hidden" name="csrf" value="{{csrf}}">
<div class="grid"><div><label>Player</label><select name="player_id">
{% for p in players %}<option value="{{p.player_id}}">{{p.full_name}} ({{p.player_id}})</option>{% endfor %}</select></div>
<div><label>Wage/week (£)</label><input type="number" name="wage_weekly" min="0" max="1000000" placeholder="Unknown"></div>
<div><label>Expiry date</label><input type="date" name="end_date"></div>
<div><label>Squad status</label><select name="squad_role"><option value="">Unknown</option>
{% for role in contract_roles %}<option value="{{role}}">{{role|replace('_',' ')|title}}</option>{% endfor %}</select></div>
<div><label>Provenance</label><select name="source_kind">
<option value="user_sandbox_assumption">Sandbox assumption</option>
<option value="source_backed">Source-backed</option></select></div>
<div><label>Source note</label><input name="source_note" placeholder="Required for source-backed"></div></div>
<button>Record contract</button></form></div></main></body></html>"""

def create_play_blueprint(db_path):
    bp=Blueprint("world_play",__name__)
    @bp.app_template_filter("club_display")
    def club_display(value):
        """Remove internal warehouse IDs from presentation only, never source keys."""
        if not isinstance(value,str):return value
        import re
        return re.sub(r"\s+\[WH27:[0-9a-fA-F]{8,20}\]$", "",value)

    def serializer():
        secret=os.getenv("WORLD_MARKET_COOKIE_SECRET","")
        if not secret: return None
        return URLSafeTimedSerializer(secret,salt="pes-world-play-v1")
    def authenticated():
        # Development deployments may intentionally allow password-free access.
        # The signed CSRF token remains mandatory for all write actions.
        if not os.getenv("WORLD_MARKET_ACCESS_KEY","").strip():
            return True
        ser=serializer()
        if not ser:return False
        try:return ser.loads(request.cookies.get("world_play_access",""),max_age=8*60*60)=="market-admin"
        except (BadSignature,SignatureExpired):return False
    def csrf_value():
        return serializer().dumps("csrf-market-v1")
    def check_write():
        if not authenticated():abort(403)
        try:
            if serializer().loads(request.form.get("csrf",""),max_age=8*60*60)!="csrf-market-v1":abort(403)
        except (BadSignature,SignatureExpired):abort(403)
        # Timed-market careers have NO writable legacy questionnaires,
        # manual AI simulation controls or ad-hoc season board events.
        # Only genuine manager Inbox decisions are permitted in that mode.
        requested=(request.view_args or {}).get("career_id")
        if requested and not request.path.startswith(
                "/world/play/career/"+requested+"/market/"):
            with connect() as db:
                if window_snapshot(db,career_id=requested)["state"]!="not_started":
                    abort(403,"Use the autonomous Manager Inbox for timed careers")
    def connect():
        from world_v2 import initialize_world
        conn=sqlite3.connect(str(db_path))  # Batch initial seed in transactions; autocommit caused 30s timeouts
        conn.row_factory=sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        initialize_world(conn)
        initialize_catalog(conn)
        initialize_market(conn)
        initialize_career_engine(conn)
        initialize_career_management(conn)
        initialize_board_objectives(conn)
        initialize_career_board_policy(conn)
        initialize_career_selling(conn)
        initialize_incoming_approaches(conn)
        initialize_transfer_protocol(conn)
        initialise_live_market(conn)
        from world_reputation_v2 import initialize_pyramid
        initialize_pyramid(conn)
        return conn
    def page(title, mode, **kwargs):
        return render_template_string(HTML,title=title,mode=mode,authenticated=True,
            access_required=bool(os.getenv("WORLD_MARKET_ACCESS_KEY","").strip()),
            csrf=csrf_value(),role_labels=ROLE_LABELS,
            error=request.args.get("error",""),
            notice=request.args.get("notice","")[:300],
            notice_scope=request.args.get("scope",""),**kwargs)
    def on_error(error,career_id=None):
        from urllib.parse import quote
        loc="/world/play"+(f"/career/{career_id}" if career_id else "")
        return redirect(loc+"?error="+quote(str(error)[:180]))

    @bp.get("/world/play")
    def index():
        if not authenticated():
            if not os.getenv("WORLD_MARKET_ACCESS_KEY"):
                explanation="Access key not configured"
            elif request.args.get("signin")=="1":
                explanation=("Sign-in did not stick: your browser did not return its "
                    "secure session cookie. Open the address directly in Safari "
                    "or Chrome rather than an embedded preview, then sign in again.")
            else:
                explanation=""
            return render_template_string(HTML,title="Unlock Career Transfer Desk",
               authenticated=False,career=None,error=explanation,
               mode="login")
        with connect() as db:
            datasets=db.execute("SELECT * FROM world_datasets ORDER BY season_id DESC").fetchall()
            selected=request.args.get("dataset",os.getenv("FC27_PREVIEW_DATASET","england-2026-27-fc27"))
            if selected not in {d["dataset_id"] for d in datasets}:abort(404)
            clubs=db.execute("""SELECT c.club_id,c.name FROM world_dataset_entries e
                JOIN world_clubs c ON c.club_id=e.club_id WHERE e.dataset_id=?
                ORDER BY c.name""",(selected,)).fetchall()
            careers=db.execute("SELECT * FROM world_career_saves WHERE state='sandbox' ORDER BY created_at DESC").fetchall()
            return page("Career Transfer Desk","index",career=None,
                        datasets=datasets,clubs=clubs,careers=careers,selected_dataset=selected)

    @bp.get("/world/play/login")
    def login_page():
        # Browsers and saved links navigate with GET, never POST. Provide a
        # safe landing page rather than Flask's default 405 response.
        return redirect("/world/play")

    @bp.post("/world/play/login")
    def login():
        password=os.getenv("WORLD_MARKET_ACCESS_KEY","")
        supplied=request.form.get("password","")
        if not password or not hmac.compare_digest(supplied,password):
            return render_template_string(HTML,title="Unlock Career Transfer Desk",authenticated=False,
                mode="login",career=None,error="Invalid access passphrase"),403
        if serializer() is None:abort(503)
        response=make_response(redirect("/world/play?signin=1"))
        # SameSite=Lax keeps CSRF protection on unsafe cross-site requests,
        # while allowing a top-level navigation from the ChatGPT app or
        # another website into the securely authenticated career desk.
        response.set_cookie("world_play_access",serializer().dumps("market-admin"),
            max_age=8*60*60,secure=True,httponly=True,samesite="Lax",path="/world")
        return response

    @bp.post("/world/play/logout")
    def logout():
        check_write()
        response=make_response(redirect("/world/play"))
        response.delete_cookie("world_play_access",path="/world")
        response.delete_cookie("world_play_access",path="/world/play")
        return response


    @bp.get("/world/play/career/<career_id>/management")
    def management(career_id):
        if not authenticated():return redirect("/world/play")
        with connect() as db:
            if window_snapshot(db,career_id=career_id)["state"]!="not_started":
                return redirect("/world/play/career/"+career_id+"/market")
            club_id=managed_club(db,career_id)
            snapshot=career_management_snapshot(db,career_id=career_id,club_id=club_id)
            club=db.execute("SELECT name FROM world_clubs WHERE club_id=?",(club_id,)).fetchone()
            players=db.execute("""SELECT p.player_id,p.full_name
                FROM world_career_registrations r JOIN world_players p ON p.player_id=r.player_id
                WHERE r.career_id=? AND r.club_id=? ORDER BY p.full_name""",(career_id,club_id)).fetchall()
            history=objective_history(db,career_id=career_id,club_id=club_id)
            baseline=strength_baseline(db,career_id=career_id,club_id=club_id)
            capacity=(resource_capacity(db,career_id=career_id,club_id=club_id,
                  baseline=baseline) if baseline["available"] else None)
            return render_template_string(CAREER_MANAGEMENT_PAGE,career_id=career_id,
                club_name=club[0],snapshot=snapshot,csrf=csrf_value(),
                players=players,board_events=BOARD_EVENTS,contract_roles=CONTRACT_ROLES,
                objective_history=history,strength_baseline=baseline,
                resource_capacity=capacity,
                buying_policy=get_policy(db,career_id,club_id))

    def managed_club(db,career_id):
        row=db.execute("""SELECT manager_club_id FROM world_career_saves
            WHERE career_id=? AND state='sandbox'""",(career_id,)).fetchone()
        if not row or row[0] is None:abort(404)
        return row[0]



    @bp.get("/world/play/career/<career_id>/selling")
    def selling_career(career_id):
        if not authenticated():return redirect("/world/play")
        with connect() as db:
            if window_snapshot(db,career_id=career_id)["state"]!="not_started":
                return redirect("/world/play/career/"+career_id+"/market")
            manager_club_id=managed_club(db,career_id)
            row=db.execute("SELECT title FROM world_career_saves WHERE career_id=?",
                           (career_id,)).fetchone()
            players=db.execute("""SELECT p.player_id,p.full_name,
                r.club_id,c.name AS club_name FROM world_career_registrations r
                JOIN world_players p ON p.player_id=r.player_id
                JOIN world_clubs c ON c.club_id=r.club_id
                WHERE r.career_id=? ORDER BY p.full_name,p.player_id""",
                (career_id,)).fetchall()
            selected_id=request.args.get("player_id",type=int)
            by_id={p["player_id"]:p for p in players}
            if selected_id is not None and selected_id not in by_id:
                abort(404)
            if selected_id is None and players:
                # Prioritise a prospective signing for the first view.
                default=next((p for p in players
                    if p["club_id"]!=manager_club_id),players[0])
                selected_id=default["player_id"]
            player=by_id.get(selected_id)
            career_dataset=db.execute("""SELECT dataset_id FROM world_career_saves
                 WHERE career_id=?""",(career_id,)).fetchone()[0]
            rated_tables=db.execute("""SELECT COUNT(*) FROM sqlite_master
                WHERE type='table' AND name IN
                ('world_dataset_rosters','world_dataset_ratings')""").fetchone()[0]
            # Partial test fixtures and incomplete archives have no source
            # valuation tables. Don't crash the selling screen or guess.
            model_valuation=(_player_reference(db,career_dataset,selected_id)[0]
                             if player and rated_tables==2 else None)
            existing=(get_seller_assumptions(db,career_id,selected_id)
                      if player else None)
            amount=request.args.get("offer_fee","").strip()
            try:
                offer_fee=int(amount) if amount else None
                if offer_fee is not None and not 0<=offer_fee<=1_000_000_000:
                    raise ValueError("Invalid preview fee")
            except ValueError:
                abort(400,description="Offer must be a whole number of pounds")
            enabled=selling_enabled(db,career_id)
            preview=(evaluate_career_seller_bid(db,career_id=career_id,
                       player_id=selected_id,seller_club_id=player["club_id"],
                       offer_fee=offer_fee)
                     if enabled and existing and offer_fee is not None else None)
            return render_template_string(SELLING_CAREER_PAGE,
                career_id=career_id,career_name=row["title"],csrf=csrf_value(),
                enabled=enabled,manager_club_id=manager_club_id,
                players=players,selected_id=selected_id,player=player,
                existing=existing,model_valuation=model_valuation,
                preview=preview,offer_fee=offer_fee,
                roles=SQUAD_ROLES,financial_options=FINANCIAL_STATES,
                board_financial_options=FINANCIAL_OBJECTIVES,
                replacement_options=REPLACEMENT_STATES,
                seller_stances=SELLER_STANCES,
                ambition_options=AMBITION_LEVELS,
                ownership_options=OWNERSHIP_PRIORITIES,
                trust_options=MANAGER_TRUST_LEVELS,
                error=request.args.get("error",""))

    def seller_error(error,career_id):
        from urllib.parse import quote
        return redirect("/world/play/career/"+career_id+
            "/selling?error="+quote(str(error)[:250]))

    @bp.post("/world/play/career/<career_id>/selling/enable")
    def selling_enable(career_id):
        check_write()
        try:
            with connect() as db:
                enable_career_selling(db,career_id=career_id,
                    source_note=request.form["source_note"])
            return redirect("/world/play/career/"+career_id+"/selling")
        except (ValueError,KeyError,sqlite3.Error) as exc:
            return seller_error(exc,career_id)

    @bp.post("/world/play/career/<career_id>/selling/circumstances")
    def selling_circumstances(career_id):
        check_write()
        try:
            def optional_int(key):
                value=request.form.get(key,"").strip()
                return None if value in ("","unknown") else int(value)
            def optional_bool(key):
                value=request.form.get(key,"unknown")
                if value not in ("yes","no","unknown"):
                    raise ValueError("Invalid "+key)
                return None if value=="unknown" else value=="yes"
            board_value=request.form.get("board_enabled","no")
            if board_value not in ("yes","no"):
                raise ValueError("Invalid selling board setting")
            player_id=int(request.form["player_id"])
            with connect() as db:
                record_seller_assumptions(db,career_id=career_id,
                    player_id=player_id,market_value=optional_int("market_value"),
                    contract_years=optional_int("contract_years"),
                    squad_role=request.form.get("squad_role","unknown"),
                    transfer_listed=optional_bool("transfer_listed"),
                    player_wants_exit=optional_bool("player_wants_exit"),
                    financial_state=request.form.get("financial_state","unknown"),
                    replacement=request.form.get("replacement","unknown"),
                    seller_stance=request.form.get("seller_stance","unknown"),
                    board_enabled=board_value=="yes",
                    exceptional_offer_pct=optional_int("exceptional_offer_pct"),
                    financial_objective=request.form.get("financial_objective","unknown"),
                    ambition=request.form.get("ambition","unknown"),
                    ownership_priority=request.form.get("ownership_priority","unknown"),
                    assumed_manager_trust=request.form.get("assumed_manager_trust","unknown"),
                    source_note=request.form["source_note"])
            return redirect("/world/play/career/"+career_id+
                            "/selling?player_id="+str(player_id))
        except (ValueError,KeyError,sqlite3.Error) as exc:
            return seller_error(exc,career_id)

    @bp.post("/world/play/career/<career_id>/management/buying-board")
    def management_buying_board(career_id):
        check_write()
        try:
            with connect() as db:
                configure_policy(db,career_id=career_id,club_id=managed_club(db,career_id),
                    max_fee_pct=int(request.form["max_fee_pct"]),
                    max_headroom_use_pct=int(request.form["max_headroom_use_pct"]),
                    financial_objective=request.form["financial_objective"],
                    ambition=request.form["ambition"],
                    ownership_priority=request.form["ownership_priority"],
                    source_note=request.form["source_note"])
            return redirect("/world/play/career/"+career_id+"/management")
        except (ValueError,KeyError,sqlite3.Error) as exc:return on_error(exc,career_id)

    @bp.post("/world/play/career/<career_id>/management/objective/auto")
    def management_auto_objective(career_id):
        check_write()
        try:
            with connect() as db:
                lock_auto_strength_objective(db,career_id=career_id,
                    club_id=managed_club(db,career_id),
                    season_key=request.form["season_key"],
                    ambition=request.form.get("ambition","consolidation"),
                    investment_mandate=request.form.get("investment_mandate","none"),
                    investment_pool=int(request.form.get("investment_pool","0")),
                    commitment_note=request.form.get("commitment_note",
                      "Explicit board strength baseline without investment mandate"))
            return redirect("/world/play/career/"+career_id+"/management")
        except (ValueError,KeyError,sqlite3.Error) as exc:return on_error(exc,career_id)

    @bp.post("/world/play/career/<career_id>/management/objective")
    def management_objective(career_id):
        check_write()
        try:
            with connect() as db:
                raw=request.form.get("expected_relegation","unknown")
                if raw not in ("unknown","yes","no"):raise ValueError("Invalid expected relegation")
                lock_objective(db,career_id=career_id,club_id=managed_club(db,career_id),
                    season_key=request.form["season_key"],
                    expected_rank=int(request.form["expected_rank"]),
                    league_size=int(request.form["league_size"]),
                    expected_relegation=None if raw=="unknown" else raw=="yes",
                    strength_source=request.form["strength_source"],
                    source_note=request.form["source_note"])
            return redirect("/world/play/career/"+career_id+"/management")
        except (ValueError,KeyError,sqlite3.Error) as exc:return on_error(exc,career_id)

    @bp.post("/world/play/career/<career_id>/management/review")
    def management_review(career_id):
        check_write()
        try:
            with connect() as db:
                yesno=lambda v: {"yes":True,"no":False}[v]
                review_season(db,career_id=career_id,club_id=managed_club(db,career_id),
                    season_key=request.form["season_key"],actual_rank=int(request.form["actual_rank"]),
                    promoted=yesno(request.form["promoted"]),
                    relegated=yesno(request.form["relegated"]),
                    cup_result=request.form["cup_result"],result_note=request.form["result_note"])
            return redirect("/world/play/career/"+career_id+"/management")
        except (ValueError,KeyError,sqlite3.Error) as exc:return on_error(exc,career_id)

    @bp.post("/world/play/career/<career_id>/management/confidence")
    def management_confidence(career_id):
        check_write()
        try:
            with connect() as db:
                set_initial_confidence(db,career_id=career_id,
                    club_id=managed_club(db,career_id),value=int(request.form["value"]))
            return redirect("/world/play/career/"+career_id+"/management")
        except (ValueError,KeyError,sqlite3.Error) as exc:return on_error(exc,career_id)

    @bp.post("/world/play/career/<career_id>/management/event")
    def management_event(career_id):
        check_write()
        try:
            with connect() as db:
                record_board_event(db,career_id=career_id,
                    club_id=managed_club(db,career_id),event_key=request.form["event_key"],
                    event_type=request.form["event_type"],event_date=request.form["event_date"],
                    source_note=request.form["source_note"])
            return redirect("/world/play/career/"+career_id+"/management")
        except (ValueError,KeyError,sqlite3.Error) as exc:return on_error(exc,career_id)

    @bp.post("/world/play/career/<career_id>/management/contract")
    def management_contract(career_id):
        check_write()
        try:
            with connect() as db:
                wage=request.form.get("wage_weekly","").strip()
                record_contract(db,career_id=career_id,
                    club_id=managed_club(db,career_id),player_id=int(request.form["player_id"]),
                    wage_weekly=int(wage) if wage else None,
                    end_date=request.form.get("end_date") or None,
                    squad_role=request.form.get("squad_role") or None,
                    source_kind=request.form["source_kind"],
                    source_note=request.form.get("source_note",""))
            return redirect("/world/play/career/"+career_id+"/management")
        except (ValueError,KeyError,sqlite3.Error) as exc:return on_error(exc,career_id)

    @bp.post("/world/play/create")
    def create():
        check_write()
        try:
            club_id=int(request.form["manager_club_id"])
            scale=float(request.form.get("scale","1"))
            with connect() as db:
                start_sandbox(db,career_id=request.form["career_id"],dataset_id=request.form["dataset_id"],
                    title=request.form["title"][:80],manager_club_id=club_id,
                    pes_lock_date=request.form["pes_lock_date"],next_summer_date=request.form["next_summer_date"],
                    economy_version=request.form.get("economy_version","prototype-v1"),scale=scale,
                    player_decision_version=request.form.get("player_decision_version",LEGACY_VERSION))
            return redirect("/world/play/career/"+request.form["career_id"])
        except (ValueError,sqlite3.Error,KeyError) as exc:return on_error(exc)

    @bp.get("/world/play/watch/<token>")
    def spectator_market(token):
        """Read-only share link; no authentication or manager actions."""
        import hmac
        with connect() as db:
            row=db.execute("""SELECT w.career_id FROM world_career_live_market_access a
                JOIN world_career_preseason_windows w ON w.window_id=a.window_id
                WHERE a.spectator_token=?""",(token,)).fetchone()
            if row is None:abort(404)
            career_id=row[0]
            snap=window_snapshot(db,career_id=career_id)
            result=process_live_market(db,career_id=career_id)
            if result.get("changed"):
                request.environ["career_live_market_dirty"]=True
            return live_market_render(db,career_id=career_id,
                                      spectator=True)

    def live_market_render(db,*,career_id,spectator=False):
        c=db.execute("""SELECT c.title,c.manager_club_id,cl.name
            FROM world_career_saves c JOIN world_clubs cl
             ON cl.club_id=c.manager_club_id
            WHERE c.career_id=? AND c.state='sandbox'""",
            (career_id,)).fetchone()
        if c is None:abort(404)
        snap=window_snapshot(db,career_id=career_id)
        offers=[]
        messages=[]
        watch_url=None
        unread=0
        signed=0
        purchases=[]
        player_search=request.args.get("player_search","").strip()[:70] if not spectator else ""
        targets=[]
        def filter_value(key):
            value=request.args.get(key,"").strip()
            return int(value) if value.isdigit() else None
        scout_query=request.args.get("scout_query","").strip()[:70] if not spectator else ""
        scout_position=request.args.get("scout_position","") if not spectator else ""
        scout_min_overall=filter_value("scout_min_overall")
        scout_max_age=filter_value("scout_max_age")
        scout_category=request.args.get("scout_category","") if not spectator else ""
        scout_min_category=filter_value("scout_min_category")
        scout_attribute=request.args.get("scout_attribute","") if not spectator else ""
        scout_min_attribute=filter_value("scout_min_attribute")
        scout_contract=request.args.get("scout_contract","") if not spectator else ""
        scout_squad=request.args.get("scout_squad")=="1" if not spectator else False
        scout_sort=request.args.get("scout_sort","overall")
        if scout_sort not in SORT_COLUMNS:scout_sort="overall"
        scout_order=request.args.get("scout_order","desc")
        if scout_order not in ("asc","desc"):scout_order="desc"
        scout_shortlist=request.args.get("scout_shortlist")=="1" if not spectator else False
        scout_attributes=scouting_attributes(db,career_id=career_id) if not spectator else []
        shortlist=scouting_search(db,career_id=career_id,shortlist_only=True,
            limit=300) if not spectator else []
        recommendations=[]  # Suggested targets intentionally hidden in the simplified scouting desk.
        squad=squad_preview(db,career_id=career_id) if not spectator else {"players":[],"departures":[]}
        scout_results=scouting_search(db,career_id=career_id,query=scout_query,
            position=scout_position,min_overall=scout_min_overall,max_age=scout_max_age,
            category=scout_category,min_category=scout_min_category,
            attribute=scout_attribute,min_attribute=scout_min_attribute,
            contract=scout_contract,squad_only=scout_squad,sort_by=scout_sort,
            descending=scout_order=="desc",shortlist_only=scout_shortlist) if not spectator else []
        if snap["state"]=="open" and not spectator and len(player_search)>=2:
            targets=manager_targets(db,career_id=career_id,query=player_search)
        if snap["state"]!="not_started":
            rows=db.execute("""SELECT o.offer_id,o.status,o.offered_fee,
                o.demanded_fee,o.player_id,p.full_name player_name,
                bc.name buyer_name,ia.status player_status,
                ia.decision_reason player_reason,
                (SELECT COUNT(*) FROM world_career_offers rival
                 WHERE rival.career_id=o.career_id AND rival.player_id=o.player_id
                   AND rival.offer_id<>o.offer_id
                   AND rival.status IN ('accepted_pending_contract','agreed_future'))
                   AS competing_offers
                FROM world_career_preseason_window_offers wo
                JOIN world_career_offers o ON o.offer_id=wo.offer_id
                JOIN world_players p ON p.player_id=o.player_id
                JOIN world_clubs bc ON bc.club_id=o.buying_club_id
                LEFT JOIN world_career_incoming_approaches ia ON ia.offer_id=o.offer_id
                WHERE wo.window_id=? AND o.career_id=?
                AND o.selling_club_id=?
                ORDER BY o.offer_id DESC""",
                (snap["window_id"],career_id,c["manager_club_id"])).fetchall()
            labels={"proposed":"New offer","countered":"Awaiting buyer",
                    "accepted_pending_contract":"Player/agent talks",
                    "agreed_future":"Signed — registering at deadline",
                    "completed":"Registered for season","rejected":"Declined",
                    "withdrawn":"Withdrawn"}
            dataset=db.execute("""SELECT dataset_id FROM world_career_saves
                WHERE career_id=?""",(career_id,)).fetchone()[0]
            offers=[]
            from world_offer_deadlines import confirmation_state
            for r in rows:
                item=dict(r,status_label=labels.get(r["status"],r["status"]))
                item["confirmation"]=confirmation_state(
                    db,career_id=career_id,offer_id=r["offer_id"])
                if r["status"]=="withdrawn" and item["confirmation"] and item["confirmation"]["expired_at"]:
                    item["status_label"]="Buyer withdrew — decision time expired"
                valuation,_=_player_reference(db,dataset,r["player_id"])
                item["market_value"]=valuation
                item["value_difference"]=(r["offered_fee"]-valuation
                                          if valuation is not None else None)
                item["value_difference_pct"]=(100*(r["offered_fee"]-valuation)/valuation
                    if valuation is not None and valuation>0 else None)
                offers.append(item)
            outgoing=db.execute("""SELECT o.offer_id,o.player_id,o.status,o.offered_fee,
                o.demanded_fee,p.full_name AS player_name,
                sc.name AS seller_name,t.status AS agent_status,
                t.demanded_wage_weekly AS agent_demand
                FROM world_career_preseason_window_offers wo
                JOIN world_career_offers o ON o.offer_id=wo.offer_id
                JOIN world_players p ON p.player_id=o.player_id
                JOIN world_clubs sc ON sc.club_id=o.selling_club_id
                LEFT JOIN world_career_agent_terms t ON t.offer_id=o.offer_id
                WHERE wo.window_id=? AND o.career_id=?
                AND o.buying_club_id=? AND o.selling_club_id<>?
                ORDER BY o.offer_id DESC""",
                (snap["window_id"],career_id,c["manager_club_id"],
                 c["manager_club_id"])).fetchall()
            buy_labels={"proposed":"Awaiting seller","countered":"Seller counteroffer",
                "rejected":"Seller rejected offer",
                "accepted_pending_contract":"Player/agent talks",
                "agreed_future":"Signed — registering at deadline",
                "completed":"Registered for season","withdrawn":"Withdrawn"}
            purchases=[dict(r,status_label=buy_labels.get(r["status"],r["status"]))
                for r in outgoing]
            signed=sum(o["status"] in ("agreed_future","completed") for o in offers+purchases)
            messages=market_messages(db,career_id=career_id)
            unread=sum(m["is_read"]==0 for m in messages)
            if not spectator:
                token=spectator_token(db,career_id=career_id)
                if token:watch_url=request.url_root.rstrip("/")+"/world/play/watch/"+token
        from world_player_morale import existing_morale
        morale=(existing_morale(db,career_id=career_id,window_id=snap["window_id"])
                if snap["state"]!="not_started" else [])
        excluded=[r for r in morale if r["status"]=="refusing_to_play"]
        summary={"arrivals":0,"departures":0,"spent":0,"received":0,
                 "deals":[],"world_deals":[],"rejected":0,"expired":0,"other_withdrawn":0}
        if snap["state"]=="closed":
            recorded=db.execute("""SELECT r.fee_gbp,r.weekly_wage_gbp,
                    r.from_club_id,r.to_club_id,p.full_name,
                    seller.name AS seller_name,buyer.name AS buyer_name
                FROM world_career_preseason_registration_events r
                JOIN world_players p ON p.player_id=r.player_id
                JOIN world_clubs seller ON seller.club_id=r.from_club_id
                JOIN world_clubs buyer ON buyer.club_id=r.to_club_id
                WHERE r.window_id=? AND r.career_id=?
                ORDER BY r.offer_id""",
                (snap["window_id"],career_id)).fetchall()
            for item in recorded:
                incoming=item["to_club_id"]==c["manager_club_id"]
                outgoing=item["from_club_id"]==c["manager_club_id"]
                if not (incoming or outgoing):
                    summary["world_deals"].append({
                        "player":item["full_name"],"seller":item["seller_name"],
                        "buyer":item["buyer_name"],"fee":item["fee_gbp"]})
                    continue
                if incoming:
                    summary["arrivals"]+=1
                    summary["spent"]+=item["fee_gbp"]
                else:
                    summary["departures"]+=1
                    summary["received"]+=item["fee_gbp"]
                summary["deals"].append({
                    "direction":"In" if incoming else "Out",
                    "player":item["full_name"],
                    "other_club":item["seller_name"] if incoming else item["buyer_name"],
                    "fee":item["fee_gbp"],
                    "wage":item["weekly_wage_gbp"]})
            history=db.execute("""SELECT o.offer_id,o.status,
                EXISTS(SELECT 1 FROM world_career_offer_events e
                  WHERE e.offer_id=o.offer_id
                    AND e.event_type='preseason_deadline_expired') expired
                FROM world_career_preseason_window_offers wo
                JOIN world_career_offers o ON o.offer_id=wo.offer_id
                WHERE wo.window_id=? AND o.career_id=?
                AND (o.buying_club_id=? OR o.selling_club_id=?)""",
                (snap["window_id"],career_id,c["manager_club_id"],
                 c["manager_club_id"])).fetchall()
            summary["rejected"]=sum(o["status"]=="rejected" for o in history)
            summary["expired"]=sum(bool(o["expired"]) for o in history)
            summary["other_withdrawn"]=sum(
                o["status"]=="withdrawn" and not o["expired"] for o in history)
        season_tasks=(season_checklist(db,career_id=career_id)
                      if snap["state"]=="closed" and not spectator else
                      {"available":False,"steps":{},"completed":False})
        rendered=render_template_string(LIVE_MARKET_PAGE,
            title=c["title"],career_id=career_id,manager_name=c["name"],
            spectator=spectator,snap=snap,offers=offers,
            purchases=purchases,targets=targets,player_search=player_search,
            buy_request_key="manager-buy-v1-"+secrets.token_urlsafe(14),
            messages=messages,unread=unread,signed=signed,watch_url=watch_url,
            scout_results=scout_results,scout_attributes=scout_attributes,
            shortlist=shortlist,recommendations=recommendations,squad=squad,
            scout_categories=CATEGORIES,scout_query=scout_query,
            scout_position=scout_position,scout_min_overall=scout_min_overall or "",
            scout_max_age=scout_max_age or "",scout_category=scout_category,
            scout_min_category=scout_min_category or "",scout_attribute=scout_attribute,
            scout_min_attribute=scout_min_attribute or "",scout_contract=scout_contract,
            scout_squad=scout_squad,scout_sort=scout_sort,
            scout_order=scout_order,scout_shortlist=scout_shortlist,
            summary=summary,season_tasks=season_tasks,
            player_morale=morale,season_exclusions=excluded,
            money=format_market_gbp,
            funds=budget_remaining(db,career_id,c["manager_club_id"]),
            budget_total=db.execute("""SELECT transfer_budget FROM world_career_club_ledger
                WHERE career_id=? AND club_id=?""",(career_id,c["manager_club_id"])).fetchone()[0],
            wage_total=wage_budget_breakdown(db,career_id,c["manager_club_id"])["total"],
            wage_headroom=wage_budget_breakdown(db,career_id,c["manager_club_id"])["remaining"],
            csrf=csrf_value() if not spectator else "",
            error=request.args.get("error","")[:260] if not spectator else "",
            notice=request.args.get("notice","")[:260] if not spectator else "")
        response=make_response(rendered)
        response.headers["Cache-Control"]="private, no-store" if not spectator else "no-store"
        response.headers["Referrer-Policy"]="no-referrer"
        return response

    @bp.get("/world/play/career/<career_id>/market/shortlist")
    def scout_shortlist_page(career_id):
        if not authenticated():return redirect("/world/play")
        with connect() as db:
            players=scouting_search(db,career_id=career_id,
                                    shortlist_only=True,limit=300)
        template="""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Transfer shortlist</title><style>
body{background:#101a27;color:#ecf5ff;font:15px system-ui;margin:0}
main{max-width:950px;margin:25px auto;padding:0 16px}
a{color:#b8dbff}table{border-collapse:collapse;width:100%}
td,th{padding:12px;border-bottom:1px solid #3c5c78;text-align:left}
th{background:#1d3044}div.scroll{overflow-x:auto}
</style></head><body><main>
<p><a href="/world/play/career/{{career_id}}/market">← Transfer Desk</a></p>
<h1>My transfer shortlist</h1>
<p>Players you have saved for this career, available before, during and after the window.</p>
{% if players %}<div class="scroll"><table><thead><tr>
<th>Player</th><th>Club</th><th>Position</th><th>OVR</th><th>Age</th><th>Estimated market value</th><th>Report</th>
</tr></thead><tbody>{% for p in players %}
<tr><td>{{p.full_name}}</td><td>{{p.club_name|club_display}}</td><td>{{p.primary_position or '—'}}</td>
<td>{{p.overall}}</td><td>{{p.age if p.age is not none else '—'}}</td>
<td>{{money(p.market_value) if p.market_value is not none else 'Unknown'}}</td>
<td><a href="/world/play/career/{{career_id}}/market/player/{{p.player_id}}">Scout / approach</a></td></tr>
{% endfor %}</tbody></table></div>
{% else %}<p>No players saved yet. Open a scout report and select Add to shortlist.</p>{% endif %}
</main></body></html>"""
        response=make_response(render_template_string(template,
            players=players,career_id=career_id,money=format_market_gbp))
        response.headers["Cache-Control"]="private, no-store"
        return response

    @bp.get("/world/play/career/<career_id>/market/player/<int:player_id>")
    def scout_player(career_id,player_id):
        if not authenticated():return redirect("/world/play")
        with connect() as db:
            try: player=player_profile(db,career_id=career_id,player_id=player_id)
            except ValueError:abort(404)
            market_open=window_snapshot(db,career_id=career_id)["state"]=="open"
            manager=db.execute("""SELECT manager_club_id FROM world_career_saves
                WHERE career_id=?""",(career_id,)).fetchone()[0]
            funds=budget_remaining(db,career_id,manager)
        response=make_response(render_template_string(SCOUT_PLAYER_PAGE,
            player=player,career_id=career_id,csrf=csrf_value(),money=format_market_gbp,
            market_open=market_open,funds=funds,
            request_key="manager-buy-v1-"+secrets.token_urlsafe(14)))
        response.headers["Cache-Control"]="private, no-store"
        return response

    @bp.post("/world/play/career/<career_id>/market/shortlist")
    def scout_shortlist(career_id):
        check_write()
        try:
            player_id=int(request.form["player_id"])
            action=request.form.get("action")
            if action not in ("save","remove"):raise ValueError("Invalid shortlist action")
            with connect() as db:
                set_shortlisted(db,career_id=career_id,player_id=player_id,save=action=="save")
            return redirect(f"/world/play/career/{career_id}/market/player/{player_id}")
        except (ValueError,KeyError,sqlite3.Error):
            return redirect(f"/world/play/career/{career_id}/market#scouting")

    @bp.get("/world/play/career/<career_id>/market")
    def manager_market(career_id):
        if not authenticated():return redirect("/world/play")
        with connect() as db:
            snap=window_snapshot(db,career_id=career_id)
            if snap["state"]!="not_started":
                result=process_live_market(db,career_id=career_id)
                if result.get("changed"):
                    request.environ["career_live_market_dirty"]=True
            return live_market_render(db,career_id=career_id)

    @bp.post("/world/play/career/<career_id>/market/start")
    def manager_market_start(career_id):
        check_write()
        try:
            if request.form.get("confirm")!="start-30-minute-window":
                raise ValueError("Confirm that the manager is ready for the 30-minute session")
            with connect() as db:
                state=start_live_market(db,career_id=career_id)
            return redirect("/world/play/career/"+career_id+"/market?notice="+
                            "The+30-minute+pre-season+market+has+started")
        except (ValueError,sqlite3.Error) as exc:
            from urllib.parse import quote
            return redirect("/world/play/career/"+career_id+
                "/market?error="+quote(str(exc)[:260]))

    @bp.post("/world/play/career/<career_id>/market/buy")
    def manager_market_buy(career_id):
        check_write()
        try:
            with connect() as db:
                result=submit_buy_offer(db,career_id=career_id,
                    player_id=int(request.form["player_id"]),
                    offered_fee=int(request.form["offered_fee"]),
                    request_key=request.form["request_key"])
            text=("Offer already recorded" if result["existing"] else
                  "Transfer bid submitted; selling club response: "+
                  result["status"].replace("_"," "))
            from urllib.parse import quote
            return redirect("/world/play/career/"+career_id+
                "/market?notice="+quote(text)+"#purchases")
        except (ValueError,sqlite3.Error,KeyError) as exc:
            from urllib.parse import quote
            return redirect("/world/play/career/"+career_id+
                "/market?error="+quote(str(exc)[:260])+"#buy-players")

    @bp.post("/world/play/career/<career_id>/market/buy/rebid")
    def manager_market_rebid(career_id):
        check_write()
        from urllib.parse import quote
        try:
            original_id=int(request.form["offer_id"])
            revised=int(request.form["offered_fee"])
            with connect() as db:
                snap=window_snapshot(db,career_id=career_id)
                if snap["state"]!="open":
                    raise ValueError("The transfer window is no longer open")
                old=db.execute("""SELECT o.player_id,o.status,o.offered_fee
                    FROM world_career_offers o
                    JOIN world_career_saves c ON c.career_id=o.career_id
                    JOIN world_career_preseason_window_offers wo
                      ON wo.offer_id=o.offer_id
                    WHERE o.career_id=? AND o.offer_id=? AND wo.window_id=?
                    AND o.buying_club_id=c.manager_club_id
                    AND o.selling_club_id<>c.manager_club_id""",
                    (career_id,original_id,snap["window_id"])).fetchone()
                if not old or old["status"] not in ("rejected","withdrawn"):
                    raise ValueError("Only a previously rejected or withdrawn bid can be resubmitted")
                if revised<=old["offered_fee"]:
                    raise ValueError("Submit an improved fee to reopen talks with this club")
                result=submit_buy_offer(db,career_id=career_id,
                    player_id=old["player_id"],offered_fee=revised,
                    request_key="manager-buy-v1-rebid-"+secrets.token_urlsafe(14))
            return redirect("/world/play/career/"+career_id+
                "/market?notice="+quote("Revised offer submitted: "+
                    result["status"].replace("_"," "))+"#inbox")
        except (ValueError,KeyError,sqlite3.Error) as exc:
            return redirect("/world/play/career/"+career_id+
                "/market?error="+quote(str(exc)[:260])+"#inbox")

    @bp.post("/world/play/career/<career_id>/market/buy/decision")
    def manager_market_buy_decision(career_id):
        check_write()
        try:
            action=request.form.get("decision","")
            with connect() as db:
                result=act_on_buy_offer(db,career_id=career_id,
                    offer_id=int(request.form["offer_id"]),action=action,
                    weekly_wage=(int(request.form["weekly_wage"])
                          if action=="terms" else None),
                    contract_years=int(request.form.get("contract_years","3")),
                    role_promise=request.form.get("role_promise","regular_starter"),
                    negotiated_fee=(int(request.form["negotiated_fee"])
                        if action=="negotiate_counter" else None))
            from urllib.parse import quote
            return redirect("/world/play/career/"+career_id+
                "/market?notice="+quote(result)+"#purchases")
        except (ValueError,sqlite3.Error,KeyError) as exc:
            from urllib.parse import quote
            return redirect("/world/play/career/"+career_id+
                "/market?error="+quote(str(exc)[:260])+"#purchases")

    @bp.post("/world/play/career/<career_id>/market/season/step")
    def manager_season_step(career_id):
        check_write()
        from urllib.parse import quote
        try:
            step=request.form.get("step","")
            done=request.form.get("done")=="1"
            with connect() as db:
                result=season_change_step(db,career_id=career_id,
                                          step=step,done=done)
            message=("PES season setup checklist complete." if result["completed"]
                     else "Season setup checklist updated.")
            return redirect("/world/play/career/"+career_id+
                            "/market?notice="+quote(message)+"#season-setup")
        except (ValueError,sqlite3.Error) as exc:
            return redirect("/world/play/career/"+career_id+
                            "/market?error="+quote(str(exc)[:260])+"#season-setup")

    @bp.post("/world/play/career/<career_id>/market/squad/decision")
    def manager_squad_decision(career_id):
        check_write()
        from urllib.parse import quote
        try:
            action=request.form.get("action","")
            if action not in ("update","offer"):
                raise ValueError("Choose a valid squad management action")
            role=request.form.get("role")
            listed=request.form.get("listed")=="1"
            with connect() as db:
                message=update_squad_player(db,career_id=career_id,
                    player_id=int(request.form["player_id"]),
                    role=role,listed=listed,offer_to_clubs=action=="offer")
            return redirect("/world/play/career/"+career_id+
                "/market?notice="+quote(message)+"#squad")
        except (ValueError,KeyError,sqlite3.Error) as exc:
            return redirect("/world/play/career/"+career_id+
                "/market?error="+quote(str(exc)[:260])+"#squad")

    @bp.post("/world/play/career/<career_id>/market/read")
    def manager_market_read(career_id):
        check_write()
        with connect() as db:
            mark_market_read(db,career_id=career_id)
        return redirect("/world/play/career/"+career_id+"/market#inbox")

    @bp.post("/world/play/career/<career_id>/market/decision")
    def manager_market_decision(career_id):
        check_write()
        try:
            action=request.form.get("decision","")
            fee=(int(request.form["counter_fee"]) if action=="counter" else None)
            with connect() as db:
                result=manager_respond(db,career_id=career_id,
                    offer_id=int(request.form["offer_id"]),action=action,
                    counter_fee=fee)
            from urllib.parse import quote
            return redirect("/world/play/career/"+career_id+
                "/market?notice="+quote(result) +"#inbox")
        except (ValueError,KeyError,sqlite3.Error) as exc:
            from urllib.parse import quote
            return redirect("/world/play/career/"+career_id+
                "/market?error="+quote(str(exc)[:260])+"#inbox")

    @bp.get("/world/play/career/<career_id>")
    def career(career_id):
        if not authenticated():return redirect("/world/play")
        with connect() as db:
            # Timed-window careers are played from the autonomous inbox;
            # old manual 'simulate AI' and seller questionnaire sections
            # remain only for never-enrolled legacy test careers.
            if window_snapshot(db,career_id=career_id)["state"]!="not_started":
                return redirect("/world/play/career/"+career_id+"/market")
            c=db.execute("SELECT * FROM world_career_saves WHERE career_id=? AND state='sandbox'",(career_id,)).fetchone()
            if c is None:abort(404)
            records=db.execute("""SELECT o.*,p.full_name,cb.name AS buyer_name,
                cs.name AS seller_name,t.demanded_wage_weekly AS agent_demand,
                t.status AS agent_status
                FROM world_career_offers o
                JOIN world_players p ON p.player_id=o.player_id
                JOIN world_clubs cb ON cb.club_id=o.buying_club_id
                JOIN world_clubs cs ON cs.club_id=o.selling_club_id
                LEFT JOIN world_career_agent_terms t ON t.offer_id=o.offer_id
                WHERE o.career_id=? ORDER BY o.offer_id DESC""",(career_id,)).fetchall()
            labels={"proposed":"Awaiting response","countered":"Club counteroffer",
                "rejected":"Offer rejected","accepted_pending_contract":"Agree personal terms",
                "agreed_future":"Future deal agreed — not registered",
                "withdrawn":"Withdrawn","completed":"Registered"}
            offers=[]
            for o in records:
                interest=player_move_interest(db,career_id=career_id,offer_id=o["offer_id"]) if o["status"]=="accepted_pending_contract" else {"signal":"","reason":""}
                if o["status"]=="proposed" and selling_enabled(db,career_id) and not offer_decision(db,o["offer_id"]):
                    labels["proposed"]="Awaiting selling club information"
                stage=("Agent terms accepted — awaiting your confirmation"
                       if o["status"]=="accepted_pending_contract" and o["agent_status"]=="accepted"
                       else labels.get(o["status"],o["status"]))
                current_context=player_circumstances(db,career_id,o["player_id"]) if (
                    career_player_policy(db,career_id)["version"]==DECISION_V2_VERSION) else None
                europe_context=offer_europe_context(
                    db,career_id,o["offer_id"]) if (
                        career_player_policy(db,career_id)["version"]==DECISION_V2_VERSION
                    ) else None
                known_contract=db.execute("""SELECT wage_weekly,squad_role,end_date
                    FROM world_career_management_contracts
                    WHERE career_id=? AND player_id=? AND club_id=?""",
                    (career_id,o["player_id"],o["selling_club_id"])).fetchone()
                seller_info=get_seller_assumptions(db,career_id,o["player_id"])
                incoming_state=(incoming_approach(db,o["offer_id"])
                  if o["selling_club_id"]==c["manager_club_id"] and
                     o["buying_club_id"]!=c["manager_club_id"] else None)
                modern_offer=offer_uses_five_stages(db,o["offer_id"])
                if modern_offer:
                    stage=stage_description(offer_status=o["status"],
                        agent_status=o["agent_status"],
                        incoming_status=incoming_state["status"] if incoming_state else None)
                elif incoming_state:
                    stage=incoming_state["status"].replace("_"," ").title()
                evidence=db.execute("""SELECT detail FROM world_career_offer_events
                    WHERE offer_id=? AND event_type='ai_bid_pricing'
                    ORDER BY event_id LIMIT 1""",(o["offer_id"],)).fetchone()
                ai_bid=None
                if evidence:
                    try:
                        ai_bid=json.loads(evidence[0])
                    except (TypeError,ValueError):
                        # Never fabricate a price explanation for older deals.
                        ai_bid=None
                offers.append(dict(o,incoming=incoming_state,ai_bid=ai_bid,
                    offer_five_stage=modern_offer,
                    known_contract=known_contract,seller_info=seller_info,
                    seller_review=offer_decision(db,o["offer_id"]),context=current_context,
                    europe_context=europe_context,
                    context_wage_label=display_gbp(current_context["current_wage_weekly"])
                        if current_context else None,
                    fee_label=display_gbp(o["offered_fee"]),
                    counter_label=display_gbp(o["demanded_fee"]),
                    agent_demand_label=display_gbp(o["agent_demand"]),stage_label=stage,
                    interest_signal=interest["signal"],interest_reason=interest["reason"],
                    interest_decision=interest.get("decision","review"),
                    interest_issue=interest.get("issue"),
                    interest_can_negotiate=interest.get("can_negotiate",False),
                    interest_phase=interest.get("player_phase"),
                    interest_required_role=interest.get("required_role","none"),
                    interest_buyer_prestige=interest.get("buyer_prestige"),
                    interest_seller_prestige=interest.get("seller_prestige"),
                    interest_competitor_pressure=interest.get("competing_pressure",0)))
            player_search=request.args.get("player_search","").strip()[:80]
            if player_search:
                # Parameterised search across ALL registrations, rather than
                # silently restricting targets to the global top 300.
                targets=db.execute("""SELECT p.player_id,p.full_name,
                    cl.name club_name,x.overall
                    FROM world_career_registrations r
                    JOIN world_players p ON p.player_id=r.player_id
                    JOIN world_clubs cl ON cl.club_id=r.club_id
                    LEFT JOIN world_dataset_ratings x
                      ON x.dataset_id=? AND x.player_id=r.player_id
                    WHERE r.career_id=? AND r.club_id!=?
                      AND LOWER(p.full_name) LIKE ? ESCAPE '\\'
                    ORDER BY x.overall DESC,p.full_name LIMIT 100""",
                    (c["dataset_id"],career_id,c["manager_club_id"],
                     "%"+player_search.lower().replace("\\","\\\\")
                         .replace("%","\\%").replace("_","\\_")+"%")).fetchall()
            else:
                targets=db.execute("""SELECT p.player_id,p.full_name,
                    cl.name club_name,x.overall
                    FROM world_career_registrations r
                    JOIN world_players p ON p.player_id=r.player_id
                    JOIN world_clubs cl ON cl.club_id=r.club_id
                    LEFT JOIN world_dataset_ratings x
                      ON x.dataset_id=? AND x.player_id=r.player_id
                    WHERE r.career_id=? AND r.club_id!=?
                    ORDER BY x.overall DESC,p.full_name LIMIT 150""",
                    (c["dataset_id"],career_id,c["manager_club_id"])).fetchall()
            home_players=db.execute("""SELECT p.player_id,p.full_name
                FROM world_career_registrations r
                JOIN world_players p ON p.player_id=r.player_id
                WHERE r.career_id=? AND r.club_id=? ORDER BY p.full_name""",
                (career_id,c["manager_club_id"])).fetchall()
            manager=db.execute("SELECT name FROM world_clubs WHERE club_id=?",(c["manager_club_id"],)).fetchone()
            wages=wage_budget_breakdown(db,career_id,c["manager_club_id"])
            return page(c["title"],"career",career=c,
                 decision_policy=career_player_policy(db,career_id),
                 europe_labels={"unknown":"Unknown — needs review",
                                "none":"No European competition",
                                "conference_league":"Conference League",
                                "europa_league":"Europa League",
                                "champions_league":"Champions League"},
                 offers=offers,targets=targets,player_search=player_search,
                 home_players=home_players,
                 seller_policy_on=selling_enabled(db,career_id),
                 transfer_protocol_on=transfer_protocol_enabled(db,career_id),
                 manager_name=manager[0],remaining_label=display_gbp(budget_remaining(db,career_id,c["manager_club_id"])),
                 wage_total_label=display_gbp(wages["total"]),
                 wage_committed_label=display_gbp(wages["committed"]),
                 wage_reserved_label=display_gbp(wages["reserved_future"]),
                 wage_remaining_label=display_gbp(wages["remaining"]),
                 wage_remaining_raw=wages["remaining"],
                 wage_default_preview=display_gbp(wages["remaining"]-10000),
                 today=date.today().isoformat(),request_key=secrets.token_urlsafe(14))

    def do_offer(career_id, op):
        check_write()
        notice=""
        target_id=None
        try:
            with connect() as db:
                if window_snapshot(db,career_id=career_id)["state"]!="not_started":
                    raise ValueError("A timed career uses the autonomous Manager Inbox, not manual simulation or seller forms")
                manager=db.execute("""SELECT manager_club_id FROM world_career_saves
                    WHERE career_id=? AND state='sandbox'""",(career_id,)).fetchone()
                if manager is None:abort(404)
                manager_id=manager[0]
                if op=="offer" and int(request.form["buying_club_id"])!=manager_id:
                    abort(403)
                if op=="seller_review":
                    reference=db.execute("""SELECT buying_club_id,selling_club_id
                        FROM world_career_offers WHERE career_id=? AND offer_id=?""",
                        (career_id,int(request.form["offer_id"]))).fetchone()
                    if reference is None:abort(404)
                    if manager_id not in (reference[0],reference[1]):abort(403)
                if op in ("incoming_circumstances","incoming_advance",
                          "incoming_finalise","incoming_cancel"):
                    bid=db.execute("""SELECT o.selling_club_id,o.buying_club_id
                        FROM world_career_offers o WHERE o.career_id=? AND o.offer_id=?""",
                        (career_id,int(request.form["offer_id"]))).fetchone()
                    if not bid:abort(404)
                    if bid[0]!=manager_id or bid[1]==manager_id:abort(403)
                if op in ("accept","agree","confirm","withdraw","circumstances"):
                    owner=db.execute("""SELECT buying_club_id FROM world_career_offers
                         WHERE career_id=? AND offer_id=?""",
                         (career_id,int(request.form["offer_id"]))).fetchone()
                    if owner is None:abort(404)
                    if owner[0]!=manager_id:abort(403)
                if op=="offer":
                    target_id=int(request.form["player_id"])
                    oid=propose_offer(db,career_id=career_id,
                        request_key=request.form["request_key"],player_id=target_id,
                        buying_club_id=int(request.form["buying_club_id"]),
                        offered_fee=int(request.form["offered_fee"]),
                        agreement_date=request.form["agreement_date"],
                        seller_stance=request.form.get("seller_stance","neutral"))
                    status=db.execute("SELECT status FROM world_career_offers WHERE offer_id=?",
                                      (oid,)).fetchone()[0]
                    if status=="proposed":
                        notice=("Offer recorded and visible in Negotiations, but the "
                                "selling club needs additional verified or explicitly "
                                "assumed circumstances before it can respond. "
                                "Use the player-specific link and Get selling club response.")
                    else:
                        notice=("Offer recorded. Selling club status: "+
                                status.replace("_"," ")+". See Negotiations below.")
                elif op=="seller_review":
                    status=review_pending_seller_offer(db,career_id=career_id,
                        offer_id=int(request.form["offer_id"]))
                    notice="Selling club response recorded: "+status.replace("_"," ")+"."

                elif op=="circumstances":
                    field=request.form.get("transfer_listed")
                    if field not in ("yes","no"):
                        raise ValueError("Transfer-listing status must be explicitly yes or no")
                    set_player_circumstances(
                        db,career_id=career_id,offer_id=int(request.form["offer_id"]),
                        current_wage_weekly=int(request.form["current_wage_weekly"]),
                        current_role=request.form["current_role"],
                        transfer_listed=field=="yes",
                        renewal_status=request.form["renewal_status"],
                        buyer_europe=request.form.get("buyer_europe","unknown"),
                        seller_europe=request.form.get("seller_europe","unknown"))
                elif op=="incoming_circumstances":
                    listed=request.form.get("transfer_listed","")
                    if listed not in ("yes","no"):
                        raise ValueError("Transfer listing must be explicitly yes or no")
                    set_player_circumstances(db,career_id=career_id,
                        offer_id=int(request.form["offer_id"]),
                        current_wage_weekly=int(request.form["current_wage_weekly"]),
                        current_role=request.form["current_role"],
                        transfer_listed=listed=="yes",
                        renewal_status=request.form["renewal_status"],
                        buyer_europe=request.form.get("buyer_europe","unknown"),
                        seller_europe=request.form.get("seller_europe","unknown"),
                        allow_selling_manager=True)
                elif op=="incoming_advance":
                    advance_incoming_approach(db,career_id=career_id,
                        offer_id=int(request.form["offer_id"]))
                elif op=="incoming_finalise":
                    finalise_incoming_approach(db,career_id=career_id,
                        offer_id=int(request.form["offer_id"]))
                elif op=="incoming_cancel":
                    reject_incoming_offer(db,career_id=career_id,
                        offer_id=int(request.form["offer_id"]))
                    notice=("AI bid rejected. Re-run incoming bids to see "
                            "whether this club can justify an improved offer.")
                elif op=="accept":
                    accept_counter(db,career_id=career_id,offer_id=int(request.form["offer_id"]))
                elif op=="agree":
                    negotiate_agent(db,career_id=career_id,offer_id=int(request.form["offer_id"]),
                       weekly_wage=int(request.form["weekly_wage"]),
                       contract_years=int(request.form.get("contract_years","3")),
                       agreement_date=request.form["agreement_date"],
                       role_promise=request.form.get("role_promise","unspecified"))
                elif op=="confirm":
                    confirm_future_agreement(db,career_id=career_id,offer_id=int(request.form["offer_id"]),
                        agreement_date=request.form["agreement_date"])
                elif op=="withdraw":
                    withdraw_offer(db,career_id=career_id,offer_id=int(request.form["offer_id"]))
                elif op=="ai":
                    target_id=int(request.form["player_id"])
                    summary=simulate_ai_bids(db,career_id=career_id,
                        player_id=target_id,report=True)
                    notice=summary["reason"]
                elif op=="ai_inbound":
                    target_id=int(request.form["player_id"])
                    owner=db.execute("""SELECT club_id FROM world_career_registrations
                        WHERE career_id=? AND player_id=?""",
                        (career_id,target_id)).fetchone()
                    if not owner or owner[0]!=manager_id:
                        abort(403)
                    summary=simulate_ai_bids(db,career_id=career_id,
                        player_id=target_id,report=True)
                    notice=summary["reason"]
            from urllib.parse import urlencode
            if notice and op in ("offer","seller_review","ai","ai_inbound","incoming_cancel"):
                params={"notice":notice,
                        "scope":"ai_inbound" if op=="incoming_cancel" else op}
                if op=="offer" and request.form.get("player_search"):
                    params["player_search"]=request.form["player_search"][:80]
                section=("negotiations" if op in ("offer","seller_review")
                         else "ai-inbound" if op in ("ai_inbound","incoming_cancel")
                         else "ai-rivals")
                return redirect("/world/play/career/"+career_id+"?"+
                                urlencode(params)+"#"+section)
            return redirect("/world/play/career/"+career_id)
        except (ValueError,sqlite3.Error,KeyError) as exc:
            if op in ("offer","seller_review","ai","ai_inbound"):
                from urllib.parse import urlencode
                params={"error":str(exc)[:260],"scope":op}
                if op=="offer" and request.form.get("player_search"):
                    params["player_search"]=request.form["player_search"][:80]
                section=("negotiations" if op=="seller_review" else
                         "ai-inbound" if op=="ai_inbound" else
                         "ai-rivals" if op=="ai" else "transfer-offers")
                return redirect("/world/play/career/"+career_id+"?"+
                                urlencode(params)+"#"+section)
            return on_error(exc,career_id)

    @bp.route("/world/play/career/<career_id>/offer",methods=["GET","POST"])
    def offer(career_id):
        if request.method=="GET":
            # A direct GET to a submission endpoint must not display an
            # unhelpful 405 or accidentally mutate a save.
            return redirect("/world/play/career/"+career_id+"?error=Offers+must+be+submitted+using+the+Send+offer+form")
        return do_offer(career_id,"offer")
    @bp.post("/world/play/career/<career_id>/protocol/enable")
    def transfer_protocol_enable(career_id):
        check_write()
        try:
            with connect() as db:
                enable_transfer_protocol(db,career_id=career_id,
                    activation_note=request.form["activation_note"])
            return redirect("/world/play/career/"+career_id)
        except (ValueError,KeyError,sqlite3.Error) as exc:
            return on_error(exc,career_id)

    @bp.post("/world/play/career/<career_id>/accept")
    def accept(career_id):return do_offer(career_id,"accept")
    @bp.post("/world/play/career/<career_id>/agree")
    def agree(career_id):return do_offer(career_id,"agree")
    @bp.post("/world/play/career/<career_id>/confirm")
    def confirm(career_id):return do_offer(career_id,"confirm")
    @bp.post("/world/play/career/<career_id>/withdraw")
    def withdraw(career_id):return do_offer(career_id,"withdraw")
    @bp.post("/world/play/career/<career_id>/seller/review")
    def seller_review(career_id):return do_offer(career_id,"seller_review")
    @bp.post("/world/play/career/<career_id>/ai")
    def ai(career_id):return do_offer(career_id,"ai")
    @bp.post("/world/play/career/<career_id>/ai-inbound")
    def ai_inbound(career_id):return do_offer(career_id,"ai_inbound")
    @bp.post("/world/play/career/<career_id>/incoming/circumstances")
    def incoming_circumstances(career_id):return do_offer(career_id,"incoming_circumstances")
    @bp.post("/world/play/career/<career_id>/incoming/advance")
    def incoming_advance(career_id):return do_offer(career_id,"incoming_advance")
    @bp.post("/world/play/career/<career_id>/incoming/finalise")
    def incoming_finalise(career_id):return do_offer(career_id,"incoming_finalise")
    @bp.post("/world/play/career/<career_id>/incoming/cancel")
    def incoming_cancel(career_id):return do_offer(career_id,"incoming_cancel")
    @bp.post("/world/play/career/<career_id>/circumstances")
    def circumstances(career_id):return do_offer(career_id,"circumstances")
    return bp

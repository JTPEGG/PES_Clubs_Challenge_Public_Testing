# Autonomous career world — locked gameplay design contract

Status: **Approved direction / required design principle**  
Scope: **Development career fork only**. This is a design contract, **not a claim that autonomous gameplay is already implemented**.  
Project: PES Clubs Challenge / Career Transfer Desk

> **You manage your football club. The rest of the football world carries on around you, whether you intervene or not.**

## Non-negotiable player experience

1. **Zero manual player/club circumstance setup during gameplay.** The player never enters market valuations, current wages, contract years, transfer-listed status, playing-time category, seller financial strength, board preferences, replacement difficulty, player ambition, or comparable modelling facts. The database and career simulation generate these automatically and transparently. The manager can make football-management decisions such as proposing a target, responding to a bid, negotiating, making promises, or deciding to sell.
2. **No player-selection or “Simulate AI bids / Generate interest / Advance AI negotiations” buttons in normal gameplay.** These are prototype/dev diagnostic controls only. They must not appear as requirements for the career world to operate. Admin/test tools, when retained, remain separate from the manager experience.
3. **Unsolicited AI transfer approaches arrive automatically in a persistent Manager's Inbox.** News includes incoming bids on the human club's players, competing interest, new and revised offers, withdrawals, accepted/rejected developments, contract/player concerns, and significant team or market events. The manager may accept, counter, reject, or ignore relevant messages; unanswered offers may expire according to clear, deterministic rules.
4. **All other clubs operate autonomously.** AI teams assess squad depth, finances and objectives; buy and sell among themselves; and compete for the same targets. Their transfers affect future depth, valuation, finances and league competitiveness. Every deal must satisfy budgets, registration/season restrictions, player choice and relevant board approvals.
5. **The world is persistent, event-driven and dynamic.** Player role, ambition, availability, estimated wage, contract remaining, happiness, transfer valuation and club objectives evolve from the simulated career calendar, credible model rules, and *recorded* game events. Club relegation, promotion, European qualification, injuries, results, transfers, and board decisions may affect simulation only when reliably represented in the career state—never invent real PES match results or user gameplay activity.
6. **A reload, repeated HTTP request or repeated opening of the Inbox never manufactures new bids or advances time.** No global wall-clock simulation for a save without an explicit career-calendar progression policy. Each career event is committed once and keyed by career/season/turn/event identity. Scheduled processing, if later introduced, must use the same idempotent calendar and transaction rules.
7. **Maintain a truthful data provenance boundary.** Start with PES-compatible player/club data for game ratings and eligibility. Football Manager-style detail may enrich private management attributes only through a verified, permitted data source/export; official database availability does not imply unrestricted copying or redistribution. For every key attribute, distinguish source-provided, modelled/estimated, inferred from *recorded* events, and unknown. Do not present modelled contracts, hidden player intentions, real-world wages or transfer rumours as confirmed facts.
8. **Preserve PES gameplay integrity and challenge history.** No transfer silently changes an Xbox PES game save or player registration. Respect the existing career summer registration lock and finance ledger; only advance in-app registrations when the current explicit transfer protocol permits it. Existing careers, offers, audit trails and production challenge data are not reset or rewritten.
9. **Give reasons without exposing data-entry forms.** Inbox cards show why a buyer is interested, what changed, and what actions the manager may take, while avoiding claims that assumptions are verified external facts. Respect the agreed squad-role hierarchy: Key Player, Regular Starter, then lower roles.
10. **Difficult, realistic career progression remains the goal.** Clubs and players react strongly to prestige, salary, competitive level, European football, finances, and realistic alternatives. An elite starter in a Champions League side cannot be easily acquired by a weaker team simply by requesting negotiations.

## Locked pre-season window format — approved 15 October 2026

- **Duration:** Exactly **30 minutes of real-world wall-clock time**, beginning only when the manager deliberately opens the pre-season transfer window. The clock is server-authoritative, persisted in UTC, and **does not restart on refresh or reconnect**.
- **One transfer window per season**: the 30-minute pre-season period. **No January window and no transfers while the season is active** in version one. Later seasons require an attested/recorded season boundary before opening a new window.
- **Deals signed before the deadline**: bids, player consent, contractual terms and the final management decision must be completed before the clock reaches zero. Incomplete offers expire; a pending bid is not an agreement.
- **Batch registration at the deadline**: fully signed, properly funded and eligible transfers register as a single idempotent pre-season batch immediately once deadline processing runs. The squad is then fixed for the entire season. Registration is **inside the web-app career ledger**, not an automatic edit to the Xbox PES 2020 game file; users must still reflect approved players in PES by whatever game setup is supported.
- **World continues throughout the window:** AI-club bids and any AI-to-AI transfers occur by autonomous rules and appear as inbox events on the real-world timer. No player-specific "simulate offers" button; no manual circumstance forms.
- **Group experience:** a clearly visible countdown, a live inbox, a concise offer history, and a read-only spectator view for the other human squad members. Only the authorised manager can accept/reject/negotiate, even if spectators have access to the read-only feed.
- **Fairness & safety:** no requests accepted at or after the authoritative deadline. The finalisation transaction is safe to retry and never moves a player twice or deducts a fee twice. If the host loses connectivity the clock still runs; administrative recovery is separate and auditable.
- **Rate of events:** market activity should be staggered realistically through the 30 minutes, not all delivered simultaneously or mechanically once every minute. A late bid can create genuine deadline pressure but does not override realism.
- **Persistence:** existing experimental sandbox saves are preserved and are not suddenly enrolled or given a running timer on deployment; activation for the approved real-time mode requires an explicit safe start at a future challenge session.

### Implementation note on timing

The 30-minute clock deliberately **replaces the earlier proposal to advance the market only on PES match/season milestones during the transfer window**. Outside the window the squad is locked, and season progress still depends exclusively on recorded PES outcomes. A server heartbeat, timed worker or safe request-triggered reconciliation can enact the deadline, but never treats browser refresh as a new transfer event.

## Development implementation status — 15 October 2026

**First usable slice implemented (development fork only):**

- `world_live_market.py` implements source-labelled modelled starting player circumstances, a manager-only 30-minute window start, deterministic staggered autonomous buying-club offers, finite post-rejection bids, an auditable Market Inbox, separate AI fee and player/agent decisions, and a manager-authenticated Accept / Counter / Reject / final signing sequence.
- `world_career_play.py` provides the responsive manager inbox and token-protected, **read-only** spectator view with countdown, live news and finances. Legitimate non-manager spectators cannot post decisions. Timed-mode careers block the old seller questionnaire and manually triggered AI simulation routes. Window refreshes process due market moments but are idempotent.
- `world_preseason_window.py` ensures one immutable 1800-second deadline, expiry of unfinished talks and registration of fully signed pre-season deals as a single idempotent app-roster transaction. It does **not** edit the Xbox PES 2020 console game file.
- `test_live_market_http.py` exercises an **actual seeded 2026/27 Nottingham Forest test career** with authenticated browser requests and an isolated temporary SQLite file. Historic challenge saves remain untouched.
- **214+ automated test regressions passed** in GitHub Actions. The market only begins after the manager explicitly starts; simply deploying does not start any existing career's clock.

**Deliberate remaining limitations, not yet implemented:**

1. **AI-to-AI completed transfers across the other clubs** (the first slice simulates eligible AI approaches to the managed club). This is necessary for the full independent world.
2. **Second and later seasons** require a verified in-game season transition and a new 30-minute window; this first version safely supports only the first window.
3. **Real source-backed wages, contracts, European qualification and richer Football Manager-style attributes** have not been imported. Current values are fictional estimates, clearly labelled. The provisional European qualification model assigns starting slots by stored top-division prestige for gameplay; it does not claim actual Champions League qualification.
4. **Always-on server-side scheduling** is not yet enabled. Market moments are reconciled when an authenticated manager or valid read-only spectator page is requested (including page polling), with persisted timestamps and immutable deadlines. An absent session cannot restart the clock or make late requests valid; final close/reconciliation occurs on the next valid request if no client is connected when the deadline hits.
5. **Independent review of the exact PES Xbox Edit Mode squad-update process** is still needed before relying on the website's completed registration roster in a real match.

These unfinished items must not be described as delivered.

## Minimum viable end-to-end slice — implement next

Use the existing code in `world_careers.py`, `world_ai_bidding.py`, `world_career_selling.py`, `world_career_incoming.py`, `world_career_transfer_protocol.py`, and the `world_career_play.py` routes as the starting point. Do **not** rewrite these engines or erase existing saves for this phase.

### A. Career calendar and reproducible progression

- Store a versioned career-specific calendar, season/turn, seed and last-processed turn.
- Progress exclusively on a clearly defined in-game calendar event (initially an established/recorded match or season milestone from the saved challenge, where supported). Define the mapping to the PES results workflow before implementing.
- Process each turn once in a database transaction; replay/restart may be retried safely with no duplicate offers or messages.
- Advance simulated contracts, budgets and club conditions only for elapsed career time and verified lifecycle events. No invented played matches.

### B. Automatic circumstances for the existing universe

- Create a baseline table/state per player, club and save, seeded from current dataset / PES-rated data.
- Fill simulation-only circumstances using reproducible policies, positional squad ranking, player age, contract/wage **assumptions with provenance**, budgets, league standing and European context, with source precedence when permitted data exists.
- A missing optional fact must not produce a *manual seller questionnaire* or an unexplained universal “open to talks”; the autonomous engine must apply an explicit conservative simulated estimate or a clearly constrained policy.
- Add dated change/event history so these properties evolve on later calendar turns.

### C. Manager Inbox and autonomous inbound transfer offers

- Persist messages with career ID, type, created career date/turn, linked event/offer ID, unread flag, available manager actions, response deadline and expiry.
- AI buyer shortlist and amount are determined from credible real simulated squad needs, financial constraints and market competition, using the existing club-specific bid pricing. Not every club bids every turn.
- Queue and process offers at the correct career time; generate inbox messages automatically, without user pressing an AI simulation button.
- Existing offers are authoritative. Rejecting may trigger a later, higher bid only if club still qualifies, within three total rounds. No duplicate on page reload.
- Ensure AI-to-AI transfer decisions and in-app registration changes can be modelled in later slices, after the human-inbox path is proven.

### D. Manager-facing experience

- Add Inbox navigation, unread count and a chronological feed with realistic bid messages and Accept / Counter / Reject where applicable.
- Keep all model setup, simulation and override controls out of normal gameplay; admin-only diagnostics may remain separate in development.
- An existing career must upgrade lazily/idempotently. Initialising a career or opening the home page must not run a transfer simulation unexpectedly or erase prior data.

## First vertical-slice acceptance tests

1. A new career starts with a reproducible player/club baseline and an initially valid Inbox, **without completing any transfer data form**.
2. A *recorded, valid game-calendar advancement* autonomously evaluates prospective AI demand and can deliver one or more legitimate bids to the Inbox, without selecting a player or pressing “simulate”. Event and bid audit records identify their source, date and rationale.
3. Reopening, refreshing or retrying that same advancement does **not** create any additional bids, messages or time advancement.
4. The manager can reject an offer from the Inbox. Only a subsequent valid career turn may produce a financially justified improved bid, up to the capped negotiation rounds.
5. Transfers reserve budgets, respect contract/player/board decisions and never change PES registrations without the defined PES registration-window protocol.
6. Confirmed match outcomes and real human activity are never fabricated; without verified events, the calendar does not pretend fixtures have been played.
7. Existing development saves and historic offers remain available. No production GitHub/Render/Supabase modifications.
8. All transfer regression tests plus new calendar/idempotency/inbox HTTP tests pass before release.

## Implementation order

1. **Vertical slice:** career calendar + source-aware circumstances baseline + durable inbox + autonomous incoming bids to the managed club. Replace required gameplay use of manual seller forms or “simulate” buttons.
2. **Living market:** AI-to-AI dealings, transfer priorities, contract events, competition between buyers, follow-up re-bidding over future turns, meaningful expiry.
3. **Season evolution:** player happiness, role and contract changes; club objectives, board confidence, sporting results and prestige; season changes; consistent transfer windows.
4. **Expanded database:** evaluate legitimate Football Manager data sources/exports and licensing, then optionally import compatible club/player attributes without overriding PES game ratings or assuming unavailable real-world facts.

**Next engineering deliverable:** a working, tested inbox event end-to-end from an automatically processed in-game turn. A mock inbox or a manual “simulate” shortcut is not sufficient.

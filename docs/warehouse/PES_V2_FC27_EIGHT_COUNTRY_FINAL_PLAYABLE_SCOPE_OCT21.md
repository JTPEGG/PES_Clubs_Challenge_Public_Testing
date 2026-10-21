# FC27 2026/27 — Final eight-country intended playable scope

**Latest user correction, 21 October 2026:** Germany **and** the Netherlands remain open. The immediately preceding six-country-only decision is superseded in the active release build.

**Repository:** `JTPEGG/PES_Clubs_Challenge_Public_Testing`  
**Branch:** `feat/fifa-pes-converter-v2-complete`  
**Verified passing GitHub Actions:** [run 39595984002](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39595984002) — **36 Python tests passed** and the derived FC27 SQLite release built successfully.

## Exactly eight open and intended playable countries

| Country | Domestic open and intended playable divisions | Source clubs |
|---|---|---:|
| England | Premier League, Championship, League One, League Two | 92 |
| Germany | Bundesliga, 2. Bundesliga, 3. Liga | 56 |
| Spain | La Liga, Segunda División | 42 |
| France | Ligue 1, Ligue 2 | 36 |
| Italy | Serie A, Serie B | 40 |
| Scotland | Scottish Premiership | 12 |
| Portugal | Primeira Liga | 18 |
| Netherlands | Eredivisie | 18 |
| **Total** | **16 open domestic competition codes** | **314** |

The other **37 FC27 competition codes / 345 source clubs** are treated as **closed for sporting promotion/relegation**, not deleted from the football world. All original 659 FC27 source clubs remain available as existing clubs for the future transfers and managerial-job market; they do not all have their actual PES playing files certified yet.

### Deliberate game simplifications and corrected decisions

- **Newly closed relative to the previous 21-open scope:** Poland, Turkey, Austria, Belgium and Argentina (five first-division competition codes).
- **Germany stays open:** all three tiers, and both previously sourced Bundesliga ↔ 2. Bundesliga ↔ 3. Liga promotion/relegation boundaries remain **enabled in effective game scope**. Any previously staged automatic closure of those boundaries in the superseded six-country policy is **removed from the active release**, while original source rules remain untouched.
- **Netherlands stays open:** Eredivisie retains its season-specific source movement format with the Eerste Divisie as an immediate feeder, subject to valid promotion eligibility and eventual PES club registration. It is **not** treated as a closed Dutch league.
- **Austria becomes closed:** the older user-approved direct 2. Liga champion/Bundesliga-bottom-club exchange is **retained in game decision history** but **disabled in the effective release**. Do not falsely claim the user still wants Austrian promotion/relegation.
- **Belgium becomes closed:** Challenger Pro League's **15 previously sourced real club names are retained for reference**, but no Belgian feeder is part of active career promotion processing.
- **Italy remains open with the explicitly user-approved mandatory Serie B 3rd–8th play-offs**. Its Serie C three-group club identity source remains retained; players are not invented.
- Source historical regulations are still maintained even where different from simplifying game decisions.
- South Korea, Romania, Sweden, Norway and the other previously closed peripheral competitions remain closed.

## Effective feeder scope

The final effective one-hop **named** feeder pool registry now has **four** competition identities without complete PES player squads: French Ligue 3, Italian Serie C, Portuguese Liga 2 and Dutch Eerste Divisie. Two of these (France and Italy) already have 18 and 60 official real club identities registered, respectively. Portugal and the Netherlands do not yet have their respective real club pools attached here.

Other independently identified movement boundaries, such as the English National League feeder, Spain's regional Primera Federación and Germany's Regionalliga, are tracked separately in the sourced historical competition topology. These cannot be counted as completed PES squads merely because movement rules exist.

The prior sourced 15 Belgian feeder names remain present in the immutable reference records; they are **not currently required for promotion into a playable league**.

## Machine-readable release files

- **Active decision:** `data/warehouse/fc27_2026_27_eight_country_playable_scope.json`
- **Active application:** `world_fc27_eight_country_playable_scope.py` — applied after original historical rules and the earlier broad closure scope, before the source feeder-club import.
- **Effective tables:** `fc27_effective_world_league_movement_scope`, `fc27_eight_country_playable_approval`, `fc27_eight_country_new_closed_decisions`, `fc27_effective_core_pyramid_game_boundaries`, `fc27_eight_country_playable_club_candidates`, `fc27_career_world_clubs` and `fc27_feeder_pool_readiness`.
- **Derived generated files:** `FC27_2026_27_ALL_659_SOURCE_CLUB_HOME_COMPETITIONS.sqlite`, `FC27_2026_27_CAREER_WORLD_CLUB_ROLES.csv`, `FC27_COMPETITION_STRUCTURE_READINESS.json` and the original/official source audits. Available from the release GitHub Actions artifacts.

The earlier `world_fc27_six_country_playable_scope.py` and JSON are a **superseded historical development decision**, not used by the current release builder. Their regression tests remain as documentation of the previous scope and do not alter the active eight-country release.

## Remaining game build blockers

1. Validate game-compatible player squads for the **314 original clubs** before marking their divisions genuinely selectable and schedulable in PES.
2. Source real one-hop feeder club pools for the Portuguese and Dutch second tiers, where needed, and reconcile English/German/Spanish regional or immediately lower feeders without recursively generating extra tiers.
3. Implement/verify the actual season-end algorithm for the 16 open divisions (play-offs, direct up/down, promotion eligibility, and source team identity movements). The current data is a staged movement policy, not live career season-end gameplay.
4. Keep **`career_ready=false`**, no production career changes, no FC26 backfill until these core first-edition quality checks pass.

**No new real-world sporting rule was invented as a fact by this adjustment.** This is an explicit choice of game-scope boundaries and manager-playability intent, precisely reflecting the user's correction.

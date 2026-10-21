# FC27 playable MLS, 2026/27 Dutch and Portuguese feeders, season-end calculation prototype

**Date:** 21 October 2026  
**Repository:** `JTPEGG/PES_Clubs_Challenge_Public_Testing`  
**Branch:** `feat/fifa-pes-converter-v2-complete`  
**Latest completed passing release:** [GitHub Actions run 39598946131](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39598946131) — **47 Python tests passed**, derived 659-club SQLite built, SQLite foreign keys and original game identity-preservation checks passed.

## 1. MLS is playable, with no promotion/relegation

The user explicitly requested that the MLS be **playable** alongside the eight approved European countries. Treat MLS as a **playable closed-pyramid competition**, not an "open pyramid" or a simulated lower-tier feeder. It has its own regular season and championship knockout format.

- **17 intended playable divisions**: 16 in the eight European countries plus MLS; **344 original FC27 club records** (314 European, 30 MLS).
- **36 other domestic divisions** are background/non-selectable, with 315 original FC27 clubs. Note: **37** divisions have **no promotion/relegation**, including the playable MLS.
- Official **2026 MLS** structure: 30 teams; **15 Eastern + 15 Western** conference clubs; **34 regular season matches per club** (17 home/17 away); 9 playoff qualifiers from each conference; 1st–7th direct; 8th–9th wildcard; first round best-of-three; single match conference semifinal/final and MLS Cup.
- Primary sources: [Official 2026 MLS competition guidelines](https://bracket.mlssoccer.com/league-reports/competition-guidelines/), [MLS About/2026 competition season](https://www.mlssoccer.com/news/about-major-league-soccer-x4174).
- **All 30 official MLS conference names have an explicit one-to-one mapping to the existing 30 original FC27 club IDs.** Eleven conventional short-name aliases are approved after inspecting original FC27 source club names, e.g., LAFC for Los Angeles Football Club, Red Bulls for Red Bull New York, Sounders FC for Seattle Sounders FC, Whitecaps FC for Vancouver Whitecaps FC. Neither new clubs nor fake squads are added.
- Data: `data/warehouse/fc27_2026_mls_playable_competition.json`, `world_fc27_mls_playable_scope.py`. Read `fc27_mls_official_conference_membership` for 30 conference placements and original FC27 keys; `fc27_mls_calendar_and_playoff_policy` for the sourced competition template; `fc27_mls_playable_closed_league_approval` for no relegation and manager-selection approval; `fc27_effective_manager_selectable_competitions` unifies 16 European leagues and MLS.
- **Not yet live:** no MLS player-squad PES edit-file compatibility claim, simulated fixture table or automatic season-end playoff winner. Only the competition scope, identity crosswalk and game-format template have been staged and tested.

## 2. Four current named European feeder pools now have real club identities

The two previously missing real club lists were sourced:

| Named non-playable lower feeder | Real named clubs | Reserve/youth flags | Evidence |
|---|---:|---:|---|
| French Ligue 3 (2026/27) | 18 | 0 | Official FFF membership calendar already staged |
| Italian Serie C (2026/27) | 60 across three 20-team regional groups | 3 | Lega Pro 2026/27 clubs already staged |
| Dutch Eerste Divisie (2026/27) | 20 | 4 | [2026/27 member list, VI](https://www.vi.nl/competities/eerste-divisie/over), crosschecked against [KNVB official fixtures](https://www.knvb.nl/nieuws/betaald-voetbal/competitiezaken/71918/definitief-competitieprogramma-202627-vastgesteld). The full 20-team list originates with VI and is not falsely marked official |
| Portuguese Liga Portugal 2 (2026/27) | 18 | 3 | [Official Liga Portugal 2026/27 standings](https://www.ligaportugal.pt/competition/912/liga-portugal-meu-super/round/20262027?stat=players&tab=stats&type=50) |
| **Active feeder club names** | **116** | **10** | None given fictional players |

Additionally, the already-sourced **15 Belgian Challenger Pro League** club names (four youth clubs) stay in source evidence, although Belgian sporting promotion/relegation is deliberately closed for our game. **131 real feeder names** therefore exist in the source database overall, of which **116 are in currently active one-hop named feeder pools**. The four active national feeder pools now have **zero missing real club-name lists**.

Data: `data/warehouse/fc27_2026_27_netherlands_portugal_feeder_clubs.json` and `world_fc27_nl_pt_feeder_review.py`. The original French/Belgian/Italian 93-club source snapshot remains unchanged.

**Very important:** Real feeder *names* are not PES-editable squads or created source clubs. All 131 names have `PES_player_squad_imported=0`, and all four feeder pools retain `season_end_promotion_enabled=0`. Only eligible teams with validated game-ready player squads may be registered as promotion participants later. Reserve clubs cannot be promoted under the approved simplified game rule.

## 3. New season-end logic prototype

Implemented `world_fc27_season_end_logic.py` and `test_world_fc27_season_end_logic.py`:

- Accept ordered actual top/bottom division club IDs, verified season table size, explicit promotion/relegation slots, optional recorded intra-lower-division playoff winner(s), and conditional interdivision playoff winner when applicable.
- Automatically exclude reserve/unregistered club IDs from lower-league direct promotion eligibility. **Never fabricate substitute club IDs.**
- Block movement when real PES player squads or actual end-season results are absent, club IDs are duplicated or in two competitions, or there are insufficient verified eligible promotion candidates.
- Enforce balanced division sizes, preserve source club identities and standings order in dry-run outcomes, including the user-approved **mandatory Serie B promotion playoff**.
- Separate **2026 MLS conference playoff seed selection**, from actual 15/15 tables (top seven directly plus 8th/9th in a wildcard). Does not invent knockout results.
- These are **pure calculations tested against synthetic regression fixtures only**: no real club has been moved; no career-save mutation or production game integration is implied.

## Still outstanding before a fully running career

1. Spain's Primera Federación and Germany's Regionalliga external/regional feeders are *tracked in the existing sourced pyramid topology* separately from the four named national feeders; their remaining real club identity pools and eligibility need attention **only one tier below playable divisions**.
2. Actual PES compatible player identity/ratings/squad imports for potential promoted lower-tier clubs and original playable clubs; original source FC27-to-PES conversion gate.
3. Integration of effective league movements, valid league results, and MLS conference season/playoff simulations into the career engine, preserving staged historical data.
4. MLS season is **2026 calendar-based**, distinct from UEFA-country 2026/27 season; avoid shifting team memberships casually across calendar boundaries.
5. `career_ready=false`, `FC26_allowed_to_start=false`. Keep original production repository, careers and archives intact.

**Bottom line:** The user has nine intended playable countries (MLS included), 17 selectable-target competition codes, 344 original source club candidates. The remaining world of 315 original clubs stays in the transfer/job market. MLS is playable *without relegation*. The four national named feeder club lists are complete; the season-end dry-run now has tested, fail-closed calculations.

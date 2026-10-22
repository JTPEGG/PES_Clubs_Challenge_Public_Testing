# FC27 — Regional immediate feeders and unified effective season-end routes

**Date:** 21 October 2026  
**Repository:** `JTPEGG/PES_Clubs_Challenge_Public_Testing`  
**Branch:** `feat/fifa-pes-converter-v2-complete`  
**CI:** [successful full 55-test FC27 release run 39602792857](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39602792857).

## Scope: respect the user-approved nine playable countries

The user wants the MLS playable as a 30-club, two-conference **closed-pyramid championship**, and eight European countries playable with sporting promotion/relegation: England, Germany, Spain, France, Italy, Scotland, the Netherlands and Portugal.

- **17 intended selectable divisions**, **344 existing original game clubs** (314 European + 30 MLS).
- **16 European divisions with actual sporting promotion/relegation routes**; **MLS is not one** and cannot be erroneously promoted/relegated.
- **37 globally sporting-closed leagues**, of which **MLS is playable**. **36 are background-only leagues**, preserving their **315 original game clubs** as transfer / job-market participants.
- **659 original FC27 game clubs and all their names/identities/squads** retained without rewriting source or deploying a new game.
- Every external feeder is limited to **one division below a playable country’s lowest tier**. Do not add recursive feeders to their feeders.

## 1. Spain: real 2026/27 Primera Federación roster

**40 genuinely named clubs** in **two real 20-club groups**, based on the [Spanish federation's 24 June 2026 published division groups](https://rfef.es/es/noticias/aprobados-los-grupos-de-primera-federacion-para-la-temporada-202627).

Group 1 and Group 2 are **two distinct source standings**, not one imaginary 40-team table. **Five official B/reserve sides** are flagged.

Game movement assumption: **four clubs promoted to Segunda División each season**. The champion (or next eligible senior club, if required by game restriction) of each group is automatically promoted, and **two more** qualify through actual recorded regional playoff results. In exchange, four real Segunda División clubs are relegated. This preserves the season-scoped RFEF two-up/two-playoff format without recreating the entire real-world bracket schedule inside the management game.

**No automatic reserve-team promotion** in game. Real promotion-eligible IDs and real player squads are mandatory. Actual relegated-club assignment to a particular Spanish regional group is still **not determined** until club geography/registration is sourced.

## 2. Germany: real 2026/27 Regionalliga rosters

**91 genuinely named clubs** across the five actual fourth-tier leagues:

| Regionalliga | Clubs | Source |
|---|---:|---|
| Nord | 18 | [2026/27 DFB league records](https://datencenter.dfb.de/en/data-center/107/current/fair-play) |
| Nordost | 18 | [NOFV federation 2026/27](https://www.nofv-online.de/index.php/nofv-vereine.html) and [season overview](https://www.nofv-online.de/index.php/aktuelles-leser/start-mit-druck-kein-platz-fuer-geduld.html) |
| West | 18 | [Westdeutscher Fußballverband 2026/27 official member list](https://wdfv.de/spielbetrieb/herren-regionalliga-west) |
| Südwest | 18 | [Regionalliga Südwest official 1 July 2026 club list](https://www.regionalliga-suedwest.de/Spielbetrieb/Vereine/) |
| Bayern | **19** | [DFB 2026/27 actual team table](https://datencenter.dfb.de/en/competitions/2257/seasons/current/current_matchweek?datacenter_name=data-center) |
| **Total** | **91** | |

Bavaria's actual current 19-club table is preserved; it is **not made 18** simply because an earlier preliminary association document targeted 18.

Game movement: **four clubs promoted from the five regions into 3. Liga**, with **West, Südwest and Nordost group champions** directly promoted and a recorded **Nord vs Bayern regional champion playoff** providing the fourth. The [Bavarian federation describes this exact 2026/27 Nord/Bayern promotion pairing](https://www.bfv.de/spielbetrieb-verbandsleben/ligabetrieb/regionalliga-bayern). There are four 3. Liga relegations. The upper-division club's regional allocation awaits actual source-backed geography and is not guessed.

## 3. Data and tested route coverage

Source records:
- `data/warehouse/fc27_2026_27_es_de_regional_feeder_clubs.json`
- `world_fc27_regional_feeder_rosters.py`
- `fc27_regional_feeder_2026_27_group` — **7 real groups**
- `fc27_regional_feeder_2026_27_club` — **131 real club identities** with reserve-team marker and `PES_player_squad_imported=0`
- `fc27_regional_feeder_game_policy` — two four-up/four-down game source policies, not yet activated.
- `world_fc27_regional_season_end.py` — fail-closed dry-run candidate resolver accepting real final regional standings, eligible real club IDs, PES-ready squads and explicit playoff winners.
- Exported `FC27_2026_27_SPANISH_GERMAN_REAL_REGIONAL_FEEDERS.csv` in workflow artifact.

**The named one-hop feeder coverage for the open European countries** is now:
- 116 named clubs in the four national lower feeder divisions (France 18, Italy 60, Netherlands 20, Portugal 18).
- 131 named clubs in the seven Spanish and German regional subgroups (Spain 40, Germany 91).
- England's independently dated National League contains 24 known source-side club identities in the original topology.
- The unrelated 15 Belgian lower-division club identities are retained historically but are **not part of the active playable movement scope**.

## 4. New unified effective season-end route index

`world_fc27_effective_season_end_routes.py` derives a single **16-row** `fc27_effective_playable_season_end_routes` view-ready table from all authorised historical/source/user-simplified rules:

| Route source | Active European league edges |
|---|---:|
| Dated England/Germany/Spain core routes | 7 |
| Six dated country movements (France×2, Italy Serie A, Scotland, Netherlands, Portugal) | 6 |
| Explicit simplified Italian Serie C→Serie B exchange | 1 |
| Spanish and German regional bottom playable-tier feeds | 2 |
| **Total** | **16** |

Each of the 16 open divisions has **exactly one intended directly lower promotion feeder route**. The 17th playable competition, MLS, is intentionally *absent* from this sporting exchange index. Two German higher-division **conditional relegation ties** are explicitly modelled as *potential* promotion/relegation exchanges, **not guaranteed third promotion places**. The user-approved Italian Serie B 3rd–8th playoff is preserved.

Every route currently has `executable_career_movement=0`: this is a **structural index and validated dry-run algorithm**, *not* the production career engine. All 16 routes require real league-end results and full club/PES identity validations before career movement.

Additional export: `FC27_2026_27_EFFECTIVE_OPEN_PLAYABLE_SEASON_END_ROUTES.csv`.

## 5. Safeguards and actual remaining blockers

- **55 full Python tests** passed in [GitHub Actions 39602792857](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39602792857). End-to-end build validates SQLite integrity and original FC27 memberships.
- **No regional feeder club can be registered for promotion today**: `PES_player_squad_imported=0`, `promotion_eligible_game_registration=0`. We must not fabricate PES data, player ratings or club identities.
- All regional play-offs must use recorded actual **in-game** season results, not randomness or guessed real-world season outcomes.
- Assigning relegated 3. Liga / Segunda División clubs to particular regional groups needs actual geographical registration / club association data before we can complete the lower-group movement side.
- The real career engine still needs standings/fixture generation, results handling, game roster readiness checks, season-end mutation and a staging-to-production review. MLS needs its conference fixtures and real postseason bracket engine.
- `career_ready=false`; `FC26_allowed_to_start=false`. No deployed application, original game archive or production career has been modified.

**Suggested next implementation gate:** A *database-bound dry run* using a synthetic single-season result fixture containing the exact existing original game IDs, and a stable city/region map for relegated Spanish/German clubs. Only after that should any route become season-end executable.

# FC27 2026/27 career-world roles and first three one-hop feeder rosters

**Decision and source review:** 21 October 2026. Development repository `JTPEGG/PES_Clubs_Challenge_Public_Testing`, branch `feat/fifa-pes-converter-v2-complete`. Scope: FC27 2026/27 staging database only. No production, archived source, historical careers or FC26 touched.

**Green end-to-end QA:** [GitHub Actions run 39593279089](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39593279089). The workflow executes **30 Python tests**, regenerates the final derived SQLite, verifies the 659 source clubs, 53 leagues and retention of all player/source original records, and exports the data to GitHub Actions artifacts.

## Career-world model

- The **21 open leagues** comprise **410 original FC27 source clubs**. Their teams receive `open_league_season_candidate` status. They are the primary **game league standings and promotion/relegation simulation candidates**, not an assertion that season-end behaviour or PES playable files are ready.
- The **32 closed leagues** comprise **249 original FC27 source clubs**. Their teams receive `closed_background_world` status. They remain eligible to be considered in the **transfer market and managerial job market** even though their league standings produce no sporting promotion/relegation. One- or two-club source groups are **not falsely described as playable full leagues**.
- Every original club key remains preserved and unique. `fc27_career_world_clubs` has exactly 659 rows: `transfer_market_candidate=1`, `manager_job_market_candidate=1`, `playable_in_PES_verified=0`, and `domestic_season_schedule_activated=0`. These are **development flags**, not a live selectable job or match calendar.
- All known closed-league decisions, including South Korea, Romania, Sweden and Norway, remain in effect; Italy and Austria's user-approved simple rules remain unchanged.
- The current core fifth-tier English National League has a separately sourced 24-club one-hop feeder pool in the immutable source-side registry. The 2026/27 League Two → National League boundary remains defined.

## Genuine clubs added to the *unpopulated feeder* registry

| Source competition | Real source club names | Region grouping | Source | PES squads |
|---|---:|---|---|---|
| France, 2026/27 Ligue 3 | **18** | One national table | [Official FFF 1 July 2026 18-team roster](https://www.fff.fr/article/17022-le-calendrier-2026-2027-est-servi.html) | **None imported yet** |
| Belgium, 2026/27 Challenger Pro League | **15** | One national table | [Official Pro League season opening fixtures](https://www.proleague.be/nieuws/kalender-2026-2027-nieuwkomers-treffen-elkaar-meteen-in-challenger-pro-league) (seven named matches and first-round bye establish all 15 members) | **None imported yet** |
| Italy, 2026/27 Serie C | **60** | Three original 20-club groups A/B/C | [Official Lega Pro 2026/27 member lists](https://www.seriec.com/clubs) | **None imported yet** |
| **Total** | **93** | **Five competition table segments** | Official league/federation sources | **0 imported squads** |

**Important explicit simplifying choice:** four Belgian youth/reserve clubs and three Italian U23 clubs are marked separately. In the first gameplay implementation we will **not select a reserve side as a promoted senior club**. This is a pragmatic game eligibility choice, **not** a claim about their exact official licence or eligibility in real life. More importantly, **none of the 93 real feeder club names is currently marked eligible for game promotion** until that club has usable player identity/rating/squad data in PES. The release contains no new player, generic replacement team, guessed player or invented club.

The authoritative roster file is `data/warehouse/fc27_2026_27_verified_feeder_club_rosters.json`. The staging builder `world_fc27_career_world_playability.py` validates exact dated roster counts, duplicate real names, separate Serie C groups, official source URLs, reserve-team flags and foreign keys. The resulting tables are `fc27_sourced_real_one_hop_feeder_clubs`, `fc27_feeder_pool_readiness`, and `fc27_career_world_clubs`.

## New human-readable exports in the CI artifact

- `FC27_2026_27_OFFICIAL_REAL_FEEDER_CLUB_NAMES.csv` — 93 reviewed real feeder club names, competition code, regional group, source URLs, reserve-team flag and squad-readiness flag.
- `FC27_2026_27_CAREER_WORLD_CLUB_ROLES.csv` — 659 existing original FC27 game clubs with their competition and open/closed world roles.
- `FC27_2026_27_ALL_659_SOURCE_CLUB_HOME_COMPETITIONS.sqlite` — staging SQLite retaining the above tables and all competition/movement policies.
- `FC27_COMPETITION_STRUCTURE_READINESS.json` — current readiness and remaining gaps.

## Remaining scope

- **Six of nine named open-pyramid feeder divisions still have no real 2026/27 club pool attached:** Argentina Primera Nacional, Polish I liga, Turkish TFF 1. Lig, Austrian 2. Liga, Dutch Eerste Divisie, Portuguese Liga Portugal 2. Do not hallucinate any identities; add only genuinely reviewed source clubs where worthwhile.
- Additional core open-pyramid **external regional feeder boundaries** for Spain's Primera Federación and Germany's Regionalliga are tracked in the existing original topology separately from the nine named source-only feeder records. Do not silently claim these are complete.
- Before a real club is *promoted into a PES playable league*, ensure it has a game-importable player squad and a valid original/constructed identity crosswalk; do not treat mere names as registered player squads.
- **Human career selection vs actual PES playability** remains gated: manager and market *candidacy* can span all 659 existing FC27 clubs, but only game-compatible squads and a viable competition schedule can support active play. The 21 open leagues are the natural first career-league schedule targets, the 32 closed are background economies/job-market candidates.
- Career readiness is **blocked**, and FC26 backfill remains **not started**.

This stage increases data realism without broadening the user's preferred simple non-playable league scope or adding another mandatory regional league layer.

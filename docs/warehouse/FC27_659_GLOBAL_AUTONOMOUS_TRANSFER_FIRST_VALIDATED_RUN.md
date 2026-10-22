# FC27 659-club global autonomous market: first verified end-to-end test

**22 October 2026 — isolated development branch, not production.**

## Why switch to the full world?

The 92-club English-only simulation had unrealistic elite-club selling and limited recruiting sources. The **approved 659 active source clubs**, **53 source competitions**, and **17,593 registered player records** from the immutable 2027 warehouse let autonomous negotiations operate across actual source club IDs and currencies/contract models without declaring unverified real-world facts.

### Implementation

- `scripts/fc27_warehouse_world_bridge.py`: new development-world dataset `fc27-warehouse-659-mens-2026-27`, source SHA256 and exact source IDs, 659 clubs, 53 competitions, 17,593 players/contracts, all 29 FIFA→PES2020 V2 numeric attributes each, source/model wages and estimated club budgets. Refuses overwrite. Older historic 670-club edition is **not reused** or misreported. Existing 92-club fixture/production remains isolated.
- `scripts/fc27_warehouse_659_market_smoke.py`: creates a new disposable career, activates the normal human inbox/board/agent/AI-market services, advances all actual 30-minute scheduled moments, completes registration only at deadline, validates unique player registration and SQLite integrity, and reports source-team finance and transfers. Club/competition hierarchy readiness is **explicitly overridden for QA only**, never for a real manager-facing career.
- `.github/workflows/fc27-warehouse-659-market-qa.yml`: downloads the previously validated `FC27_UNIFIED_REFERENCE_WAREHOUSE_AI_DIMENSIONS_V2.sqlite` source artifact, populates a new isolated SQLite database, runs an actual autonomous test window, verifies and uploads JSON audit.
- `world_squad_planner.recruitment_fit`: new optional **recent_senior_departure** context allows a *comparable rated senior* replacement after a **genuinely agreed** sale, even when not a +3 point overall upgrade. A club may still recruit before selling. No sign-first requirement or fabricated replacement.
- `world_ai_world`: clubs with signed positional departures get earlier consideration; no arbitrary exclusion for a large (>14 overall) target quality upgrade; same source-rated position/buyer/seller scouting calculations cached for a single moment to scale to 659 without changing negotiations.
- **Removed arbitrary global 90 transfer cap**: the initial real 659 test hit it exactly. The finite idempotent scheduled market moments and transfer-stage checks are the remaining safety mechanisms. No per-club forced sales or signing caps are reinstated.

## First successful full 659-club career-engine test

[Verified real market run 39752836633](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39752836633). Completed the complete 30-minute game market in approximately nine minutes runtime, independent of the original live site.

| Observation | First 659 test |
|---|---:|
| Active clubs in source-scoped starting dataset | 659 |
| Original source competitions represented | 53 |
| Source-registered players and starting contracts | 17,593 |
| Converted numeric PES2020V2 attributes | 510,197 |
| Actual completed/registered autonomous transfers | **90** |
| Distinct transfers between original competitions | **84** |
| Classified senior first-team arrivals | **71** |
| Classified developmental/prospect arrivals | **19** |
| GK moves | **9** |
| Checked starting XI/source specialist cover warnings | **1** (Crystal Palace, right wing) |
| Double registrations or SQLite FK/integrity errors | **0** |

**Important interpretation:** 90 is exactly the **old engine hard safety ceiling**, which truncates the volume and makes it impossible to infer the true organic transfer count or whether every club can access the market. This old cap has now been removed. Likewise, “84 cross-competition” is not a claim of 84 cross-country transactions; the more detailed rerun distinguishes them.

## What is and is not verified

- **Verified:** the original 659 source club IDs and 17,593 starting registrations can create an independent mutable actual career test; the complete original transfer and agent/board/registration pipeline can negotiate and finalise player moves spanning multiple source competitions without fake transfer registrations.
- **Verified:** 33/33 focused senior and squad planning regressions passed [run 39754455658](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39754455658), and the reworked 92-club two-window regression passed 77 tests plus real market cycles [run 39754422040](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39754422040). Arsenal now bought 4 players, of which 3 were classified as senior, in that limited two-window test.
- **Not yet proven:** full 659-club seasonal 20-window statistical behaviour, realistic transfer *volume* untruncated by old cap, equitable coverage across 659 buyers, budget reinvestment from agreed sales, elite club first-team quality, ability to trade between countries with appropriate sporting league/prestige considerations, or confirmed real manager personalities.
- **No live deployment**; no production career changes, no PES native export/import and no false source-reported financial accounts. This is a QA-only sandbox; source expected promotion/relegation graph completeness remains a separate career launch gate.

## Next test: unrestricted transaction count and new senior recruitment context

The follow-on 659 simulation is a **new source build** with improved reporting for Arsenal, Chelsea and Manchester City, senior/prospect splits, unique buyers/sellers, actual cross-country versus cross-league moves and team-level departures. Its result must be read from its own GitHub run before declaring the improvement effective. Unlike the initial test, the global 90 deal ceiling has been removed.

Longer-term: split a genuine multi-window 659 club simulation into isolated source-identical careers and assess strategic changes and club finances with country-relevant league strength rather than assuming every league-one tier is equivalent. Keep source and mutable career state separate, and subsequently build documented real-world manager records with simulations tagged as assumptions.

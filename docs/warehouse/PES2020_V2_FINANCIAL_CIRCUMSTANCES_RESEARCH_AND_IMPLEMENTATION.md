# PES V2: historical men's club finance source research and first implementation

> **Development decision (20 October 2026):** Companies House and full club-account extraction are **out of scope for the game-ready baseline**. They are not required for career launch and will not block further development. Use official league history and reported financial events, Deloitte/UEFA aggregate and club revenue benchmarks, and the already-approved historical player wages. Unknown individual cash balances, debt and owner contributions stay *unknown*, while affordable wage ceilings and transfer allowances remain explicitly marked as **game estimates**. The next priority is connecting this baseline to historical career setup and the 30-minute AI transfer window.

**Date:** 20 October 2026
**Platform:** PC / PlayStation.
**Scope:** 22 historical starting editions (FC25 unavailable) and 13,104 men's club-season entries.
**Deployment:** Development test branch only; no new career dataset activation, Render deployment, existing career reset or PES game-file modification.

## Why we need the V2 layer

The prior financial profile (see `world_historical_club_financials.py`) derived budgets from estimated and source player wages. That was useful as a financial capacity proxy but could not detect promotion/relegation cash-flow shocks, owners funding losses, debts, administration or clubs whose existing wages exceed affordable salary capacity. An expensive squad does NOT automatically indicate a healthy club.

The **new evidence overlay** preserves that first version's original player payrolls (and all underlying contracts and loans), records official historical events with cited dates, and calculates a *separate provisional game policy*. Budgets are NOT reported real balances. These first-pass numerical policies are explicitly provisional for later calibration and sim tests.

## First validated implementation

### A. Dated primary-source event archive

Source file: `data/warehouse/historical_club_financial_events_v1.json`:
- 42 source-backed men-only club events: 18 promotion, 18 relegation, 2 ownership change, 4 documented financial distress.
- Premier League official promotions/relegations for starts 2020/21, 2022/23, 2023/24, 2024/25, 2025/26, 2026/27.
- Newcastle's 7 October 2021 takeover via PL statement and Chelsea's completed 30 May 2022 Boehly/Clearlake deal via club announcement.
- EFL documentation for Wigan administration/late salary funding, Reading wage and ownership funding failures, Sheffield United historic transfer obligation payment defaults.
- No invented takeover investments or false dates (Wigan 2020 administration has month precision). A source event after the start of a season is NOT applied retroactively to that preseason.

[Validated dated financial circumstances workflow](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39429984572); [download the validated V2 club circumstances CSV/SQLite pack](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39429984572/artifacts/12266484668).

The CI run verified 13,104 original financial profiles, 22 supported editions, 35 events uniquely linked to a club, 33 linked and effective by that edition's preseason, 17 modelled over-budget club profiles, zero observed cash/debt/investor balances falsely invented, and exact source payroll equality. Of seven source year nonmatches, six were because FC25 is absent; the Sheffield United 2024 sanction was also directed to that missing edition and deliberately not reassigned to FC24 or FC26.

### B. Finance-policy logic, v2 sandbox overlay

New module: `world_historical_financial_circumstances.py`. Separate `PES_V2_CLUB_FINANCIAL_CIRCUMSTANCES.sqlite` and CSV review files.

- Original committed payroll remains exactly unchanged.
- Promotion: provisional 1.18x wage ceiling and 1.45x transfer allowance.
- Relegation: provisional 0.70x wage ceiling and 0.42x transfer allowance.
- Official financial distress: provisional 0.60x wage ceiling, transfer allowance zero (game rule).
- Ownership change: a source-backed ownership-status fact, **no automatic extra money**.
- These are **illustrative simulation factors, not sourced amounts**. They are implemented separately so a later accounts-driven model can replace them.
- A negative wage headroom is permitted, and the club can be `model_wages_over_budget`. Club player obligations are NOT rewritten upwards or downwards to hide the problem.
- `revenue_reported_gbp`, `verified_cash_balance_gbp`, `verified_net_debt_gbp`, and `verified_owner_capital_injection_gbp` remain NULL in the circumstances dataset; no official club balance sheet has yet been parsed.

### C. Real club revenue observations and sector benchmarks

`data/warehouse/historical_club_revenue_observations_v1.json` holds **22 exact EUR annual football-revenue observations** from dated Deloitte men's Money League publications (financial years ending 2024 and 2025), plus five **aggregate GBP sector benchmarks** drawn from Deloitte annual football financial reviews.

`world_historical_revenue_evidence.py` maps only unambiguous club names and only attaches figures to a historical edition if the source report was published **before the edition's modelled preseason date**. No automatic FX conversion, invented transfer cash, or ownership-financing inference is applied.

[Validated revenue evidence run](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39430703831); [download revenue evidence CSV/SQLite](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39430703831/artifacts/12267258870).

The test linked published observations into **19 club-edition financial profiles** (23 source-edition matches; five unresolved label matches retained for review); all 13,104 profiles keep an explicit observed-revenue status. Other club revenues remain unknown. The cited Deloitte money league is not an audited cash/funds-available statement.

### D. UK company entity pilot

`data/warehouse/uk_club_legal_entity_pilot_v1.json` stores source-backed Companies House legal reporting entities:
- Chelsea Football Club Limited, company number **01965149**.
- Manchester City Football Club Limited, company number **00040946**.

These mappings are NOT proof that an individual company filing is the correct consolidated economic reporting entity for the football group. The full annual accounts and their consolidation scope, historic reorganisation, period, notes, and financial metrics need further review; **no** raw account cash/debt/revenue has been imported from Companies House in this pass. The official company filing-history API requires an API key for automation.

## Source coverage and constraints

1. Deloitte Football Money League archive has publications back to 2006, particularly useful for 20–30 large European men's clubs per year.
2. UEFA's annual European Club Finance and Investment Landscape supplies league/country wage-to-revenue and operating cost benchmark series across many countries; aggregate statistics must never be assigned to individual clubs as reported facts.
3. Deloitte Annual Review of Football Finance covers Premier League, Championship and English lower-league aggregate revenue/wages; its 2023/24 Championship total of £958m revenue and £892m wages is a **sector benchmark**, not proof about a particular club.
4. Companies House offers full historic UK football company accounts; requires verified legal entity/company-group matching, filing-year alignment, and significant human/cautious automated accounting extraction work. International equivalents have varying access.
5. Premier League and EFL publish authoritative membership, status and sanctions. Financial implications must be estimated separately.
6. Football-data.co.uk has historical league CSVs but publicly states restrictions on automated collection and AI/data-training uses; we did **not** ingest that site's data. Use permitted/licensed feeds and official league standings instead.

## Implementation backlog / next milestones (superseded by game-ready decision above)

**Priority 1: Get more SOURCE FACTS.**
- Extend Premier League and EFL season membership to all feasible edition-years with verified league/tier, continental qualification and promotion/relegation history; do not guess gaps in older snapshots. Ensure official *season dates* and no knowledge of future promotions at earlier career starting points.
- **Deferred:** audited club-account extraction for Chelsea, Manchester City and EFL clubs. This is optional longer-term research, NOT a prerequisite for playable careers.
- Reuse existing official league events and Deloitte/UEFA historical benchmarks; expand only where an obvious financial edge case materially affects gameplay, rather than demanding full coverage before launch.

**Priority 2: Calibrate pragmatic game economics (no company accounts required).**
- Use source-backed club/league circumstances plus game-calibrated financial health and board policy; do not simulate precise cash balances or debt service when the source has no evidence.
- Separate documented events from estimated spending decisions. Relegated/financially distressed clubs can have **negative wage headroom**; wealthy or promoted clubs may have greater spending flexibility based on the game policy.
- Allow negative wage budget headroom, negative operating margin, transfer freezes, planned player disposals, and soft/hard board constraints.
- Include parachute-payment periods, wage relegation clauses only where known/modelled, and distinguish owner net-worth from documented investments.

**Priority 3: Integrate with the AI career.**
- Add a new immutable career dataset/league-club-player crosswalk. Opt in only after 22-season source consistency and transfer/board tests pass; do not alter existing careers.
- Update career budget and AI seller/buyer behaviours to respect financial distress, wage oversubscription, profit targets, insolvency risk, and realistic owner injection instead of unconditional affordability.
- Test promoted/relegated, newly purchased, high-payroll-distressed, moderate-budget and elite clubs. Compare outcomes against documented source snapshots and ensure no impossible repeatable “free owner cash”.

## Locked decisions

- User-confirmed FC27 transfers (including Salah at Trabzonspor) are correct and must NOT be reversed.
- The 69 previously reviewed high-priority player wages are accepted; do not casually recompute.
- Women's football is outside the career scope.
- Current 30-minute preseason automated AI transfer window and PC/PlayStation target remain unchanged.
- The v2 overlay has **not** yet replaced the v1 budget model in the actual career engine or live web app. This avoids claiming sourced real transfer budgets where we do not have evidence.

# PES V2 — historical men's club finances release

**Date:** 20 October 2026
**Platforms:** PC / PlayStation
**Status:** Fully generated and source-payroll validated in isolated test branch; not installed in a production game or saved career.

## Release

- [Successful 22-edition club-finances GitHub validation](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39427144648)
- [Download complete 13,104-club financial database + CSV review files](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39427144648/artifacts/12265663623)
- Input: previously approved [FC27 V4 wages and 22-year contract/loan archive](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39423495384/artifacts/12264772712).

**Important:** The original FC transfers and the approved 69 high-priority player wages are left unchanged. The user confirmed the FC27 assignments, including Salah at Trabzonspor. No player identity, original source, ratings or contracts changed.

## Included data (all game-model estimates unless described otherwise)

- 13,104 club/year entries across 22 editions; FC25 remains unavailable.
- `starting_payroll_weekly_gbp` is derived from the approved player-wage and loan-share obligations. Resolved pre-existing loans contribute their wage cost to both borrowing and parent clubs; a player never counts as two *registered* players. Four unmatched source loan parents remain unresolved in the upstream historical database.
- `game_wage_budget_weekly_gbp` is a **modelled total weekly salary ceiling**, including that already-committed payroll.
- `starting_wage_headroom_weekly_gbp` is the difference, not an additional new wage allowance. Club-specific spending on new offers must reserve this headroom.
- `game_transfer_budget_gbp` is a **separate modelled transfer spending allocation** (not real cash, actual revenue, profitability or net debt).
- `financial_capacity_percentile` and `financial_capacity_band` represent each club's *relative modelled payroll strength within its starting edition*, with limited adjustment for previous same-named editions. These are not verified long-run institutional reputation ratings or real sporting-division rankings.
- `source_league_name` remains null where the source lacks a trustworthy competition label: league assignments have not been guessed.

## How the estimates are calculated

1. Start with the precise already-reviewed club payroll, including agreed loan-share model assumptions. **Do not change player salaries to make budgets fit.**
2. If a source edition contains fewer than 18 registered players at a club, estimate the cost of planning for an 18-player minimum using a bounded typical wage (between 0.4× and 8× that edition's median). This affects **budget planning only**: no phantom players, no invented wages or contract commitments.
3. Compute a within-edition percentile of planned club payroll, with at most a 20% smoothing influence from similarly named clubs in the previous five source editions. All percentile/band labels explicitly say proxy.
4. Simulated total wage budget = max(actual committed payroll plus 10%/£1,000, projected wage bill × (1.14 + 0.12 × capacity percentile)), rounded to £50.
5. Simulated starting transfer budget = projected weekly payroll × 52 × (0.075 + 0.325 × capacity percentile ^ 1.8), with an additional conservative reduction if any single wage obligation exceeds 25% of the club's whole payroll; rounded to £1,000/£5,000/£50,000 depending on size.
6. A club's actual starting payroll is always deducted from its wage budget. The unspent transfer budget and wage headroom are **distinct and cannot be counted twice**.

The 7.5%–40% simulated annualized payroll transfer-spend multiplier and wage-headroom multipliers are initial gameplay assumptions, **not independently observed historical budgeting evidence**. The next practical test is whether AI bidding, contract renewals and board intervention work believably at those amounts.

## Verified output

Artifacts:
- `PES_V2_HISTORICAL_CLUB_FINANCIALS.sqlite`: standalone 22-edition club finance overlay with edition-scoped source club key and full source/provider provenance caveats.
- `ALL_22_EDITIONS_CLUB_FINANCES.csv`: the entire cross-season list.
- `FC27_CLUB_FINANCES.csv`: sorted FC27 subset (670 clubs).
- `CLUB_FINANCE_REVIEW_FLAGS.csv`: 1,445 financially notable club/year records. Review flags represent incomplete squads, concentration or unresolved source loans, *not* missing leagues by itself.
- `CLUB_FINANCE_AUDIT.json`: year-by-year payroll, budget and source-coverage metrics.

Regression/CI checks:
- **13,104 unique edition-specific clubs** and 22 editions, no FC25.
- All 13,104 initial payrolls equal the same club's value in the approved wage/loan reference; **317,449 player wages and 10,861 named-source loans unchanged**.
- All clubs have a nonnegative transfer budget, total weekly wage budget at least as large as starting committed payroll, and headroom equal to the difference.
- The financial source explicitly identifies every new transfer and total-wage budget as a **game estimate**, never as a verified real-world balance.
- No production, Render, existing career, historical source archive or game-file save changed.

## Example FC27 game budgets

| Club | Existing weekly wages | Total weekly wage budget | Transfer budget |
|---|---:|---:|---:|
| Real Madrid | £4.287m | £5.401m | £89.15m |
| Arsenal | £3.290m | £4.144m | £68.10m |
| Manchester City | £2.365m | £2.979m | £49.00m |
| Chelsea | £2.249m | £2.832m | £46.35m |
| Liverpool | £2.277m | £2.857m | £44.35m |

Source leagues are unavailable in many older annual editions and remain explicitly unknown rather than being invented. More than 1,200 historical squads have fewer than 16 registered players; their **finance reliability is flagged** separately from data rights and historical transfer facts.

## Next integration boundary

The existing career engine already supports opt-in `world_dataset_club_finances` rows holding transfer and weekly wage budgets. Once a historical edition's clubs, competition entries and players receive explicit validated world IDs, map these edition-scoped finance rows to that new immutable dataset. The mapped budgets will then feed `world_careers.start_sandbox` alongside the approved contracts and starting loans, without manual manager wage entry. **Do not automatically merge based on name alone**, and do not activate production until an end-to-end historical test career proves payroll, club transfers and loan returns operate correctly.

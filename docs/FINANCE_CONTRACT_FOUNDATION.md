# Club finance and contract foundation (prototype)

## What exists
- Read-only `/world/finances` index and `/world/finances/club/<club_id>?dataset=...` club screens.
- `world_dataset_club_finances` contains optional transfer budget, weekly wage budget/spend, cash and debt per **dataset + club**.
- `world_dataset_player_contracts` contains optional contract dates, weekly wages, release clauses and squad role per **dataset + player**.
- Every non-empty financial record must be explicitly marked `source-backed` or `simulation-assumption`; neither is silently inferred from ratings.
- The `world_valuation.contract_adjusted_value` function discounts a player's theoretical value only when a *confirmed* contract term is supplied; unknown terms do not change value.
- All existing clubs currently show unknown budgets/wages and unverified contracts. The source does not provide reliable values for these fields.
- The screens do not create transfer offers, publish new deals or modify career save cash.

## Season isolation
Data for `england-2026-27-fc27` is wholly distinct from historical or alternative dataset IDs. Starting a career must eventually fork a dataset into a career ID with independent ledgers and financial transactions. Do not overwrite immutable reference financial records during gameplay.

## Source integrity and caveats
- Cash, debt, transfer budget and weekly wage budgets are **not interchangeable**.
- Wage bill and weekly budget should never be filled with an identical synthetic number by default.
- A dataset being marked `review` does not imply contracts or finances are verified.
- The first basic valuation algorithm (`prototype-v1`) is still the default on player pages. The contract term module is available but must not be applied to unknown contract durations.
- Historical inflation, league distributions, currency, loan obligations, club reputations, financial rules and PS4 registration constraints remain future development items.

## Planned next move
Introduce an explicit club-by-club *scenario builder* where the user can choose the realism settings, starting budgets and effective season. Keep sourced figures and simulated assumptions visibly separate. Then create a transactional transfer ledger, offer/counteroffer and registration-date enforcement. Do not activate transfers until the season-lock rule is covered end-to-end.

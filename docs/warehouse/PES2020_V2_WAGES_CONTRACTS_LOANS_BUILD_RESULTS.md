# PES V2 historical starting wages, contracts and loans — tested baseline

**Status:** Fully generated and tested as an isolated men's reference database; career integration is opt-in and has not yet been deployed.
**Platforms:** PC and PlayStation. No native PES import files or production changes.
**Review date:** 20 October 2026.

## Download and evidence

- [Completed 317,449-player wage, contract and source-loan archive](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39416831590/artifacts/12261718266)
- [Full source salary and loan model validation](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39416831590)
- [Career lifecycle and existing-loan testing](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39416686011)
- [Original 22-edition source coverage audit](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39412411641)

## Verified reference build

- 317,449 men's player rows across 22 annual editions, with complete, numeric **game-estimated weekly wages** and game contract expiry dates.
- 177,340 provisional source wage observations retained (units, weekly period and any FX conversion are assumptions, not independently verified real salaries). Remaining 140,109 rows use modelled wages.
- 10,861 source-named loan parents: **10,857 uniquely matched** within edition; four unmatchable parents remain unresolved without fictional club identities.
- Loans still have the correct borrower match registration, separate parent reference and modelled end-of-season return date. The original immutable archives and PES ratings are retained.
- Historical FIFA12–14 wages are preserved as raw source values but **excluded from salary calibration** because their underlying units/scale cannot be relied on. FIFA15 all-zero wages are also estimated, not treated as genuine salary evidence.
- The separate SQLite contains starting_player_finances, starting_source_loans, starting_club_finances and starting_finance_model, along with the pre-existing men's player/club/squad reference tables.
- The JSON audit contains model and provenance, per-year coverage and held-out error metrics, missing source wages, parent resolution, and salary estimates.

## Mathematical estimation policy

Only suitable FIFA16+ source wages train year-specific, player-level deterministic 80/20 train/test wage models. A robust typical salary after adjusting for overall rating, age and position is scaled by club wage evidence (where available) and squad-strength benchmark (when unavailable). The result is a bounded per-week wage estimate, with explicit source-versus-inferred provenance. Missing earlier editions use a 7.5% yearly game-money scaling assumption backwards from FIFA16. Missing years between anchored observations interpolate in logarithmic terms; FC27 scales from the later model. **These are simulation assumptions**, not claims of actual historical salaries.

Example source-population median simulation results: FIFA05 approx £950/week; FIFA12 £2,900/week; FIFA20 £2,640/week; FC27 £2,950/week. Variation partly reflects historical source player-pool composition, so do not treat those medians as empirical real-world inflation.

The FIFA06–14 field contract_length stores an **end year**, not years remaining. Known end years are converted to June 30 game dates with an assumed-day flag. Unknown expiries get a reproducible modelled 1–4-season contract, age-adjusted, never a fabricated historical contract date.

## Starting loan agreement game rules

The player starts in the **borrowing club's playing squad**, with contract ownership at the uniquely resolved parent club. No existing loan needs a new offer during the 30-minute window.

- Actual historic return date and wage percentage are not established by these sources. The model defaults to June 30 at starting season end, with a 50% borrower wage-share assumption, explicitly tagged.
- After **verified PES season completion**, loans return their players to their parent and release the borrower wage share. Parent payroll increases to the full wage. A parent contract that expires without renewal releases the player as a free agent instead.
- A borrower is not allowed to sell a loaned player as its own asset. Full negotiated owner-driven mid-loan transfers are still to be implemented.
- Transfers and loan returns happen transactionally and are idempotent. Historical source IDs and source wages remain immutable and source-provenanced.

## Career engine boundary

The development branch includes an optional initial-loan and payroll seed within creation of a **new** sandbox career. It is enabled only when a world dataset explicitly registers the historical finance policy and correctly maps player and parent-club IDs. Existing careers and nonhistorical datasets remain unchanged. Invalid budgets, missing contracts or contradictory loan ownership block creation rather than silently assigning fictional clubs.

**Not yet done:** Importing these historical annual worlds into the career setup app's actual world_datasets tables, mapping competition membership, creating playable historical career saves, and running end-to-end transfer-window sessions. That is the immediate next development milestone, and nothing has been deployed to Render or merged to production.

FC25 remains excluded. Faces, player skills and native PES PC/PlayStation save compatibility remain deferred.

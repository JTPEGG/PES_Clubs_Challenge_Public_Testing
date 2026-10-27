# PES Clubs Challenge — Minimal non-playable feeder model

**User-approved simplified scope — 20 October 2026.** Men's football; all changes testing branch only. No production career, saved season or game club is mutated.

## No unnecessary lower pyramid

Only the tier **immediately below the lowest playable tier** needs a non-playable team pool. For the England 2026/27 testing dataset:

| Playable lowest tier | Nonplayable source leagues needed | End of model |
|---|---|---|
| League Two (default) | National League (tier 5) | Tier 5, no lower tier required |
| National League (future playable option) | National League North AND South (tier 6) | Tier 6; no Step 3 / tier-7 clubs required |

**This replaces the former intention to build all of England's Steps 3–6 as prerequisites.** An unrelated regional tier cannot make the career invalid if nothing playable is relegated to it or promoted from it.

## Minimal data fields

A non-playable club needs only: **club identity/name**, **season-specific home competition ID**, **promotion eligibility**, and **current feeder-pool presence**. The historical initial club list must be real and date-sourced. No game squad, player ratings, bank account, transfer market budget, home venue, contract data or detailed non-playable match simulation is required.

When a season rolls over, a simple *seeded deterministic nonplayable outcome* selects actual feeder-club entrants. This is an in-game fictional league outcome (not a claim about actual historical results). The promoted clubs enter the playable tier; the clubs relegated from the playable tier replace them in its feeder pool. Both remain the correct size, even over repeated virtual seasons. Use new simulated club memberships for the next career season, not next year's real-world historic membership list.

If the National League is made playable, two simulated entrants from each of National League North/South are selected in the current streamlined testing design. North/South destinations for the four relegated NL clubs require an explicit valid regional assignment; geographical placements are **not invented**. The two lower regional divisions are terminal. Further tiers do not block the career.

## Tested implementation

- [`world_lightweight_feeder.py`](../../world_lightweight_feeder.py) is the isolated source pool, selection and rollover adapter.
- [`test_world_lightweight_feeder.py`](../../test_world_lightweight_feeder.py) checks repeatability, correct sizes, two season progression, invalid/duplicate club rejection, North/South transition and absence of deeper tiers.
- [GitHub Actions one-hop simulation](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39486211009) passed against the 367-season consolidated source register. [Validated QA artifact](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39486211009/artifacts/12292699315).
- Source club pools: official May 2026 FA National League allocations cross-checked with independent dated fixtures, 24 each (National/North/South), plus 24 independently sourced League Two members.

**Important:** This is working feeder-policy code with successful *isolated* simulated rollover QA, not a newly activated full career save. The incomplete original FIFA/FC 22-edition domestic club assignments (7,877 unresolved at last consolidated audit), country-specific boundaries and player import remain separate work. The normal historical career gate must continue to block unresolved playable clubs. Completing unrelated lower non-playable pyramids is **no longer a prerequisite**.

## Apply to other leagues

The same one-hop policy applies wherever the football system uses promotion/relegation: choose the user's lowest playable tier, source the one next-tier competition or regional groups, use their real clubs only, simulate their entrance to playable football, and stop. Closed systems (e.g. MLS) require **no** promotion feeder. Regional systems may need multiple divisions at the *one* next level, not six extra levels.

**Next actual work:** finish real historical domestic identities for the remaining playable clubs, and source a direct eligible feeder pool under each playable lower division. Do not use extra regional-depth work as a substitute for filling the essential original FIFA competition links.

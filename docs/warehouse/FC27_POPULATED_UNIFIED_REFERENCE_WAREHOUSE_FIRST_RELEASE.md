# FC27 Populated Reference Warehouse — First Working Release

**Date:** 21 October 2026  
**Repo:** `JTPEGG/PES_Clubs_Challenge_Public_Testing`  
**Branch:** `feat/fifa-pes-converter-v2-complete`  
**Status:** Validated independent immutable SQLite reference snapshot for 2026/27, **not yet hosted on PostgreSQL or bound to a live career**. PES export intentionally deferred.

## Architecture decision

The original [Warehouse Architecture V1](WAREHOUSE_ARCHITECTURE_V1.md) and [field dictionary](DATA_DICTIONARY_V1.md) remain the long-term contract. Their 16 `wh_*` tables were tested as an **additive proposed migration** referencing the existing `world_datasets`/`world_players`/`world_clubs` domain; they were **not populated or installed into an app database**.

The next concrete stage has now been implemented as a **standalone 2026/27 populated reference snapshot** in `warehouse/fc27_populated_reference_v1.sql` with `wh_fc27_*` tables. This intentionally does **not** attempt an unsafe migration over an existing `world_career_*` save. A versioned adapter/migration is still needed when moving from standalone source keys to a permanent shared PostgreSQL warehouse and existing world IDs. This is an *incremental compatible read model*, not a claim the previously proposed warehouse migration is complete.

### Reference truth vs mutable career data

- **Warehouse:** immutable edition-specific source players, starting rosters, team memberships, converted PES-style ratings, game-estimated starting contracts/wages, game-model finance capacity, promotion routes and source SHA256 manifest.
- **Career overlay:** created from an explicit frozen warehouse version. Actual current registrations, cash movements, market negotiations, tactical squad status, managerial changes, match results, morale and live contract state belong **only** to that career's tables/events. Do not mutate frozen warehouse starting registrations to simulate transfers.
- **AI engine:** eventually reads a consistent merged career context and warehouse source profile, not disconnected unversioned source tables.
- **PES editor/export:** not a warehouse dependency; parked until separately requested. The app simulates background leagues without any PES squad.

## Source systems and exact FC27 coverage

Three independently validated SQLite artifacts are read **query-only** by `scripts/build_fc27_populated_warehouse.py`:

1. FC27 world competition reference [passing run 39602792857](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39602792857): 659 original active source clubs across 53 competitions, eight European intended playable countries plus closed-but-playable MLS, 16 sporting season-end routes.
2. Reviewed 22-edition men's source wages, contracts and loans [run 39423495384](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39423495384): 17,849 FC27 original male player registrations from which **17,593** have source club IDs in the agreed 659-active-club set. The other 256 source rows remain in the archived source and are **not** assigned to unknown clubs.
3. Approved historical club game financial model [run 39427144648](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39427144648): starting club payroll, wage budget, transfer budget, remaining headroom, relative financial percentile/band and a clearly labelled **game-model** origin. All 659 active source clubs are joined on their original `club_key`.

Frozen snapshot contains:

| Entity / measurement | Count | Caveat |
|---|---:|---|
| Original club identities | **659** | Stable source keys, not duplicated across playable/background scopes |
| Original domestic competitions | **53** | 17 intended playable, including MLS |
| Registered active players | **17,593** | 256 excluded rows remain only in immutable historical archive |
| Converted core attributes | **439,825** | 25 estimated PES attributes per player |
| Converted supplementary values | **70,372** | 4 game-scale auxiliaries per player |
| Total fine-grained attribute observations | **510,197** | Every estimate marked `fifa_pes_v2_converted_model` |
| Starting contracts / wage observations | **17,593** | Wage and contract expiry provenance carried with each player |
| Starting club finance profiles | **659** | Budgets **game-model estimates**, not real cash/accounts |
| Players originally registered with intended playable clubs | **9,269** | No actual PES file needed to simulate these players in the app |
| Original real regional/national movement routes | **16** | Rule scope defined, executable career movement remains disabled |

**No unsupported assertions about managers, stadiums, personality, or audited finances.** These appear as explicit domain-level `wh_fc27_coverage_gaps`, not invented populated profiles. Primary positions and raw alternative role fields are preserved; precise position suitability remains flagged for further validation.

## Actual files

- `warehouse/fc27_populated_reference_v1.sql` — normalized independent SQLite tables, constraints, source ID FK integrity and read views.
- `scripts/build_fc27_populated_warehouse.py` — deterministic all-input population and SHA256 provenance report; refuses to overwrite an existing output; archives read-only.
- `warehouse/fc27_reference_reader.py` — read-only adapter for future app/AI career setup: competition list, starting roster, player profile and numeric attributes, source-labelled wages, club financial budgets, immediate promotion route, and known gaps.
- `test_fc27_populated_warehouse.py` and `test_fc27_reference_reader.py` — baseline schema, read-only guards, source/model provenance and no phantom entities.
- `.github/workflows/fc27-populated-warehouse.yml` — build and data-integrity validation, ships `FC27_UNIFIED_REFERENCE_WAREHOUSE_V1.sqlite` plus `FC27_UNIFIED_REFERENCE_WAREHOUSE_V1.audit.json` in a GitHub Actions artifact.

## Real project readiness and next tasks

**Achieved:** the 2027 immutable reference read model is actually populated and checked from the previously approved player, club and financial data; app read interface is available. This removes the earlier need to keep multiple different source files in business-logic call paths.

**Not yet achieved:** a permanent migration of this reference snapshot into a deployed PostgreSQL warehouse, a career dataset selector that reads only the new authoritative snapshot, a complete set of manager/personality/stadium profiles, an integration with the AI recruitment logic, or a live multi-season simulated career.

Recommended sequencing:

1. **Career integration:** introduce a versioned `dataset_id` referencing a checksum of the warehouse snapshot. Seed disposable career overlay contracts, squads and finances from the reader; prove post-seed transfers never mutate the reference warehouse. No import into production saves.
2. **AI data contract:** confirm exact fields the AI decision engine uses, resolve salary/role/reputation fallbacks and their provenance from the canonical warehouse. Test contract expiring, source loans and outside-squad club requirements.
3. **Missing domains:** add manager/stadium/institutional stature/personality only where source-backed or explicitly modelled, with separate coverage percentages and `NULL` where unknown.
4. **Game simulation:** connect complete seasonal standings to the 16 routes, including closed league background results and MLS playoffs, using app player registrations. PES game compatibility isn't a gate.
5. **Historical backfill:** bring in FC26 and others only after FC27 seeding + actual realistic AI testing are stable.

**Safety boundary:** no Render or PostgreSQL deployment, no production career mutation, no FC26 backfill and no PES editor work.

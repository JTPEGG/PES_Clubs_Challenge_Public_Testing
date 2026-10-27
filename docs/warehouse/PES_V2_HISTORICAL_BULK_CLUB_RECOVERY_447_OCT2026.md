# PES V2 — original FIFA competition bulk gap recovery

**20 October 2026 — men’s football — testing branch only — no production career writes.**

## Verified GitHub Actions

- [Expanded pinned fixture team source collection — success, 80 newly sourced league seasons](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39501727986)
- [Rebuilt 22-edition sourced competition SQLite — success, 447 league seasons](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39501911329)
- [13,104 club-year exact-source gap audit — success, 7,163 still unresolved](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39502032762)
- [Independent edition-specific FIFA15–23 EA team-ID audit — successful safety validation, 21 coincidental numeric IDs rejected](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39502708219)

Downloadable workflow evidence:
- [Historical source fixture names and checksums](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39501727986/artifacts/12302495000)
- [Consolidated competition registry, 22-edition original team-league staging](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39501911329/artifacts/12302560107)

## Reconciled source and club-identity changes

| Audited measure | Before bulk recovery | Latest passing release |
|---|---:|---:|
| Original game club-years, unchanged | 13,104 | **13,104** |
| Game editions, FC25 unavailable | 22 | **22** |
| Season-specific sourced domestic league seasons | 367 | **447** |
| External independently sourced fixture club-years | 7,073 | **8,491** |
| Original game club-years with league evidence (provisional) | 5,227 | **5,941** |
| Original game club-years not yet crosswalked | 7,877 | **7,163** |
| Individual exact-name fixture observations in register | — | **4,043** |
| Alias-name source evidence requiring identity review | 1,241 | **1,407** |
| Career-ready historical editions | 0 | **0** |

The importer **adds 80 historical league seasons and 1,418 independently sourced fixture club years** from dated, pinned OpenFootball and CC0 footballcsv sources, including Brazil, Japan, China, Mexico, Australia, Argentina and additional European systems. This led to **714 more original FIFA/FC club-year records** with source evidence. Each league source is edition-aligned: game FIFA22 starts in 2021/22 or calendar 2021, and later memberships are not automatically back-applied to earlier years.

The scripts `scripts/collect_historical_domestic_backfill.py` and `world_historical_competition_registry.py` store SHA-256 provenance, validate fixture club counts and avoid registering an edition/code already present in the earlier 367-season registry. Missing or malformed source files are quarantined; game player squads are not invented. Existing source-status, original-squad and career-readiness safeguards all passed.

**These are league evidence links, not 5,941 verified FIFA game identities or 447 complete promotion/relegation systems.** Unverified aliases, country-known homonyms and 2027 CONMEBOL continental-only teams remain blocked.

## Separate, conclusive EA game-ID source experiment

The SoFIFA 2015–23 archived men's game team dataset looked promising for restoring missing original league ID values. The source was pinned by an exact 113 MB SHA-256 digest and its original FIFA edition was compared with each original club's numeric key. The audit found **701 original edition-team-ID candidates**, **21 same-number matches**, and **0 corroborating same-club names**. Thus all 21 ID collisions are excluded as **incompatible source key namespaces**, and **zero imported same-ID league assignments** were permitted. The test has an explicit regression that an uncorroborated ID cannot assign a different club or league.

This failed candidate is useful: do not merge two datasets by a bare integer team ID unless the namespace/identity and game edition are independently verified. Its source still exists as a review artifact, not as a league-membership replacement.

## Remaining priorities

1. Recover the original game competition association for clubs with missing original league keys. Last audited: **7,163 unresolved** overall, dominated by these source-less FIFA club records.
2. Extend 2005–2024 first-team competition source coverage only for real, **same-year** club membership evidence. Prioritise actual unresolved game edition/country gaps rather than filling unrelated leagues.
3. Retain the agreed **one-hop** nonplayable model: League Two to National League; optional future playable National League to North/South only. Do not source Step 3/4 leagues merely to tick readiness boxes.
4. Map all true playable clubs to year-specific domestic competitions, then test actual saved-career season changes and dated movement boundaries. Never register a cup bucket as a home league, invent player skills, reset existing careers or claim a fully ready edition while original domestic assignments are unresolved.

**Scope remains the isolated testing repository/branch.** Original production careers, saved seasons and PES option files have not been modified.

# PES Clubs Challenge V2 — historic FIFA/FC domestic competition expansion

**20 October 2026 | Men's football | PC/PlayStation | Testing branch only**

## Validated delivery

- [Pinned English + MLS + Argentina + professional European tier source collection CI](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39457937149)
- [Rebuilt consolidated competition register, 351 league-seasons, success](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39458087320)
- [Latest gap analysis run, 8,083 unresolved and zero unmatched unique names, success](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39458233597)
- [Consolidated SQLite, edition club assignments, fixture crosswalks, movement-rule CSV and source audit](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39458087320/artifacts/12281572665)
- [Full 22-edition per-club gap and original FIFA source-group review CSV package](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39458233597/artifacts/12280678601)

### What changed

Continued from the approved source database and existing `world_historical_competition_registry.py` instead of rebuilding the original squad pipeline. Added `scripts/collect_historical_competition_supplement.py` to fetch **immutably pinned, CC0 Football.TXT match fixtures** for a division only when its edition-specific pinned JSON source was unavailable. Each match list is parsed for original team names; the declared number of teams must match the parsed teams and the source must have at least 50 genuine fixture rows. Missing, incomplete and corrupted source data is recorded and excluded rather than guessed.

The new supplement contains **47 additional independently sourced domestic league-seasons and 1,036 fixture club-season membership records**, comprising:

| Source family | New league-seasons |
|---|---:|
| Major League Soccer (US/Canada, calendar years) | 20 |
| England (previously missing Premier League/Championship/League One/League Two seasons) | 12 |
| Argentina Primera División (calendar years) | 5 |
| Spain Segunda División | 3 |
| France Ligue 2 | 3 |
| Germany 3. Liga | 2 |
| Italy Serie B | 2 |
| **Total** | **47** |

Calendar-year domestic leagues are explicitly aligned with the game's **starting year**, not its FIFA number: FIFA26 starts in 2025, so it must use **2025 MLS/Argentina** fixtures, not 2026. FC25 has no playable source database and is still excluded. No missing 2026 league teams are copied from 2025.

Two verified EA game-ID conflicts are excluded from cross-country name matching in `data/warehouse/historical_club_identity_disambiguation_v1.json`:

- FC24 `Liverpool`, EA ID `111326`: **Liverpool Fútbol Club (Uruguay)**, not the Premier League club
- FC24 `River Plate`, EA ID `112184`: **River Plate Montevideo (Uruguay)**, not the Argentine club

Both still require independent Uruguayan *domestic* memberships; the identity guard deliberately does not make a league assignment. Review queue now has **zero** unique same-name/country candidates without either a source match or an explicit ID-based exception. It does *not* mean all 1,106 current source aliases are verified; they remain candidates.

### Reconciled final source counts

| Metric | Beginning of this work | Latest validated |
|---|---:|---:|
| FIFA/FC starting editions | 22 | **22** |
| Original men's club-season records (never changed) | 13,104 | **13,104** |
| Independently sourced domestic league-seasons | 304 | **351** |
| Independently sourced fixture participant club-seasons | 5,709 | **6,745** |
| Exact game-club to fixture observations | 2,857 | **3,530** |
| Conservative identity-review aliases | 953 | **1,106** |
| Corroborated original source groups | 62 | **81** |
| Club-years with some sourced league evidence (still provisional) | 4,084 | **5,021** |
| Unresolved club-years | **9,020** | **8,083** |
| Countries with source league-season evidence | 19 | **20** |
| Fully verified career-starting editions | 0 | **0** |

The reduction of **937 unresolved club-years** is measured against the unchanged original approved 13,104 records. Distinct fixture identities, group-level evidence and genuine EA squad identity certification must not be conflated. This is staged evidence, not a ready-to-use PES option file.

### Latest unresolved reason audit

| Reason | Club-season rows |
|---|---:|
| No original FIFA league field and no sufficient individual identity evidence | **6,365** |
| Original FIFA source league group present but not independently identified | **1,676** |
| FC27 CONMEBOL continental buckets needing separate domestic division | **40** |
| FC24 Liverpool Uruguay / River Plate Montevideo identified, home domestic league unsourced | **2** |
| **Total unresolved** | **8,083** |

## Next best source investments

1. **FC27 2026/27 season:** current remaining named FIFA groups include MLS (30), Argentina's LPF (30), English League One and League Two (24 each), Spanish second tier (22), German third tier (20) and Italy Serie B (20). The pinned sources often stop in 2025/26 or 2025; obtain **2026/27 or calendar-2026** member lists from verified current-season league/federation sources, *never* copy older-season club lists.
2. **Other historical national systems:** e.g. 2021/22 Japanese J1 and Turkish Süper Lig, Brazil and more regional and feeder divisions. Check actual FIFA club IDs and pinned fixture participants before assignment. Multiple competitions called `Premier League` require country and source ID disambiguation.
3. **Acknowledge missing FIFA league group fields:** 6,365 completely unsourced club records are a separate problem from the 1,676 named ones. Expand immutable archive coverage and EA game club-ID mapping, then review conservative aliases.
4. **Movement rules and feeders:** preserve England/Germany's historical playoff regime changes. Mark MLS as a separate non-relegation competition when season-aware rule evidence is integrated; don't infer promotions or loan/transfer eligibility from an MLS fixture roster. Complete playable/nonplayable feeder teams for season-end simulation, including North/South splits and licensing restrictions.

## Safety and validation

All workflows read the original FIFA archive without writing to it. The consolidated register has passed SQLite integrity and foreign-key checks, 22-edition source count invariants, 128 dated rule rows and the no-career-launch assertions. The updated gap report reconciles all editions, and protects both known EA game-ID/country collisions.

**No historical starting edition receives a `ready` certificate.** Neither production careers nor Render production deployments have been modified. Future seasons must use simulated league results and registered eligible teams, not actual future historical results.

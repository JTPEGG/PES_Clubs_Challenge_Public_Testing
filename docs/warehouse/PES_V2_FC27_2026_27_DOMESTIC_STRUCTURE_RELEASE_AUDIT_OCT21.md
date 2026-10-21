# FC27 2026/27 — domestic competition release verification (21 October 2026)

Repository: `JTPEGG/PES_Clubs_Challenge_Public_Testing`  
Branch: `feat/fifa-pes-converter-v2-complete`  
Scope: **FC27 only**. No career gameplay integration and no FC26 backfill.

## Verified CI result

GitHub Actions: [FC27 source database and one-hop competition gap audit, passing run 39582156781](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39582156781). The run executes 11 Python tests plus builds the final SQLite, checks its foreign keys and generates the diagnostic artifact. The complete CSV of all 53 competition codes is in that run's uploaded artifact, `FC27_ACTIVE_COMPETITION_STRUCTURE_GAPS.csv`.

| Verified audit item | Value |
|---|---:|
| Immutable original FC27 archive records | 670 |
| Explicit original FC27 source exclusions | 11 |
| Derived final FC27 active club records | 659 |
| Original all-edition archive club-season records (untouched) | 13,104 |
| Derived copy club-season records after FC27-only exclusion | 13,093 |
| Final active FC27 clubs with some domestic starting competition code | 659 |
| FC27 clubs without a domestic starting competition code | 0 |
| Distinct active domestic competition codes | **53** |
| CONMEBOL continental-source clubs with explicit 2026 domestic member review | **40** |
| Source clubs in deliberately incomplete, partially licensed domestic group subsets | **18** |
| Competitions lacking an independent dated fixture membership pool in this stage | **33** |
| Competitions without linked, season-specific domestic movement rules | **43** |
| Competitions with only partial/pending external-feeder movement rules | **9** |
| Competitions with explicit no-promotion/no-relegation format | **1** |
| Existing dated pyramid topology promotion edges | **7** |
| FC27 fully verified for historical career launch | **No** |

Counts of CONMEBOL clubs and incomplete licensed subsets are computed from **club-level/source-group** tables, not the number of clubs in shared domestic league codes. Brazil and Colombia have clubs in both source groups and continental source buckets; counting per league code alone can overstate the CONMEBOL cohort.

## Excluded league implementation

The **derived active 2027 database**, as distinct from the immutable original FIFA/FC source archive, now has **zero** excluded source clubs in `edition_club_competitions` and no excluded FC27 source league-group records. Other FIFA/FC editions are unchanged. In the final copy, 11 excluded FC27 records are purged from club-keyed tables and the edition readiness totals adjusted, and the positive-join active view no longer leaks orphan rows.

Explicit guard text and regression tests are deliberately retained in *source code* so that later source imports cannot silently reintroduce the disallowed league. This is a protection rule, **not** an available league or club in the active game-facing data. The user's request to remove the league from active play is enforced; the original archived source evidence is not falsified.

## Material outstanding uncertainties

- Domestic **country and competition** mapping is not equivalent to original EA game club-ID proof. The 40 CONMEBOL review entries now each have a distinct year-specific first-tier member name and league source; they are not an official original EA team-ID crosswalk.
- The 18 partially licensed source-group clubs cannot constitute complete independent competition seasons on their own. Other real league participants must be independently sourced before such leagues are promoted to fully simulated playable structures.
- The competition-membership and movement gaps overlap; do **not** add 33, 43 and 9 as though they were distinct clubs or competitions.
- The existing English/German/Spanish rule graphs have published-season structures but unverified foreign-keyed feeder/promotion destinations. There is no safe global rule generator for all 53 competitions.
- A **single immediate feeder level** is the upper limit of derived feeder lookup. Teams from an unsupported lower-of-lower pyramid are not fabricated or promoted.
- Where country-backed official club names are abbreviated in original FC27 source, reviewed mappings remain provisional until the EA team identity can be checked against original game files (e.g. `IDV`, `Macar`, `Alianza Atltico`, `City Torque`). No new FIFA squad, invented club or placeholder player is created.

## Remaining FC27 work — do not advance to FC26

1. Add independently dated 2026/27 (or calendar 2026, as applicable) club memberships to the 33 competition codes without sufficient source fixture pools. Reconcile individually, avoiding automatic ambiguous/homonymous names.
2. Finalise the 43 missing country-specific season movement rules and finish the nine partially specified pyramid regimes. Explicitly record no promotion/relegation for closed formats.
3. Link movement destinations to **the same canonical competition code** as the actual club assignment, and supply only the immediately adjacent sourced non-playable feeder when no playable lower division exists. Preserve multi-group promotion play-offs and regional allocations rather than merging divisions.
4. Reconcile 18 partially licensed clubs against whole-season domestic competition memberships and keep them non-playable until the intended gameplay scope has a complete sourceable league pool.
5. Re-check historical career readiness **only** after the 53-code roster/topology diagnostics are clear. Current readiness gate is correctly **blocked**. FC26 has not been started.

CI summary and full competition-by-competition CSV are the authoritative release evidence; do not infer completed topology from `659/659` source club code coverage alone.

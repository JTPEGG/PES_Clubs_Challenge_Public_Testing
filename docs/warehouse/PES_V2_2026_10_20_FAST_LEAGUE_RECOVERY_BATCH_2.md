# FIFA/PES V2 — 20 October 2026 Faster Historical League Recovery: Second Batch

Testing branch: `feat/fifa-pes-converter-v2-complete`; original production careers unchanged.

## Actual delivered evidence gains

| Evidence stage | Club-season records linked | Unresolved (out of 13,104) |
|---|---:|---:|
| Prior 447 independently sourced historical league-seasons | 5,941 | 7,163 |
| Add original FIFA 15–23 game team league data (same-edition unique names) | 8,142 | 4,962 |
| Add 2008/09–2015/16 European Soccer archived fixture league pool, 11 countries | 8,544 | 4,560 |
| Add original FC26 binary game `teams`, `leagueteamlinks`, `leagues` verified by source name | **8,672** | **4,432** |

**66.2%** of the original men's club-season records now have starting domestic division evidence. A SOURCE CLUB NAME match is provisional, and these do not yet mean all FIFA identity and season-end promotion rules are verified.

### Sourced in this iteration

- The independent historical match source has 87 first-division seasons, 1,474 authentic dated fixture team memberships, 2008/09–2015/16. The underlying match database is the publicly archived [European Soccer Database](https://github.com/judithagara/European-Soccer-Database/tree/7c83ef15d74c669b92663300de8e1454441939b9), pinned binary SHA-256 `c510a881aae5f8400c74dd62f78bc1a9322d697c98ec180f8beb78d9e21f724a`. Six malformed match pairings were excluded; one incomplete league-season was withheld. Provenance is retained; original match/player data is not redistributed through the game artefact.
- Among the 1,474 dated source team entries, **402 matched original FIFA club-season records lacking any earlier league evidence**. The combination keeps conflicting/ambiguous names out and does not alter previously corroborated club assignments.
- The FC26 team, league and league-membership database source is the fixed `ViniMacacari/api-eafc-files` repository at commit `7592f1734afff43d7dbc7161565732e9ba3d28bc`. Its original binary game template exposed 799 teams, 52 leagues, and 799 team/league links. We used unique same-year original game club names and restricted to men's domestic leagues with levels 1–4. Of 499 matched source-game team/league pairs, 371 corroborate existing links and **128 add new home league evidence**.
- FIFA Index provides public FIFA05–14 league-by-league pages (e.g. [FIFA05 leagues](https://fifaindex.com/leagues/fifa05), [FIFA14 leagues](https://fifaindex.com/leagues/fifa14)), but direct scripted access was blocked (HTTP 403) from GitHub Actions. SoFIFA's documented historical API was also unavailable (HTTP 403). Those restrictions were respected rather than bypassed. Neither unsupported data nor invented club country/league was introduced.
- No FC25 original game's player records were created. No live career starts were enabled, no production database or original FIFA/PES squad was modified.

### Reproducible outputs

1. [European Soccer 11-country dated match membership collector](../../scripts/collect_european_soccer_archive_memberships.py) and [successful source audit](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39506262007).
2. [Historical matches + original FIFA club league integration](../../world_historical_european_membership_overlay.py) and [successful integrity test](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39506787823).
3. [Original FC26 club/league identification using real game binary](../../scripts/match_fc26_original_game_leagues.py) and [successful source audit](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39507150616).
4. [Final non-destructive 22-edition original game & historical fixtures SQLite overlay](../../world_historical_fc26_game_overlay.py), validated via [GitHub Actions](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39507353945). Database: `HISTORICAL_COMPETITION_REGISTER_22_EDITION_FC26_EXTENDED.sqlite`, view: `full_historical_club_starting_leagues`.
5. The final release exports `FINAL_22_EDITION_STARTING_LEAGUE_GAPS.csv` so the largest outstanding individual FIFA edition gaps can be prioritised.

### Remaining

**4,432 club-season records still do not have any corroborated source league**. The main unsourced spans are early original FIFA titles, clubs not covered by 2008–16 first-tier match data, and current editions without equivalent game league source records. Don't mix future real-world memberships into a previous game's starting season. Next source priorities: FIFA 05–08/14 original game team→league exports from accessible archival copies, plus FC24 and FC27 original game team league data where not already in the source player fields. For non-playable feeders, retain the one-level-only club-pool approach. Full career readiness remains fail-closed pending playable division graph, promotion/relegation and qualified one-hop feeders.

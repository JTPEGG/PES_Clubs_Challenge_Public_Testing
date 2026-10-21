# FIFA15 2014/15 England — first complete 92-club offline PES2020 V2 source pilot

**21 October 2026. Testing branch only.** Historical career activation remains blocked. No production Render career, original FIFA/PES V2 player archive or game import file changed.

## Real demonstrated results

| Audit | Passed value | Verified build |
|---|---:|---|
| Original 22-edition men's club-season records | 13,104 | [historic source register](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39507482880) |
| Evidence-linked club-season records after new FIFA 05–14 Spanish Segunda | 8,750 (66.8%) | [successful source overlay](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39554046026) |
| Unresolved across 22 editions | 4,354 | same |
| 2014/15 Premier + Championship + League One + League Two clubs | 20 + 24 + 24 + 24 = **92** | [92 original game club staging QA](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39556522361) |
| Original FIFA15 imported English source players (91 clubs) | 2,566 | [full player source pilot](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39558159280) |
| Source-restored FIFA15 York City real game players, team ID 1948 | 20 from pinned SoFIFA legacy FIFA15 update 2 | [original player recovery](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39557140558) |
| All 92 playable-club real source players with PES2020 V2 25+4 estimated numeric attributes | **2,586** | [independent offline pilot database](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39558159280) |
| 2014/15 Conference Premier one-hop external feeder clubs | 24 real dated clubs | [repeatable real-club transition QA](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39555901436) |

### Opening-year source exceptions correctly handled

- **Shrewsbury Town**: FIFA15 imported game catalogue labels the actual club "Shrewsbury" (source FIFA15 team ID **127**); we preserve the existing game club key, link the historical League Two name and do **not** invent a new team.
- **York City**: FIFA15 original club catalogue omitted the team despite its presence in FIFA15 (source team ID **1948**). A pinned historical SoFIFA male players archive contains **20 actual game update-2 players**, each with a real source player ID and source fields. These were restored non-destructively to an edition-scoped pilot table and converted using the project's existing PES2020 v2 25+4 rating estimator: all 500 original-player core ratings are direct or weighted source equivalents, all 80 additional numeric ratings are produced. The alternative FIFA Index team listing has **28** players from another source snapshot. **Do not fill the eight-row difference** without a matching authentic original game roster snapshot. The game source player import is not certified as opening day.
- English nonplayable feeder is **Football Conference Premier 2014/15**, 24 source clubs from Football Club History Database; no Conference North/South or Step 3 lower pyramid required with League Two lowest playable.

### Finished deliverable

Download [validated FIFA15 English 92-club offline test database](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39558159280/artifacts/12326670669). SQLite filename `FIFA15_ENGLISH_92_ORIGINAL_CLUB_AND_PLAYER_GAMEPLAY_TEST.sqlite`.

It contains:
- `competitions` — four playable English divisions + terminal nonplayable Conference pool
- `source_real_game_clubs` — exact 92 sourced game club identities and starting division
- `real_game_source_players` — 2,586 source-present original game player identifiers and 25+4 fully numeric PES2020 V2 estimates; source method retained
- `external_nonplayable_feeder_clubs` — 24 dated 2014/15 Conference club names, **no invented feeder players**
- `real_club_roster_counts` — 92 rows; every playable club has at least one player
- `edition_metadata` — explicit `career_ready=0`, `source_rosters_fully_verified=0`, `native_option_file_available=0`.

The offline database deliberately excludes actual result entry, fully source-verified opening day lineups, future promoted clubs' player generation, squad transfer simulation and a binary PES game option file. It is **not a deployed career**. A complete historical career also needs the runtime World/Career league-season registration, playoff scheduling, demotion/promotion boundary and a policy for source-real vs simulated future-season new players.

### Work still blocking historical gameplay

1. **Pilot career integration:** Wire only this edition-scoped read-only dataset into a fresh isolated world season with the dated 2014/15 English promotion and playoff rules. Never touch production history.
2. **Feeder entrants after simulated promotion:** clubs promoted from the source nonplayable Conference pool have no historical FIFA15 source squad. They will require an explicitly game-simulated future roster policy or authentic source data for that career season; they must never masquerade as players present in FIFA15.
3. **Historical season roster completeness:** original annual source archives may be partial FIFA Index crawls, and the recovered York City original-game update-2 roster has 20 players vs a different 28-player web snapshot. A numeric estimate is not proof that opening-day game rosters are complete.
4. **Remaining historical editions:** 4,354 source club-years unresolved. New matches from 2004/05–2013/14 Spanish Segunda added **78** real dated, source-linked game-club candidates. Continue bulk imports using direct same-edition source game league IDs and dated licensed fixture lists, not invented lower pyramids.
5. **Safety:** 0 of 22 editions certified career-ready. Production untouched. No false transfer updates, native Konami game file or background job claimed.

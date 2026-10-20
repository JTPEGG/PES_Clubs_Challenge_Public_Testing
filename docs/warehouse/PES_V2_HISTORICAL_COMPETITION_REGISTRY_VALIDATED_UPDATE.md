# PES Clubs Challenge V2 — Season-specific competition database, implementation update

**20 October 2026 · Men's football · PC / PlayStation · Test branch only**

## What was built and validated

**Latest expanded consolidated CI passed:** [historical competition registry run 39450980308](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39450980308).

[Download the **complete current competition-registry review package** (SQLite, memberships and 22-season rule CSV)](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39450980308/artifacts/12278501550).

The existing `world_historical_competition_registry.py` now merges the original game-club source with three pinned fixture pipelines: 2011–2027 OpenFootball, 2005–2010 England Football.TXT, and 2005–2010 multi-country CC0 Soccerverse. The 5,709 fixture-source club entries are persisted in the new `sourced_domestic_league_clubs` table. They are **source observations, not manufactured playable PES squads**.

| Audit | Validated |
|---|---:|
| FIFA/FC starting editions | 22, excluding missing FC25 |
| Men's club-season records preserved | 13,104 |
| Independent domestic league-season source records | **304** |
| Exact game-club matches to independent league fixtures | **2,857** |
| Additional unique conservative alias review candidates | **890** |
| Provider source league groups independently corroborated | **62** |
| Club-season records with some supported domestic-league reference | **4,021** |
| Still unresolved or insufficiently proven | **9,083** |
| Historical competition source countries | **19** |
| All independent domestic source-team memberships (including unlicensed/nonplayable clubs) | **5,709** |
| Dated England/Germany movement rule records | 128 |
| Historic nonplayable National League club-season feeder entries | 239 |
| Source-backed promotion/relegation graph edges for 2025/26 and 2026/27 | 14 |
| Boundary pools still requiring completion in existing graph | 6 |
| Full career-starting editions ready | **0** |

Source evidence:
- [Pinned 2010/11–2026/27 domestic league fixture membership (232 league-seasons, 4,297 source team memberships across available countries)](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39449937724)
- [Pinned multi-country 2004/05–2009/10 first divisions (48 league-seasons, 860 source team memberships in eight countries)](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39450520785)
- [Pinned English 2004/05–2009/10 Football.TXT league memberships](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39443877744)
- [Historical English National League independent feeder-membership check: 10 seasons, 239 source club-season entries](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39447460963)
- [English German Spanish date-scoped first promotion/relegation graph](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39442462702)

## Important distinctions

**Independent game-club identity**: A unique same-season source club/fixture name match is an *audit fact* linking two source lists, not official PES roster validation. The 890 unique normalized names (e.g. Arsenal vs Arsenal FC) remain **candidates** requiring review. No fuzzy assignment, namespaced ID collision or fabricated missing teams.

**Domestic vs continental**: FC27's original FIFA source includes 40 club records in CONMEBOL cup buckets. These are continental competition memberships, NOT the clubs' home league tiers. They are **not** silently placed into a domestic division.

**Rule regime vs complete competition**: The dated rule graph now reflects the German 3. Liga starting in 2008/09, 2017/18 six-team National League play-offs, and 2026/27 six-team Championship play-offs. Formal historic rule exceptions, actual club eligibility and promotion destinations at the nonplayable boundary still need verification. 128 dated rule records do **not** mean 128 completely simulated and populated league boundaries.

**Feeder source vs playable club**: The 239 National League entries are real season-specific fixture participants, *not* invented PES players or complete squads. The real 2024/25 feeder evidence is retained independently even though there is no playable FC25 source edition. The 2026/27 National League source and North/South lower clubs need completion.

**Fail closed**: The historical career engine will not launch a normal save without a fully verified competition certificate. Existing player/squad imports for FIFA26/FC27 remain QA-only snapshots; override is available only when explicitly creating isolated technical smoke tests. No Render production app, previous saved career, player contract, or original archived fixture was changed.

## Next development, in priority order

1. **Finish season-specific club-to-league matches** by expanding independently sourced full league tables and alias checks. First handle the 9,083 original club-season mappings without defensible home competition evidence; the 890 unique alias candidates can be checked quickly against source club IDs and annual rosters.
2. **Extend and certify competition association coverage** beyond the now sourced 19 countries, including Scandinavia, Brazil and USA. The new Scottish, Dutch, Portuguese, Belgian, Turkish, Mexican, Argentine and other fixture sources establish club-year observations, **not** verified historical movement formats. Each requires season-dated promotion, play-off, licensing, and financial context. MLS, A-League and other closed/semi-closed leagues need explicit **no direct promotion/relegation** rules rather than unknown transitions. MLS, A-League and other closed/semi-closed leagues need explicit **no direct promotion/relegation** rules rather than unknown transitions.
3. **Complete lower-tier feeder pools** (National League North/South and other countries' regional feeders) without fabricating a player database for nonplayable clubs. Decide which clubs enter the playable world after seasonal league movement, based on genuine source pool and licensing.
4. **Add historical cup and continental qualification graphs** (separate from domestic league movement), versioned by season.
5. **Test season-end simulated movement**, with actual manager-season standings feeding into the next season's new league membership—not real future football tables.
6. Issue per-edition **competition readiness certificates only when all hard blockers clear**, then enable the manager career selector for that historical year.

The starting database is **substantially better evidenced than the original league-name-only FIFA catalogue**, but it is **not yet an accurate completed 22-year football pyramid**. Accuracy takes priority over turning unresolved competitions into seemingly complete careers.

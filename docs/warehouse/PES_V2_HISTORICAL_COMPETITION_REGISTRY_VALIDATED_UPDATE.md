# PES Clubs Challenge V2 — Season-specific competition database, implementation update

**20 October 2026 · Men's football · PC / PlayStation · Test branch only**

## What was built and validated

**Final consolidated CI passed:** [historical competition registry and feeders run 39447900955](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39447900955).

[Download the **complete current competition-registry review package** (SQLite, memberships and 22-season rule CSV)](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39447900955/artifacts/12276398483).

The new `world_historical_competition_registry.py` creates one reproducible season-specific database from *unchanged* original PES/FIFA source clubs plus individually pinned public-domain historical fixture/club evidence.

| Audit | Validated |
|---|---:|
| FIFA/FC starting editions | 22, excluding missing FC25 |
| Men's club-season records preserved | 13,104 |
| Independent domestic league-season source records | 176 |
| Exact game-club matches to independent league fixtures | 2,029 |
| Additional unique conservative alias review candidates | 805 |
| Provider source league groups independently corroborated | 42 |
| Club-season records with some supported domestic-league reference | 3,015 |
| Still unresolved or insufficiently proven | **10,089** |
| Dated England/Germany movement rule records | 128 |
| Historic nonplayable National League club-season feeder entries | 239 |
| Source-backed promotion/relegation graph edges for 2025/26 and 2026/27 | 14 |
| Boundary pools still requiring completion in existing graph | 6 |
| Full career-starting editions ready | **0** |

Source evidence:
- [Pinned 2010/11–2026/27 domestic league fixture membership (England, Germany, Spain, Italy, France)](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39443264830)
- [Pinned English 2004/05–2009/10 Football.TXT league memberships](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39443877744)
- [Historical English National League independent feeder-membership check: 10 seasons, 239 source club-season entries](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39447460963)
- [English German Spanish date-scoped first promotion/relegation graph](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39442462702)

## Important distinctions

**Independent game-club identity**: A unique same-season source club/fixture name match is an *audit fact* linking two source lists, not official PES roster validation. The 805 unique normalized names (e.g. Arsenal vs Arsenal FC) remain **candidates** requiring review. No fuzzy assignment, namespaced ID collision or fabricated missing teams.

**Domestic vs continental**: FC27's original FIFA source includes 40 club records in CONMEBOL cup buckets. These are continental competition memberships, NOT the clubs' home league tiers. They are **not** silently placed into a domestic division.

**Rule regime vs complete competition**: The dated rule graph now reflects the German 3. Liga starting in 2008/09, 2017/18 six-team National League play-offs, and 2026/27 six-team Championship play-offs. Formal historic rule exceptions, actual club eligibility and promotion destinations at the nonplayable boundary still need verification. 128 dated rule records do **not** mean 128 completely simulated and populated league boundaries.

**Feeder source vs playable club**: The 239 National League entries are real season-specific fixture participants, *not* invented PES players or complete squads. The real 2024/25 feeder evidence is retained independently even though there is no playable FC25 source edition. The 2026/27 National League source and North/South lower clubs need completion.

**Fail closed**: The historical career engine will not launch a normal save without a fully verified competition certificate. Existing player/squad imports for FIFA26/FC27 remain QA-only snapshots; override is available only when explicitly creating isolated technical smoke tests. No Render production app, previous saved career, player contract, or original archived fixture was changed.

## Next development, in priority order

1. **Finish season-specific club-to-league matches** by expanding independently sourced full league tables and alias checks. First handle the 10,089 original club-season mappings without defensible home competition evidence; the 805 unique alias candidates can be checked quickly against source club IDs and annual rosters.
2. **Extend competition association coverage** beyond England/Germany/Spain/Italy/France using official league membership records and dated country league structures, including Scotland, Netherlands, Portugal, Belgium, Turkey, Scandinavia, Brazil, Argentina, Mexico, USA, etc. MLS, A-League and other closed/semi-closed leagues need explicit **no direct promotion/relegation** rules rather than unknown transitions.
3. **Complete lower-tier feeder pools** (National League North/South and other countries' regional feeders) without fabricating a player database for nonplayable clubs. Decide which clubs enter the playable world after seasonal league movement, based on genuine source pool and licensing.
4. **Add historical cup and continental qualification graphs** (separate from domestic league movement), versioned by season.
5. **Test season-end simulated movement**, with actual manager-season standings feeding into the next season's new league membership—not real future football tables.
6. Issue per-edition **competition readiness certificates only when all hard blockers clear**, then enable the manager career selector for that historical year.

The starting database is **substantially better evidenced than the original league-name-only FIFA catalogue**, but it is **not yet an accurate completed 22-year football pyramid**. Accuracy takes priority over turning unresolved competitions into seemingly complete careers.

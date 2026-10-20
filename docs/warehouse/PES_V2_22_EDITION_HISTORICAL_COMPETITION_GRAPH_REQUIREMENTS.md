# PES V2 — complete historical men's competition hierarchy: audited requirements and implementation

Date: 20 October 2026. Platform: PC / PlayStation. Scope: **all 22 FIFA/FC starting seasons 2004/05–2026/27 (FC25 excluded)**.
**Status: In progress. NO historical edition is fully competition-validated and career-ready.** The previous FIFA26/FC27 player/contract imports remain technical **QA sandboxes only** until the graph below is complete. Original career saves and production unchanged.

## User's locked requirement

Every club must have an accurate, edition-specific *domestic competition* and a known league/country/tier. Every division in a playable season must have the correct promotion destination, relegation destination, automatic allocations, play-off bracket and other qualifying conditions. Non-promoting systems (e.g. closed leagues) must state that explicitly rather than be left `NULL`.

No actual live/saved career may begin with unknown competitions. Missing entries are **blockers for career activation**, not random default nations, divisions or fixtures.

Don't confuse a source FIFA squad grouping with a football league: FC27 has 20 squads in a `CONMEBOL Libertadores` group and 20 in `CONMEBOL Sudamericana` — those are continental competitions, not a team's home domestic division. No automatic promotion or relegation can be based on these lists.

## Audit of original source

[Validated all-edition, 13,104-club competition audit](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39442462702).
[Download detailed CSV and country-pyramid graph review](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39442462702/artifacts/12275112217).

The original FIFA player source files contain:
- 9,716 club-season records with **no** source league field.
- 2,968 further club-season entries where a league label exists but the corresponding *verified canonical competition/country/rule system* is not yet established.
- 40 FC27 club records placed in **continental cup source buckets**, not defensible domestic league assignments.
- 380 club-season records (190 each from FIFA26 and FC27) **directly mapped** from distinct source league IDs/labels to top English, German and Spanish divisions as a first confirmed identification stage, with their dated regulation topology attached.

These are starting source-data classifications; they DO NOT mean 380 individual club-season entries have complete future promotion/relegation feeder pools.

## Independent historical competition sources — now ingested

**Pinned OpenFootball, CC0 public domain:**

1. [2010/11 onward: 152 league-season source files, 1,694 provisional exact source-club-name matches, 1,444 needing name identity review](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39443264830). PIN `openfootball/football.json@e6744429ee395bc86f247348c6184bb08d4eb361`. Covers major English, German, Spanish, Italian and French domestic tiers where the source edition file exists. Fixture team pairs identify season membership; source files are not fabricated club rosters. Download [source evidence CSV](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39443264830/artifacts/12275033315).

2. [2004/05–2009/10: 24 English tier-1-to-4 season source files, 552 source-team entries, 335 provisional exact game-club matches, 217 identity-review cases](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39443877744). PIN `openfootball/england@9ee7a0c351805c99cc334478a9bf04b7d0432fec`. Historic Football.TXT match outcomes are parsed only for club/team names; no fuzzy matching, no fabricated team entries. [Download older English season files CSV](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39443877744/artifacts/12274008661).

**Do not sum counts as distinct final memberships:** Source-name matches and existing source league matches can overlap, and all currently remain staged until edition-specific competition identity/cross-season verification succeeds.

Other sources researched:
- [RSSSF historical domestic tables and country-by-country promotion records](https://rsssf.org/histdom.html) for historical league, boundary and country coverage.
- [EFL 2025/26 full regulations](https://images.gc.eflservices.co.uk/6a32d710-5b0b-11f0-ad0f-97502a343283.pdf), plus [the official March 2026 announcement](https://www.efl.com/news/2026/march/05/efl-statement--sky-bet-championship-play-off-format/) expanding the Championship play-offs from four contenders to six **starting in the 2026/27 season**.
- [DFL German promotion/relegation explainer](https://www.bundesliga.com/en/bundesliga/news/how-does-promotion-and-relegation-work-in-the-bundesliga-10645) for Bundesliga/2. Bundesliga/3. Liga automatic and inter-divisional playoffs.
- [La Liga promotion/relegation 2025/26](https://www.laliga.com/noticias/equipos-que-bajan-a-segunda) and [the lower Segunda/Primera Federación boundary](https://www.laliga.com/noticias/descensos-segunda-division-24-25).
- [UEFA access lists](https://www.uefa.com/nationalassociations/uefarankings/accesslist/allcompetitions/) for continental qualification, separately from domestic league movements.

## Data tables to finalise before allowing careers

1. `competition_identity`: country/association, stable competition ID, sport category men, competition type (domestic division, knockout cup, continental cup, closed league, etc.), calendar-year vs split-year season format, valid editions, canonical league label and aliases.
2. `competition_season`: source start edition, year, league size, tier, verified source, capacity, calendar anchor and historical exceptional changes.
3. `club_competition_membership`: every club's single home domestic division for that exact starting season; source unique club reference, dates, evidence, verification confidence. Clubs in continental cup source buckets need **separate domestic membership**, not a fake continental pyramid.
4. `season_movement_rules`: from division, to division, direct slots, playoff entrants/rank/format, relegation slots, inter-divisional ties, promotion eligibility/licensing and edition-specific exception rules. Source URL per edge.
5. `boundary_eligible_teams`: verified clubs from non-playable feeder leagues. This avoids a League Two club being relegated into an empty league or an invented promoted opponent appearing from nowhere. Country-specific regional routing may need additional information.
6. `continental_qualification_rules` and `domestic_cup_entry_rules`: these are **not promotion/relegation**. Historical UEFA competition qualifying places change over time with access lists. Knockout cups, continental events and international teams are separate types.
7. `career_competition_verification`: a strict one-row-per-edition certificate only if all registered clubs and every future-season competition movement destination can be resolved deterministically.

## Implemented dated rule graph

`world_historical_competition_topology.py` includes separate England, Germany and Spain graphs for 2025/26 and 2026/27 (9 directly sourced divisions plus lower-boundary stubs).
- England Premier League -> Championship -> League One -> League Two -> National League. Default EFL standard rules plus 2026/27 six-team Championship playoffs; other seasonal changes require dated evidence.
- Germany Bundesliga -> 2. Bundesliga -> 3. Liga -> Regionalliga. Inter-divisional play-off ties are preserved as ties, NOT converted into unconditional relegations.
- Spain La Liga -> Segunda División -> two-group Primera Federación. Additional group club pools still need to be sourced.
- Promotions out of and into lower non-playable divisions currently have an **external club pool required** flag. This is not a “known” full-world career graph until the actual team pool is supplied.

## Safety gate already enforced

`world_careers.start_sandbox` now blocks PES V2 historical datasets that have no `ready` verification certificate for complete competitions. The technical import smoke tests pass only using an **explicit QA-only override**, and verify normal creation first fails without changing the source or creating a save. Read-only selector marks imported squads `competition structure pending`, not career-ready. No live app deployment.

## Next priorities

1. Merge the independently sourced historical membership observations into season-specific domestic league identities. Review name aliases and homonymous clubs rather than fuzzy merge. Expand 2004–2010 beyond England via RSSSF/country public sources.
2. Prioritise English EFL levels 1–5, then German 1–4, Spanish 1–3, Italian 1–3, French 1–3. Preserve 2008 German 3. Liga creation and other real historical structural changes, not one rigid league graph across all seasons.
3. Expand to every FIFA-listed country and competition, including calendar-year South American and MLS leagues, where some leagues have **no promotion/relegation**. Avoid assigning federation participation pools to domestic leagues.
4. Source lower-league eligible clubs and any cross-country/cross-league transitions. Resolve cups and UEFA qualification as separate graphs, versioned by season.
5. Add a full-time simulator integration that uses the simulated season's final standings, not future historical standings, to determine promotion and relegation **after the chosen starting season**.
6. Only then issue a per-season `ready` certificate and enable that starting year's full career setup.

**All 22 historical editions currently remain blocked for full-career activation.** We have a credible initial data extraction pipeline and validated key rule changes; this is not yet a complete verified world.

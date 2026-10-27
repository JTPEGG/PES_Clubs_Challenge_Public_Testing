# PES V2 — Fast historical club home-league recovery

**As at 20 October 2026. Testing branch only.** This is a materially faster follow-on from the sourced competition registry, not a completed full career certification.

## Results actually executed and validated in GitHub Actions

| Measure | Before | After |
|---|---:|---:|
| Original 22-edition men's club-season records | 13,104 | 13,104 |
| Domestic fixture-supported league-evidence records | 5,941 | 5,941 |
| Additional original game league assignments, independent of fixture coverage | 0 | **2,201** |
| Club-season records with at least one usable starting home-league evidence identifier | 5,941 | **8,142 (62.1%)** |
| Unresolved without any available starting-division evidence | 7,163 | **4,962** |
| Registered dated external fixture league-seasons | 447 | 447 |
| Original FIFA game league groups recovered (FIFA 15–23) | 0 | 387 |
| Game league groups independently corroborated by >=3 fixture club matches | 0 | 182 |
| Career-ready editions | 0 | 0 |

### Why this is more productive

A club's actual league **in its original FIFA game** is a valid primary source for its *game starting division*. It need not first appear in a separately maintained historic fixture file if that competition source is missing. The archived FIFA 15–23 source was fixed to an immutable revision and SHA256-verified; game clubs join ONLY to source teams from the same edition and by uniquely matching club names. The source is a dated game-league identity, **not** permission to invent player squads, movement rules or lower-league clubs.

The direct game-source matching found 4,697 eligible unique club-season pairs; 2,496 already had source fixture evidence and 2,201 filled gaps. Sixteen name conflicts were isolated. An additional abbreviated-name pass over the existing fixture sources produced eight unique candidate matches but did not significantly affect the major source deficit. A trial of additional abbreviated game team names resolved no new real records in the 2015–23 archive and was safely validated as zero additional matches.

### Reproducible work products

1. [Pinned, same-edition game league parser and QA](../../scripts/match_original_fifa_game_leagues.py), [successful source run](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39504234946).
2. [Original-source game-league overlay](../../world_historical_game_league_overlay.py), [successful consolidated audit](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39505095998).
3. Download the consolidated artifact from the Actions run. Its SQLite file is named `HISTORICAL_COMPETITION_REGISTER_WITH_ORIGINAL_FIFA_LEAGUES.sqlite`. The unified view `historical_club_starting_leagues` gives each source FIFA club edition, club key/name, home division evidence, evidence origin, and original game league name/tier where available. Importantly, `GAME:<edition>:<league_id>` is scoped to a single FIFA edition and is not yet a fully verified interdivision pyramid identifier.
4. `GAME_STARTING_LEAGUE_COVERAGE_BY_EDITION.csv` is a clear batch-prioritisation report. Also included are game league to independent fixture competition crosswalk review and original game league inconsistency review.

### Safeguards and still-needed work

- This **does not activate historical careers**. Promoted/relegated club movement needs each competition to have an actual destination and immediate eligible feeder club pool. The one-hop-only feeder policy still applies.
- The immutable original FIFA squads, sourced fixture register and existing saves are unchanged.
- Where two same-edition game clubs share a name, or archived source updates disagree on the team's league, the join stays on review rather than silently selecting a destination. No club from another edition is substituted.
- Many of the remaining **4,962** are from years outside the archived FIFA 15–23 game team source or clubs that have no same-edition league-source match. These now need *additional original-game league source records or historically dated memberships* rather than more low-value name normalisation.
- The standalone/source-backed SQLite overlay and view are **not wired to live career creation**. The original fail-closed gating stays in place until playable starting assignments, future movement and minimal feeder boundaries are validated.

### Next development focus

Obtain a reliable source-game team league export for FIFA 05–14 and FIFA 24/FC 26–27 where not already resolved. Re-use this **same-edition name and league-ID join** in a batch; use manual reviews only for genuinely conflicting names. Prioritise filling *playable division* memberships and immediate one-level feeder graph, not low regional leagues.

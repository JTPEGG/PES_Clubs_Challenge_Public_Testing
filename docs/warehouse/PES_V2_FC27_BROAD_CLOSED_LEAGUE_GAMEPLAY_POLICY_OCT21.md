# FC27 — Broad closed-league gameplay policy (21 October 2026)

**Repository:** `JTPEGG/PES_Clubs_Challenge_Public_Testing`  
**Branch:** `feat/fifa-pes-converter-v2-complete`  
**Verified:** [successful GitHub Actions run 39590924215](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39590924215), **28 Python tests passed**.

## User's design decision

The user specifically requested that minor leagues including **South Korea, Romania, Sweden and Norway** stay closed, and authorised the same approach for a substantially broader group. Aim to stop wasting development effort on unneeded lower-league feeders while retaining all original source clubs, their domestic assignments, career/job-market possibilities and transfers.

A *closed division in the FC27 game* means sporting promotion and relegation are disabled; it does **not** mean the club is deleted, the club must be made playable, or the original real-world historical regulations are rewritten.

## Effective 2027 competition scope

| Setting | Number |
|---|---:|
| Original eligible FC27 teams retained | **659 / 659** |
| Active domestic competition codes | **53** |
| Closed game movement leagues | **32** |
| Open game movement leagues | **21** |
| Active named adjacent one-hop lower feeder divisions without registered original squads | **9** |
| New original club identities invented | **0** |
| Historical career gameplay activated | **No** |
| FC26 backfill started | **No** |

The 32 closed league codes consist of **30** from the 34 previous simplified source-group policies, **Swiss Super League** as one additional closure overriding its previously mapped source movement, plus **MLS**, already supported as a no-promotion/no-relegation league.

### 30 closed from previously 34-member delegated policy

- United Arab Emirates, Australia, Azerbaijan, Bulgaria, Bolivia, Brazil, Chile, China, Colombia, Cyprus, Czech Republic, Denmark, Ecuador, Finland, Greece, Croatia, Hungary, Ireland, South Korea, Mexico, Norway, Peru, Paraguay, Romania, Saudi Arabia, Sweden, Thailand, Ukraine, Uruguay, and Venezuela.
- **Original Korean 2026 K League 1: 12 clubs preserved.** The previously staged simulation assumption to expand it to 14 in 2027 is **superseded** for game purposes; the 2026/27 FC27 world freezes this league at the original 12. This intentionally differs from real-world Korean expansion and needs no invented K League 2 entrants.
- The previous 34-code group now keeps only **Argentina, Poland, Turkey and Italy Serie B** open. Italy Serie B to Serie A retains the earlier user-approved mandatory 3rd–8th promotion play-offs; Italy Serie C to Serie B remains the separately disclosed four-team direct-game exchange rule.
- Greece's four original FC27 clubs stay available in the game database. No artificial new Greek top-flight squads or lower-league entrants are created.
- Swiss Super League's old sourced promotion/relegation details, including conditional barrage, are still in the **historical source table** but have zero effective *game* movements.

### Open movement division scope

The other **21 of 53** domestic competition codes remain open for potential simulated movement, including:
- England (Premier League, Championship, League One, League Two)
- Germany (Bundesliga, 2. Bundesliga, 3. Liga)
- Spain (La Liga, Segunda División)
- France (Ligue 1, Ligue 2)
- Italy (Serie A, Serie B)
- Scotland (Scottish Premiership)
- Netherlands (Eredivisie), Portugal (Primeira Liga), Belgium (Pro League), Austria (Bundesliga)
- Turkey (Süper Lig), Poland (Ekstraklasa) and Argentina (Primera División)

These 21 are **game movement scope**, not a declaration that every competition has a finished playable player-squad/eligible-feeder roster.

### Effective data structures

- `data/warehouse/fc27_remaining_34_gameplay_movement_policy.json`: source-group game rules, 30 explicitly closed, four remaining open, each closure recording its rationale. Version **v2** supersedes the old v1 34-code open movement assumptions.
- `world_fc27_remaining_movement_game_policy.py`: validates approved mode changes, zeroes closed leagues, preserves original club counts, creates **only four** named lower feeder nodes from the delegated 34-code group.
- `world_fc27_broader_closed_league_scope.py`: whole-53-code decision table `fc27_effective_world_league_movement_scope`, preserving original membership/teams. Additional Swiss historical source override in a separate game-scope table, **not** by rewriting historical regulations.
- `fc27_effective_additional_movement_after_world_closure`: authoritative effective sourced movement with Switzerland zeroed, while prior explicit Italy/Austria game decisions remain.
- `fc27_effective_named_immediate_game_feeders`: authoritative **nine** remaining active *named* lower feeder identities (four delegated plus five sourced) with no fabricated rosters, and no feeder required for a closed league.
- The full **53-code competition readiness audit** now reports `gameplay_closed_leagues_across_entire_fc27=32`, `gameplay_open_leagues_across_entire_fc27=21`, and `gameplay_remaining_effective_feeders_without_club_rosters=9`.

**Historical source code, data and test safeguards remain intact.** A league's real-world movement arrangements are not relabelled as official closed formats. No original archived edition, source club assignment, player or production career is mutated.

## Remaining FC27 work

1. Prioritise **genuine clubs only for the nine named adjacent lower divisions** if an open playable league actually needs incoming teams. The existing National League 24-club dated feeder dataset remains separate.
2. Certify which of the 21 open movement competitions are *playable* and which need only a source-backed one-hop feeder or a non-playable season-end club exchange.
3. Implement promotion/relegation season-end actions and game-calculated play-off winners using the **effective** game-scope rules, not blindly every historical source regulation or obsolete v1 policy.
4. Check conditional and regional allocation gaps **only for open, actually simulated** pyramids, not for the 32 closed leagues.
5. Keep career-readiness and FC26 backfill blocked until sufficient FC27 eligible club identities/movement integration exist.

This deliberately prioritises a working, coherent football-management challenge over unnecessary realism in peripheral competitions.

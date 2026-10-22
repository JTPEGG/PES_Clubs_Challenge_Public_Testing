# PES Clubs Challenge — FC27 2026/27 gameplay simplification decisions

**Decision date:** 21 October 2026  
**Scope:** FC27 development database only; do not alter the historical source data, original production application, or careers.

## Design principle: favour sensible, transparent, playable rules

The game does not need to model every league's unusual regulatory exception. Use an ordinary, credible football rule when exact licensing, exceptional eligibility or rare format triggers would obstruct development. Keep the original independently sourced league regulations for provenance, store **effective game-specific rules in a separate table**, and identify every deliberate departure from real life to the user. Ensure each promotion/relegation route preserves the right number of teams, and don't invent club identity or claim a feeder has a real squad when it doesn't.

### Assumption log

| ID | League, season | Game rule | Real-world complexity intentionally ignored | Origin |
|---|---|---|---|---|
| FC27-GAME-001 | Italy Serie B → Serie A, 2026/27 | **1 final promotion via 3rd–8th play-offs every season**, in addition to 1st and 2nd automatic: **3 promoted / 3 relegated**. Never bypass play-offs on a points-gap trigger | Possible real-world direct third promotion where point-gap criteria apply | User approved 21 October 2026 |
| FC27-GAME-002 | Austria 2. Liga → Bundesliga, 2026/27 | **Champion promoted automatically, bottom Bundesliga team relegated** every season. Exactly **1 up / 1 down**, no tie | Licence requirements, eligibility of other second-tier clubs, exceptional no-exchange seasons | User approved 21 October 2026 |

These **game rules** are not claims about exact official competition regulations.

The original rules are retained in `fc27_additional_movement_boundaries`, the two game overrides in `fc27_user_approved_movement_game_rules`, and the `fc27_effective_additional_game_movement_rules` view exposes the game-specific outcome with `effective_rule_provenance`. The original 659 clubs, the 33 accepted membership groups, and all previous competition alignments remain unchanged.

**The rule has been recorded in the development database, not yet activated in the career gameplay engine.** The career readiness check remains off until the competition world and eligible feeder teams are ready.

## Proposed repeatable judgement calls

For future leagues, choose the least complex workable rule, normally:

1. Retain ordinary automatic promotion/relegation places and common play-offs where they add genuine football interest.
2. If licensing, financial eligibility or an unusual administrative exception would make the simulation fragile, explicitly document a simple alternative.
3. If a lower division is not playable, reference the real division and its limited one-level feeder pool rather than inventing a club, squad or league.
4. Keep a record per exception: original source rule, effective game rule, exact number up/down, relevant country/season, and reason.
5. Tell the user whenever such a decision is made; don't quietly describe it as confirmed real-world fact.

No further implicit movement rule assumptions were applied in this particular change beyond FC27-GAME-001 and FC27-GAME-002.

**Automated quality checks:** `test_world_fc27_movement_gameplay_policy.py` verifies the exact effective movement slots, full original historical regulation retention, rejection of unauthorised changes and that readiness remains false.

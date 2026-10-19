# Continuous pyramid reputation model: rep-pyramid-v2

## Why v2 was necessary
The original `rep-prototype-v1` gave every club in a division the same large base score.
That made a bottom-end Premier League club such as Hull substantially more attractive
on paper than a strong Championship club such as West Ham, despite the imported
reference squad ratings showing West Ham's top-16 squad is stronger.

The new model **uses a single playing-strength scale from League Two to the
Premier League**. The club's competition remains relevant but is NOT an absolute
barrier. The v1 tables are retained as immutable legacy snapshots.

## Formula

This is a **simulation** of current sporting appeal, not actual club reputation,
institutional prestige, expected league position, verified finances or signing likelihood.

Using the sixteen highest source OVR ratings assigned to each club within the
selected season snapshot:

```text
strength_component = round(35 + 2.3 × (average_top16_overall − 60))
context_adjustment = Premier League +4 | Championship 0 | League One −4 | League Two −8
rank_adjustment    = top ~16% of squads in division +1 | bottom ~16% −1 | others 0
sporting_appeal    = clamp(strength_component + context_adjustment + rank_adjustment, 10, 99)
```

The ranks are based solely on comparative **source squad ratings**, not points,
results, betting odds or the real/live league table. The indicator is a relative
squad-strength proxy that *may* inform a later prospects model; it is not a
promotion or relegation forecast. Incomplete leagues with no source ratings
receive an explicit **Unknown**, not a fictitious carried-over value.

Versioned output is stored in independent tables
`world_pyramid_club_appeal` and `world_pyramid_league_strength`, keyed by
`dataset_id`, `model_version`, and club/competition ID. Existing v1 entries
and any career finances, agreements or source data are not modified.

### Illustrative 2026/27 source-derived comparisons

| Club | Division | Top-16 OVR mean | Provisional v2 sporting appeal |
|---|---|---:|---:|
| Arsenal | Premier League | 85.31 | 98 |
| Hull City | Premier League | 73.69 | 69 |
| West Ham United | Championship | 76.25 | 73 |
| Leicester City | League One | 69.94 | 55 |
| Bolton Wanderers | Championship | 68.00 | 52 |
| Salford City | League Two | 64.38 | 38 |
| Burton Albion | League One | 63.44 | 38 |

These are generated solely from the 2026/27 imported EA reference snapshot
and explicit formula, **not verified player consent, historical club prestige,
current league standings, or real promotion chances**.

Under this mechanism, the strongest club in the division below can rival
the weakest club in the division above, across *every* English-league boundary.

## Transfer decision rules
The career engine's `player_move_interest` now reads versioned v2 snapshots,
without reverting to v1's large tier cliff when source data are missing.

- Comparable scores across adjacent divisions: open to talks, not automatically
  rejected simply because the league is lower.
- A meaningful sporting decline (10+ rating points, or certain larger two-tier
  drops) requires playing-time assurances and stronger wage requests.
- Large declines (28+ points, or some 18+ point two-tier drops) cause the
  prototype to refuse discussions regardless of wages.
- Scores unassessed: the game does not infer player enthusiasm.
- Individual playing time, player ambition, agent character, actual league
  position, expected career development and competing offers need further work.

These are intentionally transparent **initial gameplay gates**, not claims
about real players' decisions. Agent agreement is followed by manager
confirmation and summer-only PES registration.

## Job market
The hypothetical Job Eligibility Lab uses the v2 sporting-appeal scale and
different thresholds within and across divisions. However, this is **not**
the real managerial job board, and no actual performance, interviews or offers
are invented. Actual manager reputation will be derived only from logged
challenge results.

## Inspect and compare

- Main audit: `/world/reputations`
- Direct comparison: `/world/reputations/compare?a=Hull+City&b=West+Ham+United`
- Club detail: `/world/reputations/v2/club/<club_id>`
- Legacy v1 comparison: `/world/reputations/legacy`
- Hypothetical manager jobs: `/world/reputations/jobs?manager=30`

## What still needs development

A separate **institutional prestige** score derived from documented history
and supporter/infrastructure evidence. That will allow the simulator to
distinguish Arsenal and Hull beyond current squad strength, without assigning
pretend achievements to clubs.

A genuine **dynamic prospects** component should consume only verified
career league results and objective history, and update club reputation gradually
across seasons. Today's snapshot does not itself predict promotion/relegation.

For alternative starting seasons, import source-qualified ratings for that
specific year; v2 will never use 2026/27 ratings for 2004/05.

## Verification
Run `python -m unittest -v test_world_reputation_v2 test_world_reputation test_world_careers test_world_career_play`.
A live Render deploy establishes that the application boots; it does not
alone verify every HTTP route or test case.

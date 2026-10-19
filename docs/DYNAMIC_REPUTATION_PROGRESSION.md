# Dynamic Reputation & Historical Prestige — Development Milestone

Version: `rep-career-progression-v2` (sporting opportunities `rep-season-opportunities-v1`)

## October 2026: Cup and continental opportunities

Cup trophies and continental participation now influence **next-season sporting
appeal**, separately from the underlying division/form/squad calculation.

| Distinct outcome | One-season sporting opportunity bonus |
|---|---:|
| FA Cup winner | +3 |
| League Cup winner | +2 |
| Champions League participation | +5 |
| Europa League participation | +3 |
| Conference League participation | +2 |
| Champions League trophy | +4 |
| Europa League trophy | +3 |
| Conference League trophy | +2 |

The total **temporary opportunity bonus is capped at +8**, preventing
unrealistic stacking when a club wins several trophies and plays in Europe.

- Cups are no longer included a second time in the league-form component.
- Bonuses describe the **following season only**. They are replaced, not
  accumulated, so a second consecutive Champions League season does not grant
  an additional +5 on top of last year's +5.
- Continental qualification is **explicitly sourced**. The model never assumes
  a third-place Premier League finish qualifies without checking the rules
  for that specific career season.
- The old untyped `cup_won=True` flag remains compatible as an unspecified
  +1 legacy bonus. It is not silently rewritten to mean an FA Cup victory.
  Typed cup evidence is preferred for all new submissions.
- Season-finalisation records must provide specific source references for
  named cups, continental participation and continental trophies. The
  underlying club sporting appeal is stored separately from these bonuses,
  making them reversible next season even at the 99-point rating ceiling.
- Prestige still increases slowly and only from a **previously reviewed** base.
  A confirmed trophy may contribute +1 in the existing capped prestige model,
  but continental entry by itself does not manufacture historical stature.
- **Finances do not change automatically.** European revenues and prize money
  require a separate evidenced finance engine rather than double-counting
  potential wealth as sporting appeal.
- Updated preview: `/world/reputations/progression`, including optional
  FA Cup / League Cup and Champions / Europa / Conference selectors. This is
  GET-only and cannot alter career state.

### Example of the current calculation
Starting Hull City on 69 and a third-place league finish: moving from a
source-snapshot lower-strength band (−1) to an actual top band (+2) adds +3,
reaching a core sporting appeal of **72**. Confirmed Champions League
qualification then adds **+5** for a final one-season appeal of **77**.

The earlier conversational 69→73 example was illustrative; 77 is what
this exact current algorithm returns when using the stored starting form
adjustment. No real Hull result or qualification has been recorded.

## Previous v1 foundations (still applicable unless superseded above)

## What is implemented

### 1. Season-to-season sporting appeal
A separate, immutable *career* reputation timeline is available without changing
`world_pyramid_club_appeal` (the 2026/27 starting dataset), `world_clubs`,
PES player registrations, transfers, wages, club ledgers or the original
production challenge.

The calculation is **not** a simulated season outcome. It runs only after
a full externally recorded season has been deliberately submitted:

```text
new_sporting_appeal = clamp(
    previous_sporting_appeal
    + (new_league_context - old_league_context)
    + (new_bounded_form - old_bounded_form),
    10, 99
)
```


Division context remains ENG1 +4, ENG2 0, ENG3 −4, ENG4 −8.
This directly deducts four points for relegation or adds four for promotion,
**all else equal**.

The additional *form component* is based on explicit league finish and cup
result, not inferred future results, and is capped between −3 and +3:
top 12.5% +2, upper 30% +1, middle 0, lower 30% −1, bottom 12.5% −2.
The latest model treats all cup victories as separate one-season sporting
opportunities; they are no longer included in the form component.

It replaces the previous form adjustment rather than stacking every
result indefinitely. The underlying squad-rating component stays fixed until
a new, separately sourced player-rating dataset is supplied.

### 2. Historical club prestige
A separate, evidence-gated prestige ledger is now supported:
- evidence includes club, dataset, specific historical claim, category, source URL,
  optional date, and review status;
- a reviewer must explicitly review each item;
- a prestige score can only be signed off with **three reviewed items covering
  at least two evidence categories and two distinct source URLs**, plus a
  documented methodology and named reviewer;
- missing evidence results in **unknown prestige**, not a guessed numeric score.

Once an approved prestige score exists, subsequent **attested** seasonal
results allow intentionally modest year-on-year changes: +2 for a top-flight
title, +1 for a lower-tier championship, +1 for a domestic cup, and −1 for
relegation, net capped at ±2 per season. Promotion alone does not magically
change historical stature. If the starting prestige is unknown, it remains
unknown rather than being calculated from squads or division.

There is **no seeded "verified" institutional prestige database yet**.
Neither fact URLs nor real-world club honours have been invented.

### 3. Complete results validation
The season finalizer (`finalize_career_season`) is a deliberately protected
developer operation, **not an HTTP POST route**.

Before updating a career, it demands:
1. An explicit YYYY/YY label matching the career's starting-season chronology.
2. Exactly one result for **every club** in the selected career world.
3. Explicit evidence URL or internal archive reference for each club; an
   attested reference is *not* proof of independent verification.
4. Unique finish positions for every club in its original division.
5. Valid positions and division sizes; no club jumping more than one tier.
6. The standard 92-club 2026/27 English pyramid must exchange exactly 3 teams
   PL↔Championship, 3 Championship↔League One, and 4 League One↔League Two.
   Promotion places must be top-six (top-seven in League Two) and relegation
   must come from the bottom three or four as applicable.
7. An atomic database transaction; all errors roll the whole season back.
8. An idempotent signature: replay of the same season and evidence is a no-op,
   contradictory revisions are rejected pending explicit reconciliation.

No real season outcomes have been submitted through this mechanism yet.

### 4. Transfer-interest integration
`world_careers.player_move_interest` now uses the latest completed
**career-specific** sporting-appeal and division snapshot. Until an actual
season is finalised, it uses the starting `rep-pyramid-v2` ratings.
Older careers are untouched. A reputation update does not move a PES player,
change their contract, or imply real-world player consent.

### 5. Read-only screens
- `/world/reputations/progression` — hypothetical promotion/relegation scenario
  with separate direct division and form adjustments.
- `/world/reputations/prestige` — evidence coverage and reviewed prestige scores;
  all unreviewed clubs remain unassessed.
- `/world/reputations/career/<career_id>` — **authenticated**, career-specific
  rating timeline, showing audited prior and new divisions, form effects,
  slow prestige changes (when reviewed), and original source references.

The login session cookie now uses path `/world`, remaining Secure, HttpOnly,
SameSite Strict and signed. Existing browser sessions may require re-login
to visit the career-history screen.

## Remaining work
- Source and review historical honours, supporter measures and long-term
  club stature for all 92 clubs, with an agreed **prestige scoring rubric**.
  The absence of an approved score must not be concealed.
- Integrate the development challenge archive's **verified match/league table
  records** into a previewable 92-club end-of-season results importer.
  The current 2026/27 development starting dataset cannot silently inherit
  results from an unrelated 2020/21 PES archive.
- Connect managerial achievements to similarly sourced job-market progression
  (job offers are still partly legacy/predefined).
- Future seasons need refreshed, independently sourced squad ratings, budgets
  and team movements (including EFL↔National League when imported).
- Add a separate agent/player decision stage using institutional prestige
  once club prestige evidence is complete.
- Run and confirm the regression CI suite and independent browser workflow.

## Test command
```bash
python -m unittest -v test_world_reputation_progression \
    test_world_reputation_v2 test_world_careers test_world_career_play
```

The tests contain clearly marked *synthetic fixtures*, never imported
as true results or into an actual career.

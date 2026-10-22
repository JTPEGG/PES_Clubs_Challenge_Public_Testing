# FC27 wage estimation correction — second-pass calibration

**Date:** 20 October 2026  
**Scope:** Men's-only FC27 starting wages and corresponding club payroll ceilings. PC/PlayStation, no production career edits.

## Problem confirmed

The first 317,449-player wage catalogue had no source wage values for FC27. Its rating-and-club-average model compressed superstar wages. Example: Mbappé received £129,100/week and Erling Haaland £122,000/week, versus **source-derived modelled FC26** wages of £518,500/week and £221,000/week respectively.

## Correction approved for version two starting dataset

Model version `historical-wage-and-loan-v2-fc27-anchored` builds on the existing men-only SQLite and uses the selected FC26 source (not an external fabricated FC27 wage).

For FC27 players, match to an **individual prior-year source wage only when source player ID, exact date of birth, nationality, and plausible overall trajectory (within ten rating points) all agree uniquely**. Matching only the numeric ID or shortened name is prohibited.

- Same club, allowing a small fixed reviewed alias table: carry the FC26 nominal GBP weekly wage forward with an assumed **7.5% game-season increase**, rounded to £50. The resulting wage is **an estimate**, never presented as actual FC27 salary.
- Different club: blend 55% of prior-year wage (including the same simulated 7.5% increase) with 45% of the destination club's existing rating-based model, **capped at 2.5×** the destination-club model to avoid importing impossible elite wages into much poorer clubs. Treat this as a simulated new-contract scenario, not observed pay.
- Unmatched identity/unknown employer: retain the original modelled estimate; no names-only joins, invented source contracts or forced salary carry.
- Keep three audit columns: `reference_2026_weekly_wage_gbp`, `reference_2026_player_key`, `reference_2026_match_status`. Preserve the FC27 salary as `game_estimate_...` provenance.
- Recalculate clubs' initial wage bills and ceilings from corrected player values. All loans, contract terms, source files and other annual wage estimates remain unchanged.

## Fully validated results

[Successful complete-database GitHub Action](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39420912054) · [Updated standalone wage/contract/loan database ZIP](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39420912054/artifacts/12262878720)

| Player | Old FC27 estimate | FC26 source (modelled GBP) | Revised FC27 simulation |
|---|---:|---:|---:|
| Kylian Mbappé | £129,100 | £518,500 | **£557,400** |
| Erling Haaland | £122,000 | £221,000 | **£237,600** |
| Jude Bellingham | £100,050 | £272,000 | **£292,400** |
| Cole Palmer | £50,250 | £157,250 | **£169,050** |

**FC27: 17,849 men-only player records**. Of these, 5,264 carry same-club wage history, 6,644 use a cautious changed-club prior-wage blend, and 5,941 retain the unmatched model. **11,726 annual player wage values changed**, 21 other starting seasons have **zero salary changes**, and 10,861 source loans are unchanged. Whole SQLite validated with `PRAGMA integrity_check` and full targeted regression checks.

These remain fictional game estimates; FC26's weekly-pay basis and the EUR→GBP conversion are model assumptions and are not independently verified actual wages. Existing saved careers, original source archives and production are untouched.

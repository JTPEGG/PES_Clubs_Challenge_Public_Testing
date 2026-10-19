# Historical Prestige Calibration — First 15 Clubs

**Project:** PES Clubs Challenge development sandbox  
**Season dataset:** england-2026-27-fc27  
**Version:** institutional-prestige-calibration-v2  
**Status:** PROPOSED — not approved for transfer, agent or job-market use.

## Purpose

Historical prestige must be measured separately from current sporting appeal.
Relegating a club directly affects its sporting opportunities but does not erase
a century of football history. This calibration is deliberately **read-only**.
No career finances, contracts, registered players, existing results or approved
club reputation records are modified.

Review in the development app:
- /world/reputations/prestige/calibration
- /world/reputations/prestige/calibration/<club_id>
- /world/reputations/prestige

## Rubric — 100 possible points

| Component | Max points | Mechanism |
|---|---:|---|
| Major domestic honours | 25 | Repeatable diminishing returns on **top-flight** league, FA Cup and League Cup victories only |
| Continental heritage | 15 | Previous European editorial assessment proportionally adjusted from 20 to 15 |
| Historical league standing and continuity | 35 | Previous history/continuity editorial assessment proportionally adjusted from 20 to 35 |
| Venue scale | 15 | Objective capacity brackets; NOT a measurement of supporters or money |
| Identity and recognition | 10 | Proposed editorial band for lasting cultural footprint |

Major honours are counted independently of the club's current division:
15 points available from top-flight league championships, 8 from FA Cups and
2 from League Cups. Each count is scored as the ratio of
ln(1 + count) to the log of a reference maximum (14 league titles,
14 FA Cups, 5 League Cups). Individual parts are capped at their maximum.
This rewards early major trophies more strongly than additional titles
at the very top. Lower-league titles, promotions, the EFL Trophy and
Community Shields are **not** scored as major domestic honours. Those
achievements may be discussed in a club's historical context.

The remaining ten points from the previously suggested lower-league-honours
category have been reassigned to **historical league standing and continuity**,
as explicitly chosen for simplicity. Venue scale (15) and identity (10) are
unchanged. European pedigree is now 15 rather than 20. The **underlying
editorial judgement** for a club's Europe and history remains from v1 and is
normalised into the new maximum: round(old_Europe × 15 / 20), and
round(old_history × 35 / 20). Nobody receives an ad hoc individual boost.

Venue bands: 60k+ seats = 15; 40k+ = 13; 30k+ = 11; 20k+ = 9;
10k+ = 7; 5k+ = 5; below 5k = 3. Capacities are approximate,
source-attributed references and do not establish the number of active
supporters or actual commercial resources.

**Important:** Continental, historical and identity points involve
judgement and therefore require explicit review. Facts are source-linked;
no source is claimed to endorse the resulting game scores.

## Proposed scores

| 2026/27 division | Club | Domestic | Europe | Historical standing | Stadium | Identity | Proposed prestige |
|---|---|---:|---:|---:|---:|---:|---:|
| Premier League | Arsenal | 24 | 10 | 35 | 15 | 10 | **94** |
| Premier League | Aston Villa | 20 | 15 | 35 | 13 | 9 | **92** |
| Premier League | Nottingham Forest | 9 | 15 | 28 | 11 | 9 | **72** |
| Premier League | Hull City | 0 | 1 | 18 | 9 | 6 | **34** |
| Championship | West Ham United | 4 | 10 | 32 | 15 | 9 | **70** |
| Championship | Derby County | 8 | 2 | 28 | 11 | 8 | **57** |
| Championship | Portsmouth | 9 | 2 | 28 | 9 | 8 | **56** |
| Championship | Wrexham | 0 | 0 | 18 | 7 | 10 | **35** |
| League One | Leicester City | 8 | 3 | 30 | 11 | 9 | **61** |
| League One | Sheffield Wednesday | 14 | 0 | 32 | 11 | 9 | **66** |
| League One | Bradford City | 2 | 0 | 21 | 9 | 7 | **39** |
| League One | AFC Wimbledon | 0 | 0 | 11 | 5 | 9 | **25** |
| League Two | Grimsby Town | 0 | 0 | 21 | 5 | 6 | **32** |
| League Two | York City | 0 | 0 | 16 | 5 | 6 | **27** |
| League Two | Salford City | 0 | 0 | 7 | 5 | 8 | **20** |


## Important comparison decisions

- Arsenal's current squad and prestige may both be elite, but
  they represent different things. The gulf from Hull in **historic major
  honours** is much larger than the difference in their current
  English top-flight status.
- West Ham has substantial continental and FA Cup history even in
  the development world's 2026/27 Championship.
- Leicester's 2016 Premier League title and 2021 FA Cup remain relevant
  despite its League One starting membership.
- Nottingham Forest's European Cups from 1979 and 1980 are central
  to its historical prestige, independently of present squad ratings.
- AFC Wimbledon was formed in 2002. Its identity openly connects to
  Wimbledon FC, the 1988 FA Cup winners; this calibration **does not count
  the 1988 trophy as an AFC Wimbledon title**.
- Wrexham's global visibility is unusually strong for a club without
  major English domestic championships. Its high identity band is
  explicitly **subjective**, not a verified fanbase measure.
- Hull's 2020/21 League One championship remains acknowledged in the
  historical notes but, by design, is not a major domestic honour.
  This draft moves Hull from 26 to **34** solely through weighting changes.
  It places Wrexham at 35 and Grimsby at 32: an explicit question for
  calibration rather than grounds for selectively modifying a club score.

## Evidence

Every club has directly linked historical source references in its
detail screen, including club histories, FA or UEFA records, and
Football Ground Guide capacity references. Examples:

- Arsenal: https://www.arsenal.com/history
- Aston Villa: https://www.avfc.co.uk/history/timeline/
- Forest: https://www.uefa.com/uefasupercup/history/1979/
- Hull: https://tigerbase.hullcity.com/tigers-honours.php
- West Ham: https://www.whufc.com/en/the-club/history/honours-and-records/honours
- Derby: https://www.dcfc.co.uk/page/derby-county-club-honours
- Portsmouth: https://www.thefa.com/news/2019/nov/30/emirates-fa-cup-second-round-301119
- Wrexham: https://www.wales.com/news/united-kingdom/wrexham-afc-promoted-championship
- Leicester: https://www.lcfc.com/history-honours-men
- Sheffield Wednesday: https://www.efl.com/news/2020/february/the-league-cup-1990-1999
- Bradford: https://www.thefa.com/news/2014/nov/28/fa-cup-preview-bradford-v-dartford
- AFC Wimbledon: https://www.afcwimbledon.co.uk/club/
- Grimsby: https://www.fchd.info/GRIMSBYT.HTM
- York: https://www.thefa.com/news/2017/may/21/macclesfield-v-york-report-210517
- Salford: https://www.salfordcityfc.co.uk/news/2024/august/02/gary-neville-acquires-peter-lim-interest-in-salford-city/

Omitted trophies or missing references must be investigated; never
interpret a zero editorial points band as a proof that the club never
played in Europe.

## Before wider deployment

1. User reviews the 15 clubs and signs off (or adjusts) the weights,
   source facts, and editorial bands.
2. Extend consistent, attributed ratings to the remaining 77 English clubs.
3. Convert accepted historical evidence and reviewer decisions into the
   existing **approved** prestige tables via the controlled review workflow.
4. Connect prestige to players' preferences and managerial eligibility
   **only after** the full club catalogue is reviewed. Keep player-specific
   factors such as role, money, career age and continental participation.
5. Keep 2026/27 calibration distinct from any 2004/05 or future starting season.

Local test: python -m unittest -v test_world_prestige_calibration

Original project, existing career saves and summer registration timing
are unchanged.

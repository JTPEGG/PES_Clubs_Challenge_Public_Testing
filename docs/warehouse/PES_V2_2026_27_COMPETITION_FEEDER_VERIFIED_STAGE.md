# PES V2 Historical Competition Registry — 2026/27 source and feeder milestone

**20 October 2026 — MEN'S football — FC27 2026 starting season — isolated testing branch**

## GitHub Actions validation (successful)

- Pinned 2026/27 and 2026 calendar-year 16-competition collector: [run 39467154912](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39467154912).
- Independent English National League FA May 2026 division allocation cross-check (72/72): [run 39465806639](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39465806639).
- Official MLS calendar-2026 club conference and competition rules (30/30): [run 39466458050](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39466458050).
- **Full consolidated 22-edition source registry and SQLite integrity gate: [run 39467266710](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39467266710).**
- **Reconciled, all-original-club per-edition gaps: [run 39467371845](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39467371845).**

Artifacts:
- [Competition SQLite, complete evidence and original club competition crosswalks](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39467266710/artifacts/12284683674)
- [Per-club mapping gap CSVs, remaining missing home leagues and priority data](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39467371845/artifacts/12284463977)
- [FA 2026/27 step 1 and 2 original-vs-fixture allocations](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39465806639/artifacts/12284851948)
- [Official 2026 MLS East-West membership and play-off schema](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39466458050/artifacts/12286110549)

## Current independently audited figures

| Measure | Before this batch | After this batch |
|---|---:|---:|
| Historical starting editions (FC25 absent) | 22 | **22** |
| Original men's game club-season records (unchanged) | 13,104 | **13,104** |
| Dated, sourced domestic competition-seasons | 351 | **367** |
| External fixture-source club-season observations | 6,745 | **7,073** |
| Club-season records with some evidence (provisional, not yet certified game identity) | 5,021 | **5,227** |
| Unresolved original game club-season records | 8,083 | **7,877** |
| Unverified alias identity candidates within linked records | 1,106 | **1,241** |
| Historical non-playable feeder membership records | 239 | **311** |
| FA officially sourced and cross-checked FC27 fifth/sixth-tier club identities | 0 | **72** |
| Official MLS 2026 clubs and league structure cross-checked | 0 | **30** |
| Countries/territories covered by fixture-competition group labels | 20 | **21** |
| Fully verified playable starting editions | 0 | **0** |

**206 additional club-season records linked to some evidence are not fabricated squads**. All game identities (including exact-name fixtures) remain subject to the strict career readiness gate.

The 16 new dated competition-sources include 2026/27 English League One, League Two, National League, National League North/South, Scottish Championship/League One/League Two, German 3. Liga, Spanish Segunda, Italian Serie B, French Ligue 2, Turkish Süper Lig, and calendar-2026 Major League Soccer, Argentina Primera División and Japan J1 League.

The external snapshot source is pinned to Git commit `0e39da91fb053a2ed355d9b69cef5aec6d7ae3f1`. Because no license is declared by that repository, only factual fixture **club membership names**, rather than full fixture/match data, are stored in the evidence register; every source record retains URL and source checksum and is tagged `pinned_third_party_snapshot_review`. Five explicit Scottish spelling/name abbreviations were reviewed and corrected, giving all 16 intended divisions the expected clubs. These are **source facts pending EA game identity validation**.

### 2026/27 National League feeder evidence (English men)

- FA's [club allocations dated 14 May 2026](https://www.thefa.com/news/2026/may/14/nls-club-allocations-2026-27) list the 24 National League, 24 National League North and 24 National League South clubs and remain subject to appeal/amendment.
- An independent pinned October fixture snapshot for each of the same three leagues was explicitly name-normalized, checked and compared.
- **72 of 72 official clubs match the independently observed league in the pinned fixture file** (23 more required explicit full-name/short-name equivalence, not a change of division).
- The 72 FA names are preserved in the distinct `official_fa_nls_allocations` SQL table; the non-playable fixture teams remain in `sourced_nonplayable_feeder_clubs`. These tables do **not** create players, authorise movement eligibility, prove all adjacent feeder leagues or unlock the career.
- FA's separate [Step 1–4 allocations PDF](https://www.thefa.com/-/media/thefacom-new/files/competitions/2026-27/nls/nls-1-to-4-club-allocations-2026-27---v1-140526.ashx) and [Step 5–6 allocations PDF](https://www.thefa.com/-/media/thefacom-new/files/competitions/2026-27/nls/nls-56-club-allocations-202627-v1-140526.ashx) now provide a documented path for extending the **rest** of the non-playable national/regional feeder boundaries without unknown destinations. Those additional allocations are not all imported.

### 2026 MLS official format in FC27 edition

- The [MLS official 2026 competition guidelines](https://www.mlssoccer.com/league-reports/competition-guidelines/) identify 30 clubs in 15 East and 15 West groups, 34 games each.
- Nine teams in each conference qualify for postseason: top seven enter the best-of-three round, eighth/ninth enter wild-card eliminators.
- 30/30 official teams match the pinned 2026 fixture membership when explicit published name variants are normalized.
- `official_mls_conference_clubs` and `season_non_pyramid_formats` preserve season-specific official competition facts and **zero** promotion/relegation between MLS and any external domestic division.
- These are the actual **calendar-2026** rules attached to FC27's 2026 career starting year. They must NOT be applied to every historical MLS season or to calendar-2027 without new evidence.

### What remains unresolved (source-provenanced audit)

| Cause | Original club-season records |
|---|---:|
| Game source league key missing and individual evidence insufficient | **6,365** |
| Original game league group present but unverified | **1,470** |
| FC27 CONMEBOL continental competition bucket needs true domestic association | **40** |
| Two independently disambiguated Uruguayan EA club IDs still lack sourced home leagues | **2** |
| **Total** | **7,877** |

Remaining high-value known source groups include 2021/22 German third division, Japanese J1 and Turkish Süper Lig; 2023/24 Turkish Süper Lig; and 2020/21 Brazil Série A. For source-less historic clubs, prioritize independent same-year source fixture memberships and stable EA game club ID crosswalks instead of applying later seasons' real-world memberships. The 2027 FA allocations cover only first two non-league steps and need further Steps 3–6 regional allocations / licensing rules before the English pyramid can genuinely simulate entry and exit.

**Do not treat 367 league-season evidence records as 367 complete career-competition rules.** Existing 128 dated promotion-regime rows are incomplete and six feeder boundaries remain unverified. Saved career launches remain fail-closed for all 22 editions; no production projects or careers were modified.

## Next implementation (explicit)

1. Import remaining English FA 2026/27 regional feeder divisions from official allocations, uniquely keyed by tier, region, season and real club IDs; preserve appeal status and exact origin and do not invent PES players.
2. Expand historical source coverage for source-less 2005–2024 editions: only use year-specific fixture clubs/tables; add safe cross-season EA ID alias evidence rather than assigning a club's prior division after promotions.
3. Close every country-specific movement boundary with season-dated playoff/relegation/eligibility rules. Distinguish closed-league formats and rank-based continental cup qualifications from domestic pyramids.
4. Run a **simulated** promotion/relegation season-end test with independently sourced next-year entrant pools before certifying any historical career.

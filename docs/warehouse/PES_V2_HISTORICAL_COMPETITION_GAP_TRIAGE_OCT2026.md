# Historical men's FIFA/FC competition database — audited blocker triage

**20 October 2026** · GitHub testing branch `feat/fifa-pes-converter-v2-complete` · PC/PlayStation, no production career changes.

## Confirmed implementation and validation

- [Revalidated 304-season competition registry / 63 additional provisional aliases](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39453612685)
- [Final 22-edition gap triage CI success](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39454280532)
- [Download full review ZIP: six detail CSVs, source-ID priorities, 22-edition summary, JSON audit and action plan](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39454280532/artifacts/12278874837)

The script `scripts/audit_historical_competition_gaps.py` reads the **unchanged** approved FIFA club archive alongside the newest consolidated competition SQLite. It validates keys/club names against the originals and never guesses a country from a shared league label. All output remains review-only.

| Reconciled category | Club-season rows |
|---|---:|
| Original FIFA/FC men's club records | **13,104** |
| Independently sourced domestic league-seasons | **304** |
| Source fixture-team memberships (not necessarily game squads) | **5,709** |
| Clubs with provisional individual or league-group evidence | **4,084** |
| Of which exact same-name fixture observations | 2,857 |
| Of which identity aliases needing review | 953 |
| Of which source-group-only corroborations | 274 |
| **Unresolved club-season records** | **9,020** |
| Career-ready editions | **0 / 22** |

### Why the 9,020 remain blocked

| Cause | Club-season records | Most useful next intervention |
|---|---:|---|
| No original league key and no independent identity evidence | **6,839** | Import actual season-by-season domestic league members, and reconcile original FIFA club identities |
| Original FIFA league group known, but not independently identified | **2,140** | Verify named competition, league IDs, game teams, season and country as a distinct step |
| FC27 source teams stored under CONMEBOL cup buckets | **40** | Prove the home domestic league independently, never treat the cup as a domestic pyramid |
| FC24 Liverpool, game ID 111326: identity established but home league source absent | **1** | Source Liverpool Fútbol Club's Uruguayan home division independently |
| **Total** | **9,020** | |

**Liverpool homonym prevention:** External [FC24 club ID 111326](https://www.fifacm.com/24/team/111326/liverpool-futbol-club-uruguay?vid=335) identifies **Liverpool Fútbol Club Uruguay**, not the English club whose same-season source fixture name is Liverpool FC (FC24 English Liverpool is game ID 9). The source-ID identity is preserved in `data/warehouse/historical_club_identity_disambiguation_v1.json`. Its Uruguayan domestic competition remains **unsourced and unassigned**, while country mismatch is an explicit guard in the audit. This is why names cannot safely be fuzzy-merged.

## Highest-impact early labelled FIFA groups

These are original *league labels*, not yet proof of exact club membership or regulation structure.

| Edition | Original league label | Unresolved club-years |
|---|---|---:|
| 2026 | Liga Profesional de Fútbol | 30 |
| 2026 | Major League Soccer | 30 |
| 2027 | LPF | 30 |
| 2027 | MLS | 30 |
| 2024 | Liga Profesional de Fútbol | 29 |
| 2024 | Major League Soccer | 29 |
| 2022 | USA Major League Soccer | 27 |
| 2022 | Argentina Primera División | 26 |
| 2021 | USA Major League Soccer | 26 |
| 2022 | English League One / League Two | 24 each |

The highest unresolved editions in the audited data are 2023 (531), 2018 (530), 2022 (522), 2017 (521) and 2027 (514). The 2022 gap largely consists of **labelled original source league groups**, while 2017/2018/2023 lack original league keys. These are different extraction problems and should not share an automatic fix.

## Implementation outputs

The fully source-keyed review ZIP contains:

1. `HISTORICAL_COMPETITION_CLUB_TRIAGE.csv` — all 13,104 original club-year keys with exactly one cause/status, candidate source names (hints only), reliable competition evidence if any, required action and hard career block.
2. `HISTORICAL_COMPETITION_EDITION_GAPS.csv` and `HISTORICAL_COMPETITION_CAUSES_BY_EDITION.csv` — reconciliation of every one of the 22 editions against the original registry.
3. `HISTORICAL_COMPETITION_SOURCE_GROUP_PRIORITY.csv` — 212 original source-group/edition clusters, retaining source ID/label instead of accidentally merging unrelated Premier Leagues.
4. `HISTORICAL_COMPETITION_RECURRENT_SOURCE_ID_PRIORITIES.csv` — candidates for cross-year review; repetition of an ID or name alone does **not** prove identity across editions.
5. `HISTORICAL_COMPETITION_ALIAS_REVIEW.csv` — 953 unique staged alias records requiring independent identity approval.
6. `HISTORICAL_COMPETITION_UNCROSSWALKED_NAME_REVIEW.csv` — now empty after 63 safe **review-stage** additions and the Liverpool Uruguay identity exclusion.
7. `HISTORICAL_COMPETITION_SOURCE_COVERAGE.csv` — original country/tier/season evidence completeness by imported competition.
8. `HISTORICAL_COMPETITION_GAP_ACTION_PLAN.md` and `HISTORICAL_COMPETITION_GAP_AUDIT.json`.

## Next engineering phase — evidence fixes, not career activation

**A. Resolve the named league-group backlog first.** Start with the clearly identified large groups in 2021/22, 2023/24, 2025/26 and 2026/27: MLS, Argentina top tier, English L1/L2, Spanish Segunda, German 3. Liga and French Ligue 2. Require an immutable source for exact league membership in that edition; do not extrapolate later teams.

**B. Verify club identity aliases separately.** The 953 staged aliases are NOT approved squad identities. Prioritize instances with a stable original EA club ID, independently sourced source-team identity and uniqueness within the target league-season. Record proof and conflicts rather than auto-accept all common suffixes.

**C. Attack the source-less editions.** Expand historical pinned fixture/table coverage, especially where the original FIFA archive has no league keys. Preserve non-playable club entries solely as teams and feeder eligibility, without manufacturing PES players.

**D. Build complete dated movement and external eligibility rules.** Only after home-division memberships are verified should the full historical promotion/relegation and play-off graph be certified. MLS and other closed leagues require explicitly documented zero movement. A season-end career must use **simulated** tables and results, never real future promotion outcomes.

The existing career certificate remains fail-closed. No normal historical edition is activated; no Render production app or prior career is changed.

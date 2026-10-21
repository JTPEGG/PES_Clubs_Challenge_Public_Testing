# FC27 2026/27 — One-edition club / competition alignment

**Scope:** 2026/27 source game edition only. Testing branch. Last checked 21 October 2026. Original production careers and all other 21 historical editions unchanged.

## Validated results

| FC27 stage | Original FC27 clubs | Evidence / limit |
|---|---:|---|
| Original imported game-source clubs | **670** | Unmodified original source club keys and season labels |
| Already linked to independent dated fixture club evidence | **377** | Provisional name evidence, not globally certified original EA IDs |
| Additional exact-year domestic game-source league group associations | **253** | 28 reviewed competition name/country/tier identities; not full historical club roster certification |
| Additional CONMEBOL original clubs with reviewed national association and **candidate** home division | **40** | Country independently reviewed, 2026 national league source supplied; **individual top-division participation still pending verification** |
| **All FC27 records with a named or candidate domestic division** | **670 / 670 (100%)** | **SOURCE ASSOCIATION COVERAGE ONLY**, not career readiness |

Club keys and source league groups remain unchanged. No new game players or phantom EA team IDs were manufactured. All FIFA 2005–2026 edition records remain untouched. `career_ready=0`.

**FC27 reconciliation artifact:** [Successful all-670 2026/27 edition-only SQLite export](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39570447019), name `FC27_2026_27_ALL_670_SOURCE_CLUB_HOME_COMPETITIONS.sqlite` and view `fc27_2026_27_complete_source_competition_alignment`.

### Critical source quality distinction

A source label like `Scottish Premiership` or `Metropolitan Division` can identify the **competition** without proving the *participant list* exactly matches the real 2026/27 season. Original FC27 source data contains clubs from a mix of game-source snapshots, and source player grouping is not an independently approved current registration list. A group of 4 Greek clubs, for instance, must NEVER be portrayed as the complete 2026/27 Greek domestic league.

The 40 CONMEBOL clubs were never falsely assigned to `CONMEBOL Libertadores` or `Sudamericana` as their home league. Exact original club names were matched to a reviewed 2026 [Libertadores](https://gol.conmebol.com/libertadores/en/teams) / [Sudamericana](https://gol.conmebol.com/sudamericana/en/teams) country list and nine dated domestic league source references. **None of these 40 has yet passed an individual 2026 domestic first-division participant cross-check**, so they are COUNTRY-BACKED CANDIDATES, not 40 independently certified domestic registrations. Original EA club IDs likewise still require source proof.

### 2026/27 participant-list validation: audited 4 domestic competitions

| Division | Original source clubs | Official published season clubs | Source-identical after controlled aliases |
|---|---:|---:|---:|
| Scottish Premiership | 12 | 12 | **12** |
| Belgian Jupiler Pro League | 18 | 18 | **18** |
| Romanian SuperLiga | 16 | 16 | **16** |
| Indian Super League | 11 | 13 | **10** |

**3 of 4** inspected source-group leagues agree with real 2026/27 published rosters; **56 individual name-identifiable matches** were cross-checked. All controlled abbreviations are retained in `fc27_2026_27_independent_roster_and_rules_checks.json`, not overwritten in original game. The Belgian `Waasland-Beveren` alias for SK Beveren is independently supported by [SK Beveren's own club history](https://www.skbeveren.be/club-2/) (registration number 4068 continued under new name in 2022). The spellings `Sp. Charleroi` → Sporting Charleroi and `Univ. Craiova` → Universitatea Craiova are controlled label equivalents.

**India is a genuine source roster mismatch.** The original FC27 source has `Hyderabad FC`, whereas the real published 2026/27 official Indian Super League roster contains `Sporting Club Delhi`, `East Bengal FC` and `Churchill Brothers FC` not in the original 11. The remaining 10 original identities match. Source: [official Indian Super League clubs](https://www.indiansuperleague.com/Clubs). The Hyderabad → Delhi licence transition is **not** assumed to create the same original game club key or squad; the missing 3 clubs are not fabricated.

Sources: [2026/27 Scottish Premiership](https://en.wikipedia.org/wiki/2026%E2%80%9327_Scottish_Premiership), [Belgian Pro League 2026/27 official fixtures](https://www.proleague.be/nieuws/kalender-2026-2027-club-brugge-opent-tegen-kv-kortrijk-eerste-super-sunday-al-op-speeldag-4), [Romanian League official opening 2026/27 fixture list](https://lpf.ro/noutati/superliga-programul-turului-editiei-2026-2027/6593), official Indian clubs above.

Reproducible [successful 4-competition audit](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39570273653) exports `FC27_INDEPENDENT_DOMESTIC_ROSTER_AUDIT.csv`, `FC27_CONFIRMED_FULL_ROSTER_GAME_CLUBS.csv`, and `FC27_REAL_WORLD_CLUB_ROSTER_EXCEPTIONS.csv`.

### Movement-format check now recorded

Belgium **2026/27**: 18 first-tier clubs, 34 league matches, **no championship/playoff split**, bottom 2 relegated directly to Challenger Pro League per the [league's published 2026/27 format](https://www.proleague.be/nieuws/vanaf-seizoen-26-27-met-18-clubs-in-de-jupiler-pro-league). The domestic feeder league's actual source clubs, U23 eligibility and promotion format still need season-specific validation. Do not reuse the old Belgian championship playoff logic from an earlier year.

Current underlying FC27 core historical registry still has six movement-rule edges with `feeder_verified=0`. The full season-end promotion/relegation graph cannot be certified while eligible feeder clubs or correct dated movement regimes are missing. The lightweight one-hop-only feeder policy remains locked.

## Remaining FC27 work before moving to FC26

1. **Independently verify the 2026/27 member lists** for remaining full original source domestic league groups (28 reviewed mapped groups in all, with only 4 official lists checked above), and clearly distinguish partial licensed subsets, not clubs in game, and wrong snapshot-year source membership. For each, retain exact source EA club key, game display name, 2026/27 official display name and independent source URL. Never silently invent missing players.
2. **Verify the 40 continental participant domestic registrations** against actual country-specific 2026 first-division fixtures / official tables or stronger source club IDs. Identify teams in a lower tier rather than automatically presuming first tier.
3. **Finish year-specific promotion/relegation** for playable leagues, with only their **immediately lower division** as a nonplayable feeder. Closed leagues require explicit no-promotion rules. The 2026/27 England National League already has 72 official FA step 1 & 2 club allocations for the optional terminal floor.
4. **Final fail-closed FC27 certificate**: every enabled playable competition must have correct current-year real club participants and appropriate movement/entry graph, EA original club identity evidence or explicit identity-gapped status, and zero unexplained destination edges. Do not turn on historical careers yet.

**Status: FC27 source club-to-named competition association complete (670/670), actual playable 2026/27 membership and movement certification incomplete. FC26 work has not been started in this one-year pass.**

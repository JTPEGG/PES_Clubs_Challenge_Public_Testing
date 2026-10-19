# Player Warehouse — Source Feasibility Pilot (100 Players)

**Status:** technical proof of concept; **source policy not yet locked**.  
**Scope:** six clubs × 16–17 first-team-biased sample players, 100 total.  
**Run:** [Automated pilot run](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39253769565).  
**Script:** [qa_player_source_pilot.py](../../qa_player_source_pilot.py); **nine offline regression tests**.  
**No user data collection required. No writes to warehouse or career saves.**

## Selection

| Club | Sample size | Reason |
|---|---:|---|
| Manchester City | 17 | Elite title challenger, demanding squad-depth decisions |
| Arsenal | 17 | Elite club, multiple CB and full-back rotation choices |
| Crystal Palace | 17 | Established top-division club with different sporting ambitions |
| Leeds United | 17 | More constrained Premier League squad and finances |
| Bolton Wanderers | 16 | Championship example |
| Walsall | 16 | League Two example |
| **Total** | **100** | First-team-biased sample (top OVR players) |

Player identities, six FC category ratings and ages come from the **existing** 2,498-record `world_fc27_english.py` seed. The pilot reads it but **does not certify its distribution rights, source identity matches or real-life squad accuracy**. No duplicate CSV of licensed player ratings has been committed.

## Results — last successful public GitHub Actions run

| Field | Available of 100 | Status |
|---|---:|---|
| Name, club as in existing reference seed, external source ID | 100 | Existing seed, provisional |
| Primary position | 100 | Existing seed |
| Age as of 2026-09-12 | 100 | Calculated from existing DOB |
| OVR and six broad ratings | 100 | FC-style reference, **not native PES2020** |
| Alternative playable positions | 1 | **Operator-confirmed** White CB, not independently sourced |
| Verified per-position suitability rating | 0 | Unknown |
| Detailed individual attributes | 0 | **Not in existing six-aggregate seed** |
| Potential rating | 0 | Unknown |
| Contract end | 0 | Unknown |
| Weekly wage | 0 | Unknown |
| Transfer listing/renewal status | 0 | Unknown |
| Personality traits | 0 | Unknown |
| Independent English-file CC0 name+DOB match | 28 | Exact identity association to an external dated roster |
| Height available through that CC0 match | 22 | Could enrich height after approval |

The 28 matches are **28/100 sampled players across all nationalities** using *one* England file, not a 28% global match success estimate. The source is an older snapshot; identity corroboration does not establish a 2026 club registration. On ambiguity, the code records no match.

## Automated source feasibility matrix

| Source | Technical access tested? | Coverage/potential | Rights assessment and treatment |
|---|---|---|---|
| Existing 2026/27 FC-style seed (this repo) | **Yes**, locally | 2,498 reference rows, 92 English clubs; DOB, primary role, OVR, six categories | Source rights not independently established. **Read for existing internal QA only**, no new bulk redistribution. |
| [OpenFootball/players](https://github.com/openfootball/players) | **Yes**, pinned GitHub raw text | Public-domain CC0 name, birth date, height where known, broad D/M/F/G role, nationality groups. Exact DOB/name matching proof completed. | Repository [CC0-1.0 licence](https://github.com/openfootball/players/blob/125d20f7cc06cac7e758b40df535a7695632680a/LICENSE.md), technically viable automatic feed. Older source, many countries still to check. |
| [FC26 rich dataset published on GitHub](https://github.com/ismailoksuz/EAFC26-DataHub/blob/main/data/players.csv) | **Yes, CSV header only** | Header contains **110 columns**; may address the missing detailed attributes, potential, role and contract model. | Author cites [Kaggle FC26 player dataset](https://www.kaggle.com/datasets/rovnez/fc-26-fifa-26-player-data) with CC BY 4.0 metadata, **but EA's underlying data rights and website extraction limits are not resolved**. No player rows pulled. Different edition (FC26) from FC27 target; never overlay silently. |
| [PES Master PES2020](https://www.pesmaster.com/pes-2020/) | Browser access only; no permitted automated data feed confirmed | Relevant gameplay ratings, PES-native styles and positions | Treat as evaluation/reference only until bulk access/reuse permission and versioning are settled. |
| Football Life / SmokePatch | No source-approved reusable bulk export established | PES-family squad/player data potentially useful for PC game | No ingestion; individual community tools' MIT licenses do not license the Football Life core player database. |
| Football Manager editions | No source-approved extract established | Rich player psychological, contract, manager and tactical data | Sports Interactive's databases are proprietary. Use FM as **feature-design benchmark**, not an import source without a licence. |
| Public results/open data | Catalogue exists but no transfer-profile import yet | Can build historical leagues/competition facts and modest identity enrichment | Evaluate each provider/licence independently; no claim that results data gives personality or attributes. |

**Rights nuance:** A third-party CSV marked CC BY cannot automatically confer permission to republish copyrighted source ratings from a game. Published pages and downloadability are not sufficient licence clearance. For inaccessible fields the alternative is an *explicit fictional management profile*, not fabricated claims about real people.

## Verified automation

- GitHub Actions performs nine unit tests before the pilot, then reads exactly **one pinned public-domain England file**. The external identity check requires an exact normalised full name **AND** birth date. Duplicates do not match.
- The separate FC26 probe reads **only the first CSV line** and records column headings, no player rows.
- It exports `pilot-summary.json` (field coverage, source dates, failures, evidence URLs) plus `pilot-field-coverage.csv` (one availability row per selected player) as a run artifact.
- Both source URL versions are pinned to immutable GitHub commit IDs. If an endpoint fails, report `unavailable` instead of treating zero availability as ground truth.
- Outputs are QA-only, not an implicit step toward running the private production database.

## First assessment, not a final decision

**Proven:** no one needs to supply files for us to build a repeatable, licence-aware pilot and match some source identities.  
**Not proven:** we can automatically populate all PES attributes, alternative positions, personality, wages, contract status and modern/retro player databases with legally reusable data.

**Proposed next experiment:** extend CC0 coverage from England to other nationalities using a stable source-file catalogue and strict cross-provider IDs, and separately validate FC26 attribute schema/permission with source owner before extracting rows. If this is unworkable, test public-domain/statistical measurement models and clearly labelled **fictional career traits**. Do not lock a universal supplier until comparative data coverage and rights pass agreed checks.

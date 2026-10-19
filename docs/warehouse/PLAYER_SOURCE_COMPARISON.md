# Player Source Comparison v2 — Results, 19 October 2026

**Status:** completed automated feasibility experiment; source selection **not locked**, no Render migration or live-career changes.

[Successful CI and raw diagnostic artifacts](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39258181169) | [Source comparison code](../../qa_player_source_comparison.py) | [Historical source probe](../../qa_legacy_source_probe.py) | [Warehouse v1 schema](../../warehouse/schema_v1.sql)

## Why the second pilot

The first 100-player sample relied on the existing 2026/27 FC27 reference seed and one England-only country file, leaving nearly all attributes and alternatives unpopulated. The second pilot automatically evaluated **the same 100 players**, checked all countries in OpenFootball, read richer FC26 ratings, measured PES2020/FIFA2020/FIFA2005 downloadable datasets and **imported matching FC26 records into disposable in-memory SQLite using the actual warehouse DDL**. No user files were requested.

## Source availability — measured, not inferred

| Source | Rows available | Fields / scope | What worked | Main limitation |
|---|---:|---|---|---|
| Existing `world_fc27_english.py` | 2,498, 92 English clubs | Primary position, DOB, OVR and six broad skill groups | All 100 sampled names and baseline fields available | Existing source is incomplete for detailed attributes, contracts or alternative positions |
| [EA FC26 DataHub CSV](https://github.com/ismailoksuz/EAFC26-DataHub) | **18,405** | **110 columns**, **36** fields under detailed skill/mental/physical prefixes | **92 of 100** matched by EA ID **and** DOB; potential, attributes, multiple positions and game-modelled wages/contracts readable | FC26 season does not describe an FC27/current contract; its ratings are FC-style, not PES-native |
| [OpenFootball/players pinned snapshot](https://github.com/openfootball/players) | **31,689** parsed records from **184** country files | Name, birth date, heights for some, broad position groups | **75 of 100** matches by exact normalized name + date of birth; height for **67** | Older country file snapshot; no detailed ratings, transfers or wages |
| [PES 2020 research CSV](https://github.com/mlblbc/pes---Data-visualization-project) | **15,035** | **124 columns**: 25 native abilities, 13 positional ratings, 43 skills | 15,035/15,035 rows have all 25 abilities and all 13 per-position rating values present; machine-readable automatically | No stable ID or exact birth date; cannot automatically identify against modern FC dataset; PES2020 season only |
| [FIFA 20 dataset](https://github.com/AMRYB/FIFA-Dashboard) | **18,278** | 104 columns, EA ID, DOB, positions, potential and individual attributes | **57 of 100** modern sampled players join by exact EA ID+DOB; one same-ID/DOB mismatch rejected | FIFA20 season, not contemporary strength or contract |
| [FIFA 2005 dataset](https://github.com/lbenz730/fifa_model) | **10,993** | 64 columns, IDs, birthdate, OVR and detailed attributes | Historical vintage data is accessible automatically | Expected 0 overlaps with our selected *young 2026* player sample; requires a historical 2004/05 sample to assess matching quality |
| PES21/Football Life game-file decoder | Not counted: no game file | Program can read 25 abilities and per-position suitability when a compatible source file exists | [Open-source parser](https://github.com/gvoze32/pes21-player-rating) technically available | This is a parser, **not a download source for current Football Life records** |
| FM26 save reader | Not counted: no save file | Can parse manager, club, stadium, personality, contract, player and facility records from save files | [Open-source `fmsave`](https://github.com/rhiever/fmsave) technically available | This is a parser, **not an independently accessible FM database** |

**Data rights:** Software being openly available, and a third-party dataset being downloadable, do not automatically establish rights to redistribute a game's underlying database. Large game-derived player dumps were processed in memory for this feasibility experiment and were **not** added to the public repository. We can pursue private-source storage when import policy and intended use are settled.

## Real field coverage — same 100 players

| Tested field or evidence | Available |
|---|---:|
| Current 2026/27 snapshot: DOB, primary role, OVR + six broad categories | 100 / 100 |
| FC26: EA ID **and** DOB matched | 92 / 100 |
| FC26: 15+ non-empty detailed attribute fields | 92 / 100 |
| FC26: potential | 92 / 100 |
| FC26: more than one listed position | 61 / 100 |
| FC26: edition-specific reported wage and market value | 92 / 100 |
| FC26: edition-specific contract end year | 92 / 100 |
| FC26: preferred foot | 92 / 100 |
| OpenFootball: name and DOB identity match across country files | 75 / 100 |
| OpenFootball: height on a matched identity | 67 / 100 |
| FIFA20: stable EA ID and DOB match | 57 / 100 |
| PES20: same-season FIFA20 crosswalk **candidate** for a modern pilot player | 21 / 100 |
| PES20-native ratings correctly attributable to the **current 2026/27 season** | **0** |
| Verified position-specific suitability for the 2026/27 current sample | **0** |
| Independently sourced FM-style personality for the 2026/27 current sample | **0** |

**Important:** 61 players have multiple FC26 position codes, representing **99 additional position records** in the temporary warehouse. Neither FC26 multiple positions nor historical PES positional ratings prove a player's exact 2026/27 PES ability in those roles.

## Warehouse staging proof — real input, disposable database

The automated pipeline loaded FC26 records into SQLite `:memory:` using the exact [warehouse v1 schema](../../warehouse/schema_v1.sql), with an independent `ea-fc26-pilot-only` dataset identity.

| Stored/tested relation | Row count |
|---|---:|
| Unique staged player profiles | **92** |
| Total position rows | **191** |
| Of which alternative positions | **99** |
| Detailed attribute values | **3,134** |
| Position-specific suitability inferred without evidence | **0** |
| Fictional personality invented as fact | **0** |
| Foreign-key violations | **0** |

The input game data and source player records were used **ephemerally**, not added to Git history, a permanent warehouse, or an existing career save. Contracts are not duplicated: the existing `world_dataset_player_contracts` domain will own contracts when we implement a proper dated contract adapter. The warehouse proof demonstrates **schema compatibility**, not that FC26 numbers should supersede our 2026/27 reference values.

## PES20 ↔ FIFA20 linking experiment

Exact short-name + nationality + age matching within the historical **2019/20 edition** found **4,637 unique cross-source candidate pairings**. Another **44** shared keys were ambiguous and rejected. Only **1,183** of the candidate pairs also used the exact same raw club string.

Of the 57 modern sample players verified in FIFA20, **21** had a PES20 crosswalk candidate. These candidates are **NOT verified PES IDs**. PES data lacks stable player identity and date of birth in this source file, and names, age and nationality may collide or change. Therefore none is approved for automatic merging. More evidence—such as verified club history, PES source IDs or official mapping—would be required.

## Recommended architecture after this experiment

**Keep multiple source-specific snapshots, not an averaged player record.**

1. FC/FIFA seasons: separate snapshots by edition, source date, and player EA ID; compare source editions without overwriting their attributes or wages. The current FC27 reference seed can be enriched from permitted sources at the proper edition.
2. PES2020: strong, automatically accessible 2019/20-native football skill and positional ability source. Import as **its own historical PES dataset**, initially preserving its source name/team/age without falsely matching to EA IDs. Use quality checks and an approved crosswalk for later joins.
3. Historical FIFA editions: support 2005, 2015–2020 as immutable snapshots, with stable IDs and dates where available. Prioritise the desired 2004/05 project in a separately sampled cohort.
4. Football Life: treat as future PES21-family source requiring actual game data, not an automatic data feed yet. If no file is accessible through an approved pipeline, do not claim that current Football Life positions have been populated.
5. FM: use full data-model scope (tendencies, tactical approaches, contracts, club finances and manager philosophy) as the standard. Until a usable data export exists, model fictional player/manager personalities **explicitly** using stable, versioned simulation inputs rather than treating imagined psychology as real-world facts.
6. Preserve all sources, original dates, field-by-field confidence, and mismatches. Do not blend EA and PES overall ratings in a single undifferentiated `overall` column.

## Decision and next experiment

**Feasibility proven:** Fully automated player-source downloading, international identity lookup, FC26 attribute/position parsing and valid in-memory warehouse population—all without asking the user to collect files.

**Not yet proven:** A reliable, automatic present-day native PES rating/alternative-position feed, externally sourced FM personality profiles, true current contract wages, or an independently verifiable modern 2026/27 roster source with similarly broad detailed attributes.

**Suggested follow-up:** Build a *source-specific player catalogue* for all 2,498 existing English-division players, reporting per-club/league FC26 matches and missing-data patterns; then experiment with the PES 2020 historical cohort on its own 2019/20 dataset and test safer historical crosswalks. The source strategy remains provisional until those tests complete.

**Controls:** No original production repo, user careers, real PES game files, Render instance or permanent database has been modified; the experimental repository remains separate and the PR remains draft.

# FIFA → PES 2020 converter: Version 2

**Status (19 Oct 2026):** The V2 numeric conversion and 22-edition export **PASSED CI** ([19/19 tests and successful full conversion](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39286441255)). **Rating quality and full source/player coverage are NOT approved**; full-game source coverage has never been independently verified. No deployment, merge or update to existing PES careers.

## Stage 1: historically fuller FIFA 15–20 sources (isolated candidates)

- A pinned public SoFIFA-derived dataset provides six edition-specific files, [players_15.csv through players_20.csv](https://github.com/kushal-gopal/EA-Sports-Fifa/tree/66fc78145ff32ea2dea839459e247833856e0f47). The existing FIFAIndex source for each of these six editions is capped at 10,500 players; more source rows do **not** automatically establish original launch-roster completeness or identity overlap.
- [Standalone restoration builder](../../scripts/build_fifa_fc_restored_2015_2020.py) downloads exact original bytes, checks annual SoFIFA IDs for uniqueness, required identity and rating/role fields, credible GK counts and improved row coverage, computes SHA-256 per year, and records the original archive's count and checksum. It fails rather than silently manufacturing rows.
- [Isolated restoration workflow](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/workflows/fifa-pes-v2-restore-historical.yml) compares all six candidates against the original unchanged 23-source archive and runs a *250-player-per-year smoke conversion* to check compatibility. The resulting source supplement stays separate and marked **CANDIDATE / NOT APPROVED**.
- **Successful first restoration run:** [GitHub Actions #39309545281](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39309545281). Six annual SoFIFA-derived source CSVs contain **100,995 rows** versus **63,000** in the existing six FIFAIndex files (a difference of **37,995 source rows, not verified extra distinct people**). Counts: FIFA15 **15,465**, FIFA16 **14,881**, FIFA17 **17,009**, FIFA18 **17,592**, FIFA19 **17,770**, FIFA20 **18,278**. All six passed no-duplicate-ID checks; their source-labelled goalkeepers numbered 1,703 / 1,618 / 1,925 / 1,979 / 1,986 / 2,036, respectively. **1,500 sampled players** (250/edition) passed the 25-core/4-auxiliary conversion validator. The GitHub run uploaded the *unapproved* restoration archive and smoke-conversion ZIP. The main 281,394-record export remains the previous source-based output.
- Source provider shifts, snapshot dates and mixed-provider numeric ID equivalence have not been independently certified. Do **not** blend the restored 2015–20 files with historical FIFAIndex editions or enable adjacent-year imputation across that boundary without explicit provider-aware source identity. Do **not** replace the primary export automatically.
- FIFA 20 stays the sole calibration edition; FC 25 is excluded from **all** restored sources and remains a separate gap. The next acceptance gates are confirmed year-by-year restoration counts, cross-provider player-identity review, position-stratified conversion sample, and independent calibration tests.

## Real-run results and remaining quality blockers

- **281,394 source player records** converted across 22 source editions, each with 25 bounded PES estimates and 4 auxiliary values. FC25 (2025) was not converted. The downloadable CSV artifact is attached to the successful workflow run; it is **not a console-native option file**.
- **FIFA20 native PES20 accuracy:** 127 provisional name+age+nationality+club candidate links, with only **22** in the deterministic holdout. For position-relevant attributes the raw, uncalibrated mean absolute errors were: GK **13.400** (1 goalkeeper), DEF **6.381** (7 defenders), MID **6.048** (9 midfielders), ATT **5.833** (5 attackers). These numbers are a small, potentially biased provisional matched sample—not proof of game-wide accuracy.
- **Calibration not applied:** proposed FIFA20-only offsets are *unapproved*. The same holdout was previously used to select candidates, so after-shift gains are not independent. In particular, one matched holdout goalkeeper is insufficient for GK calibration.
- **Historical source ceiling confirmed:** 13 FIFAIndex source files in FIFA07–FIFA20 have **exactly 10,500** records; the [published source scraper](https://github.com/lbenz730/fifa_model/blob/2901373e446cc21671916ac0f25ca30716b626aa/fifa_scraper.R) asks for only **700 listing pages per edition** (approximately 15 players per page). This explains the repeated ceiling and prevents calling the files complete game rosters.
- **Independent source comparison:** a separately published SoFIFA-based [FIFA20 CSV](https://github.com/kushal-gopal/EA-Sports-Fifa/blob/66fc78145ff32ea2dea839459e247833856e0f47/players_20.csv) has **18,278 player records**, compared with **10,500** in the present FIFAIndex FIFA20 input. Different snapshots/providers mean the 7,778 row difference is **not automatically a list of missing player identities**.
- **New independent QA:** [source completeness and alternate FIFA20 benchmark workflow](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/workflows/fifa-pes-v2-quality-audit.yml) generates a separate evidence artifact, with per-edition warnings and conservative four-field player matching. It never approves or applies calibration, switches source input, touches careers, or deploys anything.

**Interpretation:** V2 is technically exportable as estimated 25-stat player CSVs. It is **not yet signed off** for historical full-player coverage, verified FIFA20↔PES20 identity matching, position-specific realism or PES import-file production.

## Decisions confirmed

- **FIFA 2020 is the only edition used to train calibration against PES 2020.** FIFA 2019 is NOT used in calibration. Historical FIFA 19 records may still be converted into PES-style ability values using the mapping learned from FIFA20/PES20.
- **FC 25 must not be repaired or estimated.** Edition 2025 is excluded from ALL conversion output and from adjacent-edition evidence. It remains a named source gap until we obtain proper source data.
- For all other editions, the final exported player record must have exactly **25 numeric PES 2020 core abilities**, plus valid **Weak Foot Usage (1–4), Weak Foot Accuracy (1–4), Form (1–8), Injury Resistance (1–3)**.
- All values are bounded to the corresponding observed PES-style ranges and include per-field methods, source columns and confidence. **No blank numerical ability is allowed in the export.**
- Source FIFA CSVs are immutable and retained. Generated ratings are tagged *estimated*, even for closely matching FIFA/PES fields.

## Implementation

| New component | Function |
|---|---|
| [world_fifa_pes_converter_v2.py](../../world_fifa_pes_converter_v2.py) | Full 25-stat reconstructing converter, stable cross-year IDs + DOB, GK and position-aware related-ability fallbacks, peer medians, last-resort source-OVR priors, strict exporter checks |
| [qa_fifa20_pes20_calibration_v2.py](../../qa_fifa20_pes20_calibration_v2.py) | Uses **FIFA20 only**, compares against PES2020 with provisional exact-name/club/nationality/age candidate pairs; held-out MAE; only accepts non-GK offsets that beat baseline by 0.5+ points with adequate samples |
| [scripts/export_fifa_pes_v2.py](../../scripts/export_fifa_pes_v2.py) | Reopens the existing 23-file FIFA hard-copy ZIP and produces **22** edition-specific *complete-estimate* CSVs. FC25 is a manifest-only gap. Each score includes numeric value, method, confidence, source fields. |
| [test_fifa_pes_converter_v2.py](../../test_fifa_pes_converter_v2.py) | 10 targeted assertions: strict 25+4, GK Diving/Reflexes reconstruction, identity matching, FC25 disallow, FIFA20 calibration exclusivity, fallback and role checks |
| [test_fifa_pes_export_v2.py](../../test_fifa_pes_export_v2.py) | 2 export integration tests proving no FC25 year export and all required ability fields numeric |
| [Version 2 full-edition QA workflow](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/workflows/fifa-pes-converter-v2.yml) | Runs unit tests, downloads source ZIP, trains FIFA20/PES20 offsets and exports all non-FC25 editions; the user can download output artifact when successful |

## Recent V2 hardening (separate branch, no live data changes)

- Source-labelled LWB/RWB and additional sided historic positions map conservatively to PES 2020 native roles. No PES non-native wing-back role can pass validated export.
- Each *source-listed* primary/alternative position now has a complete numerical V2 suitability index recalculated after all 25 abilities are reconstructed. These low-confidence indices must not be treated as verified Konami positional familiarity/overall.
- Cross-year player imputation requires stable ID **and** DOB **and** matching identity name, and automatically blocks joins between incompatible source provider namespaces. Matching numeric IDs from different providers is not proof of identity.
- Full CSV output now includes per-attribute source-edition metadata, offset provenance, complete positional suitability JSON and per-edition GK/DEF/MID/ATT method counts.
- Automatic approval of provisional FIFA20/PES20 offset proposals was removed. The QA workflow generates *unapproved* candidate offsets, plus position-family held-out errors, and exports without applying them. Manual review is required to adopt a calibration.
- New synthetic test covers every FIFA 05–FC 27 edition with exactly 22 outputs, 2025 manifest-only gap, 25 validated integer core ratings and positional-fit metadata. A separate live-source QA audit evaluates up to 100 real FIFA05 goalkeepers and records method/column evidence.
- The 127 paired-player identities used previously for research are provisional exact-field matches, not verified EA↔Konami IDs. The same 20% test split was used to choose potential shifts, so exploratory after-shift improvements are **not independent confirmation**.

## Detailed imputation priority

The converter uses the existing v1 same-field mappings, then for missing values:

1. **Related FIFA attributes in the player's own game edition**: e.g., PES GK Reach/Reflexes inferred from the best available combination of FIFA GK Diving, Reflexes, Positioning and Handling. Historical outfield players are never fitted using a goalkeeper cohort.
2. **Same footballer in nearby FIFA editions**, only for exact stable EA/FIFA player ID and date of birth. Adjust for differences in recorded overall, capped at six points. Never consult FC25.
3. **Same-edition, same-positional-family peers**, matched to comparable source overall rating buckets, only when at least eight relevant direct measurements exist.
4. **Position- and source-OVR-based prior** when nothing more specific survives. Explicitly tagged very-low-confidence rather than falsely sourced.

Example: if FIFA05 omits GK Diving, available FIFA05 GK Reflexes/Positioning/Handling provide a defensible initial estimate of a PES-like GK Reach. If FIFA06 data for exactly that player exists, the model may use that too if the own-edition evidence is missing. If neither exists, compare with other same-era goalkeepers. The field is not left blank, but its estimation method is visible for audit.

FIFA05 legacy first/team roles (RS, LS, LCM, RCM, LAM, RAM, RDM, etc.) map to the closest PES2020 native positional role; these mappings are **approximations**, not invented PES positional familiarity. FC27 names recover source first/last names when `common_name` is absent.

## Calibration limits

The PES 2020 source has **15,035 real-game reference player profiles**. Prior FIFA20↔PES2020 same-name/age/nationality/club filtering found **127 candidate links**, of which ~105 train / ~22 holdout. These are **not verified EA–Konami ID matches**. Any learned offsets are experimental and must have improved actual holdout predictions. GK calibration remains **off**, as the benchmark contains too few reliable goalkeeper examples. An improved target-level offset does not mean we have Konami's official rating formula.

## What full export completeness does and does not mean

**Guaranteed by the export validator when CI succeeds:** valid mandatory *25 numerical core attributes plus four numerical auxiliary fields* for every exported non-FC25 player. The manifest will explicitly report player counts by source year, which estimates came from real fields, peer models and priors, and the deliberately skipped 2025 edition.

**Not yet implemented:** game-ready player import structures for PES2020 (height, weight, player skills and styles, ID/appearance mappings, PES 2020-specific player rating formula, position familiarity grids, proper Xbox/PS4/PC option file). A complete numerical PES-style CSV alone cannot be imported directly into the Xbox PES 2020 game; the group's current Xbox challenge is particularly constrained by the console's lack of external option file imports.

## Acceptance gates before feeding live career/squad importer

1. 100% complete 25+4 numerical attribute fields across all **22** non-FC25 editions; no invalid primary positions or identity blanks.
2. Player-count parity with every source edition that was successfully downloaded, except explicit FC25 gap. No player left out quietly.
3. No training based on FIFA19 or FC25. Calibration evidence is tagged FIFA20/PES20 and evaluated on held-out 2020 candidates.
4. Inspect distribution by GK/outfield, OVR band, historical era and high share of low-confidence reconstructed fields. Particular concern: goalkeeper imputation and clipping of weak outfield GK ratings.
5. Only after data-QA passes should we design the PES option-file encoder and decide how PC/PS4 can consume it.

**Current state:** The revised tests, live FIFA05 goalkeeper audit, FIFA20 position-family benchmarking and 22-edition full export require a successful GitHub Actions run before numerical completeness/method/accuracy results can be claimed. All changes are confined to the public isolated testing repository and draft PR.

# FIFA → PES 2020 converter: Version 2

**Status:** code complete for review; the first full-archive QA run is **queued** on GitHub, not yet verified. **No deployment, merger or update to existing PES careers.**

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

**Current state:** QA workflow queued. Until it reports success, we have a developed v2 pipeline, not a verified full output ZIP. All changes are confined to the public isolated testing repository and draft PR.

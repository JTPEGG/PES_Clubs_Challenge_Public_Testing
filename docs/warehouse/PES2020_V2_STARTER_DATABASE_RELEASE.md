# PES Clubs Challenge — Version 2 player database baseline

**Build date:** 20 October 2026  
**Code branch:** `feat/fifa-pes-converter-v2-complete` in `JTPEGG/PES_Clubs_Challenge_Public_Testing`  
**Production:** Not merged, deployed, or connected to live career records.

## Frozen scope

The selected source database is **22 edition-specific CSVs**, from FIFA 05 to FC 27, *excluding FC 25*. Original data is retained without alteration, and new FIFA 15–20 source files replace entire editions rather than stitching incompatible player snapshots together. The source baseline contains **319,389 annual player records**; this is *not* a count of distinct footballers across years.

The source-selection builder `scripts/assemble_fifa_pes_v2_final_sources.py` and its tests establish source SHA-256 parity and 22-edition coverage. The final conversion workflow is `.github/workflows/fifa-pes-v2-final-database.yml`. Its three conversion jobs run independently and the release job verifies the row count and all 25+4 integers before publishing the downloadable package.

## Source counts and selection

| Edition | Player rows | Selected source provider |
|---|---:|---|
| FIFA 05 | 10,993 | FIFAIndex-derived historical |
| FIFA 06 | 10,176 | FIFAIndex-derived historical |
| FIFA 07 | 10,500 | FIFAIndex-derived historical, page-limited |
| FIFA 08 | 10,500 | FIFAIndex-derived historical, page-limited |
| FIFA 09 | 10,500 | FIFAIndex-derived historical, page-limited |
| FIFA 10 | 10,500 | FIFAIndex-derived historical, page-limited |
| FIFA 11 | 10,478 | FIFAIndex-derived historical; coverage unverified |
| FIFA 12 | 10,500 | FIFAIndex-derived historical, page-limited |
| FIFA 13 | 10,500 | FIFAIndex-derived historical, page-limited |
| FIFA 14 | 10,500 | FIFAIndex-derived historical, page-limited |
| FIFA 15 | 15,465 | Pinned SoFIFA-derived replacement |
| FIFA 16 | 14,881 | Pinned SoFIFA-derived replacement |
| FIFA 17 | 17,009 | Pinned SoFIFA-derived replacement |
| FIFA 18 | 17,592 | Pinned SoFIFA-derived replacement |
| FIFA 19 | 17,770 | Pinned SoFIFA-derived replacement (**not** calibration) |
| FIFA 20 | 18,278 | Pinned SoFIFA-derived replacement (sole PES20 calibration candidate) |
| FIFA 21 | 18,944 | Existing pinned source |
| FIFA 22 | 19,239 | Existing pinned source |
| FIFA 23 | 18,539 | Existing pinned source |
| FC 24 | 18,331 | Existing pinned source |
| FC 25 | — | **Explicit missing edition; never manufactured** |
| FC 26 | 18,405 | Existing pinned source |
| FC 27 | 19,789 | Existing pinned source |

**New 2015–20 coverage:** 100,995 edition-specific rows, versus 63,000 rows in the old six source years, or **37,995 more rows**. This does not automatically prove 37,995 additional distinct player identities. Individual old-to-new potential overlaps are reported by strict name, date of birth, and nationality; they are **not automatic ID crosswalks** and never cause original source records to be spliced together.

## Converter and data contract

For every converted player record, the V2 export requires **25 integer PES-style core ratings (40–99)** and **four auxiliary integer ratings** (Weak Foot Usage 1–4; Weak Foot Accuracy 1–4; Form 1–8; Injury Resistance 1–3). It also retains the source edition, original source ID, **namespaced source player key**, provider, source club, nationality, height, weight, preferred foot if present, source overall, positional suitability estimates, and per-attribute provenance. Missing auxiliary game-specific metadata cannot be invented.

- FIFA20 alone may be used to calibrate against PES2020; unapproved experimental offsets stay disabled.
- Adjacent-year missing-stat reconstruction **must not** link numeric player IDs across different source providers.
- Source provenance and coverage warnings are recorded in the source manifest and final export manifest.
- Existing launch-date snapshots, source completeness and EA/Konami cross-game identity mappings are **not independently certified**.
- The rating CSVs are **not native PES2020 Xbox/PC/PS4 option files**. PES overall formula, appearance IDs, skills, playing styles, physical completion and platform-specific game-file encoding belong to the next development phase. Xbox does not support ordinary external PES option-file imports.

## Final end-to-end verification — 20 October 2026

**[Completed GitHub Actions run](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39397460464) — SUCCESS.**

**[Download the versioned full player database starter package](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39397460464/artifacts/12253683166)**. This artifact contains the converted PES2020-style player rating ZIP, the separately preserved 22-edition source ZIP, and `START_HERE.txt`.

Final validation confirmed **319,389 annual player records**, **7,984,725 valid integer core ratings**, and **1,277,556 valid integer auxiliary ratings** across **22 editions**. No FC25 player rows were included, and no original career or production data was modified.

**Identity follow-up:** The release audit found **zero missing source player IDs**, but **139 repeated provider-and-year-namespaced source IDs** across the 319,389 exported annual records. Such collisions may reflect duplicate source rows or source identity reuse; they have **not** been silently deduplicated. Until investigated, the `namespaced_source_player_key` field MUST NOT be treated as a guaranteed primary/foreign key in a future game-file importer. A stable per-row source-record key, documented collision handling, and duplicate identity review are a specific next-stage task; do not invent identities or drop players automatically.

This is a **complete numerical starter database**, not an officially complete EA/Konami original roster, validated gameplay-rating replication, or native PES2020 game-import asset. Artifact retention is time limited by GitHub Actions, so archive the package separately before expiry.

## Remaining work after starter database creation

1. Prioritise native PES player-editor fields and a real PES2020 game-file encoder for a suitable supported platform.
2. Add full source/attribute QA samples for under-covered FIFA05–14 and category distributions, without inventing missing historical players.
3. Re-evaluate PES2020 FIFA20-only calibration on identity-reviewed independently held-out position and goalkeeper groups. Do not silently apply unapproved offsets.
4. Restore FC25 only after a trustworthy independent full player source is verified.

**Acceptance criterion for this stage:** versioned 22-source archive + one complete 22-edition CSV rating archive, every source row represented once per edition with 25+4 valid integers, no FC25 rows, full per-attribute provenance, and immutable source checksum/parity. Passing this stage is a sufficient starting point for designing the actual PES import format, **not** a claim of perfect rating realism or native import readiness.

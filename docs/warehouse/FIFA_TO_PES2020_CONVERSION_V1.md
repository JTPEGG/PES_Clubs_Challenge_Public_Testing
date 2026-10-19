# FIFA / FC → PES 2020 attribute conversion model (v1)

**Status: implemented and tested, NOT approved as a native PES ratings replacement or deployed into career mode.**

## Files

- [`world_fifa_pes_converter.py`](../../world_fifa_pes_converter.py): source-edition-aware mapping into exactly 25 PES 2020 on-pitch abilities. Each stat includes `value`, `method`, `confidence`, source column names, clipping and optional calibration offset.
- [`scripts/export_fifa_pes_csvs.py`](../../scripts/export_fifa_pes_csvs.py): convert the existing [23-edition hard-copy FIFA CSV archive](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39265496743/artifacts/12193011648) into one **PES-style CSV per FIFA year**, packaged in a new ZIP; source archive remains untouched.
- [`qa_pes_conversion_pilot.py`](../../qa_pes_conversion_pilot.py): actual FIFA05,12,20,21,23,FC27 sample comparison against native PES2020.
- [`test_fifa_pes_converter.py`](../../test_fifa_pes_converter.py) and [`test_fifa_pes_csv_export.py`](../../test_fifa_pes_csv_export.py): source-specific and export regression tests.
- [CI conversion reports and sample export ZIP](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/workflows/fifa-to-pes-converter.yml). A public source audit does not mean we have a game-ready Xbox option file.

## Model source classification

| Status in converted output | Meaning |
|---|---|
| `direct_equivalent` | Closest corresponding FIFA detail field, e.g. sprint speed → PES speed. It is still an estimated PES ability until benchmarked. |
| `weighted_estimate` | Blend of two or more relevant source measures, e.g. ball control + dribbling + agility → tight possession. It may also arise when only one of several required components exists; source fields reveal which. |
| `aggregate_reconstruction` | Detailed source fields missing; infer a low-confidence PES analogue from a FIFA aggregate for that football role. |
| `missing` | No sufficiently relevant input; PES attribute remains NULL / blank. No plausible-looking number is invented. |

**Attributes covered (25):**

offensive_awareness, ball_control, dribbling, tight_possession, low_pass, lofted_pass, finishing, heading, place_kicking, curl, speed, acceleration, kicking_power, jump, physical_contact, balance, stamina, defensive_awareness, ball_winning, aggression, gk_awareness, gk_catching, gk_clearing, gk_reflexes, gk_reach.

All estimates are constrained to **40–99** to reflect this PES2020-style source format. This is a heuristic bound, not evidence of Konami's official conversion formula. For players with extremely weak goalkeeper stats this bound can affect many values. Source values remain untouched in original FIFA CSVs.

**Alternative positions** are read from the edition's explicitly supplied first/main and additional positions (zero, one or multiple), with mapping between FIFA and PES positional naming. No new unlisted positions are guessed. `position_fit_indices` are low-confidence **modelled role-fit indicators**, not Konami OVR or demonstrated PES position familiarity. Do not use them to overwrite known PES-native positional ratings. They are designed for provisional AI-squad-coverage testing with clear provenance.

## Real baseline findings from successful first pilot

| FIFA input edition | Actual input sample | Core PES ability slots available | Notes |
|---|---:|---:|---|
| FIFA 05 | 100 top source rows | 84.0% | Four legacy ability types absent in the first 100 selected rows; remains missing when no credible information exists |
| FIFA 12 | 100 | 100% | Original historical CSV contains many detailed football fields |
| FIFA 20 | 100 | 100% | Same-era candidate benchmark possible against PES2020 |
| FIFA 21 | 100 | 100% | SoFIFA detailed source fields |
| FIFA 23 | 100 | 100% | Different CamelCase input naming |
| EA FC 27 | 100 | 100% | Has current detailed football attributes and explicit alternate positions |

These are **field availability counts, NOT accuracy scores**; players sampled were the *first 100 rows* and are heavily skewed towards high-rated players.

### Calibration: promising but provisional

The native [PES 2020 research dataset](https://github.com/mlblbc/pes---Data-visualization-project) contains 15,035 records and all 25 core abilities. A **127-player** candidate crosswalk was built from **unique same-name, same-age, same-nationality and same-club matches** in FIFA20 and PES20; no PES ID crosswalk proof was available for those individual pairs. Deterministic training sample **105**, holdout **22**.

| Ability | Holdout MAE before | After provisional median shift | Comment |
|---|---:|---:|---|
| Low Pass | 8.36 | 5.91 | promising, not final calibration |
| Lofted Pass | 9.32 | 6.32 | promising |
| Finishing | 10.77 | 7.50 | promising |
| Defensive Awareness | 7.41 | 5.32 | promising |
| Jump | 9.36 | 9.55 | **worse**; do not apply shift |
| GK attributes | ~0.3–0.8 | little/no improvement | Primarily outfield players hitting the GK=40 lower bound; **not useful GK validation** |

**These offsets are NOT enabled by default.** Need a verified sample of actual goalkeepers, audited identities across both systems, multiple eras/positions, and a robust holdout before changing core conversion.

## How to use

```bash
python -m unittest -v test_fifa_pes_converter test_fifa_pes_csv_export

# Convert the real FIFA 05–FC 27 hard-copy archive into 23 separate
# PES2020-style CSV datasets. Does not create an Xbox/PS4/PC option file.
python -m scripts.export_fifa_pes_csvs \
  --source FIFA_05_to_FC_27_CSV_Hard_Copies.zip \
  --output PES2020_estimated_stats_by_fifa_edition.zip

# Small quality-check sample only
python -m scripts.export_fifa_pes_csvs \
  --source FIFA_05_to_FC_27_CSV_Hard_Copies.zip \
  --output PES2020_15_players_per_year.zip \
  --limit-per-edition 15
```

Each year-specific output CSV contains 25 PES-style scores, 25 corresponding provenance methods and 25 source-field trace arrays, along with IDs, source OVR, recorded primary/alternative positions and low-confidence positional-fit estimates.

## Historic PES companion source

[Historic PES data and calibration catalogue](HISTORIC_PES_SOURCE_AND_CALIBRATION.md) compares the downloadable PES20 CSV, PES Master PES 5 and PES 2008–2021 references and the independent [PlayersDB CSV](https://playersdb.app/download/csv) containing 104,452 Konami identity records.

**Verified discovery about PlayersDB:** the actual 30.7 MB CSV has **29 identity/position columns** and **does not include FIFA IDs or individual PES abilities**. The site advertises linked FIFA IDs and historical abilities in its web interface, but those were **not contained in the downloaded CSV**. Treat the CSV as an identity/position archive, not a verified complete conversion training dataset.

## Deployment boundary

This converter is a separate development feature. Nothing is merged into the original production repo, installed on Render or activated in a saved PES career. Position-specific fit, PES playing styles, Konami match graphics and Xbox game-file export remain separate unverified steps.

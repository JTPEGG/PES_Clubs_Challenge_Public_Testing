# PES 2020 native attributes + historical PES/eFootball identities: hard copies

**Status:** real source CSVs downloaded, checksummed, and packaged as a ZIP for the user. No changes to live PES careers. The repository stores the reproducible packaging script and this catalogue; the bulk datasets are distributed only as a downloadable build artifact.

## Delivered

| CSV | Records | Source fields | Actual content |
|---|---:|---:|---|
| `PES_2020_Native_Player_Attributes.csv` | **15,035** | **124** | Game-native PES 2020 attributes: 25 abilities, overall rating, 13 positional ratings, many player skills, playing style, footballer/team/nationality, age, height etc. |
| `PES_eFootball_Historical_Player_Identities.csv` | **104,452** | **29** | Player identities, Konami IDs, reported game editions and positions, birthdates, heights, names and nationalities. It **does not include individual historical PES ratings or FIFA ID mappings** in this downloadable CSV. |

The 119,487 rows are **row occurrences in separate datasets**, NOT 119,487 unique players. The 104,452 identity database may contain names not found in the standalone 2020 ratings dataset and vice versa.

## Original direct sources

1. [PES2020 CSV from research repository, pinned source revision](https://github.com/mlblbc/pes---Data-visualization-project/blob/5882c0023a7f16eda4599adc87c7ba160aa9411e/pes_2020.csv).
2. [PlayersDB full public CSV export](https://playersdb.app/download/csv), a site-wide historical identity archive. **Source is current as of retrieval**, not a pinned immutable edition; the dated SHA256 checksum is recorded in the ZIP.

## Verification

- Full source CSVs were independently downloaded by GitHub Actions.
- Every original file has its byte size, row count, header and SHA256 in `MANIFEST.json`.
- Source files were **not joined, stripped, re-scored, normalised or rewritten**.
- ZIP integrity and both source-file SHA256 digests verified after download.
- `PES_2020_Native_Player_Attributes.csv` SHA256: `911ddcf1947d2447575683c4e6e510c165cc831bde65ada10a2bac85ffdd66c5`.
- `PES_eFootball_Historical_Player_Identities.csv` SHA256: `9def3ffdd76b50c8c8c2f298781d0a91731a0f53c961451c347e42aaee1adc9b`.
- Latest successful run: [PES historical hard copies](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39276466714) (5/5 archive validation tests passed).

## How to reproduce

```bash
python -m unittest -v test_pes_historical_archive
python -m scripts.build_pes_historical_archive \
  --output dist/PES_Historical_Database_Hard_Copies.zip \
  --manifest dist/PES_Historical_Archive_Manifest.csv
```

## Examples from the original PES2020 player file

| PES2020 name | Team | Registered position | Game overall | Ball control | Low pass | CB positional rating | Playing style |
|---|---|---|---:|---:|---:|---:|---|
| NEYMAR | PSG | LWF | 92 | 91 | 86 | 49 | Creative Playmaker |
| M. NEUER | FC BAYERN MÜNCHEN | GK | 89 | 68 | 66 | 56 | Offensive Goalkeeper |
| EDU CAMPABADAL | LUGO RB | RB | 68 | 71 | 70 | 62 | The Destroyer |

The PES2020 native `rating_as_CB` is a position-specific **rating value**; playing positions listed by an attribute or full positional rating should not by themselves be used to claim that a player was eligible to fill that role as an alternative in a PES2020 game. Position familiarity/eligibility must be validated separately.

## Coverage warning

This archive **does NOT contain separate original PES player-rating CSVs for PES 2000–2019 or PES 2021**. The PlayersDB index includes many historical game versions, but only identity and position history. Those editions remain to be acquired and verified individually, possibly through archives or PES-native game database extraction.

Do not label the identity file as historical game attributes or infer one player's PES2020 profile from a Konami ID alone.

No production repository, private career repo, Render instance, original game file or career save has been modified.

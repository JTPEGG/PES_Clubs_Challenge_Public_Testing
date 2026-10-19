# Historical PES databases and calibration evidence (19 October 2026)

**This is a source catalogue and converter benchmark, not a claim that all game editions have complete downloadable player CSV files.**

## What is actually available

| PES edition(s) | Verified source | Form | Import status |
|---|---|---|---|
| PES 2020 | [PES 2020 research CSV](https://github.com/mlblbc/pes---Data-visualization-project/blob/master/pes_2020.csv) | **15,035 rows × 124 columns**, 25 on-pitch attributes, 13 position-specific ratings, 43 player skills | **Direct machine-readable file confirmed**, used in conversion benchmark |
| PES 2021, 2019–2011 | [PES Master search and historic edition database](https://www.pesmaster.com/) | Searchable player pages for each edition | Game-native data exists online; **no verified bulk export as part of this experiment** |
| PES 2010, PES 2009, PES 2008 | [PES Master historical announcement](https://blog.pesmaster.com/2025/07/relive-the-classics-pes-2008-2009-and-2010-databases-now-available-on-pes-master.html) | Game-native player profiles sourced from historical database exports | Web player data verified; extraction still needs a repeatable supplied archive |
| PES 5 (2005/06) | [PES Master PES 5](https://www.pesmaster.com/pes-5/search/) | 4,895 searchable players in current search index, classic old-gen ability model | Browse/reference; **not yet a downloadable complete CSV** |
| PES 3, PES 6 and 2008–09 | [Older PES ratings community project](https://www.pesgaming.com/forums/threads/most-complete-player-stats-database-for-older-pes-games.105903/) | Maintainer claims old-game player stats; PES4 extraction gap | Leads only; not validated as complete CSV |
| Broad PES/eFootball history | [PlayersDB](https://playersdb.app/) | October 2026 public site reports **104,452 unique Konami players** and **34,815 FIFA ID links**, with downloadable CSV and JSONL advertised | **Very promising crosswalk**; cannot assert counts, coverage, data version or format beyond site's own stated figures without inspecting downloaded file |
| PES 2000–2004 | N/A | Early Winning Eleven / ISS editions are not the same yearly naming convention as FIFA | No complete edition-matched downloadable dataset verified here |

For PES 2017, for example, PES Master allows filtering detailed abilities and skills, but web availability is not the same as an unblocked/approved bulk file feed. At the time of this review, Football Life remains a separate PES21-family derivative to investigate rather than evidence of a 2026/27 original PES data pack.

## PES 2020 empirical calibration

The experimental [FIFA -> PES converter](../../world_fifa_pes_converter.py) maps 25 ability fields using documented FIFA inputs, optionally reconstructing from aggregate categories with **low confidence**. It does not invent PES skills, original playing styles or native PES overall ratings. Alternative positions are **only** the roles explicitly listed in the source; modelled suitability is labelled *not PES OVR*.

**Independent benchmark:** Use actual PES2020 and FIFA20 research CSV snapshots. Form unique same-name + age + nationality + exact-club keys in both sources. These are **provisional identity candidates, not proof of identity**. Rejection of ambiguous keys, train/holdout split by deterministic player key, and inspection of both raw and median-offset estimated PES stats are part of the QA pipeline. Offsets suggested by the report are **NOT enabled by default** and may be erroneous for goalkeeper/outfield imbalance or community-created records.

[Live CI source QA and results](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/workflows/fifa-to-pes-converter.yml) creates a downloadable artifact with raw model outputs and a field-by-field accuracy comparison, rather than claiming calibration is complete.

## Why historical FIFA is still essential

The packaged FIFA 05–FC27 archive already has **23 year-specific editions**. The early FIFA Index CSVs expose 64 columns, including ball control, tackling, acceleration, sprint speed, finishing, GK handling and more. Therefore, **many supposedly 'broad-category-only' historical FIFA editions have detailed source variables**. The missing values within each historical release are determined from the actual row, not by an age-era assumption.

A player of the same name appearing in a PES 2009 site and FIFA 09 is not necessarily the same database identifier. When no robust crosswalk exists, retain PES and FIFA as **separate source-specific player snapshots**.

## Suggested next checks

1. Validate the PlayersDB downloadable file, including whether the FIFA crosswalk is stable by historic edition and whether it actually includes the 25 usable native PES fields.
2. Evaluate the crosswalk identity precision with source IDs rather than only names.
3. Benchmark PES5 and 2008–2021 distributions separately because earlier PES games used different ability categories, field definitions and sometimes overall ratings above 99.
4. Approve calibration curves only when holdout results improve and position/GK metrics are independently checked, then explicitly tag the resulting ratings as *PES-inspired generated values*.
5. Keep every source's original stats immutable in the warehouse; converted PES model snapshots should be re-creatable and versioned.

No original PES production career, game file, or existing Render database has been modified.

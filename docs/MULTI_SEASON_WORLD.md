# Multi-season Football World — Import Contract

The current 2026/27 roster is a **versioned data snapshot** called `england-2026-27-fc27`. It is not the active career. Browsing data never changes the career save.

## Separation rules
- `world_seasons` = labels and chronology of historical or fictional seasons.
- `world_datasets` = the specific imported dataset/version, with its own source date and review status. Multiple versions of a season are possible.
- `world_dataset_entries` = league membership **for that dataset only**.
- `world_dataset_rosters` = player registration **for that dataset only**.
- `world_dataset_ratings` = ability reference **for that dataset only**; never silently use a different season's FC ratings.
- `world_players` and `world_clubs` = shared identity directory. Stable IDs must be preserved even when clubs change. Player biographies and ages must be interpreted at the dataset source date; mutable attributes must not be overwritten globally by future imports.
- `world_pes_player_map` is not proof of a usable PS4 option-file export.
- `is_career_active` is reserved for future save binding. The browsable snapshots currently set it to 0.

## Planned import procedure
1. Collect licensed/source-backed squad, team and rating data with explicit season, version, source and effective date.
2. Stage a **new** dataset ID; never delete or update the existing version in place.
3. Validate competition memberships, unique player identifiers, one club registration per player per snapshot, and historical birth dates.
4. Save new memberships, squads and reference ratings into the dataset-specific tables inside a transaction.
5. Run tests and produce missing/conflict report before marking the dataset reviewable.
6. Switch the **browser's selected dataset**, not the career's active season, through `/world/explore?dataset=<dataset_id>`.
7. Starting a new career from a dataset must explicitly copy/bind that immutable dataset to a new save ID; this is NOT yet implemented.

## Current limitation
2026/27 is currently automatically imported from bundled code into the original namespaced `world_*` tables and snapshotted the first time the explorer runs. A generic externally uploaded historical-dataset importer has **not** yet been built. The architecture and test for a second separate season exist. No automatic in-game career swap exists.

## Safety
Never bulk-replace the global player or club tables. Never infer missing historical contracts, ratings, roster entries or transfer fees. Preserve production databases and old archived challenges. Do not silently merge source records on short/common names.

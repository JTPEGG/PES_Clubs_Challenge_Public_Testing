# Import a new season safely

The example in `examples/sample_historical_dataset.json` is **synthetic test data**, not a 2004/05 historical squad.

## Dataset format
Each input JSON supplies:
- `dataset.id`: unique versioned slug; existing IDs cannot be overwritten
- `dataset.season`: e.g. `2004/05`
- `dataset.title`, `dataset.source`, `dataset.source_date`
- `clubs[]`: explicit club IDs, display name, competition code (ENG1–ENG4 for English leagues in current database)
- `players[]`: explicit source player ID, club ID, name, optional birth date, position, nationality and optional source rating/attributes
- Optional `identity_source` in player or club entry: used to link an identifier to the same source across seasons. Never reuse an external identifier for a different person.
- Optional club `reuse_name_identity: true`: the importer may link an existing club with precisely the same name. Without this explicit claim, an identity is kept distinct rather than guessing.

## Preview and import locally
```bash
python world_import.py examples/sample_historical_dataset.json development.sqlite
python world_import.py examples/sample_historical_dataset.json development.sqlite --apply
python -m unittest -v test_season_rules test_world_v2 test_world_explorer test_world_import
```

**Important**: the CLI will seed the built-in 2026/27 world into the chosen SQLite database before import. Use an isolated *development* copy, not a production or career database.

The first command does not import any historical records but initializes the preview database; it also uses the existing 2026/27 seed. The second creates a new dataset only when all validation succeeds.

New dataset pages then become available at `/world/explore?dataset=DATASET_ID`. This only changes what you are browsing.

## Mandatory controls for future production use
- The current prototype is a developer CLI, **not an admin upload endpoint**. Do not expose arbitrary file uploads publicly.
- Full dataset integrity validation, credible historical sourcing, player-id reconciliation, transactional migrations and a separate career-save binding are required before a dataset is published or used in a new career.
- All EA reference ratings and model valuations are separated from PES 2020 attributes.
- Current game valuation model is `prototype-v1`, for balancing only; it is not a verified transfer fee or player market value.

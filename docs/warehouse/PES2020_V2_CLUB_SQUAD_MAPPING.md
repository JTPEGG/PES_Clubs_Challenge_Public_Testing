# Club and squad mapping: PES V2 starting worlds

**Implementation:** \`world_historical_club_squads.py\`  
**Status:** Complete independent source-to-club map; **not yet activated in a saved career**.  
**Platform target:** PC and PlayStation (actual PES game-file imports are a later stage).

## Verified first release (20 October 2026)

**[GitHub Actions run — PASS](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39406815878)**  
**[Download the validated 22-edition club and squad catalogue](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39406815878/artifacts/12257801670)**

- 319,389 source player records mapped, exactly one entry per original source row
- 13,188 edition-specific club/team entries (**not 13,188 unique clubs**)
- 316,624 player rows at known source clubs; 531 explicitly listed free agents; 2,234 players with no reliable source club
- 271 source-labelled competition entries, with historical memberships absent/unknown in some editions
- 139 repeated source player ID occurrences preserved safely under distinct source-row player keys
- 22/22 edition manifests, SQLite foreign keys and all source/player count checks passed
- FC27: source has 17,849 men's and 1,940 women's player records; men/women team names are separated, and homonymous Nacional clubs from different sourced leagues no longer merge

**Scope:** Every source player is represented; this does not prove complete original game rosters, verified league membership or import-ready PES saves. The generated SQLite database has not been installed into live careers or deployed.

## Inputs

Uses the exact two versioned files previously published in [the completed V2 player database release](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39397460464):

1. \`FIFA_SOURCE_DATABASES_22_YEARS_VERSIONED.zip\` — original full edition CSV sources, immutable and SHA-256 checked.
2. \`PES2020_V2_COMPLETE_ESTIMATED_PLAYER_DATABASE_22_YEARS.zip\` — the 319,389 player records with fully numeric PES gameplay estimates.

Do not use separate independently downloaded snapshots for these two inputs: row order is deliberately verified against the same release. FIFA 2025/FC25 remains an explicit missing source edition.

## Output

[Club/squad mapping workflow](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/workflows/fifa-pes-v2-club-squad-map.yml) produces a downloadable artifact containing:

- **\`PES_V2_22_EDITION_CLUB_SQUAD_MAP.sqlite\`** — edition-isolated clubs, leagues and every source player with correct squad assignment, all 25 PES numeric ratings and 4 auxiliary fields, source demographics, source IDs, and original loan-parent evidence where present
- **\`PES_V2_ALL_EDITION_CLUBS.csv\`** — season, source club, source league where present, gender where present, squad size and verification status
- **\`CLUB_SQUAD_MAPPING_MANIFEST.json\`** — per-year roster/club/unattached counts, missing league flags, duplicate ID counts, source SHA-256 references
- **\`README.txt\`** — safety notes and preview instructions

The SQLite catalogue is **standalone, separate from all existing career and production tables**. The query helpers \`available_editions(conn)\`, \`select_edition(conn, edition)\` and \`club_squad(conn, edition, club_key)\` make database selection and full squad viewing possible without mutating an existing career.

## Club identity rules

- Club keys always include their **source edition**. Historic clubs are not assumed to be stable across editions or data providers.
- Prefer a source-supplied numeric club ID when available.
- When no ID exists, use the original club name **and its source-listed league** (if any), avoiding homonyms like Nacional in Portugal versus Nacional from South America.
- Where explicitly sourced, gender distinguishes men's and women's team registrations. FC27 includes both; Arsenal Women, for example, is **not** merged into the men's Arsenal squad.
- The player's original source ID is retained verbatim. A separate stable \`player_key\` uses edition plus source row ordinal, so the known 139 repeated source-ID occurrences do not silently delete or overwrite player records.
- Loan-parent source information is preserved separately, but current squad assignment follows the original source team field. We do not invent contract or registration ownership.
- A player with an explicitly sourced free-agent status remains unattached. Blank or unknown club data goes in a separate **unknown** category, not in a fabricated squad.
- Leagues are populated **only where the annual source includes them**. In particular, FIFA05–20 sources do not consistently include leagues, and FIFA23's selected archive lacks reliable league identifiers. Their clubs and squads are still mapped, but competition memberships must be verified or enriched later.
- A source-listed league is **not automatically a verified historical league membership** or a confirmed opening-day squad. Club IDs, aliases, and membership are kept source-specific.

## Usage

From a standalone SQLite connection:

\`\`\`python
import sqlite3
from world_historical_club_squads import available_editions, select_edition, club_squad

db = "PES_V2_22_EDITION_CLUB_SQUAD_MAP.sqlite"
with sqlite3.connect(db) as conn:
    years = available_editions(conn)                  # 22 FIFA editions
    world = select_edition(conn, 2020)                # clubs and initial squads
    first_club = world["club_preview"][0]["club_key"]
    squad = club_squad(conn, 2020, first_club)         # players, ratings, source IDs
\`\`\`

## Stage boundary

**Now complete:** source-derived historical club and squad mappings, numerical player attributes attached, separate annual snapshots, IDs/provenance, free-agent pools, and a read-only season selector.

**Next:** connect the selected annual world to \`world_datasets\` and the career creator in a **new immutable sandbox dataset**, after deciding which league memberships to recognise and how to model unknown budgets/wages. Then we can give those clubs to the AI transfer-window engine.

No salary, transfer budget, wage, contract status, national or league membership, historical club identity, or owner was made up by this mapper. Actual PES/PC/PlayStation export/option-file encoding is deferred.

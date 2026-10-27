# FC27 — App-world player registrations and playable PES squad export foundation

**21 October 2026 · Development branch `feat/fifa-pes-converter-v2-complete` only.**

## Agreed architecture

**The app owns the football world; PES 2020 is the match engine.** Teams in background leagues do not need to exist or have playable files in PES unless they play a match against a user-controlled club or enter a playable league. Domestic and transfer simulation can run entirely within the app from its player and club database. Eventually European competition participants may require separate PES preparation, but that is explicitly deferred.

The nine selectable countries remain England, Germany, Spain, France, Italy, Scotland, Netherlands, Portugal and MLS. **344** existing original FC27 club identities are initial playable candidates; **315** other source clubs remain in background simulation. MLS remains a playable league with no sporting promotion/relegation.

## Verified direct historical mapping

The existing men-only V2 career/squad database stores exact, edition-scoped `club_key` values that **already match all 659 club keys** in the derived FC27 2026/27 competition registry. No speculative name matching is required.

Real input source: `PES_V2_22_EDITION_CLUB_SQUAD_MAP.sqlite`, from [successful men-only historical release](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39409971210). The original 2027 edition contains **17,849** source player records. **17,593** belong to the current 659 active club keys; **256** are outside those active game clubs and remain untouched in the immutable source archive. This avoids accidentally reintroducing the Indian Super League or wrongly joining unregistered source groups.

From the 17,593 active registrations, the initial **344 playable club candidates have 9,269 source players**. The other **8,324** belong to background clubs. These 2026/27 source player records already carry full **25 estimated PES 2020 core abilities**, four auxiliary attributes and stable player identity data, but are **not** native PES edit-file player IDs.

**Do not confuse:** `source_player_id` from an EA/FIFA provider, `player_key` from the V2 app-source archive, and a game binary `pes_player_id`. They are different identity namespaces.

## New isolated development output

Files:
- `world_fc27_app_pes_squad_sync.py` — immutable-source import into a new app **current-registration** SQLite table, transfer event recording, source-ID-proof review exporter.
- `scripts/build_fc27_app_pes_squad_sync_preview.py` — constructs a *new standalone* SQLite from the derived FC27 world + men-only source, never modifies the supplied source files or production careers.
- `test_world_fc27_app_pes_squad_sync.py` — synthetic fixtures and tests for registered club/player IDs, transfers, replays, export correctness and game-ID gating.
- `.github/workflows/fc27-app-pes-squad-sync.yml` — repeatable end-to-end build from the existing immutable GitHub artifacts. Includes a **disposable transfer using a real source player ID**, demonstrating background-to-playable transfers while preserving the delivered original starting squads.

Build output:
1. `FC27_2026_27_APP_PLAYER_REGISTRATION_STAGING.sqlite` — edition-scoped app player registration/squad world. Current club may change after verified simulated transfers; original source club is preserved independently.
2. `FC27_PLAYABLE_CURRENT_SQUADS_PES2020_REVIEW_ONLY.csv` — only the **current** 344 playable clubs' players, all 25+4 numeric PES attributes, 2027 `player_key`, original and current club IDs, game-ID columns left blank until verified.
3. `FC27_PES_SQUAD_SYNC_READINESS.json` — squad coverage, missing team/player game-ID counts, CSV checksum, `native_pes_edit_file_created=false`, `ready_for_game_import=false`.
4. `FC27_APP_PES_SQUAD_SYNC_BUILD_REPORT.json` — count reconciliation and technical validation.

The registration layer uses `fc27_app_player_registration` (source versus current club), `fc27_app_transfer_ledger` (replay-safe event IDs and revision checks), `fc27_verified_pes_team_identity` and `fc27_verified_pes_player_identity` (both **initially empty**). Current export uses `fc27_playable_current_squad`.

### Sample future real workflow

1. Player at a non-playable Polish club accepts a move to a playable English team through the transfer engine.
2. Once transaction is *finalised*, the app records a stable `transaction_key` and updates only `current_club_key`, not the original source identity. Contract, wages, transfer fee, and budgeting remain the responsibility of the app's actual transfer/career system.
3. The CSV exporter detects that this player's **new** club is playable and includes their existing PES-style attributes and source player identity in the target club's current squad. The source/origin remains traceable.
4. If that player later moves to a background club, they disappear from the playable export, but remain in the app world.
5. A future validated PES adapter resolves mapped `pes_team_id` and `pes_player_id`, reconciles slot/roster constraints, and emits a PC or PS4-compatible game update. **No native adapter exists yet**.

For promotion of a formerly background club into a playable division, the career must **change that club's playable registration status** and then provide a valid PES team slot and export its existing player assignments. Such changes are **not yet wired into** the production career season-end engine.

## Important protections

- All original 659 FC27 club source identifiers are cross-matched directly against the historical men-only player catalogue before staging; no fuzzy links.
- Never silently assign `club_unknown` or free agents to a club; no blank PES attributes in the exporter.
- No FIFA source ID is treated as a PES player/team ID.
- `move_player` is replay-safe for the exact same transaction, rejects reused transaction keys for other moves, detects wrong current-owner or nonexistent destination clubs, and retains the source assignment.
- A source game team or player numeric ID may only be entered with meaningful game-edit evidence, requiring unique (platform, game-ID) mapping; currently **no such mapping has been populated**.
- Xbox PES 2020 does not support ordinary external PES option-file imports. This update pipeline targets future PC/PS4 adapter implementation, not an invented Xbox file.
- CSV is **review-only** and never presented as a playable PES binary. The native-file readiness gate explicitly fails until actual game IDs are verified and the platform adapter exists.
- A development staging import with real names, attributes and IDs is **not** proof that faces, kits, club editing slots, player allocation capacity, save compatibility or other PES binary-specific constraints are supported.
- FC26 backfill remains untouched and no live production career is modified.

## Remaining essential integration steps

1. Capture a **genuine PES 2020 PC/PS4 game edit-file baseline** to build source-club-to-game-team and source-player-to-game-player ID mappings. Check the number and type of editable team/player slots; avoid slot collisions.
2. Build a validated PC/PS4 PES file writer/adapter using that baseline and prove it can be imported, backed up and reverted. The current CSV cannot be imported as a squad update on its own.
3. Hook finalised transactions from `JTPEGG/PES_Clubs_Challenge_Development` into this event-based app player registry; don't alter production. Read/write must use a proper transaction boundary so the transfer and squad state cannot diverge.
4. Add a simulated promotion/regional league finalisation event that modifies club playability **only when** a team actually joins/leaves the playable scope, instead of importing entire non-playable leagues into PES.
5. Defer extra European cups and other source background competitions until base domestic-squad sync works.

This is **an implemented and tested app-to-export foundation**, not a claim to a finished PES 2020 game import.

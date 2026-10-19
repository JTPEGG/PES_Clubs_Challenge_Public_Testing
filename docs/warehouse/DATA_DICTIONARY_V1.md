# PES Clubs Challenge — Warehouse Data Dictionary v1

**Status: proposed, not populated or deployed.** The corresponding additive SQLite schema is [warehouse/schema_v1.sql](../../warehouse/schema_v1.sql). All new tables are prefixed `wh_` to avoid conflicting with existing development career tables.

A *record* can be a confirmed source observation, an explicit simulation model output, an operator assertion, or a derived value. The `origin` field captures this distinction. **NULL means unknown; do not fill absent facts with zero, defaults or invented information.** Source rows must have `source_id`; modelled rows must identify a stable model version where present.

This dictionary covers **each new warehouse field**. Existing system-of-record fields and migration rules are documented in [WAREHOUSE_ARCHITECTURE_V1.md](WAREHOUSE_ARCHITECTURE_V1.md). Full reference-data population is a separate next phase.

## `wh_sources`

Identity, permitted-use basis, and version of every incoming data source or internal simulation.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `source_id` | TEXT | Yes | Stable unique slug for this external provider/export or internal model. |
| `name` | TEXT | Yes | Source title (for example permitted ratings export or simulator model). |
| `source_url` | TEXT | No | Public reference URL where available; NULL for offline or internal sources. |
| `rights_basis` | TEXT | Yes | Licence/permission/original research/internal simulation or unresolved rights status. |
| `source_version` | TEXT | Yes | Immutable edition, snapshot, file hash or model version of this source. |
| `retrieved_on` | TEXT | No | Date data were retrieved. Not necessarily the observation's effective date. |
| `description` | TEXT | No | Scope, caveats and permitted reuse limits. |

## `wh_field_evidence`

Field-level traceability: which source or model supported a specific fact at a specified time.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `evidence_id` | INTEGER | Yes | Unique evidence row; supports multiple independent observations per fact. |
| `dataset_id` | TEXT | Yes | Immutable season/source dataset identifier; prevents 2004/05 values overwriting 2026/27. |
| `entity_type` | TEXT | Yes | Supported record type: player, club, manager, competition, stadium or contract. |
| `entity_id` | TEXT | Yes | Source-scoped or canonical target identifier expressed as text. |
| `field_path` | TEXT | Yes | Precise field name or path (for example attributes.sprint_speed). |
| `source_id` | TEXT | Yes | References wh_sources; provides a traceable evidence or simulation origin. |
| `origin` | TEXT | Yes | Provenance category: source, model, operator or derived. Does not assert factual correctness. |
| `valid_as_of` | TEXT | No | Date the source fact is intended to describe. |
| `value_description` | TEXT | No | Optional explanation of discrepancies or model assumptions. |
| `recorded_on` | TEXT | Yes | Date/time recorded in the warehouse. |

## `wh_player_positions`

Dataset-scoped primary and unlimited alternative playing positions, with optional sourced position-specific suitability.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `dataset_id` | TEXT | Yes | Immutable season/source dataset identifier; prevents 2004/05 values overwriting 2026/27. |
| `player_id` | INTEGER | Yes | References world_players; stable internal player identity. |
| `position_code` | TEXT | Yes | Normalised playing role (for example CB, RB or DM), not a broad defender group. |
| `position_kind` | TEXT | Yes | Primary or alternative. A player may have many alternatives, only one primary. |
| `suitability_ovr` | INTEGER | No | Optional 1–99 suitability in this specific position; never invented from overall. |
| `origin` | TEXT | Yes | Provenance category: source, model, operator or derived. Does not assert factual correctness. |
| `source_id` | TEXT | Yes | References wh_sources; provides a traceable evidence or simulation origin. |
| `source_note` | TEXT | Yes | Explicit source evidence note. Does not automatically certify suitability. |

## `wh_player_attributes`

Fine-grained 1–99 football attributes; independent of aggregate EA reference-category ratings.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `dataset_id` | TEXT | Yes | Immutable season/source dataset identifier; prevents 2004/05 values overwriting 2026/27. |
| `player_id` | INTEGER | Yes | References world_players; stable internal player identity. |
| `attribute_key` | TEXT | Yes | Specific measurable skill, e.g. sprint_speed or stamina; not a vague position grade. |
| `value` | INTEGER | Yes | Recorded numeric observation on the declared scale. |
| `scale` | TEXT | Yes | Explicit 1–99 scale for all v1 source and simulation attribute values. |
| `origin` | TEXT | Yes | Provenance category: source, model, operator or derived. Does not assert factual correctness. |
| `source_id` | TEXT | Yes | References wh_sources; provides a traceable evidence or simulation origin. |

## `wh_player_traits`

Stable player behaviour dimensions; transient happiness and demands belong to an individual career.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `dataset_id` | TEXT | Yes | Immutable season/source dataset identifier; prevents 2004/05 values overwriting 2026/27. |
| `player_id` | INTEGER | Yes | References world_players; stable internal player identity. |
| `trait_key` | TEXT | Yes | Behaviour dimension, e.g. ambition, loyalty, professionalism or adaptability. |
| `score` | INTEGER | Yes | Model/source value on the 0–100 behavioural scale. |
| `origin` | TEXT | Yes | Provenance category: source, model, operator or derived. Does not assert factual correctness. |
| `source_id` | TEXT | Yes | References wh_sources; provides a traceable evidence or simulation origin. |
| `model_version` | TEXT | No | Model definition that generated a fictional observation; required when origin=model. |

## `wh_club_profiles`

Institutional stature, board ambition and recruitment approach independent of current player quality.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `dataset_id` | TEXT | Yes | Immutable season/source dataset identifier; prevents 2004/05 values overwriting 2026/27. |
| `club_id` | INTEGER | Yes | References world_clubs; stable internal club identity. |
| `institutional_stature` | INTEGER | No | Historical club stature independent of this season's squad. |
| `domestic_reputation` | INTEGER | No | Reputation within the club's domestic market. |
| `continental_reputation` | INTEGER | No | Standing with clubs and players in continental football. |
| `fanbase_score` | INTEGER | No | Relative audience/support scale, not a fabricated attendance count. |
| `board_ambition` | TEXT | No | Board target band for this season: survival through title. |
| `ownership_strategy` | TEXT | No | Owner financial and player-sale philosophy. |
| `recruitment_strategy` | TEXT | No | Club preference for prospects, value or proven first-team quality. |
| `origin` | TEXT | Yes | Provenance category: source, model, operator or derived. Does not assert factual correctness. |
| `source_id` | TEXT | Yes | References wh_sources; provides a traceable evidence or simulation origin. |

## `wh_stadiums`

Real-world stadium identities and physical information; shared across changing club tenancies.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `stadium_id` | TEXT | Yes | Persistent stadium identity, separate from club tenancy. |
| `name` | TEXT | Yes | Recorded ground name; not necessarily the name of the current sponsor. |
| `city` | TEXT | No | Stadium city/municipality. |
| `country` | TEXT | No | Stadium country. |
| `opened_year` | INTEGER | No | Year the stadium opened, if verified. |
| `capacity` | INTEGER | No | Official/sourced seating capacity; may differ by season. |
| `pitch_surface` | TEXT | No | Reported pitch surface when known. |
| `source_id` | TEXT | Yes | References wh_sources; provides a traceable evidence or simulation origin. |

## `wh_club_stadiums`

Season-specific club-to-stadium assignment; one primary home ground per club and dataset.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `dataset_id` | TEXT | Yes | Immutable season/source dataset identifier; prevents 2004/05 values overwriting 2026/27. |
| `club_id` | INTEGER | Yes | References world_clubs; stable internal club identity. |
| `stadium_id` | TEXT | Yes | Persistent stadium identity, separate from club tenancy. |
| `is_home` | INTEGER | Yes | Exactly one main home ground per club and dataset; 0 represents other utilised venue. |
| `usage_note` | TEXT | No | Groundshare, temporary tenancy or other context. |

## `wh_club_facilities`

Club training, youth and medical infrastructure, optionally scored where evidence or explicit models exist.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `dataset_id` | TEXT | Yes | Immutable season/source dataset identifier; prevents 2004/05 values overwriting 2026/27. |
| `club_id` | INTEGER | Yes | References world_clubs; stable internal club identity. |
| `training_quality` | INTEGER | No | Relative training-site quality, 0–100, if sourced or explicitly modelled. |
| `academy_quality` | INTEGER | No | Relative youth academy facilities quality, 0–100. |
| `youth_recruitment` | INTEGER | No | Relative ability to recruit youth candidates, 0–100. |
| `medical_quality` | INTEGER | No | Relative medical/sports-science facilities quality, 0–100. |
| `origin` | TEXT | Yes | Provenance category: source, model, operator or derived. Does not assert factual correctness. |
| `source_id` | TEXT | Yes | References wh_sources; provides a traceable evidence or simulation origin. |

## `wh_managers`

Persistent manager identities (not tied permanently to a club).

| Field | Type | Required | Meaning |
|---|---|---|---|
| `manager_id` | TEXT | Yes | Stable unique identifier for a real or fictional manager. |
| `full_name` | TEXT | Yes | Person's full name from a permitted source or explicitly declared fictional source. |
| `birth_date` | TEXT | No | ISO date of birth; source date governs age calculation. |
| `nationality` | TEXT | No | Nationality when known; NULL means unavailable. |
| `created_on` | TEXT | Yes | Timestamp when the manager identity was created. |

## `wh_manager_external_ids`

Verified source-scoped manager ID links, avoiding accidental cross-season name matches.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `source_id` | TEXT | Yes | References wh_sources; provides a traceable evidence or simulation origin. |
| `external_id` | TEXT | Yes | Manager identifier under a particular source, not an inferred name match. |
| `manager_id` | TEXT | Yes | Persistent manager identity; never assume two same-named managers are identical. |

## `wh_manager_profiles`

Managerial behaviours and football philosophy at a dataset snapshot.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `dataset_id` | TEXT | Yes | Immutable season/source dataset identifier; prevents 2004/05 values overwriting 2026/27. |
| `manager_id` | TEXT | Yes | Persistent manager identity; never assume two same-named managers are identical. |
| `reputation` | INTEGER | No | Snapshot managerial standing, 0–100, independent of club reputation. |
| `tactical_style` | TEXT | No | Preferred tactical identity, if available. |
| `preferred_formation` | TEXT | No | Preferred formation string, e.g. 4-3-3, not a mandated formation. |
| `preferred_pressing` | TEXT | No | Documented or modelled pressing intensity/style. |
| `youth_priority` | INTEGER | No | Preference for developing and trusting young players, 0–100. |
| `negotiation_aggression` | INTEGER | No | Tendency toward firm counteroffers and bargaining, 0–100. |
| `loyalty` | INTEGER | No | Propensity to stay with a club, 0–100. |
| `ambition` | INTEGER | No | Motivation to pursue higher-profile or stronger appointments, 0–100. |
| `risk_tolerance` | INTEGER | No | Tolerance for selling rotation players or backing speculative recruits. |
| `transfer_philosophy` | TEXT | No | Overall squad-building approach and sale-protection preference. |
| `origin` | TEXT | Yes | Provenance category: source, model, operator or derived. Does not assert factual correctness. |
| `source_id` | TEXT | Yes | References wh_sources; provides a traceable evidence or simulation origin. |

## `wh_manager_appointments`

Explicit club-manager tenures including permanent, interim and caretaker roles.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `appointment_id` | TEXT | Yes | Unique contract/tenure event identity for replay and career history. |
| `dataset_id` | TEXT | Yes | Immutable season/source dataset identifier; prevents 2004/05 values overwriting 2026/27. |
| `manager_id` | TEXT | Yes | Persistent manager identity; never assume two same-named managers are identical. |
| `club_id` | INTEGER | Yes | References world_clubs; stable internal club identity. |
| `started_on` | TEXT | Yes | Start date of manager or stadium tenure. |
| `ended_on` | TEXT | No | End date; NULL represents unknown or ongoing tenure, not proof of employment. |
| `appointment_type` | TEXT | Yes | Permanent, interim or caretaker appointment category. |
| `origin` | TEXT | Yes | Provenance category: source, model, operator or derived. Does not assert factual correctness. |
| `source_id` | TEXT | Yes | References wh_sources; provides a traceable evidence or simulation origin. |

## `wh_competition_rules`

Season-versioned competition formats, promotion/relegation, eligibility and prestige rules.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `dataset_id` | TEXT | Yes | Immutable season/source dataset identifier; prevents 2004/05 values overwriting 2026/27. |
| `competition_id` | TEXT | Yes | References world_competitions; stable competition identity. |
| `format` | TEXT | Yes | Competition structure, e.g. league or knockout. |
| `participating_clubs` | INTEGER | No | Expected entrants in this specific season, not a permanent size. |
| `points_for_win` | INTEGER | No | League points awarded for a win; NULL when irrelevant. |
| `points_for_draw` | INTEGER | No | League points awarded for a draw; NULL when irrelevant. |
| `promoted_places` | INTEGER | No | Direct promotion/relegation slots only; playoff details need additional versioned rules. |
| `relegated_places` | INTEGER | No | Direct relegation slots only; NULL when not applicable. |
| `registration_policy` | TEXT | No | Registration/deadline rule reference; enforced by the career engine. |
| `foreign_player_rule` | TEXT | No | Foreign-player or work-permit restrictions when present. |
| `domestic_cup_qualification` | TEXT | No | Domestic cup access/qualification reference. |
| `continental_qualification` | TEXT | No | European or other continental qualification scheme reference. |
| `prestige` | INTEGER | No | Competition stature score, season-dependent and explicitly sourced/modelled. |
| `origin` | TEXT | Yes | Provenance category: source, model, operator or derived. Does not assert factual correctness. |
| `source_id` | TEXT | Yes | References wh_sources; provides a traceable evidence or simulation origin. |

## `wh_competition_prizes`

Competition finishing-place reward schedule. Unknown prize amounts remain NULL.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `dataset_id` | TEXT | Yes | Immutable season/source dataset identifier; prevents 2004/05 values overwriting 2026/27. |
| `competition_id` | TEXT | Yes | References world_competitions; stable competition identity. |
| `finish_position` | INTEGER | Yes | League/cup finish rank for the declared prize amount. |
| `prize_gbp` | INTEGER | No | GBP-equivalent award; NULL when not verified, not automatically zero. |
| `source_id` | TEXT | Yes | References wh_sources; provides a traceable evidence or simulation origin. |
| `origin` | TEXT | Yes | Provenance category: source, model, operator or derived. Does not assert factual correctness. |

## Integrity expectations

- At most one `primary` position per player per dataset; unlimited `alternative` positions are allowed.
- A position's `suitability_ovr` is **optional** and independent of the player's aggregate overall. No implicit positional ability penalty is assigned.
- Every source-anchored row references a versioned, rights-catalogued `wh_sources` record.
- Negative fees, invalid ratings, invalid enum values, orphan entities and duplicate external manager IDs are rejected by schema constraints.
- The simultaneous-lineup allocator must count an individual player once even if several alternative positions are eligible.
- Source-date versions and career mutation events are never conflated. Historical snapshots remain immutable.

*Generated from schema field declarations, then annotated with business definitions. Proposed `wh_` fields: 123 across 15 tables.*

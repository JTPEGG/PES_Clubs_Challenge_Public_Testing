# PES Clubs Challenge 2.0 — Season Architecture (2026/27)

Status: agreed product rules, implementation in progress. This is the **development sandbox** only.

## Immutable decisions
- World starts at 2026/27, using verified post-summer-window registrations as the baseline.
- Persistent universe: manager, clubs, player histories, seasons and competitions persist across seasons.
- The real PES 2020 PS4 **League Mode** is the playing environment, not Kick Off mode.
- Each playable season runs as **one uninterrupted PES League Mode competition**.
- A single summer registration window: finalize transfers, development and option-file updates **before** creating the new PES league.
- No January *registration changes* for any club in that active PES competition. Winter negotiations can be future-dated for the following summer.
- Non-playable leagues may simulate January transfers if that does not invalidate currently playable PES squad registrations.
- The app owns season results, fixtures, tables, player stats, transfers, finances and careers; PES owns on-pitch execution, fatigue, injuries in league play.
- Preserve the existing human Fixed Cursor stats separately from simulated footballers' stats.
- Reuse the existing admin fixture-order tool, adjusting it for a full double round robin and home/away integrity.
- Original production repository and save must not be changed by experimental development.

## Fixture integrity
For an even-sized N-club double round robin:
- N*(N-1) match entries league-wide; N-1 opponents per club.
- Each unordered club pair must occur exactly twice: one home, one away.
- Every club plays exactly once per round; expected 2*(N-1) rounds.
- Before a season opens for posting, map PES's actual fixture order to the app through a validated admin edit. Preserve per-round integrity.
- Never change a posted fixture implicitly; corrections are audited.

## Transfers and PES export
- Each move has player_id, from_club_id, to_club_id, agreement date, effective date, status and financial postings.
- Any effective move impacting the active PES league must be deferred to the **next season boundary** after the league starts.
- Maintain explicit PES player and team mapping IDs, source version and confidence. Do not match only by name.
- Exporter must produce checksummed and versioned bundles, validate no duplicate registrations or unmatched players, and support backup/rollback.
- Automated .ted file roundtrip is an unverified engineering dependency: read/modify/re-encrypt/import test on actual PS4 files first.
- Attribute development and decline are computed by the app and exported once each summer (subject to verified compatibility).

## Architecture work
1. Verify separate development DB save key and effective persistence (done: configured development SUPABASE_SAVE_KEY; deploy verification still required).
2. Add pure validation rules and tests before integrating them into live fixture editor.
3. Design versioned relational world schema; preserve/migrate old archive without overwriting it.
4. Construct verified 2026/27 starting data, league allocation matrix and PES mapping.
5. Test physical PS4 competition slot counts, transfers and multiplayer Fixed Cursor.
6. Build full-season world simulator and controlled advancement.

## Risks / non-goals in first iteration
- It is not yet proven that PS4 competition slots can represent League One and League Two as full 24-club in-game competitions.
- No claim that a downloadable .ted editor/exporter currently works.
- Do not implement January squad changes in the ongoing PES league.
- Do not infer missing player abilities, finances or real-world contracts as verified facts.

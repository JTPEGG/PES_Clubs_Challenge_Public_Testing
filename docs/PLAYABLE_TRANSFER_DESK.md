# Playable development Career Transfer Desk

Route: `/world/play`

## Access and safety
This experimental transfer desk is gated with a separate development-only passphrase supplied through Render `WORLD_MARKET_ACCESS_KEY`. It signs an eight-hour HTTPS-only, HttpOnly, SameSite=Strict cookie using `WORLD_MARKET_COOKIE_SECRET`. Every state-changing form requires a signed CSRF token and manager-club server checks.

The same development passphrase grants access to ALL development sandbox careers. This is **not** multi-user account authentication. Do not release to the public or reuse the passphrase for production. The original game remains unaffected.

## Gameplay workflow
1. Sign in to the development desk.
2. Choose an imported season dataset and a manager club. Create a **new career sandbox** with a chosen financial scale and economy version.
3. Make a player offer on behalf of your club, subject to funds and source-derived rating references.
4. Sellers accept for contract discussion, counter or reject under the current deterministic prototype thresholds.
5. Accept a counteroffer or withdraw an open offer to release its reservation.
6. Enter a weekly wage offer, then record a future transfer agreement. No player is registered at the buying club during the active PES League Mode season.
7. Optionally generate up to two competing AI-club offers for a target. AI offers are logged and reserve competing clubs' simulated funds; they cannot be accepted or withdrawn by the human manager.
8. Review history at `/world/careers`, protected by the same sign-in.

## Known limitations
- AI offers are user-triggered deterministic prototypes, not automated/background transfer activity.
- A future agreement **does not** settle payment or register the player. Completion, medicals, free transfers, realistic contract terms, player consent and full summer PES export remain future work.
- All budgets, fees and asking prices come from the fictional `prototype-v1` economy, which requires market calibration.
- Snapshot data may have player-registration conflicts. Do not use it as an independently verified official squad list.
- Multiple managers/users in one career and role-based access are unsupported.
- Historical season datasets can be selected if they have already been imported.
- No full passing CI record has yet been established; avoid claiming production readiness.

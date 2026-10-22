# FC27 2026/27 — 33 source membership groups accepted; movement next

**Decision: 21 October 2026.** Development only on `feat/fifa-pes-converter-v2-complete`, repository `JTPEGG/PES_Clubs_Challenge_Public_Testing`. The original production repository and career saves remain unchanged.

## Scope decision

We accept the **existing FC27 source-derived club membership** in the 33 domestic competitions lacking a linked dated fixture roster; **no further full roster expansion is requested** for those groups. This is an explicit *game-building scope policy*, not a factual certificate of all real-world 2026/27 participants. The project is not instructed to delete these clubs, to replace them with guessed teams, or to change playable status solely because a separate fixture roster is missing.

- All **280** original FC27 source club rows in the 33 accepted groups are retained with the original source names and existing domestic candidate codes.
- Original Greek Super League source group: **4 retained**; their club records remain available in the game data, without generating unlicensed missing Greek clubs.
- German 2. Bundesliga source group: **18 retained**; this division must remain available as a canonical node for Bundesliga ↔ 2. Bundesliga ↔ 3. Liga, even though additional independent roster research is waived.
- Eight 2026 South American league codes have individually reviewed country-backed CONMEBOL entries; those still retain **provisional EA identity status**. No continental competition is represented as a domestic starting division.
- Excluded league remains excluded from the derived active release. Original archives remain immutable.
- The 33 accepted competitions are registered in `fc27_source_as_provided_competition_seasons`; a union view `fc27_2026_27_active_domestic_competitions` lists all **53 active domestic competition codes** with exactly **659** eligible source clubs across them.
- Source-accepted league entries are intentionally stored **outside** `competition_seasons` fixture evidence, to avoid falsely upgrading them to independently verified complete real-world rosters. The `fc27_accepted_source_as_provided_clubs` view preserves all 280 rows and their original source evidence status.
- Playability and season-end promotion/relegation are **distinct decisions**: accepting source club rows does not automatically make a league fully playable, certify a feeder or mark it as closed.

## Verification

[Passing GitHub Actions release, membership and canonical movement audit](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39585176348):
- **14 Python unit tests passed**.
- FC27 source-only membership acceptance: **33 codes, 280 clubs**, all included in a **53-code, 659-club** active catalog.
- No extra roster verification needed for these 33 **under the agreed game's membership scope**.
- Original and derived SQLite integrity, foreign keys, source edition preservation and historical career fail-closed assertions passed.
- The separate source evidence still records **33 codes with no independently dated fixture-member pool**, honestly reflecting data limitations rather than treating user-approved scope as sourced factual verification.

## Next work: 2026/27 promotion/relegation, one immediate feeder only

The separate report `FC27_SEVEN_CANONICAL_MOVEMENT_BOUNDARIES.csv` crosswalks seven source-backed edition-2027 pyramid boundaries to actual source competition codes:

| Lower division | Upper division | Treatment |
|---|---|---|
| Championship | Premier League | 2026/27 expanded 3rd–8th play-off; source-dated |
| League One | Championship | Direct + play-off movement |
| League Two | League One | Direct + play-off movement |
| National League | League Two | Existing **one-hop non-playable** source feeder pool retained |
| 2. Bundesliga | Bundesliga | German third-placed/16th-placed conditional interdivision tie |
| 3. Liga | 2. Bundesliga | German third-placed/16th-placed conditional interdivision tie |
| Segunda División | La Liga | Spanish direct + play-off promotions |

Six of seven edges also cross-check with the separately persisted versioned season movement rules. These code links are **verified staging**, not a gameplay implementation or a certificate that all eligible clubs and next-season movement outcomes are complete. National League North/South regional allocations remain distinct, one level below National League if that division eventually becomes playable.

The prior 53-code movement audit still counts 43 divisions with no linked season-end rules, nine with partial arrangements and one explicit closed/no promotion format. Those counts are **raw original broad-scope diagnostics**. They must be reprioritised against the set of actual **playable** leagues rather than forcing full feeder simulations for every club in a small, accepted source-only competition.

**Current readiness: still blocked.** Work next on the core playable 2026/27 promotion/relegation regimes and single feeder where needed. **Do not start FC26 or integrate career gameplay until the FC27 competition graph is adequately ready.**

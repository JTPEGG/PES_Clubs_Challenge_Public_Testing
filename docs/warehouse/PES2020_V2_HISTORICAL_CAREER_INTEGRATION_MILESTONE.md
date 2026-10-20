# PES V2 — Historical career dataset and preseason integration

Date: 20 October 2026. Men's football only. PC and PlayStation. Isolated development branch (never original production careers).

## Completed and validated milestone

The approved 22-edition player/wage/loan source and the two-layer club-finance model now have an actual **historical career world importer**: `world_historical_career_import.py`.

[Successful complete-world, all 29 PES numerical attributes and first 30-minute window validation](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39437011805).

| Edition | Historical game season | Clubs | Registered players | Contracts | Starting loans | Source unknown-club players omitted |
|---|---|---:|---:|---:|---:|---:|
| FIFA26 | 2025/26 | 662 | 18,316 | 18,316 | 1,325 | 89 |
| FC27 | 2026/27 | 670 | 17,849 | 17,849 | 0 | 0 |

Each registered player also carries all **25 PES2020 V2 core numerical ratings + four auxiliary ratings**, plus original source height, weight, preferred foot, alternative positions and positional familiarity in dedicated world tables. The successful build validates **531,164** attribute values for FIFA26 and **517,621** for FC27, with 1:1 metadata record coverage. Source unknown-club FIFA26 players are intentionally not assigned to invented clubs.

The imported worlds include source-club key -> internal world club ID and edition-row player key -> internal world player ID mappings. Identical club names in different seasons or competitions are not automatically treated as the same business identity. Each world uses source-named league labels (not claimed independent verification of each historic registration), source-registered squads, source or game-estimated weekly wages and contract expiries, separately owned incoming loans, approved PES-converted rating references and V2 starting transfer/wage budgets.

The 2026/27 historical leagues have no missing source competition labels in these selected archives; **many other editions do**, so the remaining 20 starting editions stay in the source catalogue but are not yet enabled to create full careers. We do not invent competitions to bypass missing historical data.

The imported datasets are **new, review-only, immutable snapshots**. Test careers are separately created; the importer never resets or touches production career IDs.

### Example sandbox validation

- Existing club wage commitments and 50/50 modelled historical parent/borrower loan responsibilities are loaded. Their provenance remains source vs game estimate.
- The manager's new career is explicitly created in the sandbox with correct starting registered players and all contract snapshots.
- The transfer window can be started with an immutable **30-minute real-time deadline**.
- All 1,325 sourced starting loans in FIFA26 begin active, with correct parent club ownership; player registration remains in borrower squads until season-end return.
- The market now uses starting `world_career_contract_snapshots` wage and expiry year for a historical player, rather than independently inventing a second wage number.
- New historical careers can start with negative wage headroom if existing contracts exceed modelled club capacity.
- FC25 stays excluded. The user-approved FC27 transfers (including Salah at Trabzonspor), accepted salary review outcomes, and existing source player records stay intact.

## Season and club selection UI

`world_historical_career_setup_ui.py` adds **GET-only** route `/world/historical-setup` in the isolated development app branch:
- 22 editions listed with a clear status, with missing league mapping honestly flagged.
- Imported 2026/27 worlds have club, league, squad, source-loan count, transfer-budget and weekly-wage-budget previews.
- The UI does NOT start or overwrite careers, register players into PES, initiate transfers, or bypass auth.
- No production deployment occurred; the actual live web link is not yet available until the approved test-world packages are provisioned in a test Render instance.

[Historical edition setup integration and read-only UI tests](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39435242547).

[Download FIFA26 test career database](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39437011805/artifacts/12272931320) · [Download FC27 test career database](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39437011805/artifacts/12273106404).

## Longer AI-market validation

The autonomous market pipeline `world_live_market.py` is now exercised in isolated historical saves, including source-wage use and a fully timed deadline. A separate deeper workflow `fifa-pes-v2-historical-autonomous-market.yml` is intended to evaluate all 12 simulated time moments; its actual results must be read from GitHub Actions before declaring offer volumes satisfactory.

## Important work remaining

1. Expand source-confirmed league membership mapping for the remaining 20 editions before making them career-launchable. No invented historic league membership.
2. Review AI buyer recruitment and offer *volume/quality* over full simulated windows: registration and timer smoke tests alone cannot prove realistic behaviour.
3. Develop an authorised **POST career creation** flow after permissions, duplicate-protection and selectable manager-club readiness have passed. The existing selector is deliberately non-mutating.
4. Ensure the user-visible autonomous inbox honours all historical source contracts/loan owner rules and financial restrictions; handle owner-aware permanent transfers of players already loaned out.
5. Deploy only to the isolated Render test site after explicit approval; original production stays untouched.
6. Later, build the PC/PlayStation native PES file import/export mapping and restore FC25 from an appropriate source, not from fabricated rows.

## Regression boundary

No new production career is created; user and AI career saves, historical source archives, original PES database, match results, player transfer locations, and all player wage figures are unchanged. All modelled budgets remain game rules, not proven financial accounts.

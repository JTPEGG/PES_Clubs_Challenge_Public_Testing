# FC27 autonomous recruitment realism — first QA baseline and elite net-balance candidate

**Date:** 21 October 2026. Development feature branch only. This is a *game AI simulation*, not a factual claim about real players/clubs/managers.

## Genuine autonomous benchmark: existing 92-club career engine

Two fully run (not mocked) [92-club autonomous 30-minute window tests](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39619826115) produced:

| Metric | Measured |
|---|---:|
| Windows | 2 |
| Total agreements completed / registered at deadline | 137 |
| Mean per window | 68.5 |
| Keeper share | 10.2% |
| Prospect share | 18.2% |
| Positional cover alerts | 0 |
| Starting-position quality alerts | 9 |
| Rotation quality alerts | 21 |
| Arsenal incoming / outgoing | 2 / 5 |
| Chelsea incoming / outgoing | 2 / 8 |
| Manchester City incoming / outgoing | 4 / 8 |

An intact *minimum* positional cover is not sufficient if strong clubs systematically lose first-team/rotation quality. In these two actual isolated windows each of the three inspected elite clubs was a net seller, reproducing the user's earlier concern.

**Important scope:** this 92-club market engine is NOT YET bound to the new 659-club 2027 warehouse source. We must not mislabel the tests as a 659-club autonomous season.

## Correction already applied and tested

`world_transfer_affordability.py` now correctly accepts signed/negative weekly wage headroom and returns **unaffordable**. It used to reject financially overstretched clubs with a parameter-validation error, despite the warehouse correctly preserving negative headroom. The new FC27 source audit confirms three negative-headroom game-model clubs.

`world_player_decisions.py` now describes refusal by a generic **top-flight** player rather than exclusively "Premier League"—the rule must work across user-selected eight European countries and MLS.

15 read-only hypothetical transfer scenarios, 66 automated tests and the 659-club source decision model audit passed [run 39619913093](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39619913093).

## Additional policy proposed for controlled calibration

`world_ai_elite_balance.py` contains a pure, deliberately **not yet plugged into the live bidding engine** candidate `assess_elite_net_departure()` with dedicated unit tests `test_world_ai_elite_balance.py`.

- Categorise a currently very strong first-team squad using **projected top-11 source overall >=82**, not club name.
- Normal case: at most **one more agreed departure than agreed incoming**. Subsequent signings re-open genuine departure headroom.
- Explicit strong exceptions—player wants exit, club cash need/distress or board-approved exceptional offer—allow at most **two net departures**, never unlimited routine stripping.
- Transfer listing alone is insufficient to bypass the cap. Record the reason for acceptance/refusal. The seller, player, agent and board must **still independently approve**.
- No provisional/imaginary replacement counts as an arrival: only **already agreed** transfers are used.
- The proposed rule is intentionally conservative; a rule affecting 659 background teams and long-term transfer volume requires calibration against the full existing 92-club simulation before activation.

**Awaited baseline benchmark:** The full existing isolated [20-window AI world market audit](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39621103349) evaluates 20 separate complete simulated 30-minute windows, with per-club quality/cover and buyer/seller evidence. Its result must be reviewed **before** switching the candidate to active AI buyer/seller selection.

## Manager database sequencing

The user's approved ordering is: **realism QA first, real present-day manager source database second**. Current warehouse's 659 anonymous fictional coaching agents are **not real managers**.

Future manager reference must include:
- Stable manager identity and provenance (official club/federation role and dates)
- Historical appointments/management career, with season-effective employment snapshots
- Tactical preferences, squad integration, player development and transfer philosophy tagged independently as **observed-source**, **model-derived inference**, or **gameplay assumption**, with nulls where unknown
- Career overlay: managerial moves, dismissals, ambition changes, coach decisions may change in game and must never mutate the real dated reference facts

No production club career, FC26 dataset or PES edit/export work is touched.

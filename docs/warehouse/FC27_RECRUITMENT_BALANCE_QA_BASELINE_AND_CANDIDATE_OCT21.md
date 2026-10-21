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

## Revised approved design: sell first, recruit later, no numerical departure caps

**The user rejected all arbitrary elite sale caps.** The proposed `world_ai_elite_balance.py` policy and its test have been deleted. Do not reinstate them.

The autonomous AI-world implementation now uses `world_ai_replacement_outlook.assess_future_replacement()` on the **projected squad** and possible same-specialist-position source-rated transfer-market options. This produces a **scouting outlook only**: no future sale is guaranteed, no incoming player is invented, and zero replacements are marked signed.

The decision flow is:
1. Examine player value and role, current contract, squad strength/rotation impact and recruitment options from other clubs.
2. Score strategic risk continuously as a **market priority**. Loss of key squad quality reduces appetite; a broad credible future candidate pool makes rebuilding more plausible.
3. Let buyer make an actual offer; let selling club **negotiate** against its sporting/contract/financial risk. For *fictional autonomous AI-only sellers*, `retain` is no longer an eternal veto: it attracts a larger asking price, which a compelling offer can meet.
4. Player/agent must accept personal terms, and the appropriate board retains separate oversight. Acceptance remains provisional until season-window finalisation.
5. A sold starter may leave a real **urgent recruiting need**. Other clubs can also sell before replacing, removing any recursive sign-first deadlock.

**No requirement to buy before selling, no blanket transfer quotas, no presumed signings.** Existing user-specified/manual seller retention decisions are preserved unchanged; this adjustment applies to AI-only source-labelled circumstances.

The true 20-window original-policy benchmark finished [run 39621103349](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39621103349):
1,422 completed transfers over 20 independent English 92-club windows (71.1 mean), goalkeeper share 10.7%; Arsenal 21 in/46 out, Chelsea 22/80, Man City 35/49. This establishes the need for more balanced sporting evaluation, not hard caps. One positional-cover alert, 77 starter-quality alerts, and 256 rotation-quality alerts were counted across the 20 simulated careers.

**Validation:** pure tests in `test_world_ai_replacement_outlook.py`, existing seller regressions, and real two-window engine smoke. This revised model is initially development-only. Do not claim that the full 659-club FC27 warehouse has already replaced the 92-club AI engine.

## Manager database sequencing

The user's approved ordering is: **realism QA first, real present-day manager source database second**. Current warehouse's 659 anonymous fictional coaching agents are **not real managers**.

Future manager reference must include:
- Stable manager identity and provenance (official club/federation role and dates)
- Historical appointments/management career, with season-effective employment snapshots
- Tactical preferences, squad integration, player development and transfer philosophy tagged independently as **observed-source**, **model-derived inference**, or **gameplay assumption**, with nulls where unknown
- Career overlay: managerial moves, dismissals, ambition changes, coach decisions may change in game and must never mutate the real dated reference facts

No production club career, FC26 dataset or PES edit/export work is touched.

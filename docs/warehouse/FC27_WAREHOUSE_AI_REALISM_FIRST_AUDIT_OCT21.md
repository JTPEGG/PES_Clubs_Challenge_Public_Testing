# FC27 warehouse realism audit — first transfer, agent, board and recruitment pass

**21 October 2026 | development branch only**

**Verified:** [66 automated tests and read-only warehouse audit passed, run 39619913093](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39619913093). The generated artifact **FC27-AI-WAREHOUSE-REALISM-AUDIT-V1** contains JSON with all **15 asserted scenario checks** and live FC27 source warehouse distributions. No production games or careers changed.

## What's been tested

The test harness `warehouse/fc27_ai_realism_audit.py` and `test_fc27_ai_realism.py` runs the **existing read-only** `world_transfer_negotiations`, `world_player_decisions`, `world_selling_club`, `world_transfer_board` and `world_transfer_affordability` functions. Every proposed offer, fee, squad role, European place and institutional prestige input is expressly a **hypothetical test fixture**, not a real player/club opinion.

- A prime elite Champions League key player refuses a severe sporting/prestige downgrade, even at high wages.
- An exceptional offer can trigger a selling-board directed sale but **cannot override the player's refusal**.
- An older listed/non-renewed reserve player can consider a lower-league club for guaranteed starts and realistic wage terms; an acceptable three-party deal is **provisional**, not registered.
- Protect a stable club's irreplaceable important first-team player with a longer contract.
- An expiring contract lowers the seller's asking fee but **does not manufacture player consent**.
- A buyer board may veto an overpriced transfer that is technically affordable.
- All **negative weekly wage headroom** inputs now return an **unaffordable** decision instead of an exception (actual implementation fix `world_transfer_affordability.py`).
- Explicit *proposed recruitment policy* would prevent goalkeeper stockpiling and substandard signings at an elite club, with an exception for confirmed outgoing/replacement needs. **This gate is QA-only, not yet integrated with autonomous recruitment**.
- Unknown actual institutional prestige results in `needs_information`, not fabricated 0–100 prestige from current squad strength.
- Tier-one transfer refusal messaging now says **top-flight** rather than assuming the club plays in England, important for the 8 European national pyramids + MLS.

## Reality check against actual warehouse rows

The read-only audit of [FC27 populated enriched reference](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39616187183) found:

| Measure | Actual |
|---|---:|
| FC27 original clubs reviewed | **659** |
| Players with explicitly fictional game behavioural priors | **17,593** |
| Sufficient source squad evidence for game sporting appeal | **651 clubs** |
| Limited source squad evidence | **8 clubs** |
| Game-model sporting appeal score observed range | **40–79** |
| Game-model ambition score observed range | **47–92** |
| Negative modelled weekly wage headroom | **3 clubs** |
| Clubs currently categorised `normal` by provisional finance model | **656 clubs** |
| Independently observed club institutional prestige | **0 clubs** |
| Simulated anonymous coaching agents | **659 clubs** |

**Financial caution:** `normal` means the simulation did not mark those other 656 clubs financially constrained; it is NOT an independent finding of real financial health. Documented financial events are sparse and must not be extrapolated into unverified cash balances.

## Important outstanding realism issues

1. **Transfer prestige decision gap.** Present transfer negotiation requires an explicit 0–100 historical/prestige value, but the new warehouse (correctly) has `institutional_prestige=NULL` for all 659 clubs. Before autonomous offers, define a separately versioned *game-only stature proxy* distinct from current squad quality and test it across countries, or source defensible institutional evidence. Never silently pass the game sporting score as factual prestige.
2. **Recruitment planning gap.** The existing engine can consider negotiating a bid without assessing whether a target actually upgrades the club's projected position group. The proposed `recruitment_fit()` safeguard exercises GK overstock and weak signings, but is NOT wired into the AI buyer's selection. Connect it to live projected squads and commitments before running a 20-window recruitment volume/quality test.
3. **Financial realism gap.** Three detected negative model wage headrooms are now correctly blocked. Others are not proven financially healthy; review small/large-budget, relegated, distressed and ownership-change assumptions rather than creating invented funding.
4. **Player character gap.** Personality priors are fictional stable player seeds and do not yet change the agent negotiation or renewal decisions; use them only as gameplay parameters after explicit calibration. Cannot claim any real individual's motivation.
5. **MLS and cross-league gap.** Relative domestic `tier=1` alone does not capture competitive differences between the closed MLS and European top flights. Provide international league strength and qualification status when source-backed or as explicitly versioned game assumptions.
6. **Real manager database:** confirmed as a future separate reference milestone. Map **actual manager identities, dated club appointments, work history and provenance**, then *derived or simulated* coaching behaviour with an independent origin marker, never invented factual personal traits. The existing 659 anonymous manager agents are only game substitutes, not real manager records.

## Next validation gates

The 66 tests and 15 checks are **deterministic transfer/board/agent scenario QA** with actual underlying club model distribution; they are NOT a stochastic **20 consecutive automatic transfer-window world simulation**. That second stage should use full recruitment squad composition, fees and committed moves and report elite-club net purchases, position coverage, high-potential young players, average deals per window, goalkeeper signings, and transfer affordability outcomes. Only then should we alter active development AI, and never production until reviewed.

All work remains on `JTPEGG/PES_Clubs_Challenge_Public_Testing` feature branch `feat/fifa-pes-converter-v2-complete`. PES native export remains deferred.

# FC27 warehouse milestone 2 — AI club / player / manager reference dimensions

**21 October 2026. Development reference only.** Repo `JTPEGG/PES_Clubs_Challenge_Public_Testing`, branch `feat/fifa-pes-converter-v2-complete`. Production, PostgreSQL, existing career history and PES export unaffected.

## Objective and rules

The user approved completing missing reference dimensions before career integration: **club reputation, club ambition, dated financial circumstances, player personality, manager profiles**. Preserve previous source data and explicitly distinguish **real observed facts**, **source-derived game estimates**, **fictional game prior seeds**, and **unknown**.

This milestone adds five normalized, model-versioned domains to the populated FC27 reference database. Existing dataset integrity and source identities remain unchanged. The game must never claim these numbers are actual living people's personality, actual managers, independently verified institutional prestige, real owner investment or club audited cash.

## Tested implementation

- `warehouse/fc27_decision_dimensions_v1.sql`: additive tables `wh_fc27_club_decision_profile`, `wh_fc27_club_financial_circumstances`, `wh_fc27_financial_evidence_events`, `wh_fc27_player_game_personality`, `wh_fc27_manager_profiles` (verified source-only), `wh_fc27_manager_recruitment_policy`, `wh_fc27_simulated_manager_agents`, and `wh_fc27_decision_model_versions`. Read view `wh_fc27_ai_club_decision_context`.
- `warehouse/fc27_enrich_decision_dimensions.py`: produces an **independent copied enriched FC27 SQLite file** from the successfully built reference + read-only dated finance circumstances release; refuses to overwrite source/output.
- `warehouse/fc27_reference_reader.py`: `get_club_ai_context()`, `get_player_ai_context()`, `get_club_financial_events()`, and `decision_dimension_coverage()`. No career writes.
- `warehouse/fc27_ai_decision_review_exports.py`: five review CSVs with **GAME**, **SOURCE** and **UNKNOWN** markers plus a reconciliation report.
- `test_fc27_decision_dimensions.py`: fixed-seed determinism, world rank/money model behaviour, no invented financial balance or real manager/personality, in-memory integration.
- `.github/workflows/fc27-populated-warehouse.yml`: now builds the original reference first, downloads the already-approved historical financial-circumstances archive from [run 39429984572](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39429984572), enriches only a **new output**, verifies counts/constraints/read APIs and uploads both reference and enriched source/audits.

## 2026/27 coverage

| Reference dimension | Records | Evidence/policy distinction |
|---|---:|---|
| Club sporting appeal and ambition | **659** | Top-sixteen players' *source overall* in each original club; within-division rank and 0–100 gameplay proxies; historical institutional prestige **NULL** |
| Club financial health | **659** | Separate officially dated events from **modelled** wage ceiling/transfer allowance; known payroll matched exactly to existing finance baseline; actual cash/debt/revenue/owner injection **NULL** |
| FC27 preseason evidence events | **6 active** | Only independently sourced dated events for this specific edition and pre-season. They are **not** proof of precisely how much money a club received/spent |
| Player behavioural priors | **17,593** | Deterministic game-seeded ambition, loyalty, professionalism, temperament, adaptability, financial motivation, 35–65; all observed real-person traits **NULL** |
| Club manager hiring policies | **659** | Modelled minimum manager reputation, tactical style preference, financial caution and rebuilding tolerance; board model, not real stated hiring requirements |
| Simulated anonymous coaching agents | **659** | One anonymous stable **fictional** career-start agent per original club, with game-only coaching ability, youth-development, flexibility, recruitment risk and financial discipline |
| Verified real manager identity/appointment records | **0** | Still requires source ID, source URL and effective date; no fictional *named real-world* coaches or 2026/27 employment claims |

**No personally attributed fictional behaviour is represented as fact.** Player priors are varied by a stable seed derived from the original identity key, independent of nationality, race, religion, gender, inferred psychological disposition, or a manager/club's historical public image. Later experience and career events can update a career's *simulated state* without modifying the reference's real-world data.

### Reputation vs ambition

- **Sporting appeal** is a current *squad strength/league context game proxy*, not a substitute for long-term club prestige. Source edition overall from up to 16 best rated squad players is used where at least eight valid ratings exist.
- The shared 0–100 sporting score uses `clamp(42 + 1.4 × (top16 average - 60),15,95)` when valid; with missing data uses a **low-confidence league-tier game fallback**. Confidence flags are preserved.
- **Competitive expectation** is derived from relative ranked source squad standard in the particular division (upper-end, middle, lower-end), NOT a prediction of the real final table.
- **Board ambition** is a reproducible game aspiration proxy depending on sporting score, relative division strength and financial pressure. Real ownership ambitions/targets remain unverified.

### Financial constraints

The previously validated `historical-club-financial-circumstances-v2` archive (13,104 club-edition entries) is joined on **exact source `club_key`**, with no fuzzy joining or guesses. Six dated real events effective for this FC27 preseason are recorded with their original source URLs, category, date and verbatim audited-event facts.

- Distress applies a model financial pressure and can prohibit speculative new expenditure.
- The **signed wage headroom is allowed negative** where committed obligations exceed a model affordability ceiling. No `max(0,...)` papering over.
- Modelled owner takeover events **never create free cash**. Official event evidence has no verified amount in this archive; revenue, cash balance, net debt and ownership injection remain genuinely **NULL**.
- The results are a **simulation of affordable budgets**, not club companies' bank balances or annual accounts.
- Currency is GBP with separate weekly wage and total transfer allowances; game policies must respect this distinction.

### Manager reference honesty and realistic career effects

- Each club has a simulated **manager hiring policy** appropriate to its competition strength, ambition and financial position.
- Each starting club also has a portable, anonymous **fictional AI manager agent** with stable game-only abilities/behaviour. This allows transfer-simulation agents to have differentiated styles without us fabricating statements about the manager who held the real club job in 2026.
- Actual manager names, CVs, qualifications and historical appointments remain empty pending **licensed/public source data with matching source IDs and effective dates**. Never treat the anonymous template as a claim of a real incumbent.
- **The existing AI/career engine is not yet bound to this new warehouse.** These profiles will not affect any currently deployed AI behaviour until an explicit validated integration step.

## Known realism limitations and next gate

1. The current reputation measures player ability, not true institutional stature/history, and the model uses modest same-competition ranking adjustments. No sourced Europe qualification, title count, fan size or academy/stadium prestige is yet incorporated.
2. Current player personality priors are deliberately fictional and independent of real people's inferred dispositions. They provide game variation, not scientifically valid personality prediction.
3. Documented manager employment and preferred tactics remain unpopulated; anonymous templates are simulations rather than verified real biographies.
4. Source finance status is more rigorous than payroll-only, but only a small number of 2026/27 club events are dated; missing events are **unknown, not proof of financial health**.
5. Career time must update reputation/ambition/manager mobility/financial pressure via **career events and standings**, not overwrite the frozen reference snapshot.

**Next priority:** validate realistic AI outcomes against a deliberately mixed club/player scenario matrix (elite selling/buying, overcommitted wages, promoted/relegated and distressed clubs, loyal key-player departures, contractual expiry, backup GK), then bind the warehouse read APIs to development career creation and transfer logic. Leave PES export and production untouched.

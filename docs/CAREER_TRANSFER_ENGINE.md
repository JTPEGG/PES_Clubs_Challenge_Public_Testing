# Career transfer engine — development milestone

## What changed
`world_careers.py` introduces persistent **career-specific**, not source-dataset-specific, negotiations and ledgers.
- `start_sandbox`: forks roster membership and an economy-version budget into a new career ID.
- `propose_offer`: idempotent offer, deterministic selling-club response, budget reservation and event history.
- `accept_counter`: records a buyer accepting an affordable counteroffer, pending contract terms.
- `settle_future_deal`: records a wage offer and **future** effective date. It does **not** transfer a player on the PES-locked roster.
- `withdraw_offer`: cancels and releases reserved budget.
- `ai_interest`: advisory affordable AI-club shortlist only. It does **not** fabricate actual AI bids.
- `world_careers_ui.py`: read-only audit page at `/world/careers`.

## Recalibrating the economy later
All numbers are assumptions. Career rows retain `economy_version` and the initial budgets copied into their own ledgers, so changing the economy for a **new** career does not silently change previous negotiated transactions. `ECONOMIES` contains `prototype-v1` and can accept later calibrated versions. Archived history remains intact.

The older value reference is `world_valuation.MODEL_VERSION` and source EA overall rating is stored separately. A negotiation stores the ability reference and economy version used at the time. **Fees are not presented as actual football-world transfer values.**

## Summer-only registration
A successful contract stage records `agreed_future` and next summer's date. Career roster registrations remain exactly where they were; there is deliberately no implemented endpoint to complete moves midseason. The summer registration/reconciliation pipeline is a future stage.

## Explicit limitations
- These are engine functions and read-only views, **not** interactive authenticated in-game transfer actions.
- Before enabling write-capable web controls, implement career ownership and authorization, identity reconciliation and atomic idempotency.
- AI interest currently finds clubs with sufficient unreserved funds; it does not make autonomous bids or form strategies yet.
- Future agreement is not contract completion: medicals, player consent, competing terms and transfer completion remain unimplemented.
- The offer ledger does not currently process transfer installments, incoming sell-on income, amortization, compensation or wage taxation.
- This **never** modifies the original production project.

## Tests
`python -m unittest -v test_world_careers`

Tests cover the source dataset being untouched, idempotency keys, reservation release, blocking duplicate open bids, delayed PES registration and advisory AI interest.

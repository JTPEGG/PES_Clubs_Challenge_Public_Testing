# Starting contracts, salaries and historical loans — V2 implementation plan

Date: 20 October 2026
Scope: Men-only PC / PlayStation career datasets; 22 starting editions (FC25 is excluded).
Status: Plan and verified source audit. Not yet an active career integration.

## Verified data source audit

Source: https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39412411641
Download CSV/JSON evidence: https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39412411641/artifacts/12259418459

The source audit checked the **unchanged 319,389-row FIFA source archive**. The
future career importer must use the already signed-off **317,449-record men's-only
catalogue**, not restore excluded records.

| Editions | Wage evidence | Contract-end evidence | Named source loan parents |
|---|---|---|---:|
| FIFA05 | Blank | Blank | 0 |
| FIFA06–11 | Blank | ~97–99% of rows, contract_length is an END YEAR | 0 |
| FIFA12–14 | 97.5–98.0% numeric wages | 97.5–100% populated END YEAR | 971 |
| FIFA15 | wage_eur populated as 0, unusable | 98.45% | 912 |
| FIFA16–21 | 100% wage_eur values | ~98.7–98.9% end year | 6,551 |
| FIFA22 | 99.68% wage_eur | 99.68% | 1,102 |
| FIFA23 | 100% WageEUR | 99.50% ContractUntil | 0 |
| FC24 | 100% wage (e.g. 340K; units need checking) | 99.97% | 0 |
| FC26 | 100% wage_eur | 99.52% | 1,325 |
| FC27 | Missing | Missing | 0 |

Total source rows naming a loan parent club: **10,861**. Those aren't confirmed
linked parent-club IDs or current valid loans for a specific registration date.
No reliable loan end date columns were found in the selected archives.

## Data model

Keep immutable reference data separately from mutable career state.

**Player reference contract:**
- Player key: edition + source-row ordinal, never bare FIFA source ID.
- Raw wage amount, source name, source currency, source unit/period, source date.
- Normalized weekly GBP for **simulation use**, with FX/assumption version, not
  falsely labelled as actual real salary.
- Original contract end value, year-only precision and separately generated
  simulation effective expiry date, quality/confidence.
- Player status and source provenance: direct_source, source_questionable,
  inferred_game, unresolved.

**Initial source loan:**
- Player and borrowing club's edition-scoped identity.
- Original parent name/ID as recorded; linked parent club ID if unambiguous.
- Loan status, original loan date/end if available, game-simulated return date,
  assumption/provenance and wage-share source.
- Unresolved parents remain unresolved; no joining on ambiguous same-name clubs.

**Career state:**
- Existing world_career_contract_snapshots and world_career_loan_agreements
  receive these starting records when a NEW immutable career starts.
- Parent retains ownership and underlying contract; borrower has playing
  registration, only until the loan ends.
- Wage commitments include currently contracted players and the loan wage share.
- Finances, contracts, positions and ownership change only through recorded
  career transactions and verified season events.

## Development sequence

1. Build provider-specific source adapters and clean numeric units. Reject blank,
   implausible token wages (e.g. 1) and FIFA15 all-zero salaries as actual salaries.
   Map contract_length (FIFA06–14) as an end YEAR, not contract duration.
   Interpret year-only expiry using the competition's model season end; keep
   original year and an explicit assumption flag.
2. Generate deterministic **historically scaled** estimated weekly wages and
   contract terms when absent. Use age, position, overall, squad standing,
   league/club prestige and bounded payroll. Validate against historical source
   distributions in nearby years; modern wage values must not be copied
   unscaled into FIFA05. Mark every estimate visibly in the data.
3. Resolve parent club references within the SAME historical edition. Keep
   source club and parent separate; identify ambiguous and absent parent clubs.
   Initial source loans are seeded active with the selected borrower squad
   intact. Unless evidence specifies otherwise, assume return at END OF THE
   INITIAL SIMULATED SEASON; this is a game rule, not a historical fact.
4. Seed the immutable starting contracts and loans into a NEW sandbox career.
   Compute club wage bills and available budgets; feed this automatically into
   the AI manager/inbox/contract decision modules without manual inputs.
5. Reconcile at VERIFIED PES season completion only. Return still-contracted
   players to parent club, release borrower wage commitments, refresh squads
   and board/AI planning. If a parent contract has also expired without renewal,
   resolve contractual release/free agency instead of phantom parent ownership.
   Events must be transactional and idempotent across repeated checks.
6. Stress-test FIFA05/15/27 estimates, FIFA12/20/26 loans, ambiguous parent
   references, loans to clubs outside playable divisions, renewals, club
   affordability, expiring contracts and no-doubled-registration guarantees.

## Frozen gameplay rules

- A loaned player plays for the borrower but is contractually owned by the parent.
- A buying club negotiates permanent transfers with the parent, not the borrower.
- Starting loans are already active; they don't need a new 30-minute-window offer.
- New loans follow agreed player/lender/borrower/board consent and wage terms.
- Only verified career season completion can cause source-loan return.
- Unknown historic salaries are NOT zero; create tagged game estimates.
- No source is silently overwritten, and no existing career or production service
  is changed. PC and PlayStation import compatibility remains a later stage.

## Acceptance criteria

Every one of the 317,449 men-only annual records gets a usable starting
wage/contract simulation state with source-versus-estimate provenance; every
source-identified loan is either linked to a defensible parent or flagged
unresolved; squad and source row counts reconcile; no club inherits fictional
history as documented fact. At least one full historical career fixture runs
through transfers and season-end loans without manual wage entry or duplicated
player registration.

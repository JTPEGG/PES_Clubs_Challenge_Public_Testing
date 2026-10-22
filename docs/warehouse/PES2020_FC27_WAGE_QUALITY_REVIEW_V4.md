# FC27 wage quality review — v4 starting database

**Scope:** Men's-only FC27 wage estimates. This is a simulation starting database, not evidence of actual player contracts, and it has not been deployed to production.

## Verified build and complete review

- [Full GitHub validation: SUCCESS](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39423495384)
- [Final enriched 22-edition SQLite artifact](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39423495384/artifacts/12264772712)
- Model: `historical-wage-and-loan-v4-fc27-quality-reviewed`.

The updated model preserves 317,449 men's annual player rows and the complete 10,861 existing source loan agreements. All 21 non-FC27 editions have **zero wage changes**, and all 10,861 source loan parent/maturity records are unchanged. SQLite integrity check and foreign-key check passed.

## Matching and adjustments

- Numeric source ID **plus exact DOB plus accepted normalized nationality** must agree. Explicit synonymous labels such as Holland / Netherlands, Türkiye / Turkey, Czech Republic / Czechia, Cabo Verde / Cape Verde and St. Lucia / Saint Lucia are accepted. A genuine nationality switch is NOT silently equated.
- **125 conservative FC26↔FC27 club-label equivalences** were inferred when >=8 source-matched players constitute >=65% of both source club rosters. These are high-confidence *source-label* matches, not verified official team IDs.
- Same-club player: continue credible FC26 source salary with **7.5% assumed simulation uplift**.
- Changed club: use previous source wage and new club's modelled wage context, but normally avoid >25% nominal pay collapse solely from a low model club baseline; age 35+ at the **actual FC27 season start (August 2026)** can use a 30% reduction. This is an assumption, not a documented new contract.
- Unknown prior identity: preserve the original rating-and-club model. Do not guess source identities from player name alone.

## Full-run counts

- FC27 annual players: **17,849**.
- **7,544** same-club wage carryovers; **4,958** genuine or unresolved club changes using the wage blend; **5,347** unmatched model estimates.
- **3,906 FC27 player wages changed** relative to the last released FC27 v2 review. None of the other 21 editions' monetary outputs changed.
- Priority audit: **69 high-priority player wage review cases** and **2,470 secondary flags** (these are review flags, not necessarily wrong figures). More than one flag may apply to a record.
- Club-budget review: **30 FC27 players** earn >=25% of their own club's *modelled* payroll; this does NOT establish that the historical wage is incorrect, since the club payroll is also an estimate.
- **39 high-rated actual club changes** still show >20% decreases versus FC26. Review these rather than enforcing fabricated club affordability.
- The review includes **604 alternate nationality labels** in source-linked records and **1,937 strongly inferred club-name changes**, which remain visible via provenance.
- Only **one player rated 84+** remains unanchored despite the review, with an uncertain prior-season identity.

## Player examples (estimated GBP per week)

| Player | FC26 game-source reference | Previous FC27 | Reviewed FC27 |
|---|---:|---:|---:|
| Mbappé, Real Madrid | £518,500 | £557,400 | **£557,400** |
| Haaland, Manchester City | £221,000 | £237,600 | **£237,600** |
| Van Dijk, Liverpool | £195,500 | £63,900 | **£210,150** |
| Frenkie de Jong, Barcelona | £144,500 | £71,500 | **£155,350** |
| Kenan Yıldız, Juventus | £68,000 | £38,650 | **£73,100** |
| Mohamed Salah, Trabzonspor (as represented by FC27 source) | £314,500 | £102,750 | **£235,900** |
| Robert Lewandowski, Chicago Fire (as represented by FC27 source) | £131,750 | £53,900 | **£92,200** |

The hypothetical FC27 squad source, not an independent real-world transfer audit, places Salah at Trabzonspor and Lewandowski at Chicago Fire. Their modelled wages represent potential game circumstances, **not known real signed contracts**.

## Remaining questions before career rollout

- The **club payroll/transfer-budget model is estimated from player wages**, so it is *not independent financial evidence* of affordability. Review concentration at clubs including Chicago Fire, Orlando City and Trabzonspor; adjust budgets or wage assumptions coherently if user feedback requires it.
- Review 69 high-priority records and any actual club changes that have unusual wage reductions. Don't automatically override prior source wages without evidence.
- The global historical age approximation has known season-year imprecision; FC27's veteran transfer wage-floor logic now specifically uses age at August 2026.
- These are still game-source-based financial guesses where no FC27 source salary exists. Source-verified contracts for FC27 are still absent.
- Career setup world-season mapping is separate; no existing careers were updated.

The per-player review CSV and club-label-alias CSV were generated separately for user inspection, and the v4 SQLite remains the source of truth.

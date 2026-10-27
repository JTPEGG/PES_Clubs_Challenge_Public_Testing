# FC27 — complete game-scope movement-policy catalogue

Date: **21 October 2026**. Development repository `JTPEGG/PES_Clubs_Challenge_Public_Testing`, branch `feat/fifa-pes-converter-v2-complete`.

## Authorised simplifying principle

The user explicitly authorised sensible **gameplay assumptions**, prioritising development of a functioning simulation over exact execution of obscure national rules, provided **every judgement call is disclosed**. These rules therefore do **not** claim to reproduce all historical official 2026/27 regulations. They are edition-scoped game decisions stored outside immutable original FC club and regulatory sources.

The file `data/warehouse/fc27_remaining_34_gameplay_movement_policy.json` provides the machine-readable version of **all 34** decisions with one precise justification each; it is the authoritative decision log for this tranche. Selected official contextual links, where available, are also included, but are not falsely represented as full verification of the game model.

## All 34 new gameplay assumptions

Promoted teams always originate **from the named immediately lower national competition** (one level only). "Direct" in the table is the *game* behaviour; for one-off continental-licensing or complicated play-out competitions this might depart intentionally from the real world.

| # | Country | Existing FC27 competition | Promoted (game) | Relegated (game) | Named direct feeder | Explicit game decision |
|---:|---|---|---|---:|---|---|
| 1 | United Arab Emirates | UAE Pro League | 2 direct | 2 | UAE First Division League | Basic 2-up/2-down; ignore administrative league licensing. |
| 2 | Argentina | Argentine Primera División | 2 direct | 2 | Primera Nacional | Use bottom two for relegation instead of rolling points averages or complex national playoffs. |
| 3 | Australia / New Zealand | A-League Men | None | 0 | — | Treat A-League Men as closed at this stage; no promotion/relegation. |
| 4 | Azerbaijan | Azerbaijan Premier League | 1 direct | 1 | Azerbaijan First Division | One-up/one-down; ignore club eligibility exceptions. |
| 5 | Bulgaria | Bulgarian First League | 2 direct | 2 | Second Professional Football League | Two direct exchanges; ignore split and play-out details. |
| 6 | Bolivia | Bolivian División Profesional | 2 direct | 2 | Copa Simón Bolívar | Two direct exchanges; no relegation averages or regional playoff modelling. |
| 7 | Brazil | Brazilian Série A | 4 direct | 4 | Campeonato Brasileiro Série B | Straight bottom four relegated; top four from Série B promoted. |
| 8 | Chile | Chilean Primera División | 2 direct | 2 | Primera B | Two direct exchanges; omit secondary promotion bracket. |
| 9 | China | Chinese Super League | 2 direct | 2 | China League One | Two direct exchanges; ignore financial/licensing disqualifications. |
| 10 | Colombia | Colombian Primera A | 2 direct | 2 | Categoría Primera B | Two direct exchanges; omit average-points relegation and calendar tournaments. |
| 11 | Cyprus | Cypriot First Division | 2 direct | 2 | Cypriot Second Division | Two direct exchanges; no split-stage results needed. |
| 12 | Czech Republic | Czech First League | 2 direct | 2 | Czech National Football League | Two direct exchanges instead of multi-team promotion/relegation playoffs. |
| 13 | Denmark | Danish Superliga | 2 direct | 2 | Danish 1st Division | Two direct exchanges; no licensing exceptions or second-tier split simulation. |
| 14 | Ecuador | Ecuador LigaPro Serie A | 2 direct | 2 | Ecuadorian Serie B | Two direct exchanges; omit relegation play-out complexities. |
| 15 | Finland | Finnish Veikkausliiga | 1 direct | 1 | Ykkösliiga | One direct exchange; omit lower-tier play-off. |
| 16 | Greece | Greek Super League | 2 direct | 2 | Super League Greece 2 | Two direct exchanges using real Super League 2 as one-hop feeder; no fabricated other Greek top-flight clubs. |
| 17 | Croatia | Croatian Football League | 1 direct | 1 | Prva NL | One direct exchange; ignore licensing exceptions. |
| 18 | Hungary | Hungarian NB I | 2 direct | 2 | Nemzeti Bajnokság II | Two direct exchanges with NB II. |
| 19 | Ireland | League of Ireland Premier Division | 1 direct | 1 | League of Ireland First Division | One direct exchange; omit Premier Division 9th v first-division challenger playoff. |
| 20 | Italy | Italian Serie B | 4 direct | 4 | Serie C | Four direct exchanges Serie B/Serie C; simplify Serie B playout and regional Serie C playoffs. Serie B-to-Serie A 3rd-8th playoffs remain mandatory under separately approved decision. |
| 21 | South Korea | K League 1 | 3 direct | 1 | K League 2 | 2026 K League 1 12-club source expands to 14 in 2027: three promoted and one relegated in-game. Ignore Gimcheon Sangmu military-club/conditional fourth-promotion exception; the annual league size changes by +2. |
| 22 | Mexico | Liga MX | None | 0 | — | Use published no-ascenso/no-descenso 2026/27 Liga MX regime. |
| 23 | Norway | Eliteserien | 2 direct | 2 | OBOS-ligaen | Two direct exchanges; omit Eliteserien 14th-place conditional playoff. |
| 24 | Peru | Peruvian Liga 1 | 2 direct | 2 | Liga 2 | Two direct exchanges; omit changing league phase/playoff rules. |
| 25 | Poland | Ekstraklasa | 2 direct + 1 playoff | 3 | I liga | Two automatic promotions plus a 3rd-6th-place I liga playoff winner; bottom three Ekstraklasa clubs relegated. Assume every I liga season has qualifying clubs. |
| 26 | Paraguay | Paraguayan Primera División | 2 direct | 2 | División Intermedia | Bottom two instead of three-year average points; top two from División Intermedia. |
| 27 | Romania | Romanian SuperLiga | 2 direct | 2 | Liga II | Two direct exchanges; ignore 13th/14th top-flight play-out interdivision playoff qualifiers. |
| 28 | Saudi Arabia | Saudi Pro League | 2 direct + 1 playoff | 3 | Saudi First Division League | Two automatically up, one via 3rd-6th promotion playoff; bottom three down; no club licensing simulation. |
| 29 | Sweden | Allsvenskan | 2 direct | 2 | Superettan | Two direct exchanges; omit Allsvenskan 14th v lower-league playoff. The actual 2026 season has this additional qualification. |
| 30 | Thailand | Thai League 1 | 2 direct + 1 playoff | 3 | Thai League 2 | Two automatic promotions plus one lower-division playoff promotion; bottom three demoted. |
| 31 | Turkey | Süper Lig | 2 direct + 1 playoff | 3 | TFF 1. Lig | Two automatic promotions plus a TFF 1. Lig 3rd-7th playoff winner; bottom three Süper Lig teams relegated. Ignore administrative withdrawals. |
| 32 | Ukraine | Ukrainian Premier League | 2 direct | 2 | Ukrainian First League | Two direct exchanges; ignore additional UPL/First League relegation play-offs. |
| 33 | Uruguay | Uruguayan Primera División | 3 direct | 3 | Segunda División Profesional | Three direct exchanges; omit relegation averages and lower-stage playoff details. |
| 34 | Venezuela | Venezuelan Primera División | 2 direct | 2 | Segunda División | Two direct exchanges; omit second-tier regional qualification complexities. |

### Important special treatment

- **K League 1 2026 → K League 1 2027:** the 12-team competition expands to 14. The simulated game rule **promotes 3 and relegates 1, net +2**. Korea's real-world special military-club exemption and contingent further play-off are explicitly not implemented. This is **an intentional size change**, so a blanket up/down balance rule must not incorrectly reject it.
- **Mexico 2026/27:** no sporting promotion/relegation; see the published suspension reported in July 2026: https://www.nmas.com.mx/deportes/liga-mx-elimina-ascenso-y-descensotemporada-2026-2027-que-significa-cambio-de-reglas/
- **A-League Men 2026/27:** intentionally closed for this edition's game; the expanding Australian national pyramid is **not** automatically linked to A-League Men.
- **Italy:** the **previous user-approved Serie B → Serie A play-off always runs for clubs 3rd–8th**, giving exactly three Serie A promotions and three relegations. This batch separately maps **Serie C → Serie B** as a **simplified four-club exchange**, rather than modeling Serie C's multiple regional groups and Serie B playout.
- **Greek Super League:** **all four existing FC27 source club records remain**, with the real Super League 2 named as a potential one-hop feeder. Neither additional Greek top-flight squads nor fake clubs are created.
- **Poland and Turkey:** lower-league 3rd-position promotions come through in-game playoff winners, preserving an accessible football drama. Their specific bracket qualifications are intentionally simplified.
- **Romania:** instead of pairing the first division play-out positions with Liga II challengers, use two direct exchanges. The 2026/27 Romanian federation real second-tier pathway has two guaranteed promotions plus two conditional interdivision matches; the game simplification discards those conditional ties: https://www.frf.ro/competitii/procedura-de-programare-a-jocurilor-din-campionatul-liga-2-casa-pariurilor-sezon-2026-2027/
- **Scandinavia:** Sweden and Norway do not use interdivision survival play-offs in this simplified game, only two exchanges. For source context, Swedish federation published the real autumn-2026 qualification pathway: https://www.svenskfotboll.se/serier-cuper/kvalspel/kval

## Total FC27 coverage

| Scope | Active competition-code coverage |
|---|---:|
| Previous England, Germany and Spain mapped source pyramid nodes (some sharing boundaries) | 9 |
| Prior additional national movement regimes | 9 |
| Previously expressly closed MLS | 1 |
| **New delegated game policies, including two closed leagues** | **34** |
| **Total active FC27 domestic competition codes with a movement policy** | **53 / 53** |

The 7 original source movement **boundaries** and 9 added source boundaries are different units from "competition-code coverage." Distinguish boundary edges from active competition codes; do not add 7+9+34 to claim that all career-country pyramids are complete.

**32 named immediate lower-division feeder records** were added as source-identity-based competition *names only*, with `original_game_club_pool_verified=0`. Those records are **not fictitious clubs, imported squads or fully registered league participants**. They require real club identities if careers actually exchange teams with the feeders.

## Tests and safeguards

GitHub Actions [verified successful CI run 39588956083](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39588956083):
- **25 Python unit tests** passed.
- Active original FC27 club count remains **659**, all 53 starting competition codes preserved. Indian Super League remains absent from derived active records.
- New staged `fc27_remaining_34_gameplay_movement` = **34**, and `fc27_game_only_named_immediate_feeders` = **32** with unverified original-club squad pools.
- All new rules explicitly reconcile `direct_promotions + playoff_promotions - direct_relegations = division_size_delta`; nonzero delta is allowed **only** for the 2027 South Korean expansion.
- Current audit `competitions_with_no_linked_season_end_movement_rule = 0`; this means a **policy exists**, not that movements can already run without missing feeder clubs.
- No existing career was modified or activated, and earlier source evidence remains separate. `career_ready=false`, `FC26_allowed_to_start=false`.

## What's still actually required

1. **Playable/non-playable scope**: mark which divisions can be controlled in the app. Lightly imported leagues with one to five clubs cannot be asserted as complete playable leagues.
2. **Eligible real club feeders**: for playable bottom divisions with open promotion/relegation, register *real* clubs from the immediately adjacent lower division. Treat a missing lower club pool as a simulation blocker, **never a licence to fabricate clubs**.
3. **Season-end logic**: implement ranking, direct promotion, playoff winner selection, tie rules and the **+2 Korean season expansion** in the career engine after feeder provenance is satisfactory.
4. **Additional rule exceptions**: apply the user-approved Italy/ Austria override and every delegated game assumption from this log consistently across future season simulations, without rewriting original historical sources.
5. **FC26 historical backfill**: only begin when FC27's world competition structure and first season world-change simulation reach the agreed quality gate.


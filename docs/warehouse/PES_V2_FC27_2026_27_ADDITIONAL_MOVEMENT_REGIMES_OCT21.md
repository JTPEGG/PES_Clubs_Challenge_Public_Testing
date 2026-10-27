# FC27 2026/27 — Additional domestic movement regime mapping (21 October 2026)

Work is isolated to the development repository `JTPEGG/PES_Clubs_Challenge_Public_Testing`, branch `feat/fifa-pes-converter-v2-complete`. No production application, original game clubs, existing careers, historical source archive, or FC26 is modified.

**Verified green CI:** [GitHub Actions run 39586569619](https://github.com/JTPEGG/PES_Clubs_Challenge_Public_Testing/actions/runs/39586569619) — **18 Python tests passed**, reconstructed FC27 SQLite passes integrity/foreign-key tests.

## New 2026/27 movement boundary entries

The nine new source-regime records are committed in `data/warehouse/fc27_2026_27_additional_movement_regimes.json` and incorporated in the generated SQLite table `fc27_additional_movement_boundaries`. The named, unpopulated lower feeder competitions are kept separately in `fc27_extra_movement_feeder_nodes`.

| Country | 2027 lower → upper code | Direct up | Direct down | Conditional up/down place | Critical qualification |
|---|---|---:|---:|---:|---|
| France | `fr.2 → fr.1` | 2 | 2 | 1 | Ligue 2 4th–5th → 3rd → Ligue 1 16th, two-leg final |
| France | `fr.3 → fr.2` | 2 | 2 | 1 | **New 2026/27 professional Ligue 3** 3rd–6th play-off winner v Ligue 2 16th |
| Belgium | `be.2 → be.1` | 1 | 2 | 1 | 15-club 2026/27 Challenger Pro League: 2nd–5th play-off awards second promotion; **not** a tie against Jupiler bottom club. U23 quota-protection removed |
| Scotland | `sco.2 → sco.1` | 1 | 1 | 1 | Championship 2nd–4th play-off path v Premiership 11th; Premiership 12th down |
| Netherlands | `nl.2 → nl.1` | 2 | 2 | 1 | Eredivisie 16th conditional play-off v qualifying Eerste Divisie clubs; youth-team and period-winner eligibility/bracket details still require review |
| Portugal | `pt.2 → pt.1` | 2 | 2 | 1 | Primeira Liga 16th plays second-tier 3rd over two legs |
| Switzerland | `ch.2 → ch.1` | 1 | 1 | 1 | Super League 11th v Challenge League 2nd; 12th down; top flight has 33-game stage plus 5-game split |
| Italy | `it.2 → it.1` | 2 | 3 | 1 | Serie B third place ordinarily assigned via 3rd–8th play-offs, with a points-gap direct-promotion exception needing official 2026/27 regulation validation |
| Austria | `at.2 → at.1` | conditional 1 | conditional 1 | alternative 1 | Licensed 2. Liga champion promotes directly; if champion unlicensed, an eligible 2nd–4th team can challenge top-flight 12th; if none qualifies no exchange. **Not two simultaneous relegations** |

In the JSON, Austria's baseline direct promotion/relegation counts are 1 each and its conditional slot is 1. The explicit mutually-exclusive licence decision takes precedence over arithmetic: it does *not* imply two top-flight clubs automatically relegated. None of these routes automatically executes a promotion in the app.

### Source URLs, season-specific and primary where available

- France LFP 2026/27 Ligue 2 play-off timetable: https://www.lfp.fr/article/ligue-2-bkt-le-calendrier-de-la-saison-2026-2027
- French FFF new professional Ligue 3 and 3rd–6th bracket: https://www.fff.fr/article/16778-la-fff-officialise-la-ligue-3-professionnelle.html
- Belgian Pro League official 2026/27 Challenger 15-club format and play-offs: https://www.proleague.be/nieuws/kalender-2026-2027-nieuwkomers-treffen-elkaar-meteen-in-challenger-pro-league
- SPFL official 2026/27 play-off dates: https://spfl.co.uk/news/key-dates-for-202627
- KNVB 2026/27 professional-football relegation/play-off rule documents: https://www.knvb.nl/themas/reglementen-en-besluiten/reglementen-en-besluiten
- Liga Portugal 2026/27 playoff pairings: https://www.ligaportugal.pt/news/28154/definido-o-emparelhamento-dos-playoffs-202627
- Swiss Football League 2026/27 dates and top-two-tier barrage: https://sfl.ch/articles/la-sfl-presente-le-plan-des-dates-pour-la-saison-202627
- Italian Serie B 2026/27 season rules overview (secondary source; qualifying-points exception separately flagged): https://sport.sky.it/calcio/serie-b/2026/07/22/calendario-serie-b-2026-2027-giornate-partite
- Austrian Bundesliga 2026/27 licence-contingent promotion/relegation: https://www.bundesliga.at/de/news/artikel/alles-wissenswerte-zur-saison-2026-27

## QA and remaining work

- 2027 original active club-to-league associations unchanged: **659 clubs in 53 competitions**.
- The **33 source-as-provided membership groups / 280 clubs** remain approved without extra full-roster reconstruction, including the Greek Super League's four original teams.
- **9 additional movement edges** make **16 season-2027 mapped/staged edges** together with the original England/Germany/Spain seven.
- **6 named lower feeder competitions** exist as source-backed *unpopulated non-playable adjacent tiers*. No fabricated clubs or players.
- All **18 tests pass**. The final career-readiness flag is still **off**.
- **34 of 53 active competition codes** still lack linked published movement regimes in the broad-scope diagnostic. Nine original pyramid competition codes remain only partially rule-linked, and nine newly mapped codes have feeder/eligibility still to certify. These categories are mutually exclusive as currently encoded; do not interpret them as missing clubs.
- Next high-value rule sources: Turkey 2026/27 specific TFF sporting regulations; Scottish lower SPFL pathways only if Championship/League One become playable; Dutch exact KNVB professional play-off entrants; Italian Serie B 2026/27 points-gap exception; Australian and North American closed-league declarations, and the minimal one-hop feeder memberships needed for playable league movement.
- **Do not proceed to FC26 or historical career gameplay integration** until user-agreed FC27 competition structure quality gate is passed.

"""Season-aware men's England/Germany game movement-rule reference.

This is NOT a completed country-wide pyramid or a career-ready certificate.
The dated *rule regime* is represented; club licensing and all external
feeder entrant pools must be verified before launching a historical career.
"""
import argparse,csv,json
from pathlib import Path
EDITION_YEARS=tuple(y for y in range(2005,2028) if y!=2025)
EFL="https://www.efl.com/news/2026/march/05/efl-statement--sky-bet-championship-play-off-format/"
NATIONAL="https://www.bbc.co.uk/sport/football/40233762"
BUNDES="https://www.bundesliga.com/en/bundesliga/news/how-does-promotion-and-relegation-work-in-the-bundesliga-10645"
DFB="https://www.dfb.de/fileadmin/_dfbdam/61175-DFB_A-Z_UK_lowRes.pdf"

def source_rules(edition):
    if edition not in EDITION_YEARS:
        raise ValueError("No invented FC25 or future division mapping")
    def edge(lower,upper,up_auto,up_playoff,eligible,down_auto,source,regime):
        return dict(edition=edition,lower=lower,upper=upper,
            direct_promotions=up_auto,playoff_promotions=up_playoff,
            playoff_entrants=eligible,direct_relegations=down_auto,
            rule_regime=regime,evidence_url=source,
            source_status="published_regime_with_gameplay_implementation_review",
            feeder_pool_status="not_yet_verified")
    champ=("3rd-8th; 5v8 and 6v7 eliminators; 3rd/4th bye" if edition>=2027
           else "3rd-6th four-team play-off")
    nat=("2nd-7th six-team play-off" if edition>=2018
         else "2nd-5th four-team play-off")
    rows=[
        edge("ENG:CH","ENG:PL",2,1,champ,3,EFL,
             "2026/27 enlarged Championship playoff" if edition>=2027
             else "historical four-club Championship playoff"),
        edge("ENG:L1","ENG:CH",2,1,"3rd-6th",3,EFL,"league-one-four-team-playoff"),
        edge("ENG:L2","ENG:L1",3,1,"4th-7th",4,EFL,"league-two-four-team-playoff"),
        edge("ENG:NL","ENG:L2",1,1,nat,2,NATIONAL,
             "six-club National League playoff" if edition>=2018
             else "four-club Conference/National playoff")]
    if edition>=2009:
        rows.append(edge("GER:BL2","GER:BL1",2,1,
             "3rd lower v 16th upper; two legs",2,BUNDES,
             "Bundesliga relegation playoff reinstated 2008/09"))
        rows.append(edge("GER:D3","GER:BL2",2,1,
             "3rd lower v 16th upper; two legs",2,DFB,
             "3.Liga new competition from 2008/09"))
    else:
        rows.append(edge("GER:BL2","GER:BL1",3,0,"none",3,BUNDES,
             "before 2008/09 Bundesliga playoff restart"))
        # Before 2008/09 3. Liga did not exist; Regionalliga North/South
        # relegation and special reorganisation require further evidence.
    return rows

def export(outdir):
    folder=Path(outdir);folder.mkdir(parents=True,exist_ok=True)
    rows=[edge for y in EDITION_YEARS for edge in source_rules(y)]
    with (folder/"SEASON_VERSIONED_MOVEMENT_RULES.csv").open(
          "w",encoding="utf-8-sig",newline="") as f:
        wr=csv.DictWriter(f,fieldnames=tuple(rows[0]))
        wr.writeheader();wr.writerows(rows)
    result={"editions":len(EDITION_YEARS),"movement_rule_records":len(rows),
       "national_playoffs_expanded_at_2018":True,
       "championship_playoffs_expanded_at_2027":True,
       "german_third_division_first_edition":2009,
       "complete_feeder_pools":False,"historical_career_ready":False,
       "status":"Season-specific source-backed rules; all league club pools and exceptions still require full validation"}
    (folder/"SEASON_VERSIONED_MOVEMENT_RULES_AUDIT.json").write_text(
         json.dumps(result,indent=2))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",required=True)
    opt=p.parse_args()
    print(json.dumps(export(opt.output),indent=2))

"""Validate machine-readable PES 2020 / historical FIFA datasets remotely.

Reads the datasets in CI memory, exports ONLY field coverage, file counts and
identity-key availability. No player ratings or full source CSV are republished.
"""
import argparse
from collections import Counter
import csv
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen

SOURCES={
 "pes2020_public_research_csv":{
  "url":"https://raw.githubusercontent.com/mlblbc/pes---Data-visualization-project/5882c0023a7f16eda4599adc87c7ba160aa9411e/pes_2020.csv",
  "edition":"PES 2020",
  "snapshot":"2020-12-06",
 },
 "fifa2020_research_csv":{
  "url":"https://raw.githubusercontent.com/AMRYB/FIFA-Dashboard/63dfdeccb80cf68d7cd116cbac88e206a0fe3e31/players_20.csv",
  "edition":"FIFA 20",
  "snapshot":"2026-05-12 (repository commit, not rating edition)",
 },
 "fifa2005_research_csv":{
  "url":"https://raw.githubusercontent.com/lbenz730/fifa_model/2901373e446cc21671916ac0f25ca30716b626aa/stats/player_stats_2005.csv",
  "edition":"FIFA 2005",
  "snapshot":"2020-05-09 (repository commit, not rating edition)",
 },
}
KEYS={
 "ea_id":("sofifa_id","player_id","playerid","id"),
 "date_of_birth":("dob","birth_date","date_of_birth","birthday"),
 "player_name":("name","name_real","player_name","full_name","long_name","short_name"),
 "playing_positions":("player_positions","player_position","position","positions","pos"),
 "overall":("overall","ovr","overall_rating","rating"),
 "potential":("potential","pot"),
 "contract":("club_contract_valid_until_year","contract_valid_until","contract_end"),
 "wage":("wage","wage_eur","weekly_wage"),
 "alternative_position_rating":("ls","st","rs","lw","lf","cf","rf","rw","lam","cam","ram",
   "lm","lcm","cm","rcm","rm","lwb","ldm","cdm","rdm","rwb","lb","lcb","cb","rcb","rb"),
 "ability_values":("speed","acceleration","ball_control","defensive_awareness",
   "sprint_speed","offensive_awareness","attacking_finishing","finishing","passing",
   "skill_dribbling","weak_foot","stamina","dribbling"),
}


def schema_probe(text,source):
    reader=csv.DictReader(io.StringIO(text))
    columns=reader.fieldnames or []
    if not 3<=len(columns)<=350:
        raise ValueError("CSV header absent or unusual")
    lower={x.strip().casefold():x for x in columns if x}
    exact_matches={key:[lower[c] for c in aliases if c in lower]
                   for key,aliases in KEYS.items()}
    contains={
        key:[col for col in columns if any(k in col.casefold() for k in aliases)]
        for key,aliases in KEYS.items()
    }
    count=0
    nonempty_per_column=Counter()
    for row in reader:
        count+=1
        if count<=150:
            for key,value in row.items():
                if value is not None and str(value).strip():
                    nonempty_per_column[key]+=1
    return {
        "source":source,"columns_total":len(columns),
        "rows_total":count,
        "column_names":columns,
        "candidate_exact_fields":exact_matches,
        "candidate_partial_fields":{key:v[:12] for key,v in contains.items()},
        "first_150_nonempty_columns":dict(nonempty_per_column),
        "identification_method":(
            "EA ID + DOB possible" if exact_matches["ea_id"] and exact_matches["date_of_birth"]
            else "Name + DOB possible" if exact_matches["player_name"] and exact_matches["date_of_birth"]
            else "No safe cross-edition identity method from header alone"
        ),
        "edition_warning":"Different season from 2026/27; no current contract inference.",
    }


def fetch(url):
    request=Request(url,headers={"User-Agent":"PES-Challenge-source-coverage/1.0"})
    with urlopen(request,timeout=60) as response:
        content=response.read(75_000_000)
    if len(content)>=75_000_000:
        raise ValueError("Data source exceeded download limit")
    return content.decode("utf-8-sig",errors="replace")


def run(folder):
    target=Path(folder)
    target.mkdir(parents=True,exist_ok=True)
    result={}
    for key,meta in SOURCES.items():
        try:
            result[key]={
                "status":"machine_readable",
                **schema_probe(fetch(meta["url"]),meta["url"]),
                "edition":meta["edition"],
                "source_commit":meta["url"].split("/")[5],
            }
        except Exception as exc:
            result[key]={
                "status":"unavailable_or_bad_schema",
                "error":f"{type(exc).__name__}: {str(exc)[:220]}",
                **meta,
            }
        print(key, result[key]["status"],result[key].get("rows_total"),
              "fields=",result[key].get("columns_total"),
              "identity=",result[key].get("identification_method"),flush=True)
    (target/"historical-source-schemas.json").write_text(
        json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="qa-player-source-historical")
    args=parser.parse_args()
    result=run(args.output)
    if not all(v["status"]=="machine_readable" for v in result.values()):
        raise SystemExit("One or more historical datasets unavailable; see detailed report")

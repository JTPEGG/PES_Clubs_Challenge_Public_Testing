"""Validate machine-readable PES 2020 / historical FIFA datasets remotely.

Reads the datasets in CI memory, exports ONLY field coverage, file counts and
identity-key availability. No player ratings or full source CSV are republished.
"""
import argparse
from collections import Counter,defaultdict
from datetime import date,datetime
from qa_player_source_pilot import sample_players,reference_birthdate,normalized_name
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
 "date_of_birth":("dob","birth_date","date_of_birth","birthday","birthdate"),
 "player_name":("name","name_real","player_name","full_name","long_name","short_name"),
 "playing_positions":("player_positions","player_position","position","positions","pos","registered_position","preferred_positions"),
 "overall":("overall","ovr","overall_rating","rating"),
 "potential":("potential","pot"),
 "contract":("club_contract_valid_until_year","contract_valid_until","contract_end","contract_length"),
 "wage":("wage","wage_eur","weekly_wage"),
 "alternative_position_rating":("ls","st","rs","lw","lf","cf","rf","rw","lam","cam","ram",
   "lm","lcm","cm","rcm","rm","lwb","ldm","cdm","rdm","rwb","lb","lcb","cb","rcb","rb"),
 "ability_values":("speed","acceleration","ball_control","defensive_awareness",
   "sprint_speed","offensive_awareness","attacking_finishing","finishing","passing",
   "skill_dribbling","weak_foot","stamina","dribbling"),
}



PES_ABILITY_COLUMNS=(
    "offensive_awareness","ball_control","dribbling","tight_possession",
    "low_pass","lofted_pass","finishing","heading","place_kicking",
    "curl","speed","acceleration","kicking_power","jump",
    "physical_contact","balance","stamina","defensive_awareness",
    "ball_winning","aggression","gk_awareness","gk_catching",
    "gk_clearing","gk_reflexes","gk_reach",
)
PES_POSITION_COLUMNS=tuple("rating_as_"+x for x in (
    "GK","CB","LB","RB","DMF","CMF","LMF","RMF","AMF",
    "LWF","RWF","SS","CF",
))
_SAMPLE_BY_EA_ID={str(p[0]):reference_birthdate(p[15])
                  for p in sample_players()}


def date_value(raw):
    if not raw:return None
    val=str(raw).strip()
    for fmt in ("%Y-%m-%d","%d-%m-%Y","%m/%d/%Y","%d %b %Y"):
        try:return datetime.strptime(val[:len(datetime.now().strftime(fmt))],fmt).date()
        except ValueError:pass
    return None


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
    matched_pilot=set()
    candidate_ids=set()
    overall_dated_mismatches=0
    pes_attributes=0
    pes_positional=0
    pes_skills=0
    abilities=[col for col in PES_ABILITY_COLUMNS if col in columns]
    positions=[col for col in PES_POSITION_COLUMNS if col in columns]
    skills=[col for col in columns if col.startswith("skill_")]
    ea_id_key=next((x for x in ("sofifa_id","player_id") if x in columns),None)
    dob_key=next((x for x in ("dob","birthdate","birth_date") if x in columns),None)
    for row in reader:
        count+=1
        if count<=150:
            for key,value in row.items():
                if value is not None and str(value).strip():
                    nonempty_per_column[key]+=1
        if abilities and all(row.get(x,"").strip() for x in abilities):
            pes_attributes+=1
        if positions and all(row.get(x,"").strip() for x in positions):
            pes_positional+=1
        if skills and any(row.get(x,"").strip() for x in skills):
            pes_skills+=1
        # Historical join is only verified by stable EA ID AND exact DOB.
        # PES has neither in this file; a name/age candidate is NOT a match.
        if ea_id_key and row.get(ea_id_key) in _SAMPLE_BY_EA_ID:
            key=row[ea_id_key]
            candidate_ids.add(key)
            if dob_key and date_value(row.get(dob_key))==_SAMPLE_BY_EA_ID[key]:
                matched_pilot.add(key)
            else:
                overall_dated_mismatches+=1
    return {
        "source":source,"columns_total":len(columns),
        "rows_total":count,
        "column_names":columns,
        "candidate_exact_fields":exact_matches,
        "candidate_partial_fields":{key:v[:12] for key,v in contains.items()},
        "first_150_nonempty_columns":dict(nonempty_per_column),
        "reference_pilot_ea_id_candidate_count":len(candidate_ids),
        "reference_pilot_verified_id_and_dob_count":len(matched_pilot),
        "reference_pilot_mismatched_or_missing_dob_records":overall_dated_mismatches,
        "native_pes_abilities_available":len(abilities),
        "native_pes_position_rating_columns":len(positions),
        "native_pes_skill_columns":len(skills),
        "records_with_all_detected_pes_abilities":pes_attributes,
        "records_with_all_detected_pes_position_ratings":pes_positional,
        "records_with_any_detected_pes_skills":pes_skills,
        "identification_method":(
            "EA ID + DOB possible" if exact_matches["ea_id"] and exact_matches["date_of_birth"]
            else "Name + DOB possible" if exact_matches["player_name"] and exact_matches["date_of_birth"]
            else "No safe cross-edition identity method from header alone"
        ),
        "edition_warning":"Different season from 2026/27; no current contract inference.",
    }



def fifa20_pes20_crosswalk_candidates(fifa_text,pes_text):
    """Discover candidate historical identity joins, NOT certified mappings.

    Same-game-season short name, nationality and age are all required. A
    collision in EITHER source invalidates candidate auto-acceptance. FIFA
    players get stable EA IDs; PES's downloaded CSV has no stable PES IDs.
    """
    fifa_rows=list(csv.DictReader(io.StringIO(fifa_text)))
    pes_rows=list(csv.DictReader(io.StringIO(pes_text)))
    index_fifa=defaultdict(list)
    index_pes=defaultdict(list)
    for r in fifa_rows:
        key=(normalized_name(r.get("short_name") or ""),
             normalized_name(r.get("nationality") or ""),
             str(r.get("age") or "").strip())
        if all(key):index_fifa[key].append(r)
    for r in pes_rows:
        key=(normalized_name(r.get("name") or ""),
             normalized_name(r.get("nationality") or ""),
             str(r.get("age") or "").strip())
        if all(key):index_pes[key].append(r)
    shared=set(index_fifa)&set(index_pes)
    qualified={}
    ambiguous=0
    same_club=0
    for key in shared:
        left=index_fifa[key];right=index_pes[key]
        if len(left)!=1 or len(right)!=1:
            ambiguous+=1
            continue
        src=left[0];pes=right[0]
        eaid=str(src.get("sofifa_id") or "").strip()
        if not eaid.isdigit():continue
        qualified[eaid]=key
        if normalized_name(src.get("club") or "")==normalized_name(pes.get("team_name") or ""):
            same_club+=1
    sample_ids={str(p[0]):reference_birthdate(p[15]) for p in sample_players()}
    matched_fifa=set()
    for row in fifa_rows:
        eid=str(row.get("sofifa_id") or "").strip()
        if eid in sample_ids and date_value(row.get("dob"))==sample_ids[eid]:
            matched_fifa.add(eid)
    return {
        "label":"historical_CANDIDATES_NOT_VERIFIED_IDENTITIES",
        "matching_criteria":"same short player name + nationality + age in FIFA20 and PES20",
        "requires_unique_in_both_sources":True,
        "qualifying_candidate_pairs":len(qualified),
        "ambiguous_shared_keys_rejected":ambiguous,
        "same_raw_club_name_pairs":same_club,
        "modern_pilot_exact_fifa20_ids":len(matched_fifa),
        "modern_pilot_with_pes20_candidate":len(matched_fifa & set(qualified)),
        "limitation":"PES source CSV lacks stable player ID and DOB. Even unique name/nationality/age can be wrong; do not automatically merge profiles or use 2019 PES stats for 2026 ratings.",
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
    source_text={}
    for key,meta in SOURCES.items():
        try:
            body=fetch(meta["url"])
            if key in ("pes2020_public_research_csv","fifa2020_research_csv"):
                source_text[key]=body
            result[key]={
                "status":"machine_readable",
                **schema_probe(body,meta["url"]),
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
    if {"pes2020_public_research_csv","fifa2020_research_csv"}<=set(source_text):
        result["cross_source_candidate_audit"]=fifa20_pes20_crosswalk_candidates(
            source_text["fifa2020_research_csv"],
            source_text["pes2020_public_research_csv"],
        )
        print("PES-FIFA possible crosswalk:",
              result["cross_source_candidate_audit"]["qualifying_candidate_pairs"],
              "pilot overlaps:",
              result["cross_source_candidate_audit"]["modern_pilot_with_pes20_candidate"],
              flush=True)
    (target/"historical-source-schemas.json").write_text(
        json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="qa-player-source-historical")
    args=parser.parse_args()
    result=run(args.output)
    if not all(v["status"]=="machine_readable" for k,v in result.items() if k in SOURCES):
        raise SystemExit("One or more historical datasets unavailable; see detailed report")

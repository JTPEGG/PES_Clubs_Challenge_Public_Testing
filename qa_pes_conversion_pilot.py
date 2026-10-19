"""Real-source PES2020 calibration and sample across historical FIFA editions.

PES/FIFA links via name+nationality+age+club are *research candidates*, NOT
verified global identities. Quantile/bias calibrations are therefore proposals,
never activated automatically as genuine Konami formulas.
"""
from collections import defaultdict,Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
from statistics import median,mean
from urllib.request import Request,urlopen

from world_fifa_pes_converter import convert,TARGETS,MODEL_VERSION

SRC={
 2005:"https://raw.githubusercontent.com/lbenz730/fifa_model/2901373e446cc21671916ac0f25ca30716b626aa/stats/player_stats_2005.csv",
 2012:"https://raw.githubusercontent.com/lbenz730/fifa_model/2901373e446cc21671916ac0f25ca30716b626aa/stats/player_stats_2012.csv",
 2020:"https://raw.githubusercontent.com/lbenz730/fifa_model/2901373e446cc21671916ac0f25ca30716b626aa/stats/player_stats_2020.csv",
 2021:"https://raw.githubusercontent.com/lokesh28-krish/Analysis-of-Fifa-21-Players-Dataset/9d55181662e2dd3caf2dabc9365a2c8e564407b9/players_21.csv",
 2023:"https://raw.githubusercontent.com/miraehab/FIFA-23-ML-Project/0d188076fa37b3d82c5d390048e00ec5a43b04a7/players_fifa23.csv",
 2027:"https://raw.githubusercontent.com/LakshmiKanth11/EA_FC_ANALYSIS/c0b2542d9fcae72d2c538a472a30ee57c4e7c75e/EA_FC_PLAYERS_DATASET_AND_%20DASHBOARD/data/players.csv",
}
PES_SRC="https://raw.githubusercontent.com/mlblbc/pes---Data-visualization-project/5882c0023a7f16eda4599adc87c7ba160aa9411e/pes_2020.csv"
PES_TARGETS={k:k for k in TARGETS}


def fetch_csv(url,limit=20_000_000):
    request=Request(url,headers={"User-Agent":"PES-Challenge-ConverterQA/1.0"})
    with urlopen(request,timeout=60) as resp:
        body=resp.read(limit+1)
    if len(body)>limit:raise ValueError("Source too large")
    return list(csv.DictReader(io.StringIO(body.decode("utf-8-sig",errors="replace"))))


def norm(value):
    return re.sub(r"[^a-z0-9]","",str(value or "").lower())


def fifa_name(r):
    return r.get("name") or r.get("short_name") or r.get("Name") or ""


def kf(r):
    return (norm(fifa_name(r)),norm(r.get("nationality") or ""),
            str(r.get("age") or ""),norm(r.get("club") or ""))


def kp(r):
    return (norm(r.get("name") or ""),norm(r.get("nationality") or ""),
            str(r.get("age") or ""),norm(r.get("team_name") or ""))


def pairs_for_calibration(fifa,pes):
    """Same name, age, nationality and club; reject all ambiguous keys."""
    f=defaultdict(list);p=defaultdict(list)
    for row in fifa:
        key=kf(row)
        if all(key):f[key].append(row)
    for row in pes:
        key=kp(row)
        if all(key):p[key].append(row)
    pairs=[]
    for key in f.keys()&p.keys():
        if len(f[key])==1 and len(p[key])==1:
            pairs.append((f[key][0],p[key][0]))
    return sorted(pairs,key=lambda x:kf(x[0]))


def observed_pes(row,attr):
    try:
        value=int(float(row.get(PES_TARGETS[attr],"")))
    except (TypeError,ValueError):
        return None
    return value if 40<=value<=99 else None


def calibration_proposal(pairs):
    """Train median residual shift on 80%, report held-out MAE for each PES stat.

    Calibration remains inactive until reviewed. No training on held-out players.
    """
    tracks=defaultdict(lambda:{"train":[],"test":[]})
    for fifa,pes in pairs:
        pred=convert(fifa,2020)
        key=":".join(kf(fifa))
        bucket="test" if int(hashlib.sha256(key.encode()).hexdigest()[:8],16)%5==0 else "train"
        for attr in TARGETS:
            source=pred["abilities"][attr]
            actual=observed_pes(pes,attr)
            if source["value"] is None or actual is None:continue
            tracks[attr][bucket].append((source["value"],actual))
    result={}
    for attr in TARGETS:
        data=tracks[attr]
        if len(data["train"])<25 or len(data["test"])<8:
            result[attr]={"train_pairs":len(data["train"]),"holdout_pairs":len(data["test"]),
                          "suggested_shift":None,"quality":"insufficient_benchmark_pairs"}
            continue
        residuals=[actual-pred for pred,actual in data["train"]]
        # Median is resistant to erroneous name matches; still not
        # sufficiently trustworthy to be a fully verified identity mapping.
        shift=max(-15,min(15,round(median(residuals))))
        mae_before=round(mean(abs(p-a) for p,a in data["test"]),2)
        mae_after=round(mean(abs(max(40,min(99,p+shift))-a) for p,a in data["test"]),2)
        result[attr]={
            "train_pairs":len(data["train"]),"holdout_pairs":len(data["test"]),
            "suggested_shift":shift,"holdout_mae_before":mae_before,
            "holdout_mae_after":mae_after,
            "validation":"provisional_same_name_age_nation_club_candidate",
            "recommended":mae_after<mae_before-0.10
        }
    return result


def coverage(rows,edition):
    metrics=Counter();examples=[]
    for i,row in enumerate(rows):
        obj=convert(row,edition)
        if i<3:
            examples.append({
                "player":obj["player_name"],"overall_source":obj["source_overall"],
                "primary":obj["primary_position"],
                "alternatives":obj["alternative_positions"],
                "pes_estimates":{a:obj["abilities"][a]["value"] for a in (
                    "ball_control","tight_possession","low_pass",
                    "finishing","speed","defensive_awareness","ball_winning")}
            })
        metrics["players"]+=1
        metrics["alternatives"]+=len(obj["alternative_positions"])
        for attr,data in obj["abilities"].items():
            metrics[data["method"]]+=1
            metrics["floor_adjusted"]+=int(data["floor_applied"])
            if data["value"] is None:metrics["missing_"+attr]+=1
    metrics["available_ability_share_pct"]=round(
        100*(25*len(rows)-metrics["missing"])/(25*len(rows)),2) if rows else 0
    return dict(metrics),examples


def run(output):
    all_files={year:fetch_csv(url) for year,url in SRC.items()}
    pes=fetch_csv(PES_SRC)
    report={"model_version":MODEL_VERSION,
        "limitations":[
          "No automatic PES Overall Rating is produced.",
          "PES/FIFA paired identities are provisional and not verified IDs.",
          "Historical source FIFA05-20 can have incomplete attributes ('NA').",
          "PES 2020 comparisons are release-specific; no cross-era attribute drift is corrected.",
          "FC27 output concerns modern edition not native PES2020.",
          "Calibration proposals are not automatically applied to conversion.",
        ],
        "sources":SRC,"pes_reference_source":PES_SRC,
        "source_files":{str(y):len(v) for y,v in all_files.items()},
        "source_pes2020_rows":len(pes),
        "editions":{}
    }
    for y,items in all_files.items():
        summary,examples=coverage(items[:100],y)
        report["editions"][str(y)]={"sample_count":100,"field_metrics":summary,
                                    "examples":examples}
    pairs=pairs_for_calibration(all_files[2020],pes)
    report["benchmark_pair_candidates"]=len(pairs)
    report["benchmark_pair_confidence"]="provisional_not_verified_identity"
    report["suggested_calibration"]=calibration_proposal(pairs)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    (output/"conversion-pilot.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    with (output/"conversion-examples.jsonl").open("w",encoding="utf-8") as f:
        for y in (2005,2020,2023,2027):
            for row in all_files[y][:20]:
                f.write(json.dumps(convert(row,y),ensure_ascii=False)+"\n")
    print(json.dumps({
        "sampled_years":{y:report["editions"][str(y)]["field_metrics"]
                         for y in all_files},
        "pes2020_rows":len(pes),
        "paired_benchmark_candidates":len(pairs),
        "offsets":{k:v for k,v in report["suggested_calibration"].items()
                   if v.get("recommended")}
    },indent=2),flush=True)


if __name__=="__main__":
    run("qa-conversion-pilot")

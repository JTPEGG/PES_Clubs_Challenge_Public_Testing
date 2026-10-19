"""Versioned, traceable FIFA/FC -> PES 2020 *estimated* ability model.

This is NOT a native Konami converter or an official PES rating formula.
Each input edition is processed separately. Never overwrite original FIFA rows.
Unknown remains None. Every generated ability records its source fields,
method, confidence and whether 40-99 PES-style bounds were applied.
"""
import csv
import io
import json
import re
from zipfile import ZipFile

MODEL_VERSION="fifa-to-pes2020-abilities-v1"
PES_MIN,PES_MAX=40,99

# Each value maps a PES 2020 stat to multiple independently measured source
# statistics. Column candidates accommodate 2005-20 FIFAIndex, 2021-22
# SoFIFA, FIFA23 CamelCase, and FC24-27 third-party CSV headers.
ALIASES={
 "att_pos":("att_position","attacking_positioning","mentality_positioning","Positioning"),
 "react":("reactions","movement_reactions","Reactions"),
 "ball":("ball_control","skill_ball_control","BallControl"),
 "dribble":("dribbling","skill_dribbling","Dribbling"),
 "agility":("agility","movement_agility","Agility"),
 "short":("short_pass","attacking_short_passing","ShortPassing"),
 "vision":("vision","mentality_vision","Vision"),
 "long":("long_pass","skill_long_passing","LongPassing"),
 "cross":("crossing","attacking_crossing","Crossing"),
 "finish":("finishing","attacking_finishing","Finishing"),
 "shotacc":("shot_accuracy","ShotAccuracy"),
 "heading":("heading","attacking_heading_accuracy","HeadingAccuracy"),
 "fk":("free_kick_accuracy","skill_fk_accuracy","FKAccuracy"),
 "curve":("curve","skill_curve","Curve"),
 "sprint":("sprint_speed","movement_sprint_speed","SprintSpeed"),
 "accel":("acceleration","movement_acceleration","Acceleration"),
 "power":("shot_power","power_shot_power","ShotPower"),
 "jump":("jumping","power_jumping","Jumping"),
 "strength":("strength","power_strength","Strength"),
 "balance":("balance","movement_balance","Balance"),
 "stamina":("stamina","power_stamina","Stamina"),
 "mark":("marking","defending_marking","defending_marking_awareness",
         "defending_awareness","Marking"),
 "intercept":("interceptions","mentality_interceptions","Interceptions"),
 "stand":("stand_tackle","defending_standing_tackle","StandingTackle"),
 "slide":("slide_tackle","defending_sliding_tackle","SlidingTackle"),
 "aggression":("aggression","mentality_aggression","Aggression"),
 "gkpos":("gk_positioning","goalkeeping_positioning","GKPositioning"),
 "gkhandle":("gk_handling","goalkeeping_handling","GKHandling"),
 "gkkick":("gk_kicking","goalkeeping_kicking","GKKicking"),
 "gkreflex":("gk_reflexes","goalkeeping_reflexes","GKReflexes"),
 "gkdive":("gk_diving","goalkeeping_diving","GKDiving"),
 # fallback CATEGORY aggregates only, not known 1:1 equivalents
 "pace":("pace","PaceTotal"),"shooting":("shooting","ShootingTotal"),
 "passing":("passing","PassingTotal"),
 "dribbling_overall":("DribblingTotal",),
 "defending":("defending","DefendingTotal"),
 "physical":("physic","physicality","PhysicalityTotal")
}
# Weighted component combinations; blends are design assumptions pending
# calibration. A single component is closer to a direct mapping.
TARGETS={
 "offensive_awareness":(("att_pos",.80),("react",.20)),
 "ball_control":(("ball",1.0),),
 "dribbling":(("dribble",.85),("agility",.15)),
 "tight_possession":(("ball",.44),("dribble",.35),("agility",.21)),
 "low_pass":(("short",.82),("vision",.18)),
 "lofted_pass":(("long",.82),("cross",.18)),
 "finishing":(("finish",.90),("shotacc",.10)),
 "heading":(("heading",1.0),),
 "set_piece_taking":(("fk",.85),("curve",.15)),
 "curl":(("curve",1.0),),
 "speed":(("sprint",1.0),),
 "acceleration":(("accel",1.0),),
 "kicking_power":(("power",1.0),),
 "jump":(("jump",1.0),),
 "physical_contact":(("strength",1.0),),
 "balance":(("balance",1.0),),
 "stamina":(("stamina",1.0),),
 "defensive_awareness":(("mark",.85),("intercept",.15)),
 "ball_winning":(("stand",.57),("intercept",.32),("slide",.11)),
 "aggression":(("aggression",1.0),),
 "gk_awareness":(("gkpos",1.0),),
 "gk_catching":(("gkhandle",1.0),),
 "gk_clearing":(("gkkick",.80),("gkhandle",.20)),
 "gk_reflexes":(("gkreflex",1.0),),
 "gk_reach":(("gkdive",1.0),),
}
assert len(TARGETS)==25

# Category fallback: intentionally low confidence; do not generate GK stats
# from non-goalkeeper categories.
CATEGORY_FALLBACK={
 "offensive_awareness":"shooting","ball_control":"dribbling_overall",
 "dribbling":"dribbling_overall","tight_possession":"dribbling_overall",
 "low_pass":"passing","lofted_pass":"passing",
 "finishing":"shooting","heading":"shooting",
 "set_piece_taking":"shooting","curl":"passing",
 "speed":"pace","acceleration":"pace",
 "kicking_power":"shooting","jump":"physical",
 "physical_contact":"physical","balance":"dribbling_overall",
 "stamina":"physical","defensive_awareness":"defending",
 "ball_winning":"defending","aggression":"physical",
}
# Basic self-contained position names; do not infer *additional* playable
# positions based on attributes or from family DEF/MID/FWD alone.
POS_MAP={
 "GK":"GK","CB":"CB","LCB":"CB","RCB":"CB","LB":"LB","RB":"RB",
 "LWB":"LWB","RWB":"RWB","CDM":"DMF","DM":"DMF","DMF":"DMF",
 "CM":"CMF","CMF":"CMF","CAM":"AMF","AM":"AMF","AMF":"AMF",
 "LM":"LMF","LMF":"LMF","RM":"RMF","RMF":"RMF",
 "LW":"LWF","LWF":"LWF","RW":"RWF","RWF":"RWF",
 "ST":"CF","CF":"CF","SS":"SS","LF":"SS","RF":"SS",
 "SW":"SW","SB":"SB","WB":"WB","SM":"SM","WF":"WF",
 "RWM":"RMF","LWM":"LMF"
}
POS_KEYS=("player_positions","preferred_positions","positions","Positions",
          "position","BestPosition","Position")
GROUPS={
 "GK":("gk_awareness","gk_catching","gk_clearing","gk_reflexes","gk_reach"),
 "CB":("defensive_awareness","ball_winning","physical_contact","jump","speed"),
 "LB":("defensive_awareness","ball_winning","speed","stamina","lofted_pass"),
 "RB":("defensive_awareness","ball_winning","speed","stamina","lofted_pass"),
 "LWB":("speed","stamina","lofted_pass","defensive_awareness","ball_winning"),
 "RWB":("speed","stamina","lofted_pass","defensive_awareness","ball_winning"),
 "DMF":("ball_winning","defensive_awareness","low_pass","physical_contact","stamina"),
 "CMF":("low_pass","ball_control","stamina","ball_winning","lofted_pass"),
 "AMF":("low_pass","ball_control","tight_possession","offensive_awareness","dribbling"),
 "LMF":("stamina","speed","dribbling","lofted_pass","low_pass"),
 "RMF":("stamina","speed","dribbling","lofted_pass","low_pass"),
 "LWF":("dribbling","acceleration","speed","finishing","ball_control"),
 "RWF":("dribbling","acceleration","speed","finishing","ball_control"),
 "CF":("finishing","offensive_awareness","kicking_power","physical_contact","ball_control"),
 "SS":("finishing","dribbling","ball_control","offensive_awareness","low_pass")
}


def field_key(text):
    return re.sub("[^a-z0-9]","",str(text).casefold())


def numeric(value):
    if value is None or str(value).strip().lower() in ("","na","n/a","nan","none","-","null"):
        return None
    try:
        number=float(str(value).replace(",","").strip())
    except (TypeError,ValueError):
        return None
    if not (1<=number<=99):
        return None
    return number


def record_value(row,aliases):
    lookup={field_key(key):key for key in row}
    for alias in aliases:
        key=lookup.get(field_key(alias))
        if key is not None:
            value=numeric(row.get(key))
            if value is not None:
                return value,key
    return None,None


def positions(row):
    lookup={field_key(k):k for k in row}
    field=next((lookup[field_key(k)] for k in POS_KEYS if field_key(k) in lookup
                and row.get(lookup[field_key(k)])),None)
    if field is None:
        return []
    # FC27 current primary and alternatives are separate columns. Preserve
    # order and zero-to-many cardinality. Slash is common in FIFA05–20.
    chunks=[str(row[field])]
    for alias in ("alternate_positions","alternatePositions"):
        if field_key(alias) in lookup:
            chunks.append(str(row[lookup[field_key(alias)]] or ""))
    output=[]
    for chunk in chunks:
        for item in re.split(r"[,;/| ]+",chunk.upper()):
            pos=POS_MAP.get(item.strip())
            if pos and pos not in output:
                output.append(pos)
    return output


def identity(row,edition):
    return {
        "source_edition":edition,
        "source_player_id":next((row.get(k) for k in
           ("player_id","sofifa_id","ID") if row.get(k)),None),
        "player_name":next((row.get(k) for k in
           ("name","long_name","short_name","Name","FullName",
            "common_name") if row.get(k)),None),
        "source_overall":next((row.get(k) for k in
           ("rating","overall","overall_rating","Overall") if row.get(k)),None),
    }


def convert(row,edition,*,calibration=None):
    """Return one footballer with 25 sourced/estimated/missing PES abilities.

    Optional calibration is a frozen approved bias shift dictionary by PES
    attribute. Calibration NEVER supplies missing data; it shifts only values
    that are actually estimated from recorded source observations.
    """
    pos=positions(row)
    resolutions={}
    for name,parts in TARGETS.items():
        available=[]
        for alias,weight in parts:
            value,col=record_value(row,ALIASES[alias])
            if value is not None:
                available.append((value,weight,col))
        fallback=False
        if available:
            # Normalize among existing observations; never count missing input
            # as zero. Mixed-source means an estimated *blend*.
            score=sum(v*w for v,w,_ in available)/sum(w for _,w,_ in available)
            method="direct_equivalent" if len(available)==1 and len(parts)==1 else "weighted_estimate"
            confidence="medium" if method=="direct_equivalent" else "medium_low"
            cols=[col for _,_,col in available]
        elif name in CATEGORY_FALLBACK:
            cat=CATEGORY_FALLBACK[name]
            v,col=record_value(row,ALIASES[cat])
            if v is None:
                score=None
            else:
                score=v;fallback=True;cols=[col]
                method="aggregate_reconstruction";confidence="low"
        else:
            score=None
        if score is None:
            resolutions[name]={"value":None,"method":"missing","confidence":"none",
                               "source_columns":[],"floor_applied":False}
            continue
        offset=(calibration or {}).get(name,0)
        if not isinstance(offset,(int,float)) or abs(offset)>15:
            raise ValueError("Unapproved calibration shift")
        raw=round(score+offset)
        clipped=max(PES_MIN,min(PES_MAX,raw))
        resolutions[name]={
            "value":clipped,"method":method,"confidence":confidence,
            "source_columns":cols,
            "floor_applied":clipped!=raw,"calibration_offset":offset
        }
    role_scores={}
    for p in pos:
        keys=GROUPS.get(p)
        if keys:
            available=[resolutions[k]["value"] for k in keys if resolutions[k]["value"] is not None]
            if len(available)>=3:
                overall=numeric(identity(row,edition)["source_overall"])
                # Explicitly heuristic *suitability index*, NOT Konami OVR.
                avg=sum(available)/len(available)
                score=.75*avg+.25*overall if overall is not None else avg
                role_scores[p]={
                    "value":max(40,min(99,round(score))),
                    "kind":"modeled_role_fit_not_pes_ovr",
                    "confidence":"low","input_abilities":len(available)
                }
            else:
                role_scores[p]={"value":None,"kind":"insufficient_abilities",
                                "confidence":"none","input_abilities":len(available)}
        else:
            role_scores[p]={"value":None,"kind":"no_rule_for_position",
                            "confidence":"none","input_abilities":0}
    return {**identity(row,edition),
            "model_version":MODEL_VERSION,
            "primary_position":pos[0] if pos else None,
            "alternative_positions":pos[1:],
            "abilities":resolutions,
            "position_fit_indices":role_scores,
            "caveats":[
                "FIFA scores are not native PES scores; mapping is experimental.",
                "Values marked weighted_estimate or aggregate_reconstruction are inferred.",
                "Position-fit indices are not Konami PES positional overall ratings.",
                "Unlisted positions are unknown; they are not automatically forbidden.",
            ]}


def convert_csv_stream(csv_file,edition,output,*,limit=None,calibration=None):
    """Stream arbitrary edition CSV to JSONL without loading whole source.
    Original FIFA CSV remains authoritative and is not overwritten.
    """
    reader=csv.DictReader(csv_file)
    counts={"processed":0,"direct":0,"estimated":0,"missing":0,
            "floor_adjusted":0,"alternate_positions":0,"with_fit":0}
    for row in reader:
        if limit is not None and counts["processed"]>=limit:break
        result=convert(row,edition,calibration=calibration)
        output.write(json.dumps(result,ensure_ascii=False)+"\n")
        counts["processed"]+=1
        counts["alternate_positions"]+=len(result["alternative_positions"])
        counts["with_fit"]+=sum(v["value"] is not None
                                 for v in result["position_fit_indices"].values())
        for d in result["abilities"].values():
            if d["method"]=="missing":counts["missing"]+=1
            elif d["method"]=="direct_equivalent":counts["direct"]+=1
            else:counts["estimated"]+=1
            counts["floor_adjusted"]+=int(d["floor_applied"])
    return counts


def convert_archive(zip_path,output_path,*,editions=None,limit_per_edition=None):
    """Direct conversion from hard-copy archive to provenance-preserving JSONL."""
    totals={}
    with ZipFile(zip_path) as archive,open(output_path,"w",encoding="utf-8") as out:
        for f in archive.namelist():
            match=re.search(r"/data/(\d{4})_",f)
            if not match:continue
            year=int(match.group(1))
            if editions is not None and year not in editions:continue
            with archive.open(f) as source:
                text=io.TextIOWrapper(source,encoding="utf-8-sig",errors="replace",newline="")
                totals[str(year)]=convert_csv_stream(text,year,out,limit=limit_per_edition)
    return totals

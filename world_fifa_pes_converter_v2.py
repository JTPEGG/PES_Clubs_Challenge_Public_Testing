"""FIFA/FC -> PES2020 complete-rating reconstruction (experimental v2).

Frozen decisions:
 * FIFA 20 is the ONLY edition used to calibrate against PES 2020.
 * FC 25 (2025) is an explicit SOURCE GAP: no imputations or exports for it.
 * All 25 PES2020 core numeric ratings MUST exist for a playable conversion.
 * Reconstructed attributes retain method, inputs, confidence and source year.
 * A CSV of estimates is not a game-ready Xbox/PS4/PC option file.

A 1-99 FIFA measurement and a 40-99 PES measurement have different meanings.
This code is a research model, NOT a Konami ratings formula.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import median
from math import isfinite
import re

from world_fifa_pes_converter import (
    convert as v1_convert, TARGETS, ALIASES, POS_MAP, GROUPS, PES_MIN,
    PES_MAX, record_value, numeric,
)

MODEL_VERSION="fifa-to-pes2020-complete-v2"
TARGET_GAME="PES 2020"
CALIBRATION_FIFA_EDITION=2020
DISALLOWED_EDITIONS=frozenset({2025})
PES_POSITIONS=frozenset(("GK","CB","LB","RB","DMF","CMF","LMF","RMF",
                          "AMF","LWF","RWF","SS","CF"))
POSITION_FAMILY={
 "GK":"GK","CB":"DEF","LB":"DEF","RB":"DEF","LWB":"DEF","RWB":"DEF",
 "DMF":"MID","CMF":"MID","LMF":"MID","RMF":"MID","AMF":"MID",
 "LWF":"ATT","RWF":"ATT","SS":"ATT","CF":"ATT",
}
# Where FIFA did not measure the precise target, lean on related abilities.
# Values chosen by football meaning, NOT fitted coefficients.
RELATIONS={
 "offensive_awareness":(("react",0.45),("finish",0.35),("vision",0.20)),
 "ball_control":(("dribble",.50),("short",.30),("agility",.20)),
 "dribbling":(("ball",.60),("agility",.40)),
 "tight_possession":(("ball",.45),("dribble",.35),("agility",.20)),
 "low_pass":(("short",.60),("vision",.25),("long",.15)),
 "lofted_pass":(("long",.60),("cross",.30),("short",.10)),
 "finishing":(("shotacc",.55),("att_pos",.30),("power",.15)),
 "heading":(("jump",.30),("strength",.25),("finish",.45)),
 "place_kicking":(("curve",.45),("long",.20),("short",.35)),
 "curl":(("fk",.60),("cross",.40)),
 "speed":(("accel",.72),("agility",.28)),
 "acceleration":(("sprint",.70),("agility",.30)),
 "kicking_power":(("long",.40),("finish",.30),("strength",.30)),
 "jump":(("heading",.60),("strength",.40)),
 "physical_contact":(("strength",.70),("balance",.30)),
 "balance":(("agility",.70),("strength",.30)),
 "stamina":(("sprint",.20),("react",.25),("strength",.55)),
 "defensive_awareness":(("intercept",.50),("stand",.35),("react",.15)),
 "ball_winning":(("stand",.50),("intercept",.35),("slide",.15)),
 "aggression":(("strength",.35),("stand",.35),("intercept",.30)),
 "gk_awareness":(("gkpos",.55),("gkreflex",.30),("gkhandle",.15)),
 "gk_catching":(("gkhandle",.65),("gkreflex",.20),("gkpos",.15)),
 "gk_clearing":(("gkkick",.45),("gkhandle",.30),("gkreflex",.25)),
 "gk_reflexes":(("gkdive",.48),("gkpos",.27),("gkhandle",.25)),
 "gk_reach":(("gkdive",.55),("gkreflex",.30),("gkpos",.15)),
}
assert set(RELATIONS)==set(TARGETS)


class ConversionError(ValueError):
    pass


class UnrestoredEdition(ConversionError):
    pass


def ensure_edition(edition):
    if not isinstance(edition,int) or not 2005<=edition<=2027:
        raise ConversionError("Unsupported FIFA edition")
    if edition in DISALLOWED_EDITIONS:
        raise UnrestoredEdition(
            "FC 25 is excluded: source detailed attributes must be restored properly."
        )


def _date(row,edition):
    text=(row.get("dob") or row.get("birthdate") or "").strip()
    if not text or text.lower() in ("na","nan"):
        return None
    for fmt in ("%Y-%m-%d","%d-%m-%Y","%m/%d/%Y","%d/%m/%Y"):
        try:
            dt=datetime.strptime(text,fmt).date()
            if 1900<=dt.year<=2020:
                return dt.isoformat()
        except ValueError:continue
    return None


def _id(row):
    for name in ("player_id","sofifa_id","ID"):
        val=str(row.get(name) or "").strip()
        if val.isdigit():
            return val
    return None


def identity_key(row,edition):
    """No name-only matches. A consistent ID and DOB are REQUIRED."""
    i=_id(row)
    dob=_date(row,edition)
    return (i,dob) if i and dob else None


def _overall(row):
    for name in ("rating","overall","overall_rating","Overall"):
        value=numeric(row.get(name))
        if value is not None:
            return value
    return None


def _family(position):
    return POSITION_FAMILY.get(position,"OTHER")


def _clamp(v):
    if not isinstance(v,(float,int)) or not isfinite(v):
        raise ConversionError("Non-finite calculated ability")
    return max(PES_MIN,min(PES_MAX,round(v)))


def _source_evidence(row,attr):
    """Weighted estimate from related same-edition FIFA observations."""
    available=[]
    for alias,weight in RELATIONS[attr]:
        value,col=record_value(row,ALIASES[alias])
        if value is not None:
            available.append((value,weight,col))
    if not available:
        return None
    total=sum(w for _,w,_ in available)
    return (
        sum(v*w for v,w,_ in available)/total,
        [col for _,_,col in available],
    )


def _method(v,kind,source_fields,source_edition,confidence):
    return {"value":_clamp(v),"method":kind,"confidence":confidence,
            "source_columns":list(dict.fromkeys(source_fields)),
            "source_edition":source_edition,"model_version":MODEL_VERSION}


class EditionContext:
    """An edition and optional adjacent year data; constructed once per season.

    Original input rows stay immutable. Current-edition peer ratings are drawn
    from DIRECT / weighted FIFA columns only, never their own imputations.
    """
    def __init__(self,edition,rows,adjacent=None):
        ensure_edition(edition)
        self.edition=edition
        self.current=rows
        self.adjacent={}
        self.peers=defaultdict(list)
        self.peer_global=defaultdict(list)
        self.rows_by_identity={}
        for r in rows:
            key=identity_key(r,edition)
            if key:
                self.rows_by_identity.setdefault(key,[]).append(r)
            self._register_peer(r)
        for other_year,other_rows in (adjacent or {}).items():
            if other_year in DISALLOWED_EDITIONS:continue
            if other_year==edition or abs(other_year-edition)>2:
                continue
            if other_year<2005 or other_year>2027:continue
            m=defaultdict(list)
            for row in other_rows:
                key=identity_key(row,other_year)
                if key:m[key].append(row)
            self.adjacent[other_year]=m

    def _register_peer(self,row):
        base=v1_convert(row,self.edition)
        p=base["primary_position"]
        family=_family(p)
        rating=_overall(row)
        bin_num=int(rating//10) if rating is not None else -1
        for attr,x in base["abilities"].items():
            if x["method"] not in ("direct_equivalent","weighted_estimate"):
                continue
            if x["value"] is None:continue
            self.peers[(family,bin_num,attr)].append(x["value"])
            self.peer_global[(family,attr)].append(x["value"])

    def adjacent_value(self,row,attribute):
        key=identity_key(row,self.edition)
        if key is None:return None
        current=_overall(row)
        found=[]
        for other_year,mapping in self.adjacent.items():
            group=mapping.get(key,[])
            # Reject duplicate/unresolved registrations, never guess a row.
            if len(group)!=1:continue
            other=group[0]
            v=v1_convert(other,other_year)["abilities"][attribute]
            if v["method"] not in ("direct_equivalent","weighted_estimate"):
                continue
            if v["value"] is None:continue
            prev=_overall(other)
            adjust=0 if current is None or prev is None else max(-6,min(6,(current-prev)*.6))
            found.append((abs(other_year-self.edition),other_year,v["value"]+adjust,v))
        if not found:return None
        found.sort(key=lambda x:(x[0],x[1]))
        min_distance=found[0][0]
        nearest=[x for x in found if x[0]==min_distance]
        value=sum(x[2] for x in nearest)/len(nearest)
        return _method(value,"adjacent_edition_same_id_dob",
                       ["source_year:"+str(x[1])+":"+("+".join(x[3]["source_columns"]))
                        for x in nearest],
                       self.edition,"medium_low")

    def peer_value(self,row,position,attribute):
        family=_family(position)
        ovr=_overall(row)
        nbin=int(ovr//10) if ovr is not None else -1
        # For small bins use a larger sample with the same positional family.
        local=self.peers.get((family,nbin,attribute),[])
        broad=self.peer_global.get((family,attribute),[])
        # Pooled rather than per-player invented profile.
        values=local if len(local)>=8 else broad
        if len(values)<8:return None
        val=median(values)
        if values is broad and ovr is not None:
            # Modest individual ability correction, never a copy of OVR.
            val+=.18*(ovr-70)
        return _method(val,"same_edition_position_peer_median",
                       ["peer_group:"+family,"peer_n:"+str(len(values))],
                       self.edition,"low")


def _baseline(row,position,attribute):
    """Last-resort statistical default; never hide its low provenance."""
    overall=_overall(row)
    quality=max(40,min(95,overall if overall is not None else 65))
    family=_family(position)
    if attribute.startswith("gk_"):
        # Non-keepers have low GK skills; keepers' base tracks ability.
        base=42 if family!="GK" else max(44,min(88,quality-7))
    elif family=="GK":
        base=max(40,min(82,quality-18))
    elif attribute in ("defensive_awareness","ball_winning"):
        base=quality+(-17 if family=="ATT" else -5 if family=="MID" else 3)
    elif attribute in ("finishing","offensive_awareness"):
        base=quality+(-18 if family=="DEF" else -6 if family=="MID" else 2)
    else:
        base=quality-7
    return _method(base,"position_ovr_prior",
                   ["source_overall","primary_position"],None,"very_low")


def _extra_fields(row,result):
    """PES2020 auxiliary ratings, 100% valid for export but tagged modelled.

    These are model assumptions, not claims about actual footballer character.
    """
    raw_weak=numeric(row.get("weak_foot"))
    if raw_weak is not None:
        weak=max(1,min(4,round(1+(raw_weak-1)*.75)))
        weak_method="mapped_fifa_weak_foot"
    else:
        weak=2
        weak_method="position_prior_unobserved_weak_foot"
    stamina=result["abilities"]["stamina"]["value"]
    reaction=result["abilities"]["offensive_awareness"]["value"]
    quality=(stamina+reaction)/2
    form=max(1,min(8,round(4+(quality-70)/18)))
    injury=max(1,min(3,round(2+(stamina-70)/40)))
    return {
        "weak_foot_usage":{"value":weak,"method":weak_method},
        "weak_foot_accuracy":{"value":weak,"method":weak_method},
        "form":{"value":form,"method":"low_confidence_career_form_proxy"},
        "injury_resistance":{"value":injury,"method":"low_confidence_stamina_proxy"},
    }


def convert_v2(row,edition,*,context=None,approved_calibration=None):
    ensure_edition(edition)
    if context is not None and context.edition!=edition:
        raise ConversionError("Context must match FIFA source edition")
    if approved_calibration is not None:
        if (edition!=CALIBRATION_FIFA_EDITION or
            approved_calibration.get("reference_game")!=TARGET_GAME or
            approved_calibration.get("source_edition")!=2020 or
            approved_calibration.get("status")!="approved"):
            raise ConversionError("Unapproved / cross-edition calibration")
    previous=v1_convert(row,edition)
    positions=[previous["primary_position"]]+previous["alternative_positions"]
    result={
        "model_version":MODEL_VERSION,"source_edition":edition,
        "source_player_id":previous["source_player_id"],
        "player_name":previous["player_name"],
        "source_overall":previous["source_overall"],
        "primary_position":previous["primary_position"],
        "alternative_positions":previous["alternative_positions"],
        "identity_dob":_date(row,edition),
        "abilities":{},"additional":{},
        "position_fit_indices":previous["position_fit_indices"],
        "export_status":"pending_validation",
    }
    for attr,old in previous["abilities"].items():
        if old["value"] is not None:
            value=_method(old["value"],old["method"],old["source_columns"],
                          edition,old["confidence"])
        else:
            # Preferred hierarchy: relevant same-edition measurements, then
            # same stable player in adjacent edition, then peer, then prior.
            related=_source_evidence(row,attr)
            if related:
                value=_method(related[0],"related_same_edition",
                              related[1],edition,"low")
            else:
                value=context.adjacent_value(row,attr) if context else None
                if value is None:
                    value=context.peer_value(row,previous["primary_position"],attr) if context else None
                if value is None:
                    value=_baseline(row,previous["primary_position"],attr)
        if approved_calibration and attr in approved_calibration.get("offsets",{}):
            shift=approved_calibration["offsets"][attr]
            if not isinstance(shift,(int,float)) or abs(shift)>15:
                raise ConversionError("Illegal approved calibration offset")
            value=dict(value,value=_clamp(value["value"]+shift),
                       calibration_status="approved_FIFA20_PES2020",
                       calibration_shift=shift)
        result["abilities"][attr]=value
    result["additional"]=_extra_fields(row,result)
    validate_exportable(result)
    result["export_status"]="complete_estimated_pes2020_profile"
    return result


def validate_exportable(profile):
    """Fail closed: no missing or invalid PES 2020 required numerical fields."""
    if profile["source_edition"] in DISALLOWED_EDITIONS:
        raise UnrestoredEdition("FC25 must remain a gap")
    if len(profile["abilities"])!=25 or set(profile["abilities"])!=set(TARGETS):
        raise ConversionError("Missing PES abilities")
    for key,val in profile["abilities"].items():
        n=val.get("value")
        if not isinstance(n,int) or not 40<=n<=99 or not val.get("method"):
            raise ConversionError("Invalid PES ability: "+key)
    if profile["primary_position"] not in PES_POSITIONS:
        raise ConversionError("Unknown or invalid primary PES 2020 position")
    for pos in profile["alternative_positions"]:
        if pos not in PES_POSITIONS:
            raise ConversionError("Invalid PES 2020 alternative position")
    expected={"weak_foot_usage":(1,4),"weak_foot_accuracy":(1,4),
              "form":(1,8),"injury_resistance":(1,3)}
    for name,(low,high) in expected.items():
        val=profile.get("additional",{}).get(name,{})
        n=val.get("value")
        if not isinstance(n,int) or not low<=n<=high or not val.get("method"):
            raise ConversionError("Invalid auxiliary PES rating: "+name)
    if not profile.get("player_name"):
        raise ConversionError("Player identity missing")
    return True

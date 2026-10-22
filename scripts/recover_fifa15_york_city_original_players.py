"""Recover actual FIFA15 York City game players from pinned MIT SoFIFA archive.

Reads a single original-edition historical snapshot (NOT current players).
Preserves source attributes, player IDs, club team ID, and FIFA update marker.
No PES abilities are invented and no original player dataset is overwritten.
"""
from __future__ import annotations
import argparse,csv,json,hashlib,collections
from pathlib import Path
from world_historical_competition_registry import canonical

VERSION="fifa15-york-city-original-source-player-recovery-v1"
PIN_REPO="jsulz/FIFA23"
PIN_COMMIT="80076aed77a08db5cfad31bfdfa2cebc579e9500"
SOURCE_FILE="male_players (legacy).csv"
PIN_SHA="13389f463935d257e92811eebbd50405df1a982aa45233a63d1ce075daca133e"
TARGET_TEAM=1948
SOURCE_URL=f"https://huggingface.co/datasets/{PIN_REPO}/resolve/{PIN_COMMIT}/male_players%20%28legacy%29.csv"

def clean_id(value):
    raw=str(value or "").strip()
    if not raw:return None
    try:
        n=float(raw)
        return int(n) if n.is_integer() else None
    except ValueError:
        return None

def recover(input_csv,output,require_checksum=True):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    h=hashlib.sha256()
    with open(input_csv,"rb") as f:
        for block in iter(lambda:f.read(1048576),b""):h.update(block)
    digest=h.hexdigest()
    if require_checksum and digest!=PIN_SHA:
        raise ValueError("Archived original game source SHA-256 changed")
    with open(input_csv,encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        cols=list(reader.fieldnames or [])
        required={"fifa_version","player_id","club_team_id","club_name",
                  "short_name","overall","player_positions"}
        if not required.issubset(cols):
            raise ValueError(f"Not real archived FIFA players: {required-set(cols)}")
        selected=[];seasons=collections.Counter()
        for row in reader:
            y=clean_id(row.get("fifa_version"))
            if y!=15:continue
            if clean_id(row.get("club_team_id"))!=TARGET_TEAM:continue
            if canonical(row.get("club_name"))!=canonical("York City"):
                raise ValueError("Official FIFA15 game team ID 1948 is assigned to a different club")
            pid=clean_id(row.get("player_id"))
            if pid is None or not 20<=int(float(row.get("overall") or 0))<=100:
                raise ValueError("Original FIFA15 team player missing game ID or valid rating")
            seasons[str(row.get("fifa_update") or row.get("fifa_update_date") or "")]+=1
            selected.append(row)
    if not selected:
        raise ValueError("No original FIFA15 York City game player source rows")
    players={clean_id(x["player_id"]) for x in selected}
    if len(players)!=len(selected):
        raise ValueError("Duplicate FIFA15 York City player IDs in one snapshot")
    if not 18<=len(selected)<=40:
        raise ValueError("Incomplete or excessive original York City roster; inspect snapshot")
    if not any("GK" in x.get("player_positions","").split(",") for x in selected):
        raise ValueError("Original York City game source has no actual goalkeeper")
    output_csv=output/"FIFA15_YORK_CITY_SOURCE_ATTRIBUTES_FROM_PINNED_GAME.csv"
    with output_csv.open("w",encoding="utf-8-sig",newline="") as f:
        wr=csv.DictWriter(f,fieldnames=cols)
        wr.writeheader();wr.writerows(selected)
    attr_cols=[col for col in cols if col.startswith((
        "attacking_","skill_","movement_","power_","mentality_","defending_","goalkeeping_"))]
    known_attr=sum(str(row.get(k) or "").strip().casefold() not in {"","nan","none"}
        for row in selected for k in attr_cols)
    report={
       "version":VERSION,"fifa_version":15,"season":"2014-15",
       "club":"York City","original_game_team_id":TARGET_TEAM,
       "source_game":SOURCE_URL,"original_players_recovered":len(selected),
       "unique_original_player_ids":len(players),
       "game_update_markers":dict(seasons),
       "original_fifa_attribute_columns":len(attr_cols),
       "nonempty_source_attribute_cells":known_attr,
       "original_source_sha256":digest,
       "source_snapshot_not_assumed_opening_day":True,
       "all_original_attributes_preserved_no_unknowns_invented":True,
       "PES_conversion_completed":False,
       "career_activation_approved":False,
       "original_player_catalogue_modified":False}
    (output/"FIFA15_YORK_CITY_REAL_GAME_PLAYER_RECOVERY_AUDIT.json").write_text(
      json.dumps(report,indent=2),encoding="utf-8")
    return report

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--source",required=True)
    a.add_argument("--output",required=True)
    a.add_argument("--no-checksum",action="store_true")
    x=a.parse_args()
    print(json.dumps(recover(x.source,x.output,not x.no_checksum),indent=2))

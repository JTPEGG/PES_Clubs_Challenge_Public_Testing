"""Create a provenance-labelled, complete PES free-agent supplement for FC27.

The existing 659-club snapshot stays immutable. The 256 excluded ISL-club
players are never treated as free agents. The public FC27 game free-agent list
is a separate dated snapshot; absent PES attributes are estimated using the
source-backed 25+4 attribute peer model, never silently set to zero.
"""
from __future__ import annotations
import argparse, gzip, hashlib, json, re, sqlite3, statistics, urllib.request
from datetime import date
from pathlib import Path
from bs4 import BeautifulSoup

EDITION=2027
PROFILE_DATE="2026-11-03"
SOURCE="https://www.fifacm.com/free-agents"
FIELDS=(
 "offensive_awareness","ball_control","dribbling","tight_possession",
 "low_pass","lofted_pass","finishing","heading","place_kicking","curl",
 "speed","acceleration","kicking_power","jump","physical_contact","balance",
 "stamina","defensive_awareness","ball_winning","aggression",
 "gk_awareness","gk_catching","gk_clearing","gk_reflexes","gk_reach",
 "weak_foot_usage","weak_foot_accuracy","form","injury_resistance")
MAP={"GK":"GK","CB":"CB","LB":"LB","RB":"RB","LWB":"LB","RWB":"RB",
 "CDM":"DMF","CM":"CMF","CAM":"AMF","LM":"LMF","RM":"RMF",
 "LW":"LWF","RW":"RWF","ST":"CF","CF":"SS"}
def family(pos):
    if pos=="GK":return "GK"
    if pos in ("CB","LB","RB","LWB","RWB"):return "DEF"
    if pos in ("CDM","CM","CAM","LM","RM"):return "MID"
    return "FWD"
def bound(value,lo=1,hi=99):
    return min(hi,max(lo,int(round(value))))
def records_from_pages(pages_dir=None):
    records={}
    for page in range(1,9):
        url=SOURCE+("?page="+str(page) if page>1 else "")
        if pages_dir:
            page_html=(Path(pages_dir)/f"page{page}.html").read_bytes()
        else:
            for attempt in range(4):
                try:
                    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
                    with urllib.request.urlopen(req,timeout=25) as response:
                        page_html=response.read()
                    break
                except Exception:
                    if attempt==3:raise
                    import time
                    time.sleep(1+attempt*2)
        document=BeautifulSoup(page_html,"html.parser")
        for tr in document.select("tr.player-row"):
            link=tr.select_one('a[href^="/player/"]')
            cells=tr.select("td")
            if not link or len(cells)<15:continue
            sid=re.search(r"/player/(\d+)/",link.get("href",""))
            if not sid:continue
            sid=sid.group(1)
            name=link.get_text(" ",strip=True)
            position=tr.select_one(".player-position-cln")
            pos=(position.get_text(" ",strip=True).split(",")[0].strip()
                 if position else "")
            rating=int(cells[1].get_text(" ",strip=True))
            age=int(cells[13].get_text(" ",strip=True))
            wage=cells[9].select_one(".pl-main")
            eur=(wage.get_text(" ",strip=True) if wage else "")
            wages=re.match(r"€([0-9.,]+)([KM]?)",eur)
            eur_value=(float(wages.group(1).replace(",",""))*
                {"":1,"K":1000,"M":1000000}[wages.group(2)]
                if wages else 0)
            height=re.search(r"(\d+)cm",cells[12].get_text(" ",strip=True))
            foot=cells[6].get("title","")
            flag=tr.select_one(".pl-flag img")
            nationality=flag.get("title","Unknown") if flag else "Unknown"
            records[sid]=dict(source_id=sid,name=name,position=MAP.get(pos,"CMF"),
                source_position=pos,overall=rating,age=age,
                wage_game_gbp=round(eur_value*0.85/500)*500,
                height_cm=int(height.group(1)) if height else None,
                preferred_foot=foot,nationality=nationality,
                source_url="https://www.fifacm.com"+link["href"])
    if len(records)!=212:
        raise ValueError("Public FC27 free-agent source changed: "+str(len(records)))
    return records

def build(original_path,warehouse_path,output_path,pages_dir=None):
    source=sqlite3.connect(original_path)
    warehouse=sqlite3.connect(warehouse_path)
    source.row_factory=sqlite3.Row
    records=records_from_pages(pages_dir)
    active_ids={str(x[0]) for x in warehouse.execute(
        "SELECT source_player_id FROM wh_fc27_players WHERE edition=2027")}
    historical={}
    peers=[]
    for r in source.execute("""SELECT edition,source_player_id,player_name,
          date_of_birth,primary_position,source_overall,pes_abilities_json,
          pes_additional_json,preferred_foot,nationality,height_cm,weight_kg
          FROM players WHERE edition BETWEEN 2017 AND 2027 ORDER BY edition DESC"""):
        try:
            main=json.loads(r["pes_abilities_json"])
            extra=json.loads(r["pes_additional_json"])
            a={**main,**extra}
        except (ValueError,TypeError):
            continue
        if set(a)!=set(FIELDS):continue
        if r["edition"]==2027 and len(peers)<18000:
            peers.append((r["primary_position"],r["source_overall"],a))
        sid=str(r["source_player_id"] or "")
        if sid and sid not in historical:
            historical[sid]=(r,a)
    if "233049" not in historical:raise ValueError("Jadon Sancho's 2026 source record not available")
    # Jadon was independently reported unattached in September 2026, and
    # has an FC26 PES V2 source. Never label him an official FC27 rating.
    jadon=historical["233049"][0]
    records["233049"]=dict(source_id="233049",name="Jadon Sancho",
      position=jadon["primary_position"],source_position="LM",
      overall=jadon["source_overall"],age=26,
      wage_game_gbp=0,height_cm=int(jadon["height_cm"] or 0) or None,
      preferred_foot=jadon["preferred_foot"],
      nationality=jadon["nationality"],
      source_url="https://www.skysports.com/football/news/13580813/free-agents-jadon-sancho-paul-pogba-and-dele-alli-among-players-available-on-free-transfer-after-summer-window-shuts",
      separate_historical_inclusion=True)
    result=[]
    for sid,data in sorted(records.items(),key=lambda x:int(x[0])):
        if sid in active_ids:
            continue  # Existing FC27 source player always wins over new feed
        original=historical.get(sid)
        if original:
            row,skills=original
            gap=data["overall"]-(row["source_overall"] or data["overall"])
            derived={k:bound(v+gap,-1 if k.startswith("weak_") else 1,
                5 if k in ("form","injury_resistance") else
                4 if k.startswith("weak_") else 99)
                for k,v in skills.items()}
            # Auxiliary ratings are categorical, not overall-scaled.
            for field in FIELDS[-4:]:derived[field]=skills[field]
            dob=row["date_of_birth"] or str(2026-data["age"])+"-07-01"
            name=("Jadon Sancho" if sid=="233049" else row["player_name"])
            provenance=("prior-fifa-"+str(row["edition"])+"-pes-v2-adjusted"
                +("-modelled-dob" if not row["date_of_birth"] else ""))
            weight=row["weight_kg"]
        else:
            choices=sorted(((abs((overall or 55)-data["overall"])+
                (0 if family(pos)==family(data["position"]) else 20),
                a) for pos,overall,a in peers),key=lambda x:x[0])[:18]
            if len(choices)<8:raise ValueError("Insufficient source attribute peers")
            derived={field:bound(statistics.median(x[1][field] for x in choices),
                1,4 if field.startswith("weak_") else 8 if field=="form"
                else 3 if field=="injury_resistance" else 99)
                for field in FIELDS}
            dob=str(2026-data["age"])+"-07-01" # explicitly modelled month/day
            name=data["name"]
            provenance="source-fc27-ovr-position-peer-pes-model"
            weight=None
        if any(not isinstance(v,int) or v<1 or v>200 for v in derived.values()):
            raise ValueError("PES conversion incomplete for "+name)
        if not dob or len(derived)!=29:raise ValueError("Unusable source record "+name)
        wage=data["wage_game_gbp"] or (20000 if data["overall"]>=78 else 3000)
        result.append({**data,"name":name,"dob":dob,
            "weight_kg":weight,"wage_game_gbp":int(wage),
            "pes_attributes":derived,"ratings_provenance":provenance,
            "snapshot_date":PROFILE_DATE})
    if len(result)<195:
        raise ValueError("Too many FC27 free agents collide with source clubs: "+str(len(result)))
    output=Path(output_path)
    output.parent.mkdir(parents=True,exist_ok=True)
    payload=dict(version="FC27-free-agents-v1",source=SOURCE,
        source_snapshot=PROFILE_DATE,official_659_clubs_unchanged=True,
        excluded_isl_players_not_free_agents=256,players=result)
    raw=(json.dumps(payload,ensure_ascii=False,separators=(",",":"),sort_keys=True)+"\n").encode()
    with gzip.open(output,"wb",compresslevel=9) as target:target.write(raw)
    print(json.dumps(dict(source_list=len(records),imported=len(result),
        prior_fifa=sum(p["ratings_provenance"].startswith("prior") for p in result),
        peer_estimate=sum(p["ratings_provenance"].startswith("source") for p in result),
        sancho=sum(p["source_id"]=="233049" for p in result),
        sha256=hashlib.sha256(output.read_bytes()).hexdigest()),indent=2),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--original",required=True)
    p.add_argument("--warehouse",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--pages-dir")
    args=p.parse_args()
    build(args.original,args.warehouse,args.output,args.pages_dir)

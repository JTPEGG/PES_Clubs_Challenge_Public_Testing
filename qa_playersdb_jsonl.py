"""Inspect PlayersDB public JSONL record schema for extra FIFA IDs and stats."""
import json
from urllib.request import Request,urlopen
from pathlib import Path
URL="https://playersdb.app/download/jsonl"
def main():
    try:
        req=Request(URL,headers={"User-Agent":"PES-Challenge-DataPilot/1.0"})
        with urlopen(req,timeout=70) as f:
            line=f.readline(512_000).decode("utf-8-sig",errors="replace")
        r=json.loads(line)
        keys=sorted(r.keys()) if isinstance(r,dict) else []
        out={"status":"first_record_read","source_url":URL,
             "keys":keys,"value_types":{k:type(r[k]).__name__ for k in keys},
             "has_external_ea_id":any("fifa" in k.lower() or "sofifa" in k.lower()
                  or "eaid" in k.lower().replace("_","") for k in keys),
             "has_ability":any("stats" in k.lower() or "abilities" in k.lower()
                  or "attributes" in k.lower() for k in keys)}
    except Exception as e:
        out={"status":"unavailable","error":str(e)[:200]}
    print("PLAYERSDB JSONL AUDIT",json.dumps(out,indent=2),flush=True)
    Path("qa-conversion-pilot/playersdb-jsonl-schema.json").write_text(
        json.dumps(out,indent=2),encoding="utf-8")
if __name__=="__main__":main()

"""Check PlayersDB's actual advertised CSV download for PES historical IDs.

Source page confirmed to link https://playersdb.app/download/csv.
Inspect metadata and 100-sample FC27 ID overlap; do not republish player
records or alter any existing career database.
"""
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path
from urllib.request import urlopen,Request
from world_fc27_english import FC27_PLAYERS

URL="https://playersdb.app/download/csv"
LIMIT=85_000_000


def fetch():
    req=Request(URL,headers={"User-Agent":"PES-Clubs-Challenge-source-research/1.0",
                            "Accept":"text/csv,*/*"})
    with urlopen(req,timeout=80) as response:
        body=response.read(LIMIT+1)
        ctype=response.headers.get("Content-Type","")
    if len(body)>LIMIT:raise ValueError("CSV too large for QA")
    if body[:300].lower().find(b"<html")>=0:
        raise ValueError("Returned HTML instead of database CSV")
    return body,ctype


def inspect(body):
    text=body.decode("utf-8-sig",errors="replace")
    reader=csv.DictReader(io.StringIO(text))
    cols=reader.fieldnames or []
    sample_ids={str(x[0]) for x in FC27_PLAYERS}
    # Build no assumptions about schema; inspect actual headers first.
    cols_norm={col.lower().replace("_","").replace(" ",""):col for col in cols}
    id_fields=[
        c for c in cols if any(pat in c.lower().replace("_","")
                                for pat in ("fifaid","eaid","sofifaid","konamiid",
                                            "pesid","fm id","fmid"))
    ]
    fifa_cols=[c for c in id_fields if any(x in c.lower().replace("_","")
                                          for x in ("fifaid","eaid","sofifaid"))]
    fifa_field=fifa_cols[0] if len(fifa_cols)==1 else None
    n=0; matches=set();by_version=Counter()
    versions=[c for c in cols if "game_version" in c.lower() or "versions" in c.lower()]
    for row in reader:
        n+=1
        if fifa_field:
            value=str(row.get(fifa_field) or "").strip()
            if value in sample_ids:matches.add(value)
        for ver in versions[:2]:
            val=str(row.get(ver) or "").strip()
            if val and len(by_version)<100:
                by_version[val[:60]]+=1
    return {
        "status":"verified_csv_download","download_bytes":len(body),
        "sha256":hashlib.sha256(body).hexdigest(),
        "column_count":len(cols),"column_names":cols,
        "player_rows":n,"id_columns":id_fields,"fifa_id_column":fifa_field,
        "fc27_source_ids_overlap_all_2498":len(matches),
        "game_version_fields":versions,
        "game_version_breakdown_if_unambiguous":dict(by_version.most_common(25)),
        "source_url":URL,
        "limitations":"Snapshot may combine PES editions and patches; do not assume every player has every PES2020 stat or a verified FIFA ID."
    }


def main():
    Path("qa-conversion-pilot").mkdir(exist_ok=True)
    try:
        body,content_type=fetch()
        result=inspect(body)
        result["response_content_type"]=content_type
    except Exception as ex:
        result={"status":"unavailable_or_unparsable",
                "error":type(ex).__name__+": "+str(ex)[:400],
                "source_url":URL}
    Path("qa-conversion-pilot/playersdb-download-check.json").write_text(
        json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    print("PLAYERSDB AUDIT",json.dumps(result,indent=2),flush=True)


if __name__=="__main__":
    main()

"""Inspect actual public PlayersDB download URLs linked by their web page.

No guessed REST route, no bulk file ingested automatically. Pin a release only
when its visible public link, schema and game-version field have been verified.
"""
from html.parser import HTMLParser
from urllib.request import Request,urlopen
import json
from pathlib import Path
from urllib.parse import urljoin,urlparse

URL="https://playersdb.app/"
class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[]
        self.last=None
    def handle_starttag(self,tag,attrs):
        if tag!="a":return
        d=dict(attrs)
        self.last=d.get("href")
        if self.last:
            self.links.append({"href":self.last,"text":""})
    def handle_data(self,data):
        if self.links:self.links[-1]["text"]+=data.strip()


def run():
    try:
        with urlopen(Request(URL,headers={"User-Agent":"PES-Challenge-Data-Pilot/1.0"}),timeout=15) as r:
            content=r.read(900_000).decode("utf-8",errors="replace")
        parser=Links();parser.feed(content)
        selected=[]
        for link in parser.links:
            h=link["href"]
            joined=urljoin(URL,h)
            if any(word in (h+" "+link["text"]).casefold()
                   for word in ("csv","jsonl","download","export")):
                selected.append({"label":link["text"][:60],
                                 "url":joined,"host":urlparse(joined).netloc})
        result={"status":"download_link_candidates",
                "public_page":URL,"links":selected,
                "notice":"Links from site HTML, not yet checked as full data exports."}
    except Exception as exc:
        result={"status":"unavailable","error":str(exc)[:200],
                "public_page":URL}
    print(json.dumps(result,indent=2),flush=True)
    Path("qa-conversion-pilot").mkdir(exist_ok=True)
    Path("qa-conversion-pilot/playersdb-download-links.json").write_text(
        json.dumps(result,indent=2),encoding="utf-8")


if __name__=="__main__":
    run()

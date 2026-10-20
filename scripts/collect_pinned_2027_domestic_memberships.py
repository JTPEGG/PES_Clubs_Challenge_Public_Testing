"""Pinned 2026/27 independently published fixture membership review for FC27.

Uses a fixed, immutable source snapshot. Only original fixture team *names*
are collected, never match results, rosters or unsupported promotions.
Independent site has no explicit data licence: attribution and source hash
are retained; redistribution of its raw match feed is prohibited here.
This is a REVIEW/STAGING data source, not certification of game club identity.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import urllib.request
from collections import Counter,defaultdict
from datetime import date
from pathlib import Path

PIN="0e39da91fb053a2ed355d9b69cef5aec6d7ae3f1"
BASE=f"https://raw.githubusercontent.com/oladeeayo/open-matchday/{PIN}/data"
EDITION=2027
VERSION="fifa27-season-fixture-membership-evidence-v1"
# These team counts are sanity constraints, not replacements for actual lists.
# Missing or ambiguous season data is quarantined rather than fabricated.
SOURCES=(
 ("en.3","ENG_3_league-one","England",3,24,"League One",False),
 ("en.4","ENG_4_league-two","England",4,24,"League Two",False),
 ("en.5","ENG_5_national-league","England",5,24,"National League",False),
 ("en.6n","ENG_6_national-league-north","England",6,24,"National League North",False),
 ("en.6s","ENG_6_national-league-south","England",6,24,"National League South",False),
 ("de.3","GER_3_3-liga","Germany",3,20,"3. Liga",False),
 ("es.2","ESP_2_segunda-division","Spain",2,22,"Segunda División",False),
 ("it.2","ITA_2_serie-b","Italy",2,20,"Serie B",False),
 ("fr.2","FRA_2_ligue-2","France",2,18,"Ligue 2",False),
 ("us.mls","USA_1_mls","United States / Canada",1,30,"Major League Soccer",True),
 ("ar.1","ARG_1_liga-profesional","Argentina",1,30,"Primera División",True),
 ("jp.1","JPN_1_j1-league","Japan",1,20,"J1 League",True),
 ("tr.1","TUR_1_super-lig","Turkey",1,18,"Süper Lig",False),
 ("sco.2","SCO_2_championship","Scotland",2,10,"Scottish Championship",False),
 ("sco.3","SCO_3_league-one","Scotland",3,10,"Scottish League One",False),
 ("sco.4","SCO_4_league-two","Scotland",4,10,"Scottish League Two",False),
)
# Explicit provider display aliases; no fuzzy or country guessing.
ALIASES={
 "Los Angeles Football Club":"LAFC",
 "New York City Football Club":"New York City FC",
 "Orlando City SC":"Orlando City",
 "Vancouver Whitecaps":"Vancouver Whitecaps FC",
 "Milton Keynes Dons":"MK Dons",
}
NOT_LEAGUE_CLUBS={"MLS All-Stars","Liga MX All-Stars"}

def canonical_team(raw):
    raw=raw.strip()
    if not raw:
        raise ValueError("Empty club name")
    return ALIASES.get(raw,raw)

def parse_matches(text, *, calendar, code):
    lines=csv.DictReader(io.StringIO(text))
    if not {"date","home","away"}.issubset(lines.fieldnames or []):
        raise ValueError("Unexpected match source format")
    rows=[]
    for row in lines:
        day=date.fromisoformat(row["date"])
        if not (date(2026,1,1)<=day<=date(2026,12,31) if calendar
                else date(2026,7,1)<=day<=date(2027,6,30)):
            raise ValueError(f"Out-of-edition source date in {code}")
        raw=[(row.get(c) or "").strip() for c in ("home","away")]
        if any(c in NOT_LEAGUE_CLUBS for c in raw):
            # The MLS source has an all-stars event mixed with league results.
            # Reject non-club matches rather than treating them as promotion.
            continue
        home,away=map(canonical_team,raw)
        if home==away:
            raise ValueError("Self-play fixture in pinned season source")
        rows.append((home,away))
    if not rows:
        raise ValueError("Empty fixture collection")
    return rows

def get(url):
    req=urllib.request.Request(url,headers={
        "User-Agent":"PES-Club-Challenge-historical-fixture-evidence"})
    with urllib.request.urlopen(req,timeout=30) as response:
        raw=response.read()
    return raw.decode("utf-8-sig"),hashlib.sha256(raw).hexdigest()

def collect(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    competitions=[];memberships=[];skipped=[];source_stats=Counter()
    for code,folder,country,tier,count,name,calendar in SOURCES:
        matches=[];urls=[];checks=[]
        try:
            for kind in ("results","fixtures"):
                url=f"{BASE}/{folder}/{kind}_2627.csv"
                body,sha=get(url)
                batch=parse_matches(body,calendar=calendar,code=code)
                matches+=batch
                urls.append(url);checks.append(sha)
            names=sorted({club for match in matches for club in match})
            if len(names)!=count:
                raise ValueError(f"expected {count} distinct clubs, saw {len(names)}")
            if len(matches)<count*4:
                raise ValueError(f"Insufficient fixture evidence: {len(matches)}")
        except (ValueError,OSError) as exc:
            skipped.append((EDITION,code,folder,str(exc)))
            source_stats["quarantined"]+=1
            continue
        # Combined SHA covers both source files and preserves order.
        evidence_sha=hashlib.sha256(("|".join(checks)).encode("ascii")).hexdigest()
        source_url=urls[0]
        competitions.append((EDITION,"2026" if calendar else "2026-27",
            code,country,tier,name,source_url,
            "pinned_independent_fixture_membership_review",len(names),
            len(matches),evidence_sha))
        for team in names:
            memberships.append((EDITION,code,country,tier,name,team,
                source_url,evidence_sha,
                "source_observation_pending_game_identity_review"))
        source_stats["verified_source_file_pairs"]+=1
    def output_csv(filename,cols,rows):
        with (out/filename).open("w",encoding="utf-8-sig",newline="") as f:
            w=csv.writer(f);w.writerow(cols);w.writerows(rows)
    output_csv("FC27_PINNED_CURRENT_COMPETITION_SEASONS.csv",
        ("Edition","Starting_Season","League_Code","Country","Tier","Competition",
         "Source_URL","Evidence_Status","Parsed_Teams","Fixture_Count",
         "Source_SHA256"),competitions)
    output_csv("FC27_PINNED_CURRENT_SOURCE_CLUBS.csv",
        ("Edition","League_Code","Country","Tier","Competition","Fixture_Club",
         "Source_URL","Source_SHA256","Evidence_Status"),memberships)
    output_csv("FC27_SOURCE_REJECTIONS.csv",
        ("Edition","League_Code","Folder","Rejection_Reason"),skipped)
    audit={"edition":EDITION,"pinned_commit":PIN,
           "source_repository":"oladeeayo/open-matchday",
           "source_license":"not declared; only fixture participants/facts used, never raw match feed",
           "source_season_calendar":"2026 for annual leagues; 2026-27 for autumn-spring",
           "independently_observed_competitions":len(competitions),
           "independently_observed_club_memberships":len(memberships),
           "rejected_competitions":len(skipped),
           "counts_by_family":dict(source_stats),
           "staging_only":True,
           "game_club_identity_confirmed":False,
           "career_ready":False,
           "manufactured_game_players":0}
    (out/"FC27_PINNED_CURRENT_MEMBERSHIP_AUDIT.json").write_text(
        json.dumps(audit,indent=2),encoding="utf-8")
    return audit

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    args=p.parse_args()
    print(json.dumps(collect(args.output),indent=2))

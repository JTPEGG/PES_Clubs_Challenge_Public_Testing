"""Audit exact game-version EA team IDs in an archived 2015-23 team export.

This is a second ORIGINAL-GAME league identity source, not a contemporary
league fixture inference. Never assign a club based only on its display name,
and never re-use a later FIFA team's league in an earlier edition.
"""
from __future__ import annotations
import argparse,csv,json,re,sqlite3
from collections import Counter,defaultdict
from pathlib import Path
from world_historical_competition_registry import canonical,cup_group

VERSION="pinned-sofifa-fifa15-23-game-team-id-identity-audit-v1"
GAME_KEY=re.compile(r"(?:^|:)id:(\d+)(?:-|$)")
COVERED=set(range(2015,2024))
BLOCK_LABELS=("rest of world","conmebol","uefa","national teams","international","free agents")

def eid(key):
    m=GAME_KEY.search(str(key))
    return int(m.group(1)) if m else None

def edition_of(raw):
    raw=str(raw).strip()
    if not raw.isdigit():return None
    y=int(raw)
    return y+2000 if 15<=y<=23 else y if 2015<=y<=2023 else None

def viable_league(league,level):
    name=str(league or "").strip()
    if not name or any(x in name.casefold() for x in BLOCK_LABELS) or cup_group(name):
        return False
    try:
        return 1<=int(float(level))<=5
    except (ValueError,TypeError):
        return False

def audit(source_sqlite,team_csv,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(f"file:{Path(source_sqlite).resolve()}?mode=ro",uri=True) as db:
        originals=[(int(y),str(key),str(name),str(group or "")) for y,key,name,group
            in db.execute("SELECT edition,club_key,name,league_key FROM clubs")]
    target=defaultdict(list)
    for edition,key,name,group in originals:
        id_value=eid(key)
        if edition in COVERED and id_value is not None:
            target[(edition,id_value)].append((key,name,group))
    evidence=defaultdict(list);stats=Counter()
    with open(team_csv,encoding="utf-8-sig",newline="") as h:
        rd=csv.DictReader(h)
        columns={"team_id","fifa_version","team_name","league_id","league_name","league_level"}
        if not columns.issubset(rd.fieldnames or []):
            raise ValueError(f"Missing source EA identity fields: {columns-set(rd.fieldnames or [])}")
        for row in rd:
            edition=edition_of(row.get("fifa_version"))
            if edition is None:continue
            try:idv=int(row["team_id"])
            except (ValueError,TypeError):continue
            if (edition,idv) not in target:continue
            stats["matching_edition_and_id_observations"]+=1
            league=row["league_name"]
            level=row["league_level"]
            if not viable_league(league,level):
                stats["non_domestic_or_undetermined_rows"]+=1
                continue
            evidence[(edition,idv)].append((
                str(row.get("team_name") or "").strip(),
                str(row["league_id"]).strip(),
                str(league).strip(),
                int(float(level)),
                str(row.get("nationality_name") or "").strip(),
                str(row.get("fifa_update") or "").strip(),
                str(row.get("fifa_update_date") or "").strip()))
            stats["valid_domestic_team_observations"]+=1
    passed=[];review=[];matched_club_ids=set()
    for idkey,orig in sorted(target.items()):
        if len(orig)!=1:
            review.append((idkey[0],idkey[1],"multiple_original_game_clubs",
                           " | ".join(r[1] for r in orig),"","",""))
            continue
        k,n,original_league=orig[0]
        candidates=evidence.get(idkey,[])
        if not candidates:
            stats["game_ids_without_domestic_source"]+=1
            continue
        variants={(e[1],e[2],e[3],e[4]) for e in candidates}
        if len(variants)!=1:
            review.append((idkey[0],idkey[1],"changed_game_league_across_updates",
                           n," | ".join(sorted({x[2] for x in candidates})),"",""))
            continue
        league_id,league_name,level,country=next(iter(variants))
        original_names={canonical(e[0]) for e in candidates}
        game_name=canonical(n)
        names_consistent=(game_name in original_names)
        if not names_consistent:
            # Source archive IDs may be provider-local numbers rather than
            # EA official game IDs. Numeric collision without team name
            # corroboration must NEVER be considered an ID join.
            review.append((idkey[0],idkey[1],
                           "numeric_id_collision_club_name_disagrees",
                           n,league_name,country,league_id))
            continue
        if not country or not league_id.isdigit():
            review.append((idkey[0],idkey[1],"missing_country_or_league_id",
                           n,league_name,country,league_id))
            continue
        passed.append((idkey[0],idkey[1],k,n,
            next(iter(sorted(set(e[0] for e in candidates)))),
            league_id,league_name,country,level,len(candidates),
            "exact_edition_and_EA_team_id_same_name",
            "game_team_league_not_independent_real_division"))
        matched_club_ids.add(idkey)
    def dump(name,heads,rows):
        with (out/name).open("w",encoding="utf-8-sig",newline="") as h:
            wr=csv.writer(h);wr.writerow(heads);wr.writerows(rows)
    dump("EA_GAME_TEAM_LEAGUE_EXACT_ID_REVIEW.csv",
        ("Edition","EA_Team_ID","Original_Club_Key","Original_Club",
         "Dataset_Team_Name","Original_Game_League_ID","Game_League_Name",
         "Game_Team_Country","Game_League_Level","Observations",
         "Identity_Confidence","Evidence_Limit"),passed)
    dump("EA_GAME_TEAM_LEAGUE_CONFLICTS.csv",
        ("Edition","EA_Team_ID","Reason","Original_Club","League","Country","League_ID"),review)
    report={
      "version":VERSION,"editions":sorted(COVERED),
      "source":"jsulz/FIFA23 archived SoFIFA mens teams by original edition/EA ID",
      "original_game_club_rows":len(originals),
      "original_edition_team_ids":sum(len(x) for x in target.values()),
      "unique_original_edition_team_id_keys":len(target),
      "same_edition_ea_game_ids_with_domestic_league":len(passed),
      "exact_id_plus_name":sum(x[10]=="exact_edition_and_EA_team_id_same_name" for x in passed),
      "same_ea_id_name_discrepancy_review":sum(x[2]=="numeric_id_collision_club_name_disagrees" for x in review),
      "conflicting_or_unidentified":len(review),
      "game_clubs_without_domestic_source":stats["game_ids_without_domestic_source"],
      "source_rows_examined":dict(stats),
      "domestic_memberships_are_historic_game_evidence_only":True,
      "no_cross_edition_club_migration":True,
      "no_auto_career_ready":True,
      "original_game_squads_modified":False}
    (out/"EA_GAME_TEAM_ID_LEAGUE_AUDIT.json").write_text(
        json.dumps(report,indent=2),encoding="utf-8")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True)
    p.add_argument("--teams",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    print(json.dumps(audit(a.source,a.teams,a.output),indent=2))
